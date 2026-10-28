"""Exercise the actual fixture-install boundary; no emulator, application or network."""
from contextlib import ExitStack
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import Mock, patch

SPEC = importlib.util.spec_from_file_location(
    "fixture_installation_harness", Path(__file__).resolve().parents[1] / "test_apk_installation.py")
harness = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(harness)
PACKAGE = "ru.omnicio.app.debug"
HOME = "topResumedActivity=ActivityRecord{abc u0 com.android.launcher3/.Launcher t1}\n"
TARGET = "mResumedActivity: ActivityRecord{def u0 ru.omnicio.app.debug/ru.omnicio.app.MainActivity}\n"
APK = Path("synthetic-debug.apk")


def response(code=0, stdout="", stderr=""):
    return subprocess.CompletedProcess([], code, stdout, stderr)


class Clock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class DebugFixtureReplacementTests(unittest.TestCase):
    def clock_context(self, clock):
        stack = ExitStack()
        stack.enter_context(patch.object(harness.time, "monotonic", clock.monotonic))
        stack.enter_context(patch.object(harness.time, "sleep", clock.sleep))
        return stack

    def test_stop_and_two_absent_pid_observations_precede_exact_fixture_install(self):
        clock = Clock()
        events = []
        answers = iter((response(), response(1), response(stdout=HOME), response(1)))

        def device(*args, timeout):
            self.assertGreater(timeout, 0)
            self.assertLessEqual(timeout, 5)
            events.append(args)
            return next(answers)

        def install(*args, **kwargs):
            events.append(("install", args, kwargs))
            return "actual-callback-result"

        with self.clock_context(clock):
            actual = harness.install_debug_ui_fixture(device, install, APK)
        self.assertEqual(actual, "actual-callback-result")
        self.assertEqual(events, [
            ("shell", "am", "force-stop", PACKAGE),
            ("shell", "pidof", PACKAGE),
            ("shell", "dumpsys", "-t", "2", "activity", "activities"),
            ("shell", "pidof", PACKAGE),
            ("install", ("debug_ui_fixture_install", APK), {"update": True}),
        ])
        self.assertEqual(clock.sleeps, [])

    def test_live_process_delays_install_without_another_force_stop(self):
        clock = Clock()
        device = Mock(side_effect=[response(), response(stdout="123 456\n"), response(1), response(stdout=HOME), response(1)])
        install = Mock()
        with self.clock_context(clock):
            harness.install_debug_ui_fixture(device, install, APK)
        self.assertEqual(clock.sleeps, [0.25])
        self.assertEqual(sum(call.args[:3] == ("shell", "am", "force-stop") for call in device.call_args_list), 1)
        install.assert_called_once_with("debug_ui_fixture_install", APK, update=True)

    def test_target_foreground_record_blocks_even_when_pid_is_absent(self):
        clock = Clock()
        device = Mock(side_effect=[response(), response(1), response(stdout=TARGET), response(1), response(stdout=HOME), response(1)])
        install = Mock()
        with self.clock_context(clock):
            harness.install_debug_ui_fixture(device, install, APK)
        self.assertEqual(clock.sleeps, [0.25])
        install.assert_called_once_with("debug_ui_fixture_install", APK, update=True)

    def test_pid_reappearing_during_foreground_read_is_not_accepted(self):
        clock = Clock()
        device = Mock(side_effect=[response(), response(1), response(stdout=HOME), response(stdout="789"), response(1), response(stdout=HOME), response(1)])
        install = Mock()
        with self.clock_context(clock):
            harness.install_debug_ui_fixture(device, install, APK)
        self.assertEqual(clock.sleeps, [0.25])
        self.assertEqual(device.call_count, 7)
        install.assert_called_once()

    def test_similar_package_name_does_not_match_target_foreground(self):
        clock = Clock()
        other = HOME.replace("com.android.launcher3/.Launcher", PACKAGE + ".other/.MainActivity")
        device = Mock(side_effect=[response(), response(1), response(stdout=other), response(1)])
        install = Mock()
        with self.clock_context(clock):
            harness.install_debug_ui_fixture(device, install, APK)
        install.assert_called_once()

    def test_failed_or_ambiguous_force_stop_never_installs_or_probes(self):
        for answer in (response(1), response(stdout="Error: failed"), response(stderr="denied")):
            with self.subTest(answer=answer), self.clock_context(Clock()):
                device, install = Mock(return_value=answer), Mock()
                with self.assertRaisesRegex(RuntimeError, "Could not stop"):
                    harness.install_debug_ui_fixture(device, install, APK)
                self.assertEqual(device.call_count, 1)
                install.assert_not_called()

    def test_pid_command_failure_is_not_process_absence(self):
        for answer in (response(), response(2), response(1, "123"), response(stdout="not-a-pid"), response(1, stderr="error")):
            with self.subTest(answer=answer), self.clock_context(Clock()):
                device, install = Mock(side_effect=[response(), answer]), Mock()
                with self.assertRaisesRegex(RuntimeError, "absence was not established"):
                    harness.install_debug_ui_fixture(device, install, APK)
                install.assert_not_called()

    def test_incomplete_or_failed_activity_dump_never_installs(self):
        for answer in (response(stdout="DUMP TIMEOUT\n"+HOME), response(1, HOME), response(stdout=HOME, stderr="binder error")):
            with self.subTest(answer=answer), self.clock_context(Clock()):
                device, install = Mock(side_effect=[response(), response(1), answer]), Mock()
                with self.assertRaisesRegex(RuntimeError, "foreground observation failed"):
                    harness.install_debug_ui_fixture(device, install, APK)
                install.assert_not_called()

    def test_missing_resumed_identity_reaches_deadline_without_installing(self):
        clock = Clock()
        def device(*args, timeout):
            if args[:3] == ("shell", "am", "force-stop"): return response()
            if args[:2] == ("shell", "pidof"): return response(1)
            return response(stdout="topResumedActivity=null\n")
        install = Mock()
        with self.clock_context(clock), self.assertRaises(TimeoutError):
            harness.install_debug_ui_fixture(device, install, APK, timeout_seconds=1)
        self.assertEqual(clock.now, 1)
        self.assertTrue(all(0 < delay <= 0.25 for delay in clock.sleeps))
        install.assert_not_called()

    def test_command_timeout_propagates_without_install_or_retry(self):
        failure = subprocess.TimeoutExpired(["synthetic-adb"], 5)
        device, install = Mock(side_effect=failure), Mock()
        with self.clock_context(Clock()), self.assertRaises(subprocess.TimeoutExpired) as caught:
            harness.install_debug_ui_fixture(device, install, APK)
        self.assertIs(caught.exception, failure)
        self.assertEqual(device.call_count, 1)
        install.assert_not_called()

    def test_late_absent_response_cannot_authorize_install(self):
        clock = Clock()
        answers = iter((response(), response(1), response(stdout=HOME), response(1)))
        calls = []
        def device(*args, timeout):
            calls.append(args)
            if len(calls) == 4: clock.now = 1.0
            return next(answers)
        install = Mock()
        with self.clock_context(clock), self.assertRaises(TimeoutError):
            harness.install_debug_ui_fixture(device, install, APK, timeout_seconds=1)
        self.assertEqual(len(calls), 4)
        install.assert_not_called()

    def test_remaining_deadline_bounds_each_command(self):
        clock = Clock()
        timeouts = []
        answers = iter((response(), response(1), response(stdout=HOME), response(1)))
        def device(*args, timeout):
            self.assertGreater(timeout, 0)
            self.assertLessEqual(timeout, 1-clock.now)
            timeouts.append(timeout)
            clock.now += 0.2
            return next(answers)
        install = Mock()
        with self.clock_context(clock):
            harness.install_debug_ui_fixture(device, install, APK, timeout_seconds=1)
        self.assertEqual(len(timeouts), 4)
        self.assertLess(timeouts[-1], timeouts[0])
        install.assert_called_once()

    def test_original_install_failure_propagates(self):
        device = Mock(side_effect=[response(), response(1), response(stdout=HOME), response(1)])
        failure = RuntimeError("synthetic original install failure")
        install = Mock(side_effect=failure)
        with self.clock_context(Clock()), self.assertRaises(RuntimeError) as caught:
            harness.install_debug_ui_fixture(device, install, APK)
        self.assertIs(caught.exception, failure)
        install.assert_called_once_with("debug_ui_fixture_install", APK, update=True)

    def test_invalid_budget_fails_before_any_device_command(self):
        for value in (0, 31, True, 1.5, "1"):
            device, install = Mock(), Mock()
            with self.subTest(value=value), self.assertRaises(ValueError):
                harness.install_debug_ui_fixture(device, install, APK, timeout_seconds=value)
            device.assert_not_called()
            install.assert_not_called()


if __name__ == "__main__":
    unittest.main()
