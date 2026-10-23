"""Run scenario entry and bounded reveals across simulated native windows.

The real handler runs through the empty-input guard and first editor reveal.
The test stops before native text entry and rotation; those require Android.
"""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import risk_scenario_probe as risk
from profile_scroll import (PACKAGE, reveal_in_list, reveal_resource_in_list,
                            visible_resource)

TITLE = "Сравнение ваших сценариев"
OPEN = "Рассчитать свой сценарий"


class FirstEditorReached(Exception):
    """End this transition-only exercise at the first native input boundary."""


class RiskDialogViewportProbe:
    def __init__(self, scale=1.0, *, qualified=False, defect=None):
        self.scale, self.qualified, self.defect = scale, qualified, defect
        self.window, self.offset, self.pending, self.dialog_reads = 156, 0, None, 0
        self.dialog = False
        self.actions, self.scrolls, self.readiness = [], [], []
        self.wrong_window_scrolls = 0

    @property
    def height(self):
        return 453 if self.dialog else 245

    def open_dialog(self):
        self.dialog, self.pending, self.offset = True, None, 0
        self.window = 156 if self.defect == "same-window" else 157

    def tree(self):
        if self.pending is not None:
            if self.pending:
                self.pending -= 1
            else:
                self.open_dialog()
        tree = ET.Element("hierarchy", {"active-window-id": str(self.window),
                                       "display-width": "320", "display-height": "640"})
        if self.dialog:
            self.dialog_reads += 1
            if self.defect == "invalid-window":
                tree.set("active-window-id", "")
            # A new active root can arrive before Compose exposes its list.
            if self.dialog_reads <= 2:
                self.readiness.append("new-window-without-list")
                return tree
        resource = f"{PACKAGE}:id/{risk.AREA}" if self.qualified else risk.AREA
        viewport = ET.SubElement(tree, "node", {
            "package": PACKAGE, "resource-id": resource,
            "visible-to-user": "true", "enabled": "true", "scrollable": "true",
            "bounds": f"[0,163][320,{163 + self.height}]",
        })
        if not self.dialog:
            tabs = ET.SubElement(tree, "node", {
                "package": PACKAGE, "resource-id": "profile-tabs",
                "visible-to-user": "true", "enabled": "true", "scrollable": "true",
                "bounds": "[0,100][320,160]",
            })
            self.row(tabs, 0, 48, text="Концентрация", button=True)
            self.row(viewport, 100, 110, text=OPEN, button=True)
            return tree
        title_ready = self.dialog_reads > 4
        self.readiness.append("content-ready" if title_ready else "new-list-without-title")
        if title_ready and self.defect != "outside-title":
            self.row(viewport, 0, 40, text=TITLE)
        if self.defect == "outside-title":
            ET.SubElement(tree, "node", {
                "package": PACKAGE, "visible-to-user": "true",
                "bounds": "[0,0][320,100]", "text": TITLE,
            })
        self.row(viewport, 50, 160, text="Задайте 2–4 гипотезы.")
        self.row(viewport, 225, 40, text="Редактируемый сценарий")
        self.row(viewport, 450, 48, resource=risk.PERCENT)
        self.row(viewport, 650, 64, text=risk.COMPARE, button=True,
                 enabled=self.defect == "enabled-empty-comparison")
        return tree

    def row(self, parent, top, height, *, text="", resource="", button=False, enabled=True):
        scale = self.scale if self.dialog else 1.0
        upper = max(0, int(top * scale) - self.offset)
        lower = min(self.height, int((top + height) * scale) - self.offset)
        if upper >= lower:
            return
        origin = 100 if parent.get("resource-id") == "profile-tabs" else 163
        ET.SubElement(parent, "node", {
            "package": PACKAGE, "visible-to-user": "true", "enabled": str(enabled).lower(),
            "bounds": f"[20,{origin + upper}][300,{origin + lower}]", "text": text,
            "resource-id": resource, "clickable": str(button or bool(resource)).lower(),
            "class": "android.widget.Button" if button else "android.view.View",
        })

    def scroll(self, _x1, y1, _x2, y2):
        if self.pending is not None:
            # Python selected the old list, but the driver's fresh active root
            # has switched to a dialog whose list is not exposed yet.
            self.open_dialog()
            self.wrong_window_scrolls += 1
            raise ConnectionError("Expected one exact visible app list")
        if self.dialog and self.dialog_reads <= 4:
            raise AssertionError("Scrolled before dialog content became ready")
        self.scrolls.append((self.window, "end" if y1 > y2 else "start"))
        extent = int(800 * self.scale) if self.dialog else 800
        self.offset = max(0, min(extent - self.height, self.offset + y1 - y2))

    def reveal(self, text, area, direction="end"):
        target = reveal_in_list(self.tree, self.scroll, text, resource_id=area, direction=direction)
        if target is None:
            raise AssertionError("Scenario label is absent: " + text)
        return target

    def reveal_resource(self, resource, area, direction="end"):
        target = reveal_resource_in_list(self.tree, self.scroll, resource,
                                         resource_id=area, direction=direction)
        if target is None:
            raise AssertionError("Scenario editor is absent: " + resource)
        return target

    def tap(self, text, area, direction="end"):
        target = reveal_in_list(self.tree, self.scroll, text, resource_id=area,
                                direction=direction, for_tap=True)
        if target is None or target.get("enabled") == "false":
            raise AssertionError("Scenario action is unavailable: " + text)
        self.actions.append(text)
        if text == OPEN:
            self.pending = 2

    @staticmethod
    def wait_for(read, message):
        for _ in range(16):
            value = read()
            if value is not None and value is not False:
                return value
        raise AssertionError(message)


