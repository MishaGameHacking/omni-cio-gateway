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
from omni_cio.contracts.v1.technical import (
    PriceAdjustmentStatus,
    PriceBarV1,
    PriceInterval,
    PriceSeriesEvidenceV1,
    TechnicalAssessmentBlocker,
    TechnicalAssessmentStatus,
    TechnicalAssessmentWarning,
    TechnicalIndicatorMetricsV1,
    TechnicalIndicatorPolicyV1,
    TechnicalMacdState,
    TechnicalMomentumState,
    TechnicalTrendState,
)
from omni_cio.market.technical_v1 import (
    TechnicalIndicatorAssessmentError,
    assess_technical_indicators,
)


NOW = datetime(2026, 7, 29, 14, 0, tzinfo=timezone.utc)
KEY = "uid:technical-a"


def _source(
    *,
    authority: SourceAuthority = SourceAuthority.OFFICIAL,
    retrieved_at: datetime = NOW,
) -> MarketSourceV1:
    return MarketSourceV1(
        provider="synthetic-market-source",
        authority=authority,
        retrieved_at=retrieved_at,
        source_id="synthetic-price-series",
    )


def _state(
    *,
    count: int,
    status: ComponentStatus = ComponentStatus.OK,
    checked_at: datetime | None = NOW,
) -> ComponentStateV1:
    source = _source() if status in (ComponentStatus.OK, ComponentStatus.DEGRADED) else None
    return ComponentStateV1(
        status=status,
        source=source,
        checked_at=checked_at,
        record_count=count,
    )


def _bundle(
    *,
    stable_key: str = KEY,
    currency: str = "RUB",
    quote_as_of: datetime = NOW,
) -> MarketResearchBundleV1:
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
        reference=InstrumentReferenceV1(
            stable_key=stable_key,
            name="Synthetic share",
            ticker="STECH",
            uid="technical-a",
            instrument_type=InstrumentType.SHARE,
            currency=currency,
            lot=10,
            issuer_id="issuer-technical-a",
            sector="technology",
            source=_source(authority=SourceAuthority.PRIMARY),
        ),
        quote=MarketQuoteV1(
            instrument_key=stable_key,
            currency=currency,
            as_of=quote_as_of,
            source=_source(),
            last_price=Decimal("134.5"),
            best_bid=Decimal("134.4"),
            best_ask=Decimal("134.6"),
        ),
        liquidity=MarketLiquidityV1(
            instrument_key=stable_key,
            currency=currency,
            as_of=NOW,
            source=_source(),
            best_bid=Decimal("134.4"),
            best_ask=Decimal("134.6"),
            spread_absolute=Decimal("0.2"),
            spread_bps=Decimal("14.86988847583643122676579926"),
            bid_depth=Decimal("1000000"),
            ask_depth=Decimal("1200000"),
            turnover_24h=Decimal("50000000"),
        ),
        events=(),
        trading_methods=False,
    )


def _bars(
    *,
    count: int = 70,
    descending: bool = False,
    missing_volume_indexes: set[int] | None = None,
    end_at: datetime = NOW,
) -> tuple[PriceBarV1, ...]:
    missing = missing_volume_indexes or set()
    result: list[PriceBarV1] = []
    for index in range(count):
        base = Decimal("150") if descending else Decimal("100")
        change = Decimal(index) * Decimal("0.5")
        close = base - change if descending else base + change
        result.append(
            PriceBarV1(
                opened_at=end_at - timedelta(days=count - 1 - index),
                open=close - Decimal("0.2"),
                high=close + Decimal("1"),
                low=close - Decimal("1"),
                close=close,
                volume=(
                    None
                    if index in missing
                    else Decimal("1000") + Decimal(index) * Decimal("10")
                ),
            )
        )
    return tuple(result)


def _evidence(
    *,
    bars: tuple[PriceBarV1, ...] | None = None,
    authority: SourceAuthority = SourceAuthority.OFFICIAL,
    source_retrieved_at: datetime = NOW,
    adjustment_status: PriceAdjustmentStatus = PriceAdjustmentStatus.ADJUSTED,
    truncated: bool = False,
    complete_session_data: bool = True,
    stable_key: str = KEY,
    currency: str = "RUB",
) -> PriceSeriesEvidenceV1:
    return PriceSeriesEvidenceV1(
        instrument_key=stable_key,
        currency=currency,
        interval=PriceInterval.DAY_1,
        source=_source(
            authority=authority,
            retrieved_at=source_retrieved_at,
        ),
        adjustment_status=adjustment_status,
        bars=bars or _bars(),
        truncated=truncated,
        complete_session_data=complete_session_data,
    )


