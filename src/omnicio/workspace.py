"""Workspace goals and current portfolio values, without broker transaction history.

Changes between our own NAV observations describe account value only. They do
not establish investment profit because cash flows are intentionally not read.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .financial import MAX_USER_AMOUNT_RUB, PERCENT_SCALE
from .freshness import PORTFOLIO_MAX_AGE

CATEGORIES = ("portfolio", "payments", "goals", "system")
_MOSCOW_TIMEZONE = "Europe/Moscow"
DEFAULT_PREFERENCES: dict[str, Any] = {
    "display_name": "",
    "locale": "ru",
    "theme": "system",
    "mask_balances": False,
    "watchlist": [],
    "notifications": dict.fromkeys(CATEGORIES, True),
    "quiet_hours": {
        "enabled": False,
        "start": "22:00",
        "end": "08:00",
        "timezone": _MOSCOW_TIMEZONE,
    },
    "digest_frequency": "off",
    "digest_time": "20:30",
    "digest_timezone": _MOSCOW_TIMEZONE,
}
GOAL_FIELDS = (
    "title",
    "kind",
    "target_amount_rub",
    "target_date",
    "start_date",
    "progress_source",
    "allocation_percent",
    "manual_amount_rub",
    "status",
)
_ZERO = Decimal("0")


def decimal_text(value: Decimal) -> str:
    return format(value, "f")


def amount(value: object, *, maximum: Decimal = MAX_USER_AMOUNT_RUB, places: int = 9) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (Decimal, str, int)):
        raise ValueError("workspace_amount_invalid")
    if isinstance(value, str) and len(value) > 64:
        raise ValueError("workspace_amount_invalid")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("workspace_amount_invalid") from exc
    if not result.is_finite() or result.copy_abs() > maximum:
        raise ValueError("workspace_amount_invalid")
    if int(result.as_tuple().exponent) < -places:
        raise ValueError("workspace_amount_precision")
    return result


def _text(value: object, *, maximum: int, empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError("workspace_text_invalid")
    result = value.strip()
    if (not result and not empty) or len(result) > maximum:
        raise ValueError("workspace_text_invalid")
    if any(ord(char) < 32 or ord(char) == 127 or 0xD800 <= ord(char) <= 0xDFFF for char in result):
        raise ValueError("workspace_text_invalid")
    return result


def _exact(value: object, fields: Sequence[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ValueError("workspace_fields_invalid")
    return value


def _choice(value: object, choices: Sequence[str]) -> str:
    if not isinstance(value, str) or value not in choices:
        raise ValueError("workspace_choice_invalid")
    return value


def _boolean(value: object) -> bool:
    if type(value) is not bool:
        raise ValueError("workspace_boolean_invalid")
    return value


def default_preferences() -> dict[str, Any]:
    """Product defaults contain no invented account, amount, goal, or instrument."""
    return copy.deepcopy(DEFAULT_PREFERENCES)


def _preference_clock(value: object, error_code: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(
        r"(?:[01]\d|2[0-3]):[0-5]\d", value, flags=re.ASCII,
    ):
        raise ValueError(error_code)
    return value


def _preference_timezone(value: object) -> str:
    timezone = _text(value, maximum=64)
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError("workspace_timezone_invalid") from exc
    return timezone


def _preference_watchlist(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list) or len(value) > 50:
        raise ValueError("workspace_watchlist_limit")
    instruments = []
    seen = set()
    for raw in value:
        item = _exact(raw, ("instrument_uid", "ticker", "name"))
        uid = _text(item["instrument_uid"], maximum=128)
        if not re.fullmatch(r"[\w-]+", uid, flags=re.ASCII) or uid in seen:
            raise ValueError("workspace_watchlist_identity")
        seen.add(uid)
        instruments.append({
            "instrument_uid": uid,
            "ticker": _text(item["ticker"], maximum=64, empty=True),
            "name": _text(item["name"], maximum=256, empty=True),
        })
    return instruments


def normalize_preferences(value: object) -> dict[str, Any]:
    # Legacy clients/documents retain the original midnight delivery schedule.
    if isinstance(value, dict) and set(value) == set(DEFAULT_PREFERENCES) - {
        "digest_time", "digest_timezone",
    }:
        quiet_value = value.get("quiet_hours")
        legacy_zone = quiet_value.get("timezone") if isinstance(quiet_value, dict) else None
        value = {**value, "digest_time": "00:00", "digest_timezone": legacy_zone}
    data = _exact(value, tuple(DEFAULT_PREFERENCES))
    notifications = _exact(data["notifications"], CATEGORIES)
    quiet = _exact(data["quiet_hours"], ("enabled", "start", "end", "timezone"))
    enabled = _boolean(quiet["enabled"])
    for key in ("start", "end"):
        _preference_clock(quiet[key], "workspace_quiet_time_invalid")
    if enabled and quiet["start"] == quiet["end"]:
        raise ValueError("workspace_quiet_interval_empty")
    timezone = _preference_timezone(quiet["timezone"])
    digest_time = _preference_clock(data["digest_time"], "workspace_digest_time_invalid")
    digest_timezone = _preference_timezone(data["digest_timezone"])
    instruments = _preference_watchlist(data["watchlist"])
    result: dict[str, Any] = {
        "display_name": _text(data["display_name"], maximum=80, empty=True),
        "locale": _choice(data["locale"], ("ru", "en")),
        "theme": _choice(data["theme"], ("system", "light", "dark")),
        "mask_balances": _boolean(data["mask_balances"]),
        "watchlist": instruments,
        "notifications": {key: _boolean(notifications[key]) for key in CATEGORIES},
        "quiet_hours": {
            "enabled": enabled,
            "start": quiet["start"],
            "end": quiet["end"],
            "timezone": timezone,
        },
        "digest_frequency": _choice(data["digest_frequency"], ("off", "daily", "weekly")),
        "digest_time": digest_time,
        "digest_timezone": digest_timezone,
    }
    # Match the database's JSONB text-size boundary before attempting a write.
    # Individual field limits alone do not bound a 50-item Unicode watchlist.
    if len(json.dumps(result, ensure_ascii=False).encode("utf-8")) > 32768:
        raise ValueError("workspace_preferences_too_large")
    return result


def _date(value: object) -> date:
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}", value, flags=re.ASCII,
    ):
        raise ValueError("workspace_date_invalid")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("workspace_date_invalid") from exc


def normalize_goal(value: object) -> dict[str, Any]:
    data = _exact(value, GOAL_FIELDS)
    kind = _choice(data["kind"], ("capital", "income"))
    source = _choice(data["progress_source"], ("portfolio", "manual"))
    if source != "manual" and source != {"capital": "portfolio", "income": "income"}[kind]:
        raise ValueError("workspace_goal_source_mismatch")
    target = amount(data["target_amount_rub"], places=8)
    if target <= 0:
        raise ValueError("workspace_goal_target_positive")
    started = _date(data["start_date"])
    target_date = _date(data["target_date"]) if data["target_date"] is not None else None
    if target_date is not None and target_date < started:
        raise ValueError("workspace_goal_date_order")
    allocation = manual = None
    if source == "manual":
        manual_value = amount(data["manual_amount_rub"], places=8)
        if manual_value < 0 or data["allocation_percent"] is not None:
            raise ValueError("workspace_goal_manual_invalid")
        manual = decimal_text(manual_value)
    else:
        allocation_value = amount(data["allocation_percent"], maximum=Decimal(PERCENT_SCALE))
        if allocation_value <= 0 or data["manual_amount_rub"] is not None:
            raise ValueError("workspace_goal_allocation_invalid")
        allocation = decimal_text(allocation_value)
    return {
        "title": _text(data["title"], maximum=120),
        "kind": kind,
        "target_amount_rub": decimal_text(target),
        "target_date": target_date.isoformat() if target_date is not None else None,
        "start_date": started.isoformat(),
        "progress_source": source,
        "allocation_percent": allocation,
        "manual_amount_rub": manual,
        "status": _choice(data["status"], ("active", "completed", "archived")),
    }


def timestamp(value: object) -> datetime | None:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        try:
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    return result.astimezone(UTC) if result.tzinfo is not None else None


def quiet_now(preferences: Mapping[str, Any], now: datetime) -> bool:
    quiet = preferences["quiet_hours"]
    if not quiet["enabled"]:
        return False
    local = now.astimezone(ZoneInfo(quiet["timezone"])).time().replace(tzinfo=None)
    start, end = time.fromisoformat(quiet["start"]), time.fromisoformat(quiet["end"])
    return start <= local < end if start < end else local >= start or local < end


def snapshot_valuation_complete(snapshot: Mapping[str, Any]) -> bool:
    """A complete valuation requires an actual finite NAV, never a missing value."""
    try:
        amount(snapshot.get("nav_rub"))
    except ValueError:
        return False
    valuation_status = snapshot.get("valuation_status")
    evidence = snapshot.get("evidence")
    if valuation_status is None and isinstance(evidence, Mapping):
        analysis = evidence.get("analysis")
        if isinstance(analysis, Mapping):
            valuation_status = analysis.get("valuation_status")
    return (
        valuation_status == "complete"
        if valuation_status is not None
        else snapshot.get("analysis_status") == "observed"
    )


def portfolio_value_change(snapshots: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Compare our own valued observations without inventing investment returns."""
    result: dict[str, Any] = {
        "status": "unavailable",
        "reason": "insufficient_valued_snapshots",
        "from": None,
        "to": None,
        "start_nav_rub": None,
        "end_nav_rub": None,
        "nav_change_rub": None,
        "method": "snapshot_value_change",
        "label": "Изменение стоимости портфеля",
        "limitation": "Разность собственных наблюдений стоимости, не доходность. "
        "История операций и денежных потоков не собирается.",
    }
    covered = [
        row
        for row in snapshots
        if timestamp(row.get("captured_at")) is not None and snapshot_valuation_complete(row)
    ]
    covered.sort(key=lambda row: timestamp(row["captured_at"]) or datetime.min.replace(tzinfo=UTC))
    if len(covered) < 2:
        return result
    first, last = covered[0], covered[-1]
    begin, end = timestamp(first["captured_at"]), timestamp(last["captured_at"])
    if begin is None or end is None or end <= begin:
        return result
    start_nav, end_nav = amount(first["nav_rub"]), amount(last["nav_rub"])
    result.update(
        status="available",
        reason=None,
        **{"from": begin.isoformat(), "to": end.isoformat()},
        start_nav_rub=decimal_text(start_nav),
        end_nav_rub=decimal_text(end_nav),
        nav_change_rub=decimal_text(end_nav - start_nav),
    )
    return result


