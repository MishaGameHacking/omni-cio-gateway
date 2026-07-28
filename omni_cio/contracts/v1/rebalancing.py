from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import (
    ContractMetadata,
    ContractModel,
    CurrencyCode,
    FiniteDecimal,
)


UnitInterval = Annotated[
    Decimal,
    Field(ge=Decimal("0"), le=Decimal("1"), allow_inf_nan=False),
]
NonNegativeDecimal = Annotated[
    Decimal,
    Field(ge=Decimal("0"), allow_inf_nan=False),
]
NonNegativeInt = Annotated[int, Field(ge=0)]


class RebalanceBandStatus(StrEnum):
    BELOW = "below"
    INSIDE = "inside"
    ABOVE = "above"


class RebalanceDirection(StrEnum):
    NONE = "none"
    ADD = "add"
    REDUCE = "reduce"


class RebalanceAlternativeKind(StrEnum):
    NO_ACTION = "no_action"
    CASH_FIRST = "cash_first"
    FULL_THRESHOLD = "full_threshold"


class RebalanceAlternativeStatus(StrEnum):
    PREFERRED = "preferred"
    AVAILABLE = "available"
    REVIEW_ONLY = "review_only"
    BLOCKED = "blocked"


class RebalanceBlocker(StrEnum):
    DECISION_NOT_READY = "decision_not_ready"
    TARGET_COVERAGE_INCOMPLETE = "target_coverage_incomplete"
    CURRENCY_MISMATCH = "currency_mismatch"
    CASH_NOT_AVAILABLE = "cash_not_available"
    SALES_REQUIRE_TAX_BASIS = "sales_require_tax_basis"
    LIVE_PREVIEW_REQUIRED = "live_preview_required"


class TargetBandV1(ContractModel):
    stable_key: Annotated[str, Field(min_length=3, max_length=256)]
    currency: CurrencyCode
    lower_weight: UnitInterval
    target_weight: UnitInterval
    upper_weight: UnitInterval

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_band(self) -> TargetBandV1:
        if not self.lower_weight <= self.target_weight <= self.upper_weight:
            raise ValueError("target weight must be inside lower and upper bounds")
        return self


class RebalanceLineV1(ContractModel):
    stable_key: Annotated[str, Field(min_length=3, max_length=256)]
    currency: CurrencyCode
    current_value: NonNegativeDecimal
    current_weight: UnitInterval
    lower_weight: UnitInterval
    target_weight: UnitInterval
    upper_weight: UnitInterval
    band_status: RebalanceBandStatus
    direction: RebalanceDirection
    deviation_from_target: FiniteDecimal
    value_to_nearest_band: NonNegativeDecimal
    value_to_target: NonNegativeDecimal
    sale_required: bool
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_line(self) -> RebalanceLineV1:
        if not self.lower_weight <= self.target_weight <= self.upper_weight:
            raise ValueError("rebalance line has invalid target band")
        expected_deviation = self.current_weight - self.target_weight
        if self.deviation_from_target != expected_deviation:
            raise ValueError("deviation_from_target does not reconcile")
        if self.band_status == RebalanceBandStatus.INSIDE:
            if self.direction != RebalanceDirection.NONE:
                raise ValueError("inside-band line must not request change")
            if self.value_to_nearest_band != 0 or self.sale_required:
                raise ValueError("inside-band line cannot require value or sale")
        elif self.band_status == RebalanceBandStatus.BELOW:
            if self.direction != RebalanceDirection.ADD or self.sale_required:
                raise ValueError("below-band line must be add-only")
        elif self.direction != RebalanceDirection.REDUCE or not self.sale_required:
            raise ValueError("above-band line must require reduction review")
        return self


