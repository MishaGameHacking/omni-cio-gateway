"""Disposable setup preconditions are explicit, reversible, and not a UI pass."""
import sys
from pathlib import Path
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from emulator_user_setup import completed_emulator_setup


def enter_setup(probe, failure=None):
    with completed_emulator_setup(probe) as state:
        if failure is not None:
            raise failure
        return state


class EmulatorSetupTests(unittest.TestCase):
    def probe(self, provisioned="1", setup="0"):
        state = {"device_provisioned": provisioned, "user_setup_complete": setup}
        probe = Mock()
        def command(*args, **kwargs):
            if args == ("emu", "avd", "name"):
                return "analyst-install-35-1\nOK"
            if args == ("shell", "getprop", "ro.kernel.qemu"):
                return "1"
            if args == ("shell", "am", "get-current-user"):
                return "0"
            if args[:2] == ("shell", "settings"):
                operation, _, name = args[2:5]
                if operation == "get":
                    return state[name]
                state[name] = "null" if operation == "delete" else args[5]
                return ""
            raise AssertionError("Unexpected command")
        probe.command.side_effect = command
        return probe, state

    def test_completes_unfinished_user_and_restores_original(self):
        probe, state = self.probe()
        with completed_emulator_setup(probe) as observed:
            self.assertEqual(observed, {"device_provisioned": "1", "user_setup_complete": "1"})
            self.assertEqual(state, observed)
        self.assertEqual(state, {"device_provisioned": "1", "user_setup_complete": "0"})

    def test_already_completed_session_is_not_mutated(self):
        probe, state = self.probe(setup="1")
        with completed_emulator_setup(probe):
            pass
        self.assertEqual(state["user_setup_complete"], "1")
        self.assertFalse(any("put" in call.args or "delete" in call.args
                             for call in probe.command.call_args_list))

    def test_absent_flags_are_restored_as_absent_even_on_failure(self):
        probe, state = self.probe("null", "null")
        failure = AssertionError("actual UI failure")
        with self.assertRaisesRegex(AssertionError, "actual UI failure"):
            enter_setup(probe, failure)
        self.assertEqual(set(state.values()), {"null"})

    def test_invalid_setting_fails_before_any_write(self):
        probe, _ = self.probe(setup="1; injected")
        with self.assertRaisesRegex(AssertionError, "Unknown Android setup flag"):
            enter_setup(probe)
        self.assertFalse(any("put" in call.args for call in probe.command.call_args_list))

    def test_physical_other_avd_and_secondary_user_are_not_modified(self):
        for replacement, value in [(("emu", "avd", "name"), "personal-avd"),
                (("shell", "getprop", "ro.kernel.qemu"), "0"),
                (("shell", "am", "get-current-user"), "10")]:
            with self.subTest(command=replacement):
                probe, _ = self.probe()
                original = probe.command.side_effect
                probe.command.side_effect = lambda *args: value if args == replacement else original(*args)
                with self.assertRaises(ValueError):
                    enter_setup(probe)
                self.assertFalse(any("put" in call.args for call in probe.command.call_args_list))

    def test_failed_setting_readback_cannot_enter_ui_scenario(self):
        probe, state = self.probe()
        original = probe.command.side_effect
        def command(*args):
            if args == ("shell", "settings", "put", "secure", "user_setup_complete", "1"):
                return ""
            return original(*args)
        probe.command.side_effect = command
        with self.assertRaisesRegex(AssertionError, "setup did not complete"):
            enter_setup(probe)
        self.assertEqual(state["user_setup_complete"], "0")


if __name__ == "__main__":
    unittest.main()
