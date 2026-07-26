from typing import Any

from fastapi import Depends, Query
from fastapi.routing import APIRoute

import main as base


app = base.app
app.version = "3.3.2"

if "market_source_diagnostics" not in base.CAPABILITIES:
    base.CAPABILITIES.append("market_source_diagnostics")


_original_safe_order_book_response = base.safe_order_book_response


def safe_order_book_response_v332(
    response: Any,
    requested_depth: int,
    retrieved_at: Any,
) -> dict[str, Any]:
    """Keep the v3.3.1 order-book response and expose its raw source enum."""
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


# The existing v3.3.1 market endpoint looks up this helper at call time, so this
# replacement adds the source field without duplicating the SDK request logic.
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


# Remove only the original GET /market/snapshot route. The original function
# remains callable and continues to own all SDK requests and error handling.
app.router.routes = [
    route
    for route in app.router.routes
    if not (
        isinstance(route, APIRoute)
        and route.path == "/market/snapshot"
        and "GET" in (route.methods or set())
    )
]


@app.get(
    "/market/snapshot",
    operation_id="getMarketSnapshot",
    summary=(
        "Get a current read-only market snapshot with source diagnostics for "
        "one exact instrument UID"
    ),
    dependencies=[Depends(base.require_gateway_key)],
)
def market_snapshot_v332(
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


# Extend the GPT Actions-compatible OpenAPI schema while retaining the explicit
# object properties added in v3.3.1.
base._OA_ORDER_BOOK["properties"]["order_book_type"] = base._OA_STRING
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

app.openapi_schema = None
