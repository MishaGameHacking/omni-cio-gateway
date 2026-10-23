"""Offline driver checks; not Android device-test evidence."""
import importlib.util
from pathlib import Path
import unittest
import subprocess
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
    def test_foreground_timeout_requires_a_new_complete_pair_and_frame(self):
        command = Mock(side_effect=[RESUMED, subprocess.TimeoutExpired("dumpsys", 4), RESUMED, RESUMED])
        read_tree = Mock(side_effect=[tree(), tree()])
        evidence = {}
        self.assertIsNone(launch.profile_frame(command, read_tree, evidence, "profile"))
        self.assertEqual(evidence["foreground_after"], ["activity observation timed out"])
        self.assertIsNotNone(launch.profile_frame(command, read_tree, evidence, "profile"))
        self.assertEqual(read_tree.call_count, 2)
        self.assertEqual(command.call_count, 4)
        command.assert_called_with("shell", "dumpsys", "-t", "2", "activity", "activities", timeout=4)

    def test_incomplete_system_dump_cannot_authorize_a_frame(self):
        read_tree = Mock(return_value=tree())
        partial = RESUMED + "\n*** SERVICE 'activity' DUMP TIMEOUT (2s) EXPIRED ***"
        command = Mock(return_value=partial)
        self.assertIsNone(launch.profile_frame(command, read_tree, {}, "profile"))
        read_tree.assert_not_called()

    def test_expired_foreground_read_cannot_reuse_previous_identity(self):
        command = Mock(side_effect=[subprocess.TimeoutExpired("dumpsys", 4), RESUMED, "other app"])
        read_tree = Mock(return_value=tree())
        evidence = {"foreground_before": [RESUMED], "foreground_after": [RESUMED]}
        self.assertIsNone(launch.profile_frame(command, read_tree, evidence, "profile"))
        read_tree.assert_not_called()
        self.assertIsNone(launch.profile_frame(command, read_tree, evidence, "profile"))

    def test_generic_ready_marker_does_not_require_a_screen(self):
        self.assertIsNotNone(ready_marker(tree(screen=""), None, None))
        self.assertIsNone(ready_marker(tree(screen="", marker="not-ready"), None, None))

    def test_scenario_without_screen_is_rejected_before_device_or_tree_access(self):
        for scenario in ("ready", "empty", "partial", "error", "job", ""):
            with self.subTest(scenario=scenario):
                command, read_tree, wait = Mock(), Mock(), Mock()
                with self.assertRaisesRegex(ValueError, "requires an explicit screen"):
                    launch_profile(command, read_tree, wait, expected_screen=None, scenario=scenario)
                command.assert_not_called()
                read_tree.assert_not_called()
                wait.assert_not_called()

                unread_tree = Mock()
                with self.assertRaisesRegex(ValueError, "requires an explicit screen"):
                    ready_marker(unread_tree, None, scenario)
                unread_tree.iter.assert_not_called()

    def test_portfolio_launch_requires_exact_production_route_and_scenario(self):
        ready = tree(screen="probe-screen:portfolio-history;probe-scenario:partial")
        self.assertIsNotNone(ready_marker(ready, "portfolio-history", "partial"))
        self.assertIsNone(ready_marker(ready, "portfolio-history", "ready"))
        self.assertIsNone(ready_marker(ready, "portfolio-dossier", "ready"))
        command = Mock(side_effect=["", "Status: ok", RESUMED, RESUMED])
        launch_profile(command, lambda: ready, lambda read, message: read(), expected_screen="portfolio-history", scenario="partial")
        self.assertEqual(command.call_args_list[1].args[-6:], ("--es", "spectrum_screen", "portfolio-history", "--es", "spectrum_scenario", "partial"))

    def test_unsupported_portfolio_route_scenario_fails_before_adb(self):
        for screen, scenario in (("portfolio-discovery", "partial"), ("portfolio-dossier", "error"),
                                 ("portfolio-history", "job"), ("portfolio-quotes", "empty"),
                                 ("portfolio-markets", "partial"), ("portfolio-appearance", "partial")):
            command = Mock()
            prepared_argument_1 = Mock()
            prepared_argument_2 = Mock()
            with self.subTest(screen=screen, scenario=scenario), self.assertRaises(ValueError):
                launch_profile(command, prepared_argument_1, prepared_argument_2, expected_screen=screen, scenario=scenario)
            command.assert_not_called()

    def test_portfolio_persistence_relaunch_requires_exact_run_identity(self):
        run_id = "a" * 32
        ready = tree(screen="probe-screen:portfolio-appearance;probe-scenario:ready;probe-run:" + run_id)
        self.assertIsNotNone(ready_marker(ready, "portfolio-appearance", "ready", run_id))
        self.assertIsNone(ready_marker(ready, "portfolio-appearance", "ready", "b" * 32))
        command = Mock(side_effect=["", "Status: ok", RESUMED, RESUMED])
        launch_profile(command, lambda: ready, lambda read, message: read(),
                       expected_screen="portfolio-appearance", scenario="ready", run_id=run_id)
        self.assertEqual(command.call_args_list[1].args[-3:], ("--es", "spectrum_probe_run", run_id))

    def test_unknown_or_unsafe_fixture_run_is_rejected_before_any_command(self):
        for screen, run_id in (("profile", "a" * 32), ("business-risk", "a" * 32),
                               ("portfolio-history", "../user"), ("portfolio-history", "a" * 33),
                               ("portfolio-history", "A" * 32), ("portfolio-history", 123)):
            command = Mock()
            prepared_argument_1 = Mock()
            prepared_argument_2 = Mock()
            with self.subTest(screen=screen, run_id=run_id), self.assertRaises(ValueError):
                launch_profile(command, prepared_argument_1, prepared_argument_2, expected_screen=screen, run_id=run_id)
            command.assert_not_called()

    def test_business_launch_requires_exact_screen_and_scenario(self):
        ready = tree(screen="probe-screen:business-risk;probe-scenario:partial")
        self.assertIsNotNone(ready_marker(ready, "business-risk", "partial"))
        self.assertIsNone(ready_marker(ready, "business-risk", "ready"))
        self.assertIsNone(ready_marker(ready, "business-plans", "partial"))
        command = Mock(side_effect=["", "Status: ok", RESUMED, RESUMED])
        launch_profile(command, lambda: ready, lambda read, message: read(), expected_screen="business-risk", scenario="partial")
        self.assertEqual(command.call_args_list[1].args[-6:], ("--es", "spectrum_screen", "business-risk", "--es", "spectrum_scenario", "partial"))

    def test_unsupported_business_scenarios_fail_before_adb(self):
        for screen, scenario in (("business-risk", "job"), ("business-strategy", "job"),
                                 ("business-notifications", "job"), ("business-analysis", "job"), ("profile", "ready"),
                                 ("business-plans", "unknown")):
            command = Mock()
            prepared_argument_1 = Mock()
            prepared_argument_2 = Mock()
            with self.subTest(screen=screen, scenario=scenario), self.assertRaises(ValueError):
                launch_profile(command, prepared_argument_1, prepared_argument_2, expected_screen=screen, scenario=scenario)
            command.assert_not_called()

    def test_host_launch_timeout_still_requires_exact_ready_screen(self):
        command = Mock(side_effect=["", subprocess.TimeoutExpired("am start", 15), RESUMED, RESUMED])
        read_tree = Mock(return_value=tree(screen="probe-screen:home"))
        launch_profile(command, read_tree, lambda read, message: read(), expected_screen="home")
        self.assertEqual(command.call_count, 4)
        self.assertEqual(command.call_args_list[1].args[-1], "home")
        read_tree.assert_called_once()

    def test_host_timeout_with_wrong_or_missing_screen_fails(self):
        for screen in ("probe-screen:profile", "", "probe-screen:portfolio"):
            with self.subTest(screen=screen):
                command = Mock(side_effect=["", subprocess.TimeoutExpired("am start", 15), RESUMED])
                with self.assertRaises(AssertionError):
                    launch_profile(command, lambda: tree(screen=screen), lambda read, message: read(), expected_screen="home")

    def test_host_timeout_with_unresumed_activity_never_reads_old_frame(self):
        command = Mock(side_effect=["", subprocess.TimeoutExpired("am start", 15), "lastResumedActivity " + ACTIVITY])
        read_tree = Mock(return_value=tree(screen="probe-screen:home"))
        with self.assertRaises(AssertionError):
            launch_profile(command, read_tree, lambda read, message: read(), expected_screen="home")
        read_tree.assert_not_called()

    def test_nonlaunch_timeout_is_not_recovered(self):
        command = Mock(side_effect=subprocess.TimeoutExpired("am force-stop", 15))
        read_tree, wait = Mock(), Mock()
        with self.assertRaises(subprocess.TimeoutExpired):
            launch_profile(command, read_tree, wait)
        read_tree.assert_not_called()
        wait.assert_not_called()

    def test_unknown_screen_is_rejected_before_adb(self):
        command = Mock()
        mock_argument = Mock()
        mock_argument_next = Mock()
        with self.assertRaises(ValueError):
            launch_profile(command, mock_argument, mock_argument_next, expected_screen="other")
        command.assert_not_called()

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
