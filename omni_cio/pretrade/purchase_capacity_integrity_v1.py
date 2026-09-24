from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
from typing import Any


MONEY_TOLERANCE = Decimal("0.01")
PRICE_TIMES_LOT_TYPES = {
    "share",
    "etf",
    "currency",
    "INSTRUMENT_TYPE_SHARE",
    "INSTRUMENT_TYPE_ETF",
    "INSTRUMENT_TYPE_CURRENCY",
}


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError, AttributeError):
        return None
    return result if result.is_finite() else None


def _integer(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (ValueError, TypeError, OverflowError):
        return None


def _decimal_string(value: Decimal) -> str:
    if value == 0:
        return "0"
    normalized = value.normalize()
    return format(normalized, "f")


def _currency(value: Any) -> str:
    text = str(value or "").strip().upper()
    return "" if text in {"", "UNAVAILABLE", "NOT_APPLICABLE"} else text


def _money(value: Any) -> tuple[Decimal | None, str]:
    data = _dict(value)
    return _decimal(data.get("amount")), _currency(data.get("currency"))


def _money_view(amount: Decimal, currency: str) -> dict[str, str]:
    return {
        "amount": _decimal_string(amount),
        "currency": currency or "unavailable",
    }


def _comparison(
    *,
    formula: str,
    expected: Decimal | None,
    reported: Decimal | None,
    currency: str,
    tolerance: Decimal = MONEY_TOLERANCE,
    reason: str | None = None,
    not_applicable: bool = False,
) -> dict[str, Any]:
    if not_applicable:
        return {
            "status": "not_applicable",
            "formula": formula,
            "expected": "not_applicable",
            "reported": (
                "unavailable" if reported is None else _decimal_string(reported)
            ),
            "difference": "not_applicable",
            "tolerance": _decimal_string(tolerance),
            "currency": currency or "unavailable",
            "reason": reason or "The formula is not applicable to this instrument.",
        }

    if expected is None or reported is None:
        return {
            "status": "unavailable",
            "formula": formula,
            "expected": (
                "unavailable" if expected is None else _decimal_string(expected)
            ),
            "reported": (
                "unavailable" if reported is None else _decimal_string(reported)
            ),
            "difference": "unavailable",
            "tolerance": _decimal_string(tolerance),
            "currency": currency or "unavailable",
            "reason": reason or "At least one required value is unavailable.",
        }

    difference = reported - expected
    passed = abs(difference) <= tolerance
    return {
        "status": "passed" if passed else "failed",
        "formula": formula,
        "expected": _decimal_string(expected),
        "reported": _decimal_string(reported),
        "difference": _decimal_string(difference),
        "tolerance": _decimal_string(tolerance),
        "currency": currency or "unavailable",
        "reason": reason or "",
    }



def _commission_candidates(
    order: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, tuple[Decimal, str]]]:
    source_fields: dict[str, Any] = {}
    candidates: dict[str, tuple[Decimal, str]] = {}
    for field_name in (
        "executed_commission",
        "executed_commission_rub",
        "service_commission",
        "deal_commission",
    ):
        amount, currency = _money(order.get(field_name))
        if amount is None:
            continue
        source_fields[field_name] = _money_view(amount, currency)
        candidates[field_name] = (amount, currency)
    return source_fields, candidates


def _canonical_commission(
    candidates: dict[str, tuple[Decimal, str]],
    preview_currency: str,
) -> tuple[str, Decimal | None, str]:
    executed = candidates.get("executed_commission")
    if executed is not None:
        return "executed_commission", executed[0], executed[1]

    executed_rub = candidates.get("executed_commission_rub")
    if executed_rub is not None and preview_currency == "RUB":
        return "executed_commission_rub", executed_rub[0], executed_rub[1]

    components = [
        item
        for item in (
            candidates.get("service_commission"),
            candidates.get("deal_commission"),
        )
        if item is not None
    ]
    component_currencies = {currency for _, currency in components if currency}
    if not components or len(component_currencies) > 1:
        return "unavailable", None, ""
    return (
        "service_plus_deal_fallback",
        sum((amount for amount, _ in components), Decimal("0")),
        next(iter(component_currencies), "") or preview_currency,
    )


