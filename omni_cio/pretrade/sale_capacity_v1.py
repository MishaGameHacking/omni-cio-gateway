from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable

import grpc
from fastapi import HTTPException

from omni_cio.pretrade.purchase_capacity_v1 import (
    PRICE_FRESH_SECONDS as PRICE_FRESH_SECONDS,
    _component_error,
    _decimal_or_none,
    _load_read_only_market_snapshot,
    _quotation_from_decimal,
    _resolve_read_only_instrument,
)
from omni_cio.pretrade.sale_capacity_normalization_v1 import (
    build_sale_capacity_preview,
    select_sale_price,
)


_ALLOWED_PRICE_BASES = frozenset({"best_bid", "last_price"})


class _SellDirectionValue(int):
    """Protobuf-compatible ORDER_DIRECTION_SELL value with readable diagnostics."""

    def __new__(cls) -> _SellDirectionValue:
        return int.__new__(cls, 2)

    @property
    def name(self) -> str:
        return "ORDER_DIRECTION_SELL"

    @property
    def value(self) -> int:
        return 2

    def __str__(self) -> str:
        return self.name


def _parse_positive_int(value: Any, field_name: str) -> int:
    if value is None or isinstance(value, bool):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INVALID_INTEGER_VALUE",
                "field": field_name,
                "message": f"{field_name} must be a positive integer.",
            },
        )
    try:
        result = int(str(value).strip())
    except (ValueError, TypeError, OverflowError) as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INVALID_INTEGER_VALUE",
                "field": field_name,
                "message": f"{field_name} must be a positive integer.",
            },
        ) from exc
    if result <= 0:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INVALID_INTEGER_VALUE",
                "field": field_name,
                "message": f"{field_name} must be greater than zero.",
            },
        )
    return result


def _sell_direction() -> _SellDirectionValue:
    return _SellDirectionValue()


def _load_sale_position_evidence(
    *,
    base: Any,
    client: Any,
    account_id: str,
    component_statuses: dict[str, str],
    component_errors: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    positions_data: dict[str, Any] | None = None
    try:
        response = client.operations.get_positions(account_id=account_id)
        positions_data = base.proto_to_dict(response)
        component_statuses["positions"] = "ok"
    except Exception as exc:
        component_statuses["positions"] = "error"
        component_errors.append(
            {"component": "positions", "error": _component_error(base, exc)}
        )

    orders_data: dict[str, Any] | None = None
    try:
        response = client.orders.get_orders(account_id=account_id)
        orders_data = base.proto_to_dict(response)
        component_statuses["open_orders"] = "ok"
    except Exception as exc:
        component_statuses["open_orders"] = "error"
        component_errors.append(
            {"component": "open_orders", "error": _component_error(base, exc)}
        )
    return positions_data, orders_data


def _load_sale_price_evidence(
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
                        "The selected sale price basis did not provide a "
                        "positive price; sale calculations were not requested."
                    ),
                },
            }
        )
        return None, None

    quotation = _quotation_from_decimal(price_value)
    sell_direction = _sell_direction()
    max_lots_data: dict[str, Any] | None = None
    try:
        response = client.orders.get_max_lots(
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
        response = client.orders.get_order_price(
            account_id=account_id,
            instrument_id=instrument_uid,
            price=quotation,
            direction=sell_direction,
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


def get_sale_capacity_preview(
    *,
    base: Any,
    app_version: str,
    market_snapshot_loader: Callable[[str, int], dict[str, Any]],
    instrument_uid: str,
    price_basis: str,
    quantity_lots: int,
) -> dict[str, Any]:
    """Collect read-only T-Invest evidence for a fail-closed sale preview."""

    base.ensure_configured()
    quantity = _parse_positive_int(quantity_lots, "quantity_lots")
    if price_basis not in _ALLOWED_PRICE_BASES:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INVALID_PRICE_BASIS",
                "field": "price_basis",
                "message": "price_basis must be best_bid or last_price.",
            },
        )

    retrieved_at = datetime.now(timezone.utc).isoformat()
    component_errors: list[dict[str, Any]] = []
    component_statuses = {
        "market_snapshot": "error",
        "instrument_reference": "error",
        "positions": "not_requested",
        "max_lots": "not_requested",
        "open_orders": "not_requested",
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
    price_info = select_sale_price(
        base=base,
        price_basis=price_basis,
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
            positions_data, orders_data = _load_sale_position_evidence(
                base=base,
                client=client,
                account_id=account_id,
                component_statuses=component_statuses,
                component_errors=component_errors,
            )
            max_lots_data, order_price_data = _load_sale_price_evidence(
                base=base,
                client=client,
                account_id=account_id,
                instrument_uid=instrument_uid,
                quantity_lots=quantity,
                price_value=price_value,
                component_statuses=component_statuses,
                component_errors=component_errors,
            )
            return build_sale_capacity_preview(
                base=base,
                app_version=app_version,
                account=safe_account,
                instrument_uid=instrument_uid,
                instrument_resolution=instrument_resolution,
                price_basis=price_basis,
                quantity_lots=quantity,
                price_info=price_info,
                positions_data=positions_data,
                max_lots_data=max_lots_data,
                orders_data=orders_data,
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

