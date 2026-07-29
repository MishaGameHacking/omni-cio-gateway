from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from omni_cio.contracts.v1.market import MarketResearchBundleV1
from omni_cio.contracts.v1.technical import (
    PriceAdjustmentStatus,
    PriceSeriesEvidenceV1,
    TechnicalAssessmentBlocker,
    TechnicalAssessmentStatus,
    TechnicalAssessmentWarning,
    TechnicalIndicatorAssessmentV1,
    TechnicalIndicatorMetricsV1,
    TechnicalIndicatorPolicyV1,
    TechnicalMacdState,
    TechnicalMomentumState,
    TechnicalTrendState,
)
from omni_cio.market.assessment_v1 import assess_market_research_bundle


class TechnicalIndicatorAssessmentError(ValueError):
    """The supplied price series cannot be assessed safely."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise TechnicalIndicatorAssessmentError(
            "TECHNICAL_ASSESSMENT_TIMESTAMP_MUST_BE_AWARE"
        )
    return result.astimezone(timezone.utc)


def _append_unique[T](target: list[T], value: T) -> None:
    if value not in target:
        target.append(value)


def _sma(values: list[Decimal], period: int) -> Decimal:
    return sum(values[-period:], Decimal("0")) / Decimal(period)


def _ema_series(values: list[Decimal], period: int) -> list[Decimal]:
    alpha = Decimal("2") / Decimal(period + 1)
    result = [values[0]]
    for value in values[1:]:
        result.append(alpha * value + (Decimal("1") - alpha) * result[-1])
    return result


def _rsi(values: list[Decimal], period: int) -> Decimal:
    changes = [current - previous for previous, current in zip(values, values[1:])]
    gains = [max(change, Decimal("0")) for change in changes]
    losses = [max(-change, Decimal("0")) for change in changes]
    average_gain = sum(gains[:period], Decimal("0")) / Decimal(period)
    average_loss = sum(losses[:period], Decimal("0")) / Decimal(period)
    for gain, loss in zip(gains[period:], losses[period:]):
        average_gain = (
            average_gain * Decimal(period - 1) + gain
        ) / Decimal(period)
        average_loss = (
            average_loss * Decimal(period - 1) + loss
        ) / Decimal(period)
    if average_loss == 0:
        return Decimal("100") if average_gain > 0 else Decimal("50")
    relative_strength = average_gain / average_loss
    return Decimal("100") - Decimal("100") / (Decimal("1") + relative_strength)


def _atr(evidence: PriceSeriesEvidenceV1, period: int) -> Decimal:
    true_ranges: list[Decimal] = []
    previous_close: Decimal | None = None
    for bar in evidence.bars:
        intrabar_range = bar.high - bar.low
        if previous_close is None:
            true_range = intrabar_range
        else:
            true_range = max(
                intrabar_range,
                abs(bar.high - previous_close),
                abs(bar.low - previous_close),
            )
        true_ranges.append(true_range)
        previous_close = bar.close
    return sum(true_ranges[-period:], Decimal("0")) / Decimal(period)


def _volatility(closes: list[Decimal], annualization_factor: int) -> tuple[Decimal, Decimal]:
    returns = [current / previous - Decimal("1") for previous, current in zip(closes, closes[1:])]
    mean_return = sum(returns, Decimal("0")) / Decimal(len(returns))
    variance = sum(
        ((value - mean_return) * (value - mean_return) for value in returns),
        Decimal("0"),
    ) / Decimal(len(returns))
    realized = variance.sqrt()
    annualized = realized * Decimal(annualization_factor).sqrt()
    return realized, annualized


def _max_drawdown(closes: list[Decimal]) -> Decimal:
    peak = closes[0]
    maximum = Decimal("0")
    for close in closes:
        peak = max(peak, close)
        drawdown = (peak - close) / peak
        maximum = max(maximum, drawdown)
    return maximum


def _build_metrics(
    evidence: PriceSeriesEvidenceV1,
    policy: TechnicalIndicatorPolicyV1,
) -> TechnicalIndicatorMetricsV1:
    closes = [bar.close for bar in evidence.bars]
    first_close = closes[0]
    last_close = closes[-1]
    sma_short = _sma(closes, policy.sma_short_period)
    sma_long = _sma(closes, policy.sma_long_period)
    rsi = _rsi(closes, policy.rsi_period)

    fast_ema = _ema_series(closes, policy.macd_fast_period)
    slow_ema = _ema_series(closes, policy.macd_slow_period)
    macd_series = [fast - slow for fast, slow in zip(fast_ema, slow_ema)]
    signal_series = _ema_series(macd_series, policy.macd_signal_period)
    macd = macd_series[-1]
    macd_signal = signal_series[-1]
    macd_histogram = macd - macd_signal

    realized_volatility, annualized_volatility = _volatility(
        closes,
        policy.annualization_factor,
    )
    available_volumes = [bar.volume for bar in evidence.bars if bar.volume is not None]
    average_volume = (
        sum(available_volumes, Decimal("0")) / Decimal(len(available_volumes))
        if available_volumes
        else None
    )
    last_volume = evidence.bars[-1].volume
    unavailable_metrics: list[str] = []
    if average_volume is None:
        unavailable_metrics.append("average_volume")
    if last_volume is None:
        unavailable_metrics.append("last_volume")

    if last_close > sma_short and last_close > sma_long:
        trend_state = TechnicalTrendState.ABOVE_BOTH_AVERAGES
    elif last_close < sma_short and last_close < sma_long:
        trend_state = TechnicalTrendState.BELOW_BOTH_AVERAGES
    else:
        trend_state = TechnicalTrendState.MIXED

    if rsi <= policy.rsi_oversold_threshold:
        momentum_state = TechnicalMomentumState.OVERSOLD_ZONE
    elif rsi >= policy.rsi_overbought_threshold:
        momentum_state = TechnicalMomentumState.OVERBOUGHT_ZONE
    else:
        momentum_state = TechnicalMomentumState.NEUTRAL

    if macd_histogram > 0:
        macd_state = TechnicalMacdState.POSITIVE
    elif macd_histogram < 0:
        macd_state = TechnicalMacdState.NEGATIVE
    else:
        macd_state = TechnicalMacdState.NEUTRAL

    return TechnicalIndicatorMetricsV1(
        bar_count=len(evidence.bars),
        first_bar_at=evidence.bars[0].opened_at,
        last_bar_at=evidence.bars[-1].opened_at,
        first_close=first_close,
        last_close=last_close,
        period_return=last_close / first_close - Decimal("1"),
        peak_close=max(closes),
        trough_close=min(closes),
        max_drawdown=_max_drawdown(closes),
        realized_volatility=realized_volatility,
        annualized_volatility=annualized_volatility,
        sma_short=sma_short,
        sma_long=sma_long,
        close_vs_sma_short=last_close / sma_short - Decimal("1"),
        close_vs_sma_long=last_close / sma_long - Decimal("1"),
        rsi=rsi,
        macd=macd,
        macd_signal=macd_signal,
        macd_histogram=macd_histogram,
        atr=_atr(evidence, policy.atr_period),
        average_volume=average_volume,
        last_volume=last_volume,
        missing_volume_count=len(evidence.bars) - len(available_volumes),
        trend_state=trend_state,
        momentum_state=momentum_state,
        macd_state=macd_state,
        unavailable_metrics=tuple(unavailable_metrics),
    )


def assess_technical_indicators(
    bundle: MarketResearchBundleV1,
    evidence: PriceSeriesEvidenceV1,
    *,
    policy: TechnicalIndicatorPolicyV1 | None = None,
    assessed_at: datetime | None = None,
) -> TechnicalIndicatorAssessmentV1:
    """Calculate technical evidence without treating indicators as price forecasts."""

    active_policy = policy or TechnicalIndicatorPolicyV1()
    evaluation_time = _aware_utc(assessed_at)
    market_readiness = assess_market_research_bundle(
        bundle,
        assessed_at=evaluation_time,
    )
    blockers: list[TechnicalAssessmentBlocker] = []
    warnings: list[TechnicalAssessmentWarning] = [
        TechnicalAssessmentWarning.PRICE_ONLY_EVIDENCE,
        TechnicalAssessmentWarning.TECHNICAL_SIGNALS_NOT_FORECASTS,
        TechnicalAssessmentWarning.INDICATORS_REQUIRE_ALTERNATIVE_EXPLANATIONS,
    ]

    if not market_readiness.decision_ready:
        _append_unique(blockers, TechnicalAssessmentBlocker.MARKET_RESEARCH_NOT_READY)

    reference = bundle.reference
    if reference is None:
        _append_unique(blockers, TechnicalAssessmentBlocker.REFERENCE_MISSING)
    else:
        if reference.stable_key != evidence.instrument_key:
            _append_unique(
                blockers,
                TechnicalAssessmentBlocker.INSTRUMENT_IDENTITY_MISMATCH,
            )
        if reference.currency != evidence.currency:
            _append_unique(blockers, TechnicalAssessmentBlocker.CURRENCY_MISMATCH)
    if bundle.instrument_key != evidence.instrument_key:
        _append_unique(
            blockers,
            TechnicalAssessmentBlocker.INSTRUMENT_IDENTITY_MISMATCH,
        )

    if evidence.source.authority not in active_policy.trusted_authorities:
        _append_unique(blockers, TechnicalAssessmentBlocker.UNTRUSTED_SOURCE)
    if len(evidence.bars) < active_policy.minimum_bars:
        _append_unique(blockers, TechnicalAssessmentBlocker.INSUFFICIENT_BARS)

    last_bar_age = (evaluation_time - evidence.bars[-1].opened_at).total_seconds()
    if last_bar_age < -active_policy.future_tolerance_seconds:
        _append_unique(
            blockers,
            TechnicalAssessmentBlocker.LAST_BAR_FUTURE_TIMESTAMP,
        )
    if last_bar_age > active_policy.max_last_bar_age_seconds:
        _append_unique(blockers, TechnicalAssessmentBlocker.LAST_BAR_STALE)

    if (
        active_policy.require_adjusted_prices
        and evidence.adjustment_status is not PriceAdjustmentStatus.ADJUSTED
    ):
        _append_unique(
            blockers,
            TechnicalAssessmentBlocker.PRICE_ADJUSTMENT_UNCONFIRMED,
        )
    if evidence.adjustment_status is PriceAdjustmentStatus.UNADJUSTED:
        _append_unique(warnings, TechnicalAssessmentWarning.UNADJUSTED_PRICE_SERIES)
    if evidence.truncated:
        _append_unique(blockers, TechnicalAssessmentBlocker.SERIES_TRUNCATED)
    if not evidence.complete_session_data:
        _append_unique(blockers, TechnicalAssessmentBlocker.SESSION_DATA_INCOMPLETE)

    missing_volume_count = sum(bar.volume is None for bar in evidence.bars)
    missing_volume_fraction = Decimal(missing_volume_count) / Decimal(len(evidence.bars))
    if missing_volume_fraction > active_policy.maximum_missing_volume_fraction:
        _append_unique(
            blockers,
            TechnicalAssessmentBlocker.VOLUME_COVERAGE_INSUFFICIENT,
        )
    if missing_volume_count:
        _append_unique(warnings, TechnicalAssessmentWarning.MISSING_VOLUME_VALUES)
    if any(bar.volume == 0 for bar in evidence.bars if bar.volume is not None):
        _append_unique(warnings, TechnicalAssessmentWarning.ZERO_VOLUME_BARS_PRESENT)

    metrics = (
        _build_metrics(evidence, active_policy)
        if len(evidence.bars) >= active_policy.minimum_bars
        else None
    )
    if metrics is not None:
        if metrics.momentum_state is TechnicalMomentumState.OVERBOUGHT_ZONE:
            _append_unique(warnings, TechnicalAssessmentWarning.RSI_OVERBOUGHT_ZONE)
        elif metrics.momentum_state is TechnicalMomentumState.OVERSOLD_ZONE:
            _append_unique(warnings, TechnicalAssessmentWarning.RSI_OVERSOLD_ZONE)
        if metrics.last_close < metrics.sma_long:
            _append_unique(
                warnings,
                TechnicalAssessmentWarning.CLOSE_BELOW_LONG_AVERAGE,
            )
        if metrics.macd_histogram < 0:
            _append_unique(
                warnings,
                TechnicalAssessmentWarning.NEGATIVE_MACD_HISTOGRAM,
            )

    analysis_ready = not blockers
    status = (
        TechnicalAssessmentStatus.READY
        if analysis_ready
        else TechnicalAssessmentStatus.REJECTED
    )
    return TechnicalIndicatorAssessmentV1(
        assessed_at=evaluation_time,
        status=status,
        analysis_ready=analysis_ready,
        instrument_key=evidence.instrument_key,
        currency=evidence.currency,
        interval=evidence.interval,
        last_bar_age_seconds=max(0, int(last_bar_age)),
        policy=active_policy,
        market_readiness=market_readiness,
        metrics=metrics,
        blockers=tuple(blockers),
        warnings=tuple(warnings),
    )
