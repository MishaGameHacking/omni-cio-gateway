"""First-boot regressions execute the real preparation and setup contexts."""
import ast
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from emulator_boot_readiness import PACKAGE_BARRIERS, prepared_emulator_session
from backend.android_runtime_contract import MIN_SDK, RUNTIME_PROFILES


class Device:
    def __init__(self):
        self.name = "analyst-install-123-1"
        self.api = str(MIN_SDK)
        self.qemu = "1"
        self.user = "0"
        self.pid = "580"
        self.flags = {"device_provisioned": "1", "user_setup_complete": "0"}
        self.calls = []
        self.barrier_output = "Success\n"
        self.barrier_code = 0
        self.barrier_error = None
        self.restart_at_barrier = False
        self.ignore_setup_write = False
        self.fail_restore = False

    def __call__(self, *args, timeout):
        self.calls.append((args, timeout))
        code, text = 0, ""
        if args == ("emu", "avd", "name"):
            text = self.name + "\nOK\n"
        elif args[:2] == ("shell", "getprop"):
            text = {"ro.build.version.sdk": self.api, "ro.kernel.qemu": self.qemu}[args[2]]
        elif args == ("shell", "am", "get-current-user"):
            text = self.user
        elif args == ("shell", "pidof", "system_server"):
            text = self.pid
        elif args[:2] == ("shell", "settings"):
            action, name = args[2], args[4]
            if action == "get":
                text = self.flags[name]
            elif self.fail_restore and (action == "delete" or args[5] == "0"):
                code = 1
            elif action == "delete":
                self.flags[name] = "null"
            elif not self.ignore_setup_write:
                self.flags[name] = args[5]
        elif args[:3] == ("shell", "cmd", "package"):
            if self.barrier_error is not None:
                raise self.barrier_error
            code, text = self.barrier_code, self.barrier_output
            if self.restart_at_barrier:
                self.pid = "3461"
        else:
            raise AssertionError("Unexpected device operation: " + repr(args))
        return subprocess.CompletedProcess(args, code, text, "")


