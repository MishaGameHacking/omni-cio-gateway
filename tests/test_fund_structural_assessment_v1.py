from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1.common import (
    Completeness,
    DataQuality,
    QualityMetadata,
)
from omni_cio.contracts.v1.fund_structure import (
    FundCurrencyExposureV1,
    FundHoldingV1,
    FundReplicationMethod,
    FundStructuralBlocker,
    FundStructuralEvidenceV1,
    FundStructuralMetricsV1,
    FundStructuralStatus,
    FundStructuralWarning,
    FundStrategyKind,
)
from omni_cio.contracts.v1.market import (
    ComponentStateV1,
    ComponentStatus,
    InstrumentReferenceV1,
    MarketLiquidityV1,
    MarketQuoteV1,
    MarketResearchBundleV1,
    MarketResearchMetadataV1,
    MarketSourceV1,
    SourceAuthority,
)
from omni_cio.contracts.v1.portfolio import InstrumentType
from omni_cio.market.fund_structure_v1 import (
    FundStructuralAssessmentError,
    assess_fund_structure,
)


NOW = datetime(2026, 7, 29, 13, 30, tzinfo=timezone.utc)
KEY = "uid:fund-a"


def _source(
    *,
    authority: SourceAuthority = SourceAuthority.OFFICIAL,
    retrieved_at: datetime = NOW,
    provider: str = "synthetic-official-source",
) -> MarketSourceV1:
    return MarketSourceV1(
        provider=provider,
        authority=authority,
        retrieved_at=retrieved_at,
        source_id=f"{provider}-record",
    )


def _state(
    *,
    count: int,
    status: ComponentStatus = ComponentStatus.OK,
    checked_at: datetime | None = NOW,
    source: MarketSourceV1 | None = None,
) -> ComponentStateV1:
    active_source = source
    if active_source is None and status in (
        ComponentStatus.OK,
        ComponentStatus.DEGRADED,
    ):
        active_source = _source()
    return ComponentStateV1(
        status=status,
        source=active_source,
        checked_at=checked_at,
        record_count=count,
    )


def _reference(
    *,
    instrument_type: InstrumentType = InstrumentType.ETF,
    currency: str = "RUB",
    stable_key: str = KEY,
) -> InstrumentReferenceV1:
    return InstrumentReferenceV1(
        stable_key=stable_key,
        name="Synthetic fund",
        ticker="SFUND",
        uid="fund-a",
        instrument_type=instrument_type,
        currency=currency,
        lot=1,
        issuer_id="management-company-a",
        sector="funds",
        source=_source(authority=SourceAuthority.PRIMARY),
    )


def _bundle(
    *,
    instrument_type: InstrumentType = InstrumentType.ETF,
    currency: str = "RUB",
    stable_key: str = KEY,
    quote_as_of: datetime = NOW,
) -> MarketResearchBundleV1:
    quote = MarketQuoteV1(
        instrument_key=stable_key,
        currency=currency,
        as_of=quote_as_of,
        source=_source(),
        last_price=Decimal("100"),
        best_bid=Decimal("99.9"),
        best_ask=Decimal("100.1"),
    )
    liquidity = MarketLiquidityV1(
        instrument_key=stable_key,
        currency=currency,
        as_of=NOW,
        source=_source(),
        best_bid=Decimal("99.9"),
        best_ask=Decimal("100.1"),
        spread_absolute=Decimal("0.2"),
        spread_bps=Decimal("20"),
        bid_depth=Decimal("1000000"),
        ask_depth=Decimal("1200000"),
        turnover_24h=Decimal("50000000"),
    )
    not_applicable = _state(
        count=0,
        status=ComponentStatus.NOT_APPLICABLE,
        checked_at=None,
    )
    return MarketResearchBundleV1(
        metadata=MarketResearchMetadataV1(
            retrieved_at=NOW,
            quality=QualityMetadata(
                quality=DataQuality.VERIFIED,
                completeness=Completeness.COMPLETE,
            ),
        ),
        instrument_key=stable_key,
        reference_state=_state(count=1),
        quote_state=_state(count=1),
        liquidity_state=_state(count=1),
        ratings_state=not_applicable,
        bond_metrics_state=not_applicable,
        events_state=_state(count=0),
        reference=_reference(
            instrument_type=instrument_type,
            currency=currency,
            stable_key=stable_key,
        ),
        quote=quote,
        liquidity=liquidity,
        events=(),
        trading_methods=False,
    )