def _component_commission_check(
    *,
    candidates: dict[str, tuple[Decimal, str]],
    canonical_amount: Decimal | None,
    canonical_currency: str,
    preview_currency: str,
) -> dict[str, Any]:
    component_values = [
        item
        for item in (
            candidates.get("service_commission"),
            candidates.get("deal_commission"),
        )
        if item is not None
    ]
    component_currencies = {currency for _, currency in component_values if currency}
    result: dict[str, Any] = {
        "status": "unavailable",
        "components_sum": "unavailable",
        "canonical_amount": (
            "unavailable"
            if canonical_amount is None
            else _decimal_string(canonical_amount)
        ),
        "difference": "unavailable",
        "currency": canonical_currency or preview_currency or "unavailable",
    }
    currencies_compatible = (
        not canonical_currency
        or not component_currencies
        or canonical_currency in component_currencies
    )
    if (
        canonical_amount is None
        or not component_values
        or len(component_currencies) > 1
        or not currencies_compatible
    ):
        return result

    components_sum = sum(
        (amount for amount, _ in component_values),
        Decimal("0"),
    )
    difference = components_sum - canonical_amount
    return {
        "status": "matched" if abs(difference) <= MONEY_TOLERANCE else "different",
        "components_sum": _decimal_string(components_sum),
        "canonical_amount": _decimal_string(canonical_amount),
        "difference": _decimal_string(difference),
        "currency": canonical_currency or preview_currency or "unavailable",
    }


def _incorrect_commission_sum(
    *,
    candidates: dict[str, tuple[Decimal, str]],
    canonical_amount: Decimal | None,
    target_currency: str,
) -> tuple[Decimal | None, Decimal | None]:
    if canonical_amount is None or not target_currency:
        return None, None
    same_currency_values = [
        amount
        for amount, currency in candidates.values()
        if currency == target_currency
    ]
    if not same_currency_values:
        return None, None
    naive_sum = sum(same_currency_values, Decimal("0"))
    return naive_sum, naive_sum - canonical_amount


def build_commission_summary(order_preview: Any) -> dict[str, Any]:
    order = _dict(order_preview)
    preview_currency = _currency(
        _dict(order.get("total_order_amount")).get("currency")
        or _dict(order.get("initial_order_amount")).get("currency")
    )
    source_fields, candidates = _commission_candidates(order)
    canonical_source, canonical_amount, canonical_currency = _canonical_commission(
        candidates,
        preview_currency,
    )
    components_sum_check = _component_commission_check(
        candidates=candidates,
        canonical_amount=canonical_amount,
        canonical_currency=canonical_currency,
        preview_currency=preview_currency,
    )
    target_currency = canonical_currency or preview_currency
    naive_sum, overstatement = _incorrect_commission_sum(
        candidates=candidates,
        canonical_amount=canonical_amount,
        target_currency=target_currency,
    )

    return {
        "status": "ok" if canonical_amount is not None else "unavailable",
        "canonical_source": canonical_source,
        "canonical_commission": (
            _money_view(canonical_amount, canonical_currency or preview_currency)
            if canonical_amount is not None
            else {
                "amount": "unavailable",
                "currency": preview_currency or "unavailable",
            }
        ),
        "source_fields": source_fields,
        "components_sum_check": components_sum_check,
        "fields_are_additive": False,
        "double_count_protection": True,
        "naive_sum_if_incorrectly_added": (
            _money_view(naive_sum, target_currency)
            if naive_sum is not None
            else {
                "amount": "unavailable",
                "currency": target_currency or "unavailable",
            }
        ),
        "overstatement_prevented": (
            _money_view(overstatement, target_currency)
            if overstatement is not None
            else {
                "amount": "unavailable",
                "currency": target_currency or "unavailable",
            }
        ),
        "notes": [
            (
                "executed_commission is the preferred aggregate commission and "
                "is not added to executed_commission_rub, service_commission, "
                "or deal_commission."
            ),
            (
                "executed_commission_rub is a RUB representation of the aggregate "
                "commission, not an additional fee."
            ),
            (
                "service_commission and deal_commission are preserved as components "
                "and are used only as a fallback when no aggregate commission is available."
            ),
        ],
    }

def build_currency_consistency(
    payload: dict[str, Any],
    commission_summary: dict[str, Any],
) -> dict[str, Any]:
    instrument = _dict(payload.get("instrument"))
    market_price = _dict(payload.get("market_price"))
    own_funds = _dict(payload.get("own_funds"))
    order_preview = _dict(payload.get("order_preview"))

    fields = {
        "instrument": _currency(instrument.get("currency")),
        "market_price": _currency(market_price.get("currency")),
        "own_funds": _currency(own_funds.get("currency")),
        "initial_order_amount": _currency(
            _dict(order_preview.get("initial_order_amount")).get("currency")
        ),
        "total_order_amount": _currency(
            _dict(order_preview.get("total_order_amount")).get("currency")
        ),
        "canonical_commission": _currency(
            _dict(commission_summary.get("canonical_commission")).get("currency")
        ),
        "remaining_cash": _currency(payload.get("remaining_cash_currency")),
        "aci_value": _currency(
            _dict(_dict(order_preview.get("extra_bond")).get("aci_value")).get(
                "currency"
            )
        ),
    }
    visible_fields = {key: value or "unavailable" for key, value in fields.items()}
    available = [value for value in fields.values() if value]
    unique = sorted(set(available))

    critical_keys = (
        "own_funds",
        "total_order_amount",
        "remaining_cash",
    )
    critical_complete = all(fields[key] for key in critical_keys)
    issues: list[str] = []
    if len(unique) > 1:
        issues.append(
            "Currency mismatch detected between purchase-capacity components."
        )
    if not critical_complete:
        issues.append("At least one critical currency is unavailable.")

    if len(unique) > 1:
        status = "warning"
    elif critical_complete:
        status = "ok"
    else:
        status = "partial"

    return {
        "status": status,
        "currencies": visible_fields,
        "unique_currencies": unique,
        "critical_fields_complete": critical_complete,
        "issues": issues,
    }


