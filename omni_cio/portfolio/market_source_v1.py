from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable

from fastapi import HTTPException


CASH_INSTRUMENT_KINDS = {
    "INSTRUMENT_TYPE_CURRENCY",
}
SPOT_INSTRUMENT_KINDS = {
    "INSTRUMENT_TYPE_SHARE",
    "INSTRUMENT_TYPE_ETF",
    "INSTRUMENT_TYPE_SP",
}
BOND_INSTRUMENT_KIND = "INSTRUMENT_TYPE_BOND"


def _normalized_kind(item: dict[str, Any], metadata: dict[str, Any]) -> str:
    value = (
        metadata.get("instrument_kind")
        or item.get("instrument_kind")
        or item.get("instrument_type")
        or "INSTRUMENT_TYPE_UNSPECIFIED"
    )
    normalized = str(value or "").strip().upper()
    aliases = {
        "SHARE": "INSTRUMENT_TYPE_SHARE",
        "STOCK": "INSTRUMENT_TYPE_SHARE",
        "BOND": "INSTRUMENT_TYPE_BOND",
        "ETF": "INSTRUMENT_TYPE_ETF",
        "CURRENCY": "INSTRUMENT_TYPE_CURRENCY",
        "FUTURES": "INSTRUMENT_TYPE_FUTURES",
        "FUTURE": "INSTRUMENT_TYPE_FUTURES",
        "OPTION": "INSTRUMENT_TYPE_OPTION",
        "SP": "INSTRUMENT_TYPE_SP",
    }
    return aliases.get(normalized, normalized or "INSTRUMENT_TYPE_UNSPECIFIED")


def _position_quantity(
    base: Any, item: dict[str, Any], metadata: dict[str, Any]
) -> Decimal | None:
    """Return instrument units, not lots, for a portfolio position."""
    for field_name in ("quantity", "balance"):
        value = base.decimal_from_any(item.get(field_name))
        if value is not None:
            return value

    quantity_lots = base.decimal_from_any(item.get("quantity_lots"))
    lot = base.decimal_from_any(metadata.get("lot"))
    if quantity_lots is not None and lot is not None and lot > 0:
        return quantity_lots * lot
    return None


def _instrument_uid(item: dict[str, Any], metadata: dict[str, Any]) -> str:
    return str(
        metadata.get("uid") or item.get("instrument_uid") or item.get("uid") or ""
    ).strip()


def _compact_instrument(
    item: dict[str, Any], metadata: dict[str, Any]
) -> dict[str, Any]:
    result = {
        "name": metadata.get("name"),
        "ticker": metadata.get("ticker"),
        "isin": metadata.get("isin"),
        "figi": metadata.get("figi") or item.get("figi"),
        "uid": _instrument_uid(item, metadata),
        "position_uid": metadata.get("position_uid") or item.get("position_uid"),
        "class_code": metadata.get("class_code"),
        "instrument_type": metadata.get("instrument_type")
        or item.get("instrument_type"),
        "instrument_kind": _normalized_kind(item, metadata),
        "lot": metadata.get("lot"),
        "currency": metadata.get("currency"),
        "nominal": metadata.get("nominal"),
        "accrued_interest": metadata.get("accrued_interest"),
    }
    return {key: value for key, value in result.items() if value not in (None, "")}



def _market_position_candidate(
    base: Any,
    item: object,
) -> tuple[str, str, dict[str, Any] | None]:
    if not isinstance(item, dict):
        return "invalid", "", None
    metadata = item.get("instrument_metadata")
    safe_metadata = metadata if isinstance(metadata, dict) else {}
    kind = _normalized_kind(item, safe_metadata)
    if kind in CASH_INSTRUMENT_KINDS:
        return "cash", "", None

    quantity = _position_quantity(base, item, safe_metadata)
    if quantity is not None and quantity == 0:
        return "zero", "", None

    uid = _instrument_uid(item, safe_metadata)
    if not uid:
        return "missing_uid", "", None
    position_uid = str(
        item.get("position_uid") or safe_metadata.get("position_uid") or ""
    ).strip()
    return (
        "market",
        uid,
        {
            "instrument": _compact_instrument(item, safe_metadata),
            "quantity_decimal": quantity,
            "position_uids": [position_uid] if position_uid else [],
            "source_occurrences": 1,
            "identity_check": item.get("identity_check"),
            "enrichment_status": item.get("enrichment_status"),
        },
    )


