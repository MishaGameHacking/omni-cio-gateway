"""Boot timing/CLI regressions with fake time and transports, never an Android pass."""
from contextlib import contextmanager, nullcontext
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS.parents[1]))
import test_apk_installation as installation


class Clock:
    def __init__(self):
        self.seconds = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.seconds

    def sleep(self, seconds):
        self.sleeps.append((self.seconds, seconds))
        self.seconds += seconds


class BootBudgetTests(unittest.TestCase):
    @contextmanager
    def simulated(self, clock, command):
        with patch.object(installation, "time", clock), \
                patch.object(installation, "run", side_effect=command) as calls, \
                patch("builtins.print") as output:
            yield calls, output

    def test_slow_progress_requires_the_explicit_extended_budget(self):
        for budget in (600, 1200):
            with self.subTest(budget=budget):
                clock = Clock()
                def command(args, *, timeout):
                    clock.seconds += min(1.0, timeout)
                    return subprocess.CompletedProcess(args, 0, "1" if clock.seconds >= 700 else "0", "")
                with self.simulated(clock, command) as (_, output):
                    expectation = self.assertRaises(TimeoutError) if budget == 600 else nullcontext()
                    with expectation:
                        installation.wait_for_boot("adb", "emulator-5600", Mock(poll=Mock(return_value=None)),
                                                   timeout_seconds=budget)
                record = json.loads(output.call_args.args[0].split("=", 1)[1])
                self.assertEqual(record["requested_seconds"], budget)
                self.assertEqual(record["boot_completed"], budget == 1200)
                self.assertEqual(record["elapsed_seconds"], clock.seconds)
                self.assertLessEqual(clock.seconds, budget)
                if budget == 1200:
                    self.assertGreater(clock.seconds, 600)

    def test_unready_or_hung_adb_never_overruns_the_remaining_budget(self):
        for response in ((0, "0"), (0, "true"), (1, "1"), None):
            with self.subTest(response=response):
                clock = Clock()
                requests = []
                def command(args, *, timeout):
                    requests.append((clock.seconds, timeout))
                    self.assertGreater(timeout, 0)
                    self.assertLessEqual(timeout, min(15, 600 - clock.seconds))
                    clock.seconds += min(14.0, timeout) if response is not None else timeout
                    if response is None:
                        raise subprocess.TimeoutExpired(args, timeout)
                    return subprocess.CompletedProcess(args, response[0], response[1], "")
                with self.simulated(clock, command), self.assertRaises(TimeoutError):
                    installation.wait_for_boot("adb", "emulator-5600", Mock(poll=Mock(return_value=None)))
                self.assertTrue(requests)
                self.assertEqual(clock.seconds, 600)
                self.assertTrue(all(0 < duration <= min(5, 600 - at) for at, duration in clock.sleeps))
                if response is not None:
                    self.assertLess(requests[-1][1], 15)

    def test_a_late_positive_reply_cannot_pass(self):
        clock = Clock()
        def command(args, *, timeout):
            clock.seconds = 601
            return subprocess.CompletedProcess(args, 0, "1", "")
        with self.simulated(clock, command) as (_, output), self.assertRaises(TimeoutError):
            installation.wait_for_boot("adb", "emulator-5600", Mock(poll=Mock(return_value=None)))
        record = json.loads(output.call_args.args[0].split("=", 1)[1])
        self.assertEqual(record["outcome"], "timeout")
        self.assertFalse(record["boot_completed"])

    def test_invalid_budgets_are_rejected_before_process_or_device_access(self):
        for value in (True, False, 0, 599, 601, 1201, 1200.0, "1200", None):
            process = Mock()
            with self.subTest(value=value), patch.object(installation, "run") as command:
                with self.assertRaises(ValueError):
                    installation.wait_for_boot("adb", "emulator-5600", process, timeout_seconds=value)
                process.poll.assert_not_called()
                command.assert_not_called()

    def test_sidecar_records_boot_and_diagnostic_io_cannot_mask_transport_loss(self):
        with tempfile.TemporaryDirectory() as directory:
            observation = Path(directory) / "boot-observation.json"
            clock = Clock()
            response = subprocess.CompletedProcess([], 0, "1\n", "")
            with self.simulated(clock, lambda *args, **kwargs: response):
                installation.wait_for_boot("adb", "emulator-5600", Mock(poll=Mock(return_value=None)),
                                           observation_path=observation)
            record = json.loads(observation.read_text())
            self.assertEqual(record["outcome"], "boot_completed")
            self.assertEqual(record["requested_seconds"], 600)
            self.assertIsNone(record["error_type"])
            with self.simulated(clock, Mock()) as (command, _), \
                    patch.object(Path, "write_text", side_effect=OSError("synthetic write failure")), \
                    self.assertRaises(installation.EmulatorTransportLost) as raised:
                installation.wait_for_boot("adb", "emulator-5600", Mock(poll=Mock(return_value=7)),
                                           observation_path=observation)
            command.assert_not_called()
            self.assertIn("Boot observation unavailable: OSError", raised.exception.__notes__)

    def test_boot_timeout_does_not_request_a_second_avd(self):
        clock = Clock()
        attempts = []
        def command(args, *, timeout):
            clock.seconds += timeout
            raise subprocess.TimeoutExpired(args, timeout)
        def execute(attempt):
            attempts.append(attempt)
            installation.wait_for_boot("adb", "emulator-5600", Mock(poll=Mock(return_value=None)))
        with self.simulated(clock, command), self.assertRaises(TimeoutError):
            installation.run_with_transport_retry(execute)
        self.assertEqual(attempts, [1])

    def test_cli_defaults_and_explicit_single_attempt_reach_the_real_dispatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            apk, previous, sdk = root / "candidate.apk", root / "previous.apk", root / "sdk"
            apk.write_bytes(b"synthetic candidate")
            previous.write_bytes(b"synthetic previous")
            sdk.mkdir()
            for extra, budget, count in (([], 600, 2),
                    (["--boot-timeout-seconds", "1200", "--attempts", "1"], 1200, 1)):
                args = ["test_apk_installation.py", "--apk", str(apk), "--previous", str(previous),
                        "--sdk", str(sdk), "--api", "37", "--page-bytes", "4096", "--work-dir",
                        str(root / ("work-" + str(count))), *extra]
                with self.subTest(extra=extra), patch.object(sys, "argv", args), \
                        patch("artifact_test_identity.apk_digest", return_value="a" * 64), \
                        patch("isolated_adb.isolated_adb_server", return_value=nullcontext()), \
                        patch.object(installation, "run_attempt", side_effect=[
                            installation.EmulatorTransportLost("synthetic transport loss"), []]) as attempt, \
                        patch("builtins.print"):
                    expectation = self.assertRaises(installation.EmulatorTransportLost) if count == 1 else nullcontext()
                    with expectation:
                        installation.main()
                self.assertEqual(attempt.call_count, count)
                self.assertEqual([call.kwargs["attempt"] for call in attempt.call_args_list], list(range(1, count + 1)))
                for call in attempt.call_args_list:
                    self.assertEqual(call.kwargs["boot_timeout_seconds"], budget)
                    self.assertEqual(call.kwargs["previous"], previous.resolve())
                    self.assertEqual(call.kwargs["candidate_digest"], "a" * 64)
                    self.assertEqual(call.kwargs["page_size_bytes"], 4096)

    def test_cli_rejects_unbounded_values_before_any_attempt(self):
        base = ["test_apk_installation.py", "--apk", "candidate", "--sdk", "sdk", "--work-dir", "work"]
        for option, value in (("--boot-timeout-seconds", "0"), ("--boot-timeout-seconds", "601"),
                              ("--boot-timeout-seconds", "1201"), ("--attempts", "0"), ("--attempts", "3")):
            with self.subTest(option=option, value=value), patch.object(sys, "argv", base + [option, value]), \
                    patch("sys.stderr", new=io.StringIO()), patch.object(installation, "run_attempt") as attempt, \
                    self.assertRaises(SystemExit) as raised:
                installation.main()
            self.assertEqual(raised.exception.code, 2)
            attempt.assert_not_called()

    def test_kernel_trace_is_enabled_without_inheriting_emulator_logcat(self):
        class LaunchInspected(Exception):
            pass
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            with patch.dict(os.environ, {"ANDROID_LOG_TAGS": "*:V", "RUN_PROFILE_UI_TESTS": "1",
                                         "VK_ICD_FILENAMES": "synthetic-lvp.json"}), \
                    patch.object(installation, "run", return_value=subprocess.CompletedProcess([], 0, "", "")), \
                    patch("emulator_storage.configure_userdata"), \
                    patch.object(installation, "free_emulator_port", return_value=5600), \
                    patch.object(installation.subprocess, "Popen", side_effect=LaunchInspected) as spawn, \
                    patch("builtins.print"):
                with self.assertRaises(LaunchInspected):
                    installation.run_attempt(apk=work / "candidate.apk", candidate_digest="a" * 64,
                                             previous=work / "previous.apk", sdk=work / "sdk", api=37,
                                             work=work, attempt=1, page_size_bytes=4096)
                args = spawn.call_args.args[0]
                child = spawn.call_args.kwargs["env"]
                expected = dict(os.environ)
                expected.pop("ANDROID_LOG_TAGS")
                self.assertEqual(child, expected)
                self.assertEqual(os.environ["ANDROID_LOG_TAGS"], "*:V")
                self.assertIn("-show-kernel", args)
                self.assertNotIn("-logcat", args)
                self.assertEqual(spawn.call_args.kwargs["stdin"], subprocess.DEVNULL)


if __name__ == "__main__":
    unittest.main()
