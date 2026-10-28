"""Synthetic publication input checks; never connects to Timeweb or a device."""
import hashlib
import json
from unittest import mock
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
import zipfile

spec = importlib.util.spec_from_file_location("shell_release", Path(__file__).with_name("publish_workspace_shell.py"))
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def package(rows):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        for name, raw in rows:
            archive.writestr(name, raw)
    payload = data.getvalue()
    meta = {"payload_bytes": len(payload), "payload_sha256": hashlib.sha256(payload).hexdigest(),
            "members": {name: {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()} for name, raw in rows}}
    return meta, payload


class PublicationInputs(unittest.TestCase):

    def runtime_fixture(self):
        raw = b"verified runtime"
        meta = {"source_commit": "b" * 40, "test_run_id": "40799999999",
            "runtime_source_commit": "a" * 40, "runtime_test_run_id": "40718753255",
            "runtime_deploy_run_id": "40721312988"}
        receipt = {"status": "deployed", "source_commit": "a" * 40,
            "test_run_id": "40718753255", "unauthenticated_presentation": 401,
            "installed_sha256": {"strategy_profiles.py": hashlib.sha256(raw).hexdigest()}}
        def read(path, maximum):
            return json.dumps(receipt).encode() if path.name == "deployment.json" else raw
        return meta, receipt, read

    def test_client_and_runtime_revisions_are_separate_verified_identities(self):
        meta, _, read = self.runtime_fixture()
        with mock.patch.object(release, "regular", side_effect=read):
            release.verify_runtime(meta)

    def test_unverified_runtime_identity_is_rejected(self):
        meta, receipt, read = self.runtime_fixture()
        receipt["source_commit"] = "c" * 40
        with mock.patch.object(release, "regular", side_effect=read):
            with self.assertRaisesRegex(RuntimeError, "required_runtime_not_deployed"):
                release.verify_runtime(meta)

    def test_exact_three_members_are_preserved(self):
        rows = [("app-preview.apk", b"synthetic"), ("apk-verification.json", b"{}"), ("build-result.json", b"{}")]
        meta, payload = package(rows)
        self.assertEqual(release.unpack(meta, payload), dict(rows))

    def test_changed_archive_is_rejected(self):
        meta, payload = package([("app-preview.apk", b"a"), ("apk-verification.json", b"b"), ("build-result.json", b"c")])
        with self.assertRaisesRegex(RuntimeError, "payload_changed"):
            release.unpack(meta, payload + b"changed")

    def test_member_hash_is_checked_independently(self):
        meta, payload = package([("app-preview.apk", b"a"), ("apk-verification.json", b"b"), ("build-result.json", b"c")])
        meta["members"]["app-preview.apk"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(RuntimeError, "member_changed"):
            release.unpack(meta, payload)

    def test_duplicate_members_are_rejected(self):
        meta, payload = package([("app-preview.apk", b"a"), ("app-preview.apk", b"b"), ("build-result.json", b"c")])
        with self.assertRaisesRegex(RuntimeError, "member_changed|unexpected_payload_members"):
            release.unpack(meta, payload)

    def test_saved_evidence_is_idempotent_and_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            release.save_new(path, b"first")
            release.save_new(path, b"first")
            with self.assertRaisesRegex(RuntimeError, "existing_file_conflict"):
                release.save_new(path, b"different")
            self.assertEqual(path.read_bytes(), b"first")


if __name__ == "__main__":
    unittest.main()
