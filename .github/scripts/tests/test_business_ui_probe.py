"""Offline fixture-identity guards; device observations are produced only by CI."""
import importlib.util
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
SPEC = importlib.util.spec_from_file_location("business_ui_probe", Path(__file__).resolve().parents[1] / "business_ui_probe.py")
business = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(business)


def frame(route="risk", scenario="partial", *, requests="3", errors="0", transport="synthetic", package="ru.omnicio.app.debug"):
    tree = ET.Element("hierarchy")
    ET.SubElement(tree, "node", {"package": package, "visible-to-user": "true", "content-desc":
        f"business-probe:{route}/{scenario};transport:{transport};requests:{requests};contract-errors:{errors};navigation:instrument:synthetic-stock::"
        ";message-posts:0;message-request-id:none;by-request-gets:0;recovered-request-id:none"})
    return tree


class BusinessUiProbeTests(unittest.TestCase):
    def test_operation_checkbox_keeps_its_quantity_label_in_an_unmerged_child(self):
        quantity = " · 3 ед."
        control = ET.Element("node", {"package": "ru.omnicio.app.debug", "checkable": "true"})
        ET.SubElement(control, "node", text="18.10.2026" + quantity)
        self.assertTrue(business._matches_business_control(control, "", True, quantity))
        self.assertFalse(business._matches_business_control(control, "", True, " · 5 ед."))
        control.set("checkable", "false")
        self.assertFalse(business._matches_business_control(control, "", True, quantity))

    def test_supported_matrix_has_twenty_six_distinct_cases(self):
        self.assertEqual(len(business.CASES), 26)
        self.assertEqual(len(set(business.CASES)), 26)
        self.assertEqual({scenario for route, scenario in business.CASES if route == "analysis"}, {"ready", "empty", "partial", "error"})
        self.assertEqual({route for route, state in business.CASES if state == "job"}, {"assistant", "plans"})

    def test_exact_identity_and_real_request_count_are_required(self):
        actual = business.business_marker(frame(), "risk", "partial")
        self.assertEqual(actual["requests"], 3)
        self.assertEqual(actual["navigation"], "instrument:synthetic-stock::")
        for tree in (frame(scenario="ready"), frame(route="plans"), frame(requests="0"),
                     frame(transport="live"), frame(package="another.app")):
            self.assertIsNone(business.business_marker(tree, "risk", "partial"))

    def test_contract_rejections_and_invalid_counters_fail_closed(self):
        for tree in (frame(errors="1"), frame(requests="-2"), frame(errors="unknown")):
            with self.assertRaises(AssertionError):
                business.business_marker(tree, "risk", "partial")
        unsupported = frame()
        with self.assertRaises(ValueError):
            business.business_marker(unsupported, "risk", "job")


if __name__ == "__main__":
    unittest.main()
