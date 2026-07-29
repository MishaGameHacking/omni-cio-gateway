from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from decimal import Decimal

from omni_cio.contracts.v1.bond_portfolio_rate_stress import (
    BondPortfolioRateScenarioV1,
    BondPortfolioRateStressV1,
    BondPortfolioStressBlocker,
    BondPortfolioStressContributionV1,
    BondPortfolioStressWarning,
)
from omni_cio.contracts.v1.bond_rate_stress import BondRateStressAssessmentV1
from omni_cio.contracts.v1.common import Money
from omni_cio.contracts.v1.market import MarketAssessmentStatus


_MAX_INSTRUMENTS = 256


class BondPortfolioRateStressError(ValueError):
    """Instrument stress assessments cannot be aggregated safely."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise BondPortfolioRateStressError(
            "BOND_PORTFOLIO_STRESS_TIMESTAMP_MUST_BE_AWARE"
        )
    return result.astimezone(timezone.utc)


def _fail(blocker: BondPortfolioStressBlocker) -> None:
    raise BondPortfolioRateStressError(blocker.value.upper())


def aggregate_bond_portfolio_rate_stress(
    assessments: Sequence[BondRateStressAssessmentV1],
    *,
    currency: str,
    assessed_at: datetime | None = None,
) -> BondPortfolioRateStressV1:
    """Aggregate complete same-currency bond scenarios on an identical shock grid."""

    normalized_currency = currency.upper()
    evaluation_time = _aware_utc(assessed_at)
    inputs = tuple(assessments)
    if not inputs:
        _fail(BondPortfolioStressBlocker.ASSESSMENTS_REQUIRED)
    if len(inputs) > _MAX_INSTRUMENTS:
        _fail(BondPortfolioStressBlocker.ASSESSMENT_LIMIT_EXCEEDED)

    keys = [assessment.instrument_key for assessment in inputs]
    if len(keys) != len(set(keys)):
        _fail(BondPortfolioStressBlocker.DUPLICATE_INSTRUMENT)
    if any(
        not assessment.stress_ready
        or assessment.status != MarketAssessmentStatus.READY
        or assessment.blockers
        for assessment in inputs
    ):
        _fail(BondPortfolioStressBlocker.INPUT_NOT_READY)
    if any(
        assessment.currency != normalized_currency
        or assessment.current_full_value.currency != normalized_currency
        for assessment in inputs
    ):
        _fail(BondPortfolioStressBlocker.CURRENCY_MISMATCH)
    if any(assessment.current_full_value.amount <= 0 for assessment in inputs):
        _fail(BondPortfolioStressBlocker.CURRENT_VALUE_INVALID)

    shock_grids = {
        tuple(scenario.shock_basis_points for scenario in assessment.scenarios)
        for assessment in inputs
    }
    if len(shock_grids) != 1:
        _fail(BondPortfolioStressBlocker.SHOCK_GRID_MISMATCH)
    shock_grid = next(iter(shock_grids))
    if not shock_grid:
        _fail(BondPortfolioStressBlocker.SHOCK_GRID_MISMATCH)

    ordered = tuple(sorted(inputs, key=lambda item: item.instrument_key))
    current_total = sum(
        assessment.current_full_value.amount for assessment in ordered
    )
    weighted_duration_numerator = sum(
        assessment.current_full_value.amount * assessment.duration_years
        for assessment in ordered
        if assessment.duration_years is not None
    )
    weighted_duration = weighted_duration_numerator / current_total

    scenarios: list[BondPortfolioRateScenarioV1] = []
    for shock_index, shock in enumerate(shock_grid):
        contributions = tuple(
            BondPortfolioStressContributionV1(
                instrument_key=assessment.instrument_key,
                shock_basis_points=shock,
                current_value=assessment.scenarios[shock_index].current_value,
                estimated_value=assessment.scenarios[shock_index].estimated_value,
                estimated_change=assessment.scenarios[shock_index].estimated_change,
                estimated_loss=assessment.scenarios[shock_index].estimated_loss,
                duration_years=assessment.scenarios[shock_index].duration_years,
                trading_methods=False,
            )
            for assessment in ordered
        )
        estimated_total = sum(
            contribution.estimated_value.amount for contribution in contributions
        )
        change_total = sum(
            contribution.estimated_change.amount for contribution in contributions
        )
        loss_total = sum(
            contribution.estimated_loss.amount for contribution in contributions
        )
        first_scenario = ordered[0].scenarios[shock_index]
        scenarios.append(
            BondPortfolioRateScenarioV1(
                shock_basis_points=shock,
                direction=first_scenario.direction,
                yield_change=first_scenario.yield_change,
                current_value=Money(
                    amount=current_total,
                    currency=normalized_currency,
                ),
                estimated_value=Money(
                    amount=estimated_total,
                    currency=normalized_currency,
                ),
                estimated_change=Money(
                    amount=change_total,
                    currency=normalized_currency,
                ),
                estimated_loss=Money(
                    amount=loss_total,
                    currency=normalized_currency,
                ),
                estimated_loss_ratio=loss_total / current_total,
                contribution_count=len(contributions),
                contributions=contributions,
                linear_duration_approximation=True,
                convexity_included=False,
                credit_spreads_held_constant=True,
                trading_methods=False,
            )
        )

    scenario_tuple = tuple(scenarios)
    worst_loss_amount = max(scenario.estimated_loss.amount for scenario in scenario_tuple)
    worst_candidates = [
        scenario.shock_basis_points
        for scenario in scenario_tuple
        if scenario.estimated_loss.amount == worst_loss_amount
    ]
    warnings = (
        BondPortfolioStressWarning.LINEAR_APPROXIMATION_ONLY,
        BondPortfolioStressWarning.CONVEXITY_NOT_INCLUDED,
        BondPortfolioStressWarning.CREDIT_SPREADS_HELD_CONSTANT,
        BondPortfolioStressWarning.CROSS_INSTRUMENT_CORRELATION_NOT_MODELED,
    )

    return BondPortfolioRateStressV1(
        assessed_at=evaluation_time,
        currency=normalized_currency,
        status=MarketAssessmentStatus.READY,
        stress_ready=True,
        instrument_count=len(ordered),
        instrument_keys=tuple(assessment.instrument_key for assessment in ordered),
        current_full_value=Money(
            amount=current_total,
            currency=normalized_currency,
        ),
        weighted_duration_years=weighted_duration,
        shock_grid_basis_points=shock_grid,
        scenarios=scenario_tuple,
        worst_loss=Money(
            amount=worst_loss_amount,
            currency=normalized_currency,
        ),
        worst_loss_ratio=worst_loss_amount / current_total,
        worst_shock_basis_points=min(worst_candidates),
        blockers=(),
        warnings=warnings,
        complete_scenario_coverage=True,
        linear_duration_approximation=True,
        convexity_included=False,
        credit_spreads_held_constant=True,
        no_cross_currency_aggregation=True,
        execution_ready=False,
        trading_methods=False,
    )
