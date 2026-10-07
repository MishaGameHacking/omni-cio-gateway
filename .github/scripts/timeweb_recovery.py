"""Physical backup reconciliation and explicitly gated isolated logical restore drills."""

from __future__ import annotations

import hashlib
import json
import math
import os
import pathlib
import re
import secrets
import subprocess
import tempfile
import time
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Protocol, cast

REMOTE_STATUS_PATH = "/var/lib/omnicio-recovery/status.json"
REMOTE_PYTHON = "python3 -"
BOOTSTRAP_COMMENT = "Managed by OmniCIO: initial R0 recovery point v1"
WEEKLY_PREFIX = "Managed by OmniCIO: weekly recovery point v1 "
WEEKLY_RETIRE = "weekly_retire_attempted"
WEEKLY_CREATE = "weekly_create"
WEEKLY_OWNED = "weekly_owned"
RELEASE_COPY = "release_copy"
RELEASE_PREFIX = "Managed by OmniCIO: prerelease recovery point v1 "
BACKUP_TIMEZONE = timezone(timedelta(hours=3))
INSPECTION_DETAIL_LIMIT = 20


class RecoveryBlocked(RuntimeError):
    """Recovery evidence is insufficient for a schema mutation."""


class Provider(Protocol):
    def request(
        self, method: str, path: str, *, api_version: str = "v1",
        payload: dict[str, Any] | None = None, timeout: int = 30,
    ) -> dict[str, Any]: ...


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
        # Two shared spare slots cover bootstrap/prerelease and weekly rotation.
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
            validate_inventory(rows, total)
            return rows
    raise RecoveryBlocked("Backup inventory pagination limit exceeded")


def validate_inventory(rows: list[dict[str, Any]], total: Any) -> None:
    if total is not None and (type(total) is not int or total != len(rows)):
        raise RecoveryBlocked("Backup inventory total does not match the completed pages")
    ids = [row.get("id") for row in rows]
    if any(type(value) is not int or value <= 0 for value in ids):
        raise RecoveryBlocked("Backup inventory contains an invalid identity")
    if len(set(ids)) != len(ids):
        raise RecoveryBlocked("Backup inventory contains duplicate identities")


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


def _inspection_error(exc: Exception) -> dict[str, Any]:
    result: dict[str, Any] = {"status": "unavailable", "reason": type(exc).__name__}
    status = getattr(exc, "status_code", None)
    if type(status) is int and 100 <= status <= 599:
        result["http_status"] = status
    return result


def _inspection_schedule(client: Provider, policy: BackupPolicy) -> dict[str, Any]:
    try:
        schedule = get_schedule(client, policy.cluster_id)
    except (RuntimeError, OSError, ValueError, TypeError, AttributeError) as exc:
        return _inspection_error(exc)
    start = schedule.get("creation_start_at")
    try:
        start = datetime.fromisoformat(start).isoformat() if isinstance(start, str) else None
    except ValueError:
        start = None
    interval = schedule.get("interval")
    count = schedule.get("copy_count")
    return {
        "status": "ok", "matches_policy": schedule_matches(schedule, policy, datetime.now(UTC)),
        "is_enabled": schedule["is_enabled"],
        "interval": interval if interval in ("day", "week", "month") else "unknown",
        "copy_count": count if type(count) is int else None, "creation_start_at": start,
    }


def _inspection_comment(value: Any) -> str:
    if value == BOOTSTRAP_COMMENT:
        return "bootstrap_tag"
    if isinstance(value, str) and value.startswith(WEEKLY_PREFIX):
        return "weekly_tag"
    if isinstance(value, str) and value.startswith(RELEASE_PREFIX):
        return "prerelease_tag"
    return "other" if value else "absent"


