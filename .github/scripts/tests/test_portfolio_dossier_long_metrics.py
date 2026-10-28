"""Reopened dossiers must traverse their full conflict records before the event."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import portfolio_research_probe as research
from portfolio_ui_probe import PortfolioCase
from profile_scroll import PACKAGE
from test_portfolio_research_traversal import EventDossierProbe


class LongMetricsEventProbe(EventDossierProbe):
    """Chosen long-record extents, with the real bounded native traversal helpers."""

    HEADINGS = ((400, "Эта бумага на всех счетах"), (1000, "Паспорт рейтинга"),
                (1700, "Показатели компании"), (6100, "Календарь отчётности"),
                (6900, "События и новости"))
    MISSING = "Источник обозначает нулём отсутствие данных. Числовая оценка не подставляется."

    def __init__(self, scale, *, missing_second_value=False, wrong_second_package=False):
        super().__init__(scale)
        self.missing_second_value = missing_second_value
        self.wrong_second_package = wrong_second_package

    def tree(self):
        if self.page == "assistant":
            return super().tree()
        common = {"package": PACKAGE, "visible-to-user": "true", "enabled": "true"}
        tree = ET.Element("hierarchy", {"display-width": "320", "display-height": "640",
            "active-window-id": "21", "keyboard-visible": "false"})
        body = ET.SubElement(tree, "node", {**common, "resource-id": research.AREA,
            "scrollable": "true", "bounds": "[56,272][320,508]"})

        def row(parent, top, height, **attributes):
            upper = max(0, top * self.scale - self.offset)
            lower = min(236, (top + height) * self.scale - self.offset)
            if lower <= upper:
                return None
            return ET.SubElement(parent, "node", {**common,
                "bounds": f"[88,{272 + upper}][288,{272 + lower}]", **attributes})

        for top, label in self.HEADINGS:
            row(body, top, 64, text=label)
        row(body, 2100, 100, text="СИНТЕТИЧЕСКОЕ расхождение периодов")
        for index, start, value, currency, period in (
            (0, 2300, "12.5", "RUB", "2026-06-30T00:00:00Z"),
            (1, 4100, "8.25", "USD", "2025-06-30T00:00:00Z"),
        ):
            record_package = "other.application" if index == 1 and self.wrong_second_package else PACKAGE
            record = row(body, start, 1500, **{"resource-id": "dossier-conflict-observation-" + str(index),
                                             "package": record_package})
            fields = ((150, period), (350, currency),
                      (550, "СИНТЕТИЧЕСКАЯ прибыль из конфликтующей записи"),
                      (650, value), (800, "СИНТЕТИЧЕСКАЯ неизвестная выручка"),
                      (1000, "Не получено"), (1150, self.MISSING))
            if record is not None:
                for offset, label in fields:
                    if index == 1 and self.missing_second_value and label == value:
                        continue
                    row(record, start + offset, 100, text=label, **{"package": record_package})
            if index == 1 and self.missing_second_value:
                # A same-valued label outside the exact observation must not pass.
                row(body, start + 650, 100, text=value)
        row(body, 5700, 100, text="Наблюдения относятся к разным периодам или валютам.")
        row(body, 100, 64, **{"resource-id": "dossier-impact-news:another-event",
                            "text": "Разобрать возможное влияние", "clickable": "true"})
        record = row(body, 7000, 1700, **{"resource-id": "dossier-news-" + research.EVENT})
        if record is not None:
            row(record, 8250, 64, text="Факт → компания → моя позиция")
            row(record, 8350, 64, **{"resource-id": self.EVENT_ACTION,
                                   "text": "Разобрать возможное влияние", "clickable": "true"})
        return tree

    def scroll_list(self, area, direction):
        if area != research.AREA or self.page != "dossier" or direction != "end":
            raise AssertionError("Unexpected long-metric traversal")
        previous = self.offset
        self.offset = min(8700 * self.scale - 236, self.offset + 142)
        self.movements.append((previous, self.offset))
        return previous != self.offset

    def _show_resource_on_screen(self, area, resource):
        from profile_scroll import visible_resource
        if area != research.AREA or resource != self.EVENT_ACTION or visible_resource(self.tree(), resource) is None:
            raise AssertionError("Cannot align an absent or unrelated event action")
        self.offset = 8350 * self.scale - 16
        return True


class LongMetricsEventTraversalTests(unittest.TestCase):
    def case(self, probe):
        calls = []
        context = {"mode": "instrument", "instrument_uid": research.SHARE_A,
            "account_id": None, "start": None, "end": None,
            "event_id": research.EVENT, "title": "СИНТЕТИЧЕСКАЯ публикация"}

        def observed():
            return {"calls": calls, "current_page": probe.page, "chat_context": context}

        case = SimpleNamespace(probe=probe, extra={}, capture=Mock(), observed=observed,
            call=lambda path, query: calls.append({"method": "GET", "path": path, "query": query}),
            expect=lambda predicate, message: self.assertTrue(predicate(observed()), message))
        case.record_text = lambda *args, **kwargs: PortfolioCase.record_text(case, *args, **kwargs)
        return case

    def test_reopened_dossier_reaches_event_after_both_full_conflict_observations(self):
        for scale in (1, 2):
            with self.subTest(conditional_scale=scale), patch("profile_scroll.time.sleep"):
                probe = LongMetricsEventProbe(scale)
                case = self.case(probe)
                research._event_draft(case)
                self.assertEqual(probe.actions, [probe.EVENT_ACTION, "assistant-event-question"])
                self.assertEqual([row["period"] for row in case.extra["conflicting_observations"]],
                                 ["2026-06-30T00:00:00Z", "2025-06-30T00:00:00Z"])
                self.assertEqual([row["value"] for row in case.extra["conflicting_observations"]], ["12.5", "8.25"])
                self.assertEqual(case.extra["event_draft"]["model_request_count"], 0)
                self.assertTrue(all(0 < after - before <= 142 for before, after in probe.movements))
                self.assertFalse(probe.keyboard)
                case.capture.assert_called_once_with("event-draft")

    def test_a_matching_value_outside_its_observation_cannot_reach_the_event(self):
        probe = LongMetricsEventProbe(2, missing_second_value=True)
        with patch("profile_scroll.time.sleep"), self.assertRaisesRegex(
                AssertionError, "Exact native source record did not expose its value: dossier-conflict-observation-1 / 8.25"):
            research._event_draft(self.case(probe))
        self.assertEqual(probe.actions, [])

    def test_a_foreign_observation_cannot_reach_the_event(self):
        probe = LongMetricsEventProbe(2, wrong_second_package=True)
        with patch("profile_scroll.time.sleep"), self.assertRaises(AssertionError):
            research._event_draft(self.case(probe))
        self.assertEqual(probe.actions, [])


if __name__ == "__main__":
    unittest.main()
