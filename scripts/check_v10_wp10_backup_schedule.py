from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "docs" / "architecture" / "V10_WP10_RECOVERY_CONTRACT.json"
SCHEDULE_PATH = ROOT / "infrastructure" / "windows" / "wp10_backup_schedule.json"
RUNNER_PATH = ROOT / "infrastructure" / "windows" / "run_wp10_backup.ps1"


class ScheduleError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ScheduleError("SCHEDULE_INPUT_NOT_OBJECT")
    return payload


def validate_schedule(
    contract: dict[str, Any],
    schedule: dict[str, Any],
    runner_text: str,
) -> None:
    if (
        schedule.get("schema_version") != "1"
        or schedule.get("work_package") != "WP10"
    ):
        raise ScheduleError("SCHEDULE_IDENTITY_INVALID")

    automation = contract["automation"]
    rpo = int(contract["recovery_objectives"]["rpo_minutes"])
    cadence = int(schedule.get("cadence_minutes", 0))
    if (
        cadence <= 0
        or cadence > rpo
        or cadence != int(automation["target_cadence_minutes"])
    ):
        raise ScheduleError("SCHEDULE_CADENCE_INVALID")

    if schedule.get("enabled_before_product_binding") is not False:
        raise ScheduleError("SCHEDULE_ACTIVATED_BEFORE_PRODUCT_BINDING")
    if schedule.get("production_database_binding") != "NOT_READY_UNTIL_WP13":
        raise ScheduleError("SCHEDULE_DATABASE_BOUND_EARLY")
    if (
        schedule.get("production_task_identity_binding")
        != "NOT_READY_UNTIL_WP13_WP14"
    ):
        raise ScheduleError("SCHEDULE_IDENTITY_BOUND_EARLY")
    if schedule.get("runner_script") != "infrastructure/windows/run_wp10_backup.ps1":
        raise ScheduleError("SCHEDULE_RUNNER_INVALID")

    if schedule.get("production_backup_class") != "POSTGRES_LOGICAL_PRIVATE_STATE":
        raise ScheduleError("SCHEDULE_BACKUP_CLASS_INVALID")
    if automation.get("production_backup_class") != "POSTGRES_LOGICAL_PRIVATE_STATE":
        raise ScheduleError("CONTRACT_BACKUP_CLASS_INVALID")

    for key, reason in (
        ("use_prepared_offdevice_target", "SCHEDULE_OFFDEVICE_TARGET_NOT_REQUIRED"),
        (
            "successful_cycle_requires_offdevice_copy",
            "SCHEDULE_OFFDEVICE_COPY_NOT_REQUIRED",
        ),
        ("successful_cycle_requires_retention", "SCHEDULE_RETENTION_NOT_REQUIRED"),
    ):
        if schedule.get(key) is not True:
            raise ScheduleError(reason)

    for key, reason in (
        (
            "production_cycle_requires_offdevice_copy",
            "CONTRACT_OFFDEVICE_COPY_NOT_REQUIRED",
        ),
        ("production_cycle_requires_retention", "CONTRACT_RETENTION_NOT_REQUIRED"),
    ):
        if automation.get(key) is not True:
            raise ScheduleError(reason)

    if schedule.get("credentials_in_task_definition") is not False:
        raise ScheduleError("SCHEDULE_EMBEDS_CREDENTIALS")
    if schedule.get("private_payload_in_task_definition") is not False:
        raise ScheduleError("SCHEDULE_EMBEDS_PRIVATE_PAYLOAD")
    if automation.get("production_schedule_activation_before_product_binding") is not False:
        raise ScheduleError("CONTRACT_ALLOWS_EARLY_SCHEDULE_ACTIVATION")
    if automation.get("secret_values_in_task_definition_forbidden") is not True:
        raise ScheduleError("CONTRACT_TASK_SECRET_GUARD_MISSING")

    required_runner_tokens = (
        "[switch]$UsePreparedOffdeviceTarget",
        "PRIVATE_STATE_BACKUP_REQUIRES_OFFDEVICE_TARGET",
        '"copy"',
        '"prune"',
        "OFFDEVICE_COPY_REQUIRED_BUT_NOT_PROVEN",
        "Get-BitLockerVolume",
    )
    for token in required_runner_tokens:
        if token not in runner_text:
            raise ScheduleError(f"RUNNER_COMPLETE_CYCLE_GUARD_MISSING:{token}")


def main() -> int:
    validate_schedule(
        _load(CONTRACT_PATH),
        _load(SCHEDULE_PATH),
        RUNNER_PATH.read_text(encoding="utf-8"),
    )
    print("V10 WP10 backup schedule check passed.")
    print("Cadence: 60 minutes <= RPO")
    print("Production success requires verified off-device copy + retention")
    print("Production DB/task identity remain sealed until WP13/WP14")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
