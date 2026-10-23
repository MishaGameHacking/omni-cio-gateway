"""Hostile frame guards; the actual scenario flow runs separately on Android."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from risk_scenario_probe import PACKAGE, scenario_record_labels
import risk_scenario_probe as risk


def frame(record="A", package=PACKAGE, visible="true"):
    root = ET.Element("hierarchy")
    card = ET.SubElement(root, "node", {"resource-id": "scenario-result-" + record,
                                     "package": package, "visible-to-user": visible})
    ET.SubElement(card, "node", {"package": package, "visible-to-user": visible,
                                "text": "Изменение: −10\u00a0000 RUB"})
    return root


class RiskScenarioRecordTests(unittest.TestCase):
    def test_actual_values_are_bound_to_the_specific_visible_app_record(self):
        self.assertIn("Изменение:-10000RUB", scenario_record_labels(frame(), "A"))
        for tree in (frame("B"), frame(package="other.app"), frame(visible="false")):
            self.assertEqual(set(), scenario_record_labels(tree, "A"))

    def test_ambiguous_record_is_rejected_and_foreign_child_cannot_supply_a_value(self):
        root = frame()
        root.append(ET.fromstring(ET.tostring(root[0])))
        with self.assertRaises(AssertionError):
            scenario_record_labels(root, "A")
        root = frame()
        root[0][0].set("package", "other.app")
        self.assertNotIn("Изменение:-10000RUB", scenario_record_labels(root, "A"))


def scenario_case(font_scale=1.0):
    events = []
    probe = Mock()
    probe.tree.return_value = ET.Element("hierarchy", {"active-window-id": "156"})
    probe.tap.side_effect = lambda text, *_args, **_kwargs: events.append(("tap", text))
    probe.dismiss_keyboard.side_effect = lambda: events.append(("dismiss",))
    probe.wait_for.return_value = ET.Element("node", {"enabled": "false"})
    case = SimpleNamespace(probe=probe, reader=Mock(), font_scale=font_scale,
                           observed=Mock(side_effect=[{"requests": 10, "scenario_comparisons": 2},
                                                      {"requests": 11, "scenario_comparisons": 3}]))
    return case, events


class RiskScenarioRotationOrderTests(unittest.TestCase):
    def test_original_a_hide_b_open_visible_rotation_precedes_trace_and_hidden_cycle(self):
        for scale, suffix in ((1.0, ""), (2.0, "-font-200")):
            case, events = scenario_case(scale)

            def visible(_probe, text, name, *, dialog):
                events.append(("visible-rotation", text, name, dialog))
                return {"original": True}

            def hidden(_probe, text, name, *, dialog):
                events.append(("hidden-rotation", text, name, dialog))
                return {"hidden": True}

            with self.subTest(scale=scale), \
                    patch.object(risk, "_enter_percent", side_effect=lambda _probe, text: events.append(("input", text))), \
                    patch.object(risk, "rotate_focused_draft", side_effect=visible), \
                    patch.object(risk, "record_editor_restore_trace", side_effect=lambda _probe, **flags: events.append(("trace", flags))), \
                    patch.object(risk, "rotate_dismissed_draft", side_effect=hidden), \
                    patch.object(risk, "_record_value"):
                result = risk.exercise_scenario_comparison(case)
            self.assertEqual(events[:10], [
                ("tap", "Концентрация"), ("tap", "Рассчитать свой сценарий"), ("input", "-10"),
                ("dismiss",), ("tap", "Сценарий B"), ("input", "5"),
                ("visible-rotation", "5", "business-risk-scenario-rotation" + suffix, True),
                ("trace", {"include_ime_history": True}),
                ("hidden-rotation", "5", "business-risk-hidden-ime-rotation" + suffix, True),
                ("tap", risk.COMPARE),
            ])
            case.probe.dismiss_keyboard.assert_called_once_with()
            self.assertEqual(result["native_draft_rotation"], {"original": True})
            self.assertEqual(result["native_hidden_draft_rotation"], {"hidden": True})
            self.assertEqual(result["comparison_requests"], 1)

    def test_original_visible_failure_prevents_trace_hidden_cycle_and_comparison(self):
        case, events = scenario_case()
        failure = AssertionError("original visible rotation failed")
        with patch.object(risk, "_enter_percent"), \
                patch.object(risk, "rotate_focused_draft", side_effect=failure), \
                patch.object(risk, "record_editor_restore_trace") as trace, \
                patch.object(risk, "rotate_dismissed_draft") as hidden, \
                self.assertRaises(AssertionError) as caught:
            risk.exercise_scenario_comparison(case)
        self.assertIs(caught.exception, failure)
        trace.assert_not_called()
        hidden.assert_not_called()
        self.assertNotIn(("tap", risk.COMPARE), events)

    def test_hidden_failure_prevents_comparison_after_successful_visible_cycle(self):
        case, events = scenario_case()
        failure = AssertionError("keyboard reopened during hidden rotation")
        with patch.object(risk, "_enter_percent"), \
                patch.object(risk, "rotate_focused_draft", return_value={"original": True}), \
                patch.object(risk, "record_editor_restore_trace") as trace, \
                patch.object(risk, "rotate_dismissed_draft", side_effect=failure), \
                self.assertRaises(AssertionError) as caught:
            risk.exercise_scenario_comparison(case)
        self.assertIs(caught.exception, failure)
        trace.assert_called_once_with(case.probe, include_ime_history=True)
        self.assertNotIn(("tap", risk.COMPARE), events)


if __name__ == "__main__":
    unittest.main()