def _inspection_backup(item: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(UTC)
    status = item.get("status")
    size = item.get("size")
    try:
        size_valid = (
            isinstance(size, (int, float)) and not isinstance(size, bool)
            and math.isfinite(size) and size > 0
        )
    except OverflowError:
        size_valid = False
    try:
        created = timestamp(item.get("created_at"))
    except (RecoveryBlocked, OverflowError):
        created = None
    reason = _inspection_freshness_reason(item, now, size_valid, created)
    known_statuses = ("precreate", "delete", "shutdown", "recover", "create", "fail", "done")
    kind = item.get("type")
    return {
        "id": item["id"], "status": status if status in known_statuses else "unknown",
        "type": kind if kind in ("manual", "auto") else "unknown",
        "size": size if size_valid else None,
        "created_at": created.isoformat() if created is not None else None,
        "age_hours": round((now - created).total_seconds() / 3600, 4)
        if created is not None else None,
        "eligible": reason == "fresh", "reason": reason,
        "comment_classification": _inspection_comment(item.get("comment")),
    }


def _inspection_freshness_reason(
    item: dict[str, Any], now: datetime, size_valid: bool, created: datetime | None,
) -> str:
    if item.get("status") != "done":
        return "not_completed"
    if not size_valid:
        return "invalid_size"
    if created is None:
        return "invalid_timestamp"
    if created > now:
        return "future_timestamp"
    # Use the same freshness rule as the mutation gate, without authorizing a mutation.
    return "fresh" if completed_backup(item, now) else "stale"


def _inspection_details(
    client: Provider, cluster_id: int, rows: list[dict[str, Any]],
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    complete = len(rows) <= INSPECTION_DETAIL_LIMIT
    for row in rows[:INSPECTION_DETAIL_LIMIT]:
        backup_id = row["id"]
        try:
            detail = client.request(
                "GET", f"/dbs/{cluster_id}/backups/{backup_id}", timeout=10,
            ).get("backup")
            if not isinstance(detail, dict) or type(detail.get("id")) is not int:
                raise RecoveryBlocked("Backup detail identity is invalid")
            if detail["id"] != backup_id:
                raise RecoveryBlocked("Backup detail identity differs from inventory")
            items.append({"status": "ok", "backup": _inspection_backup(detail)})
        except (RuntimeError, OSError, ValueError, TypeError, AttributeError) as exc:
            complete = False
            items.append({"id": backup_id, **_inspection_error(exc)})
    return {"complete": complete, "limit": INSPECTION_DETAIL_LIMIT, "items": items}


def inspect_provider_recovery(client: Provider) -> dict[str, Any]:
    """GET-only operational metadata; never certify recovery, restore, or copy ownership."""
    policy = load_policy()
    report: dict[str, Any] = {
        "cluster_id": policy.cluster_id, "recovery_verified": False, "restore_verified": False,
        "schedule": _inspection_schedule(client, policy),
    }
    try:
        rows = get_backups(client, policy.cluster_id)
    except (RuntimeError, OSError, ValueError, TypeError, AttributeError) as exc:
        report["inventory"] = {"complete": False, **_inspection_error(exc)}
        report["details"] = {"complete": False, "limit": INSPECTION_DETAIL_LIMIT, "items": []}
    else:
        selected = rows[:INSPECTION_DETAIL_LIMIT]
        report["inventory"] = {
            "status": "ok", "complete": True, "count": len(rows),
            "returned_count": len(selected), "truncated": len(selected) < len(rows),
            "items": [_inspection_backup(row) for row in selected],
        }
        report["details"] = _inspection_details(client, policy.cluster_id, rows)
    report["complete"] = (
        report["schedule"]["status"] == "ok" and report["inventory"]["complete"]
        and report["details"]["complete"]
    )
    report["observed_at"] = datetime.now(UTC).isoformat()
    return report


def mutate_once(client: Provider, method: str, path: str, **kwargs: Any) -> dict[str, Any] | None:
    """Only a subsequent read may confirm an operation, including after a lost response."""
    try:
        return client.request(method, path, **kwargs)
    except (RuntimeError, OSError, ValueError):
        print("Provider mutation was not confirmed; reconciling by read without repeating it.")
        return None


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


def _require_release_sha(value: Any) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{40}", value) is None:
        raise RecoveryBlocked("Prerelease recovery requires an exact accepted commit identity")
    return value


def _release_receipt(state: dict[str, Any], policy: BackupPolicy) -> dict[str, Any] | None:
    if RELEASE_COPY not in state:
        return None
    receipt = state[RELEASE_COPY]
    if not isinstance(receipt, dict) or receipt.get("cluster_id") != policy.cluster_id:
        raise RecoveryBlocked("Invalid prerelease recovery receipt")
    sha = _require_release_sha(receipt.get("release_sha"))
    if receipt.get("comment") != RELEASE_PREFIX + sha:
        raise RecoveryBlocked("Prerelease recovery comment differs from its receipt")
    if timestamp(receipt.get("attempted_at")) > datetime.now(UTC):
        raise RecoveryBlocked("Prerelease recovery receipt is in the future")
    baseline = receipt.get("baseline_ids")
    if not isinstance(baseline, list) or len(baseline) > policy.max_copies - 2:
        raise RecoveryBlocked("Invalid prerelease recovery baseline")
    validate_inventory([{"id": value} for value in baseline], None)
    if receipt.get("response_invalid"):
        raise RecoveryBlocked("Prerelease creation response requires independent investigation")
    _validate_release_identities(receipt, baseline)
    return receipt


def _validate_release_identities(receipt: dict[str, Any], baseline: list[Any]) -> None:
    for field in ("response_id", "confirmed_id"):
        if field in receipt:
            identity = receipt[field]
            if type(identity) is not int or identity <= 0 or identity in baseline:
                raise RecoveryBlocked("Invalid recorded prerelease recovery identity")
    if (
        "response_id" in receipt and "confirmed_id" in receipt
        and receipt["response_id"] != receipt["confirmed_id"]
    ):
        raise RecoveryBlocked("Prerelease response and confirmation identities differ")


def _verify_release_item(item: dict[str, Any], receipt: dict[str, Any]) -> None:
    if (
        item.get("type") != "manual" or item.get("comment") != receipt["comment"]
        or item.get("id") in receipt["baseline_ids"]
        or not completed_backup(item, datetime.now(UTC))
        or timestamp(item.get("created_at")) < timestamp(receipt["attempted_at"])
    ):
        raise RecoveryBlocked("Prerelease recovery copy differs from its recorded operation")
    for field in ("response_id", "confirmed_id"):
        if field in receipt and item["id"] != receipt[field]:
            raise RecoveryBlocked("Recorded prerelease recovery identity changed")


def _release_candidate(
    backups: list[dict[str, Any]], receipt: dict[str, Any],
) -> dict[str, Any] | None:
    marked = [item for item in backups
              if str(item.get("comment", "")).startswith(RELEASE_PREFIX)]
    if len(marked) > 1 or any(item.get("comment") != receipt["comment"] for item in marked):
        raise RecoveryBlocked("Prerelease recovery inventory has conflicting ownership")
    if not marked:
        return None
    item = marked[0]
    if item["id"] in receipt["baseline_ids"] or item.get("type") != "manual":
        raise RecoveryBlocked("Prerelease recovery candidate is not a new manual copy")
    if item.get("status") == "fail":
        raise RecoveryBlocked("Prerelease recovery copy failed; create was not repeated")
    if item.get("status") != "done":
        if item.get("status") in ("precreate", "create"):
            return None
        raise RecoveryBlocked("Prerelease recovery copy has an unexpected status")
    _verify_release_item(item, receipt)
    return item


def _finish_release_copy(
    client: Provider, ssh: Remote, state: dict[str, Any], policy: BackupPolicy,
    receipt: dict[str, Any],
) -> list[dict[str, Any]]:
    for _ in range(30):
        backups = get_backups(client, policy.cluster_id)
        if len(backups) > policy.max_copies:
            raise RecoveryBlocked("Prerelease inventory exceeds the reviewed allowance")
        candidate = _release_candidate(backups, receipt)
        if candidate is not None:
            detail = confirm_backup(client, policy.cluster_id, candidate["id"])
            _verify_release_item(detail, receipt)
            receipt["confirmed_id"] = detail["id"]
            write_state(ssh, state)
            return backups
        time.sleep(10)
    raise RecoveryBlocked("Prerelease recovery create is unconfirmed; it will not be repeated")


def _require_retired_bootstrap(state: dict[str, Any], backups: list[dict[str, Any]]) -> None:
    bootstrap = state.get("bootstrap_attempted")
    retired = state.get("retire_attempted")
    if bootstrap is True:
        if type(retired) is not int or retired <= 0 or any(row["id"] == retired for row in backups):
            raise RecoveryBlocked("Bootstrap recovery ownership is unresolved")
    elif (bootstrap is not None and bootstrap is not False) or retired is not None:
        raise RecoveryBlocked("Invalid bootstrap recovery receipt")


def _require_resolved_backup_receipts(
    state: dict[str, Any], backups: list[dict[str, Any]], records: list[dict[str, Any]],
) -> None:
    _require_retired_bootstrap(state, backups)
    if state.get(WEEKLY_RETIRE) is not None:
        raise RecoveryBlocked("Weekly retirement must finish before prerelease creation")
    weekly = state.get(WEEKLY_CREATE)
    if weekly is None:
        return
    if not isinstance(weekly, dict) or type(weekly.get("confirmed_id")) is not int:
        raise RecoveryBlocked("Weekly creation must finish before prerelease creation")
    if not any(row["id"] == weekly["confirmed_id"] and row["period"] == weekly.get("period")
               for row in records):
        raise RecoveryBlocked("Weekly creation receipt differs from its confirmed ledger")
    if timestamp(weekly.get("attempted_at")) > datetime.now(UTC):
        raise RecoveryBlocked("Weekly creation receipt is in the future")


def _require_release_capacity(
    client: Provider, state: dict[str, Any], policy: BackupPolicy,
    backups: list[dict[str, Any]],
) -> None:
    if len(backups) > policy.max_copies - 2:
        raise RecoveryBlocked("Prerelease copy must leave capacity for weekly rotation")
    if any(str(row.get("comment", "")).startswith(RELEASE_PREFIX) for row in backups):
        raise RecoveryBlocked("Prerelease inventory has no matching durable receipt")
    now = datetime.now(UTC)
    if any(row.get("type") not in ("auto", "manual")
           or not completed_backup(row, now, max_age=None) for row in backups):
        raise RecoveryBlocked("Prerelease creation requires a complete settled backup inventory")
    automatic = [row for row in backups if row["type"] == "auto"]
    manual_ids = {row["id"] for row in backups if row["type"] == "manual"}
    records = weekly_ledger(state, policy)
    if len(automatic) > policy.copies or len(records) > policy.weekly_copies:
        raise RecoveryBlocked("Prerelease copy would exceed the reviewed retention allowance")
    if manual_ids != {row["id"] for row in records}:
        raise RecoveryBlocked("Foreign or bootstrap manual copies occupy prerelease capacity")
    _require_resolved_backup_receipts(state, backups, records)
    confirm_weekly_inventory(client, state, policy, backups)


def _record_release_response(
    ssh: Remote, state: dict[str, Any], receipt: dict[str, Any],
    response: dict[str, Any] | None,
) -> None:
    if response is None:
        return
    if isinstance(response, dict) and response.get("backup") is None:
        return
    item = response.get("backup") if isinstance(response, dict) else None
    identity = item.get("id") if isinstance(item, dict) else None
    if type(identity) is int and identity > 0 and identity not in receipt["baseline_ids"]:
        receipt["response_id"] = identity
        write_state(ssh, state)
        return
    receipt["response_invalid"] = True
    write_state(ssh, state)
    raise RecoveryBlocked("Prerelease creation response has an invalid identity")


def ensure_release_copy(
    client: Provider, ssh: Remote, state: dict[str, Any], policy: BackupPolicy,
    backups: list[dict[str, Any]], *, release_sha: str | None,
) -> list[dict[str, Any]]:
    receipt = _release_receipt(state, policy)
    if receipt is not None:
        if "confirmed_id" not in receipt:
            return _finish_release_copy(client, ssh, state, policy, receipt)
        owned = next((row for row in backups if row["id"] == receipt["confirmed_id"]), None)
        if owned is not None and completed_backup(owned, datetime.now(UTC)):
            _verify_release_item(owned, receipt)
            detail = confirm_backup(client, policy.cluster_id, receipt["confirmed_id"])
            _verify_release_item(detail, receipt)
        return backups
    if release_sha is None or any(completed_backup(row, datetime.now(UTC)) for row in backups):
        return backups
    _require_release_capacity(client, state, policy, backups)
    # This singleton is never cleared or replaced, including for a later accepted release.
    receipt = {
        "cluster_id": policy.cluster_id, "release_sha": release_sha,
        "comment": RELEASE_PREFIX + release_sha,
        "attempted_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "baseline_ids": sorted(row["id"] for row in backups),
    }
    state[RELEASE_COPY] = receipt
    write_state(ssh, state)
    response = mutate_once(client, "POST", f"/dbs/{policy.cluster_id}/backups", payload={
        "comment": receipt["comment"],
    })
    _record_release_response(ssh, state, receipt, response)
    return _finish_release_copy(client, ssh, state, policy, receipt)


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
        period = record.get("period", "")
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


def ensure_recovery_point(
    client: Provider, ssh: Remote, cluster: dict[str, Any], *, release_sha: str | None = None,
) -> None:
    if release_sha is not None:
        _require_release_sha(release_sha)
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
        backups = ensure_release_copy(
            client, ssh, state, policy, backups, release_sha=release_sha,
        )
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


MAX_LOGICAL_ARCHIVE_BYTES = 64 * 1024 * 1024
RESTORE_ROOT = pathlib.Path(__file__).resolve().parents[2]
ENCRYPTED_ARCHIVE_NAME = "database.dump.encrypted"
_RESTORE_ARTIFACT_NAMES = frozenset({
    ENCRYPTED_ARCHIVE_NAME, "manifest.json", "restore-verification.json",
})


def restore_artifact_path(name: str | None = None) -> pathlib.Path:
    """Only this checkout's fixed artifact tree; never follow links or caller paths."""
    if name is not None and name not in _RESTORE_ARTIFACT_NAMES:
        raise RecoveryBlocked("Unexpected restore artifact name")
    root = RESTORE_ROOT
    if not root.is_absolute() or not root.is_dir() or root.resolve() != root:
        raise RecoveryBlocked("Restore workspace is not the owned checkout")
    current = root
    parts = ("artifacts", "restore") + ((name,) if name is not None else ())
    for part in parts:
        current = current / part
        if current.is_symlink() or current.is_junction() or current.resolve() != current:
            raise RecoveryBlocked("Restore artifact path contains a link or escapes its workspace")
    return current


def _private_json(name: str, payload: dict[str, Any]) -> None:
    path = restore_artifact_path(name)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    with path.open("x", encoding="utf-8") as output:
        os.chmod(path, 0o600)
        output.write(encoded)


def _postgres_process(binary: pathlib.Path, arguments: list[str], dsn: str) -> None:
    """Credentials exist only in the child environment; native output never reaches logs."""
    from psycopg.conninfo import conninfo_to_dict

    options = conninfo_to_dict(dsn)
    allowed = {
        "host": "PGHOST", "port": "PGPORT", "dbname": "PGDATABASE", "user": "PGUSER",
        "password": "PGPASSWORD", "sslmode": "PGSSLMODE", "sslrootcert": "PGSSLROOTCERT",
        "sslcert": "PGSSLCERT", "sslkey": "PGSSLKEY", "connect_timeout": "PGCONNECT_TIMEOUT",
    }
    if set(options) - allowed.keys():
        raise RecoveryBlocked("Unsupported database connection option for the restore drill")
    environment = {key: value for key, value in os.environ.items()
                   if key in {"SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATH", "LANG"}}
    environment.update({allowed[key]: str(value) for key, value in options.items()
                        if value is not None})
    environment["PGOPTIONS"] = "-c statement_timeout=900000 -c lock_timeout=15000"
    try:
        result = subprocess.run(
            [str(binary), *arguments], env=environment, capture_output=True,
            check=False, timeout=900,
        )
    except (OSError, subprocess.SubprocessError):
        raise RecoveryBlocked("PostgreSQL restore-drill command did not complete") from None
    if result.returncode != 0:
        raise RecoveryBlocked("PostgreSQL restore-drill command failed; no receipt was issued")


def export_logical_archive(
    source_dsn: str, binary: pathlib.Path, *,
    cluster_id: int, release_sha: str, signing_key: str, archive_key: str,
) -> dict[str, Any]:
    """Explicit operator export, not the scheduled physical-backup reconciler."""
    import psycopg
    from cryptography.fernet import Fernet

    from omnicio import recovery as contract

    # Validate custody before opening the source. The accepted-main runner proves
    # the source host against Timeweb before invoking this function.
    contract.sign_recovery_evidence({}, signing_key)
    cipher = Fernet(archive_key)
    destination = restore_artifact_path()
    destination.parent.mkdir(mode=0o700, exist_ok=True)
    restore_artifact_path().mkdir(mode=0o700, exist_ok=False)
    suffix = ".exe" if os.name == "nt" else ""
    try:
        with tempfile.TemporaryDirectory(prefix="omnicio-logical-") as temporary:
            dump = pathlib.Path(temporary) / "database.dump"
            with psycopg.connect(source_dsn) as source:
                source.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                source.execute("SET LOCAL statement_timeout = '120s'")
                system_id = str(cast(tuple[Any, ...], source.execute(
                    "SELECT system_identifier FROM pg_control_system()",
                ).fetchone())[0])
                snapshot = cast(tuple[Any, ...], source.execute(
                    "SELECT pg_export_snapshot()",
                ).fetchone())[0]
                source_at = cast(tuple[Any, ...], source.execute(
                    "SELECT now()",
                ).fetchone())[0].isoformat()
                fingerprints = contract.table_fingerprints(source)
                guards = contract.database_guards(source)
                if not {"users", "sessions", "workspace_preferences", "workspace_events",
                        "investment_goals", "strategy_drafts"}.issubset(fingerprints):
                    raise RecoveryBlocked("Source database is not the accepted application schema")
                _postgres_process(binary / f"pg_dump{suffix}", [
                    "--format=custom", "--no-password", "--no-owner", "--no-acl",
                    "--snapshot", snapshot, "--file", str(dump),
                ], source_dsn)
            if not 0 < dump.stat().st_size <= MAX_LOGICAL_ARCHIVE_BYTES:
                raise RecoveryBlocked("Logical backup exceeds the reviewed export size limit")
            raw = dump.read_bytes()
            if not raw.startswith(b"PGDMP"):
                raise RecoveryBlocked("Expected a PostgreSQL custom archive")
            encrypted = cipher.encrypt(raw)
            archive = restore_artifact_path(ENCRYPTED_ARCHIVE_NAME)
            with archive.open("xb") as output:
                os.chmod(archive, 0o600)
                output.write(encrypted)
            payload = {
                "kind": "logical_export_v1", "source_kind": "runtime_pg_dump",
                "cluster_id": cluster_id, "release_sha": release_sha,
                "source_at": source_at, "source_system_id": system_id,
                "archive_sha256": hashlib.sha256(raw).hexdigest(),
                "encrypted_sha256": hashlib.sha256(encrypted).hexdigest(),
                "content_digest": contract.evidence_digest(fingerprints),
                "schema_digest": contract.evidence_digest(guards),
            }
            envelope = contract.sign_recovery_evidence(payload, signing_key)
            _private_json("manifest.json", envelope)
            return envelope
    except (OSError, ValueError, psycopg.Error):
        raise RecoveryBlocked("Logical export failed; no restore proof exists") from None


def _restore_tenant_checks(connection: Any, role: str, guards: list[Any]) -> None:
    from psycopg import sql

    tables = sorted({row[0] for row in guards if row[1]})
    if not tables or any(row[1] and not row[2] for row in guards):
        raise RecoveryBlocked("Restored tenant tables do not force row-level security")
    users = [str(row[0]) for row in connection.execute("SELECT id FROM users LIMIT 2").fetchall()]
    users.append("00000000-0000-0000-0000-000000000000")
    connection.execute(sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA public TO {}").format(
        sql.Identifier(role),
    ))
    with connection.transaction():
        connection.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
        for identity in [None, *users]:
            connection.execute("SELECT set_config('omnicio.user_id', %s, true)", (identity or "",))
            predicate = sql.SQL("") if identity is None else sql.SQL(" WHERE user_id <> %s::uuid")
            parameters = () if identity is None else (identity,)
            for name in tables:
                query = sql.SQL("SELECT count(*) FROM {}{}").format(
                    sql.Identifier("public", name), predicate,
                )
                count = connection.execute(query, parameters).fetchone()[0]
                if count != 0:
                    raise RecoveryBlocked("Restored tenant isolation check failed")


def _read_logical_export(
    envelope: object, *, release_sha: str,
    signing_key: str, archive_key: str,
) -> tuple[dict[str, Any], bytes]:
    from cryptography.fernet import Fernet, InvalidToken

    from omnicio import recovery as contract

    archive = restore_artifact_path(ENCRYPTED_ARCHIVE_NAME)
    proof = contract.verified_recovery_evidence(envelope, signing_key)
    required = {"kind", "source_kind", "cluster_id", "release_sha", "source_at",
                "source_system_id", "archive_sha256", "encrypted_sha256",
                "content_digest", "schema_digest"}
    if (proof is None or set(proof) != required or proof["kind"] != "logical_export_v1"
            or proof["source_kind"] != "runtime_pg_dump" or proof["release_sha"] != release_sha
            or proof["cluster_id"] != load_policy().cluster_id):
        raise RecoveryBlocked("A matching accepted-main signed export manifest is required")
    if not 0 < archive.stat().st_size <= MAX_LOGICAL_ARCHIVE_BYTES * 2:
        raise RecoveryBlocked("Encrypted logical archive exceeds the reviewed size limit")
    encrypted = archive.read_bytes()
    if hashlib.sha256(encrypted).hexdigest() != proof["encrypted_sha256"]:
        raise RecoveryBlocked("Encrypted archive differs from its signed export")
    try:
        raw = Fernet(archive_key).decrypt(encrypted)
    except (InvalidToken, ValueError):
        raise RecoveryBlocked("Logical archive cannot be authenticated or decrypted") from None
    if (len(raw) > MAX_LOGICAL_ARCHIVE_BYTES or not raw.startswith(b"PGDMP")
            or hashlib.sha256(raw).hexdigest() != proof["archive_sha256"]):
        raise RecoveryBlocked("Archive is not the authenticated PostgreSQL logical export")
    return proof, raw


def verify_logical_archive(
    isolated_dsn: str, binary: pathlib.Path, envelope: object, *,
    release_sha: str, signing_key: str, archive_key: str,
) -> dict[str, Any]:
    """Restore only into a newly created database on another loopback cluster."""
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict, make_conninfo

    from omnicio import recovery as contract

    proof, raw = _read_logical_export(
        envelope, release_sha=release_sha, signing_key=signing_key,
        archive_key=archive_key,
    )
    options = conninfo_to_dict(isolated_dsn)
    if (options.get("host") not in {"127.0.0.1", "::1"}
            or options.get("dbname") not in {"postgres", "omnicio_test"}
            or "hostaddr" in options or "service" in options):
        raise RecoveryBlocked("Restore destination must be an explicitly isolated loopback cluster")
    started = time.monotonic()
    name = "omnicio_restore_" + secrets.token_hex(12)
    role = name + "_role"
    created_database = created_role = False
    suffix = ".exe" if os.name == "nt" else ""
    with psycopg.connect(isolated_dsn, autocommit=True) as control:
        target_system_id = str(cast(tuple[Any, ...], control.execute(
            "SELECT system_identifier FROM pg_control_system()",
        ).fetchone())[0])
        if target_system_id == proof["source_system_id"]:
            raise RecoveryBlocked("Source and restore destination are the same PostgreSQL cluster")
        try:
            control.execute(sql.SQL(
                "CREATE ROLE {} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                "NOREPLICATION NOBYPASSRLS",
            ).format(sql.Identifier(role)))
            created_role = True
            control.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(
                sql.Identifier(name), sql.Identifier(role),
            ))
            created_database = True
            target_dsn = make_conninfo(isolated_dsn, dbname=name)
            with tempfile.TemporaryDirectory(prefix="omnicio-restore-") as temporary:
                dump = pathlib.Path(temporary) / "database.dump"
                with dump.open("xb") as output:
                    os.chmod(dump, 0o600)
                    output.write(raw)
                _postgres_process(binary / f"pg_restore{suffix}", [
                    "--exit-on-error", "--single-transaction", "--no-password", "--no-owner",
                    "--no-acl", "--dbname", name, "--role", role, str(dump),
                ], target_dsn)
            with psycopg.connect(target_dsn, autocommit=True) as restored:
                if (contract.evidence_digest(contract.table_fingerprints(restored))
                        != proof["content_digest"]):
                    raise RecoveryBlocked("Restored contents differ from the source snapshot")
                guards = contract.database_guards(restored)
                if contract.evidence_digest(guards) != proof["schema_digest"]:
                    raise RecoveryBlocked("Restored schema guards differ from the source")
                if cast(tuple[Any, ...], restored.execute(
                    "SELECT count(*) FROM pg_constraint WHERE contype = 'f' AND NOT convalidated",
                ).fetchone())[0]:
                    raise RecoveryBlocked("Restored foreign keys are not validated")
                _restore_tenant_checks(restored, role, guards)
        finally:
            # Names are generated in this run; existing databases are never
            # restored, overwritten or removed. Failed cleanup suppresses proof.
            if created_database:
                control.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                    sql.Identifier(name),
                ))
            if created_role:
                control.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))
    payload = {
        "kind": "logical_restore_v1", "source_kind": "runtime_pg_dump",
        "cluster_id": proof["cluster_id"], "release_sha": release_sha,
        "source_at": proof["source_at"], "source_system_id": proof["source_system_id"],
        "target_system_id": target_system_id, "archive_sha256": proof["archive_sha256"],
        "verified_at": datetime.now(UTC).isoformat(),
        "duration_seconds": round(time.monotonic() - started, 3),
        "checks": dict.fromkeys(contract.RESTORE_CHECKS, True),
    }
    return contract.sign_recovery_evidence(payload, signing_key)


