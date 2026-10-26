"""Adversarial calendar and native control readers, not Android runtime proof."""
from datetime import date
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from portfolio_chart_probe import month_before, range_description, quote_interval_target
from portfolio_preferences_probe import selected_control
from portfolio_ui_probe import PortfolioCase

PACKAGE = "ru.omnicio.app.debug"


class PortfolioControlsEvidenceTests(unittest.TestCase):
    def test_financial_value_must_belong_to_the_exact_visible_source_record(self):
        tree = ET.Element("hierarchy")
        common = {"package": PACKAGE, "visible-to-user": "true", "bounds": "[20,100][300,180]"}
        first = ET.SubElement(tree, "node", {**common, "resource-id": "dossier-conflict-observation-0"})
        correct = ET.SubElement(first, "node", {**common, "text": "12.5"})
        second = ET.SubElement(tree, "node", {**common, "resource-id": "dossier-conflict-observation-1"})
        ET.SubElement(second, "node", {**common, "text": "8.25"})

        class Reader:
            def read(self):
                return tree

            def scroll_list(self, area, direction):
                return False

        reader = Reader()
        case = object.__new__(PortfolioCase)
        case.probe = SimpleNamespace(tree=reader.read, read_tree=reader.read, reveal_resource=lambda *args, **kwargs: first)
        self.assertIs(correct, case.record_text("dossier-conflict-observation-0", "12.5"))
        with self.assertRaises(AssertionError):
            case.record_text("dossier-conflict-observation-0", "8.25")
        correct.set("visible-to-user", "false")
        with self.assertRaises(AssertionError):
            case.record_text("dossier-conflict-observation-0", "12.5")

    def test_quote_period_preserves_calendar_month_rules(self):
        for current, expected in ((date(2026, 3, 31), date(2026, 2, 28)),
                                  (date(2024, 3, 31), date(2024, 2, 29)),
                                  (date(2026, 1, 1), date(2025, 12, 1)),
                                  (date(2026, 10, 17), date(2026, 9, 17))):
            self.assertEqual(expected, month_before(current))

    def test_range_requires_one_exact_native_date(self):
        node = ET.Element("node", {"content-desc": "Начало периода: 2026-10-03"})
        self.assertEqual(date(2026, 10, 3), range_description(node, "Начало периода: "))
        for description in ("Начало периода: вчера", "Начало периода: 2026-13-03",
                            "Начало периода: 2026-10-03\nНачало периода: 2026-10-04",
                            "Конец периода: 2026-10-03"):
            node.set("content-desc", description)
            with self.assertRaises((AssertionError, ValueError)):
                range_description(node, "Начало периода: ")

    def test_quote_interval_does_not_tap_same_label_in_period_controls(self):
        root = ET.Element("hierarchy")
        common = {"package": PACKAGE, "visible-to-user": "true"}
        ET.SubElement(root, "node", {**common, "text": "Месяц", "clickable": "true",
                                    "bounds": "[10,100][150,160]", "selected": "true"})
        row = ET.SubElement(root, "node", {**common, "resource-id": "quotes-intervals",
                                          "bounds": "[20,200][320,260]"})
        button = ET.SubElement(row, "node", {**common, "clickable": "true", "selected": "false",
                                             "bounds": "[270,200][390,260]"})
        ET.SubElement(button, "node", {**common, "text": "Месяц"})
        target = quote_interval_target(root, "Месяц")
        self.assertEqual("[270,200][320,260]", target.get("bounds"))
        self.assertEqual("false", target.get("selected"))
        button.set("bounds", "[300,200][420,260]")
        self.assertIsNone(quote_interval_target(root, "Месяц"))

    def test_quote_interval_requires_one_visible_owned_rail(self):
        root = ET.Element("hierarchy")
        row = ET.SubElement(root, "node", {"package": PACKAGE, "visible-to-user": "true",
                                          "resource-id": PACKAGE + ":id/quotes-intervals",
                                          "bounds": "[20,200][320,260]"})
        ET.SubElement(row, "node", {"package": PACKAGE, "visible-to-user": "true",
                                   "clickable": "true", "text": "Час", "bounds": "[20,200][120,260]"})
        self.assertIsNotNone(quote_interval_target(root, "Час"))
        duplicate = ET.SubElement(root, "node", dict(row.attrib))
        self.assertIsNone(quote_interval_target(root, "Час"))
        duplicate.set("visible-to-user", "false")
        self.assertIsNotNone(quote_interval_target(root, "Час"))
        row.set("package", "other.app")
        self.assertIsNone(quote_interval_target(root, "Час"))
        with self.assertRaises(ValueError):
            quote_interval_target(root, "Произвольный интервал")

    def test_visible_title_without_native_selection_cannot_prove_persistence(self):
        root = ET.Element("hierarchy")
        control = ET.SubElement(root, "node", {"package": PACKAGE, "visible-to-user": "true", "checked": "false", "checkable": "true"})
        ET.SubElement(control, "node", {"package": PACKAGE, "visible-to-user": "true", "text": "Яркое освещение"})
        self.assertIsNone(selected_control(root, "Яркое освещение", checked=True))
        self.assertIs(control, selected_control(root, "Яркое освещение", checked=False))
        control.set("checked", "true")
        self.assertIs(control, selected_control(root, "Яркое освещение", checked=True))
        self.assertIs(control, selected_control(root, "Яркое освещение"))
        for field, value in (("package", "other.app"), ("visible-to-user", "false")):
            before = control.get(field)
            control.set(field, value)
            self.assertIsNone(selected_control(root, "Яркое освещение", checked=True))
            control.set(field, before)


