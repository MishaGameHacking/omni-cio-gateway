from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from typing import Any, Callable, NotRequired, TypedDict, Unpack

import grpc
from fastapi import HTTPException


PRICE_FRESH_SECONDS = Decimal("120")
NANO_FACTOR = Decimal("1000000000")


class PurchaseCapacityPreviewFieldsV1(TypedDict):
    app_version: str
    account: dict[str, Any]
    instrument_uid: str
    instrument_resolution: dict[str, Any] | None
    price_basis: str
    quantity_lots: int
    price_info: dict[str, Any]
    max_lots_data: dict[str, Any] | None
    order_price_data: dict[str, Any] | None
    component_statuses: dict[str, str]
    component_errors: NotRequired[list[dict[str, Any]] | None]
    market_snapshot: NotRequired[dict[str, Any] | None]
    retrieved_at: NotRequired[str | None]


def _component_error(base: Any, exc: Exception) -> dict[str, Any]:
    if isinstance(exc, HTTPException):
        if isinstance(exc.detail, dict):
            return base.json_safe_value(exc.detail)
        return {
            "code": "UPSTREAM_HTTP_ERROR",
            "exception_type": type(exc).__name__,
            "message": base.safe_error_message(exc),
        }
    if isinstance(exc, grpc.RpcError):
        _, payload = base.grpc_error_payload(exc)
        return payload
    return {
        "code": (
            "GATEWAY_SDK_COMPATIBILITY_ERROR"
            if isinstance(exc, (AttributeError, TypeError, ImportError))
            else "GATEWAY_CLIENT_ERROR"
        ),
        "exception_type": type(exc).__name__,
        "message": base.safe_error_message(exc),
    }


def _parse_positive_decimal(value: Any, field_name: str) -> Decimal:
    try:
        result = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INVALID_DECIMAL_VALUE",
                "field": field_name,
                "message": f"{field_name} must be a positive decimal value.",
            },
        ) from exc

    if not result.is_finite() or result <= 0:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INVALID_DECIMAL_VALUE",
                "field": field_name,
                "message": f"{field_name} must be greater than zero.",
            },
        )

    exponent = result.as_tuple().exponent
    if not isinstance(exponent, int):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INVALID_DECIMAL_VALUE",
                "field": field_name,
                "message": f"{field_name} must be a finite decimal value.",
            },
        )
    if exponent < -9:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "TOO_MANY_DECIMAL_PLACES",
                "field": field_name,
                "message": f"{field_name} supports at most 9 decimal places.",
            },
        )
    return result


def _sdk_order_types() -> tuple[Any, Any]:
    """Load SDK order types lazily so startup remains diagnosable."""
    from t_tech.invest import OrderDirection, Quotation

    return OrderDirection, Quotation


def _quotation_from_decimal(value: Decimal) -> Any:
    order_direction, quotation_type = _sdk_order_types()
    del order_direction

    normalized = value.quantize(Decimal("0.000000001"), rounding=ROUND_DOWN)
    units = int(normalized)
    nano = int((normalized - Decimal(units)) * NANO_FACTOR)
    return quotation_type(units=units, nano=nano)


def _buy_direction() -> Any:
    order_direction, quotation_type = _sdk_order_types()
    del quotation_type
    return order_direction.ORDER_DIRECTION_BUY


