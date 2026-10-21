"""Exercise real scenario controls against the disclosed debug transport."""
from __future__ import annotations

import math
import re
import time

from native_input_evidence import empty_editor_focused, focused_editor, rotate_focused_draft
from profile_ui_probe import button_label

AREA = "workspace-content"
PACKAGE = "ru.omnicio.app.debug"
COMPARE = "Сравнить сценарии"
PERCENT = "scenario-percent"


def scenario_record_labels(tree, scenario_id):
    resource = "scenario-result-" + scenario_id
    matches = [node for node in tree.iter("node")
               if node.get("package") == PACKAGE and node.get("visible-to-user") == "true"
               and node.get("resource-id") in {resource, PACKAGE + ":id/" + resource}]
    if len(matches) > 1:
        raise AssertionError("Scenario result identity is ambiguous")
    if not matches:
        return set()
    return {re.sub(r"\s+", "", node.get("text", "")).replace("−", "-")
            for node in matches[0].iter("node")
            if node.get("package") == PACKAGE and node.get("visible-to-user") == "true"}


def _record_value(probe, reader, scenario_id, value):
    resource = "scenario-result-" + scenario_id
    probe.reveal_resource(resource, AREA)
    expected = re.sub(r"\s+", "", value)
    for _ in range(24):
        if expected in scenario_record_labels(probe.tree(), scenario_id):
            return
        if not reader.scroll_list(AREA, "end"):
            break
        time.sleep(.15)
    raise AssertionError("Scenario " + scenario_id + " did not expose its exact value: " + value)


def _enter_percent(probe, value):
    probe.tap_resource(PERCENT, AREA)
    probe.wait_for(lambda: empty_editor_focused(probe.tree()), "Scenario editor did not gain native focus")
    probe.command("shell", "input", "text", value)
    probe.wait_for(lambda: focused_editor(probe.tree(), value), "Scenario percentage was not entered")


def exercise_scenario_comparison(case):
    probe = case.probe
    probe.tap("Концентрация", "profile-tabs", direction="start")
    probe.tap("Рассчитать свой сценарий", AREA, direction="start")
    probe.reveal(COMPARE, AREA)
    disabled = probe.wait_for(lambda: button_label(probe.tree(), COMPARE), "Missing native scenario action")
    if disabled.get("enabled") != "false":
        raise AssertionError("Empty scenario assumptions permit comparison")
    probe.reveal_resource(PERCENT, AREA, direction="start")
    _enter_percent(probe, "-10")
    probe.dismiss_keyboard()
    probe.tap("Сценарий B", AREA, direction="start")
    _enter_percent(probe, "5")
    suffix = "-font-200" if math.isclose(case.font_scale, 2.0) else ""
    rotation = rotate_focused_draft(probe, "5", "business-risk-scenario-rotation" + suffix, dialog=True)
    probe.dismiss_keyboard()
    before = case.observed()["requests"]
    probe.tap(COMPARE, AREA)
    probe.wait_for(lambda: case.observed()["requests"] > before, "Scenario comparison sent no request")
    for scenario_id, change, after in (("A", "-10000", "90000"), ("B", "5000", "105000")):
        _record_value(probe, case.reader, scenario_id, "Исходный капитал: 100000 RUB")
        _record_value(probe, case.reader, scenario_id, "Изменение оценённых позиций: " + change + " RUB")
        _record_value(probe, case.reader, scenario_id, "После сценария: " + after + " RUB")
        _record_value(probe, case.reader, scenario_id, "Изменение применено к 3 из 3 позиций")
    picture = "business-risk-scenarios" + suffix
    probe.capture(picture)
    probe.tap("Закрыть", AREA)
    return {"same_baseline": "100000 RUB", "assumptions_percent": {"A": "-10", "B": "5"},
            "estimated_after": {"A": "90000 RUB", "B": "105000 RUB"},
            "native_draft_rotation": rotation, "screenshot": picture + ".png",
            "fixture": "synthetic-no-broker-or-model-call"}
