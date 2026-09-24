import os
from typing import Any

from fastapi import Depends, Query
from fastapi.routing import APIRoute

from omni_cio.portfolio import cash_liquidity_v1 as cash_liquidity_engine
import main as base
from omni_cio.analytics import portfolio_structure_v1 as portfolio_analytics_engine
from omni_cio.portfolio import market_snapshot_v1 as portfolio_market_engine


APP_VERSION = "3.6.0"
ENTRYPOINT = "app:app"

app = base.app
app.version = APP_VERSION
app.description = (
    "Private read-only gateway between a Custom GPT and T-Invest API. "
    "It exposes connection, portfolio and operations data, smart instrument "
    "search, single-instrument market diagnostics, a read-only market valuation "
    "snapshot for the whole portfolio, currency-local portfolio analytics, "
    "and cash/liquidity diagnostics. "
    "It cannot place, replace, or cancel orders."
)

for capability in (
    "market_source_diagnostics",
    "portfolio_market_snapshot",
    "portfolio_analytics",
    "cash_liquidity_diagnostics",
    "regression_shield",
):
    if capability not in base.CAPABILITIES:
        base.CAPABILITIES.append(capability)


def remove_get_route(path: str) -> None:
    """Remove one inherited GET route before registering its stable wrapper."""
    app.router.routes = [
        route
        for route in app.router.routes
        if not (
            isinstance(route, APIRoute)
            and route.path == path
            and "GET" in (route.methods or set())
        )
    ]


def build_metadata() -> dict[str, str]:
    raw_commit = (
        os.environ.get("RENDER_GIT_COMMIT")
        or os.environ.get("GITHUB_SHA")
        or "unknown"
    )
    commit_sha = raw_commit[:12] if raw_commit != "unknown" else raw_commit
    deployment_platform = (
        "render"
        if os.environ.get("RENDER") or os.environ.get("RENDER_EXTERNAL_URL")
        else "local"
    )
    return {
        "commit_sha": commit_sha,
        "entrypoint": ENTRYPOINT,
        "deployment_platform": deployment_platform,
    }


remove_get_route("/health")


@app.get(
    "/health",
    operation_id="gatewayHealth",
    summary="Check whether the gateway process is running",
)
def health_v350() -> dict[str, Any]:
    payload = base.health()
    payload["build"] = build_metadata()
    payload["regression_shield"] = {
        "profile": APP_VERSION,
        "read_only": True,
        "expected_entrypoint": ENTRYPOINT,
    }
    return base.json_safe_value(payload)


_original_safe_order_book_response = base.safe_order_book_response


def safe_order_book_response_v332(
    response: Any,
    requested_depth: int,
    retrieved_at: Any,
) -> dict[str, Any]:
    """Keep the core order-book response and expose its raw source enum."""
    result = _original_safe_order_book_response(
        response,
        requested_depth,
        retrieved_at,
    )
    data = base.proto_to_dict(response)
    result["order_book_type"] = base.normalized_operation_enum(
        data.get("order_book_type"),
        {},
        "ORDERBOOK_TYPE_UNSPECIFIED",
    )
    return base.json_safe_value(result)


# The core market endpoint resolves this helper at call time, so replacing it
# adds source diagnostics without duplicating the SDK request implementation.
base.safe_order_book_response = safe_order_book_response_v332


def market_dealer_session(
    last_price: dict[str, Any],
    trading_status: dict[str, Any],
    order_book: dict[str, Any],
) -> bool:
    """Infer a dealer session separately from the raw API fields."""
    status_name = str(trading_status.get("trading_status", "") or "").upper()
    last_price_type = str(
        last_price.get("last_price_type", "") or ""
    ).upper()
    order_book_type = str(
        order_book.get("order_book_type", "") or ""
    ).upper()

    return (
        "DEALER" in status_name
        or last_price_type == "LAST_PRICE_DEALER"
        or order_book_type == "ORDERBOOK_TYPE_DEALER"
    )


