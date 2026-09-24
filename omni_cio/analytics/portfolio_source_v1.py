from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any


SUPPORTED_VALUATION_BASES = {
    "last_price",
    "best_bid",
    "best_ask",
}

ASSET_CLASS_BY_KIND = {
    "INSTRUMENT_TYPE_SHARE": "shares",
    "INSTRUMENT_TYPE_BOND": "bonds",
    "INSTRUMENT_TYPE_ETF": "etf",
    "INSTRUMENT_TYPE_CURRENCY": "cash",
    "INSTRUMENT_TYPE_FUTURES": "futures",
    "INSTRUMENT_TYPE_OPTION": "options",
    "INSTRUMENT_TYPE_SP": "structured_products",
}

PERCENT_QUANTUM = Decimal("0.000001")


def _decimal(base: Any, value: Any) -> Decimal | None:
    return base.decimal_from_any(value)


def _percent_string(base: Any, numerator: Decimal, denominator: Decimal) -> str:
    if denominator <= 0:
        return "unavailable"
    value = (numerator * Decimal("100") / denominator).quantize(PERCENT_QUANTUM)
    return base.decimal_string(value)


def _asset_class(instrument: dict[str, Any]) -> str:
    kind = str(instrument.get("instrument_kind", "") or "").upper()
    return ASSET_CLASS_BY_KIND.get(kind, "other")


def _safe_instrument(position: dict[str, Any]) -> dict[str, Any]:
    value = position.get("instrument")
    return value if isinstance(value, dict) else {}


def _position_currency(position: dict[str, Any]) -> str:
    valuation = position.get("valuation")
    safe_valuation = valuation if isinstance(valuation, dict) else {}
    instrument = _safe_instrument(position)
    return str(
        safe_valuation.get("currency") or instrument.get("currency") or "UNKNOWN"
    ).upper()


def _position_value(
    base: Any,
    position: dict[str, Any],
    valuation_basis: str,
) -> Decimal | None:
    valuation = position.get("valuation")
    if not isinstance(valuation, dict):
        return None
    values = valuation.get("values")
    if not isinstance(values, dict):
        return None
    return _decimal(base, values.get(valuation_basis))


def _cash_map(base: Any, snapshot: dict[str, Any]) -> dict[str, Decimal]:
    result: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    rows = snapshot.get("cash_balances")
    if not isinstance(rows, list):
        return result
    for row in rows:
        if not isinstance(row, dict):
            continue
        currency = str(row.get("currency", "UNKNOWN") or "UNKNOWN").upper()
        amount = _decimal(base, row.get("reported_money"))
        if amount is not None:
            result[currency] += amount
    return result


def _position_record(
    *,
    base: Any,
    position: dict[str, Any],
    valuation_basis: str,
) -> dict[str, Any]:
    instrument = _safe_instrument(position)
    value = _position_value(base, position, valuation_basis)
    result = {
        "currency": _position_currency(position),
        "asset_class": _asset_class(instrument),
        "value_decimal": value,
        "instrument": {
            key: instrument.get(key)
            for key in (
                "name",
                "ticker",
                "isin",
                "figi",
                "uid",
                "position_uid",
                "class_code",
                "instrument_type",
                "instrument_kind",
                "lot",
                "currency",
            )
            if instrument.get(key) not in (None, "")
        },
        "quantity_units": position.get("quantity_units"),
        "valuation_status": (
            position.get("valuation", {}).get("status")
            if isinstance(position.get("valuation"), dict)
            else "unavailable"
        ),
    }
    return result


def _portfolio_records_by_currency(
    *,
    base: Any,
    snapshot: dict[str, Any],
    valuation_basis: str,
) -> tuple[
    list[dict[str, Any]],
    dict[str, list[dict[str, Any]]],
    dict[str, int],
    dict[str, int],
]:
    raw_positions = snapshot.get("portfolio_positions")
    safe_positions = raw_positions if isinstance(raw_positions, list) else []
    records = [
        _position_record(
            base=base,
            position=position,
            valuation_basis=valuation_basis,
        )
        for position in safe_positions
        if isinstance(position, dict)
    ]
    valued: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unvalued: dict[str, int] = defaultdict(int)
    totals: dict[str, int] = defaultdict(int)
    for record in records:
        currency = str(record["currency"])
        totals[currency] += 1
        if isinstance(record.get("value_decimal"), Decimal):
            valued[currency].append(record)
        else:
            unvalued[currency] += 1
    return records, valued, unvalued, totals