class RebalanceAlternativeV1(ContractModel):
    alternative_id: Annotated[
        str,
        Field(pattern=r"^[a-z0-9][a-z0-9_.:-]{2,255}$"),
    ]
    kind: RebalanceAlternativeKind
    status: RebalanceAlternativeStatus
    title: Annotated[str, Field(min_length=1, max_length=256)]
    rationale: Annotated[str, Field(min_length=1, max_length=1024)]
    uses_sales: bool
    available_cash: NonNegativeDecimal
    planned_add_value: NonNegativeDecimal
    planned_reduce_value: NonNegativeDecimal
    residual_cash: NonNegativeDecimal
    blockers: tuple[RebalanceBlocker, ...] = ()
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @model_validator(mode="after")
    def validate_alternative(self) -> RebalanceAlternativeV1:
        if len(self.blockers) != len(set(self.blockers)):
            raise ValueError("alternative blockers must be unique")
        if self.status == RebalanceAlternativeStatus.BLOCKED and not self.blockers:
            raise ValueError("blocked alternative requires blockers")
        if self.status != RebalanceAlternativeStatus.BLOCKED and self.blockers:
            raise ValueError("only blocked alternatives may contain blockers")
        if self.kind == RebalanceAlternativeKind.NO_ACTION:
            if self.uses_sales or self.planned_add_value or self.planned_reduce_value:
                raise ValueError("no-action alternative cannot contain changes")
        if not self.uses_sales and self.planned_reduce_value != 0:
            raise ValueError("no-sale alternative cannot reduce value")
        if self.planned_add_value > self.available_cash + self.planned_reduce_value:
            raise ValueError("planned additions exceed available funding")
        expected_residual = (
            self.available_cash + self.planned_reduce_value - self.planned_add_value
        )
        if self.residual_cash != expected_residual:
            raise ValueError("residual cash does not reconcile")
        return self


class ThresholdRebalancePlanV1(ContractModel):
    metadata: ContractMetadata
    source_decision_schema_version: Annotated[str, Field(min_length=1, max_length=32)]
    lines: tuple[RebalanceLineV1, ...]
    alternatives: tuple[RebalanceAlternativeV1, ...]
    preferred_alternative_id: Annotated[str, Field(min_length=3, max_length=256)]
    decision_ready: bool
    no_cross_currency_aggregation: Literal[True] = True
    breach_count: NonNegativeInt
    below_count: NonNegativeInt
    above_count: NonNegativeInt
    inside_count: NonNegativeInt
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @model_validator(mode="after")
    def validate_plan(self) -> ThresholdRebalancePlanV1:
        if self.metadata.schema_name != "threshold_rebalance_plan":
            raise ValueError("schema_name must be threshold_rebalance_plan")
        line_keys = [(line.currency, line.stable_key) for line in self.lines]
        if len(line_keys) != len(set(line_keys)):
            raise ValueError("rebalance lines must be unique by currency and key")
        counts = {
            RebalanceBandStatus.BELOW: self.below_count,
            RebalanceBandStatus.ABOVE: self.above_count,
            RebalanceBandStatus.INSIDE: self.inside_count,
        }
        for status, expected in counts.items():
            if sum(line.band_status == status for line in self.lines) != expected:
                raise ValueError("rebalance status counters do not reconcile")
        if self.breach_count != self.below_count + self.above_count:
            raise ValueError("breach_count does not reconcile")

        kinds = [alternative.kind for alternative in self.alternatives]
        if len(kinds) != 3 or set(kinds) != set(RebalanceAlternativeKind):
            raise ValueError("plan requires exactly three alternative kinds")
        ids = [alternative.alternative_id for alternative in self.alternatives]
        if len(ids) != len(set(ids)):
            raise ValueError("alternative IDs must be unique")
        preferred = [
            alternative
            for alternative in self.alternatives
            if alternative.status == RebalanceAlternativeStatus.PREFERRED
        ]
        if len(preferred) != 1:
            raise ValueError("plan requires exactly one preferred alternative")
        if preferred[0].alternative_id != self.preferred_alternative_id:
            raise ValueError("preferred alternative ID does not reconcile")
        if not self.decision_ready:
            if preferred[0].kind != RebalanceAlternativeKind.NO_ACTION:
                raise ValueError("blocked plan must prefer no action")
            if any(
                alternative.kind != RebalanceAlternativeKind.NO_ACTION
                and alternative.status != RebalanceAlternativeStatus.BLOCKED
                for alternative in self.alternatives
            ):
                raise ValueError("blocked plan must block change alternatives")
        return self