def trading_flag_consistency_issues(
    last_price: dict[str, Any],
    trading_status: dict[str, Any],
    order_book: dict[str, Any],
) -> list[str]:
    """Report notable divergences without overriding any T-Invest value."""
    issues: list[str] = []
    status_name = str(trading_status.get("trading_status", "") or "").upper()
    last_price_type = str(
        last_price.get("last_price_type", "") or ""
    ).upper()
    order_book_type = str(
        order_book.get("order_book_type", "") or ""
    ).upper()

    limit_available = trading_status.get("limit_order_available_flag")
    market_available = trading_status.get("market_order_available_flag")
    api_available = trading_status.get("api_trade_available_flag")
    bestprice_available = trading_status.get(
        "bestprice_order_available_flag"
    )
    only_best_price = trading_status.get("only_best_price")
    order_flags = (
        limit_available,
        market_available,
        bestprice_available,
    )

    if only_best_price is True and bestprice_available is False:
        issues.append(
            "only_best_price is true while "
            "bestprice_order_available_flag is false."
        )

    if api_available is False and any(flag is True for flag in order_flags):
        issues.append(
            "api_trade_available_flag is false while at least one "
            "order-type availability flag is true."
        )

    if "NORMAL_TRADING" in status_name and api_available is False:
        issues.append(
            "The trading-status name indicates normal trading while "
            "api_trade_available_flag is false."
        )

    if "NOT_AVAILABLE_FOR_TRADING" in status_name and any(
        flag is True for flag in (*order_flags, api_available)
    ):
        issues.append(
            "The trading-status name indicates that trading is unavailable "
            "while at least one availability flag is true."
        )

    if "DEALER" in status_name:
        if last_price_type == "LAST_PRICE_EXCHANGE":
            issues.append(
                "Dealer trading status was returned with an exchange "
                "last-price source."
            )
        if order_book_type == "ORDERBOOK_TYPE_EXCHANGE":
            issues.append(
                "Dealer trading status was returned with an exchange-only "
                "order book."
            )

    return issues


# Replace only GET /market/snapshot. The core function remains responsible for
# the SDK requests and the established error handling.
remove_get_route("/market/snapshot")


@app.get(
    "/market/snapshot",
    operation_id="getMarketSnapshot",
    summary=(
        "Get a current read-only market snapshot with source diagnostics for "
        "one exact instrument UID"
    ),
    dependencies=[Depends(base.require_gateway_key)],
)
def market_snapshot_v350(
    instrument_uid: str = Query(
        ...,
        min_length=1,
        max_length=120,
        description=(
            "Exact T-Invest instrument UID. Resolve it with findInstrument or "
            "getEnrichedPortfolioSnapshot before calling this method."
        ),
    ),
    depth: int = Query(
        10,
        ge=1,
        le=20,
        description="Order-book depth returned for bids and asks.",
    ),
) -> dict[str, Any]:
    result = base.market_snapshot(
        instrument_uid=instrument_uid,
        depth=depth,
    )

    last_price = result.get("last_price")
    trading_status = result.get("trading_status")
    order_book = result.get("order_book")

    safe_last_price = last_price if isinstance(last_price, dict) else {}
    safe_trading_status = (
        trading_status if isinstance(trading_status, dict) else {}
    )
    safe_order_book = order_book if isinstance(order_book, dict) else {}

    dealer_session = market_dealer_session(
        safe_last_price,
        safe_trading_status,
        safe_order_book,
    )
    consistency_issues = trading_flag_consistency_issues(
        safe_last_price,
        safe_trading_status,
        safe_order_book,
    )

    result["dealer_session"] = dealer_session
    result["market_data_sources"] = {
        "last_price_type": safe_last_price.get(
            "last_price_type",
            "LAST_PRICE_UNSPECIFIED",
        ),
        "order_book_type": safe_order_book.get(
            "order_book_type",
            "ORDERBOOK_TYPE_UNSPECIFIED",
        ),
    }
    result["trading_flag_consistency"] = {
        "status": "warning" if consistency_issues else "ok",
        "issues": consistency_issues,
        "raw_fields_preserved": True,
    }

    warnings = list(result.get("warnings") or [])
    warnings.extend(
        [
            (
                "last_price.last_price_type and order_book.order_book_type "
                "are raw T-Invest source labels. An unspecified source is "
                "not inferred or silently replaced by the gateway."
            ),
            (
                "Trading-status and order-availability flags are returned "
                "exactly as received. The gateway reports divergences but "
                "does not override one field with another."
            ),
        ]
    )
    warnings.extend(
        f"Trading-status/flag consistency warning: {issue}"
        for issue in consistency_issues
    )
    result["warnings"] = warnings

    return base.json_safe_value(result)


