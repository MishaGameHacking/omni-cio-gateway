from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from decimal import Decimal

from omni_cio.contracts.v1.analytics import (
    AdvancedPortfolioAnalyticsV1,
    CurrencyPortfolioAnalyticsV1,
)
from omni_cio.contracts.v1.common import (
    Completeness,
    ContractMetadata,
    DataQuality,
    QualityMetadata,
    SourceReference,
)
from omni_cio.contracts.v1.decision import DecisionSetV1
from omni_cio.contracts.v1.rebalancing import (
    RebalanceAlternativeKind,
    RebalanceAlternativeStatus,
    RebalanceAlternativeV1,
    RebalanceBandStatus,
    RebalanceBlocker,
    RebalanceDirection,
    RebalanceLineV1,
    TargetBandV1,
    ThresholdRebalancePlanV1,
)


class RebalancingEngineError(ValueError):
    """The supplied target policy cannot form a safe deterministic plan."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise RebalancingEngineError("REBALANCE_TIMESTAMP_MUST_BE_AWARE")
    return result.astimezone(timezone.utc)


def _currency_row(
    analytics: AdvancedPortfolioAnalyticsV1,
    currency: str,
) -> CurrencyPortfolioAnalyticsV1:
    normalized = currency.upper()
    rows = [row for row in analytics.by_currency if row.currency == normalized]
    if len(rows) != 1:
        raise RebalancingEngineError("REBALANCE_CURRENCY_NOT_FOUND")
    return rows[0]


def _band_map(
    bands: Sequence[TargetBandV1],
    currency: str,
) -> dict[str, TargetBandV1]:
    normalized = currency.upper()
    result: dict[str, TargetBandV1] = {}
    for band in bands:
        if band.currency != normalized:
            raise RebalancingEngineError("TARGET_BAND_CURRENCY_MISMATCH")
        if band.stable_key in result:
            raise RebalancingEngineError("DUPLICATE_TARGET_BAND")
        result[band.stable_key] = band
    return result


def _line(
    *,
    stable_key: str,
    currency: str,
    current_value: Decimal,
    current_weight: Decimal,
    total: Decimal,
    band: TargetBandV1,
) -> RebalanceLineV1:
    target_value = band.target_weight * total
    if current_weight < band.lower_weight:
        status = RebalanceBandStatus.BELOW
        direction = RebalanceDirection.ADD
        nearest = band.lower_weight * total - current_value
        sale_required = False
    elif current_weight > band.upper_weight:
        status = RebalanceBandStatus.ABOVE
        direction = RebalanceDirection.REDUCE
        nearest = current_value - band.upper_weight * total
        sale_required = True
    else:
        status = RebalanceBandStatus.INSIDE
        direction = RebalanceDirection.NONE
        nearest = Decimal("0")
        sale_required = False
    return RebalanceLineV1(
        stable_key=stable_key,
        currency=currency,
        current_value=current_value,
        current_weight=current_weight,
        lower_weight=band.lower_weight,
        target_weight=band.target_weight,
        upper_weight=band.upper_weight,
        band_status=status,
        direction=direction,
        deviation_from_target=current_weight - band.target_weight,
        value_to_nearest_band=nearest,
        value_to_target=abs(target_value - current_value),
        sale_required=sale_required,
        execution_ready=False,
        trading_methods=False,
    )


def _build_lines(
    row: CurrencyPortfolioAnalyticsV1,
    bands: dict[str, TargetBandV1],
) -> tuple[tuple[RebalanceLineV1, ...], bool]:
    positions = {position.stable_key: position for position in row.positions}
    if set(bands) - set(positions):
        raise RebalancingEngineError("TARGET_BAND_REFERENCES_ABSENT_POSITION")
    coverage_complete = set(positions) == set(bands)
    lines = tuple(
        sorted(
            (
                _line(
                    stable_key=position.stable_key,
                    currency=row.currency,
                    current_value=position.full_market_value,
                    current_weight=position.portfolio_weight,
                    total=row.total,
                    band=bands[position.stable_key],
                )
                for position in row.positions
                if position.stable_key in bands
            ),
            key=lambda line: line.stable_key,
        )
    )
    return lines, coverage_complete


def _sum_by_status(
    lines: tuple[RebalanceLineV1, ...],
    status: RebalanceBandStatus,
) -> Decimal:
    return sum(
        (
            line.value_to_target
            for line in lines
            if line.band_status == status
        ),
        Decimal("0"),
    )


def _blocked_alternatives(
    deployable_cash: Decimal,
    blockers: tuple[RebalanceBlocker, ...],
) -> tuple[RebalanceAlternativeV1, ...]:
    return (
        RebalanceAlternativeV1(
            alternative_id="rebalance.no_action",
            kind=RebalanceAlternativeKind.NO_ACTION,
            status=RebalanceAlternativeStatus.PREFERRED,
            title="Do nothing until the plan is decision-ready",
            rationale="A source or target-coverage gate is open.",
            uses_sales=False,
            available_cash=deployable_cash,
            planned_add_value=Decimal("0"),
            planned_reduce_value=Decimal("0"),
            residual_cash=deployable_cash,
        ),
        RebalanceAlternativeV1(
            alternative_id="rebalance.cash_first",
            kind=RebalanceAlternativeKind.CASH_FIRST,
            status=RebalanceAlternativeStatus.BLOCKED,
            title="Use cash for underweight positions",
            rationale="Cash deployment is blocked until every gate closes.",
            uses_sales=False,
            available_cash=deployable_cash,
            planned_add_value=Decimal("0"),
            planned_reduce_value=Decimal("0"),
            residual_cash=deployable_cash,
            blockers=blockers,
        ),
        RebalanceAlternativeV1(
            alternative_id="rebalance.full_threshold",
            kind=RebalanceAlternativeKind.FULL_THRESHOLD,
            status=RebalanceAlternativeStatus.BLOCKED,
            title="Review full threshold repair",
            rationale="Sales and purchases are blocked until every gate closes.",
            uses_sales=False,
            available_cash=deployable_cash,
            planned_add_value=Decimal("0"),
            planned_reduce_value=Decimal("0"),
            residual_cash=deployable_cash,
            blockers=blockers,
        ),
    )


def _ready_alternatives(
    lines: tuple[RebalanceLineV1, ...],
    deployable_cash: Decimal,
    tax_basis_available: bool,
) -> tuple[RebalanceAlternativeV1, ...]:
    below_target = _sum_by_status(lines, RebalanceBandStatus.BELOW)
    above_target = _sum_by_status(lines, RebalanceBandStatus.ABOVE)
    cash_add = min(deployable_cash, below_target)
    has_breach = any(
        line.band_status != RebalanceBandStatus.INSIDE for line in lines
    )
    no_action_status = (
        RebalanceAlternativeStatus.AVAILABLE
        if has_breach and cash_add > 0
        else RebalanceAlternativeStatus.PREFERRED
    )
    cash_status = (
        RebalanceAlternativeStatus.PREFERRED
        if has_breach and cash_add > 0
        else RebalanceAlternativeStatus.AVAILABLE
    )
    no_action = RebalanceAlternativeV1(
        alternative_id="rebalance.no_action",
        kind=RebalanceAlternativeKind.NO_ACTION,
        status=no_action_status,
        title="Keep the current structure",
        rationale="This remains the lowest-turnover option.",
        uses_sales=False,
        available_cash=deployable_cash,
        planned_add_value=Decimal("0"),
        planned_reduce_value=Decimal("0"),
        residual_cash=deployable_cash,
    )
    cash_first = RebalanceAlternativeV1(
        alternative_id="rebalance.cash_first",
        kind=RebalanceAlternativeKind.CASH_FIRST,
        status=cash_status,
        title="Direct available cash to underweight positions",
        rationale=(
            "Use cash without selling holdings; exact instruments, lots and costs require PR-14."
        ),
        uses_sales=False,
        available_cash=deployable_cash,
        planned_add_value=cash_add,
        planned_reduce_value=Decimal("0"),
        residual_cash=deployable_cash - cash_add,
    )
    full_blockers = [RebalanceBlocker.LIVE_PREVIEW_REQUIRED]
    if above_target > 0 and not tax_basis_available:
        full_blockers.append(RebalanceBlocker.SALES_REQUIRE_TAX_BASIS)
    funding = deployable_cash + above_target
    full_add = min(funding, below_target)
    full = RebalanceAlternativeV1(
        alternative_id="rebalance.full_threshold",
        kind=RebalanceAlternativeKind.FULL_THRESHOLD,
        status=RebalanceAlternativeStatus.BLOCKED,
        title="Review full threshold repair",
        rationale=(
            "This scenario may combine reductions and additions but remains blocked until a live preview validates costs and constraints."
        ),
        uses_sales=above_target > 0,
        available_cash=deployable_cash,
        planned_add_value=full_add,
        planned_reduce_value=above_target,
        residual_cash=funding - full_add,
        blockers=tuple(full_blockers),
    )
    return no_action, cash_first, full


def build_threshold_rebalance_plan(
    analytics: AdvancedPortfolioAnalyticsV1,
    decision: DecisionSetV1,
    target_bands: Sequence[TargetBandV1],
    *,
    currency: str,
    deployable_cash: Decimal = Decimal("0"),
    tax_basis_available: bool = False,
    planned_at: datetime | None = None,
) -> ThresholdRebalancePlanV1:
    """Build one currency-local read-only plan without order parameters."""
    timestamp = _aware_utc(planned_at)
    row = _currency_row(analytics, currency)
    if deployable_cash.is_nan() or deployable_cash.is_infinite() or deployable_cash < 0:
        raise RebalancingEngineError("INVALID_DEPLOYABLE_CASH")
    if deployable_cash > row.cash:
        raise RebalancingEngineError("DEPLOYABLE_CASH_EXCEEDS_PORTFOLIO_CASH")
    bands = _band_map(target_bands, row.currency)
    lines, coverage_complete = _build_lines(row, bands)
    source_ready = (
        decision.recommendation_ready
        and not decision.abstain
        and decision.metadata.account == analytics.metadata.account
    )
    plan_ready = source_ready and coverage_complete
    if plan_ready:
        alternatives = _ready_alternatives(
            lines,
            deployable_cash,
            tax_basis_available,
        )
    else:
        blockers: list[RebalanceBlocker] = []
        if not source_ready:
            blockers.append(RebalanceBlocker.DECISION_NOT_READY)
        if not coverage_complete:
            blockers.append(RebalanceBlocker.TARGET_COVERAGE_INCOMPLETE)
        alternatives = _blocked_alternatives(deployable_cash, tuple(blockers))
    preferred = next(
        alternative
        for alternative in alternatives
        if alternative.status == RebalanceAlternativeStatus.PREFERRED
    )
    below_count = sum(
        line.band_status == RebalanceBandStatus.BELOW for line in lines
    )
    above_count = sum(
        line.band_status == RebalanceBandStatus.ABOVE for line in lines
    )
    inside_count = sum(
        line.band_status == RebalanceBandStatus.INSIDE for line in lines
    )
    warnings = [
        "Plan is analytical only; live prices, lots, commissions and taxes require PR-14."
    ]
    if not coverage_complete:
        warnings.append("Target-band coverage is incomplete.")
    if not source_ready:
        warnings.append("Source DecisionSetV1 is not recommendation-ready.")
    metadata = ContractMetadata(
        schema_name="threshold_rebalance_plan",
        retrieved_at=timestamp,
        account=analytics.metadata.account,
        provenance=(
            *analytics.metadata.provenance,
            *decision.metadata.provenance,
            SourceReference(
                provider="omni-cio",
                operation="build_threshold_rebalance_plan",
                retrieved_at=timestamp,
                source_id=f"1.0:{row.currency}",
            ),
        ),
        quality=QualityMetadata(
            quality=(DataQuality.VERIFIED if plan_ready else DataQuality.PARTIAL),
            completeness=(
                Completeness.COMPLETE if plan_ready else Completeness.PARTIAL
            ),
            warnings=tuple(warnings),
        ),
    )
    return ThresholdRebalancePlanV1(
        metadata=metadata,
        source_decision_schema_version=decision.metadata.schema_version,
        lines=lines,
        alternatives=alternatives,
        preferred_alternative_id=preferred.alternative_id,
        decision_ready=plan_ready,
        no_cross_currency_aggregation=True,
        breach_count=below_count + above_count,
        below_count=below_count,
        above_count=above_count,
        inside_count=inside_count,
        execution_ready=False,
        trading_methods=False,
    )
