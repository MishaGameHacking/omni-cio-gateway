"""Native-value parser guards, never synthetic evidence of an emulator pass."""
import importlib.util
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

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


if __name__ == "__main__":
    unittest.main()
