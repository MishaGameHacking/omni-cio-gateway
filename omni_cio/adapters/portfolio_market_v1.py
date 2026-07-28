from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from omni_cio.contracts.v1 import (
    AccountReference,
    CashBalanceV1,
    Completeness,
    ContractMetadata,
    CurrencyTotalsV1,
    DataIssue,
    DataQuality,
    InstrumentIdentity,
    InstrumentType,
    IssueSeverity,
    Money,
    PortfolioPositionV1,
    PortfolioSnapshotV1,
    PositionValuation,
    QualityMetadata,
    SourceReference,
    ValuationBasis,
)


class PortfolioMarketAdapterError(ValueError):
    """Legacy portfolio-market payload cannot safely satisfy contract v1."""


_TYPE_MAP = {
    "INSTRUMENT_TYPE_SHARE": InstrumentType.SHARE,
    "SHARE": InstrumentType.SHARE,
    "STOCK": InstrumentType.SHARE,
    "INSTRUMENT_TYPE_BOND": InstrumentType.BOND,
    "BOND": InstrumentType.BOND,
    "INSTRUMENT_TYPE_ETF": InstrumentType.ETF,
    "ETF": InstrumentType.ETF,
    "INSTRUMENT_TYPE_CURRENCY": InstrumentType.CURRENCY,
    "CURRENCY": InstrumentType.CURRENCY,
    "INSTRUMENT_TYPE_FUTURES": InstrumentType.FUTURE,
    "FUTURE": InstrumentType.FUTURE,
    "FUTURES": InstrumentType.FUTURE,
    "INSTRUMENT_TYPE_OPTION": InstrumentType.OPTION,
    "OPTION": InstrumentType.OPTION,
    "INSTRUMENT_TYPE_SP": InstrumentType.STRUCTURED_PRODUCT,
    "SP": InstrumentType.STRUCTURED_PRODUCT,
    "STRUCTURED_PRODUCT": InstrumentType.STRUCTURED_PRODUCT,
}


