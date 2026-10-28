"""Run the saved-job probe through bounded scrolling of clipped list frames."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import business_ui_probe as business
from profile_scroll import reveal_in_list
from profile_ui_probe import ProfileProbe


STATUS = "Исход требует сверки"
AREA = "workspace-content"
RECOVERY = "recover-request-synthetic-request"
SAVED = "Сохранённые задания · 1"


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

    def tap(self, text, area, *, max_swipes=10):
        if (text, area, max_swipes) != ("Сохранённые задания · 1", AREA, 20):
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


class RecoveryControlReached(Exception):
    """The existing recovery tests and Android CI cover the subsequent GET."""


class SavedJobHeaderProbe(ProfileProbe):
    """A long answer precedes the saved-job card in the bounded chat history."""
    def __init__(self, height, *, qualified=False, missing=False, enabled=True):
        super().__init__(None)
        self.height, self.qualified = height, qualified
        self.missing, self.enabled = missing, enabled
        self.offset = self.scrolls = self.taps = 0
        self.opened = False

    def tree(self):
        tree = ET.Element("hierarchy", {"active-window-id": "8",
            "display-width": "320", "display-height": "640"})
        resource = f"ru.omnicio.app.debug:id/{AREA}" if self.qualified else AREA
        attributes = {"package": "ru.omnicio.app.debug", "visible-to-user": "true",
                      "enabled": "true", "clickable": "false", "class": "android.view.View"}
        viewport = ET.SubElement(tree, "node", attributes | {"resource-id": resource,
            "scrollable": "true", "bounds": f"[56,141][320,{141 + self.height}]"})
        if not self.missing:
            top = 141 + 2_600 - self.offset
            visible = str(top < 141 + self.height and top + 120 > 141).lower()
            owner = ET.SubElement(viewport, "node", attributes | {"clickable": "true",
                "enabled": str(self.enabled).lower(), "visible-to-user": visible,
                "bounds": f"[76,{top}][300,{top + 120}]"})
            ET.SubElement(owner, "node", attributes | {"text": SAVED,
                "visible-to-user": visible, "bounds": f"[84,{top + 8}][292,{top + 112}]"})
        return tree

    def _semantic_scroll_callback(self, area, direction):
        if (area, direction) != (AREA, "end"):
            raise AssertionError("Unexpected saved-job traversal")
        def scroll(*_coordinates):
            self.scrolls += 1
            self.offset = min(3_400, self.offset + self.height - 40)
        return scroll

    def command(self, *args, **_kwargs):
        if args[:3] != ("shell", "input", "tap"):
            raise AssertionError("Unexpected device action")
        x, y = map(int, args[3:])
        top = 141 + 2_600 - self.offset
        if not self.enabled or not 76 <= x < 300 or not max(141, top) <= y < min(141 + self.height, top + 120):
            raise AssertionError("Tap missed the visible native saved-job owner")
        self.taps += 1
        self.opened = True
        return ""

    def tap_resource(self, resource, area):
        if (resource, area) != (RECOVERY, AREA) or not self.opened:
            raise AssertionError("Recovery attempted before opening the saved-job card")
        raise RecoveryControlReached


class SavedJobHeaderTraversalTests(unittest.TestCase):
    @staticmethod
    def exercise(probe):
        case = business._BusinessCase(probe, None, "assistant", "job", 2.0)
        with patch("time.sleep"):
            case.job()

    def test_long_history_reaches_one_native_saved_job_header_at_both_viewport_sizes(self):
        for height in (453, 237):
            for qualified in (False, True):
                with self.subTest(height=height, qualified=qualified):
                    probe = SavedJobHeaderProbe(height, qualified=qualified)
                    with self.assertRaises(RecoveryControlReached):
                        self.exercise(probe)
                    self.assertEqual(probe.taps, 1)
                    self.assertLessEqual(probe.scrolls, 20)
                    if height == 237:
                        self.assertGreater(probe.scrolls, 10)

    def test_default_tap_budget_remains_ten_and_reproduces_the_short_viewport_failure(self):
        probe = SavedJobHeaderProbe(237)
        with patch("time.sleep"), self.assertRaisesRegex(AssertionError, "List target not reachable"):
            probe.tap(SAVED, AREA)
        self.assertEqual((probe.scrolls, probe.taps), (10, 0))

    def test_missing_header_still_fails_after_twenty_pages_without_a_tap(self):
        probe = SavedJobHeaderProbe(237, missing=True)
        with self.assertRaisesRegex(AssertionError, "List target not reachable"):
            self.exercise(probe)
        self.assertEqual((probe.scrolls, probe.taps), (20, 0))

    def test_disabled_header_cannot_be_opened_after_it_is_revealed(self):
        probe = SavedJobHeaderProbe(237, enabled=False)
        with self.assertRaisesRegex(AssertionError, "Native action geometry or enabled state did not settle"):
            self.exercise(probe)
        self.assertEqual(probe.taps, 0)


if __name__ == "__main__":
    unittest.main()