def _status_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _int_or_none(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (ValueError, TypeError, OverflowError):
        return None


def _decimal_or_none(base: Any, value: Any) -> Decimal | None:
    return base.decimal_from_any(value)


def _money_view(base: Any, value: Any) -> dict[str, Any] | None:
    result = base.safe_money(value)
    return result if isinstance(result, dict) else None


def _price_freshness(age_seconds: Any, source_time: Any, basis: str) -> dict[str, Any]:
    if basis == "manual":
        return {
            "status": "manual_input",
            "source_time": "not_applicable",
            "age_seconds": "not_applicable",
        }

    try:
        age = Decimal(str(age_seconds))
    except (InvalidOperation, ValueError, TypeError):
        age = None

    if age is None:
        status = "unknown"
        safe_age = "unavailable"
    else:
        status = "fresh" if age <= PRICE_FRESH_SECONDS else "stale"
        safe_age = format(age, "f")

    return {
        "status": status,
        "source_time": source_time or "unavailable",
        "age_seconds": safe_age,
        "fresh_threshold_seconds": format(PRICE_FRESH_SECONDS, "f"),
    }


def select_price(
    *,
    base: Any,
    price_basis: str,
    manual_price: str | None,
    market_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    if price_basis == "manual":
        if manual_price is None or not str(manual_price).strip():
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "MANUAL_PRICE_REQUIRED",
                    "field": "manual_price",
                    "message": "manual_price is required when price_basis=manual.",
                },
            )
        manual_value = _parse_positive_decimal(manual_price, "manual_price")
        return {
            "status": "ok",
            "basis": "manual",
            "source": "manual_input",
            "price": base.decimal_string(manual_value),
            "source_time": "not_applicable",
            "age_seconds": "not_applicable",
            "freshness": _price_freshness(None, None, "manual"),
        }

    if manual_price not in (None, ""):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "MANUAL_PRICE_NOT_ALLOWED",
                "field": "manual_price",
                "message": "manual_price is allowed only when price_basis=manual.",
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
        best_ask = _status_dict(source.get("best_ask"))
        raw_price = best_ask.get("price")
        source_time = source.get("time")
        age_seconds = source.get("age_seconds")
        source_name = "T-Invest GetOrderBook best ask"

    price = _decimal_or_none(base, raw_price)
    if price is None or price <= 0:
        return {
            "status": "unavailable",
            "basis": price_basis,
            "source": source_name,
            "price": "unavailable",
            "source_time": source_time or "unavailable",
            "age_seconds": (
                str(age_seconds) if age_seconds is not None else "unavailable"
            ),
            "freshness": _price_freshness(age_seconds, source_time, price_basis),
        }

    return {
        "status": "ok",
        "basis": price_basis,
        "source": source_name,
        "price": base.decimal_string(price),
        "source_time": source_time or "unavailable",
        "age_seconds": (str(age_seconds) if age_seconds is not None else "unavailable"),
        "freshness": _price_freshness(age_seconds, source_time, price_basis),
    }


def _instrument_from_resolution(resolution: Any) -> dict[str, Any]:
    resolution_dict = _status_dict(resolution)
    instrument = resolution_dict.get("instrument")
    return instrument if isinstance(instrument, dict) else {}


def _own_funds_view(base: Any, max_lots_data: Any, status: str) -> dict[str, Any]:
    data = _status_dict(max_lots_data)
    limits = _status_dict(data.get("buy_limits"))
    result: dict[str, Any] = {
        "status": status,
        "source": "T-Invest GetMaxLots buy_limits",
    }

    currency = str(data.get("currency", "") or "").upper()
    if currency:
        result["currency"] = currency

    buy_money = _decimal_or_none(base, limits.get("buy_money_amount"))
    if buy_money is not None:
        result["buy_money_amount"] = base.decimal_string(buy_money)

    buy_max_lots = _int_or_none(limits.get("buy_max_lots"))
    if buy_max_lots is not None:
        result["buy_max_lots"] = buy_max_lots

    buy_max_market_lots = _int_or_none(limits.get("buy_max_market_lots"))
    if buy_max_market_lots is not None:
        result["buy_max_market_lots"] = buy_max_market_lots

    return result


def _margin_view(base: Any, max_lots_data: Any) -> dict[str, Any]:
    data = _status_dict(max_lots_data)
    limits = _status_dict(data.get("buy_margin_limits"))
    returned = bool(limits)
    result: dict[str, Any] = {
        "included": False,
        "values_returned_but_not_used": returned,
        "reason": (
            "Margin limits are preserved for diagnostics but are excluded from "
            "the affordability decision."
        ),
    }
    if not returned:
        return result

    source_values: dict[str, Any] = {}
    buy_money = _decimal_or_none(base, limits.get("buy_money_amount"))
    if buy_money is not None:
        source_values["buy_money_amount"] = base.decimal_string(buy_money)
    buy_max_lots = _int_or_none(limits.get("buy_max_lots"))
    if buy_max_lots is not None:
        source_values["buy_max_lots"] = buy_max_lots
    buy_max_market_lots = _int_or_none(limits.get("buy_max_market_lots"))
    if buy_max_market_lots is not None:
        source_values["buy_max_market_lots"] = buy_max_market_lots
    result["source_values"] = source_values
    return result