def _holdings() -> tuple[FundHoldingV1, ...]:
    return (
        FundHoldingV1(
            stable_key="uid:share-a",
            name="Share A",
            instrument_type=InstrumentType.SHARE,
            currency="RUB",
            weight=Decimal("0.30"),
            issuer_id="issuer-a",
        ),
        FundHoldingV1(
            stable_key="uid:share-b",
            name="Share B",
            instrument_type=InstrumentType.SHARE,
            currency="RUB",
            weight=Decimal("0.25"),
            issuer_id="issuer-b",
        ),
        FundHoldingV1(
            stable_key="uid:bond-c",
            name="Bond C",
            instrument_type=InstrumentType.BOND,
            currency="RUB",
            weight=Decimal("0.20"),
            issuer_id="issuer-c",
        ),
        FundHoldingV1(
            stable_key="uid:fund-d",
            name="Fund D",
            instrument_type=InstrumentType.ETF,
            currency="USD",
            weight=Decimal("0.10"),
            issuer_id="manager-d",
        ),
        FundHoldingV1(
            stable_key="uid:future-e",
            name="Future E",
            instrument_type=InstrumentType.FUTURE,
            currency="RUB",
            weight=Decimal("0.05"),
        ),
        FundHoldingV1(
            name="Cash",
            instrument_type=InstrumentType.CURRENCY,
            currency="RUB",
            weight=Decimal("0.10"),
        ),
    )


def _evidence(
    *,
    authority: SourceAuthority = SourceAuthority.OFFICIAL,
    strategy_kind: FundStrategyKind = FundStrategyKind.INDEX,
    replication_method: FundReplicationMethod = FundReplicationMethod.FULL_PHYSICAL,
    benchmark_name: str | None = "Synthetic Total Return Index",
    structure_as_of: datetime = NOW - timedelta(days=1),
    fee_as_of: datetime = NOW - timedelta(days=30),
    tracking_as_of: datetime | None = NOW - timedelta(days=10),
    total_expense_ratio_bps: Decimal = Decimal("45"),
    tracking_difference_bps: Decimal | None = Decimal("-35"),
    tracking_error_bps: Decimal | None = Decimal("80"),
    currency: str = "RUB",
    instrument_key: str = KEY,
    source_retrieved_at: datetime = NOW,
) -> FundStructuralEvidenceV1:
    source = _source(
        authority=authority,
        retrieved_at=source_retrieved_at,
        provider="synthetic-fund-disclosure",
    )
    tracking_source = source if tracking_as_of is not None else None
    return FundStructuralEvidenceV1(
        instrument_key=instrument_key,
        currency=currency,
        strategy_kind=strategy_kind,
        replication_method=replication_method,
        management_company="Synthetic Management Company",
        benchmark_name=benchmark_name,
        structure_as_of=structure_as_of,
        structure_source=source,
        fee_as_of=fee_as_of,
        fee_source=source,
        tracking_as_of=tracking_as_of,
        tracking_source=tracking_source,
        total_expense_ratio_bps=total_expense_ratio_bps,
        tracking_difference_bps=tracking_difference_bps,
        tracking_error_bps=tracking_error_bps,
        holdings=_holdings(),
        currency_exposures=(
            FundCurrencyExposureV1(currency="RUB", weight=Decimal("0.90")),
            FundCurrencyExposureV1(currency="USD", weight=Decimal("0.10")),
        ),
    )