def build_limit_summary(payload: dict[str, Any]) -> dict[str, Any]:
    request = _dict(payload.get("request"))
    own_funds = _dict(payload.get("own_funds"))
    quantity_lots = _integer(request.get("quantity_lots"))
    buy_max_lots = _integer(own_funds.get("buy_max_lots"))
    buy_max_market_lots = _integer(own_funds.get("buy_max_market_lots"))

    def within(limit: int | None) -> str:
        if quantity_lots is None or limit is None:
            return "unavailable"
        return str(quantity_lots <= limit).lower()

    return {
        "selected_limit_field": "buy_max_lots",
        "selected_limit_source": "T-Invest GetMaxLots buy_limits",
        "selected_limit_value": (
            str(buy_max_lots) if buy_max_lots is not None else "unavailable"
        ),
        "market_limit_field": "buy_max_market_lots",
        "market_limit_value": (
            str(buy_max_market_lots)
            if buy_max_market_lots is not None
            else "unavailable"
        ),
        "requested_lots": (
            str(quantity_lots) if quantity_lots is not None else "unavailable"
        ),
        "requested_within_selected_limit": within(buy_max_lots),
        "requested_within_market_limit": within(buy_max_market_lots),
        "decision_basis": (
            "buy_max_lots is used because this endpoint previews an explicit-price "
            "limit calculation. buy_max_market_lots is preserved only as a separate "
            "current-market diagnostic."
        ),
    }



def _initial_amount_check(
    *,
    payload: dict[str, Any],
    request: dict[str, Any],
    instrument: dict[str, Any],
    market_price: dict[str, Any],
    order_preview: dict[str, Any],
) -> dict[str, Any]:
    quantity_lots = _integer(request.get("quantity_lots"))
    lot_size = _integer(market_price.get("lot_size") or instrument.get("lot"))
    price = _decimal(market_price.get("price"))
    initial_amount, initial_currency = _money(order_preview.get("initial_order_amount"))
    instrument_type = str(
        instrument.get("instrument_kind") or instrument.get("instrument_type") or ""
    )
    simple_price_formula = instrument_type in PRICE_TIMES_LOT_TYPES
    expected = None
    if (
        simple_price_formula
        and quantity_lots is not None
        and lot_size is not None
        and price is not None
    ):
        expected = price * Decimal(lot_size) * Decimal(quantity_lots)
    return _comparison(
        formula="price × lot_size × quantity_lots = initial_order_amount",
        expected=expected,
        reported=initial_amount,
        currency=initial_currency or _currency(market_price.get("currency")),
        not_applicable=not simple_price_formula,
        reason=(
            "Bond and futures quotations require instrument-specific nominal, "
            "accrued-interest, points, or guarantee treatment; the simple price "
            "times lot formula is intentionally not asserted."
            if not simple_price_formula
            else None
        ),
    )


def _total_amount_check(
    *,
    order_preview: dict[str, Any],
    commission_summary: dict[str, Any],
) -> tuple[dict[str, Any], Decimal | None]:
    initial_amount, _ = _money(order_preview.get("initial_order_amount"))
    total_amount, total_currency = _money(order_preview.get("total_order_amount"))
    canonical_amount, canonical_currency = _money(
        commission_summary.get("canonical_commission")
    )
    aci_amount, aci_currency = _money(
        _dict(order_preview.get("extra_bond")).get("aci_value")
    )
    expected = None
    if initial_amount is not None and canonical_amount is not None:
        expected = initial_amount + canonical_amount + (aci_amount or Decimal("0"))

    formula = "initial_order_amount + canonical_commission"
    if aci_amount is not None:
        formula += " + aci_value"
    formula += " = total_order_amount"
    return (
        _comparison(
            formula=formula,
            expected=expected,
            reported=total_amount,
            currency=total_currency or canonical_currency or aci_currency,
            reason=(
                "GetOrderPrice may include instrument-specific values. The check uses "
                "only the aggregate commission once and adds returned bond ACI once."
            ),
        ),
        total_amount,
    )


