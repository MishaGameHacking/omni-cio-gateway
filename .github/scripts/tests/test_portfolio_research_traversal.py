"""Conditional dossier geometry, not measured Android or font-scale acceptance."""
from datetime import date
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import portfolio_research_probe as research
from profile_scroll import PACKAGE, reveal_in_list, reveal_resource_in_list, visible_label

ISSUER = "СИНТЕТИЧЕСКИЙ проверенный эмитент"
FACT = "dossier-fact-news-" + research.EVENT
HOLDING = "dossier-holding-" + research.ACCOUNT_B
COMPANY = "Перейти к компании"
POSITIONS = "Мои позиции в этой бумаге"


class DossierViewportProbe:
    """Use real bounded reveal helpers across the full fact-to-holding traversal.

    DossierFactSheet keeps one scroll state when its fact/company/holding content
    changes. These chosen extents model preservation followed by range clamping;
    intervening content is represented by the extent, not invented device pixels.
    """

    EXTENTS = {"dossier": 2300, "fact": 1460, "company": 1160,
               "holdings": 1600, "instrument": 260}
    ROWS = {
        "dossier": ((1200, 60, FACT),),
        "fact": ((20, 60, "Контекст факта"),
                 (150, 90, "Первый СИНТЕТИЧЕСКИЙ подтверждённый факт"),
                 (1260, 60, COMPANY)),
        "company": ((150, 100, ISSUER), (320, 60, "synthetic-issuer"),
                    (970, 80, POSITIONS)),
        "holdings": ((1320, 70, HOLDING),),
        "instrument": ((20, 60, "СИНТЕТИЧЕСКАЯ компания"), (90, 60, "SYN-A"),
                       (160, 60, "СИНТЕТИЧЕСКИЙ счёт B")),
    }
    TRANSITIONS = {("dossier", FACT): ("fact", False),
                   ("fact", COMPANY): ("company", True),
                   ("company", POSITIONS): ("holdings", True),
                   ("holdings", HOLDING): ("instrument", False)}
    RESOURCES = {FACT, HOLDING}
    RESOURCE_LABELS = {}
    EXTRA_ACTIONS = set()

    def __init__(self, height, *, scale=1, page="dossier"):
        self.height, self.scale, self.page = height, scale, page
        self.offset = self.maximum_offset if page == "dossier" else 0
        self.window, self.pending = 41, None
        self.old_frame_reads, self.wrong_window_scrolls = 0, 0
        self.actions, self.movements, self.found = [], [], []
        self.transitions = {}

    @property
    def maximum_offset(self):
        return max(0, self.EXTENTS[self.page] * self.scale - self.height)

    def rows(self):
        return self.ROWS[self.page]

    def tree(self):
        if self.pending is not None:
            if self.pending[1] > 0:
                self.pending[1] -= 1
                self.old_frame_reads += 1
            else:
                self.transition(self.pending[0], preserve=False)
        tree = ET.Element("hierarchy", {"display-width": "320",
            "display-height": str(self.height + 187), "active-window-id": str(self.window)})
        viewport = ET.SubElement(tree, "node", {"package": PACKAGE,
            "resource-id": research.AREA, "bounds": f"[0,163][320,{self.height + 163}]",
            "scrollable": str(self.maximum_offset > 0).lower(),
            "visible-to-user": "true", "enabled": "true"})
        for top, height, value in self.rows():
            upper = max(0, top * self.scale - self.offset)
            lower = min(self.height, (top + height) * self.scale - self.offset)
            if upper >= lower:
                continue
            attribute = "resource-id" if value in self.RESOURCES else "text"
            ET.SubElement(viewport, "node", {"package": PACKAGE, attribute: value,
                **({"text": self.RESOURCE_LABELS.get(value, "")} if attribute == "resource-id" else {}),
                "bounds": f"[20,{163 + upper}][300,{163 + lower}]",
                "clickable": str((self.page, value) in self.TRANSITIONS or value in self.EXTRA_ACTIONS).lower(),
                "visible-to-user": "true", "enabled": "true"})
        return tree

    def scroll(self, _x1, y1, _x2, y2):
        if self.pending is not None:
            # The action gets a fresh native root even though its caller saw
            # the previous modal's frame. Apply the gesture to that new list.
            self.transition(self.pending[0], preserve=False)
            self.wrong_window_scrolls += 1
        self.movements.append((self.page, "end" if y1 > y2 else "start"))
        self.offset = max(0, min(self.maximum_offset, self.offset + y1 - y2))

    def reveal(self, text, area, direction="end"):
        return reveal_in_list(self.tree, self.scroll, text,
                              resource_id=area, direction=direction)

    def _tap(self, reveal, value, area, direction):
        if reveal(self.tree, self.scroll, value, resource_id=area,
                  direction=direction, for_tap=True) is None:
            raise AssertionError("The native action is absent: " + value)
        self.actions.append(value)
        self.selected(value)

    def selected(self, value):
        page, preserve = self.TRANSITIONS[self.page, value]
        if not preserve and page not in {"instrument", "source"}:
            self.pending = [page, 2]
        else:
            self.transition(page, preserve=preserve)

    def transition(self, page, *, preserve):
        previous = self.offset
        self.page, self.pending = page, None
        self.offset = min(previous, self.maximum_offset) if preserve else 0
        if not preserve:
            self.window += 1
        self.transitions[self.page] = previous, self.offset

    def tap(self, text, area, direction="end"):
        self._tap(reveal_in_list, text, area, direction)

    def tap_resource(self, resource, area, direction="end"):
        self._tap(reveal_resource_in_list, resource, area, direction)

    def find(self, text):
        if visible_label(self.tree(), text) is None:
            raise AssertionError("Selected holding label is absent: " + text)
        self.found.append(text)

    @staticmethod
    def wait_for(read, message):
        for _ in range(16):
            value = read()
            if value is not None and value is not False:
                return value
        raise AssertionError(message)