def _portfolio_goal_amount(
    goal: Mapping[str, Any], snapshot: Mapping[str, Any] | None, now: datetime,
) -> tuple[Decimal | None, datetime | None, str | None]:
    observed = timestamp(snapshot.get("captured_at")) if snapshot else None
    if (
        snapshot is None or observed is None or observed > now
        or not snapshot_valuation_complete(snapshot)
    ):
        return None, observed, "portfolio_not_reconciled"
    current = amount(snapshot["nav_rub"]) * amount(goal["allocation_percent"]) / PERCENT_SCALE
    return current, observed, None


def goal_progress(
    goal: Mapping[str, Any],
    *,
    connection: Mapping[str, Any] | None,
    snapshot: Mapping[str, Any] | None,
    now: datetime,
) -> dict[str, Any]:
    source = goal["progress_source"]
    current: Decimal | None = None
    observed: datetime | None = None
    reason = None
    if source == "manual":
        current, observed = amount(goal["manual_amount_rub"]), timestamp(goal["updated_at"])
    elif (
        connection is None
        or goal.get("account_id") != connection.get("account_id")
        or goal.get("environment") != connection.get("environment")
    ):
        reason = "linked_account_unavailable"
    elif source == "portfolio":
        current, observed, reason = _portfolio_goal_amount(goal, snapshot, now)
    else:
        reason = "transaction_history_not_collected"
    target = amount(goal["target_amount_rub"])
    result: dict[str, Any] = {
        "status": "unavailable",
        "amount_rub": None,
        "percent": None,
        "remaining_rub": None,
        "source": source,
        "as_of": observed.isoformat() if observed is not None else None,
        "reason": reason,
    }
    if current is not None:
        result.update(
            status="available",
            amount_rub=decimal_text(current),
            percent=decimal_text(current / target * PERCENT_SCALE),
            remaining_rub=decimal_text(max(_ZERO, target - current)),
        )
        if source != "manual" and observed is not None and now - observed >= PORTFOLIO_MAX_AGE:
            result["status"] = "stale"
    return result


