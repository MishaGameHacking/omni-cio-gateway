"""Regressions at the private transport's cost, ownership and integrity boundaries."""
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import timeweb_ci_transfer as transfer


class TransferTests(unittest.TestCase):
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
