"""Server-applied notification rules and acknowledged app-poll delivery.

An outbox row is not a delivered notification. Delivery becomes presented/read
only when the signed-in client acknowledges it. No push provider is implied.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
import time
import uuid
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field

DEFAULT_TIMEZONE = 'Europe/Moscow'


try:
    from . import app as backend
    from .ai_budget import transaction
    from .schema_migrations import execute_schema
    from .volume_state import StrictModel, encode
    from .volume_contract import HTTP_ERRORS, now_iso
except ImportError:
    import app as backend
    from ai_budget import transaction
    from schema_migrations import execute_schema
    from volume_state import StrictModel, encode
    from volume_contract import HTTP_ERRORS, now_iso

router = APIRouter(prefix="/workspace/notifications", tags=["Notification delivery"])
DEFAULTS = {"timezone": DEFAULT_TIMEZONE, "morning": "09:00", "evening": "19:00", "quiet_start": "22:00",
            "quiet_end": "08:00", "briefs_enabled": True, "critical_enabled": True, "enabled": True}
CLOCK_PATTERN = r"^([01][0-9]|2[0-3]):[0-5][0-9]$"


def initialize() -> None:
    # Preferences, outbox and due index are one schema change. Existing delivery
    # states and client acknowledgements must survive every startup unchanged.
    with transaction(backend.connect) as db:
        execute_schema(db, """
            CREATE TABLE IF NOT EXISTS workspace_notification_preferences (
                user_id INTEGER PRIMARY KEY, version INTEGER NOT NULL,
                payload_json TEXT NOT NULL, applied_at INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS workspace_notification_outbox (
                id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, kind TEXT NOT NULL,
                title TEXT NOT NULL, body TEXT NOT NULL, source_card_id TEXT,
                event_id TEXT, created_at INTEGER NOT NULL, state TEXT NOT NULL,
                eligible_at INTEGER NOT NULL, claim_id TEXT, claim_expires_at INTEGER,
                acknowledged_at INTEGER, UNIQUE(user_id,source_card_id), UNIQUE(user_id,event_id));
            CREATE INDEX IF NOT EXISTS workspace_outbox_due ON workspace_notification_outbox(user_id,state,eligible_at);
        """)


class Preferences(StrictModel):
    timezone: str = Field(default=DEFAULT_TIMEZONE, max_length=80)
    morning: str = Field(default="09:00", pattern=CLOCK_PATTERN)
    evening: str = Field(default="19:00", pattern=CLOCK_PATTERN)
    quiet_start: str = Field(default="22:00", pattern=CLOCK_PATTERN)
    quiet_end: str = Field(default="08:00", pattern=CLOCK_PATTERN)
    briefs_enabled: bool = True
    critical_enabled: bool = True
    enabled: bool = True


class PreferencesWrite(Preferences):
    expected_version: int = Field(ge=0)


def validated_preferences(payload: Preferences) -> dict:
    result = payload.model_dump(exclude={"expected_version"})
    try:
        ZoneInfo(result["timezone"])
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(422, "notification_timezone_invalid") from None
    if result["morning"] == result["evening"]:
        raise HTTPException(422, "notification_slots_overlap")
    return result


def _preferences(db, user_id: int) -> tuple[dict, int, int | None]:
    row = db.execute("SELECT * FROM workspace_notification_preferences WHERE user_id=?", (user_id,)).fetchone()
    if row:
        return json.loads(row["payload_json"]), row["version"], row["applied_at"]
    result = dict(DEFAULTS)
    row = db.execute("SELECT notify_critical,notify_briefs FROM analysis_profiles WHERE user_id=?", (user_id,)).fetchone()
    if row:
        result.update(critical_enabled=bool(row[0]), briefs_enabled=bool(row[1]))
    return result, 0, None


def sync_legacy_preferences_in(db, user_id: int, *, critical: bool, briefs: bool, now: int) -> None:
    """Old profile switches and the new delivery rules share one applied state."""
    row = db.execute("SELECT * FROM workspace_notification_preferences WHERE user_id=?", (user_id,)).fetchone()
    if row is None:
        return
    preferences = json.loads(row["payload_json"])
    changed = preferences["critical_enabled"] != critical or preferences["briefs_enabled"] != briefs
    preferences.update(critical_enabled=critical, briefs_enabled=briefs)
    if changed:
        db.execute("UPDATE workspace_notification_preferences SET payload_json=?,version=version+1,applied_at=? WHERE user_id=?",
                   (encode(preferences), now, user_id))
        pending = db.execute("SELECT id,kind FROM workspace_notification_outbox WHERE user_id=? AND state IN ('pending','claimed')", (user_id,)).fetchall()
        for item in pending:
            status, due, _ = eligibility(preferences, item["kind"], now)
            db.execute("UPDATE workspace_notification_outbox SET state=?,eligible_at=?,claim_id=NULL,claim_expires_at=NULL WHERE id=?", (status, due, item["id"]))
    db.execute("UPDATE analysis_profiles SET notify_critical=?,notify_briefs=? WHERE user_id=?",
               (int(critical and preferences["enabled"]), int(briefs and preferences["enabled"]), user_id))


def preferences_data(user_id: int) -> dict:
    with closing(backend.connect()) as db:
        preferences, version, applied = _preferences(db, user_id)
        count = db.execute("SELECT COUNT(*) FROM workspace_notification_outbox WHERE user_id=? AND state IN ('pending','claimed')", (user_id,)).fetchone()[0]
    return {"version": version, "applied": applied is not None, "applied_at": _iso(applied), "preferences": preferences,
            "delivery_channel": "app_poll", "background_delivery_available": False, "pending_count": count}


def _iso(value: int | None) -> str | None:
    return datetime.fromtimestamp(value, timezone.utc).isoformat() if value is not None else None


def eligibility(preferences: dict, kind: str, at: int) -> tuple[str, int, str | None]:
    if not preferences["enabled"] or (kind == "risk" and not preferences["critical_enabled"]) or (kind != "risk" and not preferences["briefs_enabled"]):
        return "suppressed", at, "rule_disabled"
    zone = ZoneInfo(preferences["timezone"])
    local = datetime.fromtimestamp(at, zone)
    minute = local.strftime("%H:%M")
    start, end = preferences["quiet_start"], preferences["quiet_end"]
    quiet = start != end and (start <= minute < end if start < end else minute >= start or minute < end)
    if not quiet:
        return "pending", at, None
    hour, minute_end = map(int, end.split(":"))
    due = local.replace(hour=hour, minute=minute_end, second=0, microsecond=0)
    if due <= local:
        due += timedelta(days=1)
    return "pending", int(due.timestamp()), "quiet_hours"


def enqueue_in(db, user_id: int, *, kind: str, title: str, body: str, source_card_id: str | None = None,
               event_id: str | None = None, at: int | None = None) -> None:
    if not source_card_id and not event_id:
        raise ValueError("notification_source_required")
    at = int(time.time()) if at is None else at
    preferences, _, _ = _preferences(db, user_id)
    state, due, _ = eligibility(preferences, kind, at)
    duplicate = db.execute("""SELECT 1 FROM workspace_notification_outbox
        WHERE user_id=? AND kind=? AND title=? AND body=? AND created_at>? LIMIT 1""",
        (user_id, kind, title[:200], body[:2000], at - 86400)).fetchone()
    if duplicate:
        return
    db.execute("""INSERT OR IGNORE INTO workspace_notification_outbox
        (id,user_id,kind,title,body,source_card_id,event_id,created_at,state,eligible_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (uuid.uuid4().hex, user_id, kind, title[:200], body[:2000], source_card_id, event_id, at, state, due))


def _item(row) -> dict:
    return {key: row[key] for key in ("id", "kind", "title", "body", "state", "source_card_id", "event_id")} | {
        "created_at": _iso(row["created_at"]), "eligible_at": _iso(row["eligible_at"]), "acknowledged_at": _iso(row["acknowledged_at"])}


@router.get("/preferences", responses=HTTP_ERRORS)
def preferences(user: Any = Depends(backend.current_user)) -> dict:
    return preferences_data(int(user["id"]))


@router.put("/preferences", responses=HTTP_ERRORS)
def update_preferences(payload: PreferencesWrite, user: Any = Depends(backend.current_user)) -> dict:
    value, user_id, now = validated_preferences(payload), int(user["id"]), int(time.time())
    with transaction(backend.connect) as db:
        _, version, _ = _preferences(db, user_id)
        if version != payload.expected_version:
            raise HTTPException(409, "notification_preferences_changed")
        db.execute("""INSERT INTO workspace_notification_preferences VALUES (?,?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET version=excluded.version,payload_json=excluded.payload_json,applied_at=excluded.applied_at""",
            (user_id, version + 1, encode(value), now))
        # The deployed monitoring loop reads these existing switches as well.
        db.execute("""INSERT INTO analysis_profiles(user_id,notify_critical,notify_briefs,updated_at) VALUES (?,?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET notify_critical=excluded.notify_critical,notify_briefs=excluded.notify_briefs,updated_at=excluded.updated_at""",
                   (user_id, int(value["critical_enabled"] and value["enabled"]), int(value["briefs_enabled"] and value["enabled"]), now))
        pending = db.execute("SELECT id,kind,created_at FROM workspace_notification_outbox WHERE user_id=? AND state IN ('pending','claimed')", (user_id,)).fetchall()
        for row in pending:
            state, due, _ = eligibility(value, row["kind"], now)
            db.execute("UPDATE workspace_notification_outbox SET state=?,eligible_at=?,claim_id=NULL,claim_expires_at=NULL WHERE id=?", (state, due, row["id"]))
    return preferences_data(user_id)


@router.get("/events", responses=HTTP_ERRORS)
def events(limit: int = 100, user: Any = Depends(backend.current_user)) -> dict:
    with closing(backend.connect()) as db:
        rows = db.execute("SELECT * FROM workspace_notification_outbox WHERE user_id=? ORDER BY created_at DESC,id LIMIT ?", (int(user["id"]), min(max(limit, 1), 500))).fetchall()
    seen, items = set(), []
    with closing(backend.connect()) as db:
        for row in rows:
            key = (row["kind"], row["title"], row["body"])
            if key in seen:
                continue
            seen.add(key)
            item = _item(row)
            item["visual"] = notification_visual(db, int(user["id"]), row)
            items.append(item)
    return {"items": items, "channel": "app_poll"}


def notification_visual(db, user_id: int, row) -> dict:
    event = db.execute("SELECT payload_json FROM workspace_events WHERE user_id=? AND id=?",
                       (user_id, row["event_id"])).fetchone() if row["event_id"] else None
    data = json.loads(event[0]) if event else {}
    kind = data.get("kind", "")
    details = data.get("details", {})
    after = details.get("after") or {}
    severity = "watch" if row["kind"] == "risk" else "info"
    if kind == "risk_limit_resolved":
        severity = "resolved"
    elif after.get("breached"):
        severity = "warning"
    return {"severity": severity, "share_percent": after.get("share_percent"),
            "limit_percent": after.get("limit_percent"), "label": after.get("label"),
            "action": "Проверка сохранена. Торговых поручений система не отправляла."}


class Claim(StrictModel):
    limit: int = Field(default=20, ge=1, le=100)


@router.post("/claim", responses=HTTP_ERRORS)
def claim(payload: Claim, user: Any = Depends(backend.current_user)) -> dict:
    now, user_id = int(time.time()), int(user["id"])
    identifier, expires = uuid.uuid4().hex, now + 120
    with transaction(backend.connect) as db:
        db.execute("UPDATE workspace_notification_outbox SET state='pending',claim_id=NULL,claim_expires_at=NULL WHERE user_id=? AND state='claimed' AND claim_expires_at<=?", (user_id, now))
        preferences, _, _ = _preferences(db, user_id)
        rows = db.execute("SELECT * FROM workspace_notification_outbox WHERE user_id=? AND state='pending' AND eligible_at<=? ORDER BY created_at,id LIMIT ?", (user_id, now, payload.limit)).fetchall()
        items = []
        for row in rows:
            state, due, _ = eligibility(preferences, row["kind"], now)
            if state == "suppressed" or due > now:
                db.execute("UPDATE workspace_notification_outbox SET state=?,eligible_at=? WHERE id=?", (state, due, row["id"]))
                continue
            db.execute("UPDATE workspace_notification_outbox SET state='claimed',claim_id=?,claim_expires_at=? WHERE id=?", (identifier, expires, row["id"]))
            items.append({**_item(row), "state": "claimed"})
    return {"items": items, "claim_id": identifier, "expires_at": _iso(expires)}


class Ack(StrictModel):
    claim_id: str | None = Field(default=None, max_length=80)
    state: Literal["presented", "read"]


@router.post("/{identifier}/ack", responses=HTTP_ERRORS)
def acknowledge(identifier: str, payload: Ack, user: Any = Depends(backend.current_user)) -> dict:
    now = int(time.time())
    with transaction(backend.connect) as db:
        row = db.execute("SELECT * FROM workspace_notification_outbox WHERE id=? AND user_id=?", (identifier, int(user["id"]))).fetchone()
        if row is None:
            raise HTTPException(404, "notification_not_found")
        if payload.state == "presented":
            if not payload.claim_id or row["claim_id"] != payload.claim_id or row["state"] not in {"claimed", "presented", "read"}:
                raise HTTPException(409, "notification_claim_changed")
            if row["state"] == "claimed" and row["claim_expires_at"] < now:
                raise HTTPException(409, "notification_claim_expired")
        state = "read" if row["state"] == "read" else payload.state
        db.execute("UPDATE workspace_notification_outbox SET state=?,acknowledged_at=? WHERE id=?", (state, now, identifier))
    return {"id": identifier, "state": state, "acknowledged_at": _iso(now), "receipt_basis": "client_reported"}


class Preview(StrictModel):
    preferences: Preferences


@router.post("/preview", responses=HTTP_ERRORS)
def preview(payload: Preview, user: Any = Depends(backend.current_user)) -> dict:
    value = validated_preferences(payload.preferences)
    with closing(backend.connect()) as db:
        rows = db.execute("SELECT * FROM workspace_notification_outbox WHERE user_id=? ORDER BY created_at DESC,id LIMIT 1000", (int(user["id"]),)).fetchall()
    matched, suppressed = [], []
    for row in rows:
        state, due, reason = eligibility(value, row["kind"], row["created_at"])
        item = {"id": row["id"], "title": row["title"], "created_at": _iso(row["created_at"]), "eligible_at": _iso(due), "reason": reason}
        (suppressed if state == "suppressed" else matched).append(item)
    return {"matched": matched, "suppressed": suppressed, "evaluated_count": len(rows),
            "history_start": _iso(rows[-1]["created_at"]) if rows else None,
            "history_end": _iso(rows[0]["created_at"]) if rows else None, "sent": False}


def calendar_gate(calendar: dict, market_date: str) -> str:
    days = [day for exchange in calendar.get("data", {}).get("exchanges", []) for day in exchange.get("days", [])
            if str(day.get("date", "")).startswith(market_date)]
    if not days:
        return "awaiting_calendar"
    if any(day.get("isTradingDay") is True for day in days):
        return "scheduled"
    return "market_closed"


def schedule_slots(user_id: int, at: datetime | None = None) -> list[dict]:
    now = at or datetime.now(timezone.utc)
    with closing(backend.connect()) as db:
        preferences, _, _ = _preferences(db, user_id)
        snapshot = db.execute("SELECT payload_json FROM workspace_snapshots WHERE user_id=? AND currency='RUB'", (user_id,)).fetchone()
    if not preferences["enabled"] or not preferences["briefs_enabled"]:
        return []
    data = json.loads(snapshot[0]) if snapshot else {}
    calendar = data.get("calendar", {})
    zone = ZoneInfo(preferences["timezone"])
    local = now.astimezone(zone)
    result = []
    for slot in ("morning", "evening"):
        hour, minute = map(int, preferences[slot].split(":"))
        due = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if due < local:
            due += timedelta(days=1)
        gate = calendar_gate(calendar, due.astimezone(ZoneInfo(DEFAULT_TIMEZONE)).date().isoformat())
        result.append({"slot": slot, "at": due.astimezone(timezone.utc).isoformat(), "gate": gate})
    return result


def due_flags(user_id: int, now: datetime, has_run) -> tuple[bool, bool]:
    with closing(backend.connect()) as db:
        preferences, _, _ = _preferences(db, user_id)
        row = db.execute("SELECT payload_json FROM workspace_snapshots WHERE user_id=? AND currency='RUB'", (user_id,)).fetchone()
    if not preferences["enabled"] or not preferences["briefs_enabled"]:
        return False, False
    calendar = (json.loads(row[0]) if row else {}).get("calendar", {})
    local = now.astimezone(ZoneInfo(preferences["timezone"]))
    market_date = now.astimezone(ZoneInfo(DEFAULT_TIMEZONE)).date().isoformat()
    if calendar_gate(calendar, market_date) != "scheduled":
        return False, False
    flags = []
    for slot in ("morning", "evening"):
        hour, minute = map(int, preferences[slot].split(":"))
        due = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        flags.append(0 <= (local - due).total_seconds() <= 7200 and not has_run(slot, local))
    return tuple(flags)

