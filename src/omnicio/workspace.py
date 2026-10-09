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
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .financial import MAX_USER_AMOUNT_RUB, PERCENT_SCALE, RUB_QUANTUM
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
_INCOME_FIELDS = ("coupons_rub", "dividends_rub", "other_income_rub")
_INCOME_PAYMENT_FIELDS = (*_INCOME_FIELDS, "redemptions_rub")
_PAYMENT_FIELDS = (*_INCOME_PAYMENT_FIELDS, "net_contributions_rub", "fees_rub", "taxes_rub")
_SOURCE = "https://developer.tbank.ru/invest/services/operations/methods"


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


def operation_category(operation_type: object) -> str:
    """One classification shared by the ledger and financial explanations."""
    kind = str(operation_type or "").removeprefix("OPERATION_TYPE_")
    for choices, category in (
        (_INPUT, "contribution"), (_OUTPUT, "withdrawal"), (_FEES, "fee"),
        (_TAXES, "tax"), (_INCOME.keys(), "income"), (_REDEMPTIONS, "principal_return"),
        (_INTERNAL, "internal"), (_NON_INCOME_TRANSFERS, "non_cash_transfer"),
    ):
        if kind in choices:
            return category
    return "unclassified"


def _cashflow_metric(kind: str) -> str:
    if kind in _INPUT | _OUTPUT:
        return "net_contributions_rub"
    if kind in _FEES:
        return "fees_rub"
    if kind in _TAXES:
        return "taxes_rub"
    if kind in _REDEMPTIONS:
        return "redemptions_rub"
    return _INCOME[kind]


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


@dataclass(slots=True)
class _PaymentTotals:
    values: dict[str, Decimal]
    months: dict[str, dict[str, Decimal]]
    native: dict[str, dict[str, Decimal]]
    reasons: set[str]
    income_reasons: set[str]
    metric_reasons: dict[str, set[str]]
    metric_counts: dict[str, int]


def _record_payment(
    totals: _PaymentTotals, operation: Mapping[str, Any], kind: str, at: datetime,
    reasons: set[str], income_reasons: set[str],
) -> None:
    currency = str(operation.get("payment_currency") or "").upper()
    try:
        native_payment = amount(operation.get("payment_value"))
    except ValueError:
        native_payment = None
    if native_payment is not None and re.fullmatch(r"[A-Z]{3}", currency):
        currency_values = totals.native.setdefault(currency, dict.fromkeys(_PAYMENT_FIELDS, _ZERO))
        _accumulate_cashflow(kind, at, native_payment, currency_values, {})
    metric = _cashflow_metric(kind)
    payment = _cashflow_payment(operation, kind, reasons, income_reasons)
    if payment is None:
        totals.metric_reasons[metric].update(reasons)
        return
    totals.metric_counts[metric] += 1
    _accumulate_cashflow(kind, at, payment, totals.values, totals.months)


def _record_cashflow(
    totals: _PaymentTotals, operation: Mapping[str, Any], from_at: datetime, to_at: datetime,
) -> None:
    # Errors belong to the current operation before they are merged. Repeating
    # an error already seen in another category must not hide its metric impact.
    reasons: set[str] = set()
    income_reasons: set[str] = set()
    parsed = _executed_cashflow(operation, from_at, to_at, reasons, income_reasons)
    if parsed is None:
        for key in totals.values:
            metric_errors = income_reasons if key in _INCOME_PAYMENT_FIELDS else reasons
            totals.metric_reasons[key].update(metric_errors)
    else:
        kind, at = parsed
        _record_payment(totals, operation, kind, at, reasons, income_reasons)
    totals.reasons.update(reasons)
    totals.income_reasons.update(income_reasons)


def _payment_metrics(totals: _PaymentTotals) -> dict[str, dict[str, Any]]:
    metrics = {}
    for key, value in totals.values.items():
        reasons, count = totals.metric_reasons[key], totals.metric_counts[key]
        status = "complete"
        if reasons:
            status = "partial" if count else "unavailable"
        metrics[key] = {
            "status": status,
            "value_rub": decimal_text(value) if not reasons else None,
            "observed_rub": decimal_text(value) if count else None,
            "reason": ",".join(sorted(reasons)) or None,
        }
    return metrics


def _native_payment_sums(
    native: Mapping[str, Mapping[str, Decimal]], fields: Sequence[str],
) -> dict[str, dict[str, str]]:
    return {currency: {key.removesuffix("_rub"): decimal_text(row[key]) for key in fields}
            for currency, row in sorted(native.items())}


