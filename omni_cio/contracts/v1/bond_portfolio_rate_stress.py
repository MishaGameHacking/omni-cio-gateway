from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.bond_rate_stress import (
    BondRateStressDirection,
    ShockBasisPoints,
)
from omni_cio.contracts.v1.common import ContractModel, CurrencyCode, FiniteDecimal, Money
from omni_cio.contracts.v1.market import MarketAssessmentStatus


PositiveInt = Annotated[int, Field(ge=1)]
NonNegativeDecimal = Annotated[
    Decimal,
    Field(ge=Decimal("0"), allow_inf_nan=False),
]
PositiveDecimal = Annotated[
    Decimal,
    Field(gt=Decimal("0"), allow_inf_nan=False),
]


class BondPortfolioStressBlocker(StrEnum):
    ASSESSMENTS_REQUIRED = "assessments_required"
    ASSESSMENT_LIMIT_EXCEEDED = "assessment_limit_exceeded"
    INPUT_NOT_READY = "input_not_ready"
    CURRENCY_MISMATCH = "currency_mismatch"
    DUPLICATE_INSTRUMENT = "duplicate_instrument"
    SHOCK_GRID_MISMATCH = "shock_grid_mismatch"
    CURRENT_VALUE_INVALID = "current_value_invalid"


class BondPortfolioStressWarning(StrEnum):
    LINEAR_APPROXIMATION_ONLY = "linear_approximation_only"
    CONVEXITY_NOT_INCLUDED = "convexity_not_included"
    CREDIT_SPREADS_HELD_CONSTANT = "credit_spreads_held_constant"
    CROSS_INSTRUMENT_CORRELATION_NOT_MODELED = (
        "cross_instrument_correlation_not_modeled"
    )


class BondPortfolioStressContributionV1(ContractModel):
    instrument_key: Annotated[str, Field(min_length=3, max_length=256)]
    shock_basis_points: ShockBasisPoints
    current_value: Money
    estimated_value: Money
    estimated_change: Money
    estimated_loss: Money
    duration_years: PositiveDecimal
    trading_methods: Literal[False] = False

    @model_validator(mode="after")
    def validate_contribution(self) -> BondPortfolioStressContributionV1:
        currencies = {
            self.current_value.currency,
            self.estimated_value.currency,
            self.estimated_change.currency,
            self.estimated_loss.currency,
        }
        if len(currencies) != 1:
            raise ValueError("portfolio stress contribution must use one currency")
        expected_change = self.estimated_value.amount - self.current_value.amount
        if self.estimated_change.amount != expected_change:
            raise ValueError("portfolio stress contribution change does not reconcile")
        expected_loss = max(Decimal("0"), -expected_change)
        if self.estimated_loss.amount != expected_loss:
            raise ValueError("portfolio stress contribution loss does not reconcile")
        return self


class BondPortfolioRateScenarioV1(ContractModel):
    shock_basis_points: ShockBasisPoints
    direction: BondRateStressDirection
    yield_change: FiniteDecimal
    current_value: Money
    estimated_value: Money
    estimated_change: Money
    estimated_loss: Money
    estimated_loss_ratio: NonNegativeDecimal
    contribution_count: PositiveInt
    contributions: Annotated[
        tuple[BondPortfolioStressContributionV1, ...],
        Field(min_length=1, max_length=256),
    ]
    linear_duration_approximation: Literal[True] = True
    convexity_included: Literal[False] = False
    credit_spreads_held_constant: Literal[True] = True
    trading_methods: Literal[False] = False

    @model_validator(mode="after")
    def validate_scenario(self) -> BondPortfolioRateScenarioV1:
        currencies = {
            self.current_value.currency,
            self.estimated_value.currency,
            self.estimated_change.currency,
            self.estimated_loss.currency,
        }
        currencies.update(
            contribution.current_value.currency for contribution in self.contributions
        )
        if len(currencies) != 1:
            raise ValueError("portfolio rate scenario must use one currency")
        if self.contribution_count != len(self.contributions):
            raise ValueError("portfolio stress contribution count does not reconcile")
        if any(
            contribution.shock_basis_points != self.shock_basis_points
            for contribution in self.contributions
        ):
            raise ValueError("portfolio stress contribution shock does not reconcile")
        keys = [contribution.instrument_key for contribution in self.contributions]
        if len(keys) != len(set(keys)):
            raise ValueError("portfolio stress contributions must be unique")
        if keys != sorted(keys):
            raise ValueError("portfolio stress contributions must be sorted")
        expected_direction = (
            BondRateStressDirection.RATE_UP
            if self.shock_basis_points > 0
            else BondRateStressDirection.RATE_DOWN
            if self.shock_basis_points < 0
            else BondRateStressDirection.UNCHANGED
        )
        if self.direction != expected_direction:
            raise ValueError("portfolio stress direction does not reconcile")
        expected_yield_change = Decimal(self.shock_basis_points) / Decimal("10000")
        if self.yield_change != expected_yield_change:
            raise ValueError("portfolio stress yield change does not reconcile")
        expected_current = sum(
            contribution.current_value.amount for contribution in self.contributions
        )
        expected_estimated = sum(
            contribution.estimated_value.amount for contribution in self.contributions
        )
        expected_change = sum(
            contribution.estimated_change.amount for contribution in self.contributions
        )
        expected_loss = sum(
            contribution.estimated_loss.amount for contribution in self.contributions
        )
        if self.current_value.amount != expected_current:
            raise ValueError("portfolio stress current value does not reconcile")
        if self.estimated_value.amount != expected_estimated:
            raise ValueError("portfolio stress estimated value does not reconcile")
        if self.estimated_change.amount != expected_change:
            raise ValueError("portfolio stress estimated change does not reconcile")
        if self.estimated_loss.amount != expected_loss:
            raise ValueError("portfolio stress estimated loss does not reconcile")
        expected_ratio = (
            expected_loss / expected_current if expected_current > 0 else Decimal("0")
        )
        if self.estimated_loss_ratio != expected_ratio:
            raise ValueError("portfolio stress loss ratio does not reconcile")
        return self


