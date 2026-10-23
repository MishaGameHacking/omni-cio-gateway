"""Control-only guards cannot authorize release or run on a developer machine."""
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import emulator_runtime_control as control


class RuntimeControlTests(unittest.TestCase):
    def test_only_ephemeral_linux_actions_can_enter(self):
        environment = {"RUNNER_OS": "Linux", "GITHUB_ACTIONS": "true",
                       "RUNNER_ENVIRONMENT": "github-hosted"}
        control.require_ephemeral_linux(environment, "posix")
        for key, value in (("RUNNER_OS", "Windows"), ("RUNNER_OS", "macOS"),
                           ("GITHUB_ACTIONS", "false"), ("RUNNER_ENVIRONMENT", "self-hosted")):
            with self.subTest(key=key, value=value), self.assertRaises(RuntimeError):
                control.require_ephemeral_linux({**environment, key: value}, "posix")
        with self.assertRaises(RuntimeError):
            control.require_ephemeral_linux(environment, "nt")
        with self.assertRaises(RuntimeError):
            control.require_ephemeral_linux({}, "posix")

    def test_actual_16kb_measurement_is_required(self):
        control.require_healthy_control("16384\n", "--------- beginning of crash\n")
        for value in ("4096", "", "16384 16384", "１６３８４", "163840"):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                control.require_healthy_control(value, "")

    def test_java_native_and_system_crashes_remain_failures(self):
        for crash in ("FATAL EXCEPTION: main", "Fatal signal 11 (SIGSEGV)",
                      "*** FATAL EXCEPTION IN SYSTEM PROCESS: main",
                      "WATCHDOG KILLING SYSTEM PROCESS"):
            with self.subTest(crash=crash), self.assertRaises(RuntimeError):
                control.require_healthy_control("16384", crash)

    @patch.object(control, "run_command")
    def test_nonzero_command_with_success_stdout_is_rejected(self, command):
        command.return_value = subprocess.CompletedProcess(["tool"], 1, "Success", "")
        with self.assertRaises(RuntimeError):
            control.require_command(["tool"])

    @patch.object(control, "run_command")
    def test_deadline_is_preserved_and_timeout_is_not_retried(self, command):
        error = subprocess.TimeoutExpired("tool", 15)
        command.side_effect = error
        with self.assertRaises(subprocess.TimeoutExpired) as caught:
            control.require_command(["tool"], timeout=15)
        self.assertIs(caught.exception, error)
        command.assert_called_once_with(["tool"], timeout=15, stdin=None)

    def test_successful_command_preserves_exact_observation(self):
        response = subprocess.CompletedProcess(["tool"], 0, "actual observation\n", "")
        with patch.object(control, "run_command", return_value=response):
            self.assertEqual(control.require_command(["tool"]), "actual observation\n")


if __name__ == "__main__":
    unittest.main()