def _largest_position(
    *,
    base: Any,
    records: list[dict[str, Any]],
    portfolio_value: Decimal,
    securities_value: Decimal,
) -> dict[str, Any] | None:
    if not records:
        return None
    first = records[0]
    return {
        "instrument": first["instrument"],
        "asset_class": first["asset_class"],
        "value": base.decimal_string(first["value_decimal"]),
        "portfolio_weight_percent": _percent_string(
            base,
            first["value_decimal"],
            portfolio_value,
        ),
        "securities_weight_percent": _percent_string(
            base,
            first["value_decimal"],
            securities_value,
        ),
    }


def _allocation_items(
    *,
    base: Any,
    cash_value: Decimal,
    valued_records: list[dict[str, Any]],
    portfolio_value: Decimal,
) -> list[dict[str, Any]]:
    class_values: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    class_counts: dict[str, int] = defaultdict(int)
    if cash_value != 0:
        class_values["cash"] += cash_value
        class_counts["cash"] += 1
    for record in valued_records:
        asset_class = str(record["asset_class"])
        class_values[asset_class] += record["value_decimal"]
        class_counts[asset_class] += 1
    return [
        {
            "asset_class": asset_class,
            "value": base.decimal_string(value),
            "portfolio_share_percent": _percent_string(
                base,
                value,
                portfolio_value,
            ),
            "position_count": class_counts[asset_class],
        }
        for asset_class, value in sorted(
            class_values.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]


def _position_weight_rows(
    *,
    base: Any,
    currency: str,
    valued_records: list[dict[str, Any]],
    valuation_basis: str,
    portfolio_value: Decimal,
    securities_value: Decimal,
) -> list[dict[str, Any]]:
    return [
        {
            "currency": currency,
            "rank_within_currency": rank,
            "instrument": record["instrument"],
            "asset_class": record["asset_class"],
            "quantity_units": record.get("quantity_units"),
            "valuation_basis": valuation_basis,
            "value": base.decimal_string(record["value_decimal"]),
            "portfolio_weight_percent": _percent_string(
                base,
                record["value_decimal"],
                portfolio_value,
            ),
            "securities_weight_percent": _percent_string(
                base,
                record["value_decimal"],
                securities_value,
            ),
        }
        for rank, record in enumerate(valued_records, start=1)
    ]


def _currency_analytics(
    *,
    base: Any,
    currency: str,
    cash_value: Decimal,
    valued_records: list[dict[str, Any]],
    market_position_count: int,
    unvalued_position_count: int,
    valuation_basis: str,
    top_n: int,
) -> dict[str, Any]:
    valued_records = sorted(
        valued_records,
        key=lambda row: row["value_decimal"],
        reverse=True,
    )
    securities_value = sum(
        (row["value_decimal"] for row in valued_records),
        Decimal("0"),
    )
    portfolio_value = cash_value + securities_value
    valued_position_count = len(valued_records)
    largest_position = _largest_position(
        base=base,
        records=valued_records,
        portfolio_value=portfolio_value,
        securities_value=securities_value,
    )
    top_value = sum(
        (row["value_decimal"] for row in valued_records[:top_n]),
        Decimal("0"),
    )
    coverage_percent = (
        "100"
        if market_position_count == 0
        else _percent_string(
            base,
            Decimal(valued_position_count),
            Decimal(market_position_count),
        )
    )
    summary: dict[str, Any] = {
        "currency": currency,
        "cash_value": base.decimal_string(cash_value),
        "securities_value": base.decimal_string(securities_value),
        "portfolio_value": base.decimal_string(portfolio_value),
        "cash_share_percent": _percent_string(base, cash_value, portfolio_value),
        "securities_share_percent": _percent_string(
            base,
            securities_value,
            portfolio_value,
        ),
        "market_position_count": market_position_count,
        "valued_position_count": valued_position_count,
        "unvalued_position_count": unvalued_position_count,
        "valuation_coverage_percent": coverage_percent,
        "top_n": top_n,
        "top_n_concentration_percent": _percent_string(
            base,
            top_value,
            portfolio_value,
        ),
        "top_n_securities_concentration_percent": _percent_string(
            base,
            top_value,
            securities_value,
        ),
    }
    if largest_position is not None:
        summary["largest_position"] = largest_position
    return {
        "summary": summary,
        "allocation": {
            "currency": currency,
            "items": _allocation_items(
                base=base,
                cash_value=cash_value,
                valued_records=valued_records,
                portfolio_value=portfolio_value,
            ),
        },
        "concentration": {
            "currency": currency,
            "top_n": top_n,
            "market_position_count": market_position_count,
            "largest_position_weight_percent": (
                largest_position.get("portfolio_weight_percent")
                if largest_position
                else "unavailable"
            ),
            "top_n_position_weight_percent": _percent_string(
                base,
                top_value,
                portfolio_value,
            ),
            "top_n_securities_weight_percent": _percent_string(
                base,
                top_value,
                securities_value,
            ),
        },
        "exposure": {
            "currency": currency,
            "cash_value": base.decimal_string(cash_value),
            "securities_value": base.decimal_string(securities_value),
            "portfolio_value": base.decimal_string(portfolio_value),
            "cross_currency_share_percent": "not_calculated_without_fx_conversion",
        },
        "weights": _position_weight_rows(
            base=base,
            currency=currency,
            valued_records=valued_records,
            valuation_basis=valuation_basis,
            portfolio_value=portfolio_value,
            securities_value=securities_value,
        ),
        "valued_count": valued_position_count,
        "unvalued_count": unvalued_position_count,
        "nonpositive": portfolio_value <= 0,
    }


def _portfolio_mode(
    *,
    cash_by_currency: dict[str, Decimal],
    market_positions_total: int,
) -> str:
    cash_total_nonzero = any(value != 0 for value in cash_by_currency.values())
    if not cash_total_nonzero and market_positions_total == 0:
        return "empty"
    if cash_total_nonzero and market_positions_total == 0:
        return "cash_only"
    if not cash_total_nonzero:
        return "securities_only"
    return "mixed"


def _currency_mode(currencies: list[str]) -> str:
    if not currencies:
        return "empty"
    return "single_currency" if len(currencies) == 1 else "multi_currency"


def _portfolio_warnings(
    *,
    total_unvalued_positions: int,
    skipped_by_limit: int,
    component_errors: int,
) -> list[str]:
    warnings = [
        "Analytics are calculated from the read-only portfolio market snapshot and do not create or submit orders.",
        "Last price, best bid, and best ask are different valuation bases; the selected basis is reported explicitly.",
        "Currencies are never converted or summed together. Cross-currency portfolio shares are intentionally omitted.",
        "Blocked cash is reported separately by the source snapshot and is not added to portfolio value.",
        "Position weights use only positions with a value on the selected basis; review valuation coverage before interpreting concentration.",
        "The output describes the current snapshot and is not a recommendation to buy, sell, or rebalance.",
    ]
    if total_unvalued_positions:
        warnings.append(
            f"{total_unvalued_positions} market position(s) had no value on the selected basis."
        )
    if skipped_by_limit:
        warnings.append(
            f"{skipped_by_limit} market position(s) were skipped by the source safety limit."
        )
    if component_errors:
        warnings.append(
            f"The source snapshot reported {component_errors} market-data component error(s)."
        )
    return warnings


def build_portfolio_analytics(
    *,
    base: Any,
    app_version: str,
    snapshot: dict[str, Any],
    valuation_basis: str,
    top_n: int,
) -> dict[str, Any]:
    if valuation_basis not in SUPPORTED_VALUATION_BASES:
        raise ValueError(f"Unsupported valuation basis: {valuation_basis}")

    retrieved_at = datetime.now(timezone.utc).isoformat()
    cash_by_currency = _cash_map(base, snapshot)
    (
        records,
        valued_by_currency,
        unvalued_by_currency,
        all_positions_by_currency,
    ) = _portfolio_records_by_currency(
        base=base,
        snapshot=snapshot,
        valuation_basis=valuation_basis,
    )
    currencies = sorted(
        set(cash_by_currency)
        | set(valued_by_currency)
        | set(unvalued_by_currency)
        | set(all_positions_by_currency)
    )
    summary_by_currency: list[dict[str, Any]] = []
    allocation_by_currency: list[dict[str, Any]] = []
    concentration_by_currency: list[dict[str, Any]] = []
    currency_exposure: list[dict[str, Any]] = []
    position_weights: list[dict[str, Any]] = []
    total_valued_positions = 0
    total_unvalued_positions = 0
    nonpositive_total_currencies = 0

    for currency in currencies:
        analytics = _currency_analytics(
            base=base,
            currency=currency,
            cash_value=cash_by_currency.get(currency, Decimal("0")),
            valued_records=valued_by_currency.get(currency, []),
            market_position_count=all_positions_by_currency.get(currency, 0),
            unvalued_position_count=unvalued_by_currency.get(currency, 0),
            valuation_basis=valuation_basis,
            top_n=top_n,
        )
        summary_by_currency.append(analytics["summary"])
        allocation_by_currency.append(analytics["allocation"])
        concentration_by_currency.append(analytics["concentration"])
        currency_exposure.append(analytics["exposure"])
        position_weights.extend(analytics["weights"])
        total_valued_positions += int(analytics["valued_count"])
        total_unvalued_positions += int(analytics["unvalued_count"])
        nonpositive_total_currencies += int(bool(analytics["nonpositive"]))

    source_quality = snapshot.get("quality")
    safe_source_quality = source_quality if isinstance(source_quality, dict) else {}
    enrichment_quality = snapshot.get("enrichment_quality")
    safe_enrichment_quality = (
        enrichment_quality if isinstance(enrichment_quality, dict) else {}
    )
    component_errors = int(safe_source_quality.get("component_errors", 0) or 0)
    skipped_by_limit = int(
        safe_source_quality.get("market_instruments_skipped_by_limit", 0) or 0
    )
    identity_conflicts = int(safe_enrichment_quality.get("identity_conflicts", 0) or 0)
    complete_for_selected_basis = (
        total_unvalued_positions == 0
        and skipped_by_limit == 0
        and component_errors == 0
    )
    source_status = snapshot.get("status")
    if source_status == "error":
        status = "error"
    elif source_status == "ok" and complete_for_selected_basis:
        status = "ok"
    else:
        status = "partial"

    market_position_count = len(records)
    global_coverage = (
        "100"
        if market_position_count == 0
        else _percent_string(
            base,
            Decimal(total_valued_positions),
            Decimal(market_position_count),
        )
    )
    return base.json_safe_value(
        {
            "status": status,
            "version": app_version,
            "retrieved_at": retrieved_at,
            "source_snapshot": {
                "status": source_status,
                "version": snapshot.get("version"),
                "retrieved_at": snapshot.get("retrieved_at"),
                "source_snapshot_retrieved_at": snapshot.get(
                    "source_snapshot_retrieved_at"
                ),
                "valuation_basis": valuation_basis,
            },
            "account": snapshot.get("account"),
            "portfolio_mode": _portfolio_mode(
                cash_by_currency=cash_by_currency,
                market_positions_total=market_position_count,
            ),
            "currency_mode": _currency_mode(currencies),
            "summary_by_currency": summary_by_currency,
            "asset_class_allocation_by_currency": allocation_by_currency,
            "position_weights": position_weights,
            "currency_exposure": currency_exposure,
            "concentration_by_currency": concentration_by_currency,
            "quality": {
                "source_status": source_status,
                "currencies_detected": len(currencies),
                "market_positions_total": market_position_count,
                "valued_positions": total_valued_positions,
                "unvalued_positions": total_unvalued_positions,
                "valuation_coverage_percent": global_coverage,
                "valuation_basis": valuation_basis,
                "component_errors": component_errors,
                "market_instruments_skipped_by_limit": skipped_by_limit,
                "identity_conflicts": identity_conflicts,
                "nonpositive_portfolio_currencies": nonpositive_total_currencies,
                "complete_for_selected_basis": complete_for_selected_basis,
                "no_cross_currency_aggregation": True,
            },
            "trading_methods": False,
            "warnings": _portfolio_warnings(
                total_unvalued_positions=total_unvalued_positions,
                skipped_by_limit=skipped_by_limit,
                component_errors=component_errors,
            ),
        }
    )

