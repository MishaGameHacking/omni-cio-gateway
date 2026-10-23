"""Exercise real scenario controls against the disclosed debug transport."""
from __future__ import annotations

import math
import re
import time

from native_input_evidence import (active_window_id, append_native_text, record_editor_restore_trace,
                                   rotate_dismissed_draft, rotate_focused_draft)
from native_window_evidence import wait_for_new_app_window
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
    append_native_text(probe, "", value)


def exercise_scenario_comparison(case):
    probe = case.probe
    probe.tap("Концентрация", "profile-tabs", direction="start")
    # Android hides the underlying Activity's accessibility nodes while a
    # modal dialog is open. Observe transport only while that marker is visible.
    before = case.observed()
    original_window = active_window_id(probe.tree())
    probe.tap("Рассчитать свой сценарий", AREA, direction="start")
    wait_for_new_app_window(probe, original_window, "Сравнение ваших сценариев", AREA)
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
    # Collect after the complete visible rotation and its portrait restoration.
    record_editor_restore_trace(probe, include_ime_history=True)
    hidden_rotation = rotate_dismissed_draft(probe, "5", "business-risk-hidden-ime-rotation" + suffix, dialog=True)
    probe.tap(COMPARE, AREA)
    for scenario_id, change, after in (("A", "-10000", "90000"), ("B", "5000", "105000")):
        _record_value(probe, case.reader, scenario_id, "Исходный капитал: 100000 RUB")
        _record_value(probe, case.reader, scenario_id, "Изменение оценённых позиций: " + change + " RUB")
        _record_value(probe, case.reader, scenario_id, "После сценария: " + after + " RUB")
        _record_value(probe, case.reader, scenario_id, "Изменение применено к 3 из 3 позиций")
    picture = "business-risk-scenarios" + suffix
    probe.capture(picture)
    probe.tap("Закрыть", AREA)
    after = case.observed()
    if (after["requests"] <= before["requests"] or
            after["scenario_comparisons"] != before["scenario_comparisons"] + 1):
        raise AssertionError("Scenario comparison did not send exactly one actual comparison request")
    return {"same_baseline": "100000 RUB", "assumptions_percent": {"A": "-10", "B": "5"},
            "estimated_after": {"A": "90000 RUB", "B": "105000 RUB"},
            "comparison_requests": after["scenario_comparisons"] - before["scenario_comparisons"],
            "native_draft_rotation": rotation, "native_hidden_draft_rotation": hidden_rotation,
            "screenshot": picture + ".png",
            "fixture": "synthetic-no-broker-or-model-call"}