def test_rising_series_calculates_exact_trend_momentum_atr_and_volume() -> None:
    result = assess_technical_indicators(
        _bundle(),
        _evidence(),
        assessed_at=NOW,
    )

    assert result.status is TechnicalAssessmentStatus.READY
    assert result.analysis_ready is True
    assert result.blockers == ()
    assert result.metrics is not None
    assert result.metrics.bar_count == 70
    assert result.metrics.first_close == Decimal("100.0")
    assert result.metrics.last_close == Decimal("134.5")
    assert result.metrics.period_return == Decimal("134.5") / Decimal("100") - Decimal("1")
    assert result.metrics.max_drawdown == Decimal("0")
    assert result.metrics.sma_short == Decimal("129.75")
    assert result.metrics.sma_long == Decimal("122.25")
    assert result.metrics.rsi == Decimal("100")
    assert result.metrics.atr == Decimal("2.0")
    assert result.metrics.average_volume == Decimal("1345")
    assert result.metrics.last_volume == Decimal("1690")
    assert result.metrics.trend_state is TechnicalTrendState.ABOVE_BOTH_AVERAGES
    assert result.metrics.momentum_state is TechnicalMomentumState.OVERBOUGHT_ZONE
    assert result.metrics.macd_state is TechnicalMacdState.POSITIVE
    assert TechnicalAssessmentWarning.RSI_OVERBOUGHT_ZONE in result.warnings
    assert result.no_price_forecast is True
    assert result.technical_analysis_not_sufficient_alone is True


def test_falling_series_reports_drawdown_and_negative_observations() -> None:
    result = assess_technical_indicators(
        _bundle(),
        _evidence(bars=_bars(descending=True)),
        assessed_at=NOW,
    )

    assert result.analysis_ready is True
    assert result.metrics is not None
    assert result.metrics.rsi == Decimal("0")
    assert result.metrics.max_drawdown > Decimal("0")
    assert result.metrics.trend_state is TechnicalTrendState.BELOW_BOTH_AVERAGES
    assert result.metrics.momentum_state is TechnicalMomentumState.OVERSOLD_ZONE
    assert result.metrics.macd_state is TechnicalMacdState.NEGATIVE
    assert TechnicalAssessmentWarning.RSI_OVERSOLD_ZONE in result.warnings
    assert TechnicalAssessmentWarning.CLOSE_BELOW_LONG_AVERAGE in result.warnings
    assert TechnicalAssessmentWarning.NEGATIVE_MACD_HISTOGRAM in result.warnings


def test_insufficient_history_blocks_assessment_without_fabricated_metrics() -> None:
    result = assess_technical_indicators(
        _bundle(),
        _evidence(bars=_bars(count=30)),
        assessed_at=NOW,
    )

    assert result.status is TechnicalAssessmentStatus.REJECTED
    assert TechnicalAssessmentBlocker.INSUFFICIENT_BARS in result.blockers
    assert result.metrics is None


def test_stale_future_untrusted_and_incomplete_series_fail_closed() -> None:
    stale_bars = _bars(end_at=NOW - timedelta(days=3))
    stale = assess_technical_indicators(
        _bundle(),
        _evidence(bars=stale_bars),
        assessed_at=NOW,
    )
    assert TechnicalAssessmentBlocker.LAST_BAR_STALE in stale.blockers

    future = NOW + timedelta(minutes=10)
    future_bars = _bars(end_at=future)
    future_result = assess_technical_indicators(
        _bundle(),
        _evidence(
            bars=future_bars,
            source_retrieved_at=future,
        ),
        assessed_at=NOW,
    )
    assert TechnicalAssessmentBlocker.LAST_BAR_FUTURE_TIMESTAMP in future_result.blockers

    untrusted = assess_technical_indicators(
        _bundle(),
        _evidence(authority=SourceAuthority.SECONDARY),
        assessed_at=NOW,
    )
    assert TechnicalAssessmentBlocker.UNTRUSTED_SOURCE in untrusted.blockers

    incomplete = assess_technical_indicators(
        _bundle(),
        _evidence(truncated=True, complete_session_data=False),
        assessed_at=NOW,
    )
    assert TechnicalAssessmentBlocker.SERIES_TRUNCATED in incomplete.blockers
    assert TechnicalAssessmentBlocker.SESSION_DATA_INCOMPLETE in incomplete.blockers


