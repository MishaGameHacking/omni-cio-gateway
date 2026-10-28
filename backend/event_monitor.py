"""Resumable event-only collection without refreshing prices or valuation time."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import time
from typing import Any

from fastapi import HTTPException

try:
    from . import volume_state as state, volume_workspace as workspace
    from . import autonomous_controller as controller, public_sources
    from .volume_contract import digest, now_iso
    from .market_schedule import instant
except ImportError:
    import volume_state as state
    import volume_workspace as workspace
    import autonomous_controller as controller
    import public_sources
    from volume_contract import digest, now_iso
    from market_schedule import instant


MAX_METADATA_REPAIRS = 5
METADATA_SCHEDULING_SECONDS = 15
COMPLETED_OPERATION_RECHECK_SECONDS = 600
PAYOUT_CHECKPOINT_SECONDS = 3600
AUTHORIZATION_STATUSES = frozenset({401, 403, 409})


def _basis(snapshot: dict) -> str:
    return digest({"currency": snapshot.get("currency"),
        "accounts": sorted(row["id"] for row in snapshot.get("accounts", [])),
        "holdings": sorted((row["account_id"], row["instrument_uid"], row.get("quantity"))
                           for row in snapshot.get("positions", []))})


def _sources(snapshot: dict, extra: list) -> list:
    # Preserve references used by retained positions and attribution. A fresh
    # event pass must not discard the evidence for an older valuation.
    needed, stack = set(), [value for key, value in snapshot.items() if key != "sources"]
    while stack:
        value = stack.pop()
        if isinstance(value, dict):
            needed.update(item for item in value.get("source_ids", []) if isinstance(item, str))
            if isinstance(value.get("id"), str) and "method" in value and "provider" in value:
                needed.add(value["id"])
            stack.extend(value.values())
        elif isinstance(value, list):
            stack.extend(value)
    retained = [ref for ref in snapshot.get("sources", []) if ref.get("id") in needed
                or ref.get("method") in {"GetPortfolio", "GetPortfolio/GetPositions"}]
    return list({ref["id"]: ref for ref in retained + extra}.values())


def _exchange_known(position: dict) -> bool:
    metadata = position.get("metadata")
    value = metadata.get("exchange") if isinstance(metadata, dict) else None
    return isinstance(value, str) and 0 < len(value) <= 100 and value == value.strip()


def _metadata_attempts(snapshot: dict, checkpoint: dict, missing: set) -> dict:
    previous = snapshot.get("event_monitor", {}).get("metadata_last_attempted", {})
    attempted = {uid: at for uid, at in previous.items() if uid in missing and isinstance(at, str)}
    attempted.update({uid: at for uid, at in checkpoint.get("exchange_metadata_attempted", {}).items()
                      if uid in missing and isinstance(at, str)})
    checkpoint["exchange_metadata_attempted"] = attempted
    return attempted


def _read_exchange(user: Any, uid: str) -> dict | None:
    try:
        raw = workspace.market.instrument(user, uid)
    except HTTPException as error:
        if error.status_code in AUTHORIZATION_STATUSES:
            raise
        return None
    return raw if _exchange_known({"metadata": raw}) else None


def _apply_exchange(positions: list, uid: str, raw: dict) -> None:
    for row in positions:
        if row["instrument_uid"] != uid or _exchange_known(row):
            continue
        metadata = deepcopy(row.get("metadata") or {})
        metadata["exchange"] = raw["exchange"]
        if raw.get("_source"):
            metadata["exchange_source"] = deepcopy(raw["_source"])
        row["metadata"] = metadata


def _metadata_snapshot_id(snapshot: dict) -> str:
    return digest({
        "positions": snapshot.get("positions", []), "capital": snapshot.get("capital"),
        "as_of": snapshot["as_of"], "position_coverage": snapshot.get("position_coverage"),
        "rating_signature": snapshot.get("rating_signature"),
    })


def _repair_exchange_metadata(user: Any, snapshot: dict, checkpoint: dict, progress) -> tuple[int, bool, dict]:
    """Bounded, fair venue repair in the event lane, independent of prices."""
    positions = [row for row in snapshot.get("positions", [])
                 if row.get("instrument_type") in {"share", "bond"}]
    missing = {row["instrument_uid"] for row in positions if not _exchange_known(row)}
    if not missing:
        return 0, True, {}
    attempted = _metadata_attempts(snapshot, checkpoint, missing)
    repaired = 0
    deadline = time.monotonic() + METADATA_SCHEDULING_SECONDS
    ordered = sorted(missing, key=lambda value: (attempted.get(value, ""), value))
    for uid in ordered[:MAX_METADATA_REPAIRS]:
        if time.monotonic() >= deadline:
            break
        progress("collecting_metadata", checkpoint)
        attempted[uid] = now_iso()
        raw = _read_exchange(user, uid)
        if raw is not None:
            _apply_exchange(positions, uid, raw)
            repaired += 1
            if raw.get("_source"):
                snapshot.setdefault("sources", []).append(raw["_source"])
        progress("collecting_metadata", checkpoint)
    if repaired:
        snapshot["snapshot_id"] = _metadata_snapshot_id(snapshot)
    remaining = {row["instrument_uid"] for row in positions if not _exchange_known(row)}
    return repaired, not remaining, {uid: at for uid, at in attempted.items() if uid in remaining}


def _refresh_completed_lanes(checkpoint: dict, snapshot: dict, now: datetime) -> None:
    """Only completed operation windows advance; incomplete cursors survive."""
    operations = checkpoint.get("operations", {})
    accounts = [row["id"] for row in snapshot.get("accounts", [])]
    all_complete = bool(accounts) and all(operations.get(account, {}).get("complete") is True for account in accounts)
    age = (now - instant(checkpoint["event_started_at"])).total_seconds()
    if all_complete and age >= COMPLETED_OPERATION_RECHECK_SECONDS:
        checkpoint.pop("operations", None)
        checkpoint.pop("event_operations_begin", None)
        checkpoint["event_started_at"] = now.isoformat()
    payments = checkpoint.get("payments", {})
    for uid, saved in list(payments.items()):
        try:
            age = (now - instant(saved.get("as_of"))).total_seconds()
        except (TypeError, ValueError, OverflowError):
            age = -1
        if not 0 <= age < PAYOUT_CHECKPOINT_SECONDS:
            payments.pop(uid)


def _checkpoint_reusable(checkpoint: dict, basis: str, now: datetime) -> bool:
    try:
        started = instant(checkpoint.get("event_started_at"))
        return 0 <= (now - started).total_seconds() < 86400 and checkpoint.get("event_basis") == basis
    except (TypeError, ValueError):
        return False


def _source_reusable(previous: dict, now: datetime) -> bool:
    try:
        return (previous.get("state") == "available"
                and 0 <= (now - instant(previous.get("as_of"))).total_seconds() < 600)
    except (TypeError, ValueError):
        return False


def _prepare_checkpoint(checkpoint: dict, old: dict, key: str, now: datetime) -> datetime:
    basis = _basis(old)
    if not _checkpoint_reusable(checkpoint, basis, now):
        checkpoint.clear()
        checkpoint.update(broker_key=key, event_basis=basis, event_started_at=now.isoformat())
    _refresh_completed_lanes(checkpoint, old, now)
    for name in ("news", "calendar"):
        previous = checkpoint.get(name)
        if previous is not None and not _source_reusable(previous, now):
            checkpoint.pop(name)
    return instant(checkpoint["event_started_at"])


def _operations_begin(old: dict, started: datetime, checkpoint: dict) -> datetime:
    begin = started - timedelta(days=60)
    try:
        previous_start = instant(old.get("operations", {}).get("start"))
        if started - timedelta(days=366) <= previous_start < started:
            begin = previous_start
    except (TypeError, ValueError):
        pass
    checkpoint.setdefault("event_operations_begin", begin.isoformat())
    return instant(checkpoint["event_operations_begin"])


def _optional_lane(collect, *arguments) -> tuple[list, list, bool]:
    """A source outage is partial data; revoked authorization is never optional."""
    try:
        return collect(*arguments)
    except HTTPException as error:
        if error.status_code in AUTHORIZATION_STATUSES:
            raise
        return [], [], False


def _retained_section_times(new: dict, old: dict) -> dict:
    times = new.setdefault("section_as_of", {})
    for name in ("attribution", "operations", "payouts", "events"):
        if name in old:
            times.setdefault(name, old["as_of"])
    return times


def _apply_market_lanes(new: dict, times: dict, news: dict, calendar: dict) -> tuple[bool, bool]:
    news_ok = news.get("state") == "available" and news.get("data", {}).get("complete", True) is True
    calendar_ok = calendar.get("state") == "available"
    if news.get("state") in {"available", "partial"}:
        new["news"] = news
        new["events"] = {"items": workspace._held_news(new, news), "complete": news_ok}
        times["events"] = news.get("as_of")
    if calendar_ok:
        new["calendar"] = calendar
    return news_ok, calendar_ok


def _apply_cash_lanes(new: dict, old: dict, times: dict, operations: tuple,
                      payments: tuple, begin: datetime, started: datetime) -> None:
    operation_items, _, operations_complete = operations
    payout_items, payout_sources, payouts_complete = payments
    if operations_complete:
        new["operations"] = {"items": operation_items, "complete": True,
                             "start": begin.isoformat(), "end": started.isoformat()}
        times["operations"] = started.isoformat()
    if not payouts_complete:
        return
    payout_observed = min([started] + [instant(ref["observed_at"]) for ref in payout_sources]).isoformat()
    actual_operations = new.get("operations", {}).get("items", [])
    payout_items.extend(workspace._received_payout_events(actual_operations))
    new["payouts"] = {"items": sorted(payout_items, key=lambda row: str(row.get("date")), reverse=True),
        "complete": operations_complete,
        "received_range": {"start": new.get("operations", {}).get("start"),
                           "end": new.get("operations", {}).get("end")},
        "announced_and_received_are_distinct": True,
        "position_basis_at": old["as_of"], "announcements_checked_at": payout_observed}
    times["payouts"] = payout_observed


def _monitor_result(old: dict, key: str, started: datetime, flags: dict, metadata: tuple) -> dict:
    repaired, metadata_ok, attempted = metadata
    checked = now_iso()
    complete = all(flags.values()) and metadata_ok
    result = {"checked_at": checked, "complete": complete,
        "collection_started_at": started.isoformat(), "operations_through": started.isoformat(),
        "last_successful_at": checked if complete else old.get("event_monitor", {}).get("last_successful_at"),
        "news": "available" if flags["news"] else "incomplete",
        "calendar": "available" if flags["calendar"] else "unavailable",
        "operations": "available" if flags["operations"] else "incomplete",
        "payout_announcements": "available" if flags["payouts"] else "incomplete",
        "reviewed_rating_evidence_rechecked": True, "new_rating_sources_fetched": False,
        "valuation_refreshed": False, "valuation_as_of": old["as_of"], "broker_key": key}
    if repaired or attempted or not metadata_ok:
        result.update(instrument_metadata="available" if metadata_ok else "incomplete",
                      metadata_repaired=repaired, metadata_last_attempted=attempted)
    return result


def _persist_events(user: Any, new: dict, old: dict, checkpoint: dict, progress) -> None:
    controller.assert_enabled(int(user["id"]))
    new["public_sources"] = public_sources.collect_snapshot_sources(
        workspace.backend.connect, new, checkpoint, progress)
    new["event_monitor"]["public_identity_sources"] = new["public_sources"]["state"]
    controller.assert_enabled(int(user["id"]))
    progress("persisting_events", checkpoint)
    # Compare the complete old snapshot within the existing transaction. Never
    # overwrite a newer concurrent manual/price/event observation.
    workspace.persist(user, new, expected_snapshot=old)
    if not new["event_monitor"]["complete"]:
        progress("events_partial", checkpoint)
        raise HTTPException(503, "event_sources_incomplete")


def collect_events(user: Any, payload: dict, checkpoint: dict, progress) -> dict:
    key, currency = state.broker_key(user), payload.get("currency", "RUB")
    if checkpoint.get("broker_key") not in {None, key}:
        raise HTTPException(409, "workspace_broker_connection_changed")
    controller.assert_enabled(int(user["id"]))
    old = state.saved_snapshot(user, currency)
    if old is None:
        raise HTTPException(409, "workspace_refresh_required")
    started = _prepare_checkpoint(checkpoint, old, key, datetime.now(timezone.utc))
    progress("collecting_events", checkpoint)
    workspace._collect_market_events(user, checkpoint, progress)
    basis_snapshot = {**old, "as_of": started.isoformat()}
    begin = _operations_begin(old, started, checkpoint)
    operations = _optional_lane(workspace._collect_operations, user, basis_snapshot,
                                begin, started, checkpoint, progress)
    payments = _optional_lane(workspace._payment_events, user, basis_snapshot, checkpoint, progress)
    new = deepcopy(old)
    metadata = _repair_exchange_metadata(user, new, checkpoint, progress)
    times = _retained_section_times(new, old)
    news, calendar = checkpoint["news"], checkpoint["calendar"]
    news_ok, calendar_ok = _apply_market_lanes(new, times, news, calendar)
    _apply_cash_lanes(new, old, times, operations, payments, begin, started)
    flags = {"news": news_ok, "calendar": calendar_ok,
             "operations": operations[2], "payouts": payments[2]}
    new["event_monitor"] = _monitor_result(old, key, started, flags, metadata)
    new["sources"] = _sources(new, operations[1] + payments[1] +
                              news.get("sources", []) + calendar.get("sources", []))
    _persist_events(user, new, old, checkpoint, progress)
    return {"snapshot_id": new["snapshot_id"], "currency": currency,
            "as_of": old["as_of"], "event_monitor": new["event_monitor"]}