@app.get(
    "/portfolio/market-snapshot",
    operation_id="getPortfolioMarketSnapshot",
    summary=(
        "Get a read-only market valuation snapshot for all supported portfolio "
        "positions, grouped by reported currency"
    ),
    dependencies=[Depends(base.require_gateway_key)],
)
def portfolio_market_snapshot_v350(
    depth: int = Query(
        1,
        ge=1,
        le=10,
        description=(
            "Order-book depth requested per market instrument. Depth 1 is "
            "sufficient for best bid and best ask."
        ),
    ),
    max_instruments: int = Query(
        50,
        ge=1,
        le=100,
        description=(
            "Maximum number of unique non-cash instruments for which market "
            "data is requested in one call."
        ),
    ),
) -> dict[str, Any]:
    return portfolio_market_engine.get_portfolio_market_snapshot(
        base=base,
        app_version=APP_VERSION,
        market_dealer_session=market_dealer_session,
        trading_flag_consistency_issues=trading_flag_consistency_issues,
        depth=depth,
        max_instruments=max_instruments,
    )


@app.get(
    "/portfolio/analytics",
    operation_id="getPortfolioAnalytics",
    summary=(
        "Calculate read-only portfolio structure, weights, concentration, and "
        "valuation coverage separately for each reported currency"
    ),
    dependencies=[Depends(base.require_gateway_key)],
)
def portfolio_analytics_v350(
    valuation_basis: str = Query(
        "last_price",
        pattern="^(last_price|best_bid|best_ask)$",
        description=(
            "Valuation source used for weights and concentration: last_price, "
            "best_bid, or best_ask."
        ),
    ),
    top_n: int = Query(
        5,
        ge=1,
        le=20,
        description="Number of largest market positions used for concentration.",
    ),
    depth: int = Query(
        1,
        ge=1,
        le=10,
        description=(
            "Order-book depth passed to the source market snapshot. Depth 1 is "
            "sufficient for best bid and best ask."
        ),
    ),
    max_instruments: int = Query(
        50,
        ge=1,
        le=100,
        description=(
            "Maximum number of unique non-cash instruments processed by the "
            "source market snapshot."
        ),
    ),
) -> dict[str, Any]:
    snapshot = portfolio_market_engine.get_portfolio_market_snapshot(
        base=base,
        app_version=APP_VERSION,
        market_dealer_session=market_dealer_session,
        trading_flag_consistency_issues=trading_flag_consistency_issues,
        depth=depth,
        max_instruments=max_instruments,
    )
    return portfolio_analytics_engine.build_portfolio_analytics(
        base=base,
        app_version=APP_VERSION,
        snapshot=snapshot,
        valuation_basis=valuation_basis,
        top_n=top_n,
    )


@app.get(
    "/portfolio/cash-liquidity",
    operation_id="getCashLiquiditySnapshot",
    summary=(
        "Compare read-only cash positions, blocked amounts, and withdrawal "
        "limits separately for each reported currency"
    ),
    dependencies=[Depends(base.require_gateway_key)],
)
def cash_liquidity_snapshot_v360() -> dict[str, Any]:
    return cash_liquidity_engine.get_cash_liquidity_snapshot(
        base=base,
        app_version=APP_VERSION,
    )


# Extend the GPT Actions-compatible schemas while retaining explicit response
# object properties from the core application.
_health_properties = base._ACTION_200_SCHEMAS["/health"]["properties"]
_health_properties["build"] = base._oa_obj(
    {
        "commit_sha": base._OA_STRING,
        "entrypoint": base._OA_STRING,
        "deployment_platform": base._OA_STRING,
    }
)
_health_properties["regression_shield"] = base._oa_obj(
    {
        "profile": base._OA_STRING,
        "read_only": base._OA_BOOL,
        "expected_entrypoint": base._OA_STRING,
    }
)

base._OA_ORDER_BOOK["properties"]["order_book_type"] = base._OA_STRING
base._OA_INSTRUMENT["properties"]["nominal"] = base._OA_MONEY
base._OA_INSTRUMENT["properties"]["accrued_interest"] = base._OA_MONEY
_market_properties = base._ACTION_200_SCHEMAS["/market/snapshot"]["properties"]
_market_properties["dealer_session"] = base._OA_BOOL
_market_properties["market_data_sources"] = base._oa_obj(
    {
        "last_price_type": base._OA_STRING,
        "order_book_type": base._OA_STRING,
    }
)
_market_properties["trading_flag_consistency"] = base._oa_obj(
    {
        "status": base._OA_STRING,
        "issues": base._oa_array(base._OA_STRING),
        "raw_fields_preserved": base._OA_BOOL,
    }
)

