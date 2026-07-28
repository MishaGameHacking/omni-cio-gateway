from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, timezone
from decimal import Decimal

from omni_cio.contracts.v1.analytics import (
    AdvancedPortfolioAnalyticsV1,
    AssetClassAllocationV1,
    ConcentrationMetricsV1,
    CurrencyPortfolioAnalyticsV1,
    MissingDataCode,
    MissingDataV1,
    PositionWeightV1,
    StressScenarioV1,
)
from omni_cio.contracts.v1.common import (
    Completeness,
    ContractMetadata,
    DataQuality,
    IssueSeverity,
    QualityMetadata,
    SourceReference,
)
from omni_cio.contracts.v1.portfolio import (
    InstrumentType,
    PortfolioPositionV1,
    PortfolioSnapshotV1,
    ValuationBasis,
)


class AdvancedPortfolioAnalyticsError(ValueError):
    """The source snapshot is not safe or complete enough for analytics."""


DEFAULT_STRESS_SHOCKS = (
    Decimal("-0.10"),
    Decimal("-0.20"),
    Decimal("-0.30"),
)


def _ratio(numerator: Decimal, denominator: Decimal) -> Decimal:
    return numerator / denominator if denominator > 0 else Decimal("0")


def _require_aware_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise AdvancedPortfolioAnalyticsError("ANALYTICS_TIMESTAMP_MUST_BE_AWARE")
    return value.astimezone(timezone.utc)


def _require_verified_snapshot(snapshot: PortfolioSnapshotV1) -> None:
    quality = snapshot.metadata.quality
    blocking_issue = any(
        issue.severity in (IssueSeverity.WARNING, IssueSeverity.ERROR)
        for issue in quality.issues
    )
    if (
        quality.quality != DataQuality.VERIFIED
        or quality.completeness != Completeness.COMPLETE
        or blocking_issue
    ):
        raise AdvancedPortfolioAnalyticsError(
            "PORTFOLIO_SNAPSHOT_NOT_DECISION_READY"
        )
    for position in snapshot.positions:
        valuation = position.valuation
        if (
            valuation is None
            or valuation.basis != ValuationBasis.LAST_PRICE
            or valuation.market_value is None
            or valuation.as_of is None
        ):
            raise AdvancedPortfolioAnalyticsError(
                "PORTFOLIO_POSITION_VALUATION_INCOMPLETE"
            )
        if valuation.currency != position.instrument.currency:
            raise AdvancedPortfolioAnalyticsError(
                "PORTFOLIO_POSITION_CURRENCY_MISMATCH"
            )


def _validate_shocks(shocks: Iterable[Decimal]) -> tuple[Decimal, ...]:
    result = tuple(shocks)
    if not result:
        raise AdvancedPortfolioAnalyticsError("STRESS_SHOCKS_REQUIRED")
    if len(result) != len(set(result)):
        raise AdvancedPortfolioAnalyticsError("STRESS_SHOCKS_MUST_BE_UNIQUE")
    if any(shock <= Decimal("-1") or shock >= 0 for shock in result):
        raise AdvancedPortfolioAnalyticsError("STRESS_SHOCK_OUT_OF_RANGE")
    return tuple(sorted(result, reverse=True))


def _full_value(position: PortfolioPositionV1) -> Decimal:
    valuation = position.valuation
    if valuation is None or valuation.market_value is None:
        raise AdvancedPortfolioAnalyticsError(
            "PORTFOLIO_POSITION_VALUATION_INCOMPLETE"
        )
    accrued = (
        valuation.accrued_interest.amount
        if valuation.accrued_interest is not None
        else Decimal("0")
    )
    full_value = valuation.market_value.amount + accrued
    if full_value < 0:
        raise AdvancedPortfolioAnalyticsError(
            "PORTFOLIO_POSITION_VALUE_NEGATIVE"
        )
    return full_value


def _position_rows(
    positions: tuple[PortfolioPositionV1, ...],
    *,
    currency: str,
    total: Decimal,
    invested_value: Decimal,
) -> tuple[PositionWeightV1, ...]:
    rows: list[PositionWeightV1] = []
    for position in positions:
        full_value = _full_value(position)
        rows.append(
            PositionWeightV1(
                stable_key=position.instrument.stable_key(),
                name=position.instrument.name,
                ticker=position.instrument.ticker,
                instrument_type=position.instrument.instrument_type,
                currency=currency,
                full_market_value=full_value,
                portfolio_weight=_ratio(full_value, total),
                invested_weight=_ratio(full_value, invested_value),
            )
        )
    rows.sort(key=lambda row: (row.full_market_value, row.stable_key), reverse=True)
    return tuple(rows)


