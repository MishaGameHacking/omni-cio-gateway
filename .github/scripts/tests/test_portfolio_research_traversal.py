"""Conditional portfolio geometry, not measured Android or font-scale acceptance."""
from datetime import date
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import portfolio_research_probe as research
from profile_ui_probe import ProfileProbe
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
        "company": ((20, 60, "Контекст факта"),
                    (150, 100, ISSUER), (320, 60, "synthetic-issuer"),
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
MENU_LABEL = "Действия с бумагой"
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
        "source": ((20, 60, RESEARCH), (100, 60, WATCH), (260, 60, "SYN-A")),
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
        self.dock_frame_reads = 0

    def tree(self):
        tree = super().tree()
        if self.page == "source":
            # Scaffold.bottomBar is a sibling of the scrolling body. These
            # conditional extents model that ownership, not device pixels.
            top = self.height + 163 + 8
            bottom = top + 48 * self.scale
            tree.set("display-height", str(bottom + 24))
            dock = ET.SubElement(tree, "node", {"package": PACKAGE,
                "resource-id": MENU, "class": "android.widget.Button",
                "bounds": f"[20,{top}][300,{bottom}]", "clickable": "true",
                "visible-to-user": "true", "enabled": "true"})
            ET.SubElement(dock, "node", {"package": PACKAGE, "text": MENU_LABEL,
                "bounds": f"[20,{top}][300,{bottom}]",
                "visible-to-user": "true", "enabled": "true"})
            if self.pending is None:
                self.dock_frame_reads += 1
        return tree

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

    def tap_visible(self, text):
        if text == MENU_LABEL:
            ProfileProbe.tap_visible(self, text)

    def tap_node(self, node):
        if self.page != "source" or node.get("resource-id") != MENU:
            raise AssertionError("Unexpected fixed-dock action")
        self.actions.append(MENU)
        self.selected(MENU)

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
                    call=Mock(), search=Mock(), prefix=Mock(), capture=Mock(), observed=Mock(), record_text=Mock())
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
                self.assertEqual(probe.dock_frame_reads, 4)
                self.assertFalse(any(page == "source" for page, _ in probe.movements))
                self.assertEqual(probe.actions, [MENU, RISKS, CHANGES, BACK, EVENTS])
                self.assertTrue(probe.expanded)
                case.call.assert_any_call("/workspace/risks", {"currency": "RUB"})
                case.call.assert_any_call(research.INSTRUMENTS_PATH + research.SHARE_A + research.DOSSIER_SUFFIX, {})