_OA_VALUATION_VALUES = base._oa_obj(
    {
        "last_price": base._OA_STRING,
        "best_bid": base._OA_STRING,
        "best_ask": base._OA_STRING,
    }
)
_OA_PORTFOLIO_VALUATION = base._oa_obj(
    {
        "status": base._OA_STRING,
        "currency": base._OA_STRING,
        "quantity_units": base._OA_STRING,
        "instrument_kind": base._OA_STRING,
        "basis": base._OA_STRING,
        "reason": base._OA_STRING,
        "nominal_per_instrument": base._OA_STRING,
        "accrued_interest_per_instrument": base._OA_STRING,
        "clean_values": _OA_VALUATION_VALUES,
        "values": _OA_VALUATION_VALUES,
    }
)
_OA_PORTFOLIO_MARKET_POSITION = base._oa_obj(
    {
        "instrument": base._OA_INSTRUMENT,
        "quantity_units": base._OA_STRING,
        "position_uids": base._oa_array(base._OA_STRING),
        "source_occurrences": base._OA_INT,
        "enrichment_status": base._OA_STRING,
        "identity_check": base._OA_IDENTITY_CHECK,
        "components": base._oa_obj(
            {
                "last_price": base._OA_STRING,
                "trading_status": base._OA_STRING,
                "order_book": base._OA_STRING,
                "valuation": base._OA_STRING,
            }
        ),
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
        "last_price": base._OA_LAST_PRICE,
        "trading_status": base._OA_TRADING_STATUS,
        "order_book": base._OA_ORDER_BOOK,
        "valuation": _OA_PORTFOLIO_VALUATION,
    }
)
_OA_CASH_BALANCE = base._oa_obj(
    {
        "currency": base._OA_STRING,
        "reported_money": base._OA_STRING,
        "reported_blocked": base._OA_STRING,
    }
)
_OA_CURRENCY_TOTAL = base._oa_obj(
    {
        "currency": base._OA_STRING,
        "cash_reported": base._OA_STRING,
        "cash_blocked_reported": base._OA_STRING,
        "securities_last_price": base._OA_STRING,
        "securities_best_bid": base._OA_STRING,
        "securities_best_ask": base._OA_STRING,
        "portfolio_last_price": base._OA_STRING,
        "portfolio_best_bid": base._OA_STRING,
        "portfolio_best_ask": base._OA_STRING,
        "positions_valued_last_price": base._OA_INT,
        "positions_valued_best_bid": base._OA_INT,
        "positions_valued_best_ask": base._OA_INT,
    }
)
base._ACTION_200_SCHEMAS["/portfolio/market-snapshot"] = base._oa_obj(
    {
        "status": base._OA_STRING,
        "version": base._OA_STRING,
        "retrieved_at": base._OA_STRING,
        "source_snapshot_retrieved_at": base._OA_STRING,
        "account": base._OA_ACCOUNT,
        "market_snapshot_parameters": base._oa_obj(
            {
                "order_book_depth": base._OA_INT,
                "max_instruments": base._OA_INT,
            }
        ),
        "components": base._oa_obj(
            {
                "portfolio_enrichment": base._OA_STRING,
                "last_prices_batch": base._oa_obj(
                    {
                        "status": base._OA_STRING,
                        "requested_instruments": base._OA_INT,
                        "returned_prices": base._OA_INT,
                        "api_calls": base._OA_INT,
                    }
                ),
            }
        ),
        "cash_balances": base._oa_array(_OA_CASH_BALANCE),
        "portfolio_positions": base._oa_array(_OA_PORTFOLIO_MARKET_POSITION),
        "totals_by_currency": base._oa_array(_OA_CURRENCY_TOTAL),
        "quality": base._oa_obj(
            {
                "portfolio_position_count": base._OA_INT,
                "cash_like_portfolio_positions": base._OA_INT,
                "zero_quantity_positions": base._OA_INT,
                "missing_uid_positions": base._OA_INT,
                "duplicate_uid_occurrences": base._OA_INT,
                "unique_market_instruments": base._OA_INT,
                "market_instruments_processed": base._OA_INT,
                "market_instruments_skipped_by_limit": base._OA_INT,
                "positions_with_any_valuation": base._OA_INT,
                "positions_without_valuation": base._OA_INT,
                "last_price_batch_calls": base._OA_INT,
                "order_book_calls": base._OA_INT,
                "trading_status_calls": base._OA_INT,
                "component_errors": base._OA_INT,
            }
        ),
        "enrichment_quality": base._oa_obj(
            {
                "position_occurrences": base._OA_INT,
                "unique_instrument_references": base._OA_INT,
                "references_resolved": base._OA_INT,
                "references_unresolved": base._OA_INT,
                "cache_hits": base._OA_INT,
                "instrument_api_calls": base._OA_INT,
                "identity_conflicts": base._OA_INT,
            }
        ),
        "trading_methods": base._OA_BOOL,
        "warnings": base._oa_array(base._OA_STRING),
    },
    required=["status", "version", "retrieved_at", "account"],
)

