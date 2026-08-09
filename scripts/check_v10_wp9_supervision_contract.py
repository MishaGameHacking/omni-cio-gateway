from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "docs" / "architecture" / "V10_WP9_SUPERVISION_CONTRACT.json"
EXECUTION_PATH = ROOT / "docs" / "architecture" / "V10_WP9_EXECUTION_CONTRACT.md"
PROVISIONER = ROOT / "infrastructure" / "windows" / "provision_wp9_supervision.ps1"
ROLLBACK = ROOT / "infrastructure" / "windows" / "rollback_wp9_supervision.ps1"
HEALTH = ROOT / "infrastructure" / "windows" / "wp9_health_supervisor.ps1"
GUARD = ROOT / "infrastructure" / "windows" / "wp9_component_guard.ps1"
WORKER = ROOT / "infrastructure" / "windows" / "wp9_rehearsal_worker.ps1"
COLLECTOR = ROOT / "scripts" / "collect_v10_wp9_supervision_profile.ps1"
ASSESSOR = ROOT / "scripts" / "assess_v10_wp9_supervision_profile.py"

EXPECTED_SLOT_IDS = {"core_api", "web", "telegram", "watchtower", "ai_worker"}
EXPECTED_TASKS = {
    "health_supervisor": "OmniCIO.V10.HealthSupervisor",
    "core_api": "OmniCIO.V10.CoreApi",
    "web": "OmniCIO.V10.Web",
    "telegram": "OmniCIO.V10.Telegram",
    "watchtower": "OmniCIO.V10.Watchtower",
    "ai_worker": "OmniCIO.V10.AIWorker",
}


def _load_contract(failures: list[str]) -> dict[str, Any] | None:
    try:
        data = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        failures.append(f"contract unreadable: {type(exc).__name__}")
        return None
    if not isinstance(data, dict):
        failures.append("contract root must be an object")
        return None
    return data


def _require_false(mapping: dict[str, Any], key: str, failures: list[str]) -> None:
    if mapping.get(key) is not False:
        failures.append(f"{key} must be false")


def _require_text(path: Path, needles: tuple[str, ...], failures: list[str]) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        failures.append(f"missing or unreadable: {path.relative_to(ROOT)}")
        return
    for needle in needles:
        if needle not in text:
            failures.append(f"{path.name} missing required guard: {needle}")