class BondPortfolioRateStressV1(ContractModel):
    assessed_at: datetime
    currency: CurrencyCode
    status: MarketAssessmentStatus
    stress_ready: bool
    instrument_count: PositiveInt
    instrument_keys: Annotated[
        tuple[Annotated[str, Field(min_length=3, max_length=256)], ...],
        Field(min_length=1, max_length=256),
    ]
    current_full_value: Money
    weighted_duration_years: PositiveDecimal
    shock_grid_basis_points: Annotated[
        tuple[ShockBasisPoints, ...],
        Field(min_length=1, max_length=16),
    ]
    scenarios: Annotated[
        tuple[BondPortfolioRateScenarioV1, ...],
        Field(min_length=1, max_length=16),
    ]
    worst_loss: Money
    worst_loss_ratio: NonNegativeDecimal
    worst_shock_basis_points: ShockBasisPoints
    blockers: tuple[BondPortfolioStressBlocker, ...] = ()
    warnings: tuple[BondPortfolioStressWarning, ...] = ()
    formula: Literal["sum_instrument_duration_scenarios_by_identical_shock"] = (
        "sum_instrument_duration_scenarios_by_identical_shock"
    )
    complete_scenario_coverage: Literal[True] = True
    linear_duration_approximation: Literal[True] = True
    convexity_included: Literal[False] = False
    credit_spreads_held_constant: Literal[True] = True
    no_cross_currency_aggregation: Literal[True] = True
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("assessed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("portfolio rate stress timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_assessment(self) -> BondPortfolioRateStressV1:
        if self.blockers:
            raise ValueError("ready portfolio stress cannot contain blockers")
        if not self.stress_ready or self.status != MarketAssessmentStatus.READY:
            raise ValueError("portfolio stress contract contains only ready results")
        if len(self.warnings) != len(set(self.warnings)):
            raise ValueError("portfolio stress warnings must be unique")
        if self.instrument_count != len(self.instrument_keys):
            raise ValueError("portfolio stress instrument count does not reconcile")
        if tuple(sorted(set(self.instrument_keys))) != self.instrument_keys:
            raise ValueError("portfolio stress instrument keys must be sorted and unique")
        if self.current_full_value.currency != self.currency:
            raise ValueError("portfolio stress current value currency mismatch")
        if self.worst_loss.currency != self.currency:
            raise ValueError("portfolio stress worst loss currency mismatch")
        shocks = tuple(scenario.shock_basis_points for scenario in self.scenarios)
        if shocks != self.shock_grid_basis_points:
            raise ValueError("portfolio stress scenario grid does not reconcile")
        if shocks != tuple(sorted(set(shocks))):
            raise ValueError("portfolio stress shock grid must be sorted and unique")
        if any(
            scenario.current_value.amount != self.current_full_value.amount
            for scenario in self.scenarios
        ):
            raise ValueError("portfolio scenarios must use the same current total")
        if any(
            scenario.current_value.currency != self.currency
            for scenario in self.scenarios
        ):
            raise ValueError("portfolio scenarios must use one currency")

        baseline = self.scenarios[0].contributions
        baseline_keys = tuple(item.instrument_key for item in baseline)
        if baseline_keys != self.instrument_keys:
            raise ValueError("portfolio stress instrument evidence does not reconcile")
        baseline_values = {
            item.instrument_key: item.current_value.amount for item in baseline
        }
        baseline_durations = {
            item.instrument_key: item.duration_years for item in baseline
        }
        for scenario in self.scenarios:
            if (
                tuple(item.instrument_key for item in scenario.contributions)
                != self.instrument_keys
            ):
                raise ValueError("portfolio scenario instrument coverage changed")
            if any(
                item.current_value.amount != baseline_values[item.instrument_key]
                for item in scenario.contributions
            ):
                raise ValueError("portfolio scenario current values changed")
            if any(
                item.duration_years != baseline_durations[item.instrument_key]
                for item in scenario.contributions
            ):
                raise ValueError("portfolio scenario durations changed")
        expected_weighted_duration = sum(
            item.current_value.amount * item.duration_years for item in baseline
        ) / self.current_full_value.amount
        if self.weighted_duration_years != expected_weighted_duration:
            raise ValueError("portfolio weighted duration does not reconcile")

        expected_worst = max(scenario.estimated_loss.amount for scenario in self.scenarios)
        if self.worst_loss.amount != expected_worst:
            raise ValueError("portfolio stress worst loss does not reconcile")
        worst_candidates = [
            scenario.shock_basis_points
            for scenario in self.scenarios
            if scenario.estimated_loss.amount == expected_worst
        ]
        if self.worst_shock_basis_points != min(worst_candidates):
            raise ValueError("portfolio stress worst shock does not reconcile")
        expected_ratio = expected_worst / self.current_full_value.amount
        if self.worst_loss_ratio != expected_ratio:
            raise ValueError("portfolio stress worst loss ratio does not reconcile")
        return self