def validate_export_source(source: str, client: Any) -> None:
    """Pin a manually supplied source DSN to the observed approved private cluster."""
    from psycopg.conninfo import conninfo_to_dict
    from timeweb_auth_postgres import private_database_endpoint

    values = conninfo_to_dict(source)
    cluster = client.get_database_cluster(load_policy().cluster_id)
    endpoint = private_database_endpoint(cluster)
    if (endpoint is None or values.get("host") != endpoint.host
            or int(str(values.get("port", "5432"))) != endpoint.port
            or values.get("dbname") != os.environ.get("DB_INSTANCE_NAME")
            or not values.get("dbname") or values.get("sslmode") != "verify-full"
            or "hostaddr" in values or "service" in values):
        raise RecoveryBlocked("Export source does not match the verified private production DB")


def install_restore_receipt(ssh: Remote, envelope: dict[str, Any], release_sha: str) -> None:
    """Install signed evidence only into the matching running accepted release.

    The remote runtime independently verifies using its own provisioned key.
    No source rows, archive key, or receipt signing key crosses this SSH call.
    A monotonic merge preserves physical-backup mutation receipts.
    """
    from omnicio import recovery as contract

    _require_release_sha(release_sha)
    verified = contract.verified_recovery_evidence(
        envelope, os.environ.get("OMNICIO_RESTORE_RECEIPT_KEY", ""),
    )
    if (verified is None or verified.get("release_sha") != release_sha
            or verified.get("cluster_id") != load_policy().cluster_id
            or contract._restore_verification({
                "cluster_id": load_policy().cluster_id, "restore_verification": envelope,
            }, datetime.now(UTC))["status"] != "verified"):
        raise RecoveryBlocked("Restore proof is invalid or belongs to another accepted release")
    encoded = json.dumps(envelope, ensure_ascii=True, separators=(",", ":"))
    command = ("set -a && . /etc/omnicio/runtime.env && . /etc/omnicio/product.env && "
               "set +a && /opt/omnicio/current/.venv/bin/python -")
    result = ssh.run(command, input_text=f"""
import json, os, pathlib
from datetime import UTC, datetime
from omnicio.recovery import _restore_verification, verified_recovery_evidence
path = pathlib.Path({REMOTE_STATUS_PATH!r})
if pathlib.Path('/opt/omnicio/current').resolve().name != {release_sha!r}:
    raise SystemExit('release changed')
if not path.is_file() or path.stat().st_size > 16384:
    raise SystemExit('recovery state unavailable')
state = json.loads(path.read_text(encoding='utf-8'))
if (not isinstance(state, dict) or state.get('schema_version') != 1
        or state.get('cluster_id') != {load_policy().cluster_id}):
    raise SystemExit('recovery cluster differs')
envelope = json.loads({encoded!r})
candidate = dict(state, restore_verification=envelope)
if _restore_verification(candidate, datetime.now(UTC))['status'] != 'verified':
    raise SystemExit('runtime cannot verify proof')
previous = verified_recovery_evidence(
    state.get('restore_verification'), os.environ.get('OMNICIO_RESTORE_RECEIPT_KEY', ''))
if previous and datetime.fromisoformat(previous['verified_at']) > datetime.fromisoformat(
        envelope['payload']['verified_at']):
    raise SystemExit('newer restore proof already exists')
encoded = json.dumps(candidate, ensure_ascii=True, separators=(',', ':'))
if len(encoded.encode()) > 16384:
    raise SystemExit('recovery state exceeds limit')
temp = path.with_suffix('.restore-new')
try:
    with temp.open('x', encoding='utf-8') as output:
        output.write(encoded)
        output.flush()
        os.fsync(output.fileno())
    os.chmod(temp, 0o644)
    temp.replace(path)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
finally:
    if temp.exists():
        temp.unlink()
readback = json.loads(path.read_text(encoding='utf-8'))
if readback.get('restore_verification') != envelope:
    raise SystemExit('restore proof readback differs')
print('restore_receipt_installed')
""")
    if result.strip() != "restore_receipt_installed":
        raise RecoveryBlocked("Runtime restore proof installation was not confirmed")


if __name__ == "__main__":
    raise SystemExit("Use the accepted-main manual restore workflow; standalone paths are refused")