FOLD_LABEL = "Публикация и актуальность рейтинга"
RATING_RECORDS = tuple("dossier-rating-history-synthetic-rating-" + kind + "-history"
                       for kind in ("issue", "issuer"))


class SourceFoldProbe:
    """Conditional scrolling motion consumes early taps; no device-pixel claim."""

    def __init__(self, scale=1):
        self.scale, self.reads, self.stable = scale, 0, 0
        self.previous_top, self.pending = None, None
        self.expanded = dict.fromkeys(RATING_RECORDS, False)
        self.tap_attempts, self.fold_actions = [], []
        self.ignore_tap = False
        self.read_tree = self.tree

    def tree(self):
        self.reads += 1
        top = 400 - min(self.reads, 3)
        self.stable = self.stable + 1 if top == self.previous_top else 1
        self.previous_top = top
        if self.pending is not None:
            resource, expanded, remaining = self.pending
            if remaining:
                self.pending = resource, expanded, remaining - 1
            else:
                self.expanded[resource] = expanded
                self.fold_actions.append((resource, expanded))
                self.pending = None
        bottom = 552 + (self.scale - 1) * 200
        tree = ET.Element("hierarchy", {"display-width": "320",
            "display-height": str(bottom + 88), "active-window-id": "19"})
        common = {"package": PACKAGE, "visible-to-user": "true", "enabled": "true"}
        viewport = ET.SubElement(tree, "node", {**common, "resource-id": "workspace-content",
            "scrollable": "true", "bounds": f"[0,319][320,{bottom}]"})
        for index, resource in enumerate(RATING_RECORDS):
            upper = top + index * 72 * self.scale
            lower = upper + 63 * self.scale
            bounds = f"[38,{upper}][282,{lower}]"
            row = ET.SubElement(viewport, "node", {**common, "resource-id": resource, "bounds": bounds})
            owner = ET.SubElement(row, "node", {**common, "bounds": bounds, "clickable": "true",
                "state-description": "Развёрнуто" if self.expanded[resource] else "Свёрнуто"})
            ET.SubElement(owner, "node", {**common, "text": FOLD_LABEL,
                "bounds": f"[80,{upper + 12}][270,{lower - 12}]"})
        return tree

    def reveal_resource(self, resource, _area, **_kwargs):
        return next(node for node in self.tree().iter("node") if node.get("resource-id") == resource)

    @staticmethod
    def scroll_list(_area, _direction):
        raise AssertionError("These visible source folds must not be scrolled past")

    def _semantic_scroll_callback(self, area, direction):
        if area != "workspace-content" or direction not in ("start", "end"):
            raise AssertionError("Wrong native source list")
        return lambda *_args: self.scroll_list(area, direction)

    def tap_node(self, node):
        from profile_ui_probe import node_bounds
        self.tap_attempts.append(dict(node.attrib))
        if self.stable < 3 or self.ignore_tap:
            return  # A tap during the modeled scroll stops motion, not the fold.
        left, top, right, bottom = node_bounds(node)
        center = (top + bottom) // 2
        index = 0 if center < self.previous_top + 72 * self.scale else 1
        resource = RATING_RECORDS[index]
        self.pending = resource, not self.expanded[resource], 2

    @staticmethod
    def tap(text, _area, **_kwargs):
        if text != "Как менялся рейтинг":
            raise AssertionError("Unrelated dossier action is not part of this fixture")

    @staticmethod
    def wait_for(read, message):
        for _ in range(16):
            value = read()
            if value is not None and value is not False:
                return value
        raise AssertionError(message)


