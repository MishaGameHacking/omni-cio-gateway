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

spec = importlib.util.spec_from_file_location("shell_release", Path(__file__).with_name("publish_owner56_shell.py"))
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)
prepare_spec = importlib.util.spec_from_file_location('owner56_prepare',
    Path(__file__).parents[1] / 'tools/prepare_owner56_shell.py')
prepare = importlib.util.module_from_spec(prepare_spec)
prepare_spec.loader.exec_module(prepare)


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
            "owner_password_status": 200, "owner_binding_preserved": True,
            "owner_configuration_preserved": True,
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

    def test_new_client_requires_deployed_password_entrypoints_and_preserved_owner(self):
        for key, value in [('owner_password_status', 404), ('owner_binding_preserved', False),
                           ('owner_configuration_preserved', False)]:
            with self.subTest(key=key):
                meta, receipt, read = self.runtime_fixture()
                receipt[key] = value
                with mock.patch.object(release, 'regular', side_effect=read):
                    with self.assertRaisesRegex(RuntimeError, 'required_runtime_not_deployed'):
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



class VisualIdentityTests(unittest.TestCase):
    def fixture(self, *, source='a' * 40, omit=False, tamper=False, mixed_parent=False, **changes):
        report = {'source_commit': source, 'host': 'LAPTOP-NPSGA016',
            'status': 'rendered-awaiting-visual-review', 'fixture': 'synthetic-Layoutlib-no-network',
            'baseline_updated': False, 'owned_processes_after': 0,
            'signing_identity_unchanged': True, 'native_acceptance': False,
            'required_preview_prefixes': sorted(prepare.REQUIRED_PREVIEWS), 'screenshots': []}
        rows = []
        prefixes = sorted(prepare.REQUIRED_PREVIEWS)
        for prefix in prefixes[:-1] if omit else prefixes:
            name, raw = prefix + '_synthetic.png', b'synthetic screenshot identity'
            report['screenshots'].append({'path': name, 'bytes': len(raw),
                                          'sha256': hashlib.sha256(raw).hexdigest()})
            parent = 'another-evidence' if mixed_parent else 'owner56-visual-40900000000-1'
            rows.append((parent + '/screens/' + name,
                         b'x' * len(raw) if tamper else raw))
        report.update(changes)
        rows.append(('owner56-visual-40900000000-1/result.json', json.dumps(report).encode()))
        _, raw = package(rows)
        return raw, hashlib.sha256(raw).hexdigest()

    def test_reviewed_visual_bytes_cover_all_required_screens(self):
        raw, expected = self.fixture()
        result = prepare.verify_visual(raw, 'a' * 40, expected)
        self.assertEqual(result['visual_artifact_sha256'], expected)
        self.assertFalse(result['native_acceptance'])

    def test_another_source_or_failed_cleanup_is_rejected(self):
        for changes in ({'source': 'b' * 40}, {'owned_processes_after': 1},
                        {'baseline_updated': True}, {'status': 'failed'},
                        {'signing_identity_unchanged': False}, {'signing_identity_unchanged': None},
                        {'native_acceptance': True}):
            with self.subTest(changes=changes):
                raw, expected = self.fixture(**changes)
                with self.assertRaisesRegex(RuntimeError, 'visual_receipt_changed'):
                    prepare.verify_visual(raw, 'a' * 40, expected)

    def test_missing_owner_screen_is_rejected(self):
        raw, expected = self.fixture(omit=True)
        with self.assertRaisesRegex(RuntimeError, 'visual_inventory_incomplete'):
            prepare.verify_visual(raw, 'a' * 40, expected)

    def test_screenshot_content_is_verified_independently(self):
        raw, expected = self.fixture(tamper=True)
        with self.assertRaisesRegex(RuntimeError, 'visual_screenshot_changed'):
            prepare.verify_visual(raw, 'a' * 40, expected)

    def test_screenshots_from_another_evidence_directory_cannot_satisfy_receipt(self):
        raw, expected = self.fixture(mixed_parent=True)
        with self.assertRaisesRegex(RuntimeError, 'visual_screenshot_missing'):
            prepare.verify_visual(raw, 'a' * 40, expected)

    def test_different_archive_digest_is_rejected_before_reading(self):
        raw, _ = self.fixture()
        with self.assertRaisesRegex(RuntimeError, 'visual_artifact_changed'):
            prepare.verify_visual(raw, 'a' * 40, '0' * 64)


if __name__ == "__main__":
    unittest.main()

