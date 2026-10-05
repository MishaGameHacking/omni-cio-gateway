"""Expose bounded backup evidence without claiming that a restore was verified."""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

from .freshness import FreshnessDTO, describe_freshness

INVENTORY_MAX_AGE = timedelta(hours=8)
BACKUP_MAX_AGE = timedelta(hours=24)
BACKUP_TIMEZONE = timezone(timedelta(hours=3))


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value)
    except ValueError:
        return None
    return result.astimezone(UTC) if result.tzinfo else None


def _read_evidence() -> dict[str, object]:
    """The file is produced by accepted-main infrastructure, never by HTTP input."""
    configured = os.environ.get("OMNICIO_RECOVERY_STATUS_PATH", "")
    if not configured:
        return {}
    try:
        with Path(configured).open("rb") as handle:
            raw = handle.read(8193)
        if len(raw) > 8192:
            return {}
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and parsed.get("schema_version") == 1:
            return parsed
    except (OSError, ValueError):
        # Missing, truncated or inaccessible evidence never becomes a green badge.
        return {}
    return {}


def _weekly_evidence(payload: dict[str, object], now: datetime) -> tuple[FreshnessDTO, int | None]:
    created = _timestamp(payload.get("latest_weekly_backup_at"))
    due = _timestamp(payload.get("weekly_next_due_at"))
    copies = payload.get("weekly_available_copies")
    valid = (
        created is not None and due is not None
        and type(copies) is int and 1 <= copies <= 4
        and type(payload.get("weekly_retention_copies")) is int
        and payload["weekly_retention_copies"] == 4
    )
    max_age = timedelta(days=7)
    if valid and created is not None and due is not None:
        local = created.astimezone(BACKUP_TIMEZONE)
        monday = (local - timedelta(days=local.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0,
        )
        valid = due == monday + timedelta(days=7)
        valid = valid and payload.get("weekly_period") == monday.date().isoformat()
        if valid:
            max_age = due - created
    freshness = describe_freshness(
        created if valid else None, max_age=max_age, coverage="complete", now=now,
    )
    return freshness, copies if type(copies) is int and freshness.status == "fresh" else None


def recovery_status(*, now: datetime | None = None) -> dict[str, object]:
    checked_at = now or datetime.now(UTC)
    payload = _read_evidence()

    inventory = describe_freshness(
        _timestamp(payload.get("observed_at")), max_age=INVENTORY_MAX_AGE,
        coverage="complete" if payload.get("provider_status") == "ok" else "unknown",
        now=checked_at,
    )
    backup = describe_freshness(
        _timestamp(payload.get("latest_backup_at")), max_age=BACKUP_MAX_AGE,
        coverage="complete", now=checked_at,
    )
    weekly, weekly_copies = _weekly_evidence(payload, checked_at)
    copies = payload.get("retention_copies")
    if type(copies) is not int or not 1 <= copies <= 99:
        copies = None
    daily = payload.get("schedule_enabled") is True and payload.get("schedule_interval") == "day"
    status = "unavailable"
    if inventory.status == "stale":
        status = "check_stale"
    elif inventory.status == "fresh":
        if backup.status == "unavailable":
            status = "missing"
        elif backup.status == "stale":
            status = "backup_stale"
        elif not daily or copies is None or copies < 7:
            status = "schedule_attention"
        elif weekly.status != "fresh":
            status = "weekly_attention"
        else:
            status = "fresh"
    return {
        "status": status,
        "checked_at": checked_at,
        "freshness": asdict(inventory),
        "backup": asdict(backup),
        "daily_schedule": daily if inventory.status == "fresh" else None,
        "retention_copies": copies if inventory.status == "fresh" else None,
        "weekly": {
            **asdict(weekly),
            "available_copies": weekly_copies if inventory.status == "fresh" else None,
            "retention_copies": (
                4 if weekly_copies is not None and inventory.status == "fresh" else None
            ),
        },
        "production_restore_verified": False,
    }