def _merge_market_position(
    entry: dict[str, Any],
    duplicate: dict[str, Any],
) -> None:
    existing_quantity = entry.get("quantity_decimal")
    quantity = duplicate.get("quantity_decimal")
    if isinstance(existing_quantity, Decimal) and isinstance(quantity, Decimal):
        entry["quantity_decimal"] = existing_quantity + quantity
    elif existing_quantity is None:
        entry["quantity_decimal"] = quantity
    entry["source_occurrences"] = int(entry.get("source_occurrences", 1)) + 1
    for position_uid in duplicate.get("position_uids", []):
        if position_uid and position_uid not in entry["position_uids"]:
            entry["position_uids"].append(position_uid)


def _group_market_positions(
    base: Any, enriched_positions: Any
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    grouped: dict[str, dict[str, Any]] = {}
    quality = {
        "portfolio_position_count": 0,
        "cash_like_portfolio_positions": 0,
        "zero_quantity_positions": 0,
        "missing_uid_positions": 0,
        "duplicate_uid_occurrences": 0,
    }
    if not isinstance(enriched_positions, list):
        return [], quality

    for item in enriched_positions:
        status, uid, candidate = _market_position_candidate(base, item)
        if status == "invalid":
            continue
        quality["portfolio_position_count"] += 1
        if status == "cash":
            quality["cash_like_portfolio_positions"] += 1
            continue
        if status == "zero":
            quality["zero_quantity_positions"] += 1
            continue
        if status == "missing_uid":
            quality["missing_uid_positions"] += 1
            continue
        if candidate is None:
            continue
        existing = grouped.get(uid)
        if existing is None:
            grouped[uid] = candidate
            continue
        quality["duplicate_uid_occurrences"] += 1
        _merge_market_position(existing, candidate)
    return list(grouped.values()), quality

def _money_rows(base: Any, raw_rows: Any) -> dict[str, Decimal]:
    result: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    if not isinstance(raw_rows, list):
        return result

    for row in raw_rows:
        if not isinstance(row, dict):
            continue
        currency = str(row.get("currency", "UNKNOWN") or "UNKNOWN").upper()
        amount = base.decimal_from_any(row)
        if amount is not None:
            result[currency] += amount
    return result


def build_cash_balances(base: Any, positions_data: Any) -> list[dict[str, Any]]:
    safe_positions = positions_data if isinstance(positions_data, dict) else {}
    reported = _money_rows(base, safe_positions.get("money"))
    blocked = _money_rows(base, safe_positions.get("blocked"))
    currencies = sorted(set(reported) | set(blocked))
    return [
        {
            "currency": currency,
            "reported_money": base.decimal_string(reported.get(currency, Decimal("0"))),
            "reported_blocked": base.decimal_string(
                blocked.get(currency, Decimal("0"))
            ),
        }
        for currency in currencies
    ]


def _safe_last_price_item(
    base: Any, raw_price: dict[str, Any], retrieved_at: datetime
) -> dict[str, Any]:
    price_time = raw_price.get("time")
    result = {
        "status": "ok",
        "price": base.safe_quotation(raw_price.get("price")),
        "time": price_time,
        "age_seconds": base.nonnegative_age_seconds(price_time, retrieved_at),
        "instrument_uid": raw_price.get("instrument_uid"),
        "figi": raw_price.get("figi"),
        "last_price_type": base.normalized_operation_enum(
            raw_price.get("last_price_type"),
            {},
            "LAST_PRICE_UNSPECIFIED",
        ),
    }
    return base.json_safe_value(
        {key: value for key, value in result.items() if value is not None}
    )



def _index_last_prices(
    *,
    base: Any,
    raw_prices: object,
    retrieved_at: datetime,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_uid: dict[str, dict[str, Any]] = {}
    by_figi: dict[str, dict[str, Any]] = {}
    if not isinstance(raw_prices, list):
        return by_uid, by_figi
    for raw_price in raw_prices:
        if not isinstance(raw_price, dict):
            continue
        safe_price = _safe_last_price_item(base, raw_price, retrieved_at)
        uid = str(safe_price.get("instrument_uid", "") or "").strip()
        figi = str(safe_price.get("figi", "") or "").strip()
        if uid:
            by_uid[uid] = safe_price
        if figi:
            by_figi[figi] = safe_price
    return by_uid, by_figi


def _batch_last_prices(
    base: Any,
    client: Any,
    positions: list[dict[str, Any]],
    retrieved_at: datetime,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any]]:
    uids = [
        uid
        for entry in positions
        if (uid := str(entry["instrument"].get("uid", "") or "").strip())
    ]
    if not uids:
        return {}, {}, {"status": "not_requested", "requested_instruments": 0}

    try:
        response = client.market_data.get_last_prices(instrument_id=uids)
        data = base.proto_to_dict(response)
        by_uid, by_figi = _index_last_prices(
            base=base,
            raw_prices=data.get("last_prices", []),
            retrieved_at=retrieved_at,
        )
        return (
            by_uid,
            by_figi,
            {
                "status": "ok",
                "requested_instruments": len(uids),
                "returned_prices": len(by_uid) or len(by_figi),
                "api_calls": 1,
            },
        )
    except Exception as exc:
        return (
            {},
            {},
            {
                **base.market_component_error("last_prices_batch", exc),
                "requested_instruments": len(uids),
                "api_calls": 1,
            },
        )

def _price_from_level(base: Any, level: Any) -> Decimal | None:
    if not isinstance(level, dict):
        return None
    return base.decimal_from_any(level.get("price"))



def _valuation_prices(
    base: Any,
    last_price: dict[str, Any],
    order_book: dict[str, Any],
) -> dict[str, Decimal]:
    candidates = {
        "last_price": base.decimal_from_any(last_price.get("price")),
        "best_bid": _price_from_level(base, order_book.get("best_bid")),
        "best_ask": _price_from_level(base, order_book.get("best_ask")),
    }
    return {
        name: value
        for name, value in candidates.items()
        if value is not None
    }


def _spot_valuation(
    *,
    base: Any,
    quantity: Decimal,
    prices: dict[str, Decimal],
    result: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Decimal]]:
    totals = {name: quantity * price for name, price in prices.items()}
    result["basis"] = "quantity_units_times_price_per_instrument"
    result["values"] = {
        name: base.decimal_string(value) for name, value in totals.items()
    }
    return result, totals