class RatingFoldCase(PortfolioCase):
    """Financial field assertions are scaffolding; fold traversal uses real helpers."""

    def __init__(self, scale=1):
        self.probe, self.day, self.extra = SourceFoldProbe(scale), date(2026, 10, 26), {}

    def record_text(self, resource, text, *, direction="end"):
        if text == FOLD_LABEL:
            return super().record_text(resource, text, direction=direction)
        if text.startswith(("Публикация: ", "https://")) and not self.probe.expanded[resource]:
            raise AssertionError("Selected rating source remained collapsed")
        return ET.Element("node", {"text": text})


class RatingFoldTraversalTests(unittest.TestCase):
    def test_rating_history_waits_for_scoped_native_fold_transition(self):
        from portfolio_research_probe import _rating_history
        for scale in (1, 2):
            with self.subTest(scale=scale):
                case = RatingFoldCase(scale)
                _rating_history(case)
                self.assertEqual(case.probe.fold_actions,
                    [(resource, expanded) for resource in RATING_RECORDS for expanded in (True, False)])
                self.assertEqual(len(case.probe.tap_attempts), 4)
                self.assertEqual([row["resource"] for row in case.extra["rating_history"]], list(RATING_RECORDS))

    def test_scope_excludes_sibling_labels_and_preserves_clipping_and_disabled_ancestors(self):
        from native_label_target import label_target
        from portfolio_ui_probe import _record_scope
        probe = SourceFoldProbe()
        tree = probe.tree()
        first, second = RATING_RECORDS
        target = label_target(_record_scope(tree, first), FOLD_LABEL)
        self.assertIsNotNone(target)
        self.assertNotEqual(target.get("bounds"), label_target(_record_scope(tree, second), FOLD_LABEL).get("bounds"))
        self.assertIsNone(label_target(_record_scope(tree, "absent-source"), FOLD_LABEL))
        viewport = next(node for node in tree.iter("node") if node.get("resource-id") == "workspace-content")
        viewport.set("enabled", "false")
        self.assertIsNone(label_target(_record_scope(tree, first), FOLD_LABEL))
        viewport.set("enabled", "true")
        viewport.set("bounds", "[0,319][320,420]")
        self.assertIsNone(label_target(_record_scope(tree, first), FOLD_LABEL))
        row = next(node for node in tree.iter("node") if node.get("resource-id") == first)
        duplicate = ET.SubElement(viewport, "node", dict(row.attrib))
        with self.assertRaisesRegex(AssertionError, "several native records"):
            _record_scope(tree, first)
        duplicate.set("package", "another.app")
        row.set("visible-to-user", "false")
        self.assertIsNone(label_target(_record_scope(tree, first), FOLD_LABEL))

    def test_missing_native_transition_is_a_failure_without_repeated_taps(self):
        case = RatingFoldCase()
        case.probe.ignore_tap = True
        with self.assertRaisesRegex(AssertionError, "did not change state"):
            case.record_fold(RATING_RECORDS[0], FOLD_LABEL, expanded=True)
        self.assertEqual(len(case.probe.tap_attempts), 1)
        self.assertFalse(case.probe.fold_actions)

    def test_unexpected_fold_state_does_not_toggle_the_source_again(self):
        case = RatingFoldCase()
        case.probe.expanded[RATING_RECORDS[0]] = True
        with self.assertRaisesRegex(AssertionError, "Unexpected initial"):
            case.record_fold(RATING_RECORDS[0], FOLD_LABEL, expanded=True)
        self.assertFalse(case.probe.tap_attempts)
        with self.assertRaises(ValueError):
            case.record_fold(RATING_RECORDS[0], FOLD_LABEL, expanded="true")


