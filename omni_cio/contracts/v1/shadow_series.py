from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import (
    ContractMetadata,
    ContractModel,
    CurrencyCode,
    FiniteDecimal,
    Money,
)
from omni_cio.contracts.v1.paper import PaperOrderStatus
from omni_cio.contracts.v1.shadow import ShadowOutcome


NonNegativeDecimal = Annotated[
    Decimal,
    Field(ge=Decimal("0"), allow_inf_nan=False),
]
UnitInterval = Annotated[
    Decimal,
    Field(ge=Decimal("0"), le=Decimal("1"), allow_inf_nan=False),
]
PositiveInt = Annotated[int, Field(ge=1)]
NonNegativeInt = Annotated[int, Field(ge=0)]


class ShadowSeriesPointV1(ContractModel):
    sequence: PositiveInt
    observed_at: datetime
    holding_seconds: NonNegativeDecimal
    currency: CurrencyCode
    full_market_value: Money
    gross_value_change: Money
    net_value_change_after_entry_costs: Money
    return_on_total_cost: FiniteDecimal
    running_peak_market_value: Money
    drawdown_amount: Money
    drawdown_ratio: UnitInterval
    outcome: ShadowOutcome
    observation_source: Annotated[str, Field(min_length=1, max_length=256)]
    observation_source_id: Annotated[str | None, Field(max_length=256)] = None
    no_lookahead: Literal[True] = True
    paper_only: Literal[True] = True
    trading_methods: Literal[False] = False

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("observed_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("shadow series timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_point(self) -> ShadowSeriesPointV1:
        money_values = (
            self.full_market_value,
            self.gross_value_change,
            self.net_value_change_after_entry_costs,
            self.running_peak_market_value,
            self.drawdown_amount,
        )
        if any(money.currency != self.currency for money in money_values):
            raise ValueError("shadow series point money must use one currency")
        if self.full_market_value.amount < 0:
            raise ValueError("shadow series market value cannot be negative")
        if self.running_peak_market_value.amount < self.full_market_value.amount:
            raise ValueError("running peak cannot be below current market value")
        expected_drawdown = (
            self.running_peak_market_value.amount - self.full_market_value.amount
        )
        if self.drawdown_amount.amount != expected_drawdown:
            raise ValueError("shadow series drawdown amount does not reconcile")
        expected_ratio = (
            expected_drawdown / self.running_peak_market_value.amount
            if self.running_peak_market_value.amount > 0
            else Decimal("0")
        )
        if self.drawdown_ratio != expected_ratio:
            raise ValueError("shadow series drawdown ratio does not reconcile")
        net_change = self.net_value_change_after_entry_costs.amount
        expected_outcome = (
            ShadowOutcome.PROFIT
            if net_change > 0
            else ShadowOutcome.LOSS
            if net_change < 0
            else ShadowOutcome.FLAT
        )
        if self.outcome != expected_outcome:
            raise ValueError("shadow series point outcome does not reconcile")
        return self


class ShadowPurchaseSeriesV1(ContractModel):
    metadata: ContractMetadata
    scenario_id: Annotated[
        str,
        Field(pattern=r"^[a-z0-9][a-z0-9_.:-]{2,255}$"),
    ]
    stable_key: Annotated[str, Field(min_length=3, max_length=256)]
    instrument_uid: Annotated[str | None, Field(max_length=256)] = None
    currency: CurrencyCode
    paper_status: PaperOrderStatus
    evaluated_from: datetime
    first_observed_at: datetime
    last_observed_at: datetime
    total_holding_seconds: NonNegativeDecimal
    observation_count: PositiveInt
    filled_lots: NonNegativeInt
    filled_units: NonNegativeInt
    entry_security_value: Money
    entry_commission: Money
    entry_total_cost: Money
    points: Annotated[tuple[ShadowSeriesPointV1, ...], Field(min_length=1, max_length=256)]
    peak_market_value: Money
    max_drawdown_amount: Money
    max_drawdown_ratio: UnitInterval
    final_market_value: Money
    final_net_value_change_after_entry_costs: Money
    final_return_on_total_cost: FiniteDecimal
    final_outcome: ShadowOutcome
    no_lookahead: Literal[True] = True
    observations_strictly_ordered: Literal[True] = True
    no_cross_currency_aggregation: Literal[True] = True
    paper_only: Literal[True] = True
    broker_order_created: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("evaluated_from", "first_observed_at", "last_observed_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("shadow series timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_series(self) -> ShadowPurchaseSeriesV1:
        if self.metadata.schema_name != "shadow_purchase_series":
            raise ValueError("schema_name must be shadow_purchase_series")
        if self.paper_status == PaperOrderStatus.REJECTED:
            raise ValueError("rejected paper result cannot form a shadow series")
        if self.observation_count != len(self.points):
            raise ValueError("shadow observation count does not reconcile")
        if self.first_observed_at != self.points[0].observed_at:
            raise ValueError("first observation timestamp does not reconcile")
        if self.last_observed_at != self.points[-1].observed_at:
            raise ValueError("last observation timestamp does not reconcile")
        if self.first_observed_at <= self.evaluated_from:
            raise ValueError("shadow series must begin after the paper result")
        expected_holding = Decimal(
            str((self.last_observed_at - self.evaluated_from).total_seconds())
        )
        if self.total_holding_seconds != expected_holding:
            raise ValueError("shadow series holding period does not reconcile")

        expected_sequences = list(range(1, len(self.points) + 1))
        if [point.sequence for point in self.points] != expected_sequences:
            raise ValueError("shadow series sequences must be contiguous")
        timestamps = [point.observed_at for point in self.points]
        if any(current >= following for current, following in zip(timestamps, timestamps[1:])):
            raise ValueError("shadow observations must be strictly ordered")
        if any(point.holding_seconds <= 0 for point in self.points):
            raise ValueError("every shadow point must be forward-looking")

        money_values = (
            self.entry_security_value,
            self.entry_commission,
            self.entry_total_cost,
            self.peak_market_value,
            self.max_drawdown_amount,
            self.final_market_value,
            self.final_net_value_change_after_entry_costs,
        )
        if any(money.currency != self.currency for money in money_values):
            raise ValueError("shadow series money must use one currency")
        if any(point.currency != self.currency for point in self.points):
            raise ValueError("shadow series points must use one currency")
        if self.entry_total_cost.amount != (
            self.entry_security_value.amount + self.entry_commission.amount
        ):
            raise ValueError("shadow series entry total cost does not reconcile")

        expected_peak = max(point.full_market_value.amount for point in self.points)
        if self.peak_market_value.amount != expected_peak:
            raise ValueError("shadow series peak market value does not reconcile")
        expected_max_drawdown = max(point.drawdown_amount.amount for point in self.points)
        if self.max_drawdown_amount.amount != expected_max_drawdown:
            raise ValueError("shadow series maximum drawdown amount does not reconcile")
        expected_max_ratio = max(point.drawdown_ratio for point in self.points)
        if self.max_drawdown_ratio != expected_max_ratio:
            raise ValueError("shadow series maximum drawdown ratio does not reconcile")

        final_point = self.points[-1]
        if self.final_market_value != final_point.full_market_value:
            raise ValueError("shadow series final market value does not reconcile")
        if (
            self.final_net_value_change_after_entry_costs
            != final_point.net_value_change_after_entry_costs
        ):
            raise ValueError("shadow series final net change does not reconcile")
        if self.final_return_on_total_cost != final_point.return_on_total_cost:
            raise ValueError("shadow series final return does not reconcile")
        if self.final_outcome != final_point.outcome:
            raise ValueError("shadow series final outcome does not reconcile")
        return self
