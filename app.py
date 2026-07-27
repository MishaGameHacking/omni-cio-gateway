from __future__ import annotations

from typing import Any

from fastapi import Depends, Query

import app_v360 as legacy
from app_v360 import *  # noqa: F401,F403
import purchase_capacity as purchase_capacity_engine


APP_VERSION = "3.7.0"
ENTRYPOINT = "app:app"

# Existing route handlers in the archived v3.6.0 wrapper resolve these module
# globals at call time. Updating them upgrades every established endpoint while
# preserving the stable Render entrypoint and Regression Shield behavior.
legacy.APP_VERSION = APP_VERSION
legacy.ENTRYPOINT = ENTRYPOINT

app = legacy.app
base = legacy.base
app.version = APP_VERSION
app.description = (
    "Private read-only gateway between a Custom GPT and T-Invest API. "
    "It exposes connection, portfolio and operations data, smart instrument "
    "search, single-instrument market diagnostics, whole-portfolio market "
    "valuation, currency-local analytics, cash/liquidity diagnostics, and a "
    "read-only purchase-capacity preview. It cannot create, submit, replace, "
    "or cancel orders."
)

if "purchase_capacity_preview" not in base.CAPABILITIES:
    base.CAPABILITIES.append("purchase_capacity_preview")


@app.get(
    "/portfolio/purchase-capacity",
    operation_id="getPurchaseCapacityPreview",
    summary=(
        "Calculate read-only own-funds limits and a preliminary purchase cost "
        "for one exact instrument"
    ),
    dependencies=[Depends(base.require_gateway_key)],
)
def purchase_capacity_preview_v370(
    instrument_uid: str = Query(
        ...,
        min_length=1,
        max_length=120,
        description=(
            "Exact T-Invest instrument UID. Resolve it with findInstrument or "
            "getEnrichedPortfolioSnapshot before calling this method."
        ),
    ),
    price_basis: str = Query(
        "best_ask",
        pattern="^(best_ask|last_price|manual)$",
        description=(
            "Price used for the preview: current best ask, latest recorded "
            "trade price, or an explicit manual price."
        ),
    ),
    quantity_lots: int = Query(
        1,
        ge=1,
        le=1_000_000,
        description="Positive number of lots to include in the preliminary cost.",
    ),
    manual_price: str | None = Query(
        None,
        pattern=r"^\d{1,18}(?:\.\d{1,9})?$",
        description=(
            "Positive decimal price with up to 9 fractional digits. Required "
            "only when price_basis=manual and rejected for other price bases."
        ),
    ),
) -> dict[str, Any]:
    return purchase_capacity_engine.get_purchase_capacity_preview(
        base=base,
        app_version=APP_VERSION,
        market_snapshot_loader=lambda uid, depth: legacy.market_snapshot_v350(
            uid,
            depth,
        ),
        instrument_uid=instrument_uid,
        price_basis=price_basis,
        quantity_lots=quantity_lots,
        manual_price=manual_price,
    )