class HistorySelectionEvidenceTests(unittest.TestCase):
    """Exercise the real history assertion; unrelated gestures are scaffolding."""

    CLOSE = "Выбрано · 22.10.2026 21:00:00 · 901.75 ₽"

    def exercise(self, *, selected="false", checkable="true", checked="true",
                 label=CLOSE, state="Selected", sibling_label=False):
        from datetime import datetime, timezone
        from unittest.mock import Mock, patch
        import portfolio_chart_probe as chart

        row = ET.Element("node", {"package": PACKAGE, "visible-to-user": "true",
            "enabled": "true", "resource-id": "history-observation-10",
            "bounds": "[34,457][286,531]", "selected": selected,
            "checkable": checkable, "checked": checked, "state-description": state})
        root = ET.Element("hierarchy")
        root.append(row)
        ET.SubElement(root if sibling_label else row, "node", {
            "package": PACKAGE, "visible-to-user": "true", "text": label,
            "bounds": "[46,469][274,519]"})

        def reveal_resource(resource, area):
            self.assertEqual((resource, area), ("history-observation-10", chart.AREA))
            return row

        probe = SimpleNamespace(reveal=Mock(), tap=Mock(), find=Mock(),
            tap_resource=Mock(), reveal_resource=reveal_resource)
        case = SimpleNamespace(probe=probe, scenario="ready",
            history_start=date(2026, 10, 12), history_end=date(2026, 10, 25),
            history_instant=datetime(2026, 10, 22, 10, tzinfo=timezone.utc),
            call=Mock(), capture=Mock(), expect=Mock(), extra={})
        with patch.object(chart, "_select_history_bar"), patch.object(chart, "_drag_range",
                return_value={"start": "2026-10-14", "end": "2026-10-23"}):
            checks = chart.exercise_history(case)
        self.assertIn("bar-selects-exact-closing-native-table-row", checks)
        return case.extra["bar_table_selection"]

    def test_checked_native_history_row_keeps_exact_closing_identity(self):
        for state in ("Selected", ""):
            with self.subTest(state_description=state):
                evidence = self.exercise(state=state)
                self.assertEqual(evidence["native_resource"], "history-observation-10")
                self.assertEqual(evidence["native_selected"], "false")
                self.assertEqual(evidence["native_checked"], "true")
                self.assertEqual(evidence["native_checkable"], "true")
                self.assertEqual(evidence["visible_label"], self.CLOSE)
                self.assertEqual(evidence["exact_close"], "2026-10-22T18:00:00+00:00")

    def test_selected_native_history_encoding_is_still_supported(self):
        evidence = self.exercise(selected="true", checkable="false", checked="false")
        self.assertEqual(evidence["native_selected"], "true")
        self.assertEqual(evidence["native_checked"], "false")

    def test_label_alone_malformed_state_or_another_observation_cannot_pass(self):
        variants = (
            {"checkable": "false", "checked": "false"},
            {"checkable": "false", "checked": "true"},
            {"checkable": "true", "checked": "false"},
            {"selected": "true", "label": "Выбрано · 22.10.2026 13:00:00 · 101.25 ₽"},
            {"label": "Выбрано · 22.10.2026 21:00:00 · 101.25 ₽"},
            {"label": "Выбрано · 21.10.2026 21:00:00 · 901.75 ₽"},
            {"sibling_label": True},
        )
        for variant in variants:
            with self.subTest(variant=variant), self.assertRaisesRegex(
                    AssertionError, "Selecting the daily bar did not select its exact closing observation"):
                self.exercise(**variant)



class QuotePreviousReached(Exception):
    pass


