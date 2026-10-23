"""Run strategy editing through clipped list frames, without device claims."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import strategy_editor_probe as strategy
from profile_scroll import reveal_in_list, reveal_resource_in_list

PACKAGE = "ru.omnicio.app.debug"
AREA = "workspace-content"
HORIZON = "strategy-horizon"
PREVIEW = "Рассчитать влияние"


class StrategyViewportProbe:
    """The status and six vertical choices precede the horizon editor.

    These offline frames model that production order at both font scales. Only
    clipped visible nodes enter a frame. The preview action follows the editor,
    so replacing the empty value also requires traversing back toward the start.
    """

    def __init__(self, font_scale, *, missing_editor=False, invalid_preview=False):
        self.height = 453
        self.scale = font_scale
        self.horizon_top = 680 * font_scale
        self.action_top = self.horizon_top + 360 * font_scale
        self.content_height = self.action_top + 100 * font_scale
        self.missing_editor = missing_editor
        self.invalid_preview = invalid_preview
        self.offset = 0
        self.value = "36"
        self.caret = 2
        self.focused = False
        self.keyboard = False
        self.commands = []
        self.scroll_directions = []
        self.tapped_offsets = []
        self.preview_offset = None
        self.dismissals = 0

    def tree(self):
        tree = ET.Element("hierarchy", {"keyboard-visible": str(self.keyboard).lower()})
        viewport = ET.SubElement(tree, "node", {
            "package": PACKAGE, "resource-id": AREA,
            "bounds": "[0,163][320,616]", "scrollable": "true",
            "visible-to-user": "true",
        })
        if not self.missing_editor:
            self._row(viewport, self.horizon_top, 66 * self.scale, {
                "resource-id": HORIZON, "text": self.value,
                "class": "android.widget.EditText", "editable": "true",
                "focused": str(self.focused).lower(), "enabled": "true",
                "selection-start": str(self.caret), "selection-end": str(self.caret),
            })
        self._row(viewport, self.action_top, 56 * self.scale, {
            "text": PREVIEW, "class": "android.widget.Button", "clickable": "true",
            "enabled": str(bool(self.value) or self.invalid_preview).lower(),
        })
        return tree

    def _row(self, parent, top, height, attributes):
        clipped_top = max(0, top - self.offset)
        clipped_bottom = min(self.height, top + height - self.offset)
        if clipped_top < clipped_bottom:
            ET.SubElement(parent, "node", {
                "package": PACKAGE, "visible-to-user": "true", **attributes,
                "bounds": f"[20,{163 + int(clipped_top)}][300,{163 + int(clipped_bottom)}]",
            })

    def scroll(self, _x1, y1, _x2, y2):
        self.scroll_directions.append("end" if y1 > y2 else "start")
        self.offset = max(0, min(self.content_height - self.height,
                                 self.offset + y1 - y2))

    def tap_resource(self, resource, area, direction="end"):
        target = reveal_resource_in_list(self.tree, self.scroll, resource,
                                        resource_id=area, direction=direction, for_tap=True)
        if target is None:
            raise AssertionError("Strategy editor list is absent")
        self.tapped_offsets.append(self.offset)
        self.focused = True
        self.keyboard = True

    def reveal(self, text, area, direction="end"):
        target = reveal_in_list(self.tree, self.scroll, text,
                                resource_id=area, direction=direction)
        if text == PREVIEW:
            self.preview_offset = self.offset
        return target

    def wait_for(self, predicate, message):
        for _ in range(6):
            result = predicate()
            if result is not None and result is not False:
                return result
        raise AssertionError(message)

    def command(self, *command):
        if not self.focused or not self.keyboard:
            raise AssertionError("Input arrived before observing the focused editor and IME")
        self.commands.append(command)
        if command == ("shell", "input", "keyevent", "KEYCODE_MOVE_END"):
            self.caret = len(self.value)
        elif command == ("shell", "input", "keyevent", "KEYCODE_DEL"):
            self.value = self.value[:self.caret - 1] + self.value[self.caret:]
            self.caret = max(0, self.caret - 1)
        elif command == ("shell", "input", "text", "48"):
            self.value = self.value[:self.caret] + "48" + self.value[self.caret:]
            self.caret += 2
        else:
            raise AssertionError("Unexpected strategy input command")

    def dismiss_keyboard(self):
        self.keyboard = False
        self.dismissals += 1


class StrategyEditorTraversalTests(unittest.TestCase):
    def assert_editor_reached_and_revisited(self, font_scale):
        probe = StrategyViewportProbe(font_scale)
        with patch.object(strategy, "rotate_focused_draft", return_value={"offline": True}) as rotation:
            result = strategy.exercise_strategy_editor(probe, font_scale)
        self.assertEqual(probe.value, "48")
        self.assertEqual(probe.commands, [
            ("shell", "input", "keyevent", "KEYCODE_MOVE_END"),
            ("shell", "input", "keyevent", "KEYCODE_DEL"),
            ("shell", "input", "keyevent", "KEYCODE_DEL"),
            ("shell", "input", "text", "48"),
        ])
        self.assertEqual(len(probe.tapped_offsets), 2)
        self.assertGreater(probe.tapped_offsets[0], 0)
        self.assertLessEqual(probe.tapped_offsets[1], probe.preview_offset)
        if font_scale == 2.0:
            self.assertLess(probe.tapped_offsets[1], probe.preview_offset)
        self.assertEqual(probe.dismissals, 2)
        self.assertTrue(result["empty_draft_blocks_preview"])
        suffix = "-font-200" if font_scale == 2.0 else ""
        rotation.assert_called_once_with(probe, "48", "business-strategy-draft-rotation" + suffix, portrait_only=True)

    def test_horizon_below_choices_is_reached_at_normal_font(self):
        self.assert_editor_reached_and_revisited(1.0)

    def test_horizon_below_choices_is_reached_at_large_font(self):
        self.assert_editor_reached_and_revisited(2.0)

    def test_absent_editor_still_fails_with_bounded_scrolls_before_input(self):
        probe = StrategyViewportProbe(2.0, missing_editor=True)
        with patch("builtins.print"), patch.object(strategy, "rotate_focused_draft") as rotation:
            with self.assertRaisesRegex(AssertionError, "List target not reachable: " + HORIZON):
                strategy.exercise_strategy_editor(probe, 2.0)
        self.assertEqual(len(probe.scroll_directions), 10)
        self.assertEqual(probe.commands, [])
        rotation.assert_not_called()

    def test_empty_draft_with_enabled_preview_still_fails(self):
        probe = StrategyViewportProbe(1.0, invalid_preview=True)
        with patch.object(strategy, "rotate_focused_draft") as rotation:
            with self.assertRaisesRegex(AssertionError, "Empty strategy horizon permits a server preview"):
                strategy.exercise_strategy_editor(probe, 1.0)
        self.assertEqual(probe.value, "")
        self.assertEqual(len(probe.tapped_offsets), 1)
        rotation.assert_not_called()


if __name__ == "__main__":
    unittest.main()
