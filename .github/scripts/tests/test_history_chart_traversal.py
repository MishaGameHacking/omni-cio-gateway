"""Exercise actual history-bar selection on clipped offline viewport frames."""
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import portfolio_chart_probe as chart
from profile_scroll import reveal_in_list, reveal_resource_in_list
from profile_ui_probe import node_bounds


class HistoryChartViewportProbe:
    """The native tooltip precedes the plot; the detail fold follows it.

    Only clipped visible nodes enter a frame. Scrolling and selection run
    through the real probe helpers; these frames do not claim device coverage.
    """

    def __init__(self, font_scale, origin="above", *, missing_chart=False,
                 wrong_selection=False):
        self.scale = font_scale
        self.height = 453
        self.chart_top = 800 * font_scale
        self.chart_height = 188
        self.content_height = self.chart_top + self.chart_height + 800 * font_scale
        self.offset = 0 if origin == "above" else self.chart_top + self.chart_height + 200 * font_scale
        self.missing_chart = missing_chart
        self.wrong_selection = wrong_selection
        self.history_start = date(2026, 10, 1)
        self.selected = None
        self.commands = []
        self.scroll_directions = []
        self.observed_labels = []
        self.tap_bounds = None

    def tree(self):
        tree = ET.Element("hierarchy")
        viewport = ET.SubElement(tree, "node", {
            "package": chart.PACKAGE, "resource-id": chart.AREA,
            "bounds": "[0,163][320,616]", "scrollable": "true",
            "visible-to-user": "true",
        })
        if not self.missing_chart:
            self._row(viewport, self.chart_top, self.chart_height,
                      {"resource-id": "history-bars", "enabled": "true"})
        if self.selected is not None:
            selected_day = self.history_start + timedelta(days=self.selected)
            # Compose exposes the value inside the tooltip's semantic parent.
            tooltip = self._row(viewport, self.chart_top - 140 * self.scale, 126 * self.scale,
                      {"content-desc": f"Выбранный интервал: {selected_day} — {selected_day}"})
            if tooltip is not None:
                self._row(tooltip, self.chart_top - 70 * self.scale, 56 * self.scale,
                          {"text": chart.SELECTED_HISTORY_VALUE})
        return tree

    def _row(self, parent, top, height, attributes):
        clipped_top = max(0, top - self.offset)
        clipped_bottom = min(self.height, top + height - self.offset)
        if clipped_top < clipped_bottom:
            return ET.SubElement(parent, "node", {
                "package": chart.PACKAGE, "visible-to-user": "true", **attributes,
                "bounds": f"[20,{163 + int(clipped_top)}][300,{163 + int(clipped_bottom)}]",
            })

    def scroll(self, _x1, y1, _x2, y2):
        self.scroll_directions.append("end" if y1 > y2 else "start")
        self.offset = max(0, min(self.content_height - self.height,
                                 self.offset + y1 - y2))

    def resource_tap_target(self, resource, area, direction="end"):
        target = reveal_resource_in_list(self.tree, self.scroll, resource,
                                        resource_id=area, direction=direction, for_tap=True)
        if target is None:
            raise AssertionError("History chart list is absent")
        self.tap_bounds = node_bounds(target)
        return target

    def reveal(self, text, area, direction="end"):
        target = reveal_in_list(self.tree, self.scroll, text,
                                resource_id=area, direction=direction)
        self.observed_labels.append(text)
        return target

    def command(self, *command):
        if command[:3] != ("shell", "input", "tap") or self.tap_bounds is None:
            raise AssertionError("Unexpected command or tap before a visible chart")
        self.commands.append(command)
        left, top, right, bottom = self.tap_bounds
        x, y = map(int, command[3:])
        if not left <= x < right or not top <= y < bottom:
            raise AssertionError("Chart tap is outside its observed viewport")
        self.selected = int((x - left) * 14 / (right - left))
        if self.wrong_selection:
            self.selected += 1


class HistoryChartTraversalTests(unittest.TestCase):
    def select_and_assert(self, scale, origin, **options):
        probe = HistoryChartViewportProbe(scale, origin)
        case = SimpleNamespace(probe=probe, history_start=probe.history_start)
        chart._select_history_bar(case, 10, chart.SELECTED_HISTORY_VALUE, **options)
        left, top, right, bottom = probe.tap_bounds
        self.assertEqual(probe.commands, [("shell", "input", "tap",
            str(left + int((right - left) * 10.5 / 14)), str((top + bottom) // 2))])
        selected_day = probe.history_start + timedelta(days=10)
        self.assertEqual(probe.observed_labels, [
            f"Выбранный интервал: {selected_day} — {selected_day}", chart.SELECTED_HISTORY_VALUE,
        ])
        self.assertEqual(probe.selected, 10)
        self.assertTrue(probe.scroll_directions)

    def test_chart_below_tooltip_is_reached_at_both_font_scales(self):
        for scale in (1.0, 2.0):
            with self.subTest(font_scale=scale):
                self.select_and_assert(scale, "above")

    def test_chart_above_details_is_revisited_at_both_font_scales(self):
        for scale in (1.0, 2.0):
            with self.subTest(font_scale=scale):
                self.select_and_assert(scale, "below", direction="start")

    def test_missing_chart_fails_boundedly_before_any_tap(self):
        probe = HistoryChartViewportProbe(2.0, missing_chart=True)
        case = SimpleNamespace(probe=probe, history_start=probe.history_start)
        with self.assertRaisesRegex(AssertionError, "List target not reachable: history-bars"):
            chart._select_history_bar(case, 10, chart.SELECTED_HISTORY_VALUE)
        self.assertEqual(len(probe.scroll_directions), 10)
        self.assertEqual(probe.commands, [])

    def test_wrong_selected_day_fails_without_repeating_the_tap(self):
        probe = HistoryChartViewportProbe(1.0, "below", wrong_selection=True)
        case = SimpleNamespace(probe=probe, history_start=probe.history_start)
        with self.assertRaisesRegex(AssertionError, "List target not reachable: Выбранный интервал"):
            chart._select_history_bar(case, 10, chart.SELECTED_HISTORY_VALUE, direction="start")
        self.assertEqual(len(probe.commands), 1)
        self.assertEqual(probe.observed_labels, [])


if __name__ == "__main__":
    unittest.main()
