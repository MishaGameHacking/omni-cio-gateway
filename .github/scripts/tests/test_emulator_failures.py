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


if __name__ == "__main__":
    unittest.main()
