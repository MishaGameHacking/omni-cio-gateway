from __future__ import annotations

from datetime import datetime, timezone
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from omni_cio.contracts.v1.capacity import (
    CapacityAssessmentV1,
    CapacityBlocker,
    CapacityEvidenceV1,
    CapacityMetricsV1,
    CapacityOrderRequestV1,
    CapacityPolicyV1,
    CapacityStatus,
    CapacityWarning,
)
from omni_cio.contracts.v1.market import MarketReadinessAssessmentV1


class CapacityAssessmentError(ValueError):
    """The supplied capacity assessment request is structurally invalid."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise CapacityAssessmentError("CAPACITY_ASSESSMENT_TIMESTAMP_MUST_BE_AWARE")
    return result.astimezone(timezone.utc)


def _append_unique[T](target: list[T], value: T) -> None:
    if value not in target:
        target.append(value)


def _ceiling_ratio(numerator: Decimal, denominator: Decimal) -> int:
    return int((numerator / denominator).to_integral_value(rounding=ROUND_CEILING))


def _safe_lots(
    safe_notional: Decimal,
    *,
    price: Decimal,
    lot_size: int,
) -> int:
    lot_notional = price * Decimal(lot_size)
    return int((safe_notional / lot_notional).to_integral_value(rounding=ROUND_FLOOR))


def _capacity_metrics(
    request: CapacityOrderRequestV1,
    evidence: CapacityEvidenceV1,
    policy: CapacityPolicyV1,
) -> CapacityMetricsV1:
    execution_days = Decimal(request.intended_execution_days)
    daily_slice = request.order_notional / execution_days
    daily_participation = daily_slice / evidence.average_daily_turnover_notional
    top_of_book_participation = daily_slice / evidence.top_of_book_depth_notional
    minimum_execution_days = max(
        1,
        _ceiling_ratio(
            request.order_notional,
            evidence.average_daily_turnover_notional
            * policy.maximum_daily_turnover_participation,
        ),
    )

    half_spread = evidence.spread_bps / Decimal("2")
    impact_ex_spread = (
        evidence.daily_return_volatility
        * daily_participation.sqrt()
        * policy.impact_coefficient
        * Decimal("10000")
    )
    estimated_impact = half_spread + impact_ex_spread

    maximum_by_daily = (
        evidence.average_daily_turnover_notional
        * policy.maximum_daily_turnover_participation
        * execution_days
    )
    maximum_by_top = (
        evidence.top_of_book_depth_notional
        * policy.maximum_top_of_book_participation
        * execution_days
    )
    impact_budget = policy.maximum_estimated_impact_bps - half_spread
    if impact_budget <= 0:
        maximum_by_impact = Decimal("0")
    elif evidence.daily_return_volatility == 0:
        maximum_by_impact = maximum_by_daily
    else:
        allowed_daily_participation = (
            impact_budget
            / (
                evidence.daily_return_volatility
                * policy.impact_coefficient
                * Decimal("10000")
            )
        ) ** 2
        maximum_by_impact = (
            evidence.average_daily_turnover_notional
            * allowed_daily_participation
            * execution_days
        )

    safe_notional = min(maximum_by_daily, maximum_by_top, maximum_by_impact)
    safe_lots = _safe_lots(
        safe_notional,
        price=request.reference_price,
        lot_size=request.lot_size,
    )
    return CapacityMetricsV1(
        order_notional=request.order_notional,
        daily_slice_notional=daily_slice,
        daily_turnover_participation=daily_participation,
        top_of_book_participation=top_of_book_participation,
        minimum_execution_days=minimum_execution_days,
        estimated_impact_bps=estimated_impact,
        half_spread_bps=half_spread,
        impact_ex_spread_bps=impact_ex_spread,
        maximum_notional_by_daily_turnover=maximum_by_daily,
        maximum_notional_by_top_of_book=maximum_by_top,
        maximum_notional_by_impact=maximum_by_impact,
        safe_notional_for_requested_window=safe_notional,
        safe_lots_for_requested_window=safe_lots,
        requested_notional_within_safe_capacity=(
            request.order_notional <= safe_notional
        ),
    )


def assess_market_capacity(
    request: CapacityOrderRequestV1,
    evidence: CapacityEvidenceV1,
    market_readiness: MarketReadinessAssessmentV1,
    *,
    policy: CapacityPolicyV1 | None = None,
    assessed_at: datetime | None = None,
) -> CapacityAssessmentV1:
    """Assess point-in-time execution capacity without creating an order."""

    active_policy = policy or CapacityPolicyV1()
    assessment_time = _aware_utc(assessed_at)

    if request.instrument_key != evidence.instrument_key:
        raise CapacityAssessmentError("CAPACITY_INSTRUMENT_MISMATCH")
    if request.currency != evidence.currency:
        raise CapacityAssessmentError("CAPACITY_CURRENCY_MISMATCH")
    if request.lot_size != evidence.lot_size:
        raise CapacityAssessmentError("CAPACITY_LOT_SIZE_MISMATCH")
    if request.reference_price != evidence.reference_price:
        raise CapacityAssessmentError("CAPACITY_REFERENCE_PRICE_MISMATCH")

    blockers: list[CapacityBlocker] = []
    warnings: list[CapacityWarning] = [
        CapacityWarning.SQUARE_ROOT_IMPACT_PROXY,
        CapacityWarning.IMPACT_IS_NOT_EXECUTION_PRICE,
        CapacityWarning.TOP_OF_BOOK_ONLY,
        CapacityWarning.SINGLE_VENUE_EVIDENCE,
        CapacityWarning.CAPACITY_IS_POINT_IN_TIME,
    ]

    if not market_readiness.decision_ready:
        _append_unique(blockers, CapacityBlocker.MARKET_NOT_READY)

    evidence_age_seconds = (assessment_time - evidence.as_of).total_seconds()
    if evidence_age_seconds > active_policy.evidence_max_age_seconds:
        _append_unique(blockers, CapacityBlocker.EVIDENCE_STALE)
    if evidence_age_seconds < -active_policy.future_tolerance_seconds:
        _append_unique(blockers, CapacityBlocker.EVIDENCE_FROM_FUTURE)
    source_future_seconds = (
        evidence.source.retrieved_at - assessment_time
    ).total_seconds()
    if source_future_seconds > active_policy.future_tolerance_seconds:
        _append_unique(blockers, CapacityBlocker.EVIDENCE_FROM_FUTURE)
    if evidence.source.authority not in active_policy.trusted_authorities:
        _append_unique(blockers, CapacityBlocker.UNTRUSTED_SOURCE)
    if evidence.turnover_history_days < active_policy.minimum_turnover_history_days:
        _append_unique(
            blockers,
            CapacityBlocker.INSUFFICIENT_TURNOVER_HISTORY,
        )

    metrics = _capacity_metrics(request, evidence, active_policy)
    if (
        metrics.daily_turnover_participation
        > active_policy.maximum_daily_turnover_participation
    ):
        _append_unique(blockers, CapacityBlocker.DAILY_PARTICIPATION_EXCEEDED)
    if (
        metrics.top_of_book_participation
        > active_policy.maximum_top_of_book_participation
    ):
        _append_unique(
            blockers,
            CapacityBlocker.TOP_OF_BOOK_PARTICIPATION_EXCEEDED,
        )
    if request.intended_execution_days < metrics.minimum_execution_days:
        _append_unique(blockers, CapacityBlocker.EXECUTION_WINDOW_TOO_SHORT)
    if metrics.estimated_impact_bps > active_policy.maximum_estimated_impact_bps:
        _append_unique(blockers, CapacityBlocker.ESTIMATED_IMPACT_EXCEEDED)
    if metrics.safe_notional_for_requested_window == 0:
        _append_unique(blockers, CapacityBlocker.ZERO_SAFE_CAPACITY)

    if request.intended_execution_days > 1 or metrics.minimum_execution_days > 1:
        _append_unique(warnings, CapacityWarning.ORDER_SPLITTING_REQUIRED)
    if evidence.spread_bps > active_policy.high_spread_warning_bps:
        _append_unique(warnings, CapacityWarning.HIGH_SPREAD)
    turnover_variability = (
        max(
            evidence.average_daily_turnover_notional,
            evidence.median_daily_turnover_notional,
        )
        / min(
            evidence.average_daily_turnover_notional,
            evidence.median_daily_turnover_notional,
        )
    )
    if turnover_variability > active_policy.high_turnover_variability_ratio:
        _append_unique(warnings, CapacityWarning.TURNOVER_VARIABILITY_HIGH)

    capacity_ready = not blockers
    status = CapacityStatus.READY if capacity_ready else CapacityStatus.REJECTED
    return CapacityAssessmentV1(
        assessed_at=assessment_time,
        status=status,
        capacity_ready=capacity_ready,
        request=request,
        evidence=evidence,
        policy=active_policy,
        market_decision_ready=market_readiness.decision_ready,
        metrics=metrics,
        blockers=tuple(blockers),
        warnings=tuple(warnings),
    )
