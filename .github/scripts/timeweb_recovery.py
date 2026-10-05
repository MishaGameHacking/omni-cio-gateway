"""Bounded physical-backup reconciliation; never restore or export a production database."""

from __future__ import annotations

import json
import math
import pathlib
import time
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Protocol

REMOTE_STATUS_PATH = "/var/lib/omnicio-recovery/status.json"
BOOTSTRAP_COMMENT = "Managed by OmniCIO: initial R0 recovery point v1"


class RecoveryBlocked(RuntimeError):
    """Recovery evidence is insufficient for a schema mutation."""


class Provider(Protocol):
    def request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]: ...


class Remote(Protocol):
    def run(self, command: str, *, input_text: str | None = None) -> str: ...


@dataclass(frozen=True)
class BackupPolicy:
    cluster_id: int
    copies: int
    max_disk_kib: int
    max_monthly_rub: int
    rub_per_gib: int


def load_policy() -> BackupPolicy:
    path = pathlib.Path(__file__).resolve().parents[2] / "pyproject.toml"
    with path.open("rb") as handle:
        values = tomllib.load(handle)["tool"]["omnicio"]["timeweb"]["backups"]
    policy = BackupPolicy(**values)
    if any(type(value) is not int or value <= 0 for value in values.values()):
        raise RecoveryBlocked("Backup policy values must be positive integers")
    if policy.copies != 7:
        raise RecoveryBlocked("This release supports exactly seven daily copies")
    return policy


def read_state(ssh: Remote) -> dict[str, Any]:
    raw = ssh.run("python3 -", input_text=f"""
import json, pathlib
path = pathlib.Path({REMOTE_STATUS_PATH!r})
if path.exists():
    with path.open('rb') as handle:
        raw = handle.read(16385)
    if len(raw) > 16384:
        raise SystemExit('recovery state too large')
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise SystemExit('invalid recovery state')
else:
    value = {{}}
print(json.dumps(value))
""")
    state = json.loads(raw)
    if not isinstance(state, dict):
        raise RecoveryBlocked("Recovery state is not an object")
    return state


def write_state(ssh: Remote, state: dict[str, Any]) -> None:
    # Contains only operational evidence and mutation receipts, never rows, URLs or credentials.
    encoded = json.dumps(state, ensure_ascii=True, separators=(",", ":"))
    ssh.run("python3 -", input_text=f"""
import os, pathlib
path = pathlib.Path({REMOTE_STATUS_PATH!r})
path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
temp = path.with_suffix('.new')
with temp.open('w', encoding='utf-8') as handle:
    handle.write({encoded!r})
    handle.flush()
    os.fsync(handle.fileno())
os.chmod(temp, 0o644)
temp.replace(path)
""")


def timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise RecoveryBlocked("Backup timestamp is missing")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise RecoveryBlocked("Backup timestamp is invalid") from None
    if parsed.tzinfo is None:
        raise RecoveryBlocked("Backup timestamp has no timezone")
    return parsed.astimezone(UTC)


def get_schedule(client: Provider, cluster_id: int) -> dict[str, Any]:
    value = client.request("GET", f"/dbs/{cluster_id}/auto-backups").get("auto_backups_settings")
    if not isinstance(value, dict) or type(value.get("is_enabled")) is not bool:
        raise RecoveryBlocked("Backup schedule response is incomplete")
    return value


def get_backups(client: Provider, cluster_id: int) -> list[dict[str, Any]]:
    # Full bounded inventory: an incomplete page cannot prove absence or justify creating a copy.
    rows: list[dict[str, Any]] = []
    for offset in range(0, 500, 100):
        response = client.request("GET", f"/dbs/{cluster_id}/backups?limit=100&offset={offset}")
        batch = response.get("backups")
        if not isinstance(batch, list) or not all(isinstance(item, dict) for item in batch):
            raise RecoveryBlocked("Backup inventory response is incomplete")
        rows.extend(batch)
        if len(batch) < 100:
            total = (response.get("meta") or {}).get("total")
            if total is not None and (type(total) is not int or total != len(rows)):
                raise RecoveryBlocked("Backup inventory total does not match the completed pages")
            return rows
    raise RecoveryBlocked("Backup inventory pagination limit exceeded")


def schedule_matches(schedule: dict[str, Any], policy: BackupPolicy, now: datetime) -> bool:
    # Timeweb explicitly ignores the time part of this date-only scheduling field.
    start = schedule.get("creation_start_at")
    try:
        starts_today_or_before = (
            isinstance(start, str) and datetime.fromisoformat(start).date() <= now.date()
        )
    except ValueError:
        starts_today_or_before = False
    return (
        schedule.get("is_enabled") is True and schedule.get("interval") == "day"
        and type(schedule.get("copy_count")) is int and schedule["copy_count"] == policy.copies
        and starts_today_or_before
    )


