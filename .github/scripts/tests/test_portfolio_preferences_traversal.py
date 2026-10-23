"""The actual appearance caller must reach Cancel below its restored status anchor."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import portfolio_preferences_probe as preferences
from profile_scroll import PACKAGE, reveal_in_list


class AppearanceViewportProbe:
    """Only post-rotation traversal is modeled; preference setup is test scaffolding."""

    def __init__(self, scale, *, missing_cancel=False):
        self.scale = scale
        self.missing_cancel = missing_cancel
        self.prefs = dict(preferences.DEFAULT)
        self.after_rotation = False
        self.offset = 0
        self.movements = []
        self.cancels = 0

    def tree(self):
        tree = ET.Element("hierarchy", {"display-width": "320", "display-height": "640",
                                        "active-window-id": "1"})
        viewport = ET.SubElement(tree, "node", {"package": PACKAGE, "resource-id": preferences.AREA,
            "bounds": "[0,163][320,616]", "scrollable": "true", "visible-to-user": "true", "enabled": "true"})
        # The status is visible at the lower edge; Apply and Cancel follow it.
        rows = [(preferences.DIRTY, 373, 80), ("Применить", 473, 64), ("Отменить", 557, 64)]
        for label, start, height in rows:
            if self.missing_cancel and label == "Отменить":
                continue
            top = max(0, 373 + (start - 373) * self.scale - self.offset)
            bottom = min(453, 373 + (start - 373 + height) * self.scale - self.offset)
            if top < bottom:
                ET.SubElement(viewport, "node", {"package": PACKAGE, "text": label,
                    "bounds": f"[20,{163 + int(top)}][300,{163 + int(bottom)}]",
                    "clickable": "true", "enabled": "true", "visible-to-user": "true"})
        return tree

    def scroll(self, _x1, y1, _x2, y2):
        self.movements.append("end" if y1 > y2 else "start")
        self.offset = max(0, min(1_500, self.offset + y1 - y2))

    def tap(self, text, area, direction="end"):
        if text == "Отменить":
            if self.after_rotation:
                reveal_in_list(self.tree, self.scroll, text,
                    resource_id=area, direction=direction, for_tap=True)
            self.cancels += 1
            self.prefs = dict(preferences.APPLIED)
        elif text == "Применить":
            self.prefs = dict(preferences.APPLIED)

    @staticmethod
    def reveal(_text, _area, direction="end"):
        return ET.Element("node", enabled="true")

    @staticmethod
    def find(_text):
        return None

    @staticmethod
    def wait_for(condition, message):
        value = condition()
        if not value:
            raise AssertionError(message)
        return value


class AppearanceCase:
    def __init__(self, probe):
        self.probe = probe
        self.extra = {}

    def expect(self, condition, message):
        value = {"prefs": self.probe.prefs}
        if not condition(value):
            raise AssertionError(message)
        return value

    def launch(self):
        return {"prefs": dict(preferences.APPLIED)}

    @staticmethod
    def capture(_name):
        return None


def run_appearance(probe):
    # These unrelated phases already have device gates; inject the resulting
    # post-rotation viewport and exercise the real caller and reveal helper.
    def reset(_case):
        probe.prefs = dict(preferences.DEFAULT)

    def preview(_case):
        probe.prefs = dict(preferences.PREVIEW)

    def rotated(_case):
        probe.after_rotation = True

    with patch.object(preferences, "_reset", side_effect=reset), \
         patch.object(preferences, "_preview", side_effect=preview), \
         patch.object(preferences, "_rotate_preview", side_effect=rotated), \
         patch.object(preferences, "selected_control", return_value=True), \
         patch.object(preferences, "ready_spatial_metrics", return_value={"motion": "Off"}):
        return preferences.exercise_appearance(AppearanceCase(probe))


class AppearanceTraversalTests(unittest.TestCase):
    def test_cancel_after_rotation_reaches_action_below_visible_dirty_status(self):
        for scale in (1.0, 2.0):
            with self.subTest(scale=scale):
                probe = AppearanceViewportProbe(scale)
                checks = run_appearance(probe)
                self.assertIn("unsaved-preview-survives-rotation", checks)
                self.assertEqual(probe.cancels, 2)
                self.assertEqual(probe.prefs, preferences.DEFAULT)
                self.assertTrue(probe.movements)
                self.assertEqual(set(probe.movements), {"end"})

    def test_missing_cancel_still_fails_bounded_without_a_second_cancel(self):
        probe = AppearanceViewportProbe(1.0, missing_cancel=True)
        with self.assertRaisesRegex(AssertionError, "List target not reachable: Отменить"):
            run_appearance(probe)
        self.assertLessEqual(len(probe.movements), 10)
        self.assertEqual(probe.cancels, 1)
        self.assertEqual(probe.prefs, preferences.PREVIEW)


if __name__ == "__main__":
    unittest.main()
