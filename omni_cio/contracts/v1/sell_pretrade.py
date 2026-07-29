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
from omni_cio.contracts.v1.pretrade import PreviewFreshnessStatus


PositiveDecimal = Annotated[Decimal, Field(gt=Decimal("0"), allow_inf_nan=False)]
NonNegativeDecimal = Annotated[
    Decimal,
    Field(ge=Decimal("0"), allow_inf_nan=False),
]
PositiveInt = Annotated[int, Field(gt=0)]
NonNegativeInt = Annotated[int, Field(ge=0)]
UnitInterval = Annotated[
    Decimal,
    Field(ge=Decimal("0"), le=Decimal("1"), allow_inf_nan=False),
]
_MONEY_TOLERANCE = Decimal("0.01")
_WEIGHT_TOLERANCE = Decimal("0.000000001")


class SellPreviewPriceBasis(StrEnum):
    BEST_BID = "best_bid"
    LAST_PRICE = "last_price"
    MANUAL = "manual"
    UNKNOWN = "unknown"


class SellPreTradeBlocker(StrEnum):
    PLAN_NOT_READY = "plan_not_ready"
    ACCOUNT_MISMATCH = "account_mismatch"
    TARGET_NOT_REDUCE = "target_not_reduce"
    SALE_ALTERNATIVE_NOT_AVAILABLE = "sale_alternative_not_available"
    SOURCE_INCOMPLETE = "source_incomplete"
    DIRECTION_MISMATCH = "direction_mismatch"
    INSTRUMENT_UNRESOLVED = "instrument_unresolved"
    PRICE_UNAVAILABLE = "price_unavailable"
    PRICE_STALE = "price_stale"
    PRICE_TIME_UNKNOWN = "price_time_unknown"
    PRICE_TIME_IN_FUTURE = "price_time_in_future"
    MANUAL_PRICE_NOT_ALLOWED = "manual_price_not_allowed"
    LOT_INVALID = "lot_invalid"
    POSITION_LIMITS_UNAVAILABLE = "position_limits_unavailable"
    POSITION_INSUFFICIENT = "position_insufficient"
    SHORT_SALE_FORBIDDEN = "short_sale_forbidden"
    OPEN_ORDERS_UNCHECKED = "open_orders_unchecked"
    OPEN_ORDER_CONFLICT = "open_order_conflict"
    POSITION_VALUE_MISMATCH = "position_value_mismatch"
    CURRENCY_MISMATCH = "currency_mismatch"
    COMMISSION_UNAVAILABLE = "commission_unavailable"
    TAX_BASIS_UNAVAILABLE = "tax_basis_unavailable"
    ARITHMETIC_INTEGRITY_FAILED = "arithmetic_integrity_failed"
    TARGET_REDUCTION_OVERSHOOT = "target_reduction_overshoot"
    POST_SALE_BAND_UNDERSHOOT = "post_sale_band_undershoot"


