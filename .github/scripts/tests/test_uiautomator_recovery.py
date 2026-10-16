"""Offline classification tests; they do not claim an emulator UI pass."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

MODULE = Path(__file__).resolve().parents[1] / "test_apk_installation.py"
SPEC = importlib.util.spec_from_file_location("test_apk_installation", MODULE)
installation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installation)


class UiAutomatorRecoveryTests(unittest.TestCase):
    def test_only_uiautomator_dump_command_is_eligible(self):
        self.assertTrue(
            installation.is_uiautomator_dump(
                ("shell", "uiautomator", "dump", "/sdcard/analyst-ui-test.xml")
            )
        )
        self.assertFalse(
            installation.is_uiautomator_dump(("shell", "uiautomator", "events"))
        )
        self.assertFalse(
            installation.is_uiautomator_dump(("shell", "am", "start"))
        )

    def test_direct_timeout_output_is_recoverable_only_for_tree_dump(self):
        message = "java.util.concurrent.TimeoutException: Timeout while connecting UiAutomation"
        self.assertTrue(
            installation.is_uiautomator_connect_timeout(
                ("shell", "uiautomator", "dump", "/sdcard/tree.xml"),
                message,
            )
        )
        self.assertFalse(
            installation.is_uiautomator_connect_timeout(
                ("shell", "am", "start"),
                message,
            )
        )

    def test_android16_null_root_is_transient_only_for_tree_dump(self):
        message = "ERROR: null root node returned by UiTestAutomationBridge."
        dump = ("shell", "uiautomator", "dump", "/sdcard/tree.xml")
        self.assertTrue(
            installation.is_uiautomator_connect_timeout(dump, message)
        )
        self.assertFalse(
            installation.is_uiautomator_connect_timeout(
                ("shell", "am", "start"),
                message,
            )
        )

    def test_empty_response_requires_exact_system_crash_evidence(self):
        command = ("shell", "uiautomator", "dump", "/sdcard/tree.xml")
        crash = (
            "Process: com.android.commands.uiautomator\n"
            "java.lang.RuntimeException: Error while connecting UiAutomation"
        )
        self.assertTrue(
            installation.is_uiautomator_connect_timeout(command, "", crash)
        )
        self.assertFalse(
            installation.is_uiautomator_connect_timeout(
                command,
                "",
                "Process: ru.omnicio.app.debug\nTimeout while connecting UiAutomation",
            )
        )

    def test_quoted_emulator_serial_not_found_is_transport_loss(self):
        self.assertTrue(
            installation.is_transient_adb_transport_failure(
                "adb.exe: device 'emulator-5560' not found"
            )
        )
        self.assertTrue(
            installation.is_transient_adb_transport_failure(
                "adb: device 'emulator-5622' not found"
            )
        )
        self.assertFalse(
            installation.is_transient_adb_transport_failure(
                "cat: file 'emulator-5560' not found"
            )
        )

    def test_unrelated_failure_is_not_recoverable(self):
        command = ("shell", "uiautomator", "dump", "/sdcard/tree.xml")
        self.assertFalse(
            installation.is_uiautomator_connect_timeout(
                command,
                "SecurityException: permission denied",
                "",
            )
        )
        self.assertFalse(
            installation.is_uiautomator_connect_timeout(
                command,
                "",
                "Process: com.android.commands.uiautomator\nIllegalStateException: malformed window",
            )
        )

    def test_recovery_window_and_pacing_are_bounded(self):
        self.assertGreater(installation.UIAUTOMATOR_MIN_INTERVAL_SECONDS, 0)
        self.assertLessEqual(installation.UIAUTOMATOR_MIN_INTERVAL_SECONDS, 1)
        self.assertGreaterEqual(installation.UIAUTOMATOR_RECOVERY_SECONDS, 15)
        self.assertLessEqual(installation.UIAUTOMATOR_RECOVERY_SECONDS, 60)


if __name__ == "__main__":
    unittest.main()
