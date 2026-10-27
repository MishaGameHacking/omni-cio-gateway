"""Pure broker-calendar interpretation for read-only polling, never trade permission.

UTC dates and explicit broker windows are authoritative. A weekday, an Android
clock, a cached quote or the deprecated weekend flag cannot open a session.
Free-form interval names are retained as unclassified, not mapped to 'main'.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

UTC = timezone.utc
MAX_CALENDAR_AGE = 900
MAX_EXCHANGES = 256
MAX_DAYS = 32
MAX_INTERVALS = 128
EXCLUDED_WINDOWS = (
    ("openingAuctionStartTime", "openingAuctionEndTime", "opening_auction"),
    ("closingAuctionStartTime", "closingAuctionEndTime", "closing_auction"),
    ("clearingStartTime", "clearingEndTime", "clearing"),
    ("premarketStartTime", "premarketEndTime", "premarket"),
    ("eveningOpeningAuctionStartTime", "eveningEndTime", "evening"),
    ("eveningStartTime", "eveningEndTime", "evening"),
)


def instant(value: Any) -> datetime:
    if not isinstance(value, str) or not 1 <= len(value) <= 64:
        raise ValueError("calendar_timestamp_invalid")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("calendar_timestamp_timezone_missing")
    return parsed.astimezone(UTC)


def required_exchanges(snapshot: dict | None) -> tuple[str, ...]:
    # An exact instrument exchange is never silently translated into another
    # section. With no securities yet, the configured universe is MOEX.
    positions = [p for p in (snapshot or {}).get("positions", [])
                 if p.get("instrument_type") in {"share", "bond"}]
    if not positions:
        return ("MOEX",)
    values = []
    for position in positions:
        metadata = position.get("metadata")
        value = metadata.get("exchange") if isinstance(metadata, dict) else None
        if not isinstance(value, str) or not value or len(value) > 100:
            return ()
        values.append(value)
    return tuple(sorted(set(values)))


def _window(row: dict, start: str, end: str) -> tuple[datetime, datetime] | None:
    left, right = row.get(start), row.get(end)
    if left is None and right is None:
        return None
    # A missing boundary cannot turn an auction/clearing into a regular window.
    begin, finish = instant(left), instant(right)
    if not begin < finish or finish - begin > timedelta(days=2):
        raise ValueError("calendar_window_invalid")
    return begin, finish


def _day(row: dict, now: datetime) -> tuple[str, list[datetime], bool]:
    if type(row.get("isTradingDay")) is not bool:
        raise ValueError("calendar_trading_flag_invalid")
    date = instant(row.get("date")).date()
    if not row["isTradingDay"]:
        return ("closed" if date == now.date() else "other_day"), [], False
    window = _window(row, "startTime", "endTime")
    intervals = row.get("intervals", [])
    if not isinstance(intervals, list) or len(intervals) > MAX_INTERVALS:
        raise ValueError("calendar_intervals_invalid")
    # Validate all supplied intervals even though their undocumented vocabulary
    # cannot authorize a session. Malformed additional evidence stays unknown.
    for item in intervals:
        if not isinstance(item, dict) or not isinstance(item.get("type"), str):
            raise ValueError("calendar_interval_invalid")
        span = item.get("interval")
        if not isinstance(span, dict) or _window(span, "startTs", "endTs") is None:
            raise ValueError("calendar_interval_invalid")
    if window is None:
        return ("unknown" if date == now.date() else "other_day"), [], bool(intervals)
    begin, end = window
    if abs((begin.date() - date).days) > 1:
        raise ValueError("calendar_day_window_mismatch")
    boundaries = [t for t in window if t > now]
    state = "scheduled_window" if begin <= now < end else "closed"
    for start_key, end_key, excluded in EXCLUDED_WINDOWS:
        # eveningStart/End is a complete alternative to the optional auction
        # start. Do not demand an auction when the broker did not return one.
        if start_key == "eveningOpeningAuctionStartTime" and row.get(start_key) is None:
            continue
        span = _window(row, start_key, end_key)
        if span is not None:
            boundaries.extend(t for t in span if t > now)
            if span[0] <= now < span[1]:
                state = excluded
    if date != now.date() and not begin <= now < end:
        state = "other_day"
    return state, boundaries, bool(intervals)


def polling_state(calendar: dict | None, exchanges: tuple[str, ...], *, now: datetime) -> dict:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("aware_calendar_clock_required")
    now = now.astimezone(UTC)
    result = {"state": "unknown", "reason": "calendar_missing", "as_of": None,
              "checked_at": now.isoformat(), "timezone": "UTC", "display_timezone": "Europe/Moscow",
              "required_exchanges": list(exchanges), "next_transition_at": None,
              "regular_price_polling_allowed": False, "main_session_verified": False,
              "trade_permission": False, "interval_classification": "not_available", "sections": []}
    if not exchanges:
        return {**result, "reason": "instrument_exchange_unknown"}
    try:
        envelope = calendar or {}
        if envelope.get("state") != "available":
            return result
        raw = envelope.get("data")
        if not isinstance(raw, dict) or raw.get("timezone") != "UTC":
            raise ValueError("calendar_schema_invalid")
        observed = instant(raw.get("as_of"))
        result["as_of"] = observed.isoformat()
        age = (now - observed).total_seconds()
        if not 0 <= age < MAX_CALENDAR_AGE:
            return {**result, "reason": "calendar_stale_or_future"}
        schedules = raw.get("exchanges")
        if not isinstance(schedules, list) or len(schedules) > MAX_EXCHANGES:
            raise ValueError("calendar_sections_invalid")
        indexed = {}
        for schedule in schedules:
            if not isinstance(schedule, dict) or not isinstance(schedule.get("exchange"), str):
                raise ValueError("calendar_section_invalid")
            name = schedule["exchange"]
            if name in indexed:
                raise ValueError("calendar_section_conflict")
            indexed[name] = schedule
        states, transitions, unclassified = [], [], False
        for name in exchanges:
            schedule = indexed.get(name)
            if schedule is None:
                raise ValueError("calendar_section_missing")
            days = schedule.get("days")
            if not isinstance(days, list) or not 1 <= len(days) <= MAX_DAYS:
                raise ValueError("calendar_days_invalid")
            seen, applicable, current_day = set(), [], None
            for day in days:
                if not isinstance(day, dict):
                    raise ValueError("calendar_day_invalid")
                day_date = instant(day.get("date")).date()
                if day_date in seen:
                    raise ValueError("calendar_day_conflict")
                seen.add(day_date)
                state, future, unknown_names = _day(day, now)
                transitions.extend(future)
                unclassified |= unknown_names
                if state != "other_day":
                    applicable.append(state)
                if day_date == now.date():
                    current_day = state
            if now.date() not in seen or not applicable:
                raise ValueError("calendar_today_missing")
            active = [value for value in applicable if value not in {"closed", "other_day"}]
            if len(active) > 1:
                raise ValueError("calendar_overlapping_days")
            selected = active[0] if active else current_day
            if selected == "other_day":
                selected = "closed"
            states.append(selected)
            result["sections"].append({"exchange": name, "state": selected})
        if "unknown" in states:
            state = "unknown"
        elif all(value == "scheduled_window" for value in states):
            state = "scheduled_window"
        elif len(set(states)) == 1:
            state = states[0]
        else:
            state = "mixed"
        return {**result, "state": state, "reason": "broker_schedule_" + state,
                "regular_price_polling_allowed": state == "scheduled_window",
                "next_transition_at": min(transitions).isoformat() if transitions else None,
                "interval_classification": "unclassified" if unclassified else "legacy_broker_window"}
    except (TypeError, ValueError, OverflowError, KeyError):
        return {**result, "state": "unknown", "reason": "calendar_incomplete_or_conflicting",
                "regular_price_polling_allowed": False}
