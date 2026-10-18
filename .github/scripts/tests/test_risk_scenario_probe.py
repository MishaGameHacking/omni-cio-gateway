"""Hostile frame guards; the actual scenario flow runs separately on Android."""
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from risk_scenario_probe import PACKAGE, scenario_record_labels


def frame(record="A", package=PACKAGE, visible="true"):
    root = ET.Element("hierarchy")
    card = ET.SubElement(root, "node", {"resource-id": "scenario-result-" + record,
                                     "package": package, "visible-to-user": visible})
    ET.SubElement(card, "node", {"package": package, "visible-to-user": visible,
                                "text": "Изменение: −10\u00a0000 RUB"})
    return root


class RiskScenarioRecordTests(unittest.TestCase):
    def test_actual_values_are_bound_to_the_specific_visible_app_record(self):
        self.assertIn("Изменение:-10000RUB", scenario_record_labels(frame(), "A"))
        for tree in (frame("B"), frame(package="other.app"), frame(visible="false")):
            self.assertEqual(set(), scenario_record_labels(tree, "A"))

    def test_ambiguous_record_is_rejected_and_foreign_child_cannot_supply_a_value(self):
        root = frame()
        root.append(ET.fromstring(ET.tostring(root[0])))
        with self.assertRaises(AssertionError):
            scenario_record_labels(root, "A")
        root = frame()
        root[0][0].set("package", "other.app")
        self.assertNotIn("Изменение:-10000RUB", scenario_record_labels(root, "A"))


if __name__ == "__main__":
    unittest.main()
