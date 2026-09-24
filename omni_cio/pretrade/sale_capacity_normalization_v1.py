from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping

from fastapi import HTTPException

from omni_cio.pretrade.purchase_capacity_v1 import (
    PRICE_FRESH_SECONDS,
    _decimal_or_none,
    _instrument_from_resolution,
    _order_preview_view,
    _price_freshness,
    _status_dict,
)
from omni_cio.pretrade.purchase_capacity_integrity_v1 import build_commission_summary


_ALLOWED_PRICE_BASES = frozenset({"best_bid", "last_price"})


def _integer_or_none(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (ValueError, TypeError, OverflowError):
        return None


def _direction_is_sell(value: Any) -> bool:
    if value is None or isinstance(value, bool):
        return False
    name = getattr(value, "name", None)
    if isinstance(name, str) and name.upper().endswith("SELL"):
        return True
    raw = getattr(value, "value", value)
    if isinstance(raw, int):
        return raw == 2
    text = str(raw).strip().upper()
    return text.endswith("SELL") or text == "2"


def select_sale_price(
    *,
    base: Any,
    price_basis: str,
    market_snapshot: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if price_basis not in _ALLOWED_PRICE_BASES:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INVALID_PRICE_BASIS",
                "field": "price_basis",
                "message": "price_basis must be best_bid or last_price.",
            },
        )

    snapshot = _status_dict(market_snapshot)
    if price_basis == "last_price":
        source = _status_dict(snapshot.get("last_price"))
        raw_price = source.get("price")
        source_time = source.get("time")
        age_seconds = source.get("age_seconds")
        source_name = "T-Invest GetLastPrices"
    else:
        source = _status_dict(snapshot.get("order_book"))
        best_bid = _status_dict(source.get("best_bid"))
        raw_price = best_bid.get("price")
        source_time = source.get("time")
        age_seconds = source.get("age_seconds")
        source_name = "T-Invest GetOrderBook best bid"

    price = _decimal_or_none(base, raw_price)
    freshness = _price_freshness(age_seconds, source_time, price_basis)
    freshness.setdefault(
        "fresh_threshold_seconds",
        base.decimal_string(PRICE_FRESH_SECONDS),
    )
    result = {
        "status": "ok" if price is not None and price > 0 else "unavailable",
        "basis": price_basis,
        "source": source_name,
        "price": (
            base.decimal_string(price)
            if price is not None and price > 0
            else "unavailable"
        ),
        "source_time": source_time or "unavailable",
        "age_seconds": (str(age_seconds) if age_seconds is not None else "unavailable"),
        "freshness": freshness,
    }
    return result


def _exact_lots(
    *,
    units: Decimal | None,
    lot_size: int | None,
) -> int | None:
    if units is None or units < 0 or lot_size is None or lot_size <= 0:
        return None
    lots = units / Decimal(lot_size)
    if lots != lots.to_integral_value():
        return None
    result = int(lots)
    return result if result >= 0 else None