def _asset_classes(
    positions: tuple[PositionWeightV1, ...],
    *,
    total: Decimal,
    invested_value: Decimal,
) -> tuple[AssetClassAllocationV1, ...]:
    values: dict[InstrumentType, Decimal] = defaultdict(lambda: Decimal("0"))
    counts: dict[InstrumentType, int] = defaultdict(int)
    for position in positions:
        values[position.instrument_type] += position.full_market_value
        counts[position.instrument_type] += 1
    rows = [
        AssetClassAllocationV1(
            instrument_type=instrument_type,
            full_market_value=value,
            position_count=counts[instrument_type],
            portfolio_weight=_ratio(value, total),
            invested_weight=_ratio(value, invested_value),
        )
        for instrument_type, value in values.items()
    ]
    rows.sort(
        key=lambda row: (row.full_market_value, row.instrument_type.value),
        reverse=True,
    )
    return tuple(rows)


def _concentration(
    positions: tuple[PositionWeightV1, ...],
) -> ConcentrationMetricsV1:
    portfolio_weights = [row.portfolio_weight for row in positions]
    invested_weights = [row.invested_weight for row in positions]
    hhi = sum((weight * weight for weight in invested_weights), Decimal("0"))
    return ConcentrationMetricsV1(
        top_1_portfolio_weight=sum(portfolio_weights[:1], Decimal("0")),
        top_5_portfolio_weight=sum(portfolio_weights[:5], Decimal("0")),
        top_1_invested_weight=sum(invested_weights[:1], Decimal("0")),
        top_5_invested_weight=sum(invested_weights[:5], Decimal("0")),
        hhi_invested=hhi,
        effective_position_count=(Decimal("1") / hhi if hhi > 0 else Decimal("0")),
    )


def _stress_scenarios(
    shocks: tuple[Decimal, ...],
    *,
    invested_value: Decimal,
    total: Decimal,
) -> tuple[StressScenarioV1, ...]:
    rows = []
    for shock in shocks:
        change = invested_value * shock
        rows.append(
            StressScenarioV1(
                shock=shock,
                starting_invested_value=invested_value,
                starting_total=total,
                invested_change=change,
                portfolio_change=change,
                stressed_invested_value=invested_value + change,
                stressed_total=total + change,
                portfolio_change_ratio=_ratio(change, total),
            )
        )
    return tuple(rows)


def _missing_data(has_bonds: bool) -> tuple[MissingDataV1, ...]:
    rows = [
        MissingDataV1(
            code=MissingDataCode.ISSUER,
            message="Issuer identity is absent from portfolio contract v1.",
            affected_calculations=("issuer_allocation", "issuer_concentration"),
        ),
        MissingDataV1(
            code=MissingDataCode.SECTOR,
            message="Sector classification is absent from portfolio contract v1.",
            affected_calculations=("sector_allocation", "sector_concentration"),
        ),
        MissingDataV1(
            code=MissingDataCode.LIQUIDITY,
            message="Order-book depth, spread and turnover are not present.",
            affected_calculations=("liquidity_score", "exit_cost", "market_capacity"),
        ),
        MissingDataV1(
            code=MissingDataCode.HISTORICAL_PRICES,
            message="Historical price series are not present in the snapshot.",
            affected_calculations=("returns", "risk_history"),
        ),
        MissingDataV1(
            code=MissingDataCode.MAX_DRAWDOWN,
            message="Maximum drawdown requires a historical portfolio series.",
            affected_calculations=("max_drawdown",),
        ),
        MissingDataV1(
            code=MissingDataCode.VOLATILITY,
            message="Volatility requires a historical return series.",
            affected_calculations=("volatility",),
        ),
        MissingDataV1(
            code=MissingDataCode.CORRELATION,
            message="Correlation requires aligned historical return series.",
            affected_calculations=("correlation", "diversification_benefit"),
        ),
        MissingDataV1(
            code=MissingDataCode.TAX_BASIS,
            message="Tax lots and acquisition cost basis are not present.",
            affected_calculations=("unrealized_pnl", "tax_impact"),
        ),
    ]
    if has_bonds:
        rows.extend(
            (
                MissingDataV1(
                    code=MissingDataCode.BOND_DURATION,
                    message="Bond duration is absent from portfolio contract v1.",
                    affected_calculations=("duration", "rate_sensitivity"),
                ),
                MissingDataV1(
                    code=MissingDataCode.BOND_MATURITY,
                    message="Bond maturity and offer dates are absent.",
                    affected_calculations=("maturity_ladder", "cash_flow_schedule"),
                ),
                MissingDataV1(
                    code=MissingDataCode.CREDIT_RATING,
                    message="Current issue and issuer ratings are absent.",
                    affected_calculations=("credit_quality", "default_risk"),
                ),
            )
        )
    return tuple(rows)


