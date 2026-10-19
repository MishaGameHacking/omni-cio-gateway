"""Exercise ADB console framing and every exit path of the real setup context."""
from contextlib import redirect_stdout
import io
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from emulator_boot_readiness import prepared_emulator_session
from test_emulator_boot_readiness import Device

NAME = "analyst-install-123-1"
SERVER_COMMAND = ("shell", "pidof", "system_server")


class ConsoleDevice(Device):
    def __init__(self, output=None, code=0):
        super().__init__()
        self.console_output = output if output is not None else NAME + "\nOK\n"
        self.console_code = code
        self.restart_on_restore = False
        self.pid_error = None

    def __call__(self, *args, timeout):
        if args == ("emu", "avd", "name"):
            self.calls.append((args, timeout))
            return subprocess.CompletedProcess(args, self.console_code, self.console_output, "")
        if args == SERVER_COMMAND and self.pid_error is not None:
            self.calls.append((args, timeout))
            raise self.pid_error
        if args == ("shell", "settings", "put", "secure", "user_setup_complete", "0"):
            if self.restart_on_restore:
                self.pid = "999"
        return super().__call__(*args, timeout=timeout)


def prepare(device, name=NAME):
    return prepared_emulator_session(device, name, 35)


class ConsoleReadinessTests(unittest.TestCase):
    def test_acknowledgement_variants_preserve_one_exact_identity(self):
        for output in (NAME + "\n", NAME + "\nOK\n", "OK\n" + NAME + "\nOK\n",
                       "\r\nOK\r\n" + NAME + "\r\nOK\r\n\r\n"):
            device = ConsoleDevice(output)
            with self.subTest(output=output), prepare(device) as receipt:
                self.assertEqual(device.flags["user_setup_complete"], "1")
            self.assertTrue(receipt["system_server_unchanged"])
            self.assertEqual(device.flags["user_setup_complete"], "0")

    def test_empty_wrong_duplicate_and_error_payloads_never_mutate_device(self):
        for output in ("", "OK\n", "OK\nOK\n", "other-avd\nOK\n",
                       NAME + "\nother-avd\nOK\n", NAME + "\n" + NAME + "\nOK\n",
                       NAME + "\nKO: denied\n", "error: unavailable\n" + NAME,
                       NAME + "-extra\nOK\n", "prefix-" + NAME + "\nOK\n",
                       NAME + "\x00\nOK\n"):
            device = ConsoleDevice(output)
            with self.subTest(output=output), self.assertRaises(ValueError), prepare(device):
                self.fail("Invalid identity reached setup")
            self.assertEqual([args for args, _ in device.calls], [("emu", "avd", "name")])

    def test_nonzero_exit_with_valid_stdout_is_not_identity(self):
        device = ConsoleDevice(NAME + "\nOK\n", code=1)
        with self.assertRaises(RuntimeError), prepare(device):
            self.fail("Failed command reached setup")
        self.assertEqual(len(device.calls), 1)

    def test_oversized_console_response_is_rejected_without_echoing_it(self):
        device = ConsoleDevice(NAME + "\n" + "OK\n" * 2000)
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(ValueError), prepare(device):
            self.fail("Oversized response reached setup")
        self.assertEqual(output.getvalue(), "")

    def test_identity_diagnostic_does_not_echo_unrecognized_payload(self):
        device = ConsoleDevice("unexpected-sensitive-payload\n" + NAME)
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(ValueError), prepare(device):
            self.fail("Ambiguous response reached setup")
        self.assertIn('"matches_expected": false', output.getvalue())
        self.assertNotIn("unexpected-sensitive-payload", output.getvalue())

    def test_unicode_avd_digits_are_rejected_before_device_access(self):
        for name in ("analyst-install-١٢٣-1", "analyst-install-１２３-1"):
            device = ConsoleDevice(name + "\nOK\n")
            with self.subTest(name=name), self.assertRaises(ValueError), prepare(device, name):
                self.fail("Unicode identity reached setup")
            self.assertEqual(device.calls, [])

    def test_unicode_pid_digits_remain_rejected(self):
        for pid in ("5٨0", "5８0", "５80"):
            device = ConsoleDevice()
            device.pid = pid
            with self.subTest(pid=pid), self.assertRaises(RuntimeError), prepare(device):
                self.fail("Unicode PID reached setup")
            self.assertFalse(any("put" in args for args, _ in device.calls))

    def test_ascii_pid_range_is_unchanged(self):
        for pid in ("1", "2147483647"):
            device = ConsoleDevice()
            device.pid = pid
            with self.subTest(pid=pid), prepare(device) as receipt:
                self.assertEqual(receipt["system_server_pid"], int(pid))
            self.assertTrue(receipt["system_server_unchanged"])

    def test_primary_failure_keeps_server_checks_and_setup_restoration(self):
        device = ConsoleDevice()
        error = AssertionError("Actual app assertion")
        with self.assertRaises(AssertionError) as caught, prepare(device) as receipt:
            start = len(device.calls)
            device.pid = "999"
            raise error
        self.assertIs(caught.exception, error)
        self.assertFalse(receipt["system_server_unchanged"])
        self.assertEqual(device.flags["user_setup_complete"], "0")
        final = [args for args, _ in device.calls[start:]]
        self.assertEqual(final[0], SERVER_COMMAND)
        self.assertEqual(final[-1], SERVER_COMMAND)
        self.assertEqual(len(error.__notes__), 2)
        self.assertTrue(all("restarted" in note for note in error.__notes__))

    def test_system_restart_during_restoration_cannot_pass(self):
        device = ConsoleDevice()
        device.restart_on_restore = True
        with self.assertRaisesRegex(RuntimeError, "restarted"), prepare(device) as receipt:
            pass
        self.assertFalse(receipt["system_server_unchanged"])
        self.assertEqual(device.flags["user_setup_complete"], "0")

    def test_failed_exit_read_cannot_replace_original_app_assertion(self):
        device = ConsoleDevice()
        error = AssertionError("Actual app assertion")
        with self.assertRaises(AssertionError) as caught, prepare(device) as receipt:
            device.pid_error = subprocess.TimeoutExpired("pidof", 15)
            raise error
        self.assertIs(caught.exception, error)
        self.assertFalse(receipt["system_server_unchanged"])
        self.assertEqual(device.flags["user_setup_complete"], "0")
        self.assertEqual(len(error.__notes__), 2)

    def test_exit_read_timeout_blocks_success(self):
        device = ConsoleDevice()
        with self.assertRaises(subprocess.TimeoutExpired), prepare(device) as receipt:
            device.pid_error = subprocess.TimeoutExpired("pidof", 15)
        self.assertFalse(receipt["system_server_unchanged"])
        self.assertEqual(device.flags["user_setup_complete"], "0")

    def test_generator_close_checks_server_and_restores_without_success(self):
        device = ConsoleDevice()
        context = prepare(device)
        receipt = context.__enter__()
        start = len(device.calls)
        output = io.StringIO()
        with redirect_stdout(output):
            context.gen.close()
        final = [args for args, _ in device.calls[start:]]
        self.assertEqual(final[0], SERVER_COMMAND)
        self.assertEqual(final[-1], SERVER_COMMAND)
        self.assertEqual(device.flags["user_setup_complete"], "0")
        self.assertFalse(receipt["system_server_unchanged"])
        self.assertNotIn("EMULATOR_SESSION_VERIFIED", output.getvalue())

    def test_interrupt_is_not_masked_by_server_failure(self):
        device = ConsoleDevice()
        error = KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt) as caught, prepare(device) as receipt:
            device.pid = "999"
            raise error
        self.assertIs(caught.exception, error)
        self.assertFalse(receipt["system_server_unchanged"])
        self.assertEqual(device.flags["user_setup_complete"], "0")
        self.assertEqual(len(error.__notes__), 2)

    def test_callers_handled_exception_cannot_hide_exit_verification_failure(self):
        device = ConsoleDevice()
        try:
            raise LookupError("Already handled by caller")
        except LookupError as previous:
            with self.assertRaisesRegex(RuntimeError, "restarted"), prepare(device) as receipt:
                device.pid = "999"
            self.assertFalse(receipt["system_server_unchanged"])
            self.assertFalse(hasattr(previous, "__notes__"))
        self.assertEqual(device.flags["user_setup_complete"], "0")

    def test_callers_handled_exception_does_not_hide_setup_restoration_failure(self):
        device = ConsoleDevice()
        try:
            raise LookupError("Already handled by caller")
        except LookupError as previous:
            with self.assertRaises(RuntimeError), prepare(device) as receipt:
                device.fail_restore = True
            self.assertFalse(receipt["system_server_unchanged"])
            self.assertFalse(hasattr(previous, "__notes__"))

    def test_session_inside_callers_except_can_still_complete_normally(self):
        device = ConsoleDevice()
        try:
            raise LookupError("Already handled by caller")
        except LookupError:
            with prepare(device) as receipt:
                pass
        self.assertTrue(receipt["system_server_unchanged"])
        self.assertEqual(device.flags["user_setup_complete"], "0")

    def test_early_return_still_requires_complete_cleanup(self):
        device = ConsoleDevice()

        def body():
            with prepare(device) as receipt:
                return receipt

        receipt = body()
        self.assertTrue(receipt["system_server_unchanged"])
        self.assertEqual(device.flags["user_setup_complete"], "0")


if __name__ == "__main__":
    unittest.main()
