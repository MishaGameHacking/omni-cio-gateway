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


def _basis(snapshot: dict) -> str:
    return digest({"currency": snapshot.get("currency"),
        "accounts": sorted(row["id"] for row in snapshot.get("accounts", [])),
        "holdings": sorted((row["account_id"], row["instrument_uid"], row.get("quantity"))
                           for row in snapshot.get("positions", []))})


def _sources(snapshot: dict, extra: list) -> list:
    # Keep provenance still referenced by retained attribution/positions, while
    # avoiding an ever-growing list of superseded news/calendar observations.
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


MAX_METADATA_REPAIRS = 5
METADATA_SCHEDULING_SECONDS = 15
COMPLETED_OPERATION_RECHECK_SECONDS = 600
PAYOUT_CHECKPOINT_SECONDS = 3600


def _exchange_known(position: dict) -> bool:
    metadata = position.get("metadata")
    value = metadata.get("exchange") if isinstance(metadata, dict) else None
    return isinstance(value, str) and 0 < len(value) <= 100 and value == value.strip()


def _repair_exchange_metadata(user: Any, snapshot: dict, checkpoint: dict, progress) -> tuple[int, bool, dict]:
    """Heal a failed metadata bootstrap without fetching prices or guessing a venue.

    Missing metadata prevents automatic valuation, so its repair must live in
    the independent event lane. Attempts rotate across a large portfolio; one
    unavailable instrument cannot permanently starve later instruments.
    """
    positions = [row for row in snapshot.get("positions", [])
                 if row.get("instrument_type") in {"share", "bond"}]
    missing = {row["instrument_uid"] for row in positions if not _exchange_known(row)}
    if not missing:
        return 0, True, {}
    # Keep fairness in the materialized event state as well as the job. A
    # holdings change resets paginated operations, not metadata retry order.
    previous = snapshot.get("event_monitor", {}).get("metadata_last_attempted", {})
    attempted = {uid: at for uid, at in previous.items() if uid in missing and isinstance(at, str)}
    attempted.update({uid: at for uid, at in checkpoint.get("exchange_metadata_attempted", {}).items()
                      if uid in missing and isinstance(at, str)})
    checkpoint["exchange_metadata_attempted"] = attempted
    repaired = 0
    deadline = time.monotonic() + METADATA_SCHEDULING_SECONDS
    for uid in sorted(missing, key=lambda value: (attempted.get(value, ""), value))[:MAX_METADATA_REPAIRS]:
        if time.monotonic() >= deadline:
            break
        progress("collecting_metadata", checkpoint)
        attempted[uid] = now_iso()
        try:
            raw = workspace.market.instrument(user, uid)
        except HTTPException as error:
            if error.status_code in {401, 403, 409}:
                raise
            progress("collecting_metadata", checkpoint)
            continue
        if not _exchange_known({"metadata": raw}):
            progress("collecting_metadata", checkpoint)
            continue
        for row in positions:
            if row["instrument_uid"] == uid and not _exchange_known(row):
                # A missing exchange does not invalidate other metadata. Keep
                # its existing provenance, and attach this field's own source.
                metadata = deepcopy(row.get("metadata") or {})
                metadata["exchange"] = raw["exchange"]
                if raw.get("_source"):
                    metadata["exchange_source"] = deepcopy(raw["_source"])
                row["metadata"] = metadata
        repaired += 1
        if raw.get("_source"):
            snapshot.setdefault("sources", []).append(raw["_source"])
        progress("collecting_metadata", checkpoint)
    if repaired:
        snapshot["snapshot_id"] = digest({
            "positions": snapshot.get("positions", []), "capital": snapshot.get("capital"),
            "as_of": snapshot["as_of"], "position_coverage": snapshot.get("position_coverage"),
            "rating_signature": snapshot.get("rating_signature"),
        })
    remaining = {row["instrument_uid"] for row in positions if not _exchange_known(row)}
    return repaired, not remaining, {uid: at for uid, at in attempted.items() if uid in remaining}


def _refresh_completed_lanes(checkpoint: dict, snapshot: dict, now: datetime) -> None:
    """A failed news source must not freeze independent completed cash lanes.

    An unfinished paginator retains its original upper bound and cursor. Only
    a completely collected operation window can advance to a newer horizon.
    Payout checkpoints use the existing per-source one-hour validity period.
    """
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




