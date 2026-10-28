"""Nested market tabs must enter the vertical viewport before horizontal traversal."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import portfolio_market_probe as market
from profile_scroll import PACKAGE, reveal_in_list, reveal_resource_in_list


AREA = "workspace-content"
TABS = "profile-tabs"


class SourceReadReached(Exception):
    """Stop after the actual entrypoint selects its tab and requests its source."""


class MarketViewportProbe:
    """Clipped parent/child frames; movements use the real bounded reveal helpers."""

    def __init__(self, scale, *, partial=False, missing=False):
        self.scale = scale
        self.height = 453
        self.tab_top = self.height - 20 if partial else 250 * scale
        self.tab_height = 52 * scale
        self.offset = 0
        self.horizontal = 0
        self.missing = missing
        self.movements = []
        self.taps = []

    def tree(self):
        tree = ET.Element("hierarchy", {"display-width": "320", "display-height": "640",
                                        "active-window-id": "1"})
        viewport = ET.SubElement(tree, "node", {"package": PACKAGE, "resource-id": AREA,
            "bounds": "[0,163][320,616]", "scrollable": "true", "visible-to-user": "true", "enabled": "true"})
        top, bottom = max(0, self.tab_top - self.offset), min(self.height, self.tab_top + self.tab_height - self.offset)
        if self.missing or top >= bottom:
            return tree
        bounds = f"[20,{163 + int(top)}][300,{163 + int(bottom)}]"
        rail = ET.SubElement(viewport, "node", {"package": PACKAGE, "resource-id": TABS,
            "bounds": bounds, "scrollable": "true", "visible-to-user": "true", "enabled": "true"})
        for index, label in enumerate(("Отрасли", "Классы", "География", "Сессии")):
            left = max(0, index * 140 * self.scale - self.horizontal)
            right = min(280, (index + 1) * 140 * self.scale - self.horizontal)
            if left < right:
                ET.SubElement(rail, "node", {"package": PACKAGE, "text": label,
                    "bounds": f"[{20 + int(left)},{163 + int(top)}][{20 + int(right)},{163 + int(bottom)}]",
                    "clickable": "true", "enabled": "true", "visible-to-user": "true"})
        return tree

    def scroll(self, x1, y1, x2, y2):
        if x1 == x2:
            self.movements.append((AREA, "end" if y1 > y2 else "start"))
            self.offset = max(0, min(2_000 * self.scale - self.height, self.offset + y1 - y2))
        else:
            self.movements.append((TABS, "end" if x1 > x2 else "start"))
            self.horizontal = max(0, min(560 * self.scale - 280, self.horizontal + x1 - x2))

    def reveal_resource(self, resource, area, direction="end", **options):
        return reveal_resource_in_list(self.tree, self.scroll, resource,
            resource_id=area, direction=direction, **options)

    def tap(self, text, area, direction="end"):
        target = reveal_in_list(self.tree, self.scroll, text,
            resource_id=area, direction=direction, for_tap=True)
        if target is None:
            raise AssertionError("Native action list is not visible: " + area)
        self.taps.append(text)

    @staticmethod
    def command(*_args):
        return "Etc/UTC"

    @staticmethod
    def find(_text):
        return None

    def finish_calendar(self):
        self.offset = self.tab_top + 1_200 * self.scale
        self.horizontal = 560 * self.scale - 280


class MarketCase:
    def __init__(self, probe):
        self.probe = probe
        self.calls = []

    def call(self, path, query):
        self.calls.append((path, query))
        raise SourceReadReached()


class MarketTraversalTests(unittest.TestCase):
    def test_initial_sessions_reveals_absent_or_clipped_parent_toward_end(self):
        for scale in (1.0, 2.0):
            for partial in (False, True):
                with self.subTest(scale=scale, partial=partial):
                    probe = MarketViewportProbe(scale, partial=partial)
                    case = MarketCase(probe)
                    with self.assertRaises(SourceReadReached):
                        market._calendar(case)
                    self.assertEqual(probe.taps, ["Сессии"])
                    self.assertEqual(case.calls, [("/workspace/markets/calendar", {})])
                    vertical = [direction for area, direction in probe.movements if area == AREA]
                    self.assertEqual(set(vertical), {"end"} if partial or scale == 2 else set())

    def test_geography_returns_from_calendar_footer_before_horizontal_selection(self):
        for scale in (1.0, 2.0):
            with self.subTest(scale=scale):
                probe = MarketViewportProbe(scale)
                case = MarketCase(probe)
                with patch.object(market, "_calendar", side_effect=lambda _case: probe.finish_calendar()):
                    with self.assertRaises(SourceReadReached):
                        market.exercise_markets(case)
                self.assertEqual(probe.taps, ["География"])
                self.assertEqual(case.calls, [("/workspace", {"currency": "RUB"})])
                self.assertEqual(probe.movements[0], (AREA, "start"))
                self.assertTrue(all(direction == "start" for _, direction in probe.movements))

    def test_missing_parent_still_fails_bounded_without_tapping_or_source_request(self):
        probe = MarketViewportProbe(1.0, missing=True)
        case = MarketCase(probe)
        with self.assertRaises(AssertionError) as failure:
            market._calendar(case)
        self.assertIn(TABS, str(failure.exception))
        self.assertLessEqual(len(probe.movements), 10)
        self.assertEqual(probe.taps, [])
        self.assertEqual(case.calls, [])


if __name__ == "__main__":
    unittest.main()
