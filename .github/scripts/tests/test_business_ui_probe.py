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
from profile_scroll import reveal_in_list


def frame(route="risk", scenario="partial", *, requests="3", errors="0", comparisons="0", transport="synthetic", package="ru.omnicio.app.debug"):
    tree = ET.Element("hierarchy")
    ET.SubElement(tree, "node", {"package": package, "visible-to-user": "true", "content-desc":
        f"business-probe:{route}/{scenario};transport:{transport};requests:{requests};contract-errors:{errors};navigation:instrument:synthetic-stock::"
        f";message-posts:0;message-request-id:none;by-request-gets:0;recovered-request-id:none;scenario-compares:{comparisons}"})
    return tree


class RetryViewportProbe:
    """Retry is below its error text; tapping scrolls that text out of view."""

    def __init__(self):
        self.offset = 0
        self.requests = 1
        self.observed_labels = []
        self.tapped_labels = []

    def tree(self):
        tree = frame("assistant", "error", requests=str(self.requests))
        viewport = ET.SubElement(tree, "node", {"package": "ru.omnicio.app.debug",
            "resource-id": "workspace-content", "scrollable": "true", "bounds": "[0,0][320,200]"})
        for label, top, bottom in (("Не удалось обновить", 0, 40), (business.ERROR, 56, 136),
                                   ("Повторить", 160, 212), ("Following content", 240, 420)):
            top, bottom = max(0, top - self.offset), min(200, bottom - self.offset)
            if top < bottom:
                ET.SubElement(viewport, "node", {"package": "ru.omnicio.app.debug", "text": label,
                    "bounds": f"[0,{top}][320,{bottom}]"})
        return tree

    def scroll(self, _x1, y1, _x2, y2):
        self.offset = max(0, min(220, self.offset + (160 if y1 > y2 else -160)))

    def reveal(self, text, area, direction="end"):
        target = reveal_in_list(self.tree, self.scroll, text, resource_id=area, direction=direction)
        self.observed_labels.append((text, self.requests))
        return target

    def tap(self, text, area):
        self.offset = 160  # The retry action reaches the viewport's upper edge.
        self.reveal(text, area)
        self.tapped_labels.append(text)
        self.requests += 1

    @staticmethod
    def wait_for(condition, message):
        result = condition()
        if not result:
            raise AssertionError(message)
        return result


class BusinessUiProbeTests(unittest.TestCase):
    def test_retry_reveals_the_same_error_above_the_action_viewport(self):
        probe = RetryViewportProbe()
        case = business._BusinessCase(probe, None, "assistant", "error", 1.0)
        case.error()
        self.assertEqual(probe.requests, 2)
        self.assertEqual(probe.tapped_labels, ["Повторить"])
        self.assertEqual(probe.observed_labels, [
            ("Не удалось обновить", 1), (business.ERROR, 1), ("Повторить", 1), (business.ERROR, 2),
        ])
        self.assertEqual(case.checks, ["explicit-source-error", "retry-real-request"])

    def test_operation_checkbox_keeps_its_quantity_label_in_an_unmerged_child(self):
        quantity = " · 3 ед."
        control = ET.Element("node", {"package": "ru.omnicio.app.debug", "checkable": "true"})
        ET.SubElement(control, "node", text="18.10.2026" + quantity)
        self.assertTrue(business._matches_business_control(control, "", True, quantity))
        self.assertFalse(business._matches_business_control(control, "", True, " · 5 ед."))
        control.set("checkable", "false")
        self.assertFalse(business._matches_business_control(control, "", True, quantity))

    def test_supported_matrix_has_thirty_distinct_cases(self):
        self.assertEqual(len(business.CASES), 30)
        self.assertEqual(len(set(business.CASES)), 30)
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
        for tree in (frame(errors="1"), frame(requests="-2"), frame(errors="unknown"),
                     frame(comparisons="-1"), frame(comparisons="unknown"), frame(comparisons="4")):
            with self.assertRaises(AssertionError):
                business.business_marker(tree, "risk", "partial")
        unsupported = frame()
        with self.assertRaises(ValueError):
            business.business_marker(unsupported, "risk", "job")

    def test_only_the_visible_transport_can_report_comparison_requests(self):
        self.assertEqual(business.business_marker(frame(comparisons="1"), "risk", "partial")["scenario_comparisons"], 1)
        hidden = frame(comparisons="1")
        hidden[0].set("visible-to-user", "false")
        self.assertIsNone(business.business_marker(hidden, "risk", "partial"))


if __name__ == "__main__":
    unittest.main()