def _position_limits_view(
    *,
    base: Any,
    positions_data: Mapping[str, Any] | None,
    max_lots_data: Mapping[str, Any] | None,
    instrument_uid: str,
    lot_size: int | None,
    positions_status: str,
    max_lots_status: str,
) -> dict[str, Any]:
    positions = _status_dict(positions_data)
    securities = positions.get("securities")
    matching_rows: list[Mapping[str, Any]] = []
    invalid_rows = 0
    if isinstance(securities, list):
        for row in securities:
            if not isinstance(row, Mapping):
                invalid_rows += 1
                continue
            row_uid = str(
                row.get("instrument_uid") or row.get("instrument_id") or ""
            ).strip()
            if row_uid == instrument_uid:
                matching_rows.append(row)
    elif securities is not None:
        invalid_rows += 1

    balance_units: Decimal | None = None
    blocked_units: Decimal | None = None
    duplicate_rows = max(0, len(matching_rows) - 1)
    if len(matching_rows) == 1:
        balance_units = _decimal_or_none(base, matching_rows[0].get("balance"))
        blocked_units = _decimal_or_none(base, matching_rows[0].get("blocked"))
    position_lots = _exact_lots(units=balance_units, lot_size=lot_size)
    blocked_lots = _exact_lots(units=blocked_units, lot_size=lot_size)

    max_data = _status_dict(max_lots_data)
    sell_limits = _status_dict(max_data.get("sell_limits"))
    sell_max_lots = _integer_or_none(sell_limits.get("sell_max_lots"))
    currency = str(max_data.get("currency", "") or "").upper()
    complete = (
        positions_status == "ok"
        and max_lots_status == "ok"
        and len(matching_rows) == 1
        and invalid_rows == 0
        and duplicate_rows == 0
        and position_lots is not None
        and blocked_lots is not None
        and sell_max_lots is not None
    )
    return {
        "status": "ok" if complete else "partial",
        "source": "T-Invest GetPositions + GetMaxLots sell_limits",
        "currency": currency or "unavailable",
        "position_units": (
            base.decimal_string(balance_units)
            if balance_units is not None
            else "unavailable"
        ),
        "blocked_units": (
            base.decimal_string(blocked_units)
            if blocked_units is not None
            else "unavailable"
        ),
        "position_lots": position_lots if position_lots is not None else "unavailable",
        "blocked_lots": blocked_lots if blocked_lots is not None else "unavailable",
        "sell_max_lots": sell_max_lots if sell_max_lots is not None else "unavailable",
        "matching_position_rows": len(matching_rows),
        "duplicate_position_rows": duplicate_rows,
        "invalid_position_rows": invalid_rows,
        "exact_lot_conversion": position_lots is not None and blocked_lots is not None,
        "complete": complete,
    }


def _open_orders_view(
    *,
    orders_data: Mapping[str, Any] | None,
    instrument_uid: str,
    orders_status: str,
) -> dict[str, Any]:
    payload = _status_dict(orders_data)
    rows = payload.get("orders")
    conflicting_lots = 0
    matching_orders = 0
    invalid_rows = 0
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, Mapping):
                invalid_rows += 1
                continue
            row_uid = str(
                row.get("instrument_uid") or row.get("instrument_id") or ""
            ).strip()
            if row_uid != instrument_uid or not _direction_is_sell(
                row.get("direction")
            ):
                continue
            requested = _integer_or_none(row.get("lots_requested"))
            executed = _integer_or_none(row.get("lots_executed"))
            if requested is None or requested < 0 or executed is None or executed < 0:
                invalid_rows += 1
                continue
            matching_orders += 1
            conflicting_lots += max(0, requested - executed)
    elif rows is not None:
        invalid_rows += 1
    checked = orders_status == "ok" and invalid_rows == 0
    return {
        "status": "ok" if checked else "partial",
        "source": "T-Invest GetOrders",
        "checked": checked,
        "matching_open_sell_orders": matching_orders,
        "conflicting_sell_lots": conflicting_lots,
        "invalid_order_rows": invalid_rows,
    }


def _normalized_money(
    base: Any,
    value: Any,
) -> tuple[Decimal, str] | None:
    data = _status_dict(value)
    amount = _decimal_or_none(base, data.get("amount"))
    currency = str(data.get("currency", "") or "").upper()
    if amount is None or not currency:
        return None
    return amount, currency


def _gross_proceeds_view(
    *,
    base: Any,
    order_preview: Mapping[str, Any],
) -> dict[str, str] | None:
    security = _normalized_money(base, order_preview.get("initial_order_amount"))
    if security is None:
        return None
    security_amount, security_currency = security
    aci = _normalized_money(
        base,
        _status_dict(order_preview.get("extra_bond")).get("aci_value"),
    )
    aci_amount = Decimal("0")
    if aci is not None:
        aci_amount, aci_currency = aci
        if aci_currency != security_currency:
            return None
    return {
        "amount": base.decimal_string(security_amount + aci_amount),
        "currency": security_currency,
    }


