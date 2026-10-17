"""Offline driver checks; not Android device-test evidence."""
import importlib.util
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import Mock

SPEC = importlib.util.spec_from_file_location(
    "profile_launch",
    Path(__file__).resolve().parents[1] / "profile_launch.py",
)
launch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launch)
ACTIVITY, PACKAGE, MARKER = launch.ACTIVITY, launch.PACKAGE, launch.MARKER
start_status, profile_resumed = launch.start_status, launch.profile_resumed
ready_marker, launch_profile = launch.ready_marker, launch.launch_profile


def tree(
    package=PACKAGE,
    marker=MARKER,
    bounds="[0,0][400,800]",
    screen=launch.PROFILE_SCREEN_MARKER,
):
    root = ET.Element("hierarchy")
    description = ";".join(value for value in (marker, screen) if value)
    ET.SubElement(
        root,
        "node",
        {"package": package, "content-desc": description, "bounds": bounds},
    )
    return root


def anr_tree(
    *,
    package="android",
    resource_id="android:id/aerr_wait",
    text="Wait",
    bounds="[120,400][220,460]",
):
    root = ET.Element("hierarchy")
    ET.SubElement(
        root,
        "node",
        {
            "package": package,
            "resource-id": resource_id,
            "text": text,
            "bounds": bounds,
        },
    )
    return root


RESUMED = "topResumedActivity=ActivityRecord{123 u0 " + ACTIVITY + " t12}"


