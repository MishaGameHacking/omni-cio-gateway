from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.check_v10_wp10_backup_schedule import ScheduleError, validate_schedule

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "docs" / "architecture" / "V10_WP10_RECOVERY_CONTRACT.json"
SCHEDULE_PATH = ROOT / "infrastructure" / "windows" / "wp10_backup_schedule.json"
RUNNER_PATH = ROOT / "infrastructure" / "windows" / "run_wp10_backup.ps1"


def _contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _schedule() -> dict:
    return json.loads(SCHEDULE_PATH.read_text(encoding="utf-8"))


def _runner() -> str:
    return RUNNER_PATH.read_text(encoding="utf-8")


def test_schedule_accepts_complete_offdevice_cycle() -> None:
    validate_schedule(_contract(), _schedule(), _runner())


def test_schedule_rejects_cadence_outside_rpo() -> None:
    schedule = _schedule()
    schedule["cadence_minutes"] = 61
    with pytest.raises(ScheduleError, match="SCHEDULE_CADENCE_INVALID"):
        validate_schedule(_contract(), schedule, _runner())


def test_schedule_rejects_local_only_production_cycle() -> None:
    for field, reason in (
        ("use_prepared_offdevice_target", "SCHEDULE_OFFDEVICE_TARGET_NOT_REQUIRED"),
        ("successful_cycle_requires_offdevice_copy", "SCHEDULE_OFFDEVICE_COPY_NOT_REQUIRED"),
        ("successful_cycle_requires_retention", "SCHEDULE_RETENTION_NOT_REQUIRED"),
    ):
        schedule = _schedule()
        schedule[field] = False
        with pytest.raises(ScheduleError, match=reason):
            validate_schedule(_contract(), schedule, _runner())


def test_contract_cannot_weaken_production_offdevice_or_retention() -> None:
    for field, reason in (
        ("production_cycle_requires_offdevice_copy", "CONTRACT_OFFDEVICE_COPY_NOT_REQUIRED"),
        ("production_cycle_requires_retention", "CONTRACT_RETENTION_NOT_REQUIRED"),
    ):
        contract = copy.deepcopy(_contract())
        contract["automation"][field] = False
        with pytest.raises(ScheduleError, match=reason):
            validate_schedule(contract, _schedule(), _runner())


def test_production_private_state_backup_class_is_fixed() -> None:
    schedule = _schedule()
    schedule["production_backup_class"] = "POSTGRES_LOGICAL_RECOVERY_REHEARSAL"
    with pytest.raises(ScheduleError, match="SCHEDULE_BACKUP_CLASS_INVALID"):
        validate_schedule(_contract(), schedule, _runner())


def test_runner_must_fail_closed_without_offdevice_for_private_state() -> None:
    runner = _runner().replace("PRIVATE_STATE_BACKUP_REQUIRES_OFFDEVICE_TARGET", "REMOVED")
    with pytest.raises(ScheduleError, match="RUNNER_COMPLETE_CYCLE_GUARD_MISSING"):
        validate_schedule(_contract(), _schedule(), runner)
