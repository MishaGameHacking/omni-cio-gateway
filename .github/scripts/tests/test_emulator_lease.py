"""OS/process regression tests; no emulator, phone or network is used here."""
import importlib.util
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

MODULE = Path(__file__).resolve().parents[1] / 'emulator_lease.py'
SPEC = importlib.util.spec_from_file_location('emulator_lease', MODULE)
lease = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lease)


class EmulatorLeaseTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'android.lock'

    def test_second_owner_cannot_enter(self):
        with lease._lease_at_path(self.path, 0):
            second = lease._lease_at_path(self.path, 0)
            with self.assertRaises(lease.EmulatorLeaseTimeout):
                second.__enter__()

    def test_successful_exit_releases_but_retains_inode(self):
        with lease._lease_at_path(self.path, 0):
            inode = self.path.stat().st_ino
        with lease._lease_at_path(self.path, 0):
            self.assertEqual(self.path.stat().st_ino, inode)

    def test_exception_releases_owner(self):
        try:
            with lease._lease_at_path(self.path, 0):
                raise RuntimeError('synthetic test failure')
        except RuntimeError:
            pass
        with lease._lease_at_path(self.path, 0):
            self.assertTrue(self.path.is_file())

    def test_old_file_is_not_permanent_deadlock(self):
        self.path.write_bytes(b'0')
        with lease._lease_at_path(self.path, 0):
            self.assertTrue(self.path.is_file())

    def test_crashed_process_releases_os_lock(self):
        code = "import sys,os;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from emulator_lease import _lease_at_path; c=_lease_at_path(Path(sys.argv[2]),0);c.__enter__();os._exit(17)"
        result = subprocess.run([sys.executable, '-c', code, str(MODULE.parent), str(self.path)],
                                check=False, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 17, result.stderr.decode(errors='replace'))
        with lease._lease_at_path(self.path, 0):
            self.assertTrue(self.path.exists())

    def test_invalid_wait_values_rejected(self):
        for wait in (True, '0', -1, 1201, float('nan'), float('inf')):
            context = lease._lease_at_path(self.path, wait)
            with self.subTest(wait=wait), self.assertRaises(ValueError):
                context.__enter__()
        self.assertFalse(self.path.exists())

    def test_wait_is_bounded(self):
        with patch.object(lease, '_try_lock', return_value=False):
            context = lease._lease_at_path(self.path, 0)
            with self.assertRaises(lease.EmulatorLeaseTimeout):
                context.__enter__()

    def test_same_port_wrong_avd_is_rejected(self):
        device = Mock(side_effect=[Mock(returncode=0, stdout='different-avd\nOK\n'), Mock(returncode=0, stdout='33\n')])
        with self.assertRaisesRegex(RuntimeError, 'identity mismatch'):
            lease.verify_emulator_identity(device, 'expected-avd', 33)

    def test_avd_substring_is_not_identity(self):
        device = Mock(side_effect=[Mock(returncode=0, stdout='prefix-expected-avd\nOK\n'), Mock(returncode=0, stdout='33\n')])
        with self.assertRaisesRegex(RuntimeError, 'identity mismatch'):
            lease.verify_emulator_identity(device, 'expected-avd', 33)

    def test_wrong_android_is_rejected(self):
        device = Mock(side_effect=[Mock(returncode=0, stdout='expected-avd\nOK\n'), Mock(returncode=0, stdout='36\n')])
        with self.assertRaisesRegex(RuntimeError, 'version mismatch'):
            lease.verify_emulator_identity(device, 'expected-avd', 33)

    def test_exact_identity_and_android_accepted(self):
        device = Mock(side_effect=[Mock(returncode=0, stdout='expected-avd\nOK\n'), Mock(returncode=0, stdout='33\n')])
        lease.verify_emulator_identity(device, 'expected-avd', 33)
        self.assertTrue(all(call.kwargs['timeout'] == 10 for call in device.call_args_list))

    def test_diagnostic_failure_preserves_original_test(self):
        device = Mock(side_effect=TimeoutError('synthetic'))
        lease.collect_runtime_failure(device)
        self.assertEqual(device.call_count, 5)

    def test_crash_buffer_is_read_with_a_deadline(self):
        device = Mock(return_value=Mock(stdout='synthetic diagnostic', returncode=0))
        lease.collect_runtime_failure(device)
        self.assertEqual(device.call_args_list[0].args, ('logcat', '-d', '-b', 'crash', '-v', 'threadtime'))
        self.assertEqual(device.call_args_list[0].kwargs, {'timeout': 10})

    def test_empty_crash_buffer_keeps_package_exit_and_system_kill_evidence(self):
        device = Mock(return_value=Mock(stdout='', returncode=0))
        lease.collect_runtime_failure(device)
        commands = [call.args for call in device.call_args_list]
        self.assertIn(('shell', 'dumpsys', 'activity', 'exit-info', 'ru.omnicio.app.debug'), commands)
        self.assertIn(('shell', 'dumpsys', 'meminfo'), commands)
        event_command = next(command for command in commands if 'events' in command)
        self.assertIn('am_kill:I', event_command)
        self.assertIn('am_proc_died:I', event_command)
        self.assertEqual(event_command[-1], '*:S')
        self.assertTrue(all(call.kwargs == {'timeout': 10} for call in device.call_args_list))

    @unittest.skipIf(os.name == 'nt', 'Windows symlink creation privilege is not assumed')
    def test_symlink_never_truncates_target(self):
        target = Path(self.directory.name) / 'preserve'
        target.write_bytes(b'preserve')
        self.path.symlink_to(target)
        context = lease._lease_at_path(self.path, 0)
        with self.assertRaises(ValueError):
            context.__enter__()
        self.assertEqual(target.read_bytes(), b'preserve')

    def test_reparse_points_are_rejected(self):
        metadata = Mock(st_mode=0o100600, st_file_attributes=0x400)
        with patch.object(Path, 'lstat', return_value=metadata):
            with self.assertRaises(ValueError):
                lease._reject_link(self.path)


if __name__ == '__main__':
    unittest.main()
