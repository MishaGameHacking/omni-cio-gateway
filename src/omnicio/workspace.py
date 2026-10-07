"""User workspace contracts and calculations over observed financial facts.

NAV movement and investment result are different quantities. Cash-flow accounting
uses the T-Invest OperationType contract; it never turns deposits into earnings:
https://developer.tbank.ru/invest/services/operations/methods
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
_HUNDRED = Decimal("100")
_MAX_MONEY = Decimal("1000000000000")
_INCOME_FIELDS = ("coupons_rub", "dividends_rub", "other_income_rub")
_SOURCE = "https://developer.tbank.ru/invest/services/operations/methods"


def decimal_text(value: Decimal) -> str:
    return format(value, "f")


def amount(value: object, *, maximum: Decimal = _MAX_MONEY, places: int = 9) -> Decimal:
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


def normalize_preferences(value: object) -> dict[str, Any]:
    data = _exact(value, tuple(DEFAULT_PREFERENCES))
    notifications = _exact(data["notifications"], CATEGORIES)
    quiet = _exact(data["quiet_hours"], ("enabled", "start", "end", "timezone"))
    enabled = _boolean(quiet["enabled"])
    for key in ("start", "end"):
        if not isinstance(quiet[key], str) or not re.fullmatch(
            r"(?:[01]\d|2[0-3]):[0-5]\d",
            quiet[key],
            flags=re.ASCII,
        ):
            raise ValueError("workspace_quiet_time_invalid")
    if enabled and quiet["start"] == quiet["end"]:
        raise ValueError("workspace_quiet_interval_empty")
    timezone = _text(quiet["timezone"], maximum=64)
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError("workspace_timezone_invalid") from exc
    watchlist = data["watchlist"]
    if not isinstance(watchlist, list) or len(watchlist) > 50:
        raise ValueError("workspace_watchlist_limit")
    instruments = []
    seen = set()
    for raw in watchlist:
        item = _exact(raw, ("instrument_uid", "ticker", "name"))
        uid = _text(item["instrument_uid"], maximum=128)
        if not re.fullmatch(r"[\w-]+", uid, flags=re.ASCII) or uid in seen:
            raise ValueError("workspace_watchlist_identity")
        seen.add(uid)
        instruments.append(
            {
                "instrument_uid": uid,
                "ticker": _text(item["ticker"], maximum=64, empty=True),
                "name": _text(item["name"], maximum=256, empty=True),
            }
        )
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
    source = _choice(data["progress_source"], ("portfolio", "income", "manual"))
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
        allocation_value = amount(data["allocation_percent"], maximum=_HUNDRED)
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


_INPUT = {"INPUT", "INPUT_SWIFT", "INPUT_ACQUIRING", "INP_MULTI"}
_OUTPUT = {"OUTPUT", "OUTPUT_SWIFT", "OUTPUT_ACQUIRING", "OUT_MULTI"}
_FEES = {
    "SERVICE_FEE",
    "MARGIN_FEE",
    "BROKER_FEE",
    "SUCCESS_FEE",
    "TRACK_MFEE",
    "TRACK_PFEE",
    "CASH_FEE",
    "OUT_FEE",
    "OUT_STAMP_DUTY",
    "OUTPUT_PENALTY",
    "ADVICE_FEE",
    "OVER_COM",
    "OTHER_FEE",
    "FUNDING",
}
_TAXES = {
    "BOND_TAX",
    "TAX",
    "DIVIDEND_TAX",
    "TAX_CORRECTION",
    "BENEFIT_TAX",
    "TAX_PROGRESSIVE",
    "BOND_TAX_PROGRESSIVE",
    "DIVIDEND_TAX_PROGRESSIVE",
    "BENEFIT_TAX_PROGRESSIVE",
    "TAX_CORRECTION_PROGRESSIVE",
    "TAX_REPO_PROGRESSIVE",
    "TAX_REPO",
    "TAX_REPO_HOLD",
    "TAX_REPO_REFUND",
    "TAX_REPO_HOLD_PROGRESSIVE",
    "TAX_REPO_REFUND_PROGRESSIVE",
    "TAX_CORRECTION_COUPON",
}
_INCOME = {
    "COUPON": "coupons_rub",
    "DIVIDEND": "dividends_rub",
    "OVERNIGHT": "other_income_rub",
    "OVER_INCOME": "other_income_rub",
}
_REDEMPTIONS = {"BOND_REPAYMENT", "BOND_REPAYMENT_FULL"}
_INTERNAL = {
    "BUY",
    "SELL",
    "SELL_MARGIN",
    "BUY_MARGIN",
    "ACCRUING_VARMARGIN",
    "WRITING_OFF_VARMARGIN",
    "DELIVERY_BUY",
    "DELIVERY_SELL",
    "OVER_PLACEMENT",
    "OPTION_EXPIRATION",
    "FUTURE_EXPIRATION",
    "DFA_REDEMPTION",
    "PRIMARY_ORDER",
}
_NON_INCOME_TRANSFERS = {
    "INPUT_SECURITIES",
    "OUTPUT_SECURITIES",
    "TRANS_IIS_BS",
    "TRANS_BS_BS",
    "BUY_CARD",
    "SELL_CARD",
}


def _operation_amount(operation: Mapping[str, Any]) -> Decimal | None:
    if str(operation.get("payment_currency") or "").upper() != "RUB":
        return None
    try:
        return amount(operation.get("payment_value"))
    except ValueError:
        return None


def _executed_cashflow(
    operation: Mapping[str, Any], from_at: datetime, to_at: datetime,
    reasons: set[str], income_reasons: set[str],
) -> tuple[str, datetime] | None:
    at = timestamp(operation.get("operation_date"))
    if at is None:
        reasons.add("operation_time_invalid")
        income_reasons.add("operation_time_invalid")
        return None
    if not from_at < at <= to_at:
        return None
    state = operation.get("operation_state")
    if state in {"OPERATION_STATE_CANCELED", "OPERATION_STATE_PROGRESS"}:
        return None
    if state != "OPERATION_STATE_EXECUTED":
        reasons.add("operation_state_unknown")
        income_reasons.add("operation_state_unknown")
        return None
    kind = str(operation.get("operation_type") or "").removeprefix("OPERATION_TYPE_")
    if kind in _INTERNAL:
        return None
    if kind not in _INPUT | _OUTPUT | _FEES | _TAXES | _INCOME.keys() | _REDEMPTIONS:
        reasons.add("unclassified_or_non_cash_transfer")
        if kind not in _NON_INCOME_TRANSFERS:
            income_reasons.add("unclassified_income")
        return None
    return kind, at


def _cashflow_payment(
    operation: Mapping[str, Any], kind: str, reasons: set[str], income_reasons: set[str],
) -> Decimal | None:
    payment = _operation_amount(operation)
    if payment is None:
        reasons.add("payment_currency_or_amount_unavailable")
        if kind in _INCOME.keys() | _REDEMPTIONS:
            income_reasons.add("income_currency_or_amount_unavailable")
        return None
    if (kind in _INPUT and payment < 0) or (kind in _OUTPUT and payment > 0):
        reasons.add("external_flow_sign_invalid")
        return None
    return payment


def _accumulate_cashflow(
    kind: str, at: datetime, payment: Decimal, values: dict[str, Decimal],
    months: dict[str, dict[str, Decimal]],
) -> None:
    if kind in _INPUT | _OUTPUT:
        values["net_contributions_rub"] += payment
    elif kind in _FEES:
        values["fees_rub"] -= payment
    elif kind in _TAXES:
        values["taxes_rub"] -= payment
    elif kind in _REDEMPTIONS:
        values["redemptions_rub"] += payment
    else:
        key = _INCOME[kind]
        values[key] += payment
        month = at.astimezone(ZoneInfo(_MOSCOW_TIMEZONE)).strftime("%Y-%m")
        monthly = months.setdefault(month, dict.fromkeys(_INCOME_FIELDS, _ZERO))
        monthly[key] += payment


def cashflow_summary(
    operations: Sequence[Mapping[str, Any]],
    *,
    from_at: datetime,
    to_at: datetime,
    complete: bool,
) -> dict[str, Any]:
    """Sum executed ledger payments once; embedded commission fields are metadata.

    Noncash transfers, card purchases and unfamiliar operations prevent a return
    assertion. Redemption is returned principal, separate from investment income.
    """
    values = dict.fromkeys(
        (*_INCOME_FIELDS, "redemptions_rub", "net_contributions_rub", "fees_rub", "taxes_rub"),
        _ZERO,
    )
    months: dict[str, dict[str, Decimal]] = {}
    reasons = set() if complete else {"history_incomplete"}
    income_reasons = set(reasons)
    for operation in operations:
        parsed = _executed_cashflow(operation, from_at, to_at, reasons, income_reasons)
        if parsed is None:
            continue
        kind, at = parsed
        payment = _cashflow_payment(operation, kind, reasons, income_reasons)
        if payment is None:
            continue
        _accumulate_cashflow(kind, at, payment, values, months)
    income_total = sum((values[key] for key in _INCOME_FIELDS), _ZERO)
    return {
        "status": "available" if not reasons else "unavailable",
        "reason": ",".join(sorted(reasons)) or None,
        "from": from_at.isoformat(),
        "to": to_at.isoformat(),
        **{key: decimal_text(value) if not reasons else None for key, value in values.items()},
        "income": {
            "status": "available" if not income_reasons else "unavailable",
            "reason": ",".join(sorted(income_reasons)) or None,
            "from": from_at.isoformat(),
            "to": to_at.isoformat(),
            **{
                key: decimal_text(values[key]) if not income_reasons else None
                for key in (*_INCOME_FIELDS, "redemptions_rub")
            },
            "total_rub": decimal_text(income_total) if not income_reasons else None,
            "by_month": [
                {
                    "month": month,
                    **{key: decimal_text(row[key]) for key in _INCOME_FIELDS},
                    "total_rub": decimal_text(sum(row.values(), _ZERO)),
                }
                for month, row in sorted(months.items())
            ]
            if not income_reasons
            else [],
            "source_url": _SOURCE,
            "tax_basis": "broker_payments_before_separate_tax_operations",
        },
    }


def portfolio_performance(
    snapshots: Sequence[Mapping[str, Any]],
    operations: Sequence[Mapping[str, Any]],
    *,
    watermark: datetime | None,
    history_complete: bool,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "unavailable",
        "reason": "insufficient_covered_snapshots",
        "from": None,
        "to": None,
        "start_nav_rub": None,
        "end_nav_rub": None,
        "nav_change_rub": None,
        "net_contributions_rub": None,
        "investment_result_rub": None,
        "income_received_rub": None,
        "fees_rub": None,
        "taxes_rub": None,
        "return_percent": None,
        "return_status": "unavailable",
        "return_reason": "insufficient_covered_snapshots",
        "return_method": "modified_dietz",
        "return_denominator_rub": None,
        "return_is_estimate": True,
        "return_is_annualized": False,
        "return_limitations": [
            "Cash flows are weighted by their recorded execution time within the observed period.",
            "Large flows during volatile periods can make this estimate differ from time-weighted return.",
            "This is a historical account result, not a forecast or a probability of success.",
        ],
        "return_source_url": (
            "https://www.gipsstandards.org/standards/gips-standards-for-firms/"
            "gips-standards-handbook-for-firms/"
        ),
        "method": "nav_less_external_flows",
        "source_url": _SOURCE,
    }
    covered = [
        row
        for row in snapshots
        if watermark is not None
        and (at := timestamp(row.get("captured_at"))) is not None
        and at <= watermark
        and row.get("analysis_status") == "observed"
    ]
    covered.sort(key=lambda row: timestamp(row["captured_at"]) or datetime.min.replace(tzinfo=UTC))
    if len(covered) < 2:
        return result
    first, last = covered[0], covered[-1]
    begin, end = timestamp(first["captured_at"]), timestamp(last["captured_at"])
    if begin is None or end is None or end <= begin:
        return result
    flow = cashflow_summary(operations, from_at=begin, to_at=end, complete=history_complete)
    start_nav, end_nav = amount(first["nav_rub"]), amount(last["nav_rub"])
    delta = end_nav - start_nav
    result.update(
        {
            "status": flow["status"],
            "reason": flow["reason"],
            "from": begin.isoformat(),
            "to": end.isoformat(),
            "start_nav_rub": decimal_text(start_nav),
            "end_nav_rub": decimal_text(end_nav),
            "nav_change_rub": decimal_text(delta),
            "net_contributions_rub": flow["net_contributions_rub"],
            "income_received_rub": flow["income"]["total_rub"],
            "fees_rub": flow["fees_rub"],
            "taxes_rub": flow["taxes_rub"],
        }
    )
    if flow["status"] == "available":
        # Expenses and payouts already change NAV: do not subtract/add them twice.
        investment_result = delta - amount(flow["net_contributions_rub"])
        result["investment_result_rub"] = decimal_text(investment_result)
        denominator = _dietz_denominator(start_nav, operations, begin, end)
        result["return_denominator_rub"] = decimal_text(denominator)
        if start_nav >= 0 and end_nav >= 0 and denominator >= Decimal("0.01"):
            result["return_percent"] = decimal_text(investment_result / denominator * _HUNDRED)
            result["return_status"] = "available"
            result["return_reason"] = None
        else:
            result["return_reason"] = "non_positive_or_negligible_invested_capital"
    else:
        result["return_reason"] = flow["reason"]
    return result


def _dietz_denominator(
    start_nav: Decimal, operations: Sequence[Mapping[str, Any]], begin: datetime, end: datetime,
) -> Decimal:
    """Modified Dietz; use execution timestamps, never ingestion time or binary money floats.

    A flow at the ending valuation has weight zero; a flow at the beginning
    is already in opening NAV and is excluded by the same accounting boundary.
    Called only after cash-flow classification and coverage succeed.
    """
    span = end - begin
    duration = Decimal(span.days * 86_400 + span.seconds) + Decimal(span.microseconds) / 1_000_000
    denominator = start_nav
    for operation in operations:
        classified = _executed_cashflow(operation, begin, end, set(), set())
        if classified is None or classified[0] not in _INPUT | _OUTPUT:
            continue
        remaining = end - classified[1]
        seconds = (
            Decimal(remaining.days * 86_400 + remaining.seconds)
            + Decimal(remaining.microseconds) / 1_000_000
        )
        payment = _operation_amount(operation)
        assert payment is not None  # cashflow_summary already verified this exact operation set
        denominator += payment * seconds / duration
    return denominator


def _portfolio_goal_amount(
    goal: Mapping[str, Any], snapshot: Mapping[str, Any] | None, now: datetime,
) -> tuple[Decimal | None, datetime | None, str | None]:
    observed = timestamp(snapshot.get("captured_at")) if snapshot else None
    if (
        snapshot is None or observed is None or observed > now
        or snapshot.get("analysis_status") != "observed"
    ):
        return None, observed, "portfolio_not_reconciled"
    current = amount(snapshot["nav_rub"]) * amount(goal["allocation_percent"]) / _HUNDRED
    return current, observed, None


def _income_goal_amount(
    goal: Mapping[str, Any], operations: Sequence[Mapping[str, Any]],
    watermark: datetime | None, history_complete: bool, now: datetime,
) -> tuple[Decimal | None, datetime | None, str | None]:
    if watermark is None or watermark > now:
        return None, None, "history_incomplete"
    begin = datetime.combine(_date(goal["start_date"]), time.min, ZoneInfo(_MOSCOW_TIMEZONE))
    if begin >= watermark:
        return None, None, "goal_period_not_observed"
    flow = cashflow_summary(
        operations, from_at=begin.astimezone(UTC) - timedelta(microseconds=1),
        to_at=watermark, complete=history_complete,
    )
    if flow["income"]["status"] != "available":
        return None, None, flow["income"]["reason"]
    current = amount(flow["income"]["total_rub"]) * amount(goal["allocation_percent"]) / _HUNDRED
    return current, watermark, None


def goal_progress(
    goal: Mapping[str, Any],
    *,
    connection: Mapping[str, Any] | None,
    snapshot: Mapping[str, Any] | None,
    operations: Sequence[Mapping[str, Any]],
    watermark: datetime | None,
    history_complete: bool,
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
        current, observed, reason = _income_goal_amount(
            goal, operations, watermark, history_complete, now,
        )
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
            status="available", amount_rub=decimal_text(current),
            percent=decimal_text(current / target * _HUNDRED),
            remaining_rub=decimal_text(max(_ZERO, target - current)),
        )
        if source != "manual" and observed is not None and now - observed > timedelta(hours=36):
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
        local = now.astimezone(ZoneInfo(preferences["quiet_hours"]["timezone"]))
        start = local.replace(hour=0, minute=0, second=0, microsecond=0)
        if frequency == "weekly":
            start -= timedelta(days=start.weekday())
    counts = dict.fromkeys(CATEGORIES, 0)
    if frequency != "off":
        for item in events:
            at = timestamp(item.get("occurred_at"))
            if at is not None and start <= at <= now and item.get("read_at") is None:
                counts[item["category"]] += 1
    return {
        "frequency": frequency,
        "from": start.isoformat(),
        "count": sum(counts.values()),
        "by_category": counts,
    }
