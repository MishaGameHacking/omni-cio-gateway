"""Run the saved-job probe through bounded scrolling of clipped list frames."""
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import business_ui_probe as business
from profile_scroll import reveal_in_list


STATUS = "Исход требует сверки"
AREA = "workspace-content"
RECOVERY = "recover-request-synthetic-request"


class SavedJobViewportProbe:
    """Plans puts the job below recovery; Assistant puts it above recovery.

    The action leaves the recovery viewport selected. Only visible clipped
    nodes enter each fresh frame; the real reveal helper must scroll to them.
    These offline frames are a traversal regression, not device evidence.
    """

    def __init__(self, route, font_scale, *, missing=None):
        self.height = 453
        self.content_height = 2_000 * font_scale
        self.recovery_offset = (500 if route == "plans" else 1_200) * font_scale
        self.status_top = (1_100 if route == "plans" else 600) * font_scale
        self.font_scale = font_scale
        self.missing = missing
        self.offset = 0
        self.recovered = False
        self.actions = []
        self.observed_labels = []
        self.scroll_directions = []

    def tap(self, text, area):
        if (text, area) != ("Сохранённые задания · 1", AREA):
            raise AssertionError("Unexpected saved-job action")
        self.actions.append(text)

    def tap_resource(self, resource, area):
        if (resource, area) != (RECOVERY, AREA) or self.recovered:
            raise AssertionError("Unexpected or repeated recovery")
        self.actions.append(resource)
        self.recovered = True
        self.offset = self.recovery_offset

    def tree(self):
        tree = ET.Element("hierarchy")
        viewport = ET.SubElement(tree, "node", {
            "package": "ru.omnicio.app.debug", "resource-id": AREA,
            "bounds": "[0,163][320,616]", "scrollable": "true",
            "visible-to-user": "true",
        })
        if not self.recovered:
            return tree
        rows = ((STATUS, 0, 48), (business.UNCERTAIN, 64, 220))
        for label, start, end in rows:
            if label == self.missing:
                continue
            top = max(0, self.status_top + start * self.font_scale - self.offset)
            bottom = min(self.height, self.status_top + end * self.font_scale - self.offset)
            if top < bottom:
                ET.SubElement(viewport, "node", {
                    "package": "ru.omnicio.app.debug", "text": label,
                    "bounds": f"[20,{163 + int(top)}][300,{163 + int(bottom)}]",
                    "visible-to-user": "true",
                })
        return tree

    def scroll(self, _x1, y1, _x2, y2):
        self.scroll_directions.append("end" if y1 > y2 else "start")
        self.offset = max(0, min(self.content_height - self.height,
                                 self.offset + y1 - y2))

    def reveal(self, text, area, direction="end"):
        target = reveal_in_list(self.tree, self.scroll, text,
                                resource_id=area, direction=direction)
        self.observed_labels.append(text)
        return target


class SavedJobRecoveryProbeTests(unittest.TestCase):
    def assert_recovered(self, route):
        for scale in (1.0, 2.0):
            with self.subTest(route=route, font_scale=scale):
                probe = SavedJobViewportProbe(route, scale)
                case = business._BusinessCase(probe, None, route, "job", scale)
                case.job()
                self.assertEqual(probe.actions, ["Сохранённые задания · 1", RECOVERY])
                self.assertEqual(probe.observed_labels, [STATUS, business.UNCERTAIN])
                self.assertTrue(probe.scroll_directions)
                self.assertEqual(case.checks,
                                 ["saved-request-recovered", "uncertain-not-repeated"])

    def test_plans_recovered_job_is_below_the_recovery_viewport(self):
        self.assert_recovered("plans")

    def test_assistant_recovered_job_is_above_the_recovery_viewport(self):
        self.assert_recovered("assistant")

    def test_missing_status_fails_with_bounded_scrolls_and_no_recovery_retry(self):
        probe = SavedJobViewportProbe("plans", 1.0, missing=STATUS)
        case = business._BusinessCase(probe, None, "plans", "job", 1.0)
        with self.assertRaisesRegex(AssertionError, "List target not reachable: " + STATUS):
            case.job()
        self.assertLessEqual(len(probe.scroll_directions), 10)
        self.assertEqual(probe.actions, ["Сохранённые задания · 1", RECOVERY])
        self.assertEqual(case.checks, [])

    def test_status_without_exact_uncertainty_detail_still_fails(self):
        probe = SavedJobViewportProbe("assistant", 1.0, missing=business.UNCERTAIN)
        case = business._BusinessCase(probe, None, "assistant", "job", 1.0)
        with self.assertRaisesRegex(AssertionError, "List target not reachable: " + business.UNCERTAIN):
            case.job()
        self.assertEqual(probe.observed_labels, [STATUS])
        self.assertEqual(probe.actions, ["Сохранённые задания · 1", RECOVERY])
        self.assertEqual(case.checks, [])


if __name__ == "__main__":
    unittest.main()