class BootReadinessTests(unittest.TestCase):
    def prepare(self, device, **kwargs):
        return prepared_emulator_session(device, kwargs.get("name", "analyst-install-123-1"),
                                         kwargs.get("api", MIN_SDK))

    def test_both_barriers_precede_body_and_setup_is_kept_until_exit(self):
        device = Device()
        with self.prepare(device) as receipt:
            commands = [call[0] for call in device.calls if call[0][:3] == ("shell", "cmd", "package")]
            self.assertEqual([command[3] for command in commands], list(PACKAGE_BARRIERS))
            self.assertEqual(device.flags["user_setup_complete"], "1")
            self.assertFalse(receipt["system_server_unchanged"])
        self.assertTrue(receipt["system_server_unchanged"])
        self.assertEqual(device.flags["user_setup_complete"], "0")
        self.assertTrue(all(timeout == (70 if args[:3] == ("shell", "cmd", "package") else 15)
                            for args, timeout in device.calls))

    def test_current_profiles_use_same_barriers_without_changing_jit(self):
        for profile in RUNTIME_PROFILES:
            device = Device()
            device.api = str(profile.api)
            with self.subTest(profile=profile.key), self.prepare(device, api=profile.api) as receipt:
                self.assertEqual(receipt["package_barriers"], list(PACKAGE_BARRIERS))
            self.assertTrue(receipt["system_server_unchanged"])
            self.assertFalse(any("setprop" in args or "root" in args for args, _ in device.calls))

    def test_wrong_avd_api_phone_and_secondary_user_fail_before_mutations(self):
        for field, value in (("name", "another-avd"), ("api", str(MIN_SDK - 1)), ("qemu", "0"), ("user", "10")):
            with self.subTest(field=field):
                device = Device()
                setattr(device, field, value)
                with self.assertRaises(ValueError), self.prepare(device):
                    self.fail("Must not enter body")
                self.assertFalse(any("put" in args for args, _ in device.calls))

    def test_invalid_arguments_never_access_a_device(self):
        for kwargs in ({"name": "analyst-install-1-1;reboot"}, {"api": True}, {"api": MIN_SDK - 1}):
            device = Device()
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError), self.prepare(device, **kwargs):
                self.fail("Must not enter body")
            self.assertEqual(device.calls, [])

    def test_empty_multiple_invalid_or_out_of_range_server_pid_is_rejected(self):
        for value in ("", "580 3461", "0", "-1", "2147483648", "580;reboot"):
            device = Device()
            device.pid = value
            with self.subTest(value=value), self.assertRaises(RuntimeError), self.prepare(device):
                self.fail("Must not enter body")
            self.assertFalse(any("put" in args for args, _ in device.calls))

    def test_timeout_failure_unknown_command_and_substring_never_pass(self):
        for code, output in ((1, "Success"), (0, ""), (0, "NotSuccess"), (0, "Unknown command"),
                             (0, "Timeout. PackageManager handlers are still busy.")):
            device = Device()
            device.barrier_code, device.barrier_output = code, output
            with self.subTest(output=output), self.assertRaises(RuntimeError), self.prepare(device):
                self.fail("Must not enter body")
            self.assertEqual(device.flags["user_setup_complete"], "0")

    def test_actual_host_timeout_propagates_and_restores(self):
        device = Device()
        error = subprocess.TimeoutExpired("barrier", 70)
        device.barrier_error = error
        with self.assertRaises(subprocess.TimeoutExpired) as caught, self.prepare(device):
            self.fail("Must not enter body")
        self.assertIs(caught.exception, error)
        self.assertEqual(device.flags["user_setup_complete"], "0")

    def test_restart_during_preparation_is_not_rebound_or_retried(self):
        device = Device()
        device.restart_at_barrier = True
        with self.assertRaisesRegex(RuntimeError, "restarted"), self.prepare(device):
            self.fail("Must not enter body")
        self.assertEqual(len([args for args, _ in device.calls if args[:3] == ("shell", "cmd", "package")]), 1)

    def test_restart_during_test_body_is_never_a_pass(self):
        device = Device()
        with self.assertRaisesRegex(RuntimeError, "restarted"), self.prepare(device) as receipt:
            device.pid = "3461"
        self.assertFalse(receipt["system_server_unchanged"])
        self.assertEqual(device.flags["user_setup_complete"], "0")

    def test_app_assertion_is_preserved_without_retry(self):
        device = Device()
        error = AssertionError("Actual app failed")
        with self.assertRaises(AssertionError) as caught, self.prepare(device) as receipt:
            raise error
        self.assertIs(caught.exception, error)
        self.assertFalse(receipt["system_server_unchanged"])
        self.assertEqual(device.flags["user_setup_complete"], "0")

    def test_cleanup_error_blocks_an_otherwise_successful_session(self):
        device = Device()
        with self.assertRaises(RuntimeError), self.prepare(device) as receipt:
            device.fail_restore = True
        self.assertFalse(receipt["system_server_unchanged"])

    def test_cleanup_error_does_not_mask_an_app_failure(self):
        device = Device()
        error = AssertionError("Actual app failed")
        with self.assertRaises(AssertionError) as caught, self.prepare(device):
            device.fail_restore = True
            raise error
        self.assertIs(caught.exception, error)
        self.assertIn("Setup cleanup failed", error.__notes__[0])

    def test_absent_flags_are_restored_as_absent(self):
        device = Device()
        device.flags = dict.fromkeys(device.flags, "null")
        with self.prepare(device):
            self.assertEqual(set(device.flags.values()), {"1"})
        self.assertEqual(set(device.flags.values()), {"null"})

    def test_completed_flags_are_not_rewritten(self):
        device = Device()
        device.flags["user_setup_complete"] = "1"
        with self.prepare(device):
            pass
        self.assertFalse(any("put" in args or "delete" in args for args, _ in device.calls))

    def test_failed_setup_readback_never_runs_a_barrier(self):
        device = Device()
        device.ignore_setup_write = True
        with self.assertRaises(AssertionError), self.prepare(device):
            self.fail("Must not enter body")
        self.assertFalse(any("package" in args for args, _ in device.calls))

    def test_installation_and_entire_ui_suite_are_inside_prepared_session(self):
        source = Path(__file__).resolve().parents[1] / "test_apk_installation.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        prepared = [node for node in ast.walk(tree) if isinstance(node, ast.With)
                    and any(isinstance(item.context_expr, ast.Call)
                            and getattr(item.context_expr.func, "id", None) == "prepared_emulator_session"
                            for item in node.items)]
        self.assertEqual(len(prepared), 1)
        calls = [node for node in ast.walk(prepared[0]) if isinstance(node, ast.Call)]
        self.assertEqual(sum(getattr(call.func, "id", "") == "install" for call in calls), 4)
        self.assertEqual(sum(getattr(call.func, "id", "") == "launch_candidate" for call in calls), 2)
        self.assertEqual(sum(getattr(call.func, "id", "") == "record_profile_check" for call in calls), 1)
        self.assertFalse(any(isinstance(node, ast.Return) for node in ast.walk(prepared[0])))


if __name__ == "__main__":
    unittest.main()