class ProfileLaunchTests(unittest.TestCase):
    def test_supported_statuses(self):
        self.assertEqual(start_status("Starting: Intent\nStatus: ok\n"), "ok")
        self.assertEqual(start_status("Status: timeout\n"), "timeout")

    def test_unknown_or_ambiguous_status_fails(self):
        for text in (
            "",
            "Status: stopped",
            "Status: ok\nStatus: timeout",
            "Status: ok\nError: blocked",
            "Status: ok\nSecurityException: denied",
        ):
            with self.subTest(text=text), self.assertRaises(AssertionError):
                start_status(text)

    def test_foreground_not_history_or_other_activity(self):
        self.assertTrue(profile_resumed(RESUMED))
        self.assertTrue(
            profile_resumed(
                RESUMED.replace("topResumedActivity=", "mResumedActivity: ")
            )
        )
        self.assertFalse(
            profile_resumed(
                RESUMED.replace("topResumedActivity=", "lastResumedActivity=")
            )
        )
        self.assertFalse(profile_resumed(RESUMED.replace(ACTIVITY, ACTIVITY + "Other")))
        self.assertFalse(profile_resumed(ACTIVITY))

    def test_marker_requires_exact_package_full_value_and_requested_screen(self):
        self.assertIsNotNone(ready_marker(tree()))
        self.assertIsNotNone(ready_marker(tree(), "profile"))
        self.assertIsNone(ready_marker(tree(package="another.app"), "profile"))
        self.assertIsNone(ready_marker(tree(marker=MARKER + "0"), "profile"))
        self.assertIsNone(
            ready_marker(tree(marker="probe-refresh-tests:0"), "profile")
        )
        self.assertIsNone(
            ready_marker(tree(screen="probe-screen:home"), "profile")
        )
        self.assertIsNotNone(
            ready_marker(tree(screen="probe-screen:home"), "home")
        )
        self.assertIsNotNone(ready_marker(tree(screen="probe-screen:ux100"), "ux100"))
        self.assertIsNone(ready_marker(tree(screen="probe-screen:market"), "ux100"))
        invalid_screen_tree = tree()
        with self.assertRaises(ValueError):
            ready_marker(invalid_screen_tree, "unknown")

    def test_empty_or_invalid_bounds_fail(self):
        for bounds in ("", "[0,0][0,10]", "[-1,0][10,10]", "[0,10][10,0]"):
            self.assertIsNone(ready_marker(tree(bounds=bounds), "profile"))

    def test_timeout_without_frame_never_passes(self):
        command = Mock(side_effect=["", "Status: timeout", RESUMED])

        def wait(read, message):
            self.assertIsNone(read())
            raise AssertionError(message)

        with self.assertRaises(AssertionError):
            launch_profile(command, lambda: tree(marker="not-ready"), wait)

    def test_late_frame_can_be_verified_after_fresh_explicit_launch(self):
        for status in ("ok", "timeout"):
            command = Mock(side_effect=["", "Status: " + status, RESUMED, RESUMED])
            launch_profile(command, tree, lambda read, message: read())
            self.assertEqual(
                command.call_args_list[0].args,
                ("shell", "am", "force-stop", PACKAGE),
            )
            self.assertEqual(
                command.call_args_list[1].args,
                (
                    "shell",
                    "am",
                    "start",
                    "-W",
                    "-n",
                    ACTIVITY,
                    "--es",
                    "spectrum_screen",
                    "profile",
                ),
            )

    def test_wrong_screen_frame_cannot_authorize_profile_actions(self):
        command = Mock(side_effect=["", "Status: ok", RESUMED])
        read_tree = Mock(return_value=tree(screen="probe-screen:portfolio"))

        def wait(read, message):
            self.assertIsNone(read())
            raise AssertionError(message)

        with self.assertRaises(AssertionError):
            launch_profile(command, read_tree, wait)

    def test_focus_change_during_dump_fails(self):
        command = Mock(
            side_effect=[
                "",
                "Status: ok",
                RESUMED,
                "topResumedActivity: other.app/Main",
            ]
        )
        with self.assertRaises(AssertionError):
            launch_profile(command, tree, lambda read, message: read())

    def test_command_failure_not_swallowed(self):
        command = Mock(side_effect=RuntimeError("adb disconnected"))
        wait = Mock()
        with self.assertRaises(RuntimeError):
            launch_profile(command, tree, wait)

    def test_unresumed_activity_does_not_reuse_old_tree(self):
        command = Mock(
            side_effect=[
                "",
                "Status: ok",
                "lastResumedActivity " + ACTIVITY,
            ]
        )
        read_tree = Mock(return_value=tree())
        with self.assertRaises(AssertionError):
            launch_profile(command, read_tree, lambda read, message: read())
        read_tree.assert_not_called()

    def test_system_ui_wait_action_is_exact_and_system_owned(self):
        self.assertIsNotNone(launch.system_ui_wait_action(anr_tree()))
        self.assertIsNotNone(
            launch.system_ui_wait_action(anr_tree(resource_id="", text="Подождать"))
        )
        self.assertIsNone(launch.system_ui_wait_action(anr_tree(package=PACKAGE)))
        self.assertIsNone(
            launch.system_ui_wait_action(
                anr_tree(resource_id="android:id/button1", text="Continue")
            )
        )
        self.assertIsNone(
            launch.system_ui_wait_action(anr_tree(bounds="[0,0][0,10]"))
        )

    def test_ordinary_missing_frame_does_not_trigger_recovery(self):
        command = Mock()
        evidence = {}
        self.assertFalse(
            launch.dismiss_confirmed_system_ui_anr(
                command,
                tree(marker="missing"),
                evidence,
            )
        )
        command.assert_not_called()
        self.assertEqual(evidence, {})

    def test_wait_action_without_confirmed_system_ui_anr_does_not_trigger_recovery(self):
        command = Mock(
            side_effect=["ordinary window state", "ordinary SurfaceFlinger layers"]
        )
        evidence = {}
        self.assertFalse(
            launch.dismiss_confirmed_system_ui_anr(command, anr_tree(), evidence)
        )
        self.assertEqual(command.call_count, 2)
        self.assertEqual(evidence, {})

    def test_confirmed_system_ui_anr_is_dismissed_then_rechecked(self):
        command = Mock(
            side_effect=[
                launch.SYSTEM_UI_ANR,
                "",
                "ordinary window state",
                "ordinary SurfaceFlinger layers",
            ]
        )
        evidence = {}
        self.assertTrue(
            launch.dismiss_confirmed_system_ui_anr(command, anr_tree(), evidence)
        )
        self.assertEqual(evidence["system_ui_anr_recovery"]["action"], "wait")
        self.assertEqual(
            command.call_args_list[1].args,
            ("shell", "input", "tap", "170", "430"),
        )

    def test_profile_frame_recovers_only_confirmed_system_overlay(self):
        command = Mock(
            side_effect=[
                RESUMED,
                launch.SYSTEM_UI_ANR,
                "",
                "ordinary window state",
                "ordinary SurfaceFlinger layers",
            ]
        )
        evidence = {}
        self.assertIsNone(launch.profile_frame(command, anr_tree, evidence))
        self.assertEqual(evidence["system_ui_anr_recovery"]["action"], "wait")
        self.assertNotIn("foreground_after", evidence)

    def test_confirmed_external_messages_anr_can_be_stopped(self):
        layer = "Application Not Responding: com.google.android.apps.messaging#307"
        command = Mock(side_effect=["", layer, ""])
        evidence = {}
        self.assertTrue(launch.recover_confirmed_messaging_anr(command, anr_tree(), evidence))
        self.assertEqual(command.call_args_list[-1].args,
                         ("shell", "am", "force-stop", "com.google.android.apps.messaging"))
        self.assertEqual(evidence["emulator_app_anr_recovery"]["action"], "force-stop")

    def test_app_under_test_and_unrecognized_anrs_never_recover(self):
        for layer in (
            "Application Not Responding: " + PACKAGE,
            "Application Not Responding: com.google.android.apps.messaging.other#2",
            "Application Not Responding: com.google.android.apps.messaging#2\nApplication Not Responding: " + PACKAGE,
            "ordinary layers",
        ):
            with self.subTest(layer=layer):
                command = Mock(side_effect=["", layer])
                self.assertFalse(launch.recover_confirmed_messaging_anr(command, anr_tree(), {}))
                self.assertEqual(command.call_count, 2)

    def test_external_anr_requires_system_owned_dialog(self):
        command = Mock()
        self.assertFalse(launch.recover_confirmed_messaging_anr(command, anr_tree(package=PACKAGE), {}))
        command.assert_not_called()


if __name__ == "__main__":
    unittest.main()