def _calculation_overall_status(
    checks: list[dict[str, Any]],
) -> tuple[str, int, int, int, int]:
    passed = sum(check["status"] == "passed" for check in checks)
    failed = sum(check["status"] == "failed" for check in checks)
    unavailable = sum(check["status"] == "unavailable" for check in checks)
    not_applicable = sum(check["status"] == "not_applicable" for check in checks)
    if failed:
        status = "failed"
    elif passed and unavailable == 0:
        status = "passed"
    elif passed:
        status = "partial"
    else:
        status = "unavailable"
    return status, passed, failed, unavailable, not_applicable


def build_calculation_checks(
    payload: dict[str, Any],
    commission_summary: dict[str, Any],
    currency_consistency: dict[str, Any],
) -> dict[str, Any]:
    request = _dict(payload.get("request"))
    instrument = _dict(payload.get("instrument"))
    market_price = _dict(payload.get("market_price"))
    own_funds = _dict(payload.get("own_funds"))
    order_preview = _dict(payload.get("order_preview"))

    initial_check = _initial_amount_check(
        payload=payload,
        request=request,
        instrument=instrument,
        market_price=market_price,
        order_preview=order_preview,
    )
    total_check, total_amount = _total_amount_check(
        order_preview=order_preview,
        commission_summary=commission_summary,
    )
    own_money = _decimal(own_funds.get("buy_money_amount"))
    remaining_reported = _decimal(payload.get("remaining_cash_estimate"))
    remaining_expected = (
        own_money - total_amount
        if own_money is not None and total_amount is not None
        else None
    )
    remaining_check = _comparison(
        formula="buy_money_amount - total_order_amount = remaining_cash_estimate",
        expected=remaining_expected,
        reported=remaining_reported,
        currency=_currency(payload.get("remaining_cash_currency")),
    )

    checks = [initial_check, total_check, remaining_check]
    (
        overall_status,
        passed,
        failed,
        unavailable,
        not_applicable,
    ) = _calculation_overall_status(checks)
    integrity_confirmed = all(
        (
            overall_status == "passed",
            currency_consistency.get("status") == "ok",
            commission_summary.get("status") == "ok",
            commission_summary.get("double_count_protection") is True,
        )
    )

    return {
        "initial_order_amount": initial_check,
        "total_order_amount": total_check,
        "remaining_cash": remaining_check,
        "overall_status": overall_status,
        "passed": passed,
        "failed": failed,
        "unavailable": unavailable,
        "not_applicable": not_applicable,
        "integrity_confirmed": integrity_confirmed,
    }

def apply_purchase_capacity_integrity(payload: Any) -> dict[str, Any]:
    result = deepcopy(_dict(payload))
    commission_summary = build_commission_summary(result.get("order_preview"))
    currency_consistency = build_currency_consistency(
        result,
        commission_summary,
    )
    limit_summary = build_limit_summary(result)
    calculation_checks = build_calculation_checks(
        result,
        commission_summary,
        currency_consistency,
    )

    result["commission_summary"] = commission_summary
    result["currency_consistency"] = currency_consistency
    result["limit_summary"] = limit_summary
    result["calculation_checks"] = calculation_checks

    quality = _dict(result.get("quality"))
    quality.update(
        {
            "purchase_capacity_integrity": True,
            "commission_double_count_protected": True,
            "currency_consistent": currency_consistency["status"] == "ok",
            "calculation_integrity_confirmed": calculation_checks[
                "integrity_confirmed"
            ],
            "calculation_checks_passed": calculation_checks["passed"],
            "calculation_checks_failed": calculation_checks["failed"],
            "calculation_checks_unavailable": calculation_checks["unavailable"],
        }
    )
    result["quality"] = quality

    warnings = list(result.get("warnings") or [])
    warnings.append(
        "Commission fields are not added together. One canonical aggregate "
        "commission is selected and component or RUB representations are preserved "
        "only for diagnostics."
    )
    if currency_consistency["status"] != "ok":
        warnings.append(
            "Purchase-capacity currencies are incomplete or inconsistent; "
            "cross-currency affordability is not confirmed."
        )
    if calculation_checks["overall_status"] == "failed":
        warnings.append(
            "At least one arithmetic integrity check failed; inspect the reported "
            "and expected values before relying on the preview."
        )
    result["warnings"] = warnings
    result["integrity_status"] = (
        "ok" if calculation_checks["integrity_confirmed"] else "warning"
    )
    return result
