"""Regressions at the private transport's cost, ownership and integrity boundaries."""
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import timeweb_ci_transfer as transfer
import ci_apk_archive as apk_archive


class TransferTests(unittest.TestCase):
    def test_credential_lookup_never_selects_another_storage_user(self):
        users = {"users": [{"access_key": "other", "secret_key": "other-secret"},
                           {"access_key": "selected", "secret_key": "selected-secret"}]}
        self.assertEqual(transfer.matching_secret(users, "selected"), "selected-secret")
        with self.assertRaisesRegex(transfer.ProbeError, "matching_storage_user_missing"):
            transfer.matching_secret(users, "missing")
        masked = {"users": [{"access_key": "selected", "secret_key": "********"}]}
        with self.assertRaisesRegex(transfer.ProbeError, "storage_key_masked"):
            transfer.matching_secret(masked, "selected")

    def test_hidden_credentials_stop_before_any_other_credential_lookup(self):
        bucket = {"secret_key": transfer.HIDDEN_CREDENTIAL}
        with patch.object(transfer, "read_path") as read:
            with self.assertRaisesRegex(transfer.ProbeError, "hidden_by_token_policy"):
                transfer.client("synthetic-token", bucket)
        read.assert_not_called()

    def test_archive_binds_exact_head_and_rejects_extra_members_before_writing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, target = root / "source", root / "target"
            source.mkdir()
            target.mkdir()
            for name in apk_archive.FILES:
                path = source / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(("synthetic-" + name).encode())
            with patch.dict(os.environ, {"GITHUB_SHA": "a" * 40}):
                data = apk_archive.pack(source, source / "previous.apk")
                apk_archive.unpack(data, target)
                self.assertEqual((source / apk_archive.FILES[0]).read_bytes(), (target / apk_archive.FILES[0]).read_bytes())
                bad = io.BytesIO(data)
                with zipfile.ZipFile(bad, "a") as archive:
                    archive.writestr("../escape", "unexpected")
                invalid_data = bad.getvalue()
                with self.assertRaisesRegex(transfer.ProbeError, "members_invalid"):
                    apk_archive.unpack(invalid_data, target)
            with patch.dict(os.environ, {"GITHUB_SHA": "b" * 40}), self.assertRaisesRegex(transfer.ProbeError, "identity_mismatch"):
                apk_archive.unpack(data, target)
            self.assertFalse((root / "escape").exists())

    def test_empty_recovery_rejects_nonempty_owned_bucket(self):
        with patch.object(transfer, "find_bucket", return_value={"object_amount": 1}), \
                patch.object(transfer, "delete_bucket") as delete:
            with self.assertRaisesRegex(transfer.ProbeError, "not_empty"):
                transfer.cleanup_empty("synthetic-token")
        delete.assert_not_called()

    def test_delete_refusal_is_not_hidden_without_independent_absence(self):
        with patch.object(transfer, "storage_request", side_effect=transfer.ProbeError("storage_http_403")), \
                patch.object(transfer, "find_bucket", return_value=None):
            transfer.delete_bucket("synthetic-token", {"id": 17})
        with patch.object(transfer, "storage_request", side_effect=transfer.ProbeError("storage_http_403")), \
                patch.object(transfer, "find_bucket", return_value={"id": 17}), \
                patch.object(transfer.time, "sleep"):
            with self.assertRaisesRegex(transfer.ProbeError, "storage_http_403"):
                transfer.delete_bucket("synthetic-token", {"id": 17})

    def test_sdk_diagnostics_never_echo_original_message(self):
        error = RuntimeError("secret-value")
        error.response = {"Error": {"Code": "AccessDenied", "Message": "secret-value"}}
        error.operation_name = "GetBucketAcl"
        self.assertEqual(transfer.error_summary(error), {
            "code": "RuntimeError", "s3_code": "AccessDenied", "operation": "GetBucketAcl"})

    def test_credentials_cannot_be_sent_to_arbitrary_endpoints(self):
        for host in ("https://example.invalid", "http://s3.twcstorage.ru", "s3.twcstorage.ru.evil.invalid",
                     "https://user:secret@s3.twcstorage.ru", "https://s3.twcstorage.ru/path"):
            with self.subTest(host=host), self.assertRaises(transfer.ProbeError):
                transfer.endpoint(host)
        self.assertEqual(transfer.endpoint("s3.twcstorage.ru"), "https://s3.twcstorage.ru")

    def test_only_small_offer_within_budget_is_selected(self):
        base = {"id": 1, "disk": 1024, "price": 1, "storage_class": "standard"}
        offers = {"storages_presets": [dict(base, id=2, price=99), dict(base, id=3, disk=10240), base]}
        self.assertEqual(transfer.select_offer(offers), base)
        with self.assertRaisesRegex(transfer.ProbeError, "within_budget"):
            transfer.select_offer({"storages_presets": [dict(base, price=99)]})

    def test_bucket_from_another_project_head_or_visibility_cannot_be_used(self):
        good = {"id": 1, "name": "test", "description": "head", "project_id": transfer.PROJECT_ID, "type": "private"}
        with patch.object(transfer, "identity", return_value=("test", "head")):
            self.assertEqual(transfer.owned_bucket(good), good)
            for change in ({"id": True}, {"description": "other-head"}, {"type": "public"}, {"project_id": 2}):
                with self.subTest(change=change), self.assertRaises(transfer.ProbeError):
                    transfer.owned_bucket({**good, **change})

    def test_tampered_download_fails_and_closes_stream(self):
        stream = io.BytesIO(b"tampered")
        s3 = Mock()
        s3.get_object.return_value = {"Body": stream}
        with self.assertRaisesRegex(transfer.ProbeError, "integrity_mismatch"):
            transfer.read_bytes(s3, {"name": "test"}, expected_hash="0" * 64)
        self.assertTrue(stream.closed)

    def test_public_group_permissions_are_rejected(self):
        s3 = Mock()
        s3.get_bucket_acl.return_value = {"Grants": [{"Grantee": {"Type": "Group"}}]}
        with self.assertRaisesRegex(transfer.ProbeError, "public_bucket_acl"):
            transfer.require_private(s3, {"name": "test"})

    def test_cleanup_preserves_unexpected_objects(self):
        s3 = Mock()
        s3.list_objects_v2.return_value = {"Contents": [{"Key": "unrelated"}]}
        with patch.object(transfer, "find_bucket", return_value={"name": "test"}), \
                patch.object(transfer, "client", return_value=s3), \
                patch.object(transfer, "storage_request") as request:
            with self.assertRaisesRegex(transfer.ProbeError, "unexpected_objects"):
                transfer.cleanup("synthetic-token")
        request.assert_not_called()
        s3.delete_object.assert_not_called()


if __name__ == "__main__":
    unittest.main()
