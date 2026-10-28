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


def _position_exchanges(positions: list[dict]) -> set[str]:
    values = set()
    for position in positions:
        metadata = position.get("metadata")
        value = metadata.get("exchange") if isinstance(metadata, dict) else None
        if not isinstance(value, str) or not value or len(value) > 100 or value != value.strip():
            return set()
        values.add(value)
    return values


def required_exchanges(snapshot: dict | None) -> tuple[str, ...]:
    # An exact instrument exchange is never silently translated into another
    # section. With no securities yet, the configured universe is MOEX.
    positions = [p for p in (snapshot or {}).get("positions", [])
                 if p.get("instrument_type") in {"share", "bond"}]
    values = _position_exchanges(positions) if positions else {"MOEX"}
    return tuple(sorted(values))


def _window(row: dict, start: str, end: str) -> tuple[datetime, datetime] | None:
    left, right = row.get(start), row.get(end)
    if left is None and right is None:
        return None
    # A missing boundary cannot turn an auction/clearing into a regular window.
    begin, finish = instant(left), instant(right)
    if begin >= finish or finish - begin > timedelta(days=2):
        raise ValueError("calendar_window_invalid")
    return begin, finish


def _intervals(row: dict) -> bool:
    intervals = row.get("intervals", [])
    if not isinstance(intervals, list) or len(intervals) > MAX_INTERVALS:
        raise ValueError("calendar_intervals_invalid")
    # Undocumented names never authorize a session; malformed evidence stays unknown.
    for item in intervals:
        if not isinstance(item, dict) or not isinstance(item.get("type"), str):
            raise ValueError("calendar_interval_invalid")
        span = item.get("interval")
        if not isinstance(span, dict) or _window(span, "startTs", "endTs") is None:
            raise ValueError("calendar_interval_invalid")
    return bool(intervals)


def _excluded_state(row: dict, now: datetime, state: str, boundaries: list[datetime]) -> str:
    for start_key, end_key, excluded in EXCLUDED_WINDOWS:
        # eveningStart/End is a complete alternative to the optional auction start.
        if start_key == "eveningOpeningAuctionStartTime" and row.get(start_key) is None:
            continue
        span = _window(row, start_key, end_key)
        if span is not None:
            boundaries.extend(t for t in span if t > now)
            if span[0] <= now < span[1]:
                state = excluded
    return state


def _day(row: dict, now: datetime) -> tuple[str, list[datetime], bool]:
    if type(row.get("isTradingDay")) is not bool:
        raise ValueError("calendar_trading_flag_invalid")
    date = instant(row.get("date")).date()
    if not row["isTradingDay"]:
        return ("closed" if date == now.date() else "other_day"), [], False
    window = _window(row, "startTime", "endTime")
    unclassified = _intervals(row)
    if window is None:
        return ("unknown" if date == now.date() else "other_day"), [], unclassified
    begin, end = window
    if abs((begin.date() - date).days) > 1:
        raise ValueError("calendar_day_window_mismatch")
    boundaries = [t for t in window if t > now]
    state = "scheduled_window" if begin <= now < end else "closed"
    state = _excluded_state(row, now, state, boundaries)
    if date != now.date() and not begin <= now < end:
        state = "other_day"
    return state, boundaries, unclassified


def _schedule_index(raw: dict) -> dict:
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
    return indexed


def _observed_day(day: dict, seen: set, now: datetime) -> tuple:
    if not isinstance(day, dict):
        raise ValueError("calendar_day_invalid")
    day_date = instant(day.get("date")).date()
    if day_date in seen:
        raise ValueError("calendar_day_conflict")
    seen.add(day_date)
    state, future, unknown_names = _day(day, now)
    return day_date, state, future, unknown_names


def _selected_state(applicable: list[str], current_day: str | None) -> str:
    active = [value for value in applicable if value not in {"closed", "other_day"}]
    if len(active) > 1:
        raise ValueError("calendar_overlapping_days")
    selected = active[0] if active else current_day
    return "closed" if selected == "other_day" else selected


def _section_state(schedule: dict | None, now: datetime) -> tuple[str, list[datetime], bool]:
    if schedule is None:
        raise ValueError("calendar_section_missing")
    days = schedule.get("days")
    if not isinstance(days, list) or not 1 <= len(days) <= MAX_DAYS:
        raise ValueError("calendar_days_invalid")
    seen, applicable, current_day = set(), [], None
    transitions, unclassified = [], False
    for day in days:
        day_date, state, future, unknown_names = _observed_day(day, seen, now)
        transitions.extend(future)
        unclassified |= unknown_names
        if state != "other_day":
            applicable.append(state)
        if day_date == now.date():
            current_day = state
    if now.date() not in seen or not applicable:
        raise ValueError("calendar_today_missing")
    return _selected_state(applicable, current_day), transitions, unclassified


def _combined_state(states: list[str]) -> str:
    if "unknown" in states:
        return "unknown"
    if all(value == "scheduled_window" for value in states):
        return "scheduled_window"
    if len(set(states)) == 1:
        return states[0]
    return "mixed"


def _calendar_sections(raw: dict, exchanges: tuple[str, ...], now: datetime, result: dict) -> dict:
    indexed = _schedule_index(raw)
    states, transitions, unclassified = [], [], False
    for name in exchanges:
        selected, future, unknown_names = _section_state(indexed.get(name), now)
        states.append(selected)
        transitions.extend(future)
        unclassified |= unknown_names
        result["sections"].append({"exchange": name, "state": selected})
    state = _combined_state(states)
    return {**result, "state": state, "reason": "broker_schedule_" + state,
            "regular_price_polling_allowed": state == "scheduled_window",
            "next_transition_at": min(transitions).isoformat() if transitions else None,
            "interval_classification": "unclassified" if unclassified else "legacy_broker_window"}


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
        return _calendar_sections(raw, exchanges, now, result)
    except (TypeError, ValueError, OverflowError, KeyError):
        return {**result, "state": "unknown", "reason": "calendar_incomplete_or_conflicting",
                "regular_price_polling_allowed": False}