class ReportTabsProbe(ProfileProbe):
    """Conditional nested rail clipping; unrelated report content is scaffolding."""

    def __init__(self, scale, clipped_first):
        self.scale, self.clipped_first = scale, clipped_first
        self.top, self.selected, self.visits, self.horizontal = 326, 0, 0, 0
        self.vertical_moves, self.actions = [], []
        self.read_tree = self.tree

    def tree(self):
        common = {"package": PACKAGE, "visible-to-user": "true", "enabled": "true"}
        tree = ET.Element("hierarchy", {"display-width": "320",
            "display-height": "640", "active-window-id": "19"})
        body = ET.SubElement(tree, "node", {**common, "resource-id": research.AREA,
            "scrollable": "true", "bounds": "[0,319][320,552]"})
        bottom = self.top + 52 * self.scale
        rail = ET.SubElement(body, "node", {**common, "resource-id": "dossier-tabs",
            "scrollable": "true", "bounds": f"[38,{max(319, self.top)}][282,{min(552, bottom)}]"})
        for index, (left, right, text) in enumerate(((38, 84, "Все"),
                (92, 196, "Объявлены"), (204, 333, "Опубликованы"))):
            left, right = left - self.horizontal, right - self.horizontal
            owner = ET.SubElement(rail, "node", {**common,
                "resource-id": "dossier-tabs-item-" + str(index),
                "bounds": f"[{left},{self.top}][{right},{bottom}]",
                "clickable": str(index != self.selected).lower()})
            ET.SubElement(owner, "node", {**common, "text": text,
                "bounds": f"[{left + 5},{self.top + 10}][{right - 5},{bottom - 10}]"})
        return tree

    def reveal(self, text, area, direction="end"):
        if area != research.AREA:
            raise AssertionError("Unexpected report content list")
        if text == "Календарь отчётности":
            self.visits += 1
            self.top = 519
        elif text == "Все даты":
            self.top = 319 - (52 * self.scale - 33) if self.clipped_first else 326
        return ET.Element("node", {"text": text})

    def reveal_resource(self, *args, **kwargs):
        return ProfileProbe.reveal_resource(self, *args, **kwargs)

    def _semantic_scroll_callback(self, area, direction):
        if area == research.AREA:
            def vertical(*_coordinates):
                expected = "start" if self.top < 319 else "end"
                if direction != expected:
                    raise AssertionError("Parent must move the clipped rail toward its viewport")
                self.vertical_moves.append(direction)
                self.top = 326
            return vertical
        if area == "dossier-tabs":
            def horizontal(*_coordinates):
                self.horizontal = 51
            return horizontal
        raise AssertionError("Unexpected scroll axis")

    def tap(self, text, area, direction="end", **kwargs):
        if area == "dossier-tabs":
            return ProfileProbe.tap(self, text, area, direction, **kwargs)
        if text not in ("Проверенная публикация документа", "Открыть источник"):
            raise AssertionError("Unexpected report action")

    def tap_node(self, node):
        resource = node.get("resource-id")
        if resource not in ("dossier-tabs-item-1", "dossier-tabs-item-2"):
            raise AssertionError("Wrong native report tab")
        self.selected = int(resource[-1])
        self.actions.append(resource)

    wait_for = staticmethod(DossierViewportProbe.wait_for)


class ReportTabsTraversalTests(unittest.TestCase):
    def test_reports_reveal_nested_rail_vertically_before_horizontal_tab_actions(self):
        for scale in (1, 2):
            for clipped_first in (False, True):
                with self.subTest(scale=scale, clipped_first=clipped_first):
                    probe = ReportTabsProbe(scale, clipped_first)
                    case = SimpleNamespace(probe=probe, capture=Mock(), expect=Mock())
                    research._reports(case)
                    self.assertEqual(probe.actions, ["dossier-tabs-item-1", "dossier-tabs-item-2"])
                    self.assertEqual(probe.vertical_moves, (["start"] if clipped_first else []) + ["end"])
                    self.assertEqual(probe.visits, 2)
                    case.capture.assert_any_call("scheduled-report")
                    case.capture.assert_any_call("published-report")


