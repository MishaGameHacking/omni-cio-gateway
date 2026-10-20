"""No-device regressions; these do not replace the real API37 4KB/16KB UI gate."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from xml.etree.ElementTree import Element

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from emulator_rotation import physical_quarter_turn, landscape_frame


class Console:
    def __init__(self, *, null=False, fail_turn=None):
        self.calls = []
        self.turns = 0
        self.fail_turn = fail_turn
        self.initial = {"accelerometer_rotation": "null" if null else "0",
                        "user_rotation": "null" if null else "2"}
        self.settings = self.initial.copy()

    def __call__(self, *args):
        self.calls.append(args)
        if args == ("emu", "rotate"):
            self.turns += 1
            return "KO: rejected\n" if self.turns == self.fail_turn else "OK\n"
        if args[2] == "get":
            return self.settings[args[4]]
        self.settings[args[4]] = "null" if args[2] == "delete" else args[5]
        return ""


class RotationTests(unittest.TestCase):
    def test_original_pose_and_settings_restored(self):
        console = Console()
        with physical_quarter_turn(console):
            self.assertEqual(console.settings["accelerometer_rotation"], "1")
            self.assertEqual(console.turns, 1)
        self.assertEqual(console.turns, 4)
        self.assertEqual(console.settings, console.initial)

    def test_absent_settings_remain_absent(self):
        console = Console(null=True)
        with physical_quarter_turn(console):
            pass
        self.assertEqual(console.settings, console.initial)
        self.assertEqual(sum(call[2:3] == ("delete",) for call in console.calls), 2)

    def test_ui_failure_still_restores_pose(self):
        console = Console()
        error = AssertionError("native state lost")
        session = physical_quarter_turn(console)
        with self.assertRaisesRegex(AssertionError, "native state"):
            with session:
                raise error
        self.assertEqual(console.turns, 4)
        self.assertEqual(console.settings, console.initial)

    def test_rejected_rotation_is_not_success(self):
        console = Console(fail_turn=1)
        session = physical_quarter_turn(console)
        entered = False
        with self.assertRaisesRegex(RuntimeError, "rejected"):
            with session:
                entered = True
        self.assertFalse(entered)
        self.assertEqual(console.turns, 1)
        self.assertEqual(console.settings, console.initial)

    def test_cleanup_error_does_not_hide_original_failure(self):
        console = Console(fail_turn=2)
        error = AssertionError("native state lost")
        with self.assertRaises(AssertionError) as caught:
            with physical_quarter_turn(console):
                raise error
        self.assertIs(caught.exception, error)
        self.assertIn("restore emulator rotation", error.__notes__[0])
        self.assertEqual(console.settings, console.initial)

    def test_cleanup_failure_fails_successful_body(self):
        console = Console(fail_turn=2)
        with self.assertRaisesRegex(RuntimeError, "restore emulator rotation"):
            with physical_quarter_turn(console):
                pass
        self.assertEqual(console.settings, console.initial)

    def test_unreadable_settings_fail_before_any_mutation(self):
        console = Console()
        console.settings["user_rotation"] = "error"
        session = physical_quarter_turn(console)
        entered = False
        with self.assertRaises(ValueError):
            with session:
                entered = True
        self.assertFalse(entered)
        self.assertTrue(all(call[2] == "get" for call in console.calls))


def frame(width=1280, height=720):
    return Element("hierarchy", {"display-width": str(width), "display-height": str(height)})


def ready(tree):
    return {} if int(tree.get("display-width")) > int(tree.get("display-height")) else None


class Probe:
    def __init__(self, trees=None):
        self.trees = iter(trees) if trees else None

    def tree(self):
        return next(self.trees) if self.trees else frame()

    def wait_for(self, observe, message):
        for _ in range(3):
            result = observe()
            if result is not None:
                return result
        raise AssertionError(message)


class FrameTests(unittest.TestCase):
    def test_matching_real_frame_passes(self):
        probe = Probe()
        probe.capture = lambda name: SimpleNamespace(width=1280, height=720)
        result = landscape_frame(probe, ready, lambda image: image, "rotation")
        self.assertEqual(result["png"], [1280, 720])

    def test_stale_portrait_frame_retries_without_pixel_rotation(self):
        probe = Probe()
        pictures = iter([SimpleNamespace(width=720, height=1280), SimpleNamespace(width=1280, height=720)])
        probe.capture = lambda name: next(pictures)
        result = landscape_frame(probe, ready, lambda image: image, "rotation")
        self.assertEqual(result["png"], [1280, 720])

    def test_persistent_portrait_or_scaled_capture_fails(self):
        for width, height in [(720, 1280), (640, 360), (720, 720)]:
            with self.subTest(size=(width, height)):
                probe = Probe()
                probe.capture = lambda name: SimpleNamespace(width=width, height=height)
                with self.assertRaisesRegex(AssertionError, "did not agree"):
                    landscape_frame(probe, ready, lambda image: image, "rotation")

    def test_changing_geometry_does_not_pass(self):
        probe = Probe([frame(), frame(720, 1280)] * 3)
        probe.capture = lambda name: SimpleNamespace(width=1280, height=720)
        with self.assertRaises(AssertionError):
            landscape_frame(probe, ready, lambda image: image, "rotation")

    def test_capture_failure_is_not_treated_as_orientation_success(self):
        probe = Probe()
        def failed_capture(name):
            raise RuntimeError("capture transport failed")
        probe.capture = failed_capture
        with self.assertRaisesRegex(RuntimeError, "capture transport"):
            landscape_frame(probe, ready, lambda image: image, "rotation")


if __name__ == "__main__":
    unittest.main()