def _bond_valuation(
    *,
    base: Any,
    quantity: Decimal,
    instrument: dict[str, Any],
    prices: dict[str, Decimal],
    result: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Decimal]]:
    nominal = base.decimal_from_any(instrument.get("nominal"))
    result["basis"] = "bond_price_percent_of_nominal"
    if nominal is None:
        result["reason"] = (
            "Bond nominal was not available, so valuation was not calculated."
        )
        return result, {}

    accrued = base.decimal_from_any(instrument.get("accrued_interest")) or Decimal("0")
    clean_values = {
        name: quantity * nominal * price / Decimal("100")
        for name, price in prices.items()
    }
    totals = {
        name: clean_value + quantity * accrued
        for name, clean_value in clean_values.items()
    }
    result["basis"] = (
        "quantity_times_nominal_times_price_percent_plus_accrued_interest"
    )
    result["nominal_per_instrument"] = base.decimal_string(nominal)
    result["accrued_interest_per_instrument"] = base.decimal_string(accrued)
    result["clean_values"] = {
        name: base.decimal_string(value) for name, value in clean_values.items()
    }
    result["values"] = {
        name: base.decimal_string(value) for name, value in totals.items()
    }
    return result, totals


def calculate_position_valuation(
    base: Any,
    quantity: Decimal | None,
    instrument: dict[str, Any],
    last_price: dict[str, Any],
    order_book: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Decimal]]:
    kind = str(instrument.get("instrument_kind", "") or "").upper()
    currency = str(instrument.get("currency", "") or "").upper()
    prices = _valuation_prices(base, last_price, order_book)
    result: dict[str, Any] = {
        "status": "unavailable",
        "currency": currency or None,
        "quantity_units": (
            base.decimal_string(quantity) if quantity is not None else None
        ),
        "instrument_kind": kind or None,
        "basis": None,
        "values": {},
    }

    if quantity is None:
        result["reason"] = "Position quantity was not available."
        totals: dict[str, Decimal] = {}
    elif not prices:
        result["reason"] = "No usable last price, best bid, or best ask was returned."
        totals = {}
    elif kind in SPOT_INSTRUMENT_KINDS:
        result, totals = _spot_valuation(
            base=base,
            quantity=quantity,
            prices=prices,
            result=result,
        )
    elif kind == BOND_INSTRUMENT_KIND:
        result, totals = _bond_valuation(
            base=base,
            quantity=quantity,
            instrument=instrument,
            prices=prices,
            result=result,
        )
    else:
        result["basis"] = "unsupported_generic_valuation"
        result["reason"] = (
            "The gateway does not apply a generic portfolio valuation formula "
            "to this instrument type."
        )
        totals = {}

    if totals:
        result["status"] = "ok" if len(totals) == 3 else "partial"
    return (
        base.json_safe_value({k: v for k, v in result.items() if v is not None}),
        totals,
    )