def _obj(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PortfolioMarketAdapterError(f"{field} must be an object")
    return value


def _rows(value: object, field: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise PortfolioMarketAdapterError(f"{field} must be an array")
    return value


def _text(value: object, field: str, *, optional: bool = False) -> str | None:
    text = "" if value is None else str(value).strip()
    if not text:
        if optional:
            return None
        raise PortfolioMarketAdapterError(f"{field} is required")
    return text


def _decimal(value: object, field: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise PortfolioMarketAdapterError(f"{field} must be a finite decimal")
    if isinstance(value, Mapping):
        if "amount" in value:
            return _decimal(value["amount"], field)
        if "units" in value or "nano" in value:
            return _decimal(value.get("units", 0), field) + _decimal(
                value.get("nano", 0), field
            ) / Decimal("1000000000")
    try:
        number = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise PortfolioMarketAdapterError(f"{field} must be a decimal") from exc
    if not number.is_finite():
        raise PortfolioMarketAdapterError(f"{field} must be finite")
    return number


def _time(value: object, field: str) -> datetime:
    if isinstance(value, datetime):
        result = value
    else:
        text = _text(value, field)
        assert text is not None
        try:
            result = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise PortfolioMarketAdapterError(f"{field} must be ISO-8601") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise PortfolioMarketAdapterError(f"{field} must be timezone-aware")
    return result.astimezone(timezone.utc)


def _currency(value: object, field: str) -> str:
    text = _text(value, field)
    assert text is not None
    result = text.upper()
    if len(result) != 3 or not result.isalpha():
        raise PortfolioMarketAdapterError(f"{field} must be a three-letter currency")
    return result


def _count(quality: Mapping[str, Any], field: str) -> int:
    try:
        result = int(quality.get(field, 0) or 0)
    except (TypeError, ValueError) as exc:
        raise PortfolioMarketAdapterError(f"quality.{field} must be an integer") from exc
    if result < 0:
        raise PortfolioMarketAdapterError(f"quality.{field} cannot be negative")
    return result


def _issues(payload: Mapping[str, Any]) -> tuple[DataIssue, ...]:
    quality = _obj(payload.get("quality", {}), "quality")
    definitions = (
        ("missing_uid_positions", "MISSING_INSTRUMENT_IDENTITY", "portfolio_grouping"),
        (
            "market_instruments_skipped_by_limit",
            "MARKET_INSTRUMENT_LIMIT",
            "portfolio_market",
        ),
        (
            "positions_without_valuation",
            "POSITIONS_WITHOUT_VALUATION",
            "portfolio_valuation",
        ),
        ("component_errors", "MARKET_COMPONENT_ERRORS", "portfolio_market"),
    )
    result = []
    for field, code, component in definitions:
        count = _count(quality, field)
        if count:
            result.append(
                DataIssue(
                    code=code,
                    severity=IssueSeverity.WARNING,
                    message=f"Source quality counter {field} is {count}.",
                    component=component,
                )
            )
    duplicates = _count(quality, "duplicate_uid_occurrences")
    if duplicates:
        result.append(
            DataIssue(
                code="DUPLICATE_UIDS_COLLAPSED",
                severity=IssueSeverity.INFO,
                message=f"Duplicate UID occurrences collapsed: {duplicates}.",
                component="portfolio_grouping",
            )
        )
    return tuple(result)


def _instrument(
    raw: Mapping[str, Any], position: Mapping[str, Any]
) -> InstrumentIdentity:
    kind = str(raw.get("instrument_kind") or raw.get("instrument_type") or "").upper()
    position_uids = position.get("position_uids", ())
    position_uid = None
    if isinstance(position_uids, Sequence) and not isinstance(
        position_uids, (str, bytes)
    ):
        position_uid = next(
            (str(item).strip() for item in position_uids if str(item).strip()),
            None,
        )
    position_uid = str(raw.get("position_uid") or position_uid or "").strip() or None
    lot_value = _decimal(raw.get("lot", 1), "portfolio_positions.instrument.lot")
    if lot_value != lot_value.to_integral_value() or lot_value < 1:
        raise PortfolioMarketAdapterError(
            "portfolio_positions.instrument.lot must be a positive integer"
        )
    return InstrumentIdentity(
        name=_text(raw.get("name"), "portfolio_positions.instrument.name") or "",
        instrument_type=_TYPE_MAP.get(kind, InstrumentType.OTHER),
        currency=_currency(
            raw.get("currency"), "portfolio_positions.instrument.currency"
        ),
        lot=int(lot_value),
        ticker=_text(raw.get("ticker"), "ticker", optional=True),
        isin=_text(raw.get("isin"), "isin", optional=True),
        figi=_text(raw.get("figi"), "figi", optional=True),
        uid=_text(raw.get("uid"), "uid", optional=True),
        position_uid=position_uid,
        class_code=_text(raw.get("class_code"), "class_code", optional=True),
    )


def _valuation(
    position: Mapping[str, Any],
    instrument: InstrumentIdentity,
    retrieved_at: datetime,
) -> PositionValuation | None:
    valuation = _obj(position.get("valuation", {}), "portfolio_positions.valuation")
    values = _obj(
        valuation.get("values", {}), "portfolio_positions.valuation.values"
    )
    full_value_raw = values.get("last_price")
    if full_value_raw in (None, ""):
        return None
    full_value = _decimal(
        full_value_raw, "portfolio_positions.valuation.values.last_price"
    )
    clean_values = _obj(
        valuation.get("clean_values", {}),
        "portfolio_positions.valuation.clean_values",
    )
    clean_value = (
        _decimal(
            clean_values["last_price"],
            "portfolio_positions.valuation.clean_values.last_price",
        )
        if clean_values.get("last_price") not in (None, "")
        else full_value
    )
    accrued = full_value - clean_value
    if accrued < 0:
        raise PortfolioMarketAdapterError("bond accrued interest cannot be negative")
    last_price = _obj(
        position.get("last_price", {}), "portfolio_positions.last_price"
    )
    as_of = (
        _time(last_price.get("time"), "portfolio_positions.last_price.time")
        if last_price.get("time")
        else retrieved_at
    )
    unit_price = (
        _decimal(last_price["price"], "portfolio_positions.last_price.price")
        if last_price.get("price") not in (None, "")
        else None
    )
    currency = instrument.currency
    return PositionValuation(
        basis=ValuationBasis.LAST_PRICE,
        currency=currency,
        as_of=as_of,
        unit_price=unit_price,
        market_value=Money(amount=clean_value, currency=currency),
        accrued_interest=(
            Money(amount=accrued, currency=currency) if accrued else None
        ),
    )


def _positions(
    payload: Mapping[str, Any], retrieved_at: datetime
) -> tuple[PortfolioPositionV1, ...]:
    result = []
    for index, item in enumerate(
        _rows(payload.get("portfolio_positions", ()), "portfolio_positions")
    ):
        position = _obj(item, f"portfolio_positions[{index}]")
        raw_instrument = _obj(
            position.get("instrument"), f"portfolio_positions[{index}].instrument"
        )
        instrument = _instrument(raw_instrument, position)
        quantity = _decimal(
            position.get("quantity_units"),
            f"portfolio_positions[{index}].quantity_units",
        )
        if quantity < 0:
            raise PortfolioMarketAdapterError("position quantity cannot be negative")
        result.append(
            PortfolioPositionV1(
                instrument=instrument,
                quantity_units=quantity,
                quantity_lots=quantity / Decimal(instrument.lot),
                valuation=_valuation(position, instrument, retrieved_at),
            )
        )
    return tuple(result)


def _cash(
    payload: Mapping[str, Any], retrieved_at: datetime
) -> tuple[CashBalanceV1, ...]:
    result = []
    for index, item in enumerate(
        _rows(payload.get("cash_balances", ()), "cash_balances")
    ):
        row = _obj(item, f"cash_balances[{index}]")
        currency = _currency(
            row.get("currency"), f"cash_balances[{index}].currency"
        )
        result.append(
            CashBalanceV1(
                reported=Money(
                    amount=_decimal(row.get("reported_money"), "reported_money"),
                    currency=currency,
                ),
                blocked=Money(
                    amount=_decimal(row.get("reported_blocked", 0), "reported_blocked"),
                    currency=currency,
                ),
                as_of=retrieved_at,
            )
        )
    return tuple(result)


def _totals(
    payload: Mapping[str, Any],
    positions: tuple[PortfolioPositionV1, ...],
) -> tuple[CurrencyTotalsV1, ...]:
    accrued_by_currency: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    valued_by_currency: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for position in positions:
        valuation = position.valuation
        if valuation and valuation.market_value:
            valued_by_currency[valuation.currency] += valuation.market_value.amount
            if valuation.accrued_interest:
                accrued_by_currency[valuation.currency] += (
                    valuation.accrued_interest.amount
                )

    result = []
    source_quality = _obj(payload.get("quality", {}), "quality")
    require_full_reconciliation = (
        str(payload.get("status", "")).lower() == "ok"
        and _count(source_quality, "positions_without_valuation") == 0
        and _count(source_quality, "market_instruments_skipped_by_limit") == 0
        and _count(source_quality, "missing_uid_positions") == 0
    )
    for index, item in enumerate(
        _rows(payload.get("totals_by_currency", ()), "totals_by_currency")
    ):
        row = _obj(item, f"totals_by_currency[{index}]")
        currency = _currency(
            row.get("currency"), f"totals_by_currency[{index}].currency"
        )
        cash = _decimal(row.get("cash_reported"), "cash_reported")
        securities_full = _decimal(
            row.get("securities_last_price"), "securities_last_price"
        )
        total = _decimal(row.get("portfolio_last_price"), "portfolio_last_price")
        if total != cash + securities_full:
            raise PortfolioMarketAdapterError(
                "portfolio total does not reconcile with cash and securities"
            )
        accrued = accrued_by_currency[currency]
        securities = securities_full - accrued
        if securities < 0:
            raise PortfolioMarketAdapterError(
                "accrued interest exceeds securities value"
            )
        if (
            require_full_reconciliation
            and valued_by_currency[currency] + accrued != securities_full
        ):
            raise PortfolioMarketAdapterError(
                "position valuations do not reconcile with currency totals"
            )
        result.append(
            CurrencyTotalsV1(
                currency=currency,
                cash=cash,
                securities=securities,
                accrued_interest=accrued,
                total=total,
            )
        )
    return tuple(result)


def portfolio_snapshot_v1_from_market_payload(
    payload: Mapping[str, Any],
) -> PortfolioSnapshotV1:
    """Validate and map the current read-only market snapshot into contract v1."""
    if payload.get("trading_methods") is not False:
        raise PortfolioMarketAdapterError("trading_methods must be explicitly false")
    retrieved_at = _time(payload.get("retrieved_at"), "retrieved_at")
    account = _obj(payload.get("account"), "account")
    issues = _issues(payload)
    source_status = str(payload.get("status", "")).lower()
    complete = source_status == "ok" and not any(
        issue.severity in (IssueSeverity.WARNING, IssueSeverity.ERROR)
        for issue in issues
    )
    quality = DataQuality.VERIFIED if complete else DataQuality.PARTIAL
    completeness = Completeness.COMPLETE if complete else Completeness.PARTIAL
    positions = _positions(payload, retrieved_at)
    warnings = tuple(
        str(item)[:512]
        for item in payload.get("warnings", ())
        if str(item).strip()
    )
    metadata = ContractMetadata(
        schema_name="portfolio_snapshot",
        retrieved_at=retrieved_at,
        account=AccountReference(
            masked_id=_text(account.get("masked_id"), "account.masked_id") or "",
            account_type=_text(
                account.get("name") or account.get("account_type"),
                "account.account_type",
                optional=True,
            ),
        ),
        provenance=(
            SourceReference(
                provider="t-invest",
                operation="get_enriched_portfolio_snapshot",
                retrieved_at=_time(
                    payload.get("source_snapshot_retrieved_at")
                    or payload.get("retrieved_at"),
                    "source_snapshot_retrieved_at",
                ),
            ),
            SourceReference(
                provider="t-invest",
                operation="get_portfolio_market_snapshot",
                retrieved_at=retrieved_at,
                source_id=_text(payload.get("version"), "version", optional=True),
            ),
        ),
        quality=QualityMetadata(
            quality=quality,
            completeness=completeness,
            issues=issues,
            warnings=warnings,
        ),
    )
    return PortfolioSnapshotV1(
        metadata=metadata,
        positions=positions,
        cash_balances=_cash(payload, retrieved_at),
        totals_by_currency=_totals(payload, positions),
    )