def _order_preview_view(
    base: Any,
    order_price_data: Any,
    status: str,
    quantity_lots: int,
) -> dict[str, Any]:
    data = _status_dict(order_price_data)
    result: dict[str, Any] = {
        "status": status,
        "source": "T-Invest GetOrderPrice",
        "lots_requested": _int_or_none(data.get("lots_requested")) or quantity_lots,
    }

    for field_name in (
        "initial_order_amount",
        "total_order_amount",
        "executed_commission",
        "executed_commission_rub",
        "service_commission",
        "deal_commission",
    ):
        money = _money_view(base, data.get(field_name))
        if money is not None:
            result[field_name] = money

    extra_bond = _status_dict(data.get("extra_bond"))
    if extra_bond:
        bond_result: dict[str, Any] = {}
        aci_value = _money_view(base, extra_bond.get("aci_value"))
        if aci_value is not None:
            bond_result["aci_value"] = aci_value
        conversion_rate = base.safe_quotation(extra_bond.get("nominal_conversion_rate"))
        if conversion_rate is not None:
            bond_result["nominal_conversion_rate"] = conversion_rate
        if bond_result:
            result["extra_bond"] = bond_result

    extra_future = _status_dict(data.get("extra_future"))
    if extra_future:
        initial_margin = _money_view(base, extra_future.get("initial_margin"))
        if initial_margin is not None:
            result["extra_future"] = {"initial_margin": initial_margin}

    return result


def _max_lots_check(
    *,
    quantity_lots: int,
    buy_max_lots: int | None,
) -> tuple[bool | None, list[str]]:
    if buy_max_lots is None:
        return None, ["buy_max_lots_unavailable"]
    allowed = quantity_lots <= buy_max_lots
    return (
        allowed,
        [] if allowed else ["requested_lots_exceed_own_funds_limit"],
    )


def _amount_check(
    *,
    buy_money: Decimal | None,
    total_amount: Decimal | None,
    currencies_compatible: bool,
) -> tuple[bool | None, list[str]]:
    if buy_money is None or total_amount is None:
        return None, ["amount_comparison_unavailable"]
    if not currencies_compatible:
        return None, ["currency_mismatch_between_limit_and_preview"]
    allowed = total_amount <= buy_money
    return (
        allowed,
        [] if allowed else ["preview_total_exceeds_buy_money_amount"],
    )


def _affordability_label(
    by_max_lots: bool | None,
    by_total_amount: bool | None,
) -> tuple[str, bool]:
    confirmed = by_max_lots is not None and by_total_amount is not None
    checks = [check for check in (by_max_lots, by_total_amount) if check is not None]
    if any(check is False for check in checks):
        return "no", confirmed
    if confirmed and all(check is True for check in checks):
        return "yes", True
    return "unavailable", confirmed


def _affordability(
    *,
    base: Any,
    quantity_lots: int,
    max_lots_data: Any,
    order_price_data: Any,
) -> dict[str, Any]:
    max_data = _status_dict(max_lots_data)
    buy_limits = _status_dict(max_data.get("buy_limits"))
    order_data = _status_dict(order_price_data)

    buy_max_lots = _int_or_none(buy_limits.get("buy_max_lots"))
    buy_money = _decimal_or_none(base, buy_limits.get("buy_money_amount"))
    max_currency = str(max_data.get("currency", "") or "").upper()

    total_money = _money_view(base, order_data.get("total_order_amount"))
    total_amount = (
        _decimal_or_none(base, total_money.get("amount"))
        if isinstance(total_money, dict)
        else None
    )
    total_currency = (
        str(total_money.get("currency", "") or "").upper()
        if isinstance(total_money, dict)
        else ""
    )
    currencies_compatible = (
        not max_currency
        or not total_currency
        or max_currency == total_currency
    )
    by_max_lots, lot_reasons = _max_lots_check(
        quantity_lots=quantity_lots,
        buy_max_lots=buy_max_lots,
    )
    by_total_amount, amount_reasons = _amount_check(
        buy_money=buy_money,
        total_amount=total_amount,
        currencies_compatible=currencies_compatible,
    )
    affordable, confirmed = _affordability_label(
        by_max_lots,
        by_total_amount,
    )
    remaining = (
        base.decimal_string(buy_money - total_amount)
        if buy_money is not None
        and total_amount is not None
        and currencies_compatible
        else "unavailable"
    )
    return {
        "affordable": affordable,
        "confirmed": confirmed,
        "by_max_lots": (
            "unavailable" if by_max_lots is None else str(by_max_lots).lower()
        ),
        "by_total_amount": (
            "unavailable" if by_total_amount is None else str(by_total_amount).lower()
        ),
        "remaining_cash_estimate": remaining,
        "currency": max_currency or total_currency or "unavailable",
        "reasons": [*lot_reasons, *amount_reasons],
    }


