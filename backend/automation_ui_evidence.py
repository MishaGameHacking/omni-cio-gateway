"""Validate bounded operator-supplied native UI observations, not device attestation."""
from __future__ import annotations

import math
import re

try:
    from .android_runtime_contract import AUTOMATION_CASE_IDS
except ImportError:
    from android_runtime_contract import AUTOMATION_CASE_IDS

ACTIVITY = "ru.omnicio.app.debug/ru.omnicio.app.ProfileUiProbeActivity"
TRACE_COUNTS = ("requests", "writes", "applied", "rejected", "contract-errors", "version")


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError("automation_ui_" + reason)


def _digest(value: object) -> str:
    _require(isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) is not None, "digest_invalid")
    return value


def _integer(value: object, lower: int = 0, upper: int = 10**12) -> bool:
    return type(value) is int and lower <= value <= upper


def screenshot_name(case_id: str) -> str:
    _require(isinstance(case_id, str) and case_id in AUTOMATION_CASE_IDS, "case_unknown")
    route_scenario, font = case_id.rsplit("@", 1)
    return "automation-" + route_scenario.replace("/", "-").replace("_", "-") + \
        ("-font-200" if font == "2" else "") + ".png"


def _identity(row: dict) -> str:
    font, case = row.get("font_scale"), row.get("case")
    _require(type(font) in (int, float) and font in (1, 2) and isinstance(case, str), "case_invalid")
    identity = case + "@" + str(int(font))
    _require(identity in AUTOMATION_CASE_IDS, "case_unknown")
    return identity


def _trace(raw: object) -> dict:
    _require(isinstance(raw, dict) and set(raw) == {*TRACE_COUNTS, "enabled", "page"}, "trace_missing")
    _require(all(_integer(raw[name]) for name in TRACE_COUNTS), "counter_invalid")
    _require(raw["requests"] >= 1 and raw["version"] >= 1 and raw["contract-errors"] == 0, "trace_invalid")
    _require(raw["applied"] + raw["rejected"] <= raw["writes"] < raw["requests"], "trace_inconsistent")
    _require(type(raw["enabled"]) is bool and raw["page"] in ("home", "settings", "decisions"), "state_invalid")
    return raw


def _transition(row: dict) -> tuple[str, str]:
    route, scenario = row["case"].split("/", 1)
    before, after = _trace(row.get("before")), _trace(row.get("after"))
    initial_enabled = scenario != "paused"
    _require(before["page"] == route and before["enabled"] is initial_enabled and before["version"] == 1,
             "initial_state_invalid")
    _require(all(before[key] == 0 for key in ("writes", "applied", "rejected")), "preexisting_mutation")
    mutation = route == "settings" and scenario != "error"
    applied = mutation and scenario != "conflict"
    expected = {"writes": int(mutation), "applied": int(applied), "rejected": int(scenario == "conflict"),
                "version": 1 + int(mutation), "enabled": not initial_enabled if applied else initial_enabled,
                "page": route}
    _require(all(type(after[key]) is type(value) and after[key] == value for key, value in expected.items()),
             "acknowledgement_invalid")
    additional_reads = 3 if route == "home" and scenario == "ready" else 2 if mutation else 0
    _require(after["requests"] >= before["requests"] + additional_reads, "request_journey_incomplete")
    return route, scenario


def _renderer(raw: object, font: float) -> None:
    _require(isinstance(raw, dict) and raw.get("renderer") == "native-2d" and raw.get("error") == "none",
             "renderer_missing")
    _require(_integer(raw.get("draw-operations"), 1), "native_draw_missing")
    _require(all(type(raw.get(key)) is int and raw[key] == 0
                 for key in ("engines", "windows", "frames", "meshes", "pending", "pool")), "legacy_renderer_present")
    observed, density = raw.get("font-scale"), raw.get("density")
    _require(type(observed) in (int, float) and math.isfinite(observed)
             and math.isclose(observed, font, rel_tol=0, abs_tol=1e-6), "font_scale_unverified")
    _require(type(density) in (int, float) and math.isfinite(density) and 0 < density <= 10,
             "density_unverified")
    _require(raw.get("orientation") == "1", "orientation_unverified")


