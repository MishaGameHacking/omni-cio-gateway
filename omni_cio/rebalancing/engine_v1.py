from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from decimal import Decimal

from omni_cio.contracts.v1.analytics import AdvancedPortfolioAnalyticsV1
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


def _band_map(
    bands: Sequence[TargetBandV1],
) -> dict[tuple[str, str], TargetBandV1]:
    result: dict[tuple[str, str], TargetBandV1] = {}
    for band in bands:
        key = (band.currency, band.stable_key)
        if key in result:
            raise RebalancingEngineError("DUPLICATE_TARGET_BAND")
        result[key] = band
    return result


def _deployable_cash(
    analytics: AdvancedPortfolioAnalyticsV1,
    requested: Mapping[str, Decimal],
) -> dict[str, Decimal]:
    available = {row.currency: row.cash for row in analytics.by_currency}
    normalized: dict[str, Decimal] = {}
    for raw_currency, value in requested.items():
        currency = raw_currency.upper()
        if value.is_nan() or value.is_infinite() or value < 0:
            raise RebalancingEngineError("INVALID_DEPLOYABLE_CASH")
        if currency not in available:
            raise RebalancingEngineError("UNKNOWN_DEPLOYABLE_CASH_CURRENCY")
        if value > available[currency]:
            raise RebalancingEngineError("DEPLOYABLE_CASH_EXCEEDS_PORTFOLIO_CASH")
        normalized[currency] = value
    return normalized


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
    analytics: AdvancedPortfolioAnalyticsV1,
    bands: dict[tuple[str, str], TargetBandV1],
) -> tuple[tuple[RebalanceLineV1, ...], bool]:
    lines: list[RebalanceLineV1] = []
    coverage_complete = True
    portfolio_keys: set[tuple[str, str]] = set()
    for currency_row in analytics.by_currency:
        for position in currency_row.positions:
            key = (currency_row.currency, position.stable_key)
            portfolio_keys.add(key)
            band = bands.get(key)
            if band is None:
                coverage_complete = False
                continue
            lines.append(
                _line(
                    stable_key=position.stable_key,
                    currency=currency_row.currency,
                    current_value=position.full_market_value,
                    current_weight=position.portfolio_weight,
                    total=currency_row.total,
                    band=band,
                )
            )
    if set(bands) - portfolio_keys:
        raise RebalancingEngineError("TARGET_BAND_REFERENCES_ABSENT_POSITION")
    lines.sort(key=lambda row: (row.currency, row.stable_key))
    return tuple(lines), coverage_complete


def _sum_by_status(
    lines: tuple[RebalanceLineV1, ...],
    status: RebalanceBandStatus,
    *,
    to_target: bool,
) -> Decimal:
    return sum(
        (
            line.value_to_target if to_target else line.value_to_nearest_band
            for line in lines
            if line.band_status == status
        ),
        Decimal("0"),
    )


def _alternatives(
    *,
    decision_ready: bool,
    lines: tuple[RebalanceLineV1, ...],
    deployable_cash: Decimal,
    tax_basis_available: bool,
) -> tuple[RebalanceAlternativeV1, ...]:
    below_target = _sum_by_status(
        lines,
        RebalanceBandStatus.BELOW,
        to_target=True,
    )
    above_target = _sum_by_status(
        lines,
        RebalanceBandStatus.ABOVE,
        to_target=True,
    )
    has_breach = any(
        line.band_status != RebalanceBandStatus.INSIDE for line in lines
    )

    if not decision_ready:
        blockers = (RebalanceBlocker.DECISION_NOT_READY,)
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
                rationale="Cash deployment is blocked until all gates close.",
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
                rationale="Sales and purchases are blocked until all gates close.",
                uses_sales=False,
                available_cash=deployable_cash,
                planned_add_value=Decimal("0"),
                planned_reduce_value=Decimal("0"),
                residual_cash=deployable_cash,
                blockers=blockers,
            ),
        )

    cash_add = min(deployable_cash, below_target)
    if has_breach and cash_add > 0:
        no_action_status = RebalanceAlternativeStatus.AVAILABLE
        cash_status = RebalanceAlternativeStatus.PREFERRED
    else:
        no_action_status = RebalanceAlternativeStatus.PREFERRED
        cash_status = RebalanceAlternativeStatus.AVAILABLE

    no_action = RebalanceAlternativeV1(
        alternative_id="rebalance.no_action",
        kind=RebalanceAlternativeKind.NO_ACTION,
        status=no_action_status,
        title="Keep the current structure",
        rationale=(
            "No transaction is required immediately; this remains the lowest-turnover option."
        ),
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
            "Use existing cash without selling holdings; exact instruments, lots and costs require PR-14."
        ),
        uses_sales=False,
        available_cash=deployable_cash,
        planned_add_value=cash_add,
        planned_reduce_value=Decimal("0"),
        residual_cash=deployable_cash - cash_add,
    )

    full_blockers: list[RebalanceBlocker] = [
        RebalanceBlocker.LIVE_PREVIEW_REQUIRED
    ]
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
            "This scenario may combine reductions and additions, but remains blocked until tax basis and live preview are available."
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
    deployable_cash_by_currency: Mapping[str, Decimal] | None = None,
    tax_basis_available: bool = False,
    planned_at: datetime | None = None,
) -> ThresholdRebalancePlanV1:
    """Build a read-only threshold plan without lot, price or order parameters."""
    timestamp = _aware_utc(planned_at)
    bands = _band_map(target_bands)
    cash_map = _deployable_cash(
        analytics,
        deployable_cash_by_currency or {},
    )
    lines, coverage_complete = _build_lines(analytics, bands)
    source_ready = (
        decision.recommendation_ready
        and not decision.abstain
        and decision.metadata.account == analytics.metadata.account
    )
    plan_ready = source_ready and coverage_complete
    total_deployable_cash = sum(cash_map.values(), Decimal("0"))
    alternatives = _alternatives(
        decision_ready=plan_ready,
        lines=lines,
        deployable_cash=total_deployable_cash,
        tax_basis_available=tax_basis_available,
    )
    preferred = next(
        row
        for row in alternatives
        if row.status == RebalanceAlternativeStatus.PREFERRED
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
    quality = DataQuality.VERIFIED if plan_ready else DataQuality.PARTIAL
    completeness = Completeness.COMPLETE if plan_ready else Completeness.PARTIAL
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
                source_id="1.0",
            ),
        ),
        quality=QualityMetadata(
            quality=quality,
            completeness=completeness,
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