class QuoteReflowProbe:
    """Reset removes selected details; Previous remains before Reset in the list."""

    def __init__(self, scale):
        self.scale, self.height, self.offset = scale, 236, 0
        self.selection = None
        self.actions, self.movements = [], []

    def rows(self):
        import portfolio_chart_probe as chart
        rows = [(0, "% номинала · 2026-09-26 — 2026-10-26")]
        if self.selection == "first":
            rows += [(100, "98.125000001 / 98.375000001 % номинала"),
                     (200, "97.625000001 / 99.125000001 % номинала"), (300, "100 лотов")]
        shift = 350 if self.selection == "first" else 0
        rows += [(400 + shift, "Предыдущая"), (480 + shift, "Сбросить"), (560 + shift, "Следующая")]
        return rows

    def tree(self):
        common = {"package": PACKAGE, "visible-to-user": "true", "enabled": "true"}
        root = ET.Element("hierarchy", {"display-width": "320", "display-height": "640", "active-window-id": "52"})
        body = ET.SubElement(root, "node", {**common, "resource-id": "workspace-content",
            "bounds": "[56,272][320,508]", "scrollable": "true"})
        for position, label in self.rows():
            top = max(0, position * self.scale - self.offset)
            bottom = min(self.height, (position + 64) * self.scale - self.offset)
            if top < bottom:
                ET.SubElement(body, "node", {**common, "text": label,
                    "bounds": f"[76,{272 + top}][300,{272 + bottom}]",
                    "class": "android.widget.Button", "clickable": "true"})
        return root

    def scroll(self, _x1, y1, _x2, y2):
        before = self.offset
        self.offset = max(0, min(1600 * self.scale - self.height, before + y1 - y2))
        self.movements.append((before, self.offset))

    def tap(self, text, area, direction="end"):
        from native_label_target import settled_label
        from profile_scroll import reveal_in_list
        if text == "Котировки" and area == "profile-tabs":
            return
        reveal_in_list(self.tree, self.scroll, text, resource_id=area, direction=direction, for_tap=True)
        target = settled_label(self.tree, text)
        self.actions.append(target.get("text"))
        if text == "Сбросить":
            self.selection = None
        elif text == "Следующая":
            self.selection = "first"
        elif text == "Предыдущая":
            self.selection = "last"
        else:
            raise AssertionError("Unexpected quote action")

    def reveal(self, text, area, direction="end"):
        from profile_scroll import reveal_in_list
        if text == "Текущий интервал ещё формируется" and self.selection == "last":
            raise QuotePreviousReached()
        return reveal_in_list(self.tree, self.scroll, text, resource_id=area, direction=direction)


class QuoteReflowTraversalTests(unittest.TestCase):
    def test_previous_reached_after_reset_removes_selected_details(self):
        from unittest.mock import Mock, patch
        import portfolio_chart_probe as chart
        for scale in (1, 2):
            with self.subTest(conditional_scale=scale):
                probe = QuoteReflowProbe(scale)
                case = SimpleNamespace(probe=probe, day=date(2026, 10, 26), call=Mock(), capture=Mock())
                with patch("native_label_target.time.sleep"):
                    with self.assertRaises(QuotePreviousReached):
                        chart.exercise_quotes(case)
                self.assertEqual(probe.actions, ["Сбросить", "Следующая", "Сбросить", "Предыдущая"])
                self.assertEqual(probe.selection, "last")
                case.capture.assert_called_once_with("exact-ohlc")
                case.call.assert_called_once_with("/workspace/instruments/synthetic-bond/candles",
                    {"start": "2026-09-26", "end": "2026-10-26", "interval": "day"}, status=200, after=0)


