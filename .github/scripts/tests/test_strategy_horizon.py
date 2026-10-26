"""Exercise the actual detail verifier against bounded native scroll frames.

Only transport frames/input are simulated; ProfileProbe reveal, settlement and
native-input parsing are real. Emulator acceptance is a separate Windows run.
"""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from profile_ui_probe import ProfileProbe
import profile_scroll
from test_navigation_detail_probe import NativeFrames, case, frame, node


class HorizonFrames(NativeFrames):
    def __init__(self, position=0, *, keyboard=False, obstruction=None, stuck=False):
        super().__init__(None)
        self.position = position
        self.keyboard = keyboard
        self.obstruction = obstruction
        self.stuck = stuck
        self.scrolls = []
        self.value = self.current_frame

    def current_frame(self, _):
        tree = frame(menu=False)
        tree.set("keyboard-visible", str(self.keyboard).lower())
        viewport = node(tree[0], bounds="[0,100][320,400]",
                        **{"resource-id": "workspace-content", "scrollable": "true"})
        if self.position == 0:
            node(viewport, bounds="[10,110][310,165]", text="Действует версия 3")
        if self.position == 1 or self.obstruction is not None:
            target = node(viewport, bounds="[10,200][310,256]", **{
                "resource-id": "strategy-horizon", "text": "36", "editable": "true",
                "focused": str(self.keyboard).lower(), "selection-start": "2", "selection-end": "2"})
            if self.position != 1 and self.obstruction == "clipped":
                target.set("bounds", "[10,390][310,446]")
            if self.position != 1 and self.obstruction == "foreign":
                target.set("package", "foreign.app")
        return tree

    def _semantic_scroll_callback(self, area, direction):
        def scroll(*coordinates):
            if area != "workspace-content":
                raise AssertionError("Unexpected list")
            self.scrolls.append(direction)
            if not self.stuck:
                self.position = max(0, min(2, self.position + (1 if direction == "end" else -1)))
        return scroll

    reveal = ProfileProbe.reveal
    reveal_resource = ProfileProbe.reveal_resource
    resource_tap_target = ProfileProbe.resource_tap_target
    tap_resource = ProfileProbe.tap_resource

    def _show_resource_on_screen(self, area, resource):
        raise AssertionError("A fully revealed input must settle before the tap")

    def tap_node(self, target):
        super().tap_node(target)
        self.keyboard = True


class StrategyHorizonTests(unittest.TestCase):
    def setUp(self):
        delay = patch.object(profile_scroll.time, "sleep", return_value=None)
        delay.start()
        self.addCleanup(delay.stop)

    def test_initial_goal_cards_require_downward_scroll_before_capture(self):
        probe = HorizonFrames()
        case(probe).screen_anchor("strategy")
        self.assertEqual(probe.position, 1)
        self.assertEqual(probe.scrolls, ["end"])
        self.assertEqual(probe.taps, [])

    def test_saved_position_below_editor_returns_to_top_then_finds_and_focuses_it(self):
        probe = HorizonFrames(2)
        result = case(probe).horizon("36")
        self.assertEqual(probe.scrolls, ["start", "start", "end"])
        self.assertEqual(len(probe.taps), 1)
        self.assertEqual(result["text"], "36")
        self.assertTrue(probe.keyboard)

    def test_visible_editor_with_keyboard_needs_no_scroll_or_draft_replacement(self):
        probe = HorizonFrames(1, keyboard=True)
        result = case(probe).horizon("36")
        self.assertEqual(probe.scrolls, [])
        self.assertEqual(len(probe.taps), 1)
        self.assertEqual(result["text"], "36")

    def test_clipped_or_foreign_resource_cannot_skip_revealing_the_real_input(self):
        for obstruction in ("clipped", "foreign"):
            probe = HorizonFrames(obstruction=obstruction)
            with self.subTest(obstruction=obstruction):
                case(probe).screen_anchor("strategy")
                self.assertEqual(probe.scrolls, ["end"])
                self.assertEqual(probe.position, 1)
                self.assertEqual(probe.taps, [])

    def test_unreachable_input_keeps_the_bounded_failure_and_never_taps(self):
        probe = HorizonFrames(stuck=True)
        with self.assertRaisesRegex(AssertionError, "List target not reachable: strategy-horizon"):
            case(probe).horizon("36")
        self.assertEqual(probe.scrolls, ["end"] * 10)
        self.assertEqual(probe.taps, [])

    def test_wrong_retained_draft_fails_after_one_real_target_tap(self):
        probe = HorizonFrames(1, keyboard=True)
        with self.assertRaisesRegex(AssertionError, "did not retain 48"):
            case(probe).horizon("48")
        self.assertEqual(len(probe.taps), 1)
        self.assertEqual(probe.scrolls, [])


if __name__ == "__main__":
    unittest.main()