def _compact_order_book(order_book: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "status",
        "requested_depth",
        "returned_bid_levels",
        "returned_ask_levels",
        "depth",
        "instrument_uid",
        "figi",
        "time",
        "age_seconds",
        "best_bid",
        "best_ask",
        "spread",
        "order_book_type",
    )
    return {key: order_book[key] for key in fields if key in order_book}


def _totals_rows(
    base: Any,
    cash_balances: list[dict[str, Any]],
    valuation_totals: dict[str, dict[str, Decimal]],
    valuation_counts: dict[str, dict[str, int]],
) -> list[dict[str, Any]]:
    cash_map: dict[str, dict[str, Decimal]] = {}
    for row in cash_balances:
        currency = str(row.get("currency", "UNKNOWN") or "UNKNOWN").upper()
        cash_map[currency] = {
            "reported_money": base.decimal_from_any(row.get("reported_money"))
            or Decimal("0"),
            "reported_blocked": base.decimal_from_any(row.get("reported_blocked"))
            or Decimal("0"),
        }

    currencies = sorted(set(cash_map) | set(valuation_totals))
    rows: list[dict[str, Any]] = []
    for currency in currencies:
        cash = cash_map.get(
            currency,
            {"reported_money": Decimal("0"), "reported_blocked": Decimal("0")},
        )
        securities = valuation_totals.get(currency, {})
        counts = valuation_counts.get(currency, {})
        reported_money = cash["reported_money"]
        last_value = securities.get("last_price", Decimal("0"))
        bid_value = securities.get("best_bid", Decimal("0"))
        ask_value = securities.get("best_ask", Decimal("0"))
        rows.append(
            {
                "currency": currency,
                "cash_reported": base.decimal_string(reported_money),
                "cash_blocked_reported": base.decimal_string(cash["reported_blocked"]),
                "securities_last_price": base.decimal_string(last_value),
                "securities_best_bid": base.decimal_string(bid_value),
                "securities_best_ask": base.decimal_string(ask_value),
                "portfolio_last_price": base.decimal_string(
                    reported_money + last_value
                ),
                "portfolio_best_bid": base.decimal_string(reported_money + bid_value),
                "portfolio_best_ask": base.decimal_string(reported_money + ask_value),
                "positions_valued_last_price": int(counts.get("last_price", 0)),
                "positions_valued_best_bid": int(counts.get("best_bid", 0)),
                "positions_valued_best_ask": int(counts.get("best_ask", 0)),
            }
        )
    return rows