def mutate_once(client: Provider, method: str, path: str, **kwargs: Any) -> None:
    """Only a subsequent read may confirm an operation, including after a lost response."""
    try:
        client.request(method, path, **kwargs)
    except (RuntimeError, OSError, ValueError):
        print("Provider mutation was not confirmed; reconciling by read without repeating it.")


def reconcile_schedule(
    client: Provider, ssh: Remote, state: dict[str, Any], policy: BackupPolicy, now: datetime,
) -> dict[str, Any]:
    schedule = get_schedule(client, policy.cluster_id)
    if schedule_matches(schedule, policy, now):
        return schedule
    if schedule["is_enabled"] or state.get("schedule_attempted"):
        raise RecoveryBlocked("Backup schedule changed or an earlier update is unconfirmed")
    previous_count = schedule.get("copy_count")
    if previous_count is not None and (
        type(previous_count) is not int or previous_count > policy.copies
    ):
        raise RecoveryBlocked("Refusing to reduce an existing retention policy")
    state["schedule_attempted"] = True
    write_state(ssh, state)
    mutate_once(client, "PATCH", f"/dbs/{policy.cluster_id}/auto-backups", payload={
        "is_enabled": True, "copy_count": policy.copies, "interval": "day",
        "day_of_week": 1, "creation_start_at": now.isoformat(),
    })
    for _ in range(12):
        schedule = get_schedule(client, policy.cluster_id)
        if schedule_matches(schedule, policy, now):
            return schedule
        time.sleep(5)
    raise RecoveryBlocked("Daily backup schedule could not be confirmed; update was not repeated")


def completed_backup(item: dict[str, Any], now: datetime) -> bool:
    if item.get("status") != "done":
        return False
    if type(item.get("id")) is not int or item["id"] <= 0:
        raise RecoveryBlocked("Backup identity is invalid")
    size = item.get("size")
    if not isinstance(size, (int, float)) or isinstance(size, bool):
        raise RecoveryBlocked("Completed backup has no valid size")
    if not math.isfinite(size) or size <= 0:
        raise RecoveryBlocked("Completed backup has no valid size")
    return timedelta(0) <= now - timestamp(item.get("created_at")) < timedelta(hours=24)


