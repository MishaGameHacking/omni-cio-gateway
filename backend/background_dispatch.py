"""Calendar-aware dispatch over the existing durable queues and workspace store.

No new scheduler, paid request, trade permission or broker client lives here.
Opening the status endpoint only reads persisted evidence. Explicit refreshes
remain independent of the automatic price-polling calendar.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import json
from typing import Any

from fastapi import HTTPException

try:
    from . import app as backend, volume_state as state, volume_jobs as jobs
    from . import market_schedule
    from .ai_budget import transaction
    from .ai_jobs import AnalysisQueue
except ImportError:
    import app as backend
    import volume_state as state
    import volume_jobs as jobs
    import market_schedule
    from ai_budget import transaction
    from ai_jobs import AnalysisQueue

EVENT_INTERVAL = 600
PRICE_INTERVAL = 300
EVENT_PREFIX = "auto.events."
ANALYSIS_ORIGIN = "dispatch_analysis"


def _controller():
    try:
        from . import autonomous_controller
    except ImportError:
        import autonomous_controller
    return autonomous_controller


def _age(value: str | None, now: datetime) -> float | None:
    try:
        age = (now - market_schedule.instant(value)).total_seconds()
        return age if age >= 0 else None
    except (ValueError, TypeError, OverflowError):
        return None


def schedule(user: Any, *, now: datetime | None = None, snapshot: dict | None = None) -> dict:
    clock = now or datetime.now(timezone.utc)
    if snapshot is None:
        snapshot = state.saved_snapshot(user, _controller()._currency(int(user["id"])))
    result = market_schedule.polling_state((snapshot or {}).get("calendar"),
        market_schedule.required_exchanges(snapshot), now=clock)
    events = (snapshot or {}).get("event_monitor", {})
    age = _age(events.get("checked_at"), clock)
    result.update(event_monitoring_independent_of_market=True,
                  events=events, event_interval_seconds=EVENT_INTERVAL,
                  price_interval_seconds=PRICE_INTERVAL,
                  events_due_in_seconds=0 if age is None else max(0, int(EVENT_INTERVAL - age)),
                  last_valuation_at=(snapshot or {}).get("as_of"),
                  bootstrap_required=snapshot is None)
    return result


class _PendingEvents(Exception):
    def __init__(self, job_id: str):
        self.job_id = job_id


def enqueue_events(user: Any, *, now: datetime | None = None) -> dict:
    clock = now or datetime.now(timezone.utc)
    user_id = int(user["id"])
    current = _controller()._user(user_id)
    if current is None or not current["tinvest_token_encrypted"]:
        return {"state": "not_connected"}
    if not _controller().preferences(user_id)["enabled"]:
        return {"state": "paused"}
    currency = _controller()._currency(user_id)
    snapshot = state.saved_snapshot(current, currency)
    if snapshot is None:
        return {"state": "awaiting_first_snapshot"}
    age = _age(snapshot.get("event_monitor", {}).get("checked_at"), clock)
    if age is not None and age < EVENT_INTERVAL:
        return {"state": "current"}
    key = state.broker_key(current)
    prefix = EVENT_PREFIX + key + "." + currency + "."
    checkpoint = {"broker_key": key}
    with closing(backend.connect()) as db:
        last = db.execute("""SELECT checkpoint_json FROM workspace_jobs WHERE user_id=? AND request_id LIKE ?
            AND state='failed' AND updated_at>? ORDER BY updated_at DESC,id DESC LIMIT 1""",
            (user_id, prefix + "%", int(clock.timestamp()) - 86400)).fetchone()
    if last is not None:
        prior = json.loads(last[0])
        if prior.get("broker_key") == key:
            checkpoint = prior

    def before_insert(db, _):
        _controller().assert_enabled_in(db, user_id)
        owner = db.execute("SELECT tinvest_token_encrypted FROM users WHERE id=?", (user_id,)).fetchone()
        if owner is None or state.broker_key(owner) != key:
            raise HTTPException(409, "monitoring_connection_changed")
        pending = db.execute("""SELECT id FROM workspace_jobs WHERE user_id=? AND request_id LIKE ?
            AND state IN ('queued','running') AND cancel_requested=0 ORDER BY created_at,id LIMIT 1""",
            (user_id, prefix + "%")).fetchone()
        if pending:
            raise _PendingEvents(pending["id"])

    try:
        return jobs.enqueue(user_id, prefix + str(int(clock.timestamp()) // EVENT_INTERVAL), "events",
            {"currency": currency}, before_insert=before_insert, checkpoint=checkpoint)
    except _PendingEvents as pending:
        return {"state": "coalesced", "job_id": pending.job_id}


def _enqueue_analysis(user: Any, *, automatic: bool, now: datetime) -> dict:
    user_id, key = int(user["id"]), state.broker_key(user)
    with transaction(backend.connect) as db:
        _controller().assert_enabled_in(db, user_id)
        owner = db.execute("SELECT tinvest_token_encrypted FROM users WHERE id=?", (user_id,)).fetchone()
        if owner is None or state.broker_key(owner) != key or key == "disconnected":
            raise HTTPException(409, "monitoring_connection_changed")
        result = AnalysisQueue(backend.connect).enqueue_in(db, user_id, now=int(now.timestamp()))
        if not automatic:
            mark_manual_in(db, user_id, result["job_id"])
        elif not result["coalesced"]:
            state.record(db, user_id, ANALYSIS_ORIGIN, result["job_id"],
                         {"automatic": True, "broker_key": key, "queued_at": now.isoformat()})
        db.execute("""DELETE FROM workspace_records WHERE user_id=? AND kind=? AND updated_at<?
            AND id NOT IN (SELECT id FROM ai_work_jobs WHERE status IN ('queued','running'))""",
            (user_id, ANALYSIS_ORIGIN, int(now.timestamp()) - 7 * 86400))
    return result


def mark_manual_in(db, user_id: int, job_id: str) -> None:
    # If a manual request coalesces with an automatic job, its explicit intent
    # must still permit a read-only check outside the scheduled window.
    db.execute("DELETE FROM workspace_records WHERE user_id=? AND kind=? AND id=?",
               (user_id, ANALYSIS_ORIGIN, job_id))


def enqueue_manual_analysis(user: Any) -> dict:
    return _enqueue_analysis(user, automatic=False, now=datetime.now(timezone.utc))


def automatic_collection_gate(user: Any, payload: dict, checkpoint: dict) -> dict | None:
    if checkpoint.get("broker_key") not in {None, state.broker_key(user)}:
        raise HTTPException(409, "workspace_broker_connection_changed")
    _controller().assert_enabled(int(user["id"]))
    snapshot = state.saved_snapshot(user, payload.get("currency", "RUB"))
    # A first read is necessary to learn which instruments/calendars are needed.
    if snapshot is None:
        return None
    current = schedule(user, snapshot=snapshot)
    if current["regular_price_polling_allowed"]:
        return None
    return {"state": "waiting", "reason": current["reason"], "valuation_refreshed": False}


def automatic_analysis_gate(user: Any, job_context: tuple | None, now: datetime) -> dict | None:
    if job_context is None:
        return None
    with closing(backend.connect()) as db:
        row = db.execute("SELECT payload_json FROM workspace_records WHERE user_id=? AND kind=? AND id=?",
            (int(user["id"]), ANALYSIS_ORIGIN, job_context[0])).fetchone()
    if row is None:
        return None
    origin = json.loads(row[0])
    if origin.get("broker_key") != state.broker_key(user):
        raise HTTPException(409, "monitoring_connection_changed")
    current = schedule(user, now=now)
    return None if current["regular_price_polling_allowed"] else current


def enqueue_cycle(user: Any, *, now: datetime | None = None) -> dict:
    """A cheap persisted-data decision. A failed lane cannot starve another."""
    clock = now or datetime.now(timezone.utc)
    current = _controller()._user(int(user["id"]))
    if current is None or not current["tinvest_token_encrypted"]:
        return {"state": "not_connected"}
    if not _controller().preferences(int(user["id"]))["enabled"]:
        return {"state": "paused"}
    snapshot = state.saved_snapshot(current, _controller()._currency(int(user["id"])))
    window = schedule(current, now=clock, snapshot=snapshot)
    result = {"state": "scheduled", "market": window["state"], "lanes": {}}
    actions = [("events", lambda: enqueue_events(current, now=clock))]
    if snapshot is None or window["regular_price_polling_allowed"]:
        actions.append(("collection", lambda: _controller().enqueue_collection(current, now=clock.timestamp())))
    observed_age = _age((snapshot or {}).get("as_of"), clock)
    if snapshot is not None and window["regular_price_polling_allowed"] and (observed_age is None or observed_age >= PRICE_INTERVAL):
        actions.append(("analysis", lambda: _enqueue_analysis(current, automatic=True, now=clock)))
    for name, action in actions:
        try:
            result["lanes"][name] = action()
        except HTTPException as error:
            result["lanes"][name] = {"state": "deferred", "http_status": error.status_code}
    return result