class HistoryTooltipProbe:
    """A clipped semantic parent remains visible above the chart's tap target."""

    def __init__(self, scale, *, unrelated_value=False):
        self.scale = scale
        self.height = 333 if scale == 1 else 157
        self.top = 198 if scale == 1 else 329
        self.offset = 150 * scale - 8
        self.unrelated_value = unrelated_value
        self.commands, self.movements = [], []

    def tree(self):
        common = {"package": PACKAGE, "enabled": "true", "visible-to-user": "true"}
        tree = ET.Element("hierarchy", {"display-width": "320", "display-height": "640", "active-window-id": "53"})
        body = ET.SubElement(tree, "node", {**common, "resource-id": "workspace-content",
            "bounds": f"[0,{self.top}][320,{self.top + self.height}]", "scrollable": "true"})

        def node(parent, begin, end, **attrs):
            first, last = max(0, begin - self.offset), min(self.height, end - self.offset)
            if first >= last:
                return None
            return ET.SubElement(parent, "node", {**common, **attrs,
                "bounds": f"[34,{self.top + first}][286,{self.top + last}]"})

        tooltip = node(body, 100 * self.scale, 150 * self.scale,
            **{"content-desc": "Выбранный интервал: 2026-10-22 — 2026-10-22"})
        if tooltip is not None:
            node(tooltip, 123 * self.scale, 142 * self.scale,
                text="101,25 ₽" if self.unrelated_value else "901,75 ₽")
        if self.unrelated_value:
            node(body, 20, 60, text="901,75 ₽")
        node(body, 162 * self.scale, 162 * self.scale + 188, **{"resource-id": "history-bars"})
        return tree

    def scroll(self, _x1, y1, _x2, y2):
        before = self.offset
        self.offset = max(0, min(2000, before + y1 - y2))
        self.movements.append((before, self.offset))

    def resource_tap_target(self, resource, area, direction="end"):
        from profile_scroll import tappable_resource
        target = tappable_resource(self.tree(), resource, area)
        if target is None:
            raise AssertionError("The starting chart is not actually tappable")
        return target

    def command(self, *args):
        if args[:3] != ("shell", "input", "tap"):
            raise AssertionError("Only the actual chart tap belongs to this fixture")
        self.commands.append(args)

    def reveal(self, text, area, direction="end"):
        from profile_scroll import reveal_in_list
        return reveal_in_list(self.tree, self.scroll, text, resource_id=area, direction=direction)


class HistoryTooltipTraversalTests(unittest.TestCase):
    def test_clipped_selected_tooltip_reveals_value_above_chart(self):
        import portfolio_chart_probe as chart
        for scale in (1, 2):
            with self.subTest(conditional_scale=scale):
                probe = HistoryTooltipProbe(scale)
                case = SimpleNamespace(probe=probe, history_start=date(2026, 10, 12))
                chart._select_history_bar(case, 10, "901,75 ₽")
                self.assertEqual(len(probe.commands), 1)
                self.assertEqual(probe.commands[0][3], "223")
                self.assertTrue(probe.movements)
                self.assertTrue(all(after < before for before, after in probe.movements))

    def test_another_visible_value_cannot_replace_selected_interval_value(self):
        import portfolio_chart_probe as chart
        for scale in (1, 2):
            with self.subTest(conditional_scale=scale):
                probe = HistoryTooltipProbe(scale, unrelated_value=True)
                case = SimpleNamespace(probe=probe, history_start=date(2026, 10, 12))
                with self.assertRaisesRegex(AssertionError, "selected history tooltip did not expose its exact interval value"):
                    chart._select_history_bar(case, 10, "901,75 ₽")



class SelectedQuoteIntervalProbe:
    """A native selected tab has no click action after the one actual tap."""

    def __init__(self, height, *, wrong_state=None):
        self.height, self.wrong_state = height, wrong_state
        self.taps = []
        self.read_tree = self.tree
        self.selected = False

    def tree(self):
        root = ET.Element("hierarchy", {"display-width": "320", "display-height": "640",
                                       "active-window-id": "31"})
        common = {"package": PACKAGE, "visible-to-user": "true", "enabled": "true"}
        rail = ET.SubElement(root, "node", {**common, "resource-id": "quotes-intervals",
            "bounds": f"[38,319][282,{319 + self.height}]"})
        attrs = {**common, "resource-id": "quotes-intervals-item-2",
            "bounds": f"[137,319][210,{319 + self.height}]",
            "clickable": str(not self.selected).lower(), "selected": str(self.selected).lower()}
        if self.selected and self.wrong_state:
            attrs.update(self.wrong_state)
        tab = ET.SubElement(rail, "node", attrs)
        ET.SubElement(tab, "node", {**common, "text": "Неделя",
            "bounds": f"[145,336][202,{min(355, 319 + self.height)}]"})
        return root

    @staticmethod
    def resource_tap_target(resource, area, direction="end"):
        if (resource, area, direction) != ("quotes-intervals", "workspace-content", "start"):
            raise AssertionError("Wrong candle rail")
        return ET.Element("node")

    def tap_node(self, node):
        if node.get("clickable") != "true" or node.get("selected") == "true":
            raise AssertionError("A state observation must not be tapped")
        self.taps.append(dict(node.attrib))
        self.selected = True

    @staticmethod
    def wait_for(read, message):
        for _ in range(4):
            value = read()
            if value is not None and value is not False:
                return value
        raise AssertionError(message)

    @staticmethod
    def scroll_list(*_args):
        raise AssertionError("This exact native candle action is already visible")