def _purchase_preview_status(
    *,
    instrument_resolved: bool,
    price_available: bool,
    max_lots_available: bool,
    order_price_available: bool,
    component_errors: list[dict[str, Any]] | None,
) -> tuple[str, bool]:
    complete = all(
        (
            instrument_resolved,
            price_available,
            max_lots_available,
            order_price_available,
            not component_errors,
        )
    )
    if complete:
        return "ok", True
    any_available = any(
        (
            instrument_resolved,
            price_available,
            max_lots_available,
            order_price_available,
        )
    )
    return ("partial" if any_available else "error"), False


def _purchase_preview_warnings(
    *,
    freshness: dict[str, Any],
    affordability_confirmed: bool,
) -> list[str]:
    warnings = [
        (
            "This endpoint is a read-only preview. It calculates limits and a "
            "preliminary amount but does not create, replace, cancel, or submit an order."
        ),
        (
            "GetOrderPrice is a preliminary calculation. Commissions, accrued "
            "interest, guarantees, market quotes, and broker restrictions may change."
        ),
        (
            "Only buy_limits based on own funds are used for affordability. "
            "buy_margin_limits are returned only for diagnostics and are ignored."
        ),
        (
            "A read-only T-Invest token can obtain information but cannot place "
            "trading instructions."
        ),
    ]
    if freshness.get("status") == "stale":
        warnings.append(
            "The selected market price is stale relative to the gateway freshness threshold."
        )
    if not affordability_confirmed:
        warnings.append(
            "Affordability is not fully confirmed because at least one required "
            "own-funds or preliminary-cost comparison is unavailable."
        )
    return warnings