def validate_contract(data: dict[str, Any], failures: list[str]) -> None:
    if data.get("schema_version") != "1":
        failures.append("schema_version must be 1")
    if data.get("work_package") != "WP9":
        failures.append("work_package must be WP9")

    supervision = data.get("supervision")
    if not isinstance(supervision, dict):
        failures.append("supervision must be an object")
    else:
        expected = {
            "mechanism": "WINDOWS_TASK_SCHEDULER_PLUS_EXISTING_WINDOWS_SERVICES",
            "health_principal": r"NT AUTHORITY\LOCAL SERVICE",
            "health_logon_type": "ServiceAccount",
            "health_run_level": "Limited",
            "periodic_health_interval_minutes": 1440,
            "component_restart_count": 3,
            "component_restart_interval_seconds": 15,
            "component_execution_limit_minutes": 10,
            "multiple_instances": "IgnoreNew",
        }
        for key, value in expected.items():
            if supervision.get(key) != value:
                failures.append(f"supervision.{key} mismatch")
        for key in ("third_party_service_wrapper_allowed", "infinite_restart_loop_allowed"):
            _require_false(supervision, key, failures)
        if supervision.get("startup_trigger_required") is not True:
            failures.append("startup trigger must be required")
        if supervision.get("owner_admin_required_for_apply") is not True:
            failures.append("OWNER admin apply must be required")
        if supervision.get("preview_default") is not True:
            failures.append("preview must be default")

    paths = data.get("paths")
    if not isinstance(paths, dict):
        failures.append("paths must be an object")
    else:
        root = r"C:\ProgramData\OmniCIO\services\wp9"
        if paths.get("wp9_root") != root:
            failures.append("wp9 root mismatch")
        for key in (
            "deployed_root",
            "evidence_root",
            "status_file",
            "provision_state",
            "restart_rehearsal",
            "dependency_rehearsal",
            "reboot_rehearsal",
        ):
            value = paths.get(key)
            if not isinstance(value, str) or not value.startswith(root + "\\"):
                failures.append(f"paths.{key} must stay below WP9 root")

    if data.get("task_folder") != "\\OmniCIO\\V10\\":
        failures.append("task_folder mismatch")
    tasks = data.get("tasks")
    if not isinstance(tasks, dict) or tasks != EXPECTED_TASKS:
        failures.append("task map mismatch")
    if isinstance(tasks, dict) and any("Execution" in str(value) for value in tasks.values()):
        failures.append("WP9 may not define an execution task")

    components = data.get("components")
    if not isinstance(components, list):
        failures.append("components must be a list")
    else:
        by_id = {item.get("id"): item for item in components if isinstance(item, dict)}
        if set(by_id) != EXPECTED_SLOT_IDS | {"database", "health_supervisor"}:
            failures.append("component set mismatch")
        database = by_id.get("database", {})
        if database.get("service_name") != "postgresql-x64-18":
            failures.append("database service must remain PostgreSQL 18")
        if database.get("activation") != "EXISTING_REQUIRED":
            failures.append("database activation mismatch")
        health = by_id.get("health_supervisor", {})
        if health.get("activation") != "ACTIVE_WP9":
            failures.append("health supervisor must be the only WP9 active task")
        for slot_id in EXPECTED_SLOT_IDS:
            slot = by_id.get(slot_id, {})
            if slot.get("activation") != "SEALED_UNTIL_OWNING_WP":
                failures.append(f"later product slot must remain sealed: {slot_id}")
            if slot.get("expected_current_state") != "NOT_READY":
                failures.append(f"sealed slot must be NOT_READY: {slot_id}")
            if slot.get("guard_principal") != r"NT AUTHORITY\LOCAL SERVICE":
                failures.append(f"slot guard principal mismatch: {slot_id}")

    sealed = data.get("sealed_boundaries")
    if not isinstance(sealed, dict):
        failures.append("sealed_boundaries must be an object")
    else:
        for key in (
            "execution_task_created",
            "execution_role_enabled",
            "broker_write_enabled",
            "real_money_authority_changed",
            "wp8_payload_access_for_health_principal",
            "later_product_runtime_activation_allowed",
        ):
            _require_false(sealed, key, failures)

    restart = data.get("restart_rehearsal")
    if not isinstance(restart, dict):
        failures.append("restart_rehearsal must be an object")
    else:
        if set(restart.get("slots", [])) != EXPECTED_SLOT_IDS:
            failures.append("restart rehearsal must cover all five controlled slots")
        for key in (
            "uses_synthetic_non_product_workers",
            "kill_then_recover_required",
            "bounded_restart_required",
            "temporary_rehearsal_tasks_removed_after_test",
            "real_runtime_retest_required_in_owning_future_wp",
        ):
            if restart.get(key) is not True:
                failures.append(f"restart_rehearsal.{key} must be true")

    dependency = data.get("dependency_rehearsal")
    if not isinstance(dependency, dict):
        failures.append("dependency_rehearsal must be an object")
    else:
        if dependency.get("uses_synthetic_non_product_dependency") is not True:
            failures.append("dependency rehearsal must be synthetic")
        if dependency.get("dependent_blocked_when_dependency_down") is not True:
            failures.append("dependency loss must block dependent")
        if dependency.get("dependent_recovers_when_dependency_restored") is not True:
            failures.append("dependency restore must recover dependent")
        if dependency.get("production_database_stop_required") is not False:
            failures.append("WP9 rehearsal must not stop production PostgreSQL")

    reboot = data.get("reboot_rehearsal")
    if not isinstance(reboot, dict):
        failures.append("reboot_rehearsal must be an object")
    else:
        for key in (
            "owner_initiated_full_reboot_required",
            "self_hosted_runner_must_return_automatically",
            "health_status_must_be_written_after_new_boot",
            "stale_pre_reboot_status_may_not_pass",
        ):
            if reboot.get(key) is not True:
                failures.append(f"reboot_rehearsal.{key} must be true")
        if reboot.get("manual_application_terminal_launch_allowed") is not False:
            failures.append("manual application launch must be forbidden during reboot gate")

    privacy = data.get("privacy")
    if not isinstance(privacy, dict):
        failures.append("privacy must be an object")
    else:
        for key, value in privacy.items():
            if value is not False:
                failures.append(f"privacy.{key} must be false")

    exit_gate = data.get("exit_gate")
    if not isinstance(exit_gate, dict):
        failures.append("exit_gate must be an object")
    else:
        if exit_gate.get("app_entrypoint") != "app:app":
            failures.append("app:app must remain protected")
        if exit_gate.get("trading_methods") is not False:
            failures.append("trading_methods must remain false")
        if exit_gate.get("real_money_authority_unchanged") is not True:
            failures.append("Real-money authority must remain unchanged")