class QuoteIntervalStateTests(unittest.TestCase):
    def test_selected_nonclickable_interval_is_observed_after_exactly_one_tap(self):
        import portfolio_chart_probe as chart
        for height in (52, 57):
            with self.subTest(rail_height=height):
                probe = SelectedQuoteIntervalProbe(height)
                chart._tap_interval(SimpleNamespace(probe=probe), "Неделя")
                self.assertEqual(len(probe.taps), 1)
                self.assertEqual(probe.taps[0]["resource-id"], "quotes-intervals-item-2")
                self.assertIsNone(chart.quote_interval_target(probe.tree(), "Неделя"))
                selected = chart.quote_interval_target(probe.tree(), "Неделя", selected=True)
                self.assertEqual(selected.get("selected"), "true")
                self.assertEqual(selected.get("clickable"), "false")

    def test_missing_wrong_or_disabled_selection_never_causes_another_tap(self):
        import portfolio_chart_probe as chart
        variants = ({"selected": "false"},
                    {"selected": "false", "checkable": "true", "checked": "true"},
                    {"selected": "true", "enabled": "false"},
                    {"selected": "true", "visible-to-user": "false"},
                    {"selected": "true", "package": "another.app"})
        for attrs in variants:
            with self.subTest(native_state=attrs):
                probe = SelectedQuoteIntervalProbe(52, wrong_state=attrs)
                with self.assertRaisesRegex(AssertionError, "Candle interval did not acquire its actual native selected state"):
                    chart._tap_interval(SimpleNamespace(probe=probe), "Неделя")
                self.assertEqual(len(probe.taps), 1)