_OA_ANALYTICS_LARGEST_POSITION = base._oa_obj(
    {
        "instrument": base._OA_INSTRUMENT,
        "asset_class": base._OA_STRING,
        "value": base._OA_STRING,
        "portfolio_weight_percent": base._OA_STRING,
        "securities_weight_percent": base._OA_STRING,
    }
)
_OA_ANALYTICS_SUMMARY = base._oa_obj(
    {
        "currency": base._OA_STRING,
        "cash_value": base._OA_STRING,
        "securities_value": base._OA_STRING,
        "portfolio_value": base._OA_STRING,
        "cash_share_percent": base._OA_STRING,
        "securities_share_percent": base._OA_STRING,
        "market_position_count": base._OA_INT,
        "valued_position_count": base._OA_INT,
        "unvalued_position_count": base._OA_INT,
        "valuation_coverage_percent": base._OA_STRING,
        "top_n": base._OA_INT,
        "top_n_concentration_percent": base._OA_STRING,
        "top_n_securities_concentration_percent": base._OA_STRING,
        "largest_position": _OA_ANALYTICS_LARGEST_POSITION,
    }
)
_OA_ASSET_CLASS_ALLOCATION_ITEM = base._oa_obj(
    {
        "asset_class": base._OA_STRING,
        "value": base._OA_STRING,
        "portfolio_share_percent": base._OA_STRING,
        "position_count": base._OA_INT,
    }
)
_OA_ASSET_CLASS_ALLOCATION = base._oa_obj(
    {
        "currency": base._OA_STRING,
        "items": base._oa_array(_OA_ASSET_CLASS_ALLOCATION_ITEM),
    }
)
_OA_POSITION_WEIGHT = base._oa_obj(
    {
        "currency": base._OA_STRING,
        "rank_within_currency": base._OA_INT,
        "instrument": base._OA_INSTRUMENT,
        "asset_class": base._OA_STRING,
        "quantity_units": base._OA_STRING,
        "valuation_basis": base._OA_STRING,
        "value": base._OA_STRING,
        "portfolio_weight_percent": base._OA_STRING,
        "securities_weight_percent": base._OA_STRING,
    }
)
_OA_CURRENCY_EXPOSURE = base._oa_obj(
    {
        "currency": base._OA_STRING,
        "cash_value": base._OA_STRING,
        "securities_value": base._OA_STRING,
        "portfolio_value": base._OA_STRING,
        "cross_currency_share_percent": base._OA_STRING,
    }
)
_OA_CONCENTRATION = base._oa_obj(
    {
        "currency": base._OA_STRING,
        "top_n": base._OA_INT,
        "market_position_count": base._OA_INT,
        "largest_position_weight_percent": base._OA_STRING,
        "top_n_position_weight_percent": base._OA_STRING,
        "top_n_securities_weight_percent": base._OA_STRING,
    }
)
base._ACTION_200_SCHEMAS["/portfolio/analytics"] = base._oa_obj(
    {
        "status": base._OA_STRING,
        "version": base._OA_STRING,
        "retrieved_at": base._OA_STRING,
        "source_snapshot": base._oa_obj(
            {
                "status": base._OA_STRING,
                "version": base._OA_STRING,
                "retrieved_at": base._OA_STRING,
                "source_snapshot_retrieved_at": base._OA_STRING,
                "valuation_basis": base._OA_STRING,
            }
        ),
        "account": base._OA_ACCOUNT,
        "portfolio_mode": base._OA_STRING,
        "currency_mode": base._OA_STRING,
        "summary_by_currency": base._oa_array(_OA_ANALYTICS_SUMMARY),
        "asset_class_allocation_by_currency": base._oa_array(
            _OA_ASSET_CLASS_ALLOCATION
        ),
        "position_weights": base._oa_array(_OA_POSITION_WEIGHT),
        "currency_exposure": base._oa_array(_OA_CURRENCY_EXPOSURE),
        "concentration_by_currency": base._oa_array(_OA_CONCENTRATION),
        "quality": base._oa_obj(
            {
                "source_status": base._OA_STRING,
                "currencies_detected": base._OA_INT,
                "market_positions_total": base._OA_INT,
                "valued_positions": base._OA_INT,
                "unvalued_positions": base._OA_INT,
                "valuation_coverage_percent": base._OA_STRING,
                "valuation_basis": base._OA_STRING,
                "component_errors": base._OA_INT,
                "market_instruments_skipped_by_limit": base._OA_INT,
                "identity_conflicts": base._OA_INT,
                "nonpositive_portfolio_currencies": base._OA_INT,
                "complete_for_selected_basis": base._OA_BOOL,
                "no_cross_currency_aggregation": base._OA_BOOL,
            }
        ),
        "trading_methods": base._OA_BOOL,
        "warnings": base._oa_array(base._OA_STRING),
    },
    required=[
        "status",
        "version",
        "retrieved_at",
        "account",
        "portfolio_mode",
        "currency_mode",
    ],
)