class EventDossierProbe(ProfileProbe):
    """Long conditional dossier; assistant navigation is unrelated scaffolding."""

    HEADINGS = ((400, "Эта бумага на всех счетах"), (1000, "Паспорт рейтинга"),
                (1700, "Показатели компании"), (2600, "Календарь отчётности"),
                (3400, "События и новости"))
    EVENT_ACTION = "dossier-impact-" + research.EVENT
    QUESTION = "Как это событие может повлиять на мои позиции?"

    def __init__(self, scale):
        self.scale, self.offset, self.page = scale, 0, "instrument"
        self.movements, self.actions = [], []
        self.question, self.keyboard = "", False
        self.read_tree = self.tree

    def tree(self):
        common = {"package": PACKAGE, "visible-to-user": "true", "enabled": "true"}
        tree = ET.Element("hierarchy", {"display-width": "320", "display-height": "640",
            "active-window-id": "21", "keyboard-visible": str(self.keyboard).lower()})
        body = ET.SubElement(tree, "node", {**common, "resource-id": research.AREA,
            "scrollable": "true", "bounds": "[0,319][320,552]"})
        if self.page == "assistant":
            ET.SubElement(body, "node", {**common, "resource-id": "assistant-event-question",
                "bounds": "[20,340][300,400]", "clickable": "true"})
            ET.SubElement(body, "node", {**common, "text": self.question,
                "bounds": "[20,410][300,470]", "class": "android.widget.EditText",
                "editable": "true", "focused": str(self.keyboard).lower(),
                "selection-start": str(len(self.question)), "selection-end": str(len(self.question))})
            return tree

        def row(parent, top, height, **attributes):
            upper = max(0, top * self.scale - self.offset)
            lower = min(233, (top + height) * self.scale - self.offset)
            if upper >= lower:
                return None
            return ET.SubElement(parent, "node", {**common,
                "bounds": f"[20,{319 + upper}][300,{319 + lower}]", **attributes})

        for top, label in self.HEADINGS:
            row(body, top, 64, text=label)
        row(body, 100, 64, **{"resource-id": "dossier-impact-news:another-event",
                            "text": "Разобрать возможное влияние", "clickable": "true"})
        row(body, 2100, 64, text="Факт → компания → моя позиция")
        record = row(body, 3500, 1700, **{"resource-id": "dossier-news-" + research.EVENT})
        if record is not None:
            row(record, 4750, 64, text="Факт → компания → моя позиция")
            row(record, 4850, 64, **{"resource-id": self.EVENT_ACTION,
                                   "text": "Разобрать возможное влияние", "clickable": "true"})
        return tree

    def scroll_list(self, area, direction):
        if area != research.AREA or self.page != "dossier" or direction != "end":
            raise AssertionError("Unexpected event traversal")
        previous = self.offset
        self.offset = min(5200 * self.scale - 233, self.offset + 141)
        self.movements.append((previous, self.offset))
        return previous != self.offset

    def _semantic_scroll_callback(self, area, direction):
        return lambda *_coordinates: self.scroll_list(area, direction)

    def _show_resource_on_screen(self, area, resource):
        from profile_scroll import visible_resource
        if area != research.AREA or resource != self.EVENT_ACTION or visible_resource(self.tree(), resource) is None:
            raise AssertionError("Cannot align an absent or unrelated event action")
        self.offset = 4850 * self.scale - 16
        return True

    def tap(self, text, area, direction="end", **kwargs):
        if (text, area, self.page) != ("Досье", "profile-tabs", "instrument"):
            raise AssertionError("Unexpected instrument tab action")
        self.page = "dossier"

    def tap_node(self, node):
        resource = node.get("resource-id")
        if resource == self.EVENT_ACTION and self.page == "dossier":
            self.page = "assistant"
        elif resource == "assistant-event-question" and self.page == "assistant":
            self.question = self.QUESTION
        else:
            raise AssertionError("Wrong event or assistant action")
        self.actions.append(resource)

    def find(self, text):
        if (self.page, text) != ("assistant", "Ассистент"):
            raise AssertionError("Assistant did not open")

    def tap_visible(self, text):
        if text != "Ваш вопрос" or self.question != self.QUESTION:
            raise AssertionError("Unexpected draft focus")
        self.keyboard = True

    def command(self, *args):
        if args != ("shell", "input", "keyevent", "BACK") or not self.keyboard:
            raise AssertionError("Unexpected native input command")
        self.keyboard = False

    wait_for = staticmethod(DossierViewportProbe.wait_for)


class EventDossierTraversalTests(unittest.TestCase):
    def test_event_draft_crosses_long_dossier_and_uses_only_the_exact_unsent_event(self):
        from portfolio_ui_probe import PortfolioCase
        from unittest.mock import patch

        for scale in (1, 2):
            with self.subTest(scale=scale), patch("profile_scroll.time.sleep"):
                probe = EventDossierProbe(scale)
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
                research._event_draft(case)
                self.assertGreater(len(probe.movements), 10)
                self.assertTrue(all(0 < after - before <= 141 for before, after in probe.movements))
                self.assertEqual(probe.actions, [probe.EVENT_ACTION, "assistant-event-question"])
                self.assertEqual(case.extra["event_draft"],
                    {"text": probe.QUESTION, "context": context, "model_request_count": 0})
                self.assertFalse(probe.keyboard)
                self.assertEqual([row["path"] for row in calls], [
                    research.INSTRUMENTS_PATH + research.SHARE_A + research.DOSSIER_SUFFIX,
                    "/workspace/chat/threads",
                    "/workspace/chat/threads/synthetic-portfolio-thread/messages"])
                case.capture.assert_called_once_with("event-draft")