def build_purchase_capacity_preview(
    *,
    base: Any,
    **fields: Unpack[PurchaseCapacityPreviewFieldsV1],
) -> dict[str, Any]:
    app_version = fields["app_version"]
    account = fields["account"]
    instrument_uid = fields["instrument_uid"]
    instrument_resolution = fields["instrument_resolution"]
    price_basis = fields["price_basis"]
    quantity_lots = fields["quantity_lots"]
    price_info = fields["price_info"]
    max_lots_data = fields["max_lots_data"]
    order_price_data = fields["order_price_data"]
    component_statuses = fields["component_statuses"]
    component_errors = fields.get("component_errors")
    market_snapshot = fields.get("market_snapshot")
    retrieved_at = fields.get("retrieved_at")
    resolution = _status_dict(instrument_resolution)
    instrument = _instrument_from_resolution(resolution)
    max_status = component_statuses.get("max_lots", "not_requested")
    order_status = component_statuses.get("order_price", "not_requested")

    own_funds = _own_funds_view(base, max_lots_data, max_status)
    margin = _margin_view(base, max_lots_data)
    order_preview = _order_preview_view(
        base,
        order_price_data,
        order_status,
        quantity_lots,
    )
    affordability = _affordability(
        base=base,
        quantity_lots=quantity_lots,
        max_lots_data=max_lots_data,
        order_price_data=order_price_data,
    )

    lot_size = _int_or_none(instrument.get("lot"))
    market_price = dict(price_info)
    market_price["currency"] = (
        str(
            instrument.get("currency")
            or own_funds.get("currency")
            or affordability.get("currency")
            or ""
        ).upper()
        or "unavailable"
    )
    market_price["lot_size"] = lot_size if lot_size is not None else 0

    instrument_resolved = resolution.get("status") == "resolved"
    price_available = price_info.get("status") == "ok"
    max_lots_available = max_status == "ok"
    order_price_available = order_status == "ok"
    status, complete = _purchase_preview_status(
        instrument_resolved=instrument_resolved,
        price_available=price_available,
        max_lots_available=max_lots_available,
        order_price_available=order_price_available,
        component_errors=component_errors,
    )

    snapshot = _status_dict(market_snapshot)
    market_context = {
        "requested": price_basis != "manual",
        "dealer_session": bool(snapshot.get("dealer_session", False)),
        "market_data_sources": _status_dict(snapshot.get("market_data_sources")),
        "trading_flag_consistency": _status_dict(
            snapshot.get("trading_flag_consistency")
        ),
    }

    freshness = _status_dict(price_info.get("freshness"))
    warnings = _purchase_preview_warnings(
        freshness=freshness,
        affordability_confirmed=bool(affordability["confirmed"]),
    )

    payload = {
        "status": status,
        "version": app_version,
        "retrieved_at": retrieved_at or datetime.now(timezone.utc).isoformat(),
        "account": account,
        "request": {
            "instrument_uid": instrument_uid,
            "price_basis": price_basis,
            "quantity_lots": quantity_lots,
            "direction": "ORDER_DIRECTION_BUY",
        },
        "instrument": instrument,
        "instrument_resolution": {
            "status": resolution.get("status", "unavailable"),
            "identity_check": _status_dict(resolution.get("identity_check")),
            "resolution": _status_dict(resolution.get("resolution")),
        },
        "market_price": market_price,
        "market_context": market_context,
        "own_funds": own_funds,
        "margin": margin,
        "order_preview": order_preview,
        "affordable": affordability["affordable"],
        "affordability_confirmed": affordability["confirmed"],
        "affordability_checks": {
            "by_max_lots": affordability["by_max_lots"],
            "by_total_amount": affordability["by_total_amount"],
            "reasons": affordability["reasons"],
        },
        "remaining_cash_estimate": affordability["remaining_cash_estimate"],
        "remaining_cash_currency": affordability["currency"],
        "price_freshness": freshness,
        "components": component_statuses,
        "quality": {
            "instrument_resolved": instrument_resolved,
            "price_available": price_available,
            "max_lots_available": max_lots_available,
            "order_price_available": order_price_available,
            "affordability_confirmed": affordability["confirmed"],
            "margin_ignored": True,
            "component_errors": len(component_errors or []),
            "complete": complete,
            "read_only": True,
            "no_order_created": True,
        },
        "complete": complete,
        "component_errors": component_errors or [],
        "trading_methods": False,
        "warnings": warnings,
    }
    return base.json_safe_value(payload)