def collect_events(user: Any, payload: dict, checkpoint: dict, progress) -> dict:
    key, currency = state.broker_key(user), payload.get("currency", "RUB")
    if checkpoint.get("broker_key") not in {None, key}:
        raise HTTPException(409, "workspace_broker_connection_changed")
    controller.assert_enabled(int(user["id"]))
    old = state.saved_snapshot(user, currency)
    if old is None:
        raise HTTPException(409, "workspace_refresh_required")
    now = datetime.now(timezone.utc)
    basis = _basis(old)
    try:
        started = instant(checkpoint.get("event_started_at"))
        reusable = 0 <= (now - started).total_seconds() < 86400 and checkpoint.get("event_basis") == basis
    except (TypeError, ValueError):
        reusable = False
    if not reusable:
        checkpoint.clear()
        checkpoint.update(broker_key=key, event_basis=basis, event_started_at=now.isoformat())
    _refresh_completed_lanes(checkpoint, old, now)
    started = instant(checkpoint["event_started_at"])
    for name in ("news", "calendar"):
        previous = checkpoint.get(name)
        if previous is not None:
            try:
                reusable_source = previous.get("state") == "available" and 0 <= (now - instant(previous.get("as_of"))).total_seconds() < 600
            except (TypeError, ValueError):
                reusable_source = False
            if not reusable_source:
                checkpoint.pop(name)
    progress("collecting_events", checkpoint)
    workspace._collect_market_events(user, checkpoint, progress)
    # The event horizon follows the collector clock. It is not the timestamp of
    # the last portfolio valuation and cannot relabel that valuation as current.
    basis_snapshot = {**old, "as_of": started.isoformat()}
    begin = started - timedelta(days=60)
    try:
        previous_start = instant(old.get("operations", {}).get("start"))
        if started - timedelta(days=366) <= previous_start < started:
            begin = previous_start
    except (TypeError, ValueError):
        pass
    checkpoint.setdefault("event_operations_begin", begin.isoformat())
    begin = instant(checkpoint["event_operations_begin"])
    operations, operation_sources, operations_complete = [], [], False
    payouts, payout_sources, payouts_complete = [], [], False
    try:
        operations, operation_sources, operations_complete = workspace._collect_operations(
            user, basis_snapshot, begin, started, checkpoint, progress)
    except HTTPException as error:
        if error.status_code in {401, 403, 409}:
            raise
    try:
        payouts, payout_sources, payouts_complete = workspace._payment_events(user, basis_snapshot, checkpoint, progress)
    except HTTPException as error:
        if error.status_code in {401, 403, 409}:
            raise
    new = deepcopy(old)
    metadata_repaired, metadata_ok, metadata_attempts = _repair_exchange_metadata(user, new, checkpoint, progress)
    section_times = new.setdefault("section_as_of", {})
    for name in ("attribution", "operations", "payouts", "events"):
        if name in old:
            section_times.setdefault(name, old["as_of"])
    news, calendar = checkpoint["news"], checkpoint["calendar"]
    news_ok = news.get("state") == "available" and news.get("data", {}).get("complete", True) is True
    calendar_ok = calendar.get("state") == "available"
    if news.get("state") in {"available", "partial"}:
        new["news"] = news
        new["events"] = {"items": workspace._held_news(new, news), "complete": news_ok}
        section_times["events"] = news.get("as_of")
    if calendar_ok:
        new["calendar"] = calendar
    if operations_complete:
        new["operations"] = {"items": operations, "complete": True, "start": begin.isoformat(), "end": started.isoformat()}
        section_times["operations"] = started.isoformat()
    actual_operations = new.get("operations", {}).get("items", [])
    if payouts_complete:
        payout_observed = min([started] + [instant(ref["observed_at"]) for ref in payout_sources]).isoformat()
        payouts.extend(workspace._received_payout_events(actual_operations))
        new["payouts"] = {"items": sorted(payouts, key=lambda row: str(row.get("date")), reverse=True),
            "complete": operations_complete, "received_range": {"start": new.get("operations", {}).get("start"),
                "end": new.get("operations", {}).get("end")}, "announced_and_received_are_distinct": True,
            "position_basis_at": old["as_of"], "announcements_checked_at": payout_observed}
        section_times["payouts"] = payout_observed
    checked = now_iso()
    complete = news_ok and calendar_ok and operations_complete and payouts_complete and metadata_ok
    new["event_monitor"] = {"checked_at": checked, "complete": complete,
        "collection_started_at": started.isoformat(), "operations_through": started.isoformat(),
        "last_successful_at": checked if complete else old.get("event_monitor", {}).get("last_successful_at"),
        "news": "available" if news_ok else "incomplete", "calendar": "available" if calendar_ok else "unavailable",
        "operations": "available" if operations_complete else "incomplete",
        "payout_announcements": "available" if payouts_complete else "incomplete",
        "reviewed_rating_evidence_rechecked": True, "new_rating_sources_fetched": False,
        "valuation_refreshed": False, "valuation_as_of": old["as_of"], "broker_key": key}
    if metadata_repaired or metadata_attempts or not metadata_ok:
        new["event_monitor"].update(instrument_metadata="available" if metadata_ok else "incomplete",
            metadata_repaired=metadata_repaired, metadata_last_attempted=metadata_attempts)
    new["sources"] = _sources(new, operation_sources + payout_sources +
        news.get("sources", []) + calendar.get("sources", []))
    controller.assert_enabled(int(user["id"]))
    new["public_sources"] = public_sources.collect_snapshot_sources(
        workspace.backend.connect, new, checkpoint, progress)
    new["event_monitor"]["public_identity_sources"] = new["public_sources"]["state"]
    controller.assert_enabled(int(user["id"]))
    progress("persisting_events", checkpoint)
    # The same transaction checks that a concurrent price/manual collector has
    # not replaced any part of the snapshot. A conflict keeps the old result.
    workspace.persist(user, new, expected_snapshot=old)
    if not complete:
        # Persist useful independent lanes, then retain the exact acknowledged
        # cursor in the failed durable job for the next bounded retry.
        progress("events_partial", checkpoint)
        raise HTTPException(503, "event_sources_incomplete")
    return {"snapshot_id": new["snapshot_id"], "currency": currency,
            "as_of": old["as_of"], "event_monitor": new["event_monitor"]}