class SellPreTradePreviewV1(ContractModel):
    metadata: ContractMetadata
    stable_key: Annotated[str, Field(min_length=3, max_length=256)]
    instrument_uid: Annotated[str | None, Field(max_length=256)] = None
    currency: CurrencyCode
    price_basis: SellPreviewPriceBasis
    price_source: Annotated[str, Field(min_length=1, max_length=256)]
    price_time: datetime | None = None
    evaluated_at: datetime
    price_age_seconds: NonNegativeDecimal | None = None
    max_price_age_seconds: PositiveDecimal
    freshness_status: PreviewFreshnessStatus
    unit_price: PositiveDecimal | None = None
    lot_size: PositiveInt | None = None
    quantity_lots: PositiveInt | None = None
    quantity_units: PositiveInt | None = None
    position_lots: PositiveInt | None = None
    sell_max_lots: NonNegativeInt | None = None
    conflicting_open_sell_lots: NonNegativeInt | None = None
    available_after_open_orders_lots: NonNegativeInt | None = None
    remaining_position_lots: NonNegativeInt | None = None
    current_position_value: Money
    sold_position_value: Money | None = None
    gross_security_proceeds: Money | None = None
    accrued_interest_proceeds: Money | None = None
    gross_proceeds: Money | None = None
    canonical_commission: Money | None = None
    estimated_tax: Money | None = None
    net_proceeds: Money | None = None
    estimated_post_sale_position_value: Money | None = None
    estimated_portfolio_value_before: Money | None = None
    estimated_portfolio_value_after: Money | None = None
    current_weight: UnitInterval
    lower_weight: UnitInterval
    target_weight: UnitInterval
    upper_weight: UnitInterval
    estimated_post_sale_weight: UnitInterval | None = None
    reduction_value_limit: Money
    tax_basis_confirmed: bool
    open_orders_checked: bool
    position_availability_confirmed: bool
    source_complete: bool
    integrity_confirmed: bool
    blockers: tuple[SellPreTradeBlocker, ...]
    preview_ready: bool
    no_short_sale: Literal[True] = True
    no_cross_currency_aggregation: Literal[True] = True
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("price_time")
    @classmethod
    def require_aware_price_time(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("sell-preview timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("evaluated_at")
    @classmethod
    def require_aware_evaluated_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("sell-preview timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_preview(self) -> SellPreTradePreviewV1:
        if self.metadata.schema_name != "sell_pretrade_preview":
            raise ValueError("schema_name must be sell_pretrade_preview")
        if len(self.blockers) != len(set(self.blockers)):
            raise ValueError("sell-preview blockers must be unique")
        if not self.lower_weight <= self.target_weight <= self.upper_weight:
            raise ValueError("sell-preview target band is invalid")
        if self.current_weight <= self.upper_weight:
            if SellPreTradeBlocker.TARGET_NOT_REDUCE not in self.blockers:
                raise ValueError("non-overweight sell preview requires target blocker")
        if self.preview_ready != (not self.blockers):
            raise ValueError("sell preview readiness must match blockers")
        if self.preview_ready and (
            not self.source_complete
            or not self.integrity_confirmed
            or not self.tax_basis_confirmed
            or not self.open_orders_checked
            or not self.position_availability_confirmed
        ):
            raise ValueError("ready sell preview requires every source confirmation")
        if self.preview_ready and self.freshness_status != PreviewFreshnessStatus.FRESH:
            raise ValueError("ready sell preview requires a fresh price")
        if self.preview_ready and any(
            value is None
            for value in (
                self.instrument_uid,
                self.price_time,
                self.price_age_seconds,
                self.unit_price,
                self.lot_size,
                self.quantity_lots,
                self.quantity_units,
                self.position_lots,
                self.sell_max_lots,
                self.conflicting_open_sell_lots,
                self.available_after_open_orders_lots,
                self.remaining_position_lots,
                self.sold_position_value,
                self.gross_security_proceeds,
                self.gross_proceeds,
                self.canonical_commission,
                self.estimated_tax,
                self.net_proceeds,
                self.estimated_post_sale_position_value,
                self.estimated_portfolio_value_before,
                self.estimated_portfolio_value_after,
                self.estimated_post_sale_weight,
            )
        ):
            raise ValueError("ready sell preview requires every critical field")

        if self.price_time is None:
            if self.price_age_seconds is not None:
                raise ValueError("sell price age requires price time")
            if self.freshness_status == PreviewFreshnessStatus.FRESH:
                raise ValueError("fresh sell price requires price time")
        else:
            expected_age = Decimal(
                str((self.evaluated_at - self.price_time).total_seconds())
            )
            if expected_age < 0:
                if SellPreTradeBlocker.PRICE_TIME_IN_FUTURE not in self.blockers:
                    raise ValueError("future sell price requires blocker")
            elif self.price_age_seconds is None:
                raise ValueError("sell price time requires age")
            elif abs(self.price_age_seconds - expected_age) > Decimal("0.001"):
                raise ValueError("sell price age does not reconcile")

        if self.freshness_status == PreviewFreshnessStatus.FRESH:
            if (
                self.price_age_seconds is None
                or self.price_age_seconds > self.max_price_age_seconds
            ):
                raise ValueError("fresh sell price exceeds threshold")
        elif self.freshness_status == PreviewFreshnessStatus.STALE:
            if (
                self.price_age_seconds is None
                or self.price_age_seconds <= self.max_price_age_seconds
            ):
                raise ValueError("stale sell price must exceed threshold")

        money_values = (
            self.current_position_value,
            self.sold_position_value,
            self.gross_security_proceeds,
            self.accrued_interest_proceeds,
            self.gross_proceeds,
            self.canonical_commission,
            self.estimated_tax,
            self.net_proceeds,
            self.estimated_post_sale_position_value,
            self.estimated_portfolio_value_before,
            self.estimated_portfolio_value_after,
            self.reduction_value_limit,
        )
        currency_mismatch = any(
            money is not None and money.currency != self.currency
            for money in money_values
        )
        if (
            currency_mismatch
            and SellPreTradeBlocker.CURRENCY_MISMATCH not in self.blockers
        ):
            raise ValueError("sell-preview currency mismatch requires blocker")

        if self.lot_size is not None and self.quantity_lots is not None:
            expected_units = self.lot_size * self.quantity_lots
            if self.quantity_units != expected_units:
                raise ValueError("sell-preview quantity units do not reconcile")

        if (
            self.position_lots is not None
            and self.conflicting_open_sell_lots is not None
        ):
            expected_available = max(
                0,
                self.position_lots - self.conflicting_open_sell_lots,
            )
            if self.available_after_open_orders_lots != expected_available:
                raise ValueError("sell-preview open-order availability does not reconcile")

        if self.position_lots is not None and self.quantity_lots is not None:
            if self.quantity_lots > self.position_lots:
                if SellPreTradeBlocker.SHORT_SALE_FORBIDDEN not in self.blockers:
                    raise ValueError("sell-preview oversell requires short-sale blocker")
                if self.remaining_position_lots is not None:
                    raise ValueError("oversell cannot contain remaining position lots")
            elif self.remaining_position_lots != self.position_lots - self.quantity_lots:
                raise ValueError("remaining sell-preview lots do not reconcile")

        if (
            self.position_lots is not None
            and self.quantity_lots is not None
            and self.sold_position_value is not None
            and self.estimated_post_sale_position_value is not None
            and not currency_mismatch
        ):
            expected_sold_value = (
                self.current_position_value.amount
                * Decimal(self.quantity_lots)
                / Decimal(self.position_lots)
            )
            if (
                abs(self.sold_position_value.amount - expected_sold_value)
                > _MONEY_TOLERANCE
            ):
                raise ValueError("sold position value does not reconcile")
            expected_remaining_value = (
                self.current_position_value.amount - expected_sold_value
            )
            if (
                abs(
                    self.estimated_post_sale_position_value.amount
                    - expected_remaining_value
                )
                > _MONEY_TOLERANCE
            ):
                raise ValueError("post-sale position value does not reconcile")

        if (
            self.gross_security_proceeds is not None
            and self.gross_proceeds is not None
            and not currency_mismatch
        ):
            expected_gross = self.gross_security_proceeds.amount + (
                self.accrued_interest_proceeds.amount
                if self.accrued_interest_proceeds is not None
                else Decimal("0")
            )
            if abs(self.gross_proceeds.amount - expected_gross) > _MONEY_TOLERANCE:
                if SellPreTradeBlocker.ARITHMETIC_INTEGRITY_FAILED not in self.blockers:
                    raise ValueError("gross sell proceeds mismatch requires blocker")

        if (
            self.gross_proceeds is not None
            and self.canonical_commission is not None
            and self.estimated_tax is not None
            and self.net_proceeds is not None
            and not currency_mismatch
        ):
            expected_net = (
                self.gross_proceeds.amount
                - self.canonical_commission.amount
                - self.estimated_tax.amount
            )
            if abs(self.net_proceeds.amount - expected_net) > _MONEY_TOLERANCE:
                if SellPreTradeBlocker.ARITHMETIC_INTEGRITY_FAILED not in self.blockers:
                    raise ValueError("net sell proceeds mismatch requires blocker")

        if self.current_weight > 0 and self.estimated_portfolio_value_before is not None:
            expected_before = self.current_position_value.amount / self.current_weight
            if (
                abs(self.estimated_portfolio_value_before.amount - expected_before)
                > _MONEY_TOLERANCE
            ):
                raise ValueError("portfolio value before sale does not reconcile")

        if (
            self.estimated_portfolio_value_before is not None
            and self.sold_position_value is not None
            and self.net_proceeds is not None
            and self.estimated_portfolio_value_after is not None
            and not currency_mismatch
        ):
            expected_after = (
                self.estimated_portfolio_value_before.amount
                - self.sold_position_value.amount
                + self.net_proceeds.amount
            )
            if (
                abs(self.estimated_portfolio_value_after.amount - expected_after)
                > _MONEY_TOLERANCE
            ):
                raise ValueError("portfolio value after sale does not reconcile")

        if (
            self.estimated_post_sale_position_value is not None
            and self.estimated_portfolio_value_after is not None
            and self.estimated_post_sale_weight is not None
            and self.estimated_portfolio_value_after.amount > 0
        ):
            expected_weight = (
                self.estimated_post_sale_position_value.amount
                / self.estimated_portfolio_value_after.amount
            )
            if (
                abs(self.estimated_post_sale_weight - expected_weight)
                > _WEIGHT_TOLERANCE
            ):
                raise ValueError("post-sale weight does not reconcile")

        if (
            self.sold_position_value is not None
            and self.sold_position_value.currency == self.reduction_value_limit.currency
            and self.sold_position_value.amount
            > self.reduction_value_limit.amount + _MONEY_TOLERANCE
            and SellPreTradeBlocker.TARGET_REDUCTION_OVERSHOOT not in self.blockers
        ):
            raise ValueError("sell reduction overshoot requires blocker")
        if (
            self.estimated_post_sale_weight is not None
            and self.estimated_post_sale_weight + _WEIGHT_TOLERANCE < self.lower_weight
            and SellPreTradeBlocker.POST_SALE_BAND_UNDERSHOOT not in self.blockers
        ):
            raise ValueError("post-sale band undershoot requires blocker")
        return self