class MovingQuoteIntervalProbe:
    """Conditional scroll completion: an early physical tap stops the motion.

    The final rectangles use the observed Hour rail. Intermediate frames model
    asynchronous accessibility scrolling; they are not claimed device samples.
    """

    def __init__(self, height, *, changing=None, wrong_selection=False):
        self.height, self.width = height, 48 if height == 52 else 58
        self.changing, self.wrong_selection = changing, wrong_selection
        self.scrolls, self.frames, self.stable = [], 0, 0
        self.previous, self.selected = None, False
        self.taps, self.accepted = [], 0
        self.read_tree = self.tree

    def tree(self):
        if self.scrolls:
            self.frames += 1
            left = (30, 34, 38)[min(self.frames - 1, 2)] if self.width > 48 else 38
            if self.changing == "bounds":
                left = 38 + self.frames % 2
        else:
            left = 70 - self.width  # Only 32px is visible before the real scroll.
        window = 31 + self.frames % 2 if self.changing == "window" else 31
        rail_left = 38 + self.frames % 2 if self.changing == "rail" else 38
        resource = "quotes-intervals-item-1" if self.changing == "item" else "quotes-intervals-item-0"
        signature = (left, window, rail_left, resource)
        self.stable = self.stable + 1 if self.scrolls and signature == self.previous else 1
        self.previous = signature
        root = ET.Element("hierarchy", {"display-width": "320", "display-height": "640",
                                       "active-window-id": str(window)})
        common = {"package": PACKAGE, "visible-to-user": "true", "enabled": "true"}
        rail = ET.SubElement(root, "node", {**common, "resource-id": "quotes-intervals",
            "bounds": f"[{rail_left},319][282,{319 + self.height}]"})
        chosen = self.selected and not self.wrong_selection
        hour = ET.SubElement(rail, "node", {**common, "resource-id": resource,
            "bounds": f"[{left},319][{left + self.width},{319 + self.height}]",
            "clickable": str(not chosen).lower(), "selected": str(chosen).lower()})
        ET.SubElement(hour, "node", {**common, "text": "Час",
            "bounds": f"[{left + 8},336][{left + self.width - 8},355]"})
        month = ET.SubElement(rail, "node", {**common, "resource-id": "quotes-intervals-item-3",
            "bounds": f"[232,319][282,{319 + self.height}]",
            "clickable": str(chosen).lower(), "selected": str(not chosen).lower()})
        ET.SubElement(month, "node", {**common, "text": "Месяц", "bounds": "[240,336][282,355]"})
        return root

    resource_tap_target = staticmethod(SelectedQuoteIntervalProbe.resource_tap_target)
    wait_for = staticmethod(SelectedQuoteIntervalProbe.wait_for)

    def scroll_list(self, resource, direction):
        if (resource, direction) != ("quotes-intervals", "start") or self.scrolls:
            raise AssertionError("Only the one necessary backward candle scroll is permitted")
        self.scrolls.append((resource, direction))
        return True

    def tap_node(self, target):
        if target.get("resource-id") != "quotes-intervals-item-0" or target.get("clickable") != "true":
            raise AssertionError("The action must be the exact clickable Hour item")
        self.taps.append(dict(target.attrib))
        if self.stable >= 3:
            self.accepted += 1
            self.selected = True


class QuoteIntervalMotionTests(unittest.TestCase):
    def test_backward_scroll_settles_before_the_single_hour_tap(self):
        import portfolio_chart_probe as chart
        from unittest.mock import patch
        for height in (52, 57):
            with self.subTest(height=height), patch.object(chart.time, "sleep"):
                probe = MovingQuoteIntervalProbe(height)
                chart._tap_interval(SimpleNamespace(probe=probe), "Час", direction="start")
                self.assertEqual(probe.scrolls, [("quotes-intervals", "start")])
                self.assertEqual((len(probe.taps), probe.accepted), (1, 1))
                self.assertEqual(probe.taps[0]["bounds"], f"[38,319][{38 + probe.width},{319 + height}]")
                selected = chart.quote_interval_target(probe.tree(), "Час", selected=True)
                self.assertEqual(selected.get("resource-id"), "quotes-intervals-item-0")
                self.assertEqual(selected.get("clickable"), "false")

    def test_unsettled_window_rail_item_or_bounds_never_receive_a_tap(self):
        import portfolio_chart_probe as chart
        from unittest.mock import patch
        for changing in ("bounds", "window", "rail", "item"):
            with self.subTest(changing=changing), patch.object(chart.time, "sleep"):
                probe = MovingQuoteIntervalProbe(57, changing=changing)
                with self.assertRaisesRegex(AssertionError, "Candle interval action did not settle"):
                    chart._tap_interval(SimpleNamespace(probe=probe), "Час", direction="start")
                self.assertEqual(probe.taps, [])
                self.assertLessEqual(probe.frames, 21)

    def test_settled_action_with_another_selected_interval_is_a_failure_without_retap(self):
        import portfolio_chart_probe as chart
        from unittest.mock import patch
        with patch.object(chart.time, "sleep"):
            probe = MovingQuoteIntervalProbe(52, wrong_selection=True)
            with self.assertRaisesRegex(AssertionError, "Candle interval did not acquire its actual native selected state"):
                chart._tap_interval(SimpleNamespace(probe=probe), "Час", direction="start")
        self.assertEqual((len(probe.taps), probe.accepted), (1, 1))
        self.assertIsNone(chart.quote_interval_target(probe.tree(), "Час", selected=True))
        self.assertIsNotNone(chart.quote_interval_target(probe.tree(), "Месяц", selected=True))


if __name__ == "__main__":
    unittest.main()
