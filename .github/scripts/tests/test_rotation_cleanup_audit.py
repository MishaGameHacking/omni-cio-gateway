"""Cleanup failures must not replace a primary UI failure or skip other restores."""
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from emulator_rotation import physical_quarter_turn


class FailingConsole:
    def __init__(self, error, *, fail_setting=False):
        self.error = error
        self.fail_setting = fail_setting
        self.turns = 0
        self.restored = []

    def __call__(self, *args):
        if args == ('emu', 'rotate'):
            self.turns += 1
            if self.turns == 2 and not self.fail_setting:
                raise self.error
            return 'OK\n'
        if args[2] == 'get':
            return '0'
        if args[2] == 'put' and args[-1] == '0':
            self.restored.append(args[4])
            if args[4] == 'accelerometer_rotation' and self.fail_setting:
                raise self.error
        return ''


class RotationCleanupAuditTests(unittest.TestCase):
    def assert_preserved(self, cleanup_error, *, fail_setting=False):
        console = FailingConsole(cleanup_error, fail_setting=fail_setting)
        primary = AssertionError('actual UI state lost')
        session = physical_quarter_turn(console)
        with self.assertRaises(AssertionError) as caught:
            with session:
                raise primary
        self.assertIs(caught.exception, primary)
        self.assertIn('restore emulator rotation', '\n'.join(primary.__notes__))
        self.assertEqual(console.turns, 4)
        self.assertEqual(console.restored, ['accelerometer_rotation', 'user_rotation'])

    def test_timeout_during_restore_preserves_ui_failure(self):
        error = subprocess.TimeoutExpired(['adb', 'emu', 'rotate'], 10)
        self.assert_preserved(error)

    def test_os_error_during_restore_preserves_ui_failure(self):
        self.assert_preserved(OSError('console disappeared'))

    def test_timeout_during_setting_restore_does_not_skip_second_setting(self):
        error = subprocess.TimeoutExpired(['adb', 'shell', 'settings'], 10)
        self.assert_preserved(error, fail_setting=True)

    def test_successful_body_still_fails_on_cleanup_error(self):
        console = FailingConsole(OSError('console disappeared'))
        session = physical_quarter_turn(console)
        with self.assertRaisesRegex(RuntimeError, 'restore emulator rotation'):
            with session:
                pass
        self.assertEqual(console.restored, ['accelerometer_rotation', 'user_rotation'])

    def test_cancelled_body_is_not_replaced_by_cleanup_error(self):
        console = FailingConsole(OSError('console disappeared'))
        primary = KeyboardInterrupt('cancelled')
        session = physical_quarter_turn(console)
        with self.assertRaises(KeyboardInterrupt) as caught:
            with session:
                raise primary
        self.assertIs(caught.exception, primary)
        self.assertEqual(console.restored, ['accelerometer_rotation', 'user_rotation'])


if __name__ == '__main__':
    unittest.main()