# GPT Actions requires every object response schema to declare explicit
# properties. Keep the contract compact and descriptive while leaving raw
# source meanings intact.
_OA_PC_FRESHNESS = base._oa_obj(
    {
        "status": base._OA_STRING,
        "source_time": base._OA_STRING,
        "age_seconds": base._OA_STRING,
        "fresh_threshold_seconds": base._OA_STRING,
    }
)
_OA_PC_MARKET_PRICE = base._oa_obj(
    {
        "status": base._OA_STRING,
        "basis": base._OA_STRING,
        "source": base._OA_STRING,
        "price": base._OA_STRING,
        "currency": base._OA_STRING,
        "lot_size": base._OA_INT,
        "source_time": base._OA_STRING,
        "age_seconds": base._OA_STRING,
        "freshness": _OA_PC_FRESHNESS,
    }
)
_OA_PC_LIMIT_VALUES = base._oa_obj(
    {
        "buy_money_amount": base._OA_STRING,
        "buy_max_lots": base._OA_INT,
        "buy_max_market_lots": base._OA_INT,
    }
)
_OA_PC_OWN_FUNDS = base._oa_obj(
    {
        "status": base._OA_STRING,
        "source": base._OA_STRING,
        "currency": base._OA_STRING,
        "buy_money_amount": base._OA_STRING,
        "buy_max_lots": base._OA_INT,
        "buy_max_market_lots": base._OA_INT,
    }
)
_OA_PC_MARGIN = base._oa_obj(
    {
        "included": base._OA_BOOL,
        "values_returned_but_not_used": base._OA_BOOL,
        "reason": base._OA_STRING,
        "source_values": _OA_PC_LIMIT_VALUES,
    }
)
_OA_PC_BOND_EXTRA = base._oa_obj(
    {
        "aci_value": base._OA_MONEY,
        "nominal_conversion_rate": base._OA_STRING,
    }
)
_OA_PC_FUTURE_EXTRA = base._oa_obj(
    {
        "initial_margin": base._OA_MONEY,
    }
)
_OA_PC_ORDER_PREVIEW = base._oa_obj(
    {
        "status": base._OA_STRING,
        "source": base._OA_STRING,
        "lots_requested": base._OA_INT,
        "initial_order_amount": base._OA_MONEY,
        "total_order_amount": base._OA_MONEY,
        "executed_commission": base._OA_MONEY,
        "executed_commission_rub": base._OA_MONEY,
        "service_commission": base._OA_MONEY,
        "deal_commission": base._OA_MONEY,
        "extra_bond": _OA_PC_BOND_EXTRA,
        "extra_future": _OA_PC_FUTURE_EXTRA,
    }
)
_OA_PC_COMPONENT_ERROR_DETAIL = base._oa_obj(
    {
        "code": base._OA_STRING,
        "grpc_code": base._OA_STRING,
        "exception_type": base._OA_STRING,
        "message": base._OA_STRING,
        "tracking_id": base._OA_STRING,
        "field": base._OA_STRING,
    }
)
_OA_PC_COMPONENT_ERROR = base._oa_obj(
    {
        "component": base._OA_STRING,
        "error": _OA_PC_COMPONENT_ERROR_DETAIL,
    }
)
_OA_PC_COMPONENTS = base._oa_obj(
    {
        "market_snapshot": base._OA_STRING,
        "instrument_reference": base._OA_STRING,
        "max_lots": base._OA_STRING,
        "order_price": base._OA_STRING,
    }
)
_OA_PC_AFFORDABILITY_CHECKS = base._oa_obj(
    {
        "by_max_lots": base._OA_STRING,
        "by_total_amount": base._OA_STRING,
        "reasons": base._oa_array(base._OA_STRING),
    }
)
_OA_PC_MARKET_CONTEXT = base._oa_obj(
    {
        "requested": base._OA_BOOL,
        "dealer_session": base._OA_BOOL,
        "market_data_sources": base._oa_obj(
            {
                "last_price_type": base._OA_STRING,
                "order_book_type": base._OA_STRING,
            }
        ),
        "trading_flag_consistency": base._oa_obj(
            {
                "status": base._OA_STRING,
                "issues": base._oa_array(base._OA_STRING),
                "raw_fields_preserved": base._OA_BOOL,
            }
        ),
    }
)
_OA_PC_INSTRUMENT_RESOLUTION = base._oa_obj(
    {
        "status": base._OA_STRING,
        "identity_check": base._OA_IDENTITY_CHECK,
        "resolution": base._oa_obj(
            {
                "source": base._OA_STRING,
                "cache_hit": base._OA_BOOL,
                "cache_key": base._OA_STRING,
                "identifier_type": base._OA_STRING,
                "identifier": base._OA_STRING,
                "api_calls": base._OA_INT,
            }
        ),
    }
)
_OA_PC_QUALITY = base._oa_obj(
    {
        "instrument_resolved": base._OA_BOOL,
        "price_available": base._OA_BOOL,
        "max_lots_available": base._OA_BOOL,
        "order_price_available": base._OA_BOOL,
        "affordability_confirmed": base._OA_BOOL,
        "margin_ignored": base._OA_BOOL,
        "component_errors": base._OA_INT,
        "complete": base._OA_BOOL,
        "read_only": base._OA_BOOL,
        "no_order_created": base._OA_BOOL,
    }
)

base._ACTION_200_SCHEMAS["/portfolio/purchase-capacity"] = base._oa_obj(
    {
        "status": base._OA_STRING,
        "version": base._OA_STRING,
        "retrieved_at": base._OA_STRING,
        "account": base._OA_ACCOUNT,
        "request": base._oa_obj(
            {
                "instrument_uid": base._OA_STRING,
                "price_basis": base._OA_STRING,
                "quantity_lots": base._OA_INT,
                "direction": base._OA_STRING,
            }
        ),
        "instrument": base._OA_INSTRUMENT,
        "instrument_resolution": _OA_PC_INSTRUMENT_RESOLUTION,
        "market_price": _OA_PC_MARKET_PRICE,
        "market_context": _OA_PC_MARKET_CONTEXT,
        "own_funds": _OA_PC_OWN_FUNDS,
        "margin": _OA_PC_MARGIN,
        "order_preview": _OA_PC_ORDER_PREVIEW,
        "affordable": base._OA_STRING,
        "affordability_confirmed": base._OA_BOOL,
        "affordability_checks": _OA_PC_AFFORDABILITY_CHECKS,
        "remaining_cash_estimate": base._OA_STRING,
        "remaining_cash_currency": base._OA_STRING,
        "price_freshness": _OA_PC_FRESHNESS,
        "components": _OA_PC_COMPONENTS,
        "quality": _OA_PC_QUALITY,
        "complete": base._OA_BOOL,
        "component_errors": base._oa_array(_OA_PC_COMPONENT_ERROR),
        "trading_methods": base._OA_BOOL,
        "warnings": base._oa_array(base._OA_STRING),
    },
    required=[
        "status",
        "version",
        "retrieved_at",
        "account",
        "request",
        "market_price",
        "own_funds",
        "order_preview",
        "complete",
    ],
)

app.openapi_schema = None
