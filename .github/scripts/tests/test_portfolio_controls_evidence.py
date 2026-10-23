"""Adversarial calendar and native control readers, not Android runtime proof."""
from datetime import date
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from portfolio_chart_probe import month_before, range_description, quote_interval_target
from portfolio_preferences_probe import selected_control
from portfolio_ui_probe import PortfolioCase

PACKAGE = "ru.omnicio.app.debug"


class PortfolioControlsEvidenceTests(unittest.TestCase):
    def test_financial_value_must_belong_to_the_exact_visible_source_record(self):
        tree = ET.Element("hierarchy")
        common = {"package": PACKAGE, "visible-to-user": "true", "bounds": "[20,100][300,180]"}
        first = ET.SubElement(tree, "node", {**common, "resource-id": "dossier-conflict-observation-0"})
        correct = ET.SubElement(first, "node", {**common, "text": "12.5"})
        second = ET.SubElement(tree, "node", {**common, "resource-id": "dossier-conflict-observation-1"})
        ET.SubElement(second, "node", {**common, "text": "8.25"})

        class Reader:
            def read(self):
                return tree

            def scroll_list(self, area, direction):
                return False

        reader = Reader()
        case = object.__new__(PortfolioCase)
        case.probe = SimpleNamespace(tree=reader.read, read_tree=reader.read, reveal_resource=lambda *args, **kwargs: first)
        self.assertIs(correct, case.record_text("dossier-conflict-observation-0", "12.5"))
        with self.assertRaises(AssertionError):
            case.record_text("dossier-conflict-observation-0", "8.25")
        correct.set("visible-to-user", "false")
        with self.assertRaises(AssertionError):
            case.record_text("dossier-conflict-observation-0", "12.5")

    def test_quote_period_preserves_calendar_month_rules(self):
        for current, expected in ((date(2026, 3, 31), date(2026, 2, 28)),
                                  (date(2024, 3, 31), date(2024, 2, 29)),
                                  (date(2026, 1, 1), date(2025, 12, 1)),
                                  (date(2026, 10, 17), date(2026, 9, 17))):
            self.assertEqual(expected, month_before(current))

    def test_range_requires_one_exact_native_date(self):
        node = ET.Element("node", {"content-desc": "Начало периода: 2026-10-03"})
        self.assertEqual(date(2026, 10, 3), range_description(node, "Начало периода: "))
        for description in ("Начало периода: вчера", "Начало периода: 2026-13-03",
                            "Начало периода: 2026-10-03\nНачало периода: 2026-10-04",
                            "Конец периода: 2026-10-03"):
            node.set("content-desc", description)
            with self.assertRaises((AssertionError, ValueError)):
                range_description(node, "Начало периода: ")

    def test_quote_interval_does_not_tap_same_label_in_period_controls(self):
        root = ET.Element("hierarchy")
        common = {"package": PACKAGE, "visible-to-user": "true"}
        ET.SubElement(root, "node", {**common, "text": "Месяц", "clickable": "true",
                                    "bounds": "[10,100][150,160]", "selected": "true"})
        row = ET.SubElement(root, "node", {**common, "resource-id": "quotes-intervals",
                                          "bounds": "[20,200][320,260]"})
        button = ET.SubElement(row, "node", {**common, "clickable": "true", "selected": "false",
                                             "bounds": "[270,200][390,260]"})
        ET.SubElement(button, "node", {**common, "text": "Месяц"})
        target = quote_interval_target(root, "Месяц")
        self.assertEqual("[270,200][320,260]", target.get("bounds"))
        self.assertEqual("false", target.get("selected"))
        button.set("bounds", "[300,200][420,260]")
        self.assertIsNone(quote_interval_target(root, "Месяц"))

    def test_quote_interval_requires_one_visible_owned_rail(self):
        root = ET.Element("hierarchy")
        row = ET.SubElement(root, "node", {"package": PACKAGE, "visible-to-user": "true",
                                          "resource-id": PACKAGE + ":id/quotes-intervals",
                                          "bounds": "[20,200][320,260]"})
        ET.SubElement(row, "node", {"package": PACKAGE, "visible-to-user": "true",
                                   "clickable": "true", "text": "Час", "bounds": "[20,200][120,260]"})
        self.assertIsNotNone(quote_interval_target(root, "Час"))
        duplicate = ET.SubElement(root, "node", dict(row.attrib))
        self.assertIsNone(quote_interval_target(root, "Час"))
        duplicate.set("visible-to-user", "false")
        self.assertIsNotNone(quote_interval_target(root, "Час"))
        row.set("package", "other.app")
        self.assertIsNone(quote_interval_target(root, "Час"))
        with self.assertRaises(ValueError):
            quote_interval_target(root, "Произвольный интервал")

    def test_visible_title_without_native_selection_cannot_prove_persistence(self):
        root = ET.Element("hierarchy")
        control = ET.SubElement(root, "node", {"package": PACKAGE, "visible-to-user": "true", "checked": "false", "checkable": "true"})
        ET.SubElement(control, "node", {"package": PACKAGE, "visible-to-user": "true", "text": "Яркое освещение"})
        self.assertIsNone(selected_control(root, "Яркое освещение", checked=True))
        self.assertIs(control, selected_control(root, "Яркое освещение", checked=False))
        control.set("checked", "true")
        self.assertIs(control, selected_control(root, "Яркое освещение", checked=True))
        self.assertIs(control, selected_control(root, "Яркое освещение"))
        for field, value in (("package", "other.app"), ("visible-to-user", "false")):
            before = control.get(field)
            control.set(field, value)
            self.assertIsNone(selected_control(root, "Яркое освещение", checked=True))
            control.set(field, before)


if __name__ == "__main__":
    unittest.main()