class RiskDialogTransitionTests(unittest.TestCase):
    def exercise_entry(self, probe):
        case = SimpleNamespace(probe=probe, font_scale=probe.scale,
                               observed=lambda: {"requests": 10, "scenario_comparisons": 2})

        def first_input(current_probe, value):
            self.assertIs(current_probe, probe)
            self.assertEqual(value, "-10")
            self.assertIsNotNone(visible_resource(probe.tree(), risk.PERCENT))
            raise FirstEditorReached()

        with patch.object(risk, "_enter_percent", side_effect=first_input):
            risk.exercise_scenario_comparison(case)

    def test_initial_handler_waits_for_its_window_before_revealing_lower_controls(self):
        for scale in (1.0, 2.0):
            for qualified in (False, True):
                with self.subTest(scale=scale, qualified=qualified):
                    probe = RiskDialogViewportProbe(scale, qualified=qualified)
                    with self.assertRaises(FirstEditorReached):
                        self.exercise_entry(probe)
                    self.assertEqual(probe.wrong_window_scrolls, 0)
                    self.assertEqual(probe.actions, ["Концентрация", OPEN])
                    self.assertIn("new-window-without-list", probe.readiness)
                    self.assertIn("new-list-without-title", probe.readiness)
                    self.assertIn("content-ready", probe.readiness)
                    self.assertTrue(probe.scrolls)
                    self.assertTrue(all(window == 157 for window, _ in probe.scrolls))

    def test_removing_wait_reproduces_old_frame_new_root_scroll_failure(self):
        for scale in (1.0, 2.0):
            with self.subTest(scale=scale):
                probe = RiskDialogViewportProbe(scale)
                with patch.object(risk, "wait_for_new_app_window", return_value=None), \
                        self.assertRaisesRegex(ConnectionError, "Expected one exact visible app list"):
                    self.exercise_entry(probe)
                self.assertEqual(probe.wrong_window_scrolls, 1)
                self.assertEqual(probe.actions, ["Концентрация", OPEN])

    def test_same_window_or_a_title_outside_the_dialog_list_cannot_allow_scroll(self):
        for defect in ("same-window", "outside-title"):
            with self.subTest(defect=defect):
                probe = RiskDialogViewportProbe(2.0, defect=defect)
                with self.assertRaisesRegex(AssertionError, "New app window did not become ready"):
                    self.exercise_entry(probe)
                self.assertEqual(probe.scrolls, [])
                self.assertEqual(probe.wrong_window_scrolls, 0)

    def test_missing_native_window_identity_fails_before_scrolling(self):
        probe = RiskDialogViewportProbe(2.0, defect="invalid-window")
        with self.assertRaisesRegex(AssertionError, "Missing public active-window identity"):
            self.exercise_entry(probe)
        self.assertEqual(probe.scrolls, [])

    def test_ready_window_does_not_replace_the_empty_input_guard(self):
        probe = RiskDialogViewportProbe(2.0, defect="enabled-empty-comparison")
        with self.assertRaisesRegex(AssertionError, "Empty scenario assumptions permit comparison"):
            self.exercise_entry(probe)
        self.assertEqual(probe.wrong_window_scrolls, 0)
        self.assertNotIn(risk.COMPARE, probe.actions)


if __name__ == "__main__":
    unittest.main()