def _sale_currency_consistency(
    *,
    instrument: Mapping[str, Any],
    market_price: Mapping[str, Any],
    position_limits: Mapping[str, Any],
    order_preview: Mapping[str, Any],
    commission_summary: Mapping[str, Any],
) -> dict[str, Any]:
    fields = {
        "instrument": str(instrument.get("currency", "") or "").upper(),
        "market_price": str(market_price.get("currency", "") or "").upper(),
        "position_limits": str(position_limits.get("currency", "") or "").upper(),
        "initial_order_amount": str(
            _status_dict(order_preview.get("initial_order_amount")).get("currency", "")
            or ""
        ).upper(),
        "aci_value": str(
            _status_dict(
                _status_dict(order_preview.get("extra_bond")).get("aci_value")
            ).get("currency", "")
            or ""
        ).upper(),
        "canonical_commission": str(
            _status_dict(commission_summary.get("canonical_commission")).get(
                "currency", ""
            )
            or ""
        ).upper(),
    }
    visible = {
        name: value
        for name, value in fields.items()
        if value and value not in {"UNAVAILABLE", "NOT_APPLICABLE"}
    }
    currencies = set(visible.values())
    return {
        "status": "ok" if len(currencies) <= 1 and bool(visible) else "warning",
        "fields": fields,
        "currencies_detected": sorted(currencies),
        "single_currency": len(currencies) <= 1 and bool(visible),
    }