def _income_summary(
    totals: _PaymentTotals, metrics: Mapping[str, dict[str, Any]],
    from_at: datetime, to_at: datetime,
) -> dict[str, Any]:
    reasons = totals.income_reasons
    values = totals.values
    income_total = sum((values[key] for key in _INCOME_FIELDS), _ZERO)
    months = [{"month": month, **{key: decimal_text(row[key]) for key in _INCOME_FIELDS},
               "total_rub": decimal_text(sum(row.values(), _ZERO))}
              for month, row in sorted(totals.months.items())]
    return {
        "status": "available" if not reasons else "unavailable",
        "reason": ",".join(sorted(reasons)) or None,
        "from": from_at.isoformat(),
        "to": to_at.isoformat(),
        **{key: decimal_text(values[key]) if not reasons else None
           for key in _INCOME_PAYMENT_FIELDS},
        "total_rub": decimal_text(income_total) if not reasons else None,
        "by_month": [] if reasons else months,
        "source_url": _SOURCE,
        "tax_basis": "broker_payments_before_separate_tax_operations",
        "metric_coverage": {key: metrics[key] for key in _INCOME_PAYMENT_FIELDS},
        "native_payment_sums": _native_payment_sums(totals.native, _INCOME_PAYMENT_FIELDS),
    }


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
    reasons = set() if complete else {"history_incomplete"}
    totals = _PaymentTotals(
        values=dict.fromkeys(_PAYMENT_FIELDS, _ZERO), months={}, native={},
        reasons=reasons, income_reasons=set(reasons),
        metric_reasons={key: set(reasons) for key in _PAYMENT_FIELDS},
        metric_counts=dict.fromkeys(_PAYMENT_FIELDS, 0),
    )
    for operation in operations:
        _record_cashflow(totals, operation, from_at, to_at)
    metrics = _payment_metrics(totals)
    return {
        "status": "available" if not reasons else "unavailable",
        "reason": ",".join(sorted(reasons)) or None,
        "from": from_at.isoformat(), "to": to_at.isoformat(),
        **{key: decimal_text(value) if not reasons else None
           for key, value in totals.values.items()},
        "metrics": metrics,
        "native_payment_sums": {
            "basis": "observed_executed_payments_without_fx_conversion",
            "history_complete": complete,
            "currencies": _native_payment_sums(totals.native, _PAYMENT_FIELDS),
        },
        "income": _income_summary(totals, metrics, from_at, to_at),
    }


def snapshot_valuation_complete(snapshot: Mapping[str, Any]) -> bool:
    """Use independent NAV coverage; legacy snapshots require observed status."""
    valuation_status = snapshot.get("valuation_status")
    evidence = snapshot.get("evidence")
    if valuation_status is None and isinstance(evidence, Mapping):
        analysis = evidence.get("analysis")
        if isinstance(analysis, Mapping):
            valuation_status = analysis.get("valuation_status")
    return (valuation_status == "complete" if valuation_status is not None
            else snapshot.get("analysis_status") == "observed")


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
        "return_time_basis": "broker_operation_instruction_time",
        "return_limitations": [
            "Cash flows are weighted by the broker's recorded operation time (OperationItem.date), "
            "which is the instruction date, not a separately confirmed settlement timestamp.",
            "Large flows and volatility can make this estimate differ from time-weighted return.",
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
        and snapshot_valuation_complete(row)
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
            "fees_rub": flow["metrics"]["fees_rub"]["value_rub"],
            "taxes_rub": flow["metrics"]["taxes_rub"]["value_rub"],
        }
    )
    contribution = flow["metrics"]["net_contributions_rub"]
    result["metric_coverage"] = flow["metrics"]
    result["native_payment_sums"] = flow["native_payment_sums"]
    result["nav_status"] = "complete"
    if contribution["status"] == "complete":
        result.update(status="available", reason=None,
                      net_contributions_rub=contribution["value_rub"])
        # Expenses and payouts already change NAV: do not subtract/add them twice.
        # Foreign internal payouts/fees need no FX approximation for the RUB
        # account result. Only external transfers require a known RUB value.
        investment_result = delta - amount(contribution["value_rub"])
        result["investment_result_rub"] = decimal_text(investment_result)
        denominator = _dietz_denominator(start_nav, operations, begin, end)
        result["return_denominator_rub"] = decimal_text(denominator)
        if start_nav >= 0 and end_nav >= 0 and denominator >= RUB_QUANTUM:
            result["return_percent"] = decimal_text(investment_result / denominator * PERCENT_SCALE)
            result["return_status"] = "available"
            result["return_reason"] = None
        else:
            result["return_reason"] = "non_positive_or_negligible_invested_capital"
    else:
        result["return_reason"] = contribution["reason"]
    return result


def _dietz_denominator(
    start_nav: Decimal, operations: Sequence[Mapping[str, Any]], begin: datetime, end: datetime,
) -> Decimal:
    """Modified Dietz estimate using broker operation times, never ingestion time.

    A flow at the ending valuation has weight zero; a flow at the beginning
    is already in opening NAV and is excluded by the same accounting boundary.
    OperationItem.date is the broker's instruction time; exact settlement time
    is not supplied by this ledger and must not be claimed as known.
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
        or not snapshot_valuation_complete(snapshot)
    ):
        return None, observed, "portfolio_not_reconciled"
    current = amount(snapshot["nav_rub"]) * amount(goal["allocation_percent"]) / PERCENT_SCALE
    return current, observed, None


def income_goal_start(goal: Mapping[str, Any]) -> datetime:
    """The goal's inclusive Moscow calendar boundary, shared with ledger selection."""
    value = goal["start_date"]
    started = value if type(value) is date else _date(value)
    return datetime.combine(
        started, time.min, ZoneInfo(_MOSCOW_TIMEZONE),
    ).astimezone(UTC)


def _income_goal_amount(
    goal: Mapping[str, Any], operations: Sequence[Mapping[str, Any]],
    watermark: datetime | None, history_complete: bool, now: datetime,
) -> tuple[Decimal | None, datetime | None, str | None]:
    if watermark is None or watermark > now:
        return None, None, "history_incomplete"
    begin = income_goal_start(goal)
    if begin >= watermark:
        return None, None, "goal_period_not_observed"
    flow = cashflow_summary(
        operations, from_at=begin - timedelta(microseconds=1),
        to_at=watermark, complete=history_complete,
    )
    if flow["income"]["status"] != "available":
        return None, None, flow["income"]["reason"]
    current = (amount(flow["income"]["total_rub"])
               * amount(goal["allocation_percent"]) / PERCENT_SCALE)
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
