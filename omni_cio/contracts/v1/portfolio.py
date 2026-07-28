from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import (
    ContractMetadata,
    ContractModel,
    CurrencyCode,
    FiniteDecimal,
    Money,
)


NonNegativeDecimal = Annotated[
    Decimal,
    Field(ge=Decimal("0"), allow_inf_nan=False),
]


class InstrumentType(StrEnum):
    SHARE = "share"
    BOND = "bond"
    ETF = "etf"
    CURRENCY = "currency"
    FUTURE = "future"
    OPTION = "option"
    STRUCTURED_PRODUCT = "structured_product"
    OTHER = "other"


class ValuationBasis(StrEnum):
    BROKER_REPORTED = "broker_reported"
    LAST_PRICE = "last_price"
    BEST_BID = "best_bid"
    BEST_ASK = "best_ask"
    CALCULATED = "calculated"
    UNAVAILABLE = "unavailable"


class InstrumentIdentity(ContractModel):
    name: Annotated[str, Field(min_length=1, max_length=256)]
    instrument_type: InstrumentType
    currency: CurrencyCode
    lot: Annotated[int, Field(ge=1)]
    ticker: Annotated[str | None, Field(max_length=32)] = None
    isin: Annotated[
        str | None,
        Field(pattern=r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$"),
    ] = None
    figi: Annotated[str | None, Field(max_length=32)] = None
    uid: Annotated[str | None, Field(max_length=128)] = None
    position_uid: Annotated[str | None, Field(max_length=128)] = None
    class_code: Annotated[str | None, Field(max_length=32)] = None

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def require_stable_identifier(self) -> InstrumentIdentity:
        if not any((self.isin, self.figi, self.uid, self.position_uid)):
            raise ValueError("at least one stable instrument identifier is required")
        return self

    def stable_key(self) -> str:
        for prefix, value in (
            ("position_uid", self.position_uid),
            ("uid", self.uid),
            ("figi", self.figi),
            ("isin", self.isin),
        ):
            if value:
                return f"{prefix}:{value}"
        raise RuntimeError("validated instrument has no stable identifier")


class PositionValuation(ContractModel):
    basis: ValuationBasis
    currency: CurrencyCode
    as_of: datetime | None = None
    unit_price: FiniteDecimal | None = None
    market_value: Money | None = None
    accrued_interest: Money | None = None

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("as_of")
    @classmethod
    def require_aware_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_valuation(self) -> PositionValuation:
        monetary_values = (self.market_value, self.accrued_interest)
        for value in monetary_values:
            if value is not None and value.currency != self.currency:
                raise ValueError("valuation currencies must match")
        has_value = self.unit_price is not None or any(
            value is not None for value in monetary_values
        )
        if has_value and self.as_of is None:
            raise ValueError("valued positions require an as_of timestamp")
        return self


class PortfolioPositionV1(ContractModel):
    instrument: InstrumentIdentity
    quantity_units: NonNegativeDecimal
    blocked_units: NonNegativeDecimal = Decimal("0")
    quantity_lots: NonNegativeDecimal | None = None
    valuation: PositionValuation | None = None

    @model_validator(mode="after")
    def validate_quantities(self) -> PortfolioPositionV1:
        if self.blocked_units > self.quantity_units:
            raise ValueError("blocked units cannot exceed total quantity")
        if self.quantity_lots is not None:
            expected_units = self.quantity_lots * Decimal(self.instrument.lot)
            if expected_units != self.quantity_units:
                raise ValueError("quantity_lots must reconcile with lot and units")
        return self


class CashBalanceV1(ContractModel):
    reported: Money
    available: Money | None = None
    as_of: datetime
    venue: Annotated[str | None, Field(max_length=64)] = None

    @field_validator("as_of")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_currency(self) -> CashBalanceV1:
        if self.available is not None and (
            self.available.currency != self.reported.currency
        ):
            raise ValueError("cash balance currencies must match")
        return self


class CurrencyTotalsV1(ContractModel):
    currency: CurrencyCode
    cash: FiniteDecimal
    securities: FiniteDecimal
    accrued_interest: FiniteDecimal = Decimal("0")
    total: FiniteDecimal

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value


class PortfolioSnapshotV1(ContractModel):
    metadata: ContractMetadata
    positions: tuple[PortfolioPositionV1, ...] = ()
    cash_balances: tuple[CashBalanceV1, ...] = ()
    totals_by_currency: tuple[CurrencyTotalsV1, ...] = ()

    @model_validator(mode="after")
    def validate_snapshot(self) -> PortfolioSnapshotV1:
        if self.metadata.schema_name != "portfolio_snapshot":
            raise ValueError("schema_name must be portfolio_snapshot")

        keys = [position.instrument.stable_key() for position in self.positions]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate portfolio positions are not allowed")

        currencies = [row.currency for row in self.totals_by_currency]
        if len(currencies) != len(set(currencies)):
            raise ValueError("totals_by_currency must contain unique currencies")
        return self