def test_adjustment_policy_can_block_or_explicitly_allow_unadjusted_series() -> None:
    evidence = _evidence(adjustment_status=PriceAdjustmentStatus.UNADJUSTED)
    blocked = assess_technical_indicators(_bundle(), evidence, assessed_at=NOW)
    assert TechnicalAssessmentBlocker.PRICE_ADJUSTMENT_UNCONFIRMED in blocked.blockers
    assert TechnicalAssessmentWarning.UNADJUSTED_PRICE_SERIES in blocked.warnings

    allowed = assess_technical_indicators(
        _bundle(),
        evidence,
        assessed_at=NOW,
        policy=TechnicalIndicatorPolicyV1(require_adjusted_prices=False),
    )
    assert allowed.analysis_ready is True
    assert TechnicalAssessmentWarning.UNADJUSTED_PRICE_SERIES in allowed.warnings


def test_volume_coverage_threshold_distinguishes_warning_from_blocker() -> None:
    one_missing = assess_technical_indicators(
        _bundle(),
        _evidence(bars=_bars(missing_volume_indexes={10})),
        assessed_at=NOW,
    )
    assert one_missing.analysis_ready is True
    assert TechnicalAssessmentWarning.MISSING_VOLUME_VALUES in one_missing.warnings

    too_many_missing = assess_technical_indicators(
        _bundle(),
        _evidence(bars=_bars(missing_volume_indexes=set(range(10)))),
        assessed_at=NOW,
    )
    assert TechnicalAssessmentBlocker.VOLUME_COVERAGE_INSUFFICIENT in (
        too_many_missing.blockers
    )


def test_identity_currency_and_market_readiness_failures_propagate() -> None:
    identity = assess_technical_indicators(
        _bundle(stable_key="uid:other"),
        _evidence(),
        assessed_at=NOW,
    )
    assert TechnicalAssessmentBlocker.INSTRUMENT_IDENTITY_MISMATCH in identity.blockers

    currency = assess_technical_indicators(
        _bundle(currency="USD"),
        _evidence(),
        assessed_at=NOW,
    )
    assert TechnicalAssessmentBlocker.CURRENCY_MISMATCH in currency.blockers

    stale_market = assess_technical_indicators(
        _bundle(quote_as_of=NOW - timedelta(minutes=6)),
        _evidence(),
        assessed_at=NOW,
    )
    assert TechnicalAssessmentBlocker.MARKET_RESEARCH_NOT_READY in stale_market.blockers
    assert "quote" in stale_market.market_readiness.stale_components


def test_price_series_contract_rejects_invalid_ohlc_order_and_provenance() -> None:
    with pytest.raises(ValidationError, match="bar high"):
        PriceBarV1(
            opened_at=NOW,
            open=Decimal("100"),
            high=Decimal("99"),
            low=Decimal("98"),
            close=Decimal("100"),
            volume=Decimal("1"),
        )

    ordered = list(_bars())
    ordered[0], ordered[1] = ordered[1], ordered[0]
    with pytest.raises(ValidationError, match="ordered chronologically"):
        _evidence(bars=tuple(ordered))

    with pytest.raises(ValidationError, match="retrieved before"):
        _evidence(source_retrieved_at=NOW - timedelta(minutes=1))


def test_policy_and_metric_reconciliation_are_fail_closed() -> None:
    with pytest.raises(ValidationError, match="short SMA"):
        TechnicalIndicatorPolicyV1(
            sma_short_period=50,
            sma_long_period=20,
        )

    result = assess_technical_indicators(_bundle(), _evidence(), assessed_at=NOW)
    assert result.metrics is not None
    payload = result.metrics.model_dump()
    payload["period_return"] = Decimal("99")
    with pytest.raises(ValidationError, match="period return"):
        TechnicalIndicatorMetricsV1.model_validate(payload)

    payload = result.metrics.model_dump()
    payload["macd_histogram"] = Decimal("99")
    with pytest.raises(ValidationError, match="MACD histogram"):
        TechnicalIndicatorMetricsV1.model_validate(payload)


def test_unsafe_flags_and_naive_assessment_timestamp_are_rejected() -> None:
    payload = _evidence().model_dump()
    payload["trading_methods"] = True
    with pytest.raises(ValidationError):
        PriceSeriesEvidenceV1.model_validate(payload)

    with pytest.raises(
        TechnicalIndicatorAssessmentError,
        match="TECHNICAL_ASSESSMENT_TIMESTAMP_MUST_BE_AWARE",
    ):
        assess_technical_indicators(
            _bundle(),
            _evidence(),
            assessed_at=datetime(2026, 7, 29, 14, 0),
        )