def ensure_initial_copy(
    client: Provider, ssh: Remote, state: dict[str, Any], policy: BackupPolicy,
    backups: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if any(completed_backup(item, datetime.now(UTC)) for item in backups):
        return backups
    # One bootstrap only. Later schedule failures require investigation, not accumulating copies.
    if not backups and not state.get("bootstrap_attempted"):
        state["bootstrap_attempted"] = True
        write_state(ssh, state)
        mutate_once(client, "POST", f"/dbs/{policy.cluster_id}/backups", payload={
            "comment": BOOTSTRAP_COMMENT,
        })
    for _ in range(30):
        backups = get_backups(client, policy.cluster_id)
        if any(completed_backup(item, datetime.now(UTC)) for item in backups):
            return backups
        if any(item.get("status") == "fail" for item in backups):
            raise RecoveryBlocked("Provider reports a failed backup; schema remains unchanged")
        time.sleep(10)
    raise RecoveryBlocked("No completed backup younger than 24 hours; create was not repeated")


def retirement_candidate(
    backups: list[dict[str, Any]], now: datetime,
) -> tuple[int, int] | None:
    automatic = [
        item for item in backups if item.get("type") == "auto" and completed_backup(item, now)
    ]
    owned = [item for item in backups if item.get("comment") == BOOTSTRAP_COMMENT]
    if not automatic or not owned:
        return None
    if len(owned) != 1 or owned[0].get("type") != "manual" or owned[0].get("status") != "done":
        raise RecoveryBlocked("Initial recovery point has conflicting ownership or status")
    initial = owned[0]
    if type(initial.get("id")) is not int or initial["id"] <= 0:
        raise RecoveryBlocked("Initial recovery point has an invalid identity")
    if max(timestamp(item["created_at"]) for item in automatic) <= timestamp(initial["created_at"]):
        return None
    latest = max(automatic, key=lambda item: timestamp(item["created_at"]))
    return initial["id"], latest["id"]


def confirm_backup(client: Provider, cluster_id: int, backup_id: int) -> dict[str, Any]:
    detail = client.request("GET", f"/dbs/{cluster_id}/backups/{backup_id}").get("backup")
    if (
        not isinstance(detail, dict) or detail.get("id") != backup_id
        or not completed_backup(detail, datetime.now(UTC))
    ):
        raise RecoveryBlocked("Backup identity or completion could not be re-confirmed")
    return detail


def retire_bootstrap(
    client: Provider, ssh: Remote, state: dict[str, Any], policy: BackupPolicy,
    backups: list[dict[str, Any]], now: datetime,
) -> None:
    """Remove only our initial manual copy after a newer successful automatic copy exists."""
    if state.get("bootstrap_attempted") is not True:
        return
    candidate = retirement_candidate(backups, now)
    if candidate is None:
        return
    initial_id, automatic_id = candidate
    confirm_backup(client, policy.cluster_id, automatic_id)
    if state.get("retire_attempted") not in {None, initial_id}:
        raise RecoveryBlocked("Initial copy retirement has a conflicting receipt")
    if not state.get("retire_attempted"):
        state["retire_attempted"] = initial_id
        write_state(ssh, state)
        mutate_once(client, "DELETE", f"/dbs/{policy.cluster_id}/backups/{initial_id}")
    for _ in range(12):
        remaining = get_backups(client, policy.cluster_id)
        if not any(item.get("id") == initial_id for item in remaining):
            return
        time.sleep(5)
    raise RecoveryBlocked("Initial copy retirement is unconfirmed; deletion was not repeated")


def validate_budget(cluster: dict[str, Any], policy: BackupPolicy) -> None:
    disk_kib = (cluster.get("disk") or {}).get("size")
    if type(disk_kib) is not int or not 0 < disk_kib <= policy.max_disk_kib:
        raise RecoveryBlocked("Database disk exceeds the reviewed backup budget")
    # Conservative allowance: seven full-disk daily copies plus one initial copy, at the
    # published 6 RUB/GiB-month rate. This bounds configured capacity, not a provider invoice.
    allowance = Decimal(disk_kib) / (1024 * 1024) * (policy.copies + 1) * policy.rub_per_gib
    if allowance > policy.max_monthly_rub:
        raise RecoveryBlocked("Backup storage allowance exceeds the approved ceiling")
    if (cluster.get("disk_autoscaling") or {}).get("is_enabled") is not False:
        raise RecoveryBlocked("Unbounded database disk autoscaling is not permitted")


def ensure_recovery_point(client: Provider, ssh: Remote, cluster: dict[str, Any]) -> None:
    policy = load_policy()
    if cluster.get("id") != policy.cluster_id:
        raise RecoveryBlocked("Backup policy does not authorize this database cluster")
    state = read_state(ssh)
    if state and (state.get("schema_version") != 1 or state.get("cluster_id") != policy.cluster_id):
        raise RecoveryBlocked("Recovery state belongs to another contract or cluster")
    state.update(schema_version=1, cluster_id=policy.cluster_id, provider_status="pending")
    try:
        validate_budget(cluster, policy)
        now = datetime.now(UTC)
        backups = get_backups(client, policy.cluster_id)
        if len(backups) > policy.copies + 1:
            raise RecoveryBlocked("Backup inventory exceeds the reviewed storage allowance")
        reconcile_schedule(client, ssh, state, policy, now)
        backups = get_backups(client, policy.cluster_id)
        backups = ensure_initial_copy(client, ssh, state, policy, backups)
        now = datetime.now(UTC)
        retire_bootstrap(client, ssh, state, policy, backups, now)
        # Re-read after every mutation; never certify the response to a create alone.
        backups = get_backups(client, policy.cluster_id)
        now = datetime.now(UTC)
        ready = [item for item in backups if completed_backup(item, now)]
        if not ready:
            raise RecoveryBlocked("Fresh recovery point disappeared")
        latest = max(ready, key=lambda item: timestamp(item["created_at"]))
        detail = confirm_backup(client, policy.cluster_id, latest["id"])
        schedule = get_schedule(client, policy.cluster_id)
        if not schedule_matches(schedule, policy, now):
            raise RecoveryBlocked("Daily backup schedule changed during verification")
        state.update(
            provider_status="ok", observed_at=now.isoformat(),
            latest_backup_at=timestamp(detail["created_at"]).isoformat(),
            latest_backup_id=detail["id"], schedule_enabled=True,
            schedule_interval="day", retention_copies=policy.copies,
        )
        write_state(ssh, state)
        print(f"Recovery point verified: cluster={policy.cluster_id}, backup={detail['id']}, "
              f"created_at={state['latest_backup_at']}, daily_copies={policy.copies}. "
              "Production restore remains unverified.")
    except (RuntimeError, OSError, ValueError, TypeError, KeyError) as exc:
        state.update(provider_status="unavailable", observed_at=datetime.now(UTC).isoformat())
        write_state(ssh, state)
        if isinstance(exc, RecoveryBlocked):
            raise
        raise RecoveryBlocked("Backup verification failed; schema remains unchanged") from None
