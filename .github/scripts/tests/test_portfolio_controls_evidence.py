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


if __name__ == "__main__":
    unittest.main()