def build_sale_capacity_preview(
    *,
    base: Any,
    app_version: str,
    account: Mapping[str, Any],
    instrument_uid: str,
    instrument_resolution: Mapping[str, Any] | None,
    price_basis: str,
    quantity_lots: int,
    price_info: Mapping[str, Any],
    positions_data: Mapping[str, Any] | None,
    max_lots_data: Mapping[str, Any] | None,
    orders_data: Mapping[str, Any] | None,
    order_price_data: Mapping[str, Any] | None,
    component_statuses: Mapping[str, str],
    component_errors: list[dict[str, Any]] | None = None,
    market_snapshot: Mapping[str, Any] | None = None,
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    resolution = _status_dict(instrument_resolution)
    instrument = _instrument_from_resolution(resolution)
    lot_size = _integer_or_none(instrument.get("lot"))
    order_price_status = component_statuses.get("order_price", "not_requested")
    position_limits = _position_limits_view(
        base=base,
        positions_data=positions_data,
        max_lots_data=max_lots_data,
        instrument_uid=instrument_uid,
        lot_size=lot_size,
        positions_status=component_statuses.get("positions", "not_requested"),
        max_lots_status=component_statuses.get("max_lots", "not_requested"),
    )
    open_orders = _open_orders_view(
        orders_data=orders_data,
        instrument_uid=instrument_uid,
        orders_status=component_statuses.get("open_orders", "not_requested"),
    )
    order_preview = _order_preview_view(
        base,
        order_price_data,
        order_price_status,
        quantity_lots,
    )
    gross_proceeds = _gross_proceeds_view(base=base, order_preview=order_preview)
    if gross_proceeds is not None:
        order_preview["gross_proceeds"] = gross_proceeds
    commission_summary = build_commission_summary(order_preview)
    market_price = dict(price_info)
    market_price["currency"] = (
        str(instrument.get("currency") or position_limits.get("currency") or "").upper()
        or "unavailable"
    )
    market_price["lot_size"] = lot_size if lot_size is not None else 0
    currency_consistency = _sale_currency_consistency(
        instrument=instrument,
        market_price=market_price,
        position_limits=position_limits,
        order_preview=order_preview,
        commission_summary=commission_summary,
    )

    instrument_resolved = resolution.get("status") == "resolved"
    price_available = price_info.get("status") == "ok"
    position_available = position_limits.get("complete") is True
    open_orders_checked = open_orders.get("checked") is True
    commission_available = commission_summary.get("status") == "ok"
    source_complete = (
        instrument_resolved
        and price_available
        and position_available
        and open_orders_checked
        and order_price_status == "ok"
        and commission_available
        and currency_consistency.get("status") == "ok"
        and not component_errors
    )
    if source_complete:
        status = "ok"
    elif any(
        (
            instrument_resolved,
            price_available,
            position_available,
            open_orders_checked,
            order_price_status == "ok",
        )
    ):
        status = "partial"
    else:
        status = "error"

    snapshot = _status_dict(market_snapshot)
    freshness = _status_dict(price_info.get("freshness"))
    warnings = [
        (
            "This service performs read-only sale-capacity calculations and does not "
            "create, replace, cancel, or submit an order."
        ),
        (
            "The tax basis is intentionally unavailable in this collector. A strict "
            "sell pre-trade preview must remain blocked until separate verified tax "
            "evidence is supplied."
        ),
        (
            "GetMaxLots own-position sale limits and active orders are preserved "
            "separately. Short selling is not permitted."
        ),
    ]
    if freshness.get("status") == "stale":
        warnings.append(
            "The selected sale price is stale relative to the gateway freshness threshold."
        )
    payload = {
        "status": status,
        "version": app_version,
        "retrieved_at": retrieved_at or datetime.now(timezone.utc).isoformat(),
        "account": dict(account),
        "request": {
            "instrument_uid": instrument_uid,
            "price_basis": price_basis,
            "quantity_lots": quantity_lots,
            "direction": "ORDER_DIRECTION_SELL",
        },
        "instrument": instrument,
        "instrument_resolution": {
            "status": resolution.get("status", "unavailable"),
            "identity_check": _status_dict(resolution.get("identity_check")),
            "resolution": _status_dict(resolution.get("resolution")),
        },
        "market_price": market_price,
        "market_context": {
            "requested": True,
            "dealer_session": bool(snapshot.get("dealer_session", False)),
            "market_data_sources": _status_dict(snapshot.get("market_data_sources")),
            "trading_flag_consistency": _status_dict(
                snapshot.get("trading_flag_consistency")
            ),
        },
        "position_limits": position_limits,
        "open_orders": open_orders,
        "order_preview": order_preview,
        "commission_summary": commission_summary,
        "tax_basis": {
            "status": "unavailable",
            "confirmed": False,
            "source": "not_collected_by_live_sale_capacity_v1",
            "estimated_tax": {
                "amount": "unavailable",
                "currency": market_price.get("currency", "unavailable"),
            },
        },
        "price_freshness": freshness,
        "currency_consistency": currency_consistency,
        "calculation_checks": {
            "overall_status": "partial",
            "gross_proceeds_confirmed": gross_proceeds is not None,
            "commission_confirmed": commission_available,
            "tax_basis_confirmed": False,
            "net_proceeds_confirmed": False,
            "integrity_confirmed": False,
            "reason": "Verified tax evidence is not available in this collector.",
        },
        "components": dict(component_statuses),
        "quality": {
            "instrument_resolved": instrument_resolved,
            "price_available": price_available,
            "position_availability_confirmed": position_available,
            "open_orders_checked": open_orders_checked,
            "order_price_available": order_price_status == "ok",
            "tax_basis_confirmed": False,
            "commission_double_count_protected": (
                commission_summary.get("double_count_protection") is True
            ),
            "currency_consistent": currency_consistency.get("status") == "ok",
            "calculation_integrity_confirmed": False,
            "component_errors": len(component_errors or []),
            "complete": source_complete,
            "read_only": True,
            "no_order_created": True,
        },
        "complete": source_complete,
        "component_errors": component_errors or [],
        "trading_methods": False,
        "warnings": warnings,
    }
    return base.json_safe_value(payload)