def build_advanced_portfolio_analytics(
    snapshot: PortfolioSnapshotV1,
    *,
    stress_shocks: Iterable[Decimal] = DEFAULT_STRESS_SHOCKS,
    retrieved_at: datetime | None = None,
) -> AdvancedPortfolioAnalyticsV1:
    """Build exact, currency-local analytics from a verified portfolio snapshot."""
    _require_verified_snapshot(snapshot)
    shocks = _validate_shocks(stress_shocks)
    calculated_at = _require_aware_timestamp(
        retrieved_at or datetime.now(timezone.utc)
    )

    totals = {row.currency: row for row in snapshot.totals_by_currency}
    positions_by_currency: dict[str, list[PortfolioPositionV1]] = defaultdict(list)
    for position in snapshot.positions:
        valuation = position.valuation
        if valuation is None:
            raise AdvancedPortfolioAnalyticsError(
                "PORTFOLIO_POSITION_VALUATION_INCOMPLETE"
            )
        positions_by_currency[valuation.currency].append(position)

    missing_currency_totals = set(positions_by_currency) - set(totals)
    if missing_currency_totals:
        raise AdvancedPortfolioAnalyticsError(
            "PORTFOLIO_POSITION_CURRENCY_TOTAL_MISSING"
        )

    rows: list[CurrencyPortfolioAnalyticsV1] = []
    for currency, total_row in sorted(totals.items()):
        source_positions = tuple(positions_by_currency.get(currency, ()))
        invested_value = total_row.securities + total_row.accrued_interest
        full_position_value = sum(
            (_full_value(position) for position in source_positions),
            Decimal("0"),
        )
        if full_position_value != invested_value:
            raise AdvancedPortfolioAnalyticsError(
                "PORTFOLIO_POSITION_TOTAL_RECONCILIATION_FAILED"
            )
        if total_row.total != total_row.cash + invested_value:
            raise AdvancedPortfolioAnalyticsError(
                "PORTFOLIO_CURRENCY_TOTAL_RECONCILIATION_FAILED"
            )

        positions = _position_rows(
            source_positions,
            currency=currency,
            total=total_row.total,
            invested_value=invested_value,
        )
        rows.append(
            CurrencyPortfolioAnalyticsV1(
                currency=currency,
                cash=total_row.cash,
                clean_securities=total_row.securities,
                accrued_interest=total_row.accrued_interest,
                invested_value=invested_value,
                total=total_row.total,
                cash_weight=_ratio(total_row.cash, total_row.total),
                invested_weight=_ratio(invested_value, total_row.total),
                position_count=len(source_positions),
                valued_position_count=len(positions),
                positions=positions,
                asset_classes=_asset_classes(
                    positions,
                    total=total_row.total,
                    invested_value=invested_value,
                ),
                concentration=_concentration(positions),
                stress_scenarios=_stress_scenarios(
                    shocks,
                    invested_value=invested_value,
                    total=total_row.total,
                ),
            )
        )

    has_bonds = any(
        position.instrument.instrument_type == InstrumentType.BOND
        for position in snapshot.positions
    )
    metadata = ContractMetadata(
        schema_name="advanced_portfolio_analytics",
        retrieved_at=calculated_at,
        account=snapshot.metadata.account,
        provenance=(
            *snapshot.metadata.provenance,
            SourceReference(
                provider="omni-cio",
                operation="build_advanced_portfolio_analytics",
                retrieved_at=calculated_at,
                source_id=snapshot.metadata.schema_version,
            ),
        ),
        quality=QualityMetadata(
            quality=DataQuality.VERIFIED,
            completeness=Completeness.COMPLETE,
            issues=(),
            warnings=(
                "Currencies are analyzed independently without implicit FX conversion.",
            ),
        ),
    )
    return AdvancedPortfolioAnalyticsV1(
        metadata=metadata,
        source_snapshot_retrieved_at=snapshot.metadata.retrieved_at,
        by_currency=tuple(rows),
        missing_data=_missing_data(has_bonds),
        no_cross_currency_aggregation=True,
        decision_ready=True,
    )