def _market_component(
    *,
    base: Any,
    loader: Callable[[], Any],
    serializer: Callable[[Any], dict[str, Any]],
    component: str,
) -> tuple[dict[str, Any], int]:
    try:
        return serializer(loader()), 0
    except Exception as exc:
        return base.market_component_error(component, exc), 1


def _processed_market_position(
    *,
    base: Any,
    client: Any,
    entry: dict[str, Any],
    last_by_uid: dict[str, dict[str, Any]],
    last_by_figi: dict[str, dict[str, Any]],
    depth: int,
    retrieved_at: datetime,
    market_dealer_session: Callable[
        [dict[str, Any], dict[str, Any], dict[str, Any]], bool
    ],
    trading_flag_consistency_issues: Callable[
        [dict[str, Any], dict[str, Any], dict[str, Any]], list[str]
    ],
) -> tuple[dict[str, Any], dict[str, Decimal], int]:
    instrument = entry["instrument"]
    uid = str(instrument.get("uid", "") or "").strip()
    figi = str(instrument.get("figi", "") or "").strip()
    last_price = (
        last_by_uid.get(uid)
        or last_by_figi.get(figi)
        or {
            "status": "unavailable",
            "reason": "The batch last-price response did not include this instrument.",
            "instrument_uid": uid,
        }
    )
    trading_status, trading_error = _market_component(
        base=base,
        loader=lambda: client.market_data.get_trading_status(instrument_id=uid),
        serializer=base.safe_trading_status_response,
        component="trading_status",
    )
    order_book, order_error = _market_component(
        base=base,
        loader=lambda: client.market_data.get_order_book(
            instrument_id=uid,
            depth=depth,
        ),
        serializer=lambda response: base.safe_order_book_response(
            response,
            depth,
            retrieved_at,
        ),
        component="order_book",
    )
    issues = trading_flag_consistency_issues(
        last_price,
        trading_status,
        order_book,
    )
    valuation, decimal_values = calculate_position_valuation(
        base,
        entry.get("quantity_decimal"),
        instrument,
        last_price,
        order_book,
    )
    components = {
        "last_price": last_price.get("status"),
        "trading_status": trading_status.get("status"),
        "order_book": order_book.get("status"),
        "valuation": valuation.get("status"),
    }
    component_errors = (
        trading_error
        + order_error
        + int(any(value == "error" for value in components.values()))
    )
    row = {
        "instrument": instrument,
        "quantity_units": (
            base.decimal_string(entry["quantity_decimal"])
            if isinstance(entry.get("quantity_decimal"), Decimal)
            else None
        ),
        "position_uids": entry.get("position_uids", []),
        "source_occurrences": entry.get("source_occurrences", 1),
        "enrichment_status": entry.get("enrichment_status"),
        "identity_check": entry.get("identity_check"),
        "components": components,
        "dealer_session": market_dealer_session(
            last_price,
            trading_status,
            order_book,
        ),
        "market_data_sources": {
            "last_price_type": last_price.get(
                "last_price_type",
                "LAST_PRICE_UNSPECIFIED",
            ),
            "order_book_type": order_book.get(
                "order_book_type",
                "ORDERBOOK_TYPE_UNSPECIFIED",
            ),
        },
        "trading_flag_consistency": {
            "status": "warning" if issues else "ok",
            "issues": issues,
            "raw_fields_preserved": True,
        },
        "last_price": last_price,
        "trading_status": trading_status,
        "order_book": _compact_order_book(order_book),
        "valuation": valuation,
    }
    return row, decimal_values, component_errors