class ShortCompanyViewportProbe(DossierViewportProbe):
    """Company content is below the top landmark in a shortened sheet viewport."""

    EXTENTS = {**DossierViewportProbe.EXTENTS, "company": 900}
    ROWS = {**DossierViewportProbe.ROWS, "company": (
        (20, 60, "Контекст факта"), (150, 100, ISSUER),
        (320, 60, "synthetic-issuer"), (700, 80, POSITIONS))}

    def __init__(self, company_height):
        super().__init__(453)
        self.company_height = company_height

    def transition(self, page, *, preserve):
        super().transition(page, preserve=preserve)
        if page == "company":
            self.height, self.offset = self.company_height, 0
        elif page in {"holdings", "instrument"}:
            self.height = 453
            self.offset = min(self.offset, self.maximum_offset)


class ShortCompanyTraversalTests(unittest.TestCase):
    def test_exact_holding_reaches_company_below_a_short_top_viewport(self):
        for height in (101, 140):
            with self.subTest(company_height=height):
                probe = ShortCompanyViewportProbe(height)
                case = SimpleNamespace(probe=probe, destination=Mock(), capture=Mock())
                research._exact_holding(case)
                self.assertEqual(probe.actions, [FACT, COMPANY, POSITIONS, HOLDING])
                self.assertIn(("company", "end"), probe.movements)
                self.assertNotIn(("company", "start"), probe.movements)
                self.assertEqual(probe.wrong_window_scrolls, 0)
                self.assertEqual(probe.found, ["СИНТЕТИЧЕСКАЯ компания", "SYN-A", "СИНТЕТИЧЕСКИЙ счёт B"])
                case.destination.assert_called_once_with(account=research.ACCOUNT_B, query=research.SHARE_A)
                case.capture.assert_called_once_with("selected-holding")


class DiscoveryComparisonComplete(Exception):
    """Stop after the comparison section; unrelated discovery phases have tests."""


