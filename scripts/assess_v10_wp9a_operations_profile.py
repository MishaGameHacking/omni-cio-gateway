from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "docs" / "architecture" / "V10_WP9A_OPERATIONS_CONTRACT.json"
WP5_PATH = ROOT / "infrastructure" / "windows" / "wp5_node_thresholds.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def assess(profile: dict, policy: dict, wp5: dict) -> dict:
    blockers: list[str] = []
    warnings: list[str] = []

    if profile.get("schema_version") != "1" or profile.get("work_package") != "WP9A":
        blockers.append("PROFILE_IDENTITY_INVALID")

    privacy = profile.get("privacy", {})
    if not privacy or any(bool(value) for value in privacy.values()):
        blockers.append("PRIVACY_BOUNDARY_VIOLATION")

    update = profile.get("windows_update", {})
    if not update.get("service_present") or update.get("service_disabled"):
        blockers.append("WINDOWS_UPDATE_SERVICE_UNSAFE")
    if update.get("pending_reboot"):
        blockers.append("PENDING_REBOOT")

    time = profile.get("time", {})
    offset = time.get("offset_ms")
    if not time.get("service_running"):
        blockers.append("WINDOWS_TIME_NOT_RUNNING")
    if offset is None:
        blockers.append("TIME_OFFSET_UNKNOWN")
    else:
        absolute = abs(float(offset))
        if absolute > float(wp5["clock"]["block_sensitive_absolute_offset_ms"]):
            blockers.append("TIME_DRIFT_BLOCK")
        elif absolute > float(wp5["clock"]["warn_absolute_offset_ms"]):
            warnings.append("TIME_DRIFT_WARNING")

    runner = profile.get("runner", {})
    if not runner.get("service_present") or not runner.get("service_running"):
        blockers.append("RUNNER_SERVICE_UNHEALTHY")
    if runner.get("disable_update") is True:
        blockers.append("RUNNER_AUTOUPDATE_DISABLED")
    if runner.get("disable_update") is None:
        blockers.append("RUNNER_UPDATE_MODE_UNKNOWN")
    if not runner.get("version_known"):
        blockers.append("RUNNER_VERSION_UNKNOWN")
    if not runner.get("update_diagnostics_present"):
        warnings.append("RUNNER_SELFUPDATE_LOG_NOT_PRESENT")

    postgres = profile.get("postgresql", {})
    if not postgres.get("present") or not postgres.get("version_known"):
        blockers.append("POSTGRES_VERSION_UNKNOWN")
    elif int(postgres.get("major", 0)) != int(policy["postgresql"]["accepted_major"]):
        blockers.append("POSTGRES_MAJOR_MISMATCH")
    if not postgres.get("ready"):
        blockers.append("POSTGRES_NOT_READY")

    nvidia = profile.get("nvidia", {})
    if not nvidia.get("present") or not nvidia.get("driver_version_known"):
        blockers.append("NVIDIA_DRIVER_UNKNOWN")
    gpu_temp = nvidia.get("temperature_c")
    if gpu_temp is not None:
        if float(gpu_temp) > float(wp5["thermal"]["gpu_abort_load_test_c"]):
            blockers.append("GPU_TEMPERATURE_BLOCK")
        elif float(gpu_temp) > float(wp5["thermal"]["gpu_warn_c"]):
            warnings.append("GPU_TEMPERATURE_WARNING")

    ollama = profile.get("ollama", {})
    if ollama.get("present"):
        blockers.append("OLLAMA_PREMATURELY_INSTALLED")
    if not ollama.get("not_ready_allowed"):
        blockers.append("OLLAMA_NOT_READY_SEMANTICS_INVALID")

    resources = profile.get("resources", {})
    disk_gib = resources.get("system_disk_free_gib")
    disk_pct = resources.get("system_disk_free_percent")
    if disk_gib is None or disk_pct is None:
        blockers.append("DISK_FREE_STATE_UNKNOWN")
    else:
        if (
            float(disk_gib) < float(wp5["storage"]["block_free_gib"])
            or float(disk_pct) < float(wp5["storage"]["block_free_percent"])
        ):
            blockers.append("DISK_FREE_BLOCK")
        elif (
            float(disk_gib) < float(wp5["storage"]["warn_free_gib"])
            or float(disk_pct) < float(wp5["storage"]["warn_free_percent"])
        ):
            warnings.append("DISK_FREE_WARNING")

    memory = resources.get("memory_used_percent")
    if memory is None:
        blockers.append("MEMORY_STATE_UNKNOWN")
    elif float(memory) >= float(wp5["memory"]["block_new_heavy_work_percent"]):
        blockers.append("MEMORY_HEAVY_WORK_BLOCK")
    elif float(memory) >= float(wp5["memory"]["warn_used_percent"]):
        warnings.append("MEMORY_WARNING")

    wp9 = profile.get("wp9", {})
    if not wp9.get("present"):
        blockers.append("WP9_HEALTH_EVIDENCE_MISSING")
    if wp9.get("status") not in {"HEALTHY", "DEGRADED"}:
        blockers.append("WP9_HEALTH_STATUS_INVALID")
    if not wp9.get("fresh"):
        blockers.append("WP9_HEALTH_EVIDENCE_STALE")

    blockers = sorted(set(blockers))
    warnings = sorted(set(warnings))
    sensitive_ready = not any(
        item
        in {
            "WINDOWS_TIME_NOT_RUNNING",
            "TIME_OFFSET_UNKNOWN",
            "TIME_DRIFT_BLOCK",
            "PENDING_REBOOT",
        }
        for item in blockers
    )
    return {
        "schema_version": "1",
        "work_package": "WP9A",
        "status": "PASS" if not blockers else "FAIL",
        "blockers": blockers,
        "warnings": warnings,
        "sensitive_operations_ready": sensitive_ready,
        "real_money_authority_changed": False,
        "trading_methods": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", type=Path)
    args = parser.parse_args()
    result = assess(_load(args.profile), _load(POLICY_PATH), _load(WP5_PATH))
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
