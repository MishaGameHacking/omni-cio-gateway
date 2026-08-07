from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any


ALLOWED_TOP_LEVEL = {
    "schema_version",
    "attested_at_utc",
    "source_class",
    "recovery_key_custody_status",
    "battery_conservation",
    "restart_after_power_loss",
    "checks",
}
ALLOWED_CHECKS = {"reboot", "network_reconnect", "sustained_cpu_gpu_load"}
ALLOWED_LOAD_KEYS = {
    "tool",
    "tool_version",
    "duration_seconds",
    "cpu_peak_c",
    "cpu_throttling_max_percent",
    "cpu_throttling_average_percent",
    "gpu_load_started",
    "gpu_peak_c",
    "system_crash",
    "thermal_shutdown",
}


class EvidenceError(ValueError):
    pass


def _require_dict(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EvidenceError(f"{path} must be an object")
    return value


def _require_exact_keys(obj: dict[str, Any], allowed: set[str], path: str) -> None:
    missing = allowed - set(obj)
    unexpected = set(obj) - allowed
    if missing:
        raise EvidenceError(f"{path} missing keys: {sorted(missing)!r}")
    if unexpected:
        raise EvidenceError(f"{path} unexpected keys: {sorted(unexpected)!r}")


def _require_number(value: Any, path: str, minimum: float, maximum: float) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise EvidenceError(f"{path} must be numeric")
    result = float(value)
    if result < minimum or result > maximum:
        raise EvidenceError(f"{path} must be between {minimum} and {maximum}")
    return result


def validate_owner_evidence(evidence: dict[str, Any]) -> None:
    _require_exact_keys(evidence, ALLOWED_TOP_LEVEL, "$evidence")
    if evidence.get("schema_version") != "1":
        raise EvidenceError("$evidence.schema_version must equal '1'")
    if evidence.get("source_class") != "OWNER_UI_AND_PHYSICAL_TEST":
        raise EvidenceError("$evidence.source_class is not allowed")
    attested_at = evidence.get("attested_at_utc")
    if not isinstance(attested_at, str):
        raise EvidenceError("$evidence.attested_at_utc must be a date-time string")
    try:
        parsed = datetime.fromisoformat(attested_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EvidenceError("$evidence.attested_at_utc must be RFC3339") from exc
    if parsed.tzinfo is None:
        raise EvidenceError(
            "$evidence.attested_at_utc must include timezone information"
        )

    if evidence.get("recovery_key_custody_status") != "OWNER_CONFIRMED_SEPARATE":
        raise EvidenceError("recovery-key evidence may only confirm separate custody")
    if evidence.get("battery_conservation") not in {"ENABLED", "NOT_APPLICABLE"}:
        raise EvidenceError(
            "battery_conservation evidence must be ENABLED or NOT_APPLICABLE"
        )
    if evidence.get("restart_after_power_loss") not in {
        "ENABLED",
        "NOT_SUPPORTED_BY_FIRMWARE",
    }:
        raise EvidenceError(
            "restart_after_power_loss evidence must be ENABLED or NOT_SUPPORTED_BY_FIRMWARE"
        )

    checks = _require_dict(evidence.get("checks"), "$evidence.checks")
    _require_exact_keys(checks, ALLOWED_CHECKS, "$evidence.checks")
    if checks.get("reboot") != "PASS":
        raise EvidenceError("OWNER reboot evidence must be PASS")
    if checks.get("network_reconnect") != "PASS":
        raise EvidenceError("OWNER network reconnect evidence must be PASS")

    load = _require_dict(
        checks.get("sustained_cpu_gpu_load"),
        "$evidence.checks.sustained_cpu_gpu_load",
    )
    _require_exact_keys(
        load,
        ALLOWED_LOAD_KEYS,
        "$evidence.checks.sustained_cpu_gpu_load",
    )
    if load.get("tool") != "AIDA64_EXTREME":
        raise EvidenceError(
            "only AIDA64_EXTREME evidence is accepted for this WP5 record"
        )
    if not isinstance(load.get("tool_version"), str) or not load.get("tool_version"):
        raise EvidenceError("tool_version must be a non-empty string")
    _require_number(load.get("duration_seconds"), "duration_seconds", 1, 86400)
    _require_number(load.get("cpu_peak_c"), "cpu_peak_c", 0, 125)
    _require_number(
        load.get("cpu_throttling_max_percent"),
        "cpu_throttling_max_percent",
        0,
        100,
    )
    _require_number(
        load.get("cpu_throttling_average_percent"),
        "cpu_throttling_average_percent",
        0,
        100,
    )
    if load.get("gpu_load_started") is not True:
        raise EvidenceError("gpu_load_started must be true")
    gpu_peak = load.get("gpu_peak_c")
    if gpu_peak is not None:
        _require_number(gpu_peak, "gpu_peak_c", 0, 125)
    for key in ("system_crash", "thermal_shutdown"):
        if not isinstance(load.get(key), bool):
            raise EvidenceError(f"{key} must be boolean")


def assess_load_evidence(evidence: dict[str, Any], thresholds: dict[str, Any]) -> str:
    load = evidence["checks"]["sustained_cpu_gpu_load"]
    thermal = thresholds["thermal"]
    load_policy = thresholds["load_test"]

    minimum_seconds = float(load_policy["minimum_duration_minutes"]) * 60.0
    if float(load["duration_seconds"]) < minimum_seconds:
        return "FAIL"
    if load["system_crash"] or load["thermal_shutdown"]:
        return "FAIL"
    if float(load["cpu_peak_c"]) > float(thermal["cpu_core_abort_load_test_c"]):
        return "FAIL"
    if float(load["cpu_throttling_average_percent"]) > float(
        thermal["cpu_throttling_block_average_percent"]
    ):
        return "FAIL"
    gpu_peak = load.get("gpu_peak_c")
    if load_policy.get("combined_gpu_peak_required", True) and gpu_peak is None:
        return "FAIL"
    if gpu_peak is not None and float(gpu_peak) > float(
        thermal["gpu_abort_load_test_c"]
    ):
        return "FAIL"
    return "PASS"


def apply_owner_evidence(
    profile: dict[str, Any], evidence: dict[str, Any], thresholds: dict[str, Any]
) -> str:
    validate_owner_evidence(evidence)
    profile["capture_mode"] = "PASSIVE_PLUS_OWNER_EVIDENCE"
    profile["security"]["full_disk_encryption"]["recovery_key_custody_status"] = (
        evidence["recovery_key_custody_status"]
    )
    profile["power"]["battery_conservation"] = evidence["battery_conservation"]
    profile["power"]["restart_after_power_loss"] = evidence["restart_after_power_loss"]
    profile["checks"]["reboot"] = evidence["checks"]["reboot"]
    profile["checks"]["network_reconnect"] = evidence["checks"]["network_reconnect"]
    load_result = assess_load_evidence(evidence, thresholds)
    profile["checks"]["sustained_cpu_gpu_load"] = load_result
    return load_result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Apply sanitized OWNER physical evidence to a passive WP5 node profile"
    )
    parser.add_argument("profile")
    parser.add_argument("evidence")
    parser.add_argument("--thresholds", required=True)
    args = parser.parse_args(argv)

    try:
        profile_path = Path(args.profile)
        profile = json.loads(profile_path.read_text(encoding="utf-8-sig"))
        evidence = json.loads(Path(args.evidence).read_text(encoding="utf-8"))
        thresholds = json.loads(Path(args.thresholds).read_text(encoding="utf-8"))
        if (
            not isinstance(profile, dict)
            or not isinstance(evidence, dict)
            or not isinstance(thresholds, dict)
        ):
            raise EvidenceError("profile, evidence and thresholds must be JSON objects")
        load_result = apply_owner_evidence(profile, evidence, thresholds)
        profile_path.write_text(
            json.dumps(profile, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, json.JSONDecodeError, KeyError, TypeError, EvidenceError) as exc:
        print(f"WP5 OWNER evidence application failed: {exc}", file=sys.stderr)
        return 1

    print(f"WP5 OWNER evidence applied; sustained load result={load_result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
