"""Bounded physical-backup reconciliation; never restore or export a production database."""

from __future__ import annotations

import json
import math
import pathlib
import time
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Protocol

REMOTE_STATUS_PATH = "/var/lib/omnicio-recovery/status.json"
REMOTE_PYTHON = "python3 -"
BOOTSTRAP_COMMENT = "Managed by OmniCIO: initial R0 recovery point v1"
WEEKLY_PREFIX = "Managed by OmniCIO: weekly recovery point v1 "
WEEKLY_RETIRE = "weekly_retire_attempted"
WEEKLY_CREATE = "weekly_create"
WEEKLY_OWNED = "weekly_owned"
BACKUP_TIMEZONE = timezone(timedelta(hours=3))


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
    weekly_copies: int

    @property
    def max_copies(self) -> int:
        # Include both the bootstrap and one temporary copy during weekly rotation.
        return self.copies + self.weekly_copies + 2


def load_policy() -> BackupPolicy:
    path = pathlib.Path(__file__).resolve().parents[2] / "pyproject.toml"
    with path.open("rb") as handle:
        values = tomllib.load(handle)["tool"]["omnicio"]["timeweb"]["backups"]
    policy = BackupPolicy(**values)
    if any(type(value) is not int or value <= 0 for value in values.values()):
        raise RecoveryBlocked("Backup policy values must be positive integers")
    if policy.copies != 7 or policy.weekly_copies != 4:
        raise RecoveryBlocked("This release requires seven daily and four weekly copies")
    return policy