def event_id(kind: str, identity: object) -> str:
    value = json.dumps([kind, identity], sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(value.encode()).hexdigest()


def event_digest(
    events: Sequence[Mapping[str, Any]],
    preferences: Mapping[str, Any],
    now: datetime,
) -> dict[str, Any]:
    frequency = preferences["digest_frequency"]
    start = now
    if frequency != "off":
        local = now.astimezone(ZoneInfo(preferences.get(
            "digest_timezone", preferences["quiet_hours"]["timezone"],
        )))
        start = local.replace(hour=0, minute=0, second=0, microsecond=0)
        if frequency == "weekly":
            start -= timedelta(days=start.weekday())
    counts = dict.fromkeys(CATEGORIES, 0)
    selected = []
    if frequency != "off":
        for item in events:
            at = timestamp(item.get("updated_at"))
            if (at is not None and start <= at <= now and item.get("read_at") is None
                    and preferences["notifications"].get(item["category"], False)):
                counts[item["category"]] += 1
                selected.append(item)
    selected.sort(key=lambda item: (
        {"critical": 2, "warning": 1}.get(str(item.get("severity")), 0),
        timestamp(item.get("updated_at")) or start,
    ), reverse=True)
    return {
        "frequency": frequency,
        "period_basis": "available_at",
        "from": start.isoformat(),
        "to": now.isoformat(),
        "count": sum(counts.values()),
        "by_category": counts,
        "source_basis": "persisted_owner_events",
        "highlights": [{key: row.get(key) for key in (
            "id", "category", "kind", "severity", "title", "detail", "occurred_at", "destination",
        )} for row in selected[:8]],
        "highlights_limit": 8,
    }