class DossierTraversalTests(unittest.TestCase):
    def assert_holding_reached(self, height):
        probe = DossierViewportProbe(height)
        case = SimpleNamespace(probe=probe, destination=Mock(), capture=Mock())
        research._exact_holding(case)
        self.assertEqual(probe.wrong_window_scrolls, 0)
        self.assertEqual(probe.old_frame_reads, 2)
        self.assertEqual(probe.actions, [FACT, COMPANY, POSITIONS, HOLDING])
        self.assertEqual(probe.page, "instrument")
        self.assertEqual(probe.found, ["СИНТЕТИЧЕСКАЯ компания", "SYN-A", "СИНТЕТИЧЕСКИЙ счёт B"])
        case.destination.assert_called_once_with(account=research.ACCOUNT_B, query=research.SHARE_A)
        case.capture.assert_called_once_with("selected-holding")
        return probe

    def test_small_viewports_return_to_issuer_above_preserved_company_offset(self):
        for height in (453, 720):
            with self.subTest(viewport_height=height):
                probe = self.assert_holding_reached(height)
                previous, clamped = probe.transitions["company"]
                self.assertGreater(previous, clamped)
                self.assertEqual(clamped, 1160 - height)
                self.assertGreater(clamped, 250)  # The whole issuer label is above the viewport.
                self.assertIn(("company", "start"), probe.movements)

    def test_large_viewport_clamps_company_offset_to_zero_without_upward_scroll(self):
        probe = self.assert_holding_reached(1300)
        previous, clamped = probe.transitions["company"]
        self.assertGreater(previous, 0)
        self.assertEqual(clamped, 0)
        self.assertNotIn(("company", "start"), probe.movements)


RESEARCH = "discovery-research-" + research.SHARE_A
WATCH = "Открыть бумагу на всех счетах"
MENU = "instrument-context-actions"
RISKS = "instrument-context-risks"
EVENTS = "instrument-context-events"
CHANGES = "Изменения риска этой бумаги"
RISK_EVENT = "СИНТЕТИЧЕСКОЕ изменение риска выбранной бумаги"
BACK = "Назад к действиям"