def _skipped_market_position(base: Any, entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "instrument": entry["instrument"],
        "quantity_units": (
            base.decimal_string(entry["quantity_decimal"])
            if isinstance(entry.get("quantity_decimal"), Decimal)
            else None
        ),
        "position_uids": entry.get("position_uids", []),
        "source_occurrences": entry.get("source_occurrences", 1),
        "enrichment_status": entry.get("enrichment_status"),
        "components": {
            "last_price": "skipped",
            "trading_status": "skipped",
            "order_book": "skipped",
            "valuation": "skipped",
        },
        "valuation": {
            "status": "skipped",
            "reason": "The per-request market-instrument safety limit was reached.",
        },
    }


def _market_snapshot_status(
    *,
    eligible_positions: int,
    processed_positions: int,
    skipped_positions: int,
    valued_positions: int,
    component_errors: int,
) -> str:
    if eligible_positions == 0:
        return "ok"
    if (
        valued_positions == processed_positions
        and skipped_positions == 0
        and component_errors == 0
    ):
        return "ok"
    return "partial" if valued_positions > 0 else "error"


def _market_snapshot_warnings(
    *,
    max_instruments: int,
    positions_skipped: list[dict[str, Any]],
    last_batch: dict[str, Any],
) -> list[str]:
    warnings = [
        "Last price is the latest recorded trade and is not automatically an executable price.",
        "Best bid and best ask are visible quotes at snapshot time and may change before any later decision.",
        "Portfolio position quantity is treated as instrument units; order-book quantities are expressed in lots.",
        "Bond quotations are percentages of nominal. Bond totals include reported accrued interest when nominal is available.",
        "Cash is reported from GetPositions.money. GetPositions.blocked is shown separately and is not added again to portfolio totals.",
        "Currencies are never converted or summed together; totals are grouped by reported currency.",
        "A failure for one market-data component does not discard successful data for other instruments.",
        "The gateway remains read-only and exposes no order placement, replacement, or cancellation endpoints.",
    ]
    if positions_skipped:
        warnings.append(
            f"Market data was limited to {max_instruments} unique instruments in this request."
        )
    if last_batch.get("status") == "error":
        warnings.append(
            "The batch last-price request failed; order-book and trading-status results may still be present."
        )
    return warnings


