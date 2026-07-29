from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from decimal import Decimal

from omni_cio.contracts.v1.bond_credit import BondCreditRiskAssessmentV1
from omni_cio.contracts.v1.bond_rate_stress import (
    BondRateShockScenarioV1,
    BondRateStressAssessmentV1,
    BondRateStressBlocker,
    BondRateStressDirection,
    BondRateStressWarning,
)
from omni_cio.contracts.v1.common import Money
from omni_cio.contracts.v1.market import MarketAssessmentStatus


_DEFAULT_SHOCKS = (-200, -100, 100, 200)
_MAX_SCENARIOS = 16


class BondRateStressAssessmentError(ValueError):
    """The supplied bond-rate stress inputs cannot be evaluated safely."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise BondRateStressAssessmentError(
            "BOND_RATE_STRESS_TIMESTAMP_MUST_BE_AWARE"
        )
    return result.astimezone(timezone.utc)


def _append_unique[T](target: list[T], value: T) -> None:
    if value not in target:
        target.append(value)


def assess_bond_rate_stress(
    credit_assessment: BondCreditRiskAssessmentV1,
    current_full_value: Money,
    *,
    currency: str,
    shock_basis_points: Sequence[int] = _DEFAULT_SHOCKS,
    assessed_at: datetime | None = None,
) -> BondRateStressAssessmentV1:
    """Apply a bounded linear duration approximation to explicit rate shocks."""

    evaluation_time = _aware_utc(assessed_at)
    normalized_currency = currency.upper()
    blockers: list[BondRateStressBlocker] = []
    warnings: list[BondRateStressWarning] = [
        BondRateStressWarning.CONVEXITY_NOT_INCLUDED,
        BondRateStressWarning.CREDIT_SPREAD_HELD_CONSTANT,
        BondRateStressWarning.COUPON_REINVESTMENT_NOT_MODELED,
        BondRateStressWarning.LINEAR_APPROXIMATION_ONLY,
    ]

    if credit_assessment.status == MarketAssessmentStatus.REJECTED:
        _append_unique(
            blockers,
            BondRateStressBlocker.CREDIT_ASSESSMENT_REJECTED,
        )
    elif credit_assessment.status == MarketAssessmentStatus.PARTIAL:
        _append_unique(
            warnings,
            BondRateStressWarning.CREDIT_ASSESSMENT_PARTIAL,
        )

    duration_years = credit_assessment.duration_years
    if duration_years is None or duration_years <= 0:
        _append_unique(blockers, BondRateStressBlocker.DURATION_MISSING)
    if current_full_value.currency != normalized_currency:
        _append_unique(blockers, BondRateStressBlocker.CURRENCY_MISMATCH)
    if current_full_value.amount <= 0:
        _append_unique(blockers, BondRateStressBlocker.CURRENT_VALUE_INVALID)

    shocks = tuple(shock_basis_points)
    if not shocks or len(shocks) > _MAX_SCENARIOS:
        _append_unique(blockers, BondRateStressBlocker.SCENARIOS_REQUIRED)
    if len(shocks) != len(set(shocks)):
        _append_unique(blockers, BondRateStressBlocker.DUPLICATE_SHOCK)
    if 0 in shocks:
        _append_unique(blockers, BondRateStressBlocker.ZERO_SHOCK_NOT_ALLOWED)
    if any(isinstance(shock, bool) or shock < -1000 or shock > 1000 for shock in shocks):
        _append_unique(
            blockers,
            BondRateStressBlocker.LINEAR_APPROXIMATION_OUT_OF_RANGE,
        )

    scenarios: list[BondRateShockScenarioV1] = []
    if not blockers and duration_years is not None:
        for shock in sorted(shocks):
            yield_change = Decimal(shock) / Decimal("10000")
            price_change_ratio = -duration_years * yield_change
            estimated_value = current_full_value.amount * (
                Decimal("1") + price_change_ratio
            )
            if estimated_value < 0:
                _append_unique(
                    blockers,
                    BondRateStressBlocker.LINEAR_APPROXIMATION_OUT_OF_RANGE,
                )
                scenarios.clear()
                break
            estimated_change = estimated_value - current_full_value.amount
            scenarios.append(
                BondRateShockScenarioV1(
                    shock_basis_points=shock,
                    direction=(
                        BondRateStressDirection.RATE_UP
                        if shock > 0
                        else BondRateStressDirection.RATE_DOWN
                    ),
                    yield_change=yield_change,
                    estimated_price_change_ratio=price_change_ratio,
                    estimated_value=Money(
                        amount=estimated_value,
                        currency=normalized_currency,
                    ),
                    estimated_change=Money(
                        amount=estimated_change,
                        currency=normalized_currency,
                    ),
                    estimated_loss=Money(
                        amount=max(Decimal("0"), -estimated_change),
                        currency=normalized_currency,
                    ),
                    current_value=Money(
                        amount=current_full_value.amount,
                        currency=normalized_currency,
                    ),
                    duration_years=duration_years,
                    linear_duration_approximation=True,
                    convexity_included=False,
                    credit_spread_held_constant=True,
                    trading_methods=False,
                )
            )

    stress_ready = not blockers
    status = (
        MarketAssessmentStatus.READY
        if stress_ready
        else MarketAssessmentStatus.REJECTED
        if BondRateStressBlocker.CREDIT_ASSESSMENT_REJECTED in blockers
        else MarketAssessmentStatus.PARTIAL
    )
    scenario_tuple = tuple(scenarios)
    worst_loss_amount = max(
        (scenario.estimated_loss.amount for scenario in scenario_tuple),
        default=Decimal("0"),
    )
    worst_loss_ratio = (
        worst_loss_amount / current_full_value.amount
        if current_full_value.amount > 0
        else Decimal("0")
    )

    return BondRateStressAssessmentV1(
        assessed_at=evaluation_time,
        instrument_key=credit_assessment.instrument_key,
        currency=normalized_currency,
        status=status,
        stress_ready=stress_ready,
        source_credit_status=credit_assessment.status,
        current_full_value=Money(
            amount=current_full_value.amount,
            currency=current_full_value.currency,
        ),
        duration_years=duration_years,
        scenarios=scenario_tuple,
        worst_loss=Money(
            amount=worst_loss_amount,
            currency=normalized_currency,
        ),
        worst_loss_ratio=worst_loss_ratio,
        blockers=tuple(blockers),
        warnings=tuple(warnings),
        linear_duration_approximation=True,
        convexity_included=False,
        credit_spread_held_constant=True,
        coupon_reinvestment_modeled=False,
        no_cross_currency_aggregation=True,
        execution_ready=False,
        trading_methods=False,
    )
