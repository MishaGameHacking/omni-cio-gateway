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
from omni_cio.contracts.v1.paper import PaperOrderStatus


NonNegativeDecimal = Annotated[
    Decimal,
    Field(ge=Decimal("0"), allow_inf_nan=False),
]
FiniteDecimal = Annotated[Decimal, Field(allow_inf_nan=False)]
NonNegativeInt = Annotated[int, Field(ge=0)]


class ShadowOutcome(StrEnum):
    PROFIT = "profit"
    LOSS = "loss"
    FLAT = "flat"


class ShadowMarketObservationV1(ContractModel):
    stable_key: Annotated[str, Field(min_length=3, max_length=256)]
    currency: CurrencyCode
    observed_at: datetime
    full_market_value: Money
    source: Annotated[str, Field(min_length=1, max_length=256)]
    source_id: Annotated[str | None, Field(max_length=256)] = None

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("observed_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("shadow observation timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_observation(self) -> ShadowMarketObservationV1:
        if self.full_market_value.currency != self.currency:
            raise ValueError("shadow observation currency does not reconcile")
        if self.full_market_value.amount < 0:
            raise ValueError("shadow observed value cannot be negative")
        return self


class ShadowPurchaseEvaluationV1(ContractModel):
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
    observed_at: datetime
    holding_seconds: NonNegativeDecimal
    filled_lots: NonNegativeInt
    filled_units: NonNegativeInt
    entry_gross_amount: Money
    entry_accrued_interest: Money
    entry_security_value: Money
    entry_commission: Money
    entry_total_cost: Money
    observed_full_market_value: Money
    gross_value_change: Money
    net_value_change_after_entry_costs: Money
    return_on_total_cost: FiniteDecimal
    outcome: ShadowOutcome
    observation_source: Annotated[str, Field(min_length=1, max_length=256)]
    observation_source_id: Annotated[str | None, Field(max_length=256)] = None
    no_lookahead: Literal[True] = True
    no_cross_currency_aggregation: Literal[True] = True
    paper_only: Literal[True] = True
    broker_order_created: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("evaluated_from", "observed_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("shadow evaluation timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_evaluation(self) -> ShadowPurchaseEvaluationV1:
        if self.metadata.schema_name != "shadow_purchase_evaluation":
            raise ValueError("schema_name must be shadow_purchase_evaluation")
        if self.paper_status == PaperOrderStatus.REJECTED:
            raise ValueError("rejected paper result cannot form a shadow evaluation")
        if self.observed_at <= self.evaluated_from:
            raise ValueError("shadow observation must be later than paper evaluation")
        expected_holding = Decimal(
            str((self.observed_at - self.evaluated_from).total_seconds())
        )
        if self.holding_seconds != expected_holding:
            raise ValueError("shadow holding period does not reconcile")

        money_values = (
            self.entry_gross_amount,
            self.entry_accrued_interest,
            self.entry_security_value,
            self.entry_commission,
            self.entry_total_cost,
            self.observed_full_market_value,
            self.gross_value_change,
            self.net_value_change_after_entry_costs,
        )
        if any(money.currency != self.currency for money in money_values):
            raise ValueError("shadow evaluation money must use one currency")
        if self.entry_security_value.amount != (
            self.entry_gross_amount.amount + self.entry_accrued_interest.amount
        ):
            raise ValueError("entry security value does not reconcile")
        if self.entry_total_cost.amount != (
            self.entry_security_value.amount + self.entry_commission.amount
        ):
            raise ValueError("entry total cost does not reconcile")
        if self.gross_value_change.amount != (
            self.observed_full_market_value.amount - self.entry_security_value.amount
        ):
            raise ValueError("gross value change does not reconcile")
        if self.net_value_change_after_entry_costs.amount != (
            self.observed_full_market_value.amount - self.entry_total_cost.amount
        ):
            raise ValueError("net value change does not reconcile")
        expected_return = (
            self.net_value_change_after_entry_costs.amount
            / self.entry_total_cost.amount
            if self.entry_total_cost.amount > 0
            else Decimal("0")
        )
        if self.return_on_total_cost != expected_return:
            raise ValueError("shadow return does not reconcile")

        net_change = self.net_value_change_after_entry_costs.amount
        expected_outcome = (
            ShadowOutcome.PROFIT
            if net_change > 0
            else ShadowOutcome.LOSS
            if net_change < 0
            else ShadowOutcome.FLAT
        )
        if self.outcome != expected_outcome:
            raise ValueError("shadow outcome does not match net value change")
        return self