def validate_assets(failures: list[str]) -> None:
    _require_text(
        EXECUTION_PATH,
        (
            "WP9",
            "app:app",
            "trading_methods=false",
            "LocalService",
            "WP9A",
            "DEGRADED",
        ),
        failures,
    )
    _require_text(
        PROVISIONER,
        (
            "WP9_APPLY_REQUIRES_OWNER_ADMINISTRATOR",
            "WP9_IDEMPOTENCE_NOT_PROVEN",
            "New-ScheduledTaskPrincipal",
            "ServiceAccount",
            "RunLevel Limited",
            "-AtStartup",
            "RestartCount",
            "Stop-Process",
            "shutdown.exe /r /t 10",
            "Execution task created: False",
            "Real secret values used: NO",
        ),
        failures,
    )
    _require_text(
        ROLLBACK,
        (
            "WP9_REFUSES_UNOWNED",
            "PostgreSQL/runner/WP6/WP7/WP8 preserved: True",
            "Unregister-ScheduledTask",
        ),
        failures,
    )
    _require_text(
        HEALTH,
        (
            "pg_isready.exe",
            "127.0.0.1",
            "SEALED_PRODUCT_SLOTS_NOT_READY",
            '"DEGRADED"',
            "post_boot_observed",
        ),
        failures,
    )
    _require_text(GUARD, ("sealed until its owning V10 work package", "exit 23"), failures)
    _require_text(WORKER, ("BLOCKED", "RECOVERED", "process_id", "exit 42"), failures)
    _require_text(
        COLLECTOR,
        (
            "local_service_wp8_payload_read_grant",
            "POST_REBOOT_FRESH_STATUS_NOT_PROVEN",
            "process_command_lines_collected = $false",
        ),
        failures,
    )
    _require_text(ASSESSOR, ("POST_REBOOT_FRESH_STATUS_NOT_PROVEN", "EXECUTION_TASK_PRESENT"), failures)


def main() -> int:
    failures: list[str] = []
    data = _load_contract(failures)
    if data is not None:
        validate_contract(data, failures)
    validate_assets(failures)

    if failures:
        print("V10 WP9 supervision contract check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("V10 WP9 supervision contract check passed.")
    print("Supervisor: Windows Task Scheduler / LocalService")
    print("Later product slots: sealed and NOT_READY")
    print("Restart policy: bounded synthetic rehearsal required")
    print("Reboot Exit Gate: fresh HEALTHY/DEGRADED evidence required")
    print("Real-money authority: unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