class ResearchWindowProbe(DossierViewportProbe):
    """Unrelated discovery setup is scaffolding; modal traversal uses real helpers."""

    EXTENTS = {"source": 1200, "research": 900, "watch": 900,
               "menu": 1000, "risks": 1250}
    ROWS = {
        "source": ((20, 60, RESEARCH), (100, 60, WATCH), (180, 60, MENU), (260, 60, "SYN-A")),
        "research": ((0, 60, "Закрыть разбор"),
                     (120, 100, "Показана одна выбранная карточка. Общие выводы относятся к исходному анализу."),
                     (350, 80, "СИНТЕТИЧЕСКОЕ исследование RESEARCH")),
        "watch": ((0, 60, "Закрыть досье"), (120, 80, "Эта бумага на всех счетах"),
                  (400, 60, "СИНТЕТИЧЕСКИЙ счёт A"), (550, 60, "СИНТЕТИЧЕСКИЙ счёт B")),
        "menu": ((0, 60, "SYN-A"), (260, 60, RISKS), (390, 60, EVENTS)),
        "risks": ((0, 60, "SYN-A"), (160, 70, "Риски этой бумаги"),
                  (320, 60, "СИНТЕТИЧЕСКАЯ концентрация выбранной бумаги"),
                  (430, 60, "42.4242%"), (510, 60, "Лимит превышен"),
                  (590, 60, "Кредитное качество"), (690, 60, CHANGES),
                  (800, 60, RISK_EVENT), (1120, 60, BACK)),
    }
    TRANSITIONS = {("source", RESEARCH): ("research", False),
                   ("research", "Закрыть разбор"): ("source", False),
                   ("source", WATCH): ("watch", False),
                   ("watch", "Закрыть досье"): ("source", False),
                   ("source", MENU): ("menu", False),
                   ("menu", RISKS): ("risks", False),
                   ("risks", BACK): ("menu", False),
                   ("menu", EVENTS): ("source", False)}
    RESOURCES = {RESEARCH, MENU, RISKS, EVENTS}
    RESOURCE_LABELS = {RISKS: "Риски этой бумаги"}
    EXTRA_ACTIONS = {CHANGES}

    def __init__(self, scale):
        super().__init__(453, scale=scale, page="source")
        self.expanded = False

    def rows(self):
        return [row for row in super().rows() if row[2] != RISK_EVENT or self.expanded]

    def selected(self, value):
        if value == CHANGES:
            self.expanded = True
        else:
            super().selected(value)

    def tap_resource(self, resource, area, direction="end"):
        if resource in self.RESOURCES:
            super().tap_resource(resource, area, direction)

    def tap(self, text, area, direction="end"):
        if self.page != "source" or text == WATCH:
            super().tap(text, area, direction)

    def reveal(self, text, area, direction="end"):
        if self.page != "source" or self.pending is not None:
            return super().reveal(text, area, direction)
        return ET.Element("node")

    @staticmethod
    def tap_visible(_text):
        return None

    @staticmethod
    def find(_text):
        return None

    def read_tree(self):
        return self.tree()

    def scroll_list(self, area, direction):
        if area != research.AREA or direction != "end":
            raise AssertionError("Unexpected context-risk traversal")
        previous = self.offset
        self.scroll(0, self.height // 2, 0, 0)
        return previous != self.offset


class ResearchWindowTraversalTests(unittest.TestCase):
    def test_discovery_handlers_wait_for_both_new_dialogs_before_scrolling(self):
        for scale in (1, 2):
            with self.subTest(scale=scale):
                probe = ResearchWindowProbe(scale)
                case = SimpleNamespace(probe=probe, day=date(2026, 10, 18),
                    history_start="2026-01-01", history_end="2026-06-30",
                    call=Mock(), search=Mock(), prefix=Mock(), capture=Mock(), observed=Mock())
                checks = research.exercise_discovery(case)
                self.assertEqual(probe.wrong_window_scrolls, 0)
                self.assertEqual(probe.old_frame_reads, 4)
                self.assertEqual(probe.actions, [RESEARCH, "Закрыть разбор", WATCH, "Закрыть досье"])
                self.assertIn("single-research-selection", checks)
                self.assertIn("watch-reason-and-all-accounts", checks)
                case.capture.assert_any_call("watch-dossier")

    def test_context_handlers_wait_for_menu_risks_and_reopened_menu(self):
        for scale in (1, 2):
            with self.subTest(scale=scale):
                probe = ResearchWindowProbe(scale)
                case = SimpleNamespace(probe=probe, call=Mock())
                research._context_risks(case)
                self.assertEqual(probe.wrong_window_scrolls, 0)
                self.assertEqual(probe.old_frame_reads, 6)
                self.assertEqual(probe.actions, [MENU, RISKS, CHANGES, BACK, EVENTS])
                self.assertTrue(probe.expanded)
                case.call.assert_any_call("/workspace/risks", {"currency": "RUB"})
                case.call.assert_any_call(research.INSTRUMENTS_PATH + research.SHARE_A + research.DOSSIER_SUFFIX, {})


if __name__ == "__main__":
    unittest.main()
