"""Regression tests for recording failures; no claim of an Android UI pass."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import Mock, patch

MODULE = Path(__file__).resolve().parents[1] / "test_apk_installation.py"
SPEC = importlib.util.spec_from_file_location("apk_installation", MODULE)
installation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installation)


class EmulatorFailureTests(unittest.TestCase):
    def test_success_requires_completed_exercise(self):
        from backend.installation_evidence import BUSINESS_CASE_IDS, PORTFOLIO_CASE_IDS, CURRENT_UI_SUITE
        fixture = {"test": "debug_ui_fixture_install", "success": True, "apk_sha256": "c" * 64}
        receipt = {"ui_suite": CURRENT_UI_SUITE, "business_case_count": 52, "business_cases": sorted(BUSINESS_CASE_IDS),
                   "portfolio_case_count": 14, "portfolio_cases": sorted(PORTFOLIO_CASE_IDS)}
        results = [fixture]
        device = Mock()

        def exercise(actual):
            self.assertIs(actual, device)
            self.assertEqual(
                results,
                [fixture, {"test": "profile_ui", "success": False}],
            )
            return receipt

        installation.record_profile_check(device, results, exercise)
        self.assertEqual(
            results,
            [fixture, {"test": "profile_ui", "success": True, **receipt, "fixture_apk_sha256": "c" * 64}],
        )

    def test_empty_or_partial_exercise_receipt_remains_a_failed_check(self):
        for receipt in (None, {}, {"ui_suite": "spectrum-3d-100-v1", "business_case_count": 0, "business_cases": []}):
            results = [{"test": "debug_ui_fixture_install", "success": True, "apk_sha256": "c" * 64}]
            with self.subTest(receipt=receipt), self.assertRaises(ValueError):
                installation.record_profile_check(Mock(), results, Mock(return_value=receipt))
            self.assertFalse(results[-1]["success"])

    def test_screenshot_timeout_is_recorded_and_propagated(self):
        results = []
        error = subprocess.TimeoutExpired("screencap", 15)
        with self.assertRaises(subprocess.TimeoutExpired) as raised:
            installation.record_profile_check(
                Mock(),
                results,
                Mock(side_effect=error),
            )
        self.assertIs(raised.exception, error)
        self.assertEqual(
            results,
            [
                {
                    "test": "profile_ui",
                    "success": False,
                    "error_type": "TimeoutExpired",
                }
            ],
        )

    def test_assertion_is_not_swallowed(self):
        results = [{"test": "candidate_clean_install", "success": True}]
        error = AssertionError("incorrect palette")
        with self.assertRaises(AssertionError):
            installation.record_profile_check(
                Mock(),
                results,
                Mock(side_effect=error),
            )
        self.assertTrue(results[0]["success"])
        self.assertFalse(results[1]["success"])
        self.assertEqual(results[1]["error_type"], "AssertionError")

    def test_transport_loss_restarts_the_whole_attempt_once(self):
        calls = []

        def execute(attempt):
            calls.append(attempt)
            if attempt == 1:
                raise installation.EmulatorTransportLost("device offline")
            return [{"test": "profile_ui", "success": True}]

        with patch("builtins.print"):
            result = installation.run_with_transport_retry(execute)
        self.assertEqual(calls, [1, 2])
        self.assertEqual(
            result,
            [{"test": "profile_ui", "success": True}],
        )

    def test_second_transport_loss_remains_a_failure(self):
        execute = Mock(
            side_effect=installation.EmulatorTransportLost("device missing")
        )
        with patch("builtins.print"), self.assertRaises(
            installation.EmulatorTransportLost
        ):
            installation.run_with_transport_retry(execute)
        self.assertEqual(execute.call_count, 2)

    def test_ui_assertion_is_never_retried_as_transport(self):
        execute = Mock(side_effect=AssertionError("incorrect palette"))
        with self.assertRaises(AssertionError):
            installation.run_with_transport_retry(execute)
        execute.assert_called_once_with(1)

    def test_retry_count_is_bounded(self):
        for attempts in (0, 3, True, 1.5):
            execute = Mock()
            with self.subTest(attempts=attempts):
                with self.assertRaises(ValueError):
                    installation.run_with_transport_retry(
                        execute,
                        attempts=attempts,
                    )
                execute.assert_not_called()

    def test_diagnostics_bound_both_calls(self):
        device = Mock(return_value=Mock(stdout="emulator data"))
        with patch("builtins.print"):
            installation.collect_failure_diagnostics(device)
        self.assertEqual(device.call_count, 2)
        self.assertEqual(
            [call.kwargs["timeout"] for call in device.call_args_list],
            [10, 10],
        )

    def test_missing_logcat_does_not_skip_graphics_diagnostic(self):
        device = Mock(
            side_effect=[
                subprocess.TimeoutExpired("logcat", 10),
                Mock(stdout="graphics"),
            ]
        )
        with patch("builtins.print"):
            installation.collect_failure_diagnostics(device)
        device.assert_called_with(
            "shell",
            "dumpsys",
            "SurfaceFlinger",
            timeout=10,
        )

    def test_missing_diagnostics_do_not_mask_test_failure(self):
        device = Mock(side_effect=OSError("unavailable"))
        with patch("builtins.print"):
            installation.collect_failure_diagnostics(device)
        self.assertEqual(device.call_count, 2)

    def test_graphics_uid_requires_one_exact_installed_candidate(self):
        self.assertEqual(installation.candidate_package_uid(
            "package:ru.omnicio.app.debug.other uid:10999\npackage:ru.omnicio.app.debug uid:10207\n"
        ), "10207")
        for output in ("", "package:other.app uid:10207", "package:ru.omnicio.app.debug.other uid:10207",
                       "package:ru.omnicio.app.debug uid:0", "package:ru.omnicio.app.debug uid:-1",
                       "package:ru.omnicio.app.debug uid:2147483648", "package:ru.omnicio.app.debug uid:10207 --pid=1",
                       "package:ru.omnicio.app.debug uid:10207\npackage:ru.omnicio.app.debug uid:10208"):
            with self.subTest(output=output):
                self.assertIsNone(installation.candidate_package_uid(output))

    def test_shader_and_dead_process_logs_do_not_use_noisy_global_tail(self):
        compile_error = '10-17 21:24:48.210 2187 2289 E Filament: InfoLog="synthetic compile failure"'

        def read(*command, timeout):
            self.assertEqual(timeout, 10)
            if command[:5] == ("shell", "cmd", "package", "list", "packages"):
                self.assertEqual(command[5:], ("-U", "ru.omnicio.app.debug"))
                return subprocess.CompletedProcess(command, 0, "package:ru.omnicio.app.debug uid:10207\n", "")
            self.assertEqual(command[:8], ("logcat", "-d", "-b", "main", "-b", "system", "-v", "threadtime"))
            self.assertNotIn("-t", command)
            self.assertNotIn("-T", command)
            if command[-1] == "--uid=10207":
                return subprocess.CompletedProcess(command, 0, compile_error, "")
            self.assertIn("Filament:V", command)
            self.assertIn("*:S", command)
            return subprocess.CompletedProcess(command, 0, compile_error, "")

        device = Mock(side_effect=read)
        with patch("builtins.print") as output:
            installation.collect_graphics_diagnostics(device)
        self.assertEqual(device.call_count, 3)
        messages = "\n".join(call.args[0] for call in output.call_args_list)
        self.assertIn("candidate-uid-10207", messages)
        self.assertIn("shader-main-system", messages)
        self.assertEqual(messages.count(compile_error), 2)

    def test_unknown_uid_never_reads_an_unrelated_apps_log(self):
        device = Mock(side_effect=[
            subprocess.CompletedProcess([], 0, "package:ru.omnicio.app.debug.other uid:10999", ""),
            subprocess.CompletedProcess([], 0, "shader diagnostic", ""),
        ])
        with patch("builtins.print") as output:
            installation.collect_graphics_diagnostics(device)
        self.assertEqual(device.call_count, 2)
        self.assertFalse(any(part.startswith("--uid=") for call in device.call_args_list for part in call.args))
        self.assertIn("EMULATOR_GRAPHICS_IDENTITY=unavailable", [call.args[0] for call in output.call_args_list])

    def test_missing_shader_log_does_not_skip_candidate_uid_log(self):
        device = Mock(side_effect=[
            subprocess.CompletedProcess([], 0, "package:ru.omnicio.app.debug uid:10207", ""),
            subprocess.TimeoutExpired("logcat", 10),
            subprocess.CompletedProcess([], 0, "retained app PID and error", ""),
        ])
        with patch("builtins.print") as output:
            installation.collect_graphics_diagnostics(device)
        self.assertEqual(device.call_args_list[-1].args[-1], "--uid=10207")
        self.assertTrue(all(call.kwargs["timeout"] == 10 for call in device.call_args_list))
        self.assertIn("retained app PID and error", "\n".join(call.args[0] for call in output.call_args_list))

    def test_missing_package_diagnostic_still_collects_shader_error(self):
        device = Mock(side_effect=[
            OSError("package manager unavailable"),
            subprocess.CompletedProcess([], 0, "InfoLog=synthetic shader error", ""),
        ])
        with patch("builtins.print") as output:
            installation.collect_graphics_diagnostics(device)
        self.assertEqual(device.call_count, 2)
        self.assertIn("InfoLog=synthetic shader error", "\n".join(call.args[0] for call in output.call_args_list))

    def test_graphics_diagnostic_output_keeps_bounded_beginning_and_end(self):
        diagnostic = "begin-shader\n" + "x" * 50000 + "\nend-abort"
        device = Mock(side_effect=[
            subprocess.CompletedProcess([], 1, "", "not installed"),
            subprocess.CompletedProcess([], 0, diagnostic, ""),
        ])
        with patch("builtins.print") as output:
            installation.collect_graphics_diagnostics(device)
        message = output.call_args_list[-1].args[0]
        self.assertLess(len(message), 32200)
        self.assertIn("begin-shader", message)
        self.assertIn("middle omitted", message)
        self.assertTrue(message.endswith("end-abort"))

    def test_failed_graphics_log_command_is_reported_as_unavailable(self):
        device = Mock(side_effect=[
            subprocess.CompletedProcess([], 1, "package:ru.omnicio.app.debug uid:10207", "failed"),
            subprocess.CompletedProcess([], 1, "invalid graphics evidence", "failed"),
        ])
        with patch("builtins.print") as output:
            installation.collect_graphics_diagnostics(device)
        messages = "\n".join(call.args[0] for call in output.call_args_list)
        self.assertIn("EMULATOR_GRAPHICS_DIAGNOSTIC_UNAVAILABLE=shader-main-system", messages)
        self.assertNotIn("invalid graphics evidence", messages)

    def test_broken_frame_with_offline_adb_restarts_complete_attempt(self):
        calls = []
        process = Mock(poll=Mock(return_value=None))
        original = ConnectionError("frame ended")
        def execute(attempt):
            calls.append(attempt)
            if attempt == 1:
                classified = installation.classify_frame_failure(
                    original, "adb", "emulator-5600", process
                )
                raise classified from original
            return [{"test": "profile_ui", "success": True}]
        with patch.object(installation, "adb_transport_connected", return_value=False) as probe, \
                patch("builtins.print"):
            result = installation.run_with_transport_retry(execute)
        self.assertEqual(calls, [1, 2])
        self.assertTrue(result[0]["success"])
        probe.assert_called_once_with("adb", "emulator-5600")

    def test_broken_frame_on_connected_emulator_keeps_original_failure(self):
        original = ConnectionError("driver stopped")
        process = Mock(poll=Mock(return_value=None))
        with patch.object(installation, "adb_transport_connected", return_value=True), \
                patch("builtins.print"):
            result = installation.classify_frame_failure(
                original, "adb", "emulator-5600", process
            )
        self.assertIs(result, original)

    def test_ui_assertions_and_malformed_frames_never_probe_or_retry(self):
        process = Mock(poll=Mock(return_value=1))
        for original in (AssertionError("missing label"), ValueError("stale frame"), TimeoutError("slow UI")):
            with self.subTest(error=type(original).__name__), \
                    patch.object(installation, "adb_transport_connected") as probe:
                result = installation.classify_frame_failure(
                    original, "adb", "emulator-5600", process
                )
            self.assertIs(result, original)
            probe.assert_not_called()
        process.poll.assert_not_called()

    def test_exited_emulator_classifies_frame_loss_without_touching_other_devices(self):
        original = ConnectionError("frame ended")
        process = Mock(poll=Mock(return_value=3221225477))
        with patch.object(installation, "adb_transport_connected") as probe, \
                patch("builtins.print"):
            result = installation.classify_frame_failure(
                original, "adb", "emulator-5600", process
            )
        self.assertIsInstance(result, installation.EmulatorTransportLost)
        self.assertIn("3221225477", str(result))
        probe.assert_not_called()


if __name__ == "__main__":
    unittest.main()
