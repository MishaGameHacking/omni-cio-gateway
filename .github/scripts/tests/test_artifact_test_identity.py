"""Driver tests with fake adb; not a real emulator installation."""
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock

SPEC = importlib.util.spec_from_file_location('artifact_test_identity', Path(__file__).resolve().parents[1] / 'artifact_test_identity.py')
identity = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(identity)


class ArtifactIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.apk = Path(self.temp.name) / 'synthetic.bin'
        self.apk.write_bytes(b'Synthetic bytes - not an APK')
        self.result = []
        self.device = Mock(return_value=Mock(returncode=0, stdout='Success\n', stderr=''))

    def test_exact_digest_is_attached(self):
        identity.record_install(self.device, self.result, 'candidate_clean_install', self.apk)
        self.assertTrue(self.result[0]['success'])
        self.assertEqual(self.result[0]['apk_sha256'], hashlib.sha256(self.apk.read_bytes()).hexdigest())

    def test_timeout_keeps_failed_record(self):
        self.device.side_effect = subprocess.TimeoutExpired('fake adb', 1)
        with self.assertRaises(subprocess.TimeoutExpired):
            identity.record_install(self.device, self.result, 'upgrade_to_candidate', self.apk, update=True)
        self.assertIs(self.result[0]['success'], False)
        self.assertEqual(self.result[0]['error_type'], 'TimeoutExpired')

    def test_changed_file_cannot_pass(self):
        def changed(*args, **kwargs):
            self.apk.write_bytes(b'Changed candidate')
            return Mock(returncode=0, stdout='Success\n', stderr='')
        self.device.side_effect = changed
        with self.assertRaises(RuntimeError):
            identity.record_install(self.device, self.result, 'candidate_clean_install', self.apk)
        self.assertIs(self.result[0]['success'], False)

    def test_success_substring_does_not_pass(self):
        self.device.return_value.stdout = 'NotSuccess'
        with self.assertRaises(RuntimeError):
            identity.record_install(self.device, self.result, 'candidate_clean_install', self.apk)
        self.assertIs(self.result[0]['success'], False)

    def test_exit_failure_cannot_pass(self):
        self.device.return_value.returncode = 1
        with self.assertRaises(RuntimeError):
            identity.record_install(self.device, self.result, 'candidate_clean_install', self.apk)

    def test_missing_file_still_leaves_failure(self):
        self.apk.unlink()
        with self.assertRaises(ValueError):
            identity.record_install(self.device, self.result, 'candidate_clean_install', self.apk)
        self.assertIs(self.result[0]['success'], False)
        self.device.assert_not_called()

    def test_no_implicit_downgrade_or_testonly_flags(self):
        identity.record_install(self.device, self.result, 'upgrade_to_candidate', self.apk, update=True)
        args, kwargs = self.device.call_args
        self.assertEqual(args, ('install', '--no-streaming', '-r', str(self.apk)))
        self.assertEqual(kwargs, {'timeout': 240})


if __name__ == '__main__':
    unittest.main()
