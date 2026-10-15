"""A portfolio screenshot must use its own allowlisted list and bounded gestures."""
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from profile_scroll import PACKAGE, SCROLL_AXES, reveal_in_list


def frame(resource="portfolio-content", package=PACKAGE, show_target=False):
    tree = ET.Element("hierarchy")
    area = ET.SubElement(tree, "node", {"package": package, "resource-id": resource,
        "scrollable": "true", "bounds": "[20,180][300,600]"})
    if show_target:
        ET.SubElement(area, "node", {"package": package, "text": "Денежные средства",
            "bounds": "[30,280][250,320]"})
    return tree


class PortfolioScrollTests(unittest.TestCase):
    def test_portfolio_is_explicitly_vertical(self):
        self.assertEqual(SCROLL_AXES["portfolio-content"], "vertical")

    def test_reveals_allocation_inside_exact_portfolio_list(self):
        trees = iter([frame(), frame(show_target=True)])
        gestures = []
        target = reveal_in_list(lambda: next(trees), lambda *v: gestures.append(v),
            "Денежные средства", resource_id="portfolio-content")
        self.assertIsNotNone(target)
        self.assertEqual(len(gestures), 1)
        x1, y1, x2, y2 = gestures[0]
        self.assertEqual(x1, x2)
        self.assertTrue(180 < y2 < y1 < 600)

    def test_does_not_scroll_profile_instead(self):
        gestures = []
        result = reveal_in_list(lambda: frame(resource="profile-content"),
            lambda *v: gestures.append(v), "Денежные средства", resource_id="portfolio-content")
        self.assertIsNone(result)
        self.assertFalse(gestures)

    def test_foreign_package_not_touched(self):
        gestures = []
        result = reveal_in_list(lambda: frame(package="other.app"),
            lambda *v: gestures.append(v), "Денежные средства", resource_id="portfolio-content")
        self.assertIsNone(result)
        self.assertFalse(gestures)

    def test_unknown_list_remains_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown_scroll_list"):
            reveal_in_list(lambda: frame(), lambda *v: None, "anything", resource_id="arbitrary")

    def test_unreachable_target_still_fails_at_bound(self):
        gestures = []
        with self.assertRaisesRegex(AssertionError, "not reachable"):
            reveal_in_list(lambda: frame(), lambda *v: gestures.append(v),
                "Денежные средства", resource_id="portfolio-content", max_swipes=2)
        self.assertEqual(len(gestures), 2)


if __name__ == "__main__":
    unittest.main()