def get_portfolio_market_snapshot(
    *,
    base: Any,
    app_version: str,
    market_dealer_session: Callable[
        [dict[str, Any], dict[str, Any], dict[str, Any]], bool
    ],
    trading_flag_consistency_issues: Callable[
        [dict[str, Any], dict[str, Any], dict[str, Any]], list[str]
    ],
    depth: int,
    max_instruments: int,
) -> dict[str, Any]:
    base.ensure_configured()
    retrieved_at = datetime.now(timezone.utc)
    try:
        enriched = base.enriched_snapshot()
        grouped_positions, grouping_quality = _group_market_positions(
            base,
            enriched.get("enriched_portfolio_positions", []),
        )
        cash_balances = build_cash_balances(base, enriched.get("positions"))
        positions_to_process = grouped_positions[:max_instruments]
        positions_skipped = grouped_positions[max_instruments:]

        valuation_totals: dict[str, dict[str, Decimal]] = defaultdict(
            lambda: defaultdict(lambda: Decimal("0"))
        )
        valuation_counts: dict[str, dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        output_positions: list[dict[str, Any]] = []
        component_errors = 0
        valued_positions = 0

        with base.Client(base.TINVEST_TOKEN) as client:
            last_by_uid, last_by_figi, last_batch = _batch_last_prices(
                base,
                client,
                positions_to_process,
                retrieved_at,
            )
            for entry in positions_to_process:
                row, decimal_values, row_errors = _processed_market_position(
                    base=base,
                    client=client,
                    entry=entry,
                    last_by_uid=last_by_uid,
                    last_by_figi=last_by_figi,
                    depth=depth,
                    retrieved_at=retrieved_at,
                    market_dealer_session=market_dealer_session,
                    trading_flag_consistency_issues=trading_flag_consistency_issues,
                )
                output_positions.append(row)
                component_errors += row_errors
                currency = str(
                    row["valuation"].get("currency", "UNKNOWN") or "UNKNOWN"
                ).upper()
                for source_name, value in decimal_values.items():
                    valuation_totals[currency][source_name] += value
                    valuation_counts[currency][source_name] += 1
                valued_positions += int(bool(decimal_values))

        output_positions.extend(
            _skipped_market_position(base, entry)
            for entry in positions_skipped
        )
        totals_by_currency = _totals_rows(
            base,
            cash_balances,
            valuation_totals,
            valuation_counts,
        )
        eligible_positions = len(grouped_positions)
        overall_status = _market_snapshot_status(
            eligible_positions=eligible_positions,
            processed_positions=len(positions_to_process),
            skipped_positions=len(positions_skipped),
            valued_positions=valued_positions,
            component_errors=component_errors,
        )
        return base.json_safe_value(
            {
                "status": overall_status,
                "version": app_version,
                "retrieved_at": retrieved_at.isoformat(),
                "source_snapshot_retrieved_at": enriched.get("retrieved_at"),
                "account": enriched.get("account"),
                "market_snapshot_parameters": {
                    "order_book_depth": depth,
                    "max_instruments": max_instruments,
                },
                "components": {
                    "portfolio_enrichment": enriched.get("status", "unknown"),
                    "last_prices_batch": last_batch,
                },
                "cash_balances": cash_balances,
                "portfolio_positions": output_positions,
                "totals_by_currency": totals_by_currency,
                "quality": {
                    **grouping_quality,
                    "unique_market_instruments": eligible_positions,
                    "market_instruments_processed": len(positions_to_process),
                    "market_instruments_skipped_by_limit": len(positions_skipped),
                    "positions_with_any_valuation": valued_positions,
                    "positions_without_valuation": max(
                        0, eligible_positions - valued_positions
                    ),
                    "last_price_batch_calls": int(last_batch.get("api_calls", 0) or 0),
                    "order_book_calls": len(positions_to_process),
                    "trading_status_calls": len(positions_to_process),
                    "component_errors": component_errors,
                },
                "enrichment_quality": enriched.get("enrichment_quality", {}),
                "trading_methods": False,
                "warnings": _market_snapshot_warnings(
                    max_instruments=max_instruments,
                    positions_skipped=positions_skipped,
                    last_batch=last_batch,
                ),
            }
        )
    except HTTPException:
        raise
    except Exception as exc:
        safe_message = base.safe_error_message(exc)
        base.logger.exception(
            "Gateway portfolio-market-snapshot failure: %s: %s",
            type(exc).__name__,
            safe_message,
        )
        if isinstance(exc, base.grpc.RpcError):
            http_status, payload = base.grpc_error_payload(exc)
            raise HTTPException(status_code=http_status, detail=payload) from exc
        raise HTTPException(
            status_code=502,
            detail={
                "code": "GATEWAY_PORTFOLIO_MARKET_SNAPSHOT_ERROR",
                "exception_type": type(exc).__name__,
                "message": safe_message,
                "runtime": {
                    "python": base.sys.version.split()[0],
                    "t_tech_investments": base.package_version("t-tech-investments"),
                    "protobuf": base.package_version("protobuf"),
                    "grpcio": base.package_version("grpcio"),
                },
            },
        ) from exc