def _load_read_only_market_snapshot(
    *,
    base: Any,
    market_snapshot_loader: Callable[[str, int], dict[str, Any]],
    instrument_uid: str,
    price_basis: str,
    component_statuses: dict[str, str],
    component_errors: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if price_basis == "manual":
        return None
    try:
        snapshot = market_snapshot_loader(instrument_uid, 1)
    except Exception as exc:
        component_errors.append(
            {"component": "market_snapshot", "error": _component_error(base, exc)}
        )
        return None
    component_statuses["market_snapshot"] = "ok"
    return snapshot


def _resolve_read_only_instrument(
    *,
    base: Any,
    client: Any,
    instrument_uid: str,
    component_statuses: dict[str, str],
    component_errors: list[dict[str, Any]],
) -> dict[str, Any] | None:
    try:
        resolution = base.resolve_instrument_reference(
            client,
            {"instrument_uid": instrument_uid},
        )
    except Exception as exc:
        component_errors.append(
            {
                "component": "instrument_reference",
                "error": _component_error(base, exc),
            }
        )
        return None

    resolved = resolution.get("status") == "resolved"
    component_statuses["instrument_reference"] = "ok" if resolved else "unresolved"
    if not resolved:
        component_errors.append(
            {
                "component": "instrument_reference",
                "error": {
                    "code": "INSTRUMENT_REFERENCE_UNRESOLVED",
                    "message": "The exact instrument UID could not be resolved.",
                },
            }
        )
    return resolution


def _purchase_order_inputs(
    *,
    base: Any,
    client: Any,
    account_id: str,
    instrument_uid: str,
    quantity_lots: int,
    price_value: Decimal | None,
    component_statuses: dict[str, str],
    component_errors: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if price_value is None or price_value <= 0:
        component_errors.append(
            {
                "component": "selected_price",
                "error": {
                    "code": "SELECTED_PRICE_UNAVAILABLE",
                    "message": (
                        "The selected price basis did not provide a positive price; "
                        "pre-trade calculations were not requested."
                    ),
                },
            }
        )
        return None, None

    orders_service = getattr(client, "orders", None)
    if orders_service is None:
        raise AttributeError("The SDK client has no orders service.")
    quotation = _quotation_from_decimal(price_value)
    buy_direction = _buy_direction()

    max_lots_data: dict[str, Any] | None = None
    try:
        response = orders_service.get_max_lots(
            account_id=account_id,
            instrument_id=instrument_uid,
            price=quotation,
        )
        max_lots_data = base.proto_to_dict(response)
        component_statuses["max_lots"] = "ok"
    except Exception as exc:
        component_statuses["max_lots"] = "error"
        component_errors.append(
            {"component": "max_lots", "error": _component_error(base, exc)}
        )

    order_price_data: dict[str, Any] | None = None
    try:
        response = orders_service.get_order_price(
            account_id=account_id,
            instrument_id=instrument_uid,
            price=quotation,
            direction=buy_direction,
            quantity=quantity_lots,
        )
        order_price_data = base.proto_to_dict(response)
        component_statuses["order_price"] = "ok"
    except Exception as exc:
        component_statuses["order_price"] = "error"
        component_errors.append(
            {"component": "order_price", "error": _component_error(base, exc)}
        )
    return max_lots_data, order_price_data


def get_purchase_capacity_preview(
    *,
    base: Any,
    app_version: str,
    market_snapshot_loader: Callable[[str, int], dict[str, Any]],
    instrument_uid: str,
    price_basis: str,
    quantity_lots: int,
    manual_price: str | None,
) -> dict[str, Any]:
    base.ensure_configured()
    retrieved_at = datetime.now(timezone.utc).isoformat()
    component_errors: list[dict[str, Any]] = []
    component_statuses = {
        "market_snapshot": "not_requested" if price_basis == "manual" else "error",
        "instrument_reference": "error",
        "max_lots": "not_requested",
        "order_price": "not_requested",
    }
    market_snapshot = _load_read_only_market_snapshot(
        base=base,
        market_snapshot_loader=market_snapshot_loader,
        instrument_uid=instrument_uid,
        price_basis=price_basis,
        component_statuses=component_statuses,
        component_errors=component_errors,
    )
    price_info = select_price(
        base=base,
        price_basis=price_basis,
        manual_price=manual_price,
        market_snapshot=market_snapshot,
    )
    price_value = _decimal_or_none(base, price_info.get("price"))

    try:
        with base.Client(base.TINVEST_TOKEN) as client:
            account_id, safe_account = base.get_open_account(client)
            instrument_resolution = _resolve_read_only_instrument(
                base=base,
                client=client,
                instrument_uid=instrument_uid,
                component_statuses=component_statuses,
                component_errors=component_errors,
            )
            max_lots_data, order_price_data = _purchase_order_inputs(
                base=base,
                client=client,
                account_id=account_id,
                instrument_uid=instrument_uid,
                quantity_lots=quantity_lots,
                price_value=price_value,
                component_statuses=component_statuses,
                component_errors=component_errors,
            )
            return build_purchase_capacity_preview(
                base=base,
                app_version=app_version,
                account=safe_account,
                instrument_uid=instrument_uid,
                instrument_resolution=instrument_resolution,
                price_basis=price_basis,
                quantity_lots=quantity_lots,
                price_info=price_info,
                max_lots_data=max_lots_data,
                order_price_data=order_price_data,
                component_statuses=component_statuses,
                component_errors=component_errors,
                market_snapshot=market_snapshot,
                retrieved_at=retrieved_at,
            )
    except HTTPException:
        raise
    except grpc.RpcError as exc:
        http_status, payload = base.grpc_error_payload(exc)
        raise HTTPException(status_code=http_status, detail=payload) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=_component_error(base, exc),
        ) from exc

