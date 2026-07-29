from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from decimal import Decimal

from omni_cio.contracts.v1.fund_structure import (
    FundReplicationMethod,
    FundStructuralAssessmentV1,
    FundStructuralBlocker,
    FundStructuralEvidenceV1,
    FundStructuralMetricsV1,
    FundStructuralPolicyV1,
    FundStructuralStatus,
    FundStructuralWarning,
    FundStrategyKind,
)
from omni_cio.contracts.v1.market import MarketResearchBundleV1
from omni_cio.contracts.v1.portfolio import InstrumentType
from omni_cio.market.assessment_v1 import assess_market_research_bundle


_SECONDS_PER_DAY = 86_400
_DERIVATIVE_TYPES = {
    InstrumentType.FUTURE,
    InstrumentType.OPTION,
    InstrumentType.STRUCTURED_PRODUCT,
}


class FundStructuralAssessmentError(ValueError):
    """The supplied fund evidence cannot be assessed safely."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise FundStructuralAssessmentError(
            "FUND_STRUCTURAL_ASSESSMENT_TIMESTAMP_MUST_BE_AWARE"
        )
    return result.astimezone(timezone.utc)


def _append_unique[T](target: list[T], value: T) -> None:
    if value not in target:
        target.append(value)


def _age_days(
    value_at: datetime,
    *,
    assessed_at: datetime,
    future_tolerance_seconds: int,
    future_blocker: FundStructuralBlocker,
    stale_blocker: FundStructuralBlocker,
    max_age_days: int,
    blockers: list[FundStructuralBlocker],
) -> int:
    age_seconds = (assessed_at - value_at).total_seconds()
    if age_seconds < -future_tolerance_seconds:
        _append_unique(blockers, future_blocker)
    if age_seconds > max_age_days * _SECONDS_PER_DAY:
        _append_unique(blockers, stale_blocker)
    return max(0, int(age_seconds // _SECONDS_PER_DAY))


def _top_weight(weights: list[Decimal], count: int) -> Decimal:
    return sum(sorted(weights, reverse=True)[:count], Decimal("0"))


def assess_fund_structure(
    bundle: MarketResearchBundleV1,
    evidence: FundStructuralEvidenceV1,
    *,
    existing_portfolio_instrument_keys: Iterable[str] = (),
    policy: FundStructuralPolicyV1 | None = None,
    assessed_at: datetime | None = None,
) -> FundStructuralAssessmentV1:
    """Assess fund structure, fees, tracking and direct overlap without fetching data."""

    active_policy = policy or FundStructuralPolicyV1()
    evaluation_time = _aware_utc(assessed_at)
    market_readiness = assess_market_research_bundle(
        bundle,
        assessed_at=evaluation_time,
    )
    blockers: list[FundStructuralBlocker] = []
    warnings: list[FundStructuralWarning] = [
        FundStructuralWarning.MANAGEMENT_COMPANY_RISK_NOT_SCORED,
        FundStructuralWarning.STRUCTURE_IS_POINT_IN_TIME,
        FundStructuralWarning.METRICS_ARE_NOT_FORECASTS,
    ]

    if not market_readiness.decision_ready:
        _append_unique(blockers, FundStructuralBlocker.MARKET_RESEARCH_NOT_READY)

    reference = bundle.reference
    if reference is None:
        _append_unique(blockers, FundStructuralBlocker.REFERENCE_MISSING)
    else:
        if reference.instrument_type is not InstrumentType.ETF:
            _append_unique(blockers, FundStructuralBlocker.NOT_A_FUND)
        if reference.stable_key != evidence.instrument_key:
            _append_unique(
                blockers,
                FundStructuralBlocker.INSTRUMENT_IDENTITY_MISMATCH,
            )
        if reference.currency != evidence.currency:
            _append_unique(blockers, FundStructuralBlocker.CURRENCY_MISMATCH)

    if bundle.instrument_key != evidence.instrument_key:
        _append_unique(
            blockers,
            FundStructuralBlocker.INSTRUMENT_IDENTITY_MISMATCH,
        )

    evidence_sources = [evidence.structure_source, evidence.fee_source]
    if evidence.tracking_source is not None:
        evidence_sources.append(evidence.tracking_source)
    if any(
        source.authority not in active_policy.trusted_authorities
        for source in evidence_sources
    ):
        _append_unique(blockers, FundStructuralBlocker.UNTRUSTED_SOURCE)

    structure_age_days = _age_days(
        evidence.structure_as_of,
        assessed_at=evaluation_time,
        future_tolerance_seconds=active_policy.future_tolerance_seconds,
        future_blocker=FundStructuralBlocker.STRUCTURE_FUTURE_TIMESTAMP,
        stale_blocker=FundStructuralBlocker.STRUCTURE_STALE,
        max_age_days=active_policy.max_structure_age_days,
        blockers=blockers,
    )
    fee_age_days = _age_days(
        evidence.fee_as_of,
        assessed_at=evaluation_time,
        future_tolerance_seconds=active_policy.future_tolerance_seconds,
        future_blocker=FundStructuralBlocker.FEE_FUTURE_TIMESTAMP,
        stale_blocker=FundStructuralBlocker.FEE_STALE,
        max_age_days=active_policy.max_fee_age_days,
        blockers=blockers,
    )
    tracking_age_days = None
    if evidence.tracking_as_of is not None:
        tracking_age_days = _age_days(
            evidence.tracking_as_of,
            assessed_at=evaluation_time,
            future_tolerance_seconds=active_policy.future_tolerance_seconds,
            future_blocker=FundStructuralBlocker.TRACKING_FUTURE_TIMESTAMP,
            stale_blocker=FundStructuralBlocker.TRACKING_STALE,
            max_age_days=active_policy.max_tracking_age_days,
            blockers=blockers,
        )

    weights = [holding.weight for holding in evidence.holdings]
    top_1_weight = _top_weight(weights, 1)
    top_5_weight = _top_weight(weights, 5)
    top_10_weight = _top_weight(weights, 10)
    herfindahl_index = sum(
        (holding.weight * holding.weight for holding in evidence.holdings),
        Decimal("0"),
    )
    effective_holding_count = Decimal("1") / herfindahl_index

    existing_keys = {
        value.strip()
        for value in existing_portfolio_instrument_keys
        if value.strip()
    }
    overlap_pairs = sorted(
        (
            (holding.stable_key, holding.weight)
            for holding in evidence.holdings
            if holding.stable_key is not None and holding.stable_key in existing_keys
        ),
        key=lambda item: item[0],
    )
    overlapping_keys = tuple(key for key, _ in overlap_pairs)
    direct_overlap_weight = sum(
        (weight for _, weight in overlap_pairs),
        Decimal("0"),
    )

    derivative_exposure_weight = sum(
        (
            holding.weight
            for holding in evidence.holdings
            if holding.instrument_type in _DERIVATIVE_TYPES
        ),
        Decimal("0"),
    )
    fund_of_funds_exposure_weight = sum(
        (
            holding.weight
            for holding in evidence.holdings
            if holding.instrument_type is InstrumentType.ETF
        ),
        Decimal("0"),
    )
    cash_or_currency_weight = sum(
        (
            holding.weight
            for holding in evidence.holdings
            if holding.instrument_type is InstrumentType.CURRENCY
        ),
        Decimal("0"),
    )

    dominant_exposure = sorted(
        evidence.currency_exposures,
        key=lambda item: (-item.weight, item.currency),
    )[0]
    liquidity = bundle.liquidity
    spread_bps = liquidity.spread_bps if liquidity is not None else None
    turnover_24h = liquidity.turnover_24h if liquidity is not None else None
    unavailable_metrics: list[str] = []
    if evidence.tracking_difference_bps is None:
        unavailable_metrics.append("tracking_difference_bps")
    if evidence.tracking_error_bps is None:
        unavailable_metrics.append("tracking_error_bps")
    if spread_bps is None:
        unavailable_metrics.append("spread_bps")
    if turnover_24h is None:
        unavailable_metrics.append("turnover_24h")

    metrics = FundStructuralMetricsV1(
        holding_count=len(evidence.holdings),
        top_1_weight=top_1_weight,
        top_5_weight=top_5_weight,
        top_10_weight=top_10_weight,
        herfindahl_index=herfindahl_index,
        effective_holding_count=effective_holding_count,
        direct_overlap_weight=direct_overlap_weight,
        overlapping_holding_count=len(overlapping_keys),
        derivative_exposure_weight=derivative_exposure_weight,
        fund_of_funds_exposure_weight=fund_of_funds_exposure_weight,
        cash_or_currency_weight=cash_or_currency_weight,
        total_expense_ratio_bps=evidence.total_expense_ratio_bps,
        tracking_difference_bps=evidence.tracking_difference_bps,
        tracking_error_bps=evidence.tracking_error_bps,
        dominant_currency=dominant_exposure.currency,
        dominant_currency_weight=dominant_exposure.weight,
        currency_count=len(evidence.currency_exposures),
        spread_bps=spread_bps,
        turnover_24h=turnover_24h,
        overlapping_instrument_keys=overlapping_keys,
        unavailable_metrics=tuple(unavailable_metrics),
    )

    if top_1_weight > active_policy.max_single_holding_weight:
        _append_unique(
            warnings,
            FundStructuralWarning.HIGH_SINGLE_HOLDING_CONCENTRATION,
        )
    if top_10_weight > active_policy.max_top_ten_weight:
        _append_unique(
            warnings,
            FundStructuralWarning.HIGH_TOP_TEN_CONCENTRATION,
        )
    if evidence.total_expense_ratio_bps > active_policy.max_total_expense_ratio_bps:
        _append_unique(warnings, FundStructuralWarning.HIGH_EXPENSE_RATIO)
    if (
        evidence.tracking_error_bps is not None
        and evidence.tracking_error_bps > active_policy.max_tracking_error_bps
    ):
        _append_unique(warnings, FundStructuralWarning.HIGH_TRACKING_ERROR)
    if (
        evidence.tracking_difference_bps is not None
        and abs(evidence.tracking_difference_bps)
        > active_policy.max_absolute_tracking_difference_bps
    ):
        _append_unique(warnings, FundStructuralWarning.LARGE_TRACKING_DIFFERENCE)
    if (
        evidence.strategy_kind is FundStrategyKind.INDEX
        and evidence.tracking_error_bps is None
    ):
        _append_unique(warnings, FundStructuralWarning.TRACKING_STATISTICS_MISSING)
    if direct_overlap_weight > 0:
        _append_unique(warnings, FundStructuralWarning.DIRECT_HOLDING_OVERLAP)
    if derivative_exposure_weight > 0:
        _append_unique(
            warnings,
            FundStructuralWarning.DERIVATIVE_EXPOSURE_PRESENT,
        )
    if fund_of_funds_exposure_weight > 0:
        _append_unique(
            warnings,
            FundStructuralWarning.FUND_OF_FUNDS_EXPOSURE_PRESENT,
        )
    if dominant_exposure.weight >= active_policy.single_currency_warning_weight:
        _append_unique(
            warnings,
            FundStructuralWarning.SINGLE_CURRENCY_CONCENTRATION,
        )
    if evidence.replication_method is FundReplicationMethod.SYNTHETIC:
        _append_unique(warnings, FundStructuralWarning.SYNTHETIC_REPLICATION)

    analysis_ready = not blockers
    status = (
        FundStructuralStatus.READY
        if analysis_ready
        else FundStructuralStatus.REJECTED
    )
    return FundStructuralAssessmentV1(
        assessed_at=evaluation_time,
        status=status,
        analysis_ready=analysis_ready,
        instrument_key=evidence.instrument_key,
        currency=evidence.currency,
        structure_age_days=structure_age_days,
        fee_age_days=fee_age_days,
        tracking_age_days=tracking_age_days,
        policy=active_policy,
        market_readiness=market_readiness,
        metrics=metrics,
        blockers=tuple(blockers),
        warnings=tuple(warnings),
    )
