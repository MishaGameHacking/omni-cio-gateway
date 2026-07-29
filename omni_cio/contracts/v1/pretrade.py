from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import (
    ContractMetadata,
    ContractModel,
    CurrencyCode,
    Money,
)


PositiveDecimal = Annotated[Decimal, Field(gt=Decimal("0"), allow_inf_nan=False)]
NonNegativeDecimal = Annotated[
    Decimal,
    Field(ge=Decimal("0"), allow_inf_nan=False),
]
PositiveInt = Annotated[int, Field(gt=0)]
_MONEY_TOLERANCE = Decimal("0.01")


class PreviewPriceBasis(StrEnum):
    BEST_ASK = "best_ask"
    LAST_PRICE = "last_price"
    MANUAL = "manual"
    UNKNOWN = "unknown"


class PreviewFreshnessStatus(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"
    MANUAL_INPUT = "manual_input"


class PreTradeBlocker(StrEnum):
    PLAN_NOT_READY = "plan_not_ready"
    ACCOUNT_MISMATCH = "account_mismatch"
    CASH_FIRST_NOT_AVAILABLE = "cash_first_not_available"
    TARGET_NOT_ADD = "target_not_add"
    TARGET_BAND_OVERSHOOT = "target_band_overshoot"
    SOURCE_INCOMPLETE = "source_incomplete"
    INSTRUMENT_UNRESOLVED = "instrument_unresolved"
    PRICE_UNAVAILABLE = "price_unavailable"
    PRICE_STALE = "price_stale"
    PRICE_TIME_UNKNOWN = "price_time_unknown"
    PRICE_TIME_IN_FUTURE = "price_time_in_future"
    MANUAL_PRICE_NOT_ALLOWED = "manual_price_not_allowed"
    LOT_INVALID = "lot_invalid"
    CURRENCY_MISMATCH = "currency_mismatch"
    AFFORDABILITY_UNCONFIRMED = "affordability_unconfirmed"
    INSUFFICIENT_FUNDS = "insufficient_funds"
    COMMISSION_UNAVAILABLE = "commission_unavailable"
    ARITHMETIC_INTEGRITY_FAILED = "arithmetic_integrity_failed"


class PreTradePreviewV1(ContractModel):
    metadata: ContractMetadata
    stable_key: Annotated[str, Field(min_length=3, max_length=256)]
    instrument_uid: Annotated[str | None, Field(max_length=256)] = None
    currency: CurrencyCode
    price_basis: PreviewPriceBasis
    price_source: Annotated[str, Field(min_length=1, max_length=256)]
    price_time: datetime | None = None
    evaluated_at: datetime
    price_age_seconds: NonNegativeDecimal | None = None
    max_price_age_seconds: PositiveDecimal
    freshness_status: PreviewFreshnessStatus
    unit_price: PositiveDecimal | None = None
    lot_size: PositiveInt | None = None
    quantity_lots: PositiveInt | None = None
    initial_order_amount: Money | None = None
    canonical_commission: Money | None = None
    accrued_interest: Money | None = None
    total_order_amount: Money | None = None
    own_funds: Money | None = None
    remaining_cash: Money | None = None
    target_value_limit: Money
    affordable: bool
    source_complete: bool
    integrity_confirmed: bool
    blockers: tuple[PreTradeBlocker, ...]
    preview_ready: bool
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("price_time", "evaluated_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("pre-trade timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_preview(self) -> PreTradePreviewV1:
        if self.metadata.schema_name != "pretrade_preview":
            raise ValueError("schema_name must be pretrade_preview")
        if len(self.blockers) != len(set(self.blockers)):
            raise ValueError("pre-trade blockers must be unique")
        if self.preview_ready != (not self.blockers):
            raise ValueError("preview_ready must match blockers")
        if self.preview_ready and (
            not self.source_complete
            or not self.integrity_confirmed
            or not self.affordable
        ):
            raise ValueError("ready preview requires complete, affordable source data")
        if self.preview_ready and self.freshness_status != PreviewFreshnessStatus.FRESH:
            raise ValueError("ready preview requires a fresh market price")
        if self.preview_ready and any(
            value is None
            for value in (
                self.instrument_uid,
                self.price_time,
                self.price_age_seconds,
                self.unit_price,
                self.lot_size,
                self.quantity_lots,
                self.initial_order_amount,
                self.canonical_commission,
                self.total_order_amount,
                self.own_funds,
                self.remaining_cash,
            )
        ):
            raise ValueError("ready preview requires every critical field")

        if self.price_time is None:
            if self.price_age_seconds is not None:
                raise ValueError("price age requires price_time")
            if self.freshness_status == PreviewFreshnessStatus.FRESH:
                raise ValueError("fresh status requires price_time")
        else:
            expected_age = Decimal(
                str((self.evaluated_at - self.price_time).total_seconds())
            )
            if expected_age < 0:
                if PreTradeBlocker.PRICE_TIME_IN_FUTURE not in self.blockers:
                    raise ValueError("future price time requires blocker")
            elif self.price_age_seconds is None:
                raise ValueError("price_time requires price_age_seconds")
            elif abs(self.price_age_seconds - expected_age) > Decimal("0.001"):
                raise ValueError("price_age_seconds does not reconcile")

        if self.freshness_status == PreviewFreshnessStatus.FRESH:
            if (
                self.price_age_seconds is None
                or self.price_age_seconds > self.max_price_age_seconds
            ):
                raise ValueError("fresh price exceeds freshness threshold")
        elif self.freshness_status == PreviewFreshnessStatus.STALE:
            if (
                self.price_age_seconds is None
                or self.price_age_seconds <= self.max_price_age_seconds
            ):
                raise ValueError("stale price must exceed freshness threshold")

        money_values = (
            self.initial_order_amount,
            self.canonical_commission,
            self.accrued_interest,
            self.total_order_amount,
            self.own_funds,
            self.remaining_cash,
            self.target_value_limit,
        )
        if any(
            money is not None and money.currency != self.currency
            for money in money_values
        ):
            raise ValueError("all pre-trade monetary values must use one currency")

        if (
            self.initial_order_amount is not None
            and self.canonical_commission is not None
            and self.total_order_amount is not None
        ):
            expected_total = (
                self.initial_order_amount.amount
                + self.canonical_commission.amount
                + (
                    self.accrued_interest.amount
                    if self.accrued_interest is not None
                    else Decimal("0")
                )
            )
            if abs(self.total_order_amount.amount - expected_total) > _MONEY_TOLERANCE:
                raise ValueError("total order amount does not reconcile")

        if (
            self.own_funds is not None
            and self.total_order_amount is not None
            and self.remaining_cash is not None
        ):
            expected_remaining = self.own_funds.amount - self.total_order_amount.amount
            if abs(self.remaining_cash.amount - expected_remaining) > _MONEY_TOLERANCE:
                raise ValueError("remaining cash does not reconcile")

        if (
            self.total_order_amount is not None
            and self.total_order_amount.amount
            > self.target_value_limit.amount + _MONEY_TOLERANCE
            and PreTradeBlocker.TARGET_BAND_OVERSHOOT not in self.blockers
        ):
            raise ValueError("target-band overshoot requires blocker")
        return self