def _foreground_lines(raw: object) -> None:
    _require(isinstance(raw, list) and 1 <= len(raw) <= 8
             and all(isinstance(line, str) and len(line) <= 320 for line in raw), "foreground_missing")
    pattern = (r"^\s*(?:topResumedActivity|mResumedActivity)\s*[=:]\s*"
               r"ActivityRecord\{[^\s{}]+\s+u[0-9]+\s+([^\s{}]+)(?=[\s}])")
    matched = [match.group(1) for line in raw if (match := re.match(pattern, line)) is not None]
    _require(ACTIVITY in matched and all(component == ACTIVITY for component in matched),
             "foreground_wrong_activity")


def _capture_observations(row: dict) -> None:
    for name in ("foreground_before", "foreground_after"):
        observation = row.get(name)
        _require(isinstance(observation, dict) and set(observation) == {"before", "after"},
                 "foreground_observation_missing")
        _foreground_lines(observation["before"])
        _foreground_lines(observation["after"])
    process = row.get("process_id")
    _require(isinstance(process, str) and re.fullmatch(r"[1-9][0-9]{0,9}", process) is not None,
             "process_missing")
    _require(row.get("process_id_after") == process, "process_restarted")


def _switch(row: dict, route: str, scenario: str) -> None:
    _require("native_switch" in row, "switch_observation_missing")
    control = row["native_switch"]
    if route != "settings":
        _require(control is None, "unexpected_switch_observation")
        return
    _require(isinstance(control, dict) and set(control) == {"checkable", "checked", "enabled"}
             and all(type(value) is bool for value in control.values()), "native_switch_invalid")
    expected = {"checkable": True, "enabled": scenario != "error",
                "checked": scenario in ("paused", "conflict")}
    _require(control == expected, "native_switch_not_acknowledged")


def _case(row: object) -> str:
    expected = {"case", "font_scale", "before", "after", "renderer", "process_id", "process_id_after",
                "foreground_before", "foreground_after", "native_switch", "screenshot", "screenshot_sha256",
                "width", "height"}
    _require(isinstance(row, dict) and set(row) == expected, "case_missing")
    identity = _identity(row)
    route, scenario = _transition(row)
    _renderer(row.get("renderer"), row["font_scale"])
    _capture_observations(row)
    _switch(row, route, scenario)
    _require(row.get("screenshot") == screenshot_name(identity), "screenshot_name_invalid")
    _digest(row.get("screenshot_sha256"))
    width, height = row.get("width"), row.get("height")
    _require(_integer(width, 240, 4096) and _integer(height, 320, 4096)
             and width < height and width * height <= 12_000_000, "capture_dimensions_invalid")
    return identity


def validate_automation_report(raw: object, fixture_digest: str) -> int:
    expected = {"schema_version", "fixture", "actual_device_observations", "external_broker_model_calls",
                "real_order_execution", "fixture_apk_sha256", "cases"}
    _require(isinstance(raw, dict) and set(raw) == expected and type(raw.get("schema_version")) is int
             and raw["schema_version"] == 1, "report_schema_invalid")
    _require(raw.get("fixture") == "debug-only-synthetic-transport"
             and raw.get("actual_device_observations") is True
             and raw.get("external_broker_model_calls") is False
             and raw.get("real_order_execution") is False, "fixture_identity_invalid")
    _require(_digest(raw.get("fixture_apk_sha256")) == _digest(fixture_digest), "fixture_artifact_mismatch")
    rows = raw.get("cases")
    _require(isinstance(rows, list) and len(rows) == len(AUTOMATION_CASE_IDS), "matrix_incomplete")
    identities = [_case(row) for row in rows]
    _require(len(set(identities)) == len(identities) and set(identities) == AUTOMATION_CASE_IDS,
             "matrix_incomplete")
    return len(identities)
