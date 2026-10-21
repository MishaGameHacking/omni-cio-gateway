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
        results = []
        device = Mock()

        def exercise(actual):
            self.assertIs(actual, device)
            self.assertEqual(
                results,
                [{"test": "profile_ui", "success": False}],
            )

        installation.record_profile_check(device, results, exercise)
        self.assertEqual(
            results,
            [{"test": "profile_ui", "success": True}],
        )

    def test_screenshot_timeout_is_recorded_and_propagated(self):
        results = []
        error = subprocess.TimeoutExpired("screencap", 15)
        mock_argument = Mock()
        mock_argument_next = Mock(side_effect=error)
        with self.assertRaises(subprocess.TimeoutExpired) as raised:
            installation.record_profile_check(
                mock_argument,
                results,
                mock_argument_next,
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
        mock_argument = Mock()
        mock_argument_next = Mock(side_effect=error)
        with self.assertRaises(AssertionError):
            installation.record_profile_check(
                mock_argument,
                results,
                mock_argument_next,
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