_OA_CASH_SOURCE_PRESENCE = base._oa_obj(
    {
        "positions": base._OA_BOOL,
        "withdraw_limits": base._OA_BOOL,
    }
)
_OA_CASH_LIQUIDITY_ROW = base._oa_obj(
    {
        "currency": base._OA_STRING,
        "reported_money": base._OA_STRING,
        "positions_blocked": base._OA_STRING,
        "withdrawable_money": base._OA_STRING,
        "withdraw_blocked": base._OA_STRING,
        "blocked_guarantee": base._OA_STRING,
        "cash_difference": base._OA_STRING,
        "cash_difference_basis": base._OA_STRING,
        "cash_status": base._OA_STRING,
        "source_presence": _OA_CASH_SOURCE_PRESENCE,
        "discrepancy_reasons": base._oa_array(base._OA_STRING),
    }
)
_OA_CASH_COMPONENT = base._oa_obj(
    {
        "status": base._OA_STRING,
        "source": base._OA_STRING,
        "limits_loading_in_progress": base._OA_BOOL,
    }
)
_OA_CASH_COMPONENT_ERROR_DETAIL = base._oa_obj(
    {
        "code": base._OA_STRING,
        "grpc_code": base._OA_STRING,
        "exception_type": base._OA_STRING,
        "message": base._OA_STRING,
        "tracking_id": base._OA_STRING,
    }
)
_OA_CASH_COMPONENT_ERROR = base._oa_obj(
    {
        "component": base._OA_STRING,
        "error": _OA_CASH_COMPONENT_ERROR_DETAIL,
    }
)
base._ACTION_200_SCHEMAS["/portfolio/cash-liquidity"] = base._oa_obj(
    {
        "status": base._OA_STRING,
        "version": base._OA_STRING,
        "retrieved_at": base._OA_STRING,
        "account": base._OA_ACCOUNT,
        "cash_mode": base._OA_STRING,
        "cash_by_currency": base._oa_array(_OA_CASH_LIQUIDITY_ROW),
        "components": base._oa_obj(
            {
                "positions": _OA_CASH_COMPONENT,
                "withdraw_limits": _OA_CASH_COMPONENT,
            }
        ),
        "buying_power": base._oa_obj(
            {
                "confirmed": base._OA_BOOL,
                "reason": base._OA_STRING,
            }
        ),
        "quality": base._oa_obj(
            {
                "positions_source_status": base._OA_STRING,
                "withdraw_limits_source_status": base._OA_STRING,
                "currencies_detected": base._OA_INT,
                "currencies_present_in_both_sources": base._OA_INT,
                "currencies_matched": base._OA_INT,
                "source_discrepancies": base._OA_INT,
                "negative_values_detected": base._OA_INT,
                "invalid_money_rows": base._OA_INT,
                "limits_loading_in_progress": base._OA_BOOL,
                "buying_power_confirmed": base._OA_BOOL,
                "complete": base._OA_BOOL,
                "no_cross_currency_aggregation": base._OA_BOOL,
            }
        ),
        "component_errors": base._oa_array(_OA_CASH_COMPONENT_ERROR),
        "trading_methods": base._OA_BOOL,
        "warnings": base._oa_array(base._OA_STRING),
    },
    required=[
        "status",
        "version",
        "retrieved_at",
        "account",
        "cash_mode",
    ],
)

app.openapi_schema = None