def test_ready_index_fund_calculates_exact_structure_and_overlap() -> None:
    result = assess_fund_structure(
        _bundle(),
        _evidence(),
        existing_portfolio_instrument_keys=("uid:share-a", "uid:bond-c"),
        assessed_at=NOW,
    )

    assert result.status is FundStructuralStatus.READY
    assert result.analysis_ready is True
    assert result.blockers == ()
    assert result.metrics.holding_count == 6
    assert result.metrics.top_1_weight == Decimal("0.30")
    assert result.metrics.top_5_weight == Decimal("0.95")
    assert result.metrics.top_10_weight == Decimal("1.00")
    assert result.metrics.herfindahl_index == Decimal("0.2150")
    assert result.metrics.effective_holding_count == Decimal("1") / Decimal("0.2150")
    assert result.metrics.direct_overlap_weight == Decimal("0.50")
    assert result.metrics.overlapping_instrument_keys == (
        "uid:bond-c",
        "uid:share-a",
    )
    assert result.metrics.derivative_exposure_weight == Decimal("0.05")
    assert result.metrics.fund_of_funds_exposure_weight == Decimal("0.10")
    assert result.metrics.cash_or_currency_weight == Decimal("0.10")
    assert result.metrics.spread_bps == Decimal("20")
    assert result.metrics.turnover_24h == Decimal("50000000")
    assert FundStructuralWarning.DIRECT_HOLDING_OVERLAP in result.warnings
    assert FundStructuralWarning.DERIVATIVE_EXPOSURE_PRESENT in result.warnings
    assert FundStructuralWarning.FUND_OF_FUNDS_EXPOSURE_PRESENT in result.warnings


def test_index_fund_without_tracking_statistics_is_explicitly_incomplete() -> None:
    evidence = _evidence(
        tracking_as_of=None,
        tracking_difference_bps=None,
        tracking_error_bps=None,
    )

    result = assess_fund_structure(_bundle(), evidence, assessed_at=NOW)

    assert result.analysis_ready is True
    assert result.tracking_age_days is None
    assert FundStructuralWarning.TRACKING_STATISTICS_MISSING in result.warnings
    assert "tracking_difference_bps" in result.metrics.unavailable_metrics
    assert "tracking_error_bps" in result.metrics.unavailable_metrics


def test_active_fund_does_not_require_tracking_statistics() -> None:
    evidence = _evidence(
        strategy_kind=FundStrategyKind.ACTIVE,
        replication_method=FundReplicationMethod.ACTIVE_SELECTION,
        benchmark_name=None,
        tracking_as_of=None,
        tracking_difference_bps=None,
        tracking_error_bps=None,
    )

    result = assess_fund_structure(_bundle(), evidence, assessed_at=NOW)

    assert result.analysis_ready is True
    assert FundStructuralWarning.TRACKING_STATISTICS_MISSING not in result.warnings


def test_high_cost_tracking_and_synthetic_structure_are_warnings_not_forecasts() -> None:
    evidence = _evidence(
        replication_method=FundReplicationMethod.SYNTHETIC,
        total_expense_ratio_bps=Decimal("250"),
        tracking_difference_bps=Decimal("-450"),
        tracking_error_bps=Decimal("400"),
    )

    result = assess_fund_structure(_bundle(), evidence, assessed_at=NOW)

    assert result.analysis_ready is True
    assert FundStructuralWarning.HIGH_EXPENSE_RATIO in result.warnings
    assert FundStructuralWarning.HIGH_TRACKING_ERROR in result.warnings
    assert FundStructuralWarning.LARGE_TRACKING_DIFFERENCE in result.warnings
    assert FundStructuralWarning.SYNTHETIC_REPLICATION in result.warnings
    assert result.no_price_forecast is True
    assert result.no_investment_recommendation is True


def test_stale_and_untrusted_evidence_fail_closed() -> None:
    evidence = _evidence(
        authority=SourceAuthority.SECONDARY,
        structure_as_of=NOW - timedelta(days=60),
        fee_as_of=NOW - timedelta(days=600),
        tracking_as_of=NOW - timedelta(days=600),
    )

    result = assess_fund_structure(_bundle(), evidence, assessed_at=NOW)

    assert result.status is FundStructuralStatus.REJECTED
    assert FundStructuralBlocker.UNTRUSTED_SOURCE in result.blockers
    assert FundStructuralBlocker.STRUCTURE_STALE in result.blockers
    assert FundStructuralBlocker.FEE_STALE in result.blockers
    assert FundStructuralBlocker.TRACKING_STALE in result.blockers