class DiscoveryComparisonProbe(ProfileProbe):
    """Conditional scrolling controls, not Android layout or font acceptance."""

    COMPARE = "Сравнить (2/3)"
    CLEAR = "Снять выбор"
    IDS = tuple("discovery-compare-" + research.ACCOUNT_A + ":" + uid
                for uid in (research.SHARE_A, research.SHARE_B))

    def __init__(self, height, scale):
        self.height, self.scale, self.offset = height, scale, 0
        self.page, self.cleared = "search", False
        self.chosen, self.actions, self.movements = [], [], []
        self.read_tree = self.tree

    def tree(self):
        common = {"package": PACKAGE, "enabled": "true", "visible-to-user": "true"}
        tree = ET.Element("hierarchy", {"display-width": "320",
            "display-height": str(self.height + 187), "active-window-id": "23"})
        body = ET.SubElement(tree, "node", {**common, "resource-id": research.AREA,
            "bounds": f"[0,163][320,{163 + self.height}]", "scrollable": "true"})
        height = 64 * self.scale
        rows = [(250, "scope", "Поиск охватывает подключённый портфель, полученные события и материалы этого аккаунта."),
                (650, self.IDS[0], "Выбрать SYN-A"),
                (1000, self.IDS[1], "Выбрать SYN-B")]
        if self.chosen:
            rows += [(40, "comparison-open", self.COMPARE),
                     (40 + height + 80 * self.scale, "comparison-clear", self.CLEAR)]
        for top, resource, label in rows:
            upper, lower = max(0, top - self.offset), min(self.height, top + height - self.offset)
            if upper >= lower:
                continue
            owner = ET.SubElement(body, "node", {**common, "resource-id": resource,
                "class": "android.widget.Button", "clickable": "true",
                "bounds": f"[20,{163 + upper}][300,{163 + lower}]"})
            ET.SubElement(owner, "node", {**common, "text": label,
                "bounds": f"[28,{163 + upper}][292,{163 + lower}]"})
        return tree

    def _semantic_scroll_callback(self, area, direction):
        if area != research.AREA or direction not in ("start", "end"):
            raise AssertionError("Wrong discovery scroll target")
        def move(_x1, y1, _x2, y2):
            if ("end" if y1 > y2 else "start") != direction:
                raise AssertionError("Wrong discovery scroll direction")
            before = self.offset
            self.offset = max(0, min(1400 - self.height, before + y1 - y2))
            self.movements.append((direction, before, self.offset))
        return move

    def tap_resource(self, resource, area, direction="end"):
        if resource not in self.IDS or area != research.AREA:
            raise AssertionError("Wrong account or instrument selected")
        target = reveal_resource_in_list(self.tree,
            self._semantic_scroll_callback(area, direction), resource,
            resource_id=area, direction=direction, for_tap=True)
        self.tap_node(target)

    def tap_node(self, node):
        resource = node.get("resource-id")
        if resource in self.IDS:
            if resource in self.chosen:
                raise AssertionError("Duplicate instrument selected")
            self.chosen.append(resource)
            self.actions.append(resource)
        elif resource == "comparison-open":
            if self.chosen != list(self.IDS):
                raise AssertionError("Comparison must retain both exact instruments")
            self.page = "comparison"
            self.actions.append(self.COMPARE)
        elif resource == "comparison-clear":
            if self.page != "search":
                raise AssertionError("Clear belongs to the original search window")
            self.chosen.clear()
            self.cleared = True
            self.actions.append(self.CLEAR)
        else:
            raise AssertionError("Unexpected native comparison action")

    def tap(self, text, area, direction="end"):
        if area == "profile-tabs":
            if text == "Активы":
                return
            if text == "Выплаты" and self.cleared:
                raise DiscoveryComparisonComplete()
            raise AssertionError("Comparison did not finish")
        if self.page == "comparison":
            if text != "Одинаковый период по реальным котировкам":
                raise AssertionError("Unexpected comparison section")
            return
        return ProfileProbe.tap(self, text, area, direction)

    def tap_visible(self, text):
        if text == research.BACK_LABEL and self.page == "comparison":
            self.page = "search"
            self.return_movements = len(self.movements)
            self.actions.append(text)
            return
        return ProfileProbe.tap_visible(self, text)

    def find(self, text):
        expected = "Сравнение" if self.page == "comparison" else "Найти и исследовать"
        if text != expected:
            raise AssertionError("Unexpected discovery page")

    def reveal(self, text, area, direction="end"):
        if self.page == "search" and area == research.AREA:
            return ProfileProbe.reveal(self, text, area, direction)
        if self.page != "comparison" or area != research.AREA:
            raise AssertionError("Unrelated discovery content was not reached")
        return ET.Element("node", {"text": text})


class DiscoveryComparisonTraversalTests(unittest.TestCase):
    def test_offscreen_comparison_controls_preserve_exact_selected_instruments(self):
        for height, scale in ((269, 1), (190, 2)):
            with self.subTest(viewport=height, conditional_scale=scale):
                probe = DiscoveryComparisonProbe(height, scale)
                case = SimpleNamespace(probe=probe, day=date(2026, 10, 26),
                    call=Mock(), search=Mock(), prefix=Mock(), capture=Mock(), observed=Mock(), record_text=Mock())
                with patch("native_label_target.time.sleep"):
                    with self.assertRaises(DiscoveryComparisonComplete):
                        research.exercise_discovery(case)
                self.assertEqual(probe.actions, [*probe.IDS, probe.COMPARE,
                    research.BACK_LABEL, probe.CLEAR])
                self.assertEqual(probe.chosen, [])
                self.assertTrue(probe.cleared)
                self.assertTrue(any(direction == "start" and before > after
                                    for direction, before, after in probe.movements))
                if scale == 2:
                    self.assertTrue(any(direction == "end" and after > before
                                        for direction, before, after in probe.movements[probe.return_movements:]))
                for uid in (research.SHARE_A, research.SHARE_B):
                    case.call.assert_any_call(research.INSTRUMENTS_PATH + uid + "/candles",
                        {"start": "2026-09-26", "end": "2026-10-26", "interval": "day"})
                case.capture.assert_any_call("comparison")


if __name__ == "__main__":
    unittest.main()