def read_state(ssh: Remote) -> dict[str, Any]:
    raw = ssh.run(REMOTE_PYTHON, input_text=f"""
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
    ssh.run(REMOTE_PYTHON, input_text=f"""
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
directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
try:
    os.fsync(directory)
finally:
    os.close(directory)
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
            ids = [row.get("id") for row in rows]
            if any(type(value) is not int or value <= 0 for value in ids):
                raise RecoveryBlocked("Backup inventory contains an invalid identity")
            if len(set(ids)) != len(ids):
                raise RecoveryBlocked("Backup inventory contains duplicate identities")
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


def completed_backup(
    item: dict[str, Any], now: datetime, *, max_age: timedelta | None = timedelta(hours=24),
) -> bool:
    if item.get("status") != "done":
        return False
    if type(item.get("id")) is not int or item["id"] <= 0:
        raise RecoveryBlocked("Backup identity is invalid")
    size = item.get("size")
    if not isinstance(size, (int, float)) or isinstance(size, bool):
        raise RecoveryBlocked("Completed backup has no valid size")
    if not math.isfinite(size) or size <= 0:
        raise RecoveryBlocked("Completed backup has no valid size")
    age = now - timestamp(item.get("created_at"))
    return age >= timedelta(0) and (max_age is None or age < max_age)


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


def confirm_backup(
    client: Provider, cluster_id: int, backup_id: int,
    *, max_age: timedelta | None = timedelta(hours=24),
) -> dict[str, Any]:
    detail = client.request("GET", f"/dbs/{cluster_id}/backups/{backup_id}").get("backup")
    if (
        not isinstance(detail, dict) or detail.get("id") != backup_id
        or not completed_backup(detail, datetime.now(UTC), max_age=max_age)
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
    delete_with_receipt(client, ssh, state, policy, initial_id, "retire_attempted")


def delete_with_receipt(
    client: Provider, ssh: Remote, state: dict[str, Any], policy: BackupPolicy,
    backup_id: int, receipt: str,
) -> None:
    """Callers prove ownership and a newer surviving copy before authorizing deletion."""
    if state.get(receipt) not in {None, backup_id}:
        raise RecoveryBlocked("Copy retirement has a conflicting receipt")
    if not state.get(receipt):
        state[receipt] = backup_id
        write_state(ssh, state)
        mutate_once(client, "DELETE", f"/dbs/{policy.cluster_id}/backups/{backup_id}")
    for _ in range(12):
        remaining = get_backups(client, policy.cluster_id)
        if not any(item.get("id") == backup_id for item in remaining):
            return
        time.sleep(5)
    raise RecoveryBlocked("Copy retirement is unconfirmed; deletion was not repeated")


def weekly_period(value: datetime) -> str:
    local = value.astimezone(BACKUP_TIMEZONE).date()
    return (local - timedelta(days=local.weekday())).isoformat()


def weekly_ledger(state: dict[str, Any], policy: BackupPolicy) -> list[dict[str, Any]]:
    records = state.get(WEEKLY_OWNED, [])
    if not isinstance(records, list) or len(records) > policy.weekly_copies + 1:
        raise RecoveryBlocked("Invalid weekly ownership ledger")
    ids: set[int] = set()
    periods: set[str] = set()
    for record in records:
        if not isinstance(record, dict) or type(record.get("id")) is not int or record["id"] <= 0:
            raise RecoveryBlocked("Invalid weekly ownership identity")
        period = record.get("period")
        if not isinstance(period, str):
            raise RecoveryBlocked("Invalid weekly ownership period")
        try:
            day = datetime.strptime(period, "%Y-%m-%d")
        except (TypeError, ValueError):
            raise RecoveryBlocked("Invalid weekly ownership period") from None
        if day.weekday() != 0 or day.date().isoformat() != period:
            raise RecoveryBlocked("Weekly period must be a Monday")
        if record["id"] in ids or period in periods:
            raise RecoveryBlocked("Duplicate weekly ownership record")
        ids.add(record["id"])
        periods.add(period)
    return records


def verify_weekly_item(item: dict[str, Any], record: dict[str, Any]) -> None:
    if (
        item.get("id") != record["id"] or item.get("type") != "manual"
        or item.get("comment") != WEEKLY_PREFIX + record["period"]
        or not completed_backup(item, datetime.now(UTC), max_age=None)
        or weekly_period(timestamp(item.get("created_at"))) != record["period"]
    ):
        raise RecoveryBlocked("Weekly copy identity, period or completion changed")


def confirm_weekly_inventory(
    client: Provider, state: dict[str, Any], policy: BackupPolicy,
    backups: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    records = weekly_ledger(state, policy)
    owned_ids = {record["id"] for record in records}
    marked = [item for item in backups if str(item.get("comment", "")).startswith(WEEKLY_PREFIX)]
    if {item["id"] for item in marked} != owned_ids:
        raise RecoveryBlocked("Weekly copy inventory differs from durable ownership ledger")
    result = []
    for record in records:
        item = confirm_backup(client, policy.cluster_id, record["id"], max_age=None)
        verify_weekly_item(item, record)
        result.append(item)
    return sorted(result, key=lambda item: timestamp(item["created_at"]), reverse=True)


def finish_weekly_create(
    client: Provider, ssh: Remote, state: dict[str, Any], policy: BackupPolicy,
) -> None:
    attempt = state[WEEKLY_CREATE]
    period = attempt["period"]
    started = timestamp(attempt["attempted_at"])
    for _ in range(30):
        matching = [item for item in get_backups(client, policy.cluster_id)
                    if item.get("comment") == WEEKLY_PREFIX + period]
        if len(matching) > 1:
            raise RecoveryBlocked("Weekly create has multiple candidates; refusing to adopt any")
        if matching and matching[0].get("status") == "fail":
            raise RecoveryBlocked("Weekly copy failed; create was not repeated")
        if matching and matching[0].get("status") == "done":
            item = confirm_backup(client, policy.cluster_id, matching[0]["id"], max_age=None)
            record = {"id": item["id"], "period": period}
            verify_weekly_item(item, record)
            if timestamp(item["created_at"]) < started - timedelta(seconds=1):
                raise RecoveryBlocked("Weekly candidate predates this create attempt")
            records = weekly_ledger(state, policy)
            state[WEEKLY_OWNED] = [*records, record]
            attempt["confirmed_id"] = item["id"]
            write_state(ssh, state)
            return
        time.sleep(10)
    raise RecoveryBlocked("Weekly create is unconfirmed; it will not be repeated")


def finish_weekly_retirement(
    client: Provider, ssh: Remote, state: dict[str, Any], policy: BackupPolicy,
) -> None:
    target = state.get(WEEKLY_RETIRE)
    if target is None:
        return
    records = weekly_ledger(state, policy)
    if not any(record["id"] == target for record in records):
        raise RecoveryBlocked("Weekly retirement has no ownership receipt")
    # A receipt exists: only read to reconcile, never send DELETE a second time.
    delete_with_receipt(client, ssh, state, policy, target, WEEKLY_RETIRE)
    state[WEEKLY_OWNED] = [record for record in records if record["id"] != target]
    del state[WEEKLY_RETIRE]
    write_state(ssh, state)


def reconcile_weekly(
    client: Provider, ssh: Remote, state: dict[str, Any], policy: BackupPolicy,
) -> list[dict[str, Any]]:
    finish_weekly_retirement(client, ssh, state, policy)
    attempt = state.get(WEEKLY_CREATE)
    if attempt is not None and not isinstance(attempt, dict):
        raise RecoveryBlocked("Invalid weekly create receipt")
    if attempt is not None and not attempt.get("confirmed_id"):
        finish_weekly_create(client, ssh, state, policy)
    backups = get_backups(client, policy.cluster_id)
    owned = confirm_weekly_inventory(client, state, policy, backups)
    now = datetime.now(UTC)
    period = weekly_period(now)
    if not any(item["comment"] == WEEKLY_PREFIX + period for item in owned):
        if attempt is not None and attempt.get("period") == period:
            raise RecoveryBlocked("Confirmed weekly copy disappeared; create was not repeated")
        if len(backups) >= policy.max_copies or len(owned) > policy.weekly_copies:
            raise RecoveryBlocked("No reviewed capacity for another weekly copy")
        state[WEEKLY_CREATE] = {"period": period, "attempted_at": now.isoformat()}
        write_state(ssh, state)
        mutate_once(client, "POST", f"/dbs/{policy.cluster_id}/backups", payload={
            "comment": WEEKLY_PREFIX + period,
        })
        finish_weekly_create(client, ssh, state, policy)
        backups = get_backups(client, policy.cluster_id)
        owned = confirm_weekly_inventory(client, state, policy, backups)
    if len(owned) > policy.weekly_copies:
        # Newest copy and exact old ownership are reconfirmed before removing only the fifth.
        confirm_backup(client, policy.cluster_id, owned[0]["id"], max_age=timedelta(days=7))
        target = owned[-1]
        detail = confirm_backup(client, policy.cluster_id, target["id"], max_age=None)
        verify_weekly_item(detail, {"id": target["id"], "period": weekly_period(
            timestamp(target["created_at"]))})
        delete_with_receipt(client, ssh, state, policy, target["id"], WEEKLY_RETIRE)
        finish_weekly_retirement(client, ssh, state, policy)
        owned = confirm_weekly_inventory(
            client, state, policy, get_backups(client, policy.cluster_id),
        )
    return owned


def validate_budget(cluster: dict[str, Any], policy: BackupPolicy) -> None:
    disk_kib = (cluster.get("disk") or {}).get("size")
    if type(disk_kib) is not int or not 0 < disk_kib <= policy.max_disk_kib:
        raise RecoveryBlocked("Database disk exceeds the reviewed backup budget")
    # A conservative capacity allowance, not a provider invoice or billing enforcement.
    allowance = Decimal(disk_kib) / (1024 * 1024) * policy.max_copies * policy.rub_per_gib
    if allowance > policy.max_monthly_rub:
        raise RecoveryBlocked("Backup storage allowance exceeds the approved ceiling")
    if (cluster.get("disk_autoscaling") or {}).get("is_enabled") is not False:
        raise RecoveryBlocked("Unbounded database disk autoscaling is not permitted")


def inspect_restore_capacity(client: Provider, ssh: Remote, cluster_id: int) -> None:
    """Read-only preparation for an isolated drill; never print storage credentials."""
    report: dict[str, Any] = {"cluster_id": cluster_id, "restore_verified": False}
    for name, path, version, key in (
        ("logical_backups", f"/databases/{cluster_id}/backups", "v2", "backups"),
        ("storage", "/storages/buckets", "v1", "buckets"),
    ):
        try:
            rows = client.request("GET", path, api_version=version).get(key)
            if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
                raise ValueError("Incomplete inventory")
            allowed = ("id", "type", "status", "size", "created_at", "location")
            report[name] = {
                "count": len(rows),
                "items": [{k: row[k] for k in allowed if k in row} for row in rows[:20]],
            }
        except (RuntimeError, OSError, ValueError) as exc:
            report[name] = {"status": "unavailable", "reason": type(exc).__name__}
            status = getattr(exc, "status_code", None)
            if type(status) is int:
                report[name]["http_status"] = status
    raw = ssh.run(REMOTE_PYTHON, input_text=RESTORE_CAPACITY_SCRIPT)
    host = json.loads(raw)
    if not isinstance(host, dict):
        raise RecoveryBlocked("Invalid restore capacity response")
    report["host"] = host
    print("Recovery drill capacity: " + json.dumps(report, sort_keys=True))


RESTORE_CAPACITY_SCRIPT = r"""
import json, os, pathlib, shutil
memory = {}
for line in pathlib.Path('/proc/meminfo').read_text().splitlines():
    key, value = line.split(':', 1)
    if key in {'MemTotal', 'MemAvailable', 'SwapTotal', 'SwapFree'}:
        memory[key] = int(value.split()[0]) * 1024
release = {}
for line in pathlib.Path('/etc/os-release').read_text().splitlines():
    key, sep, value = line.partition('=')
    if sep and key in {'ID', 'VERSION_ID', 'VERSION_CODENAME'}:
        release[key] = value.strip('"')
disk = shutil.disk_usage('/var/lib')
print(json.dumps({
    'cpu_count': os.cpu_count(), 'memory_bytes': memory,
    'disk_total_bytes': disk.total, 'disk_free_bytes': disk.free,
    'os': release, 'systemd_run': bool(shutil.which('systemd-run')),
    'postgres_majors': sorted(p.name for p in pathlib.Path('/usr/lib/postgresql').glob('*')
                              if p.is_dir() and p.name.isdecimal()),
}))
"""


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
        if len(backups) > policy.max_copies:
            raise RecoveryBlocked("Backup inventory exceeds the reviewed storage allowance")
        reconcile_schedule(client, ssh, state, policy, now)
        backups = get_backups(client, policy.cluster_id)
        backups = ensure_initial_copy(client, ssh, state, policy, backups)
        now = datetime.now(UTC)
        retire_bootstrap(client, ssh, state, policy, backups, now)
        weekly = reconcile_weekly(client, ssh, state, policy)
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
        period = weekly_period(timestamp(weekly[0]["created_at"]))
        next_week = datetime.strptime(period, "%Y-%m-%d").replace(tzinfo=BACKUP_TIMEZONE)
        next_week += timedelta(days=7)
        if weekly_period(now) != period:
            raise RecoveryBlocked("Calendar week changed during verification; run again")
        state.update(
            provider_status="ok", observed_at=now.isoformat(),
            latest_backup_at=timestamp(detail["created_at"]).isoformat(),
            latest_backup_id=detail["id"], schedule_enabled=True,
            schedule_interval="day", retention_copies=policy.copies,
            weekly_retention_copies=policy.weekly_copies, weekly_available_copies=len(weekly),
            latest_weekly_backup_at=timestamp(weekly[0]["created_at"]).isoformat(),
            weekly_period=period, weekly_next_due_at=next_week.isoformat(),
        )
        write_state(ssh, state)
        print(f"Recovery point verified: cluster={policy.cluster_id}, backup={detail['id']}, "
              f"created_at={state['latest_backup_at']}, daily_copies={policy.copies}, "
              f"weekly_available={len(weekly)}/{policy.weekly_copies}, "
              f"weekly_backup={weekly[0]['id']}. "
              "Production restore remains unverified.")
    except (RuntimeError, OSError, ValueError, TypeError, KeyError) as exc:
        state.update(provider_status="unavailable", observed_at=datetime.now(UTC).isoformat())
        write_state(ssh, state)
        if isinstance(exc, RecoveryBlocked):
            raise
        raise RecoveryBlocked("Backup verification failed; schema remains unchanged") from None