def test_reference_identity_currency_and_type_mismatches_are_blocked() -> None:
    wrong_type = assess_fund_structure(
        _bundle(instrument_type=InstrumentType.SHARE),
        _evidence(),
        assessed_at=NOW,
    )
    wrong_currency = assess_fund_structure(
        _bundle(currency="USD"),
        _evidence(),
        assessed_at=NOW,
    )
    wrong_identity = assess_fund_structure(
        _bundle(stable_key="uid:other-fund"),
        _evidence(),
        assessed_at=NOW,
    )

    assert FundStructuralBlocker.NOT_A_FUND in wrong_type.blockers
    assert FundStructuralBlocker.CURRENCY_MISMATCH in wrong_currency.blockers
    assert FundStructuralBlocker.INSTRUMENT_IDENTITY_MISMATCH in wrong_identity.blockers


def test_market_readiness_failure_propagates_to_fund_assessment() -> None:
    bundle = _bundle(quote_as_of=NOW - timedelta(minutes=6))

    result = assess_fund_structure(bundle, _evidence(), assessed_at=NOW)

    assert result.analysis_ready is False
    assert FundStructuralBlocker.MARKET_RESEARCH_NOT_READY in result.blockers
    assert "quote" in result.market_readiness.stale_components


def test_contract_rejects_incomplete_or_non_reconciling_evidence() -> None:
    payload = _evidence().model_dump()
    payload["holdings"][0]["weight"] = Decimal("0.29")
    with pytest.raises(ValidationError, match="holding weights"):
        FundStructuralEvidenceV1.model_validate(payload)

    payload = _evidence().model_dump()
    payload["tracking_source"] = None
    with pytest.raises(ValidationError, match="tracking evidence"):
        FundStructuralEvidenceV1.model_validate(payload)

    future = NOW + timedelta(minutes=10)
    payload = _evidence().model_dump()
    payload["structure_as_of"] = future
    with pytest.raises(ValidationError, match="retrieved before"):
        FundStructuralEvidenceV1.model_validate(payload)


def test_future_evidence_timestamps_are_blocked_after_valid_provenance() -> None:
    future = NOW + timedelta(minutes=10)
    evidence = _evidence(
        structure_as_of=future,
        fee_as_of=future,
        tracking_as_of=future,
        source_retrieved_at=future,
    )

    result = assess_fund_structure(_bundle(), evidence, assessed_at=NOW)

    assert FundStructuralBlocker.STRUCTURE_FUTURE_TIMESTAMP in result.blockers
    assert FundStructuralBlocker.FEE_FUTURE_TIMESTAMP in result.blockers
    assert FundStructuralBlocker.TRACKING_FUTURE_TIMESTAMP in result.blockers


def test_metric_tampering_and_unsafe_flags_are_rejected() -> None:
    result = assess_fund_structure(_bundle(), _evidence(), assessed_at=NOW)
    metrics_payload = result.metrics.model_dump()
    metrics_payload["effective_holding_count"] = Decimal("99")
    with pytest.raises(ValidationError, match="effective holding count"):
        FundStructuralMetricsV1.model_validate(metrics_payload)

    evidence_payload = _evidence().model_dump()
    evidence_payload["trading_methods"] = True
    with pytest.raises(ValidationError):
        FundStructuralEvidenceV1.model_validate(evidence_payload)

    with pytest.raises(
        FundStructuralAssessmentError,
        match="FUND_STRUCTURAL_ASSESSMENT_TIMESTAMP_MUST_BE_AWARE",
    ):
        assess_fund_structure(
            _bundle(),
            _evidence(),
            assessed_at=datetime(2026, 7, 29, 13, 30),
        )
