"""Native-value parser guards, never synthetic evidence of an emulator pass."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from profile_ui_probe import ProfileProbe

SPEC = importlib.util.spec_from_file_location("analysis_ui_probe", Path(__file__).resolve().parents[1] / "analysis_ui_probe.py")
analysis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analysis)


class AnalysisValueEvidenceTests(unittest.TestCase):
    def test_native_money_retains_amount_unit_and_visible_app_identity(self):
        for amount in ("1000", "1 000", "1\u00a0000", "1\u202f000"):
            node = ET.Element("node", {"package": "ru.omnicio.app.debug", "text": "Оценка: " + amount + " RUB"})
            self.assertTrue(analysis.observed_money_label(node, "1000"))
        for text in ("Оценка: 1 100 RUB", "Оценка: 1 000 USD", "Оценка: 1 000 RUB (пример)", "1000", "Оценка: 1.000 RUB"):
            node = ET.Element("node", {"package": "ru.omnicio.app.debug", "text": text})
            self.assertFalse(analysis.observed_money_label(node, "1000"))
        node = ET.Element("node", {"package": "ru.omnicio.app.debug", "text": "Оценка: 1 000 RUB", "visible-to-user": "false"})
        self.assertFalse(analysis.observed_money_label(node, "1000"))
        node.attrib.update({"visible-to-user": "true", "package": "another.app"})
        self.assertFalse(analysis.observed_money_label(node, "1000"))


class AnalysisViewportProbe(ProfileProbe):
    """Logical content coordinates; offscreen labels are absent, as in LazyColumn."""
    def __init__(self, height, *, missing=False, foreign=False, enabled=False):
        super().__init__(None)
        self.height, self.missing, self.foreign, self.enabled = height, missing, foreign, enabled
        self.offset = self.scrolls = self.run_checks = 0

    def tree(self):
        top, bottom = 357, 357 + self.height
        tree = ET.Element("hierarchy")
        area = ET.SubElement(tree, "node", {"package": "ru.omnicio.app.debug", "resource-id": "workspace-content",
            "bounds": f"[0,{top}][320,{bottom}]", "scrollable": "true", "visible-to-user": "true"})
        labels = [(0, "Подтверждённых запусков ещё нет."),
                  (2700, "Сохранённых проверок пока нет."),
                  (3000, "Для сравнения нужны два сохранённых вывода."), (3350, analysis.RUN)]
        for position, label in labels:
            history = position == 2700
            y = top + position - self.offset
            if self.missing and history or y >= bottom or y + 120 <= top:
                continue
            ET.SubElement(area, "node", {"package": "another.app" if history and self.foreign else "ru.omnicio.app.debug",
                "text": label, "bounds": f"[20,{max(top, y)}][300,{min(bottom, y + 120)}]", "visible-to-user": "true",
                "class": "android.widget.Button" if label == analysis.RUN else "android.widget.TextView",
                "enabled": str(self.enabled if label == analysis.RUN else True).lower()})
        return tree

    def _semantic_scroll_callback(self, area, direction):
        if (area, direction) != ("workspace-content", "end"):
            raise AssertionError("Unexpected analysis scroll target")
        def scroll(*_coordinates):
            self.scrolls += 1
            self.offset += self.height - 40
        return scroll

    def wait_for(self, read, message):
        self.run_checks += 1
        result = read()
        if result is None:
            raise AssertionError(message)
        return result


class AnalysisEmptyTraversalTests(unittest.TestCase):
    @patch("profile_scroll.time.sleep")
    def test_default_budget_stops_before_the_history_in_the_observed_viewport(self, _sleep):
        probe = AnalysisViewportProbe(259)
        probe.reveal("Подтверждённых запусков ещё нет.", "workspace-content")
        with self.assertRaisesRegex(AssertionError, "List target not reachable"):
            probe.reveal("Сохранённых проверок пока нет.", "workspace-content")
        self.assertEqual((probe.scrolls, probe.run_checks), (10, 0))

    @patch("profile_scroll.time.sleep")
    def test_empty_timeline_reaches_history_comparison_and_disabled_native_action(self, _sleep):
        for height in (259, 450):
            with self.subTest(height=height):
                probe = AnalysisViewportProbe(height)
                result = analysis.exercise_analysis(probe, "empty", lambda: self.fail("Unexpected request observation"))
                self.assertEqual(result, ["no-invented-run-or-comparison", "unavailable-run-disabled"])
                self.assertEqual(probe.run_checks, 1)
                if height == 259:
                    self.assertGreater(probe.scrolls, 10)

    @patch("profile_scroll.time.sleep")
    def test_absent_or_foreign_history_cannot_pass_the_empty_scenario(self, _sleep):
        for changes in ({"missing": True}, {"foreign": True}):
            with self.subTest(changes=changes):
                probe = AnalysisViewportProbe(259, **changes)
                with self.assertRaisesRegex(AssertionError, "List target not reachable"):
                    analysis.exercise_analysis(probe, "empty", None)
                self.assertEqual((probe.scrolls, probe.run_checks), (20, 0))

    @patch("profile_scroll.time.sleep")
    def test_long_timeline_still_rejects_an_enabled_paid_action(self, _sleep):
        probe = AnalysisViewportProbe(259, enabled=True)
        with self.assertRaisesRegex(AssertionError, "Unavailable analysis exposes an enabled paid-run action"):
            analysis.exercise_analysis(probe, "empty", None)
        self.assertEqual(probe.run_checks, 1)


if __name__ == "__main__":
    unittest.main()
