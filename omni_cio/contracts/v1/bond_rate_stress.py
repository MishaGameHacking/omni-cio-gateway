from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel, CurrencyCode, FiniteDecimal, Money
from omni_cio.contracts.v1.market import MarketAssessmentStatus


PositiveDecimal = Annotated[
    Decimal,
    Field(gt=Decimal("0"), allow_inf_nan=False),
]
NonNegativeDecimal = Annotated[
    Decimal,
    Field(ge=Decimal("0"), allow_inf_nan=False),
]
ShockBasisPoints = Annotated[int, Field(ge=-1000, le=1000)]


class BondRateStressDirection(StrEnum):
    RATE_DOWN = "rate_down"
    UNCHANGED = "unchanged"
    RATE_UP = "rate_up"


class BondRateStressBlocker(StrEnum):
    CREDIT_ASSESSMENT_REJECTED = "credit_assessment_rejected"
    DURATION_MISSING = "duration_missing"
    CURRENCY_MISMATCH = "currency_mismatch"
    CURRENT_VALUE_INVALID = "current_value_invalid"
    SCENARIOS_REQUIRED = "scenarios_required"
    DUPLICATE_SHOCK = "duplicate_shock"
    ZERO_SHOCK_NOT_ALLOWED = "zero_shock_not_allowed"
    LINEAR_APPROXIMATION_OUT_OF_RANGE = "linear_approximation_out_of_range"


class BondRateStressWarning(StrEnum):
    CREDIT_ASSESSMENT_PARTIAL = "credit_assessment_partial"
    CONVEXITY_NOT_INCLUDED = "convexity_not_included"
    CREDIT_SPREAD_HELD_CONSTANT = "credit_spread_held_constant"
    COUPON_REINVESTMENT_NOT_MODELED = "coupon_reinvestment_not_modeled"
    LINEAR_APPROXIMATION_ONLY = "linear_approximation_only"


class BondRateShockScenarioV1(ContractModel):
    shock_basis_points: ShockBasisPoints
    direction: BondRateStressDirection
    yield_change: FiniteDecimal
    estimated_price_change_ratio: FiniteDecimal
    estimated_value: Money
    estimated_change: Money
    estimated_loss: Money
    current_value: Money
    duration_years: PositiveDecimal
    linear_duration_approximation: Literal[True] = True
    convexity_included: Literal[False] = False
    credit_spread_held_constant: Literal[True] = True
    trading_methods: Literal[False] = False

    @model_validator(mode="after")
    def validate_scenario(self) -> BondRateShockScenarioV1:
        currencies = {
            self.estimated_value.currency,
            self.estimated_change.currency,
            self.estimated_loss.currency,
            self.current_value.currency,
        }
        if len(currencies) != 1:
            raise ValueError("bond rate scenario money must use one currency")
        expected_direction = (
            BondRateStressDirection.RATE_UP
            if self.shock_basis_points > 0
            else BondRateStressDirection.RATE_DOWN
            if self.shock_basis_points < 0
            else BondRateStressDirection.UNCHANGED
        )
        if self.direction != expected_direction:
            raise ValueError("bond rate scenario direction does not reconcile")
        expected_yield_change = Decimal(self.shock_basis_points) / Decimal("10000")
        if self.yield_change != expected_yield_change:
            raise ValueError("bond rate scenario yield change does not reconcile")
        expected_ratio = -self.duration_years * expected_yield_change
        if self.estimated_price_change_ratio != expected_ratio:
            raise ValueError("bond rate scenario price ratio does not reconcile")
        expected_value = self.current_value.amount * (Decimal("1") + expected_ratio)
        if self.estimated_value.amount != expected_value:
            raise ValueError("bond rate scenario value does not reconcile")
        expected_change = expected_value - self.current_value.amount
        if self.estimated_change.amount != expected_change:
            raise ValueError("bond rate scenario change does not reconcile")
        expected_loss = max(Decimal("0"), -expected_change)
        if self.estimated_loss.amount != expected_loss:
            raise ValueError("bond rate scenario loss does not reconcile")
        if self.estimated_value.amount < 0:
            raise ValueError("bond rate scenario cannot estimate negative value")
        return self


class BondRateStressAssessmentV1(ContractModel):
    assessed_at: datetime
    instrument_key: Annotated[str, Field(min_length=3, max_length=256)]
    currency: CurrencyCode
    status: MarketAssessmentStatus
    stress_ready: bool
    source_credit_status: MarketAssessmentStatus
    current_full_value: Money
    duration_years: PositiveDecimal | None = None
    scenarios: tuple[BondRateShockScenarioV1, ...]
    worst_loss: Money
    worst_loss_ratio: NonNegativeDecimal
    blockers: tuple[BondRateStressBlocker, ...] = ()
    warnings: tuple[BondRateStressWarning, ...] = ()
    formula: Literal["delta_p_over_p_approx_minus_duration_times_delta_y"] = (
        "delta_p_over_p_approx_minus_duration_times_delta_y"
    )
    linear_duration_approximation: Literal[True] = True
    convexity_included: Literal[False] = False
    credit_spread_held_constant: Literal[True] = True
    coupon_reinvestment_modeled: Literal[False] = False
    no_cross_currency_aggregation: Literal[True] = True
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("assessed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("bond rate stress timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_assessment(self) -> BondRateStressAssessmentV1:
        if len(self.blockers) != len(set(self.blockers)):
            raise ValueError("bond rate stress blockers must be unique")
        if len(self.warnings) != len(set(self.warnings)):
            raise ValueError("bond rate stress warnings must be unique")
        if self.current_full_value.currency != self.currency:
            raise ValueError("bond rate stress current value currency mismatch")
        if self.worst_loss.currency != self.currency:
            raise ValueError("bond rate stress worst loss currency mismatch")
        if any(scenario.current_value.currency != self.currency for scenario in self.scenarios):
            raise ValueError("bond rate stress scenarios must use one currency")
        shocks = [scenario.shock_basis_points for scenario in self.scenarios]
        if len(shocks) != len(set(shocks)):
            raise ValueError("bond rate stress shocks must be unique")
        if shocks != sorted(shocks):
            raise ValueError("bond rate stress shocks must be sorted")
        if self.stress_ready != (not self.blockers):
            raise ValueError("stress_ready does not match blockers")
        expected_status = (
            MarketAssessmentStatus.READY
            if self.stress_ready
            else MarketAssessmentStatus.REJECTED
            if BondRateStressBlocker.CREDIT_ASSESSMENT_REJECTED in self.blockers
            else MarketAssessmentStatus.PARTIAL
        )
        if self.status != expected_status:
            raise ValueError("bond rate stress status does not match blockers")
        if self.duration_years is None and self.scenarios:
            raise ValueError("bond rate stress scenarios require duration")
        expected_worst_loss = max(
            (scenario.estimated_loss.amount for scenario in self.scenarios),
            default=Decimal("0"),
        )
        if self.worst_loss.amount != expected_worst_loss:
            raise ValueError("bond rate stress worst loss does not reconcile")
        expected_ratio = (
            expected_worst_loss / self.current_full_value.amount
            if self.current_full_value.amount > 0
            else Decimal("0")
        )
        if self.worst_loss_ratio != expected_ratio:
            raise ValueError("bond rate stress worst loss ratio does not reconcile")
        return self
