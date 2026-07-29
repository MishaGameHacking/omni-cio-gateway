from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import (
    ContractModel,
    CurrencyCode,
    FiniteDecimal,
)
from omni_cio.contracts.v1.market import (
    MarketReadinessAssessmentV1,
    MarketSourceV1,
    SourceAuthority,
)


PositiveDecimal = Annotated[
    Decimal,
    Field(gt=Decimal("0"), allow_inf_nan=False),
]
NonNegativeDecimal = Annotated[
    Decimal,
    Field(ge=Decimal("0"), allow_inf_nan=False),
]
UnitInterval = Annotated[
    Decimal,
    Field(ge=Decimal("0"), le=Decimal("1"), allow_inf_nan=False),
]
Oscillator = Annotated[
    Decimal,
    Field(ge=Decimal("0"), le=Decimal("100"), allow_inf_nan=False),
]
NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]
MetricName = Annotated[str, Field(min_length=1, max_length=64)]


class PriceInterval(StrEnum):
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    HOUR_1 = "1h"
    DAY_1 = "1d"
    WEEK_1 = "1w"


class PriceAdjustmentStatus(StrEnum):
    ADJUSTED = "adjusted"
    UNADJUSTED = "unadjusted"
    UNKNOWN = "unknown"


class TechnicalAssessmentStatus(StrEnum):
    READY = "ready"
    REJECTED = "rejected"


class TechnicalTrendState(StrEnum):
    ABOVE_BOTH_AVERAGES = "above_both_averages"
    BELOW_BOTH_AVERAGES = "below_both_averages"
    MIXED = "mixed"


class TechnicalMomentumState(StrEnum):
    OVERSOLD_ZONE = "oversold_zone"
    NEUTRAL = "neutral"
    OVERBOUGHT_ZONE = "overbought_zone"


class TechnicalMacdState(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class TechnicalAssessmentBlocker(StrEnum):
    MARKET_RESEARCH_NOT_READY = "market_research_not_ready"
    REFERENCE_MISSING = "reference_missing"
    INSTRUMENT_IDENTITY_MISMATCH = "instrument_identity_mismatch"
    CURRENCY_MISMATCH = "currency_mismatch"
    UNTRUSTED_SOURCE = "untrusted_source"
    INSUFFICIENT_BARS = "insufficient_bars"
    LAST_BAR_FUTURE_TIMESTAMP = "last_bar_future_timestamp"
    LAST_BAR_STALE = "last_bar_stale"
    PRICE_ADJUSTMENT_UNCONFIRMED = "price_adjustment_unconfirmed"
    SERIES_TRUNCATED = "series_truncated"
    SESSION_DATA_INCOMPLETE = "session_data_incomplete"
    VOLUME_COVERAGE_INSUFFICIENT = "volume_coverage_insufficient"


class TechnicalAssessmentWarning(StrEnum):
    UNADJUSTED_PRICE_SERIES = "unadjusted_price_series"
    MISSING_VOLUME_VALUES = "missing_volume_values"
    ZERO_VOLUME_BARS_PRESENT = "zero_volume_bars_present"
    RSI_OVERBOUGHT_ZONE = "rsi_overbought_zone"
    RSI_OVERSOLD_ZONE = "rsi_oversold_zone"
    CLOSE_BELOW_LONG_AVERAGE = "close_below_long_average"
    NEGATIVE_MACD_HISTOGRAM = "negative_macd_histogram"
    PRICE_ONLY_EVIDENCE = "price_only_evidence"
    TECHNICAL_SIGNALS_NOT_FORECASTS = "technical_signals_not_forecasts"
    INDICATORS_REQUIRE_ALTERNATIVE_EXPLANATIONS = (
        "indicators_require_alternative_explanations"
    )


class TechnicalIndicatorPolicyV1(ContractModel):
    minimum_bars: PositiveInt = 60
    max_last_bar_age_seconds: PositiveInt = 172_800
    future_tolerance_seconds: NonNegativeInt = 60
    require_adjusted_prices: bool = True
    maximum_missing_volume_fraction: UnitInterval = Decimal("0.10")
    sma_short_period: PositiveInt = 20
    sma_long_period: PositiveInt = 50
    rsi_period: PositiveInt = 14
    rsi_oversold_threshold: Oscillator = Decimal("30")
    rsi_overbought_threshold: Oscillator = Decimal("70")
    macd_fast_period: PositiveInt = 12
    macd_slow_period: PositiveInt = 26
    macd_signal_period: PositiveInt = 9
    atr_period: PositiveInt = 14
    annualization_factor: PositiveInt = 252
    trusted_authorities: tuple[SourceAuthority, ...] = (
        SourceAuthority.PRIMARY,
        SourceAuthority.OFFICIAL,
        SourceAuthority.REGULATED,
    )

    @model_validator(mode="after")
    def validate_policy(self) -> TechnicalIndicatorPolicyV1:
        if self.sma_short_period >= self.sma_long_period:
            raise ValueError("short SMA period must be below long SMA period")
        if self.macd_fast_period >= self.macd_slow_period:
            raise ValueError("MACD fast period must be below slow period")
        if self.rsi_oversold_threshold >= self.rsi_overbought_threshold:
            raise ValueError("RSI oversold threshold must be below overbought threshold")
        minimum_required = max(
            self.sma_long_period,
            self.rsi_period + 1,
            self.macd_slow_period + self.macd_signal_period,
            self.atr_period + 1,
        )
        if self.minimum_bars < minimum_required:
            raise ValueError("minimum_bars is below indicator lookback requirement")
        if not self.trusted_authorities:
            raise ValueError("technical policy requires trusted authorities")
        if len(set(self.trusted_authorities)) != len(self.trusted_authorities):
            raise ValueError("technical policy trusted authorities must be unique")
        return self


class PriceBarV1(ContractModel):
    opened_at: datetime
    open: PositiveDecimal
    high: PositiveDecimal
    low: PositiveDecimal
    close: PositiveDecimal
    volume: NonNegativeDecimal | None = None

    @field_validator("opened_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("price bar timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_ohlc(self) -> PriceBarV1:
        if self.high < max(self.open, self.close):
            raise ValueError("bar high is below open or close")
        if self.low > min(self.open, self.close):
            raise ValueError("bar low is above open or close")
        if self.low > self.high:
            raise ValueError("bar low exceeds high")
        return self


class PriceSeriesEvidenceV1(ContractModel):
    schema_name: Literal["price_series_evidence"] = "price_series_evidence"
    schema_version: Literal["1.0"] = "1.0"
    instrument_key: Annotated[str, Field(min_length=3, max_length=256)]
    currency: CurrencyCode
    interval: PriceInterval
    source: MarketSourceV1
    adjustment_status: PriceAdjustmentStatus
    bars: tuple[PriceBarV1, ...]
    truncated: bool = False
    complete_session_data: bool = True
    evidence_complete: Literal[True] = True
    forecast_data_included: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_series(self) -> PriceSeriesEvidenceV1:
        if not self.bars:
            raise ValueError("price series requires at least one bar")
        timestamps = [bar.opened_at for bar in self.bars]
        if timestamps != sorted(timestamps):
            raise ValueError("price bars must be ordered chronologically")
        if len(set(timestamps)) != len(timestamps):
            raise ValueError("price bar timestamps must be unique")
        if self.source.retrieved_at < self.bars[-1].opened_at:
            raise ValueError("price series was retrieved before its latest bar")
        return self


class TechnicalIndicatorMetricsV1(ContractModel):
    bar_count: PositiveInt
    first_bar_at: datetime
    last_bar_at: datetime
    first_close: PositiveDecimal
    last_close: PositiveDecimal
    period_return: FiniteDecimal
    peak_close: PositiveDecimal
    trough_close: PositiveDecimal
    max_drawdown: UnitInterval
    realized_volatility: NonNegativeDecimal
    annualized_volatility: NonNegativeDecimal
    sma_short: PositiveDecimal
    sma_long: PositiveDecimal
    close_vs_sma_short: FiniteDecimal
    close_vs_sma_long: FiniteDecimal
    rsi: Oscillator
    macd: FiniteDecimal
    macd_signal: FiniteDecimal
    macd_histogram: FiniteDecimal
    atr: NonNegativeDecimal
    average_volume: NonNegativeDecimal | None = None
    last_volume: NonNegativeDecimal | None = None
    missing_volume_count: NonNegativeInt
    trend_state: TechnicalTrendState
    momentum_state: TechnicalMomentumState
    macd_state: TechnicalMacdState
    unavailable_metrics: tuple[MetricName, ...] = ()
    exact_decimal_arithmetic: Literal[True] = True

    @field_validator("first_bar_at", "last_bar_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("technical metric timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_metrics(self) -> TechnicalIndicatorMetricsV1:
        if self.first_bar_at > self.last_bar_at:
            raise ValueError("technical metric period is reversed")
        if self.period_return != self.last_close / self.first_close - Decimal("1"):
            raise ValueError("technical period return does not reconcile")
        if self.macd_histogram != self.macd - self.macd_signal:
            raise ValueError("MACD histogram does not reconcile")
        if len(set(self.unavailable_metrics)) != len(self.unavailable_metrics):
            raise ValueError("technical unavailable metrics must be unique")
        return self


class TechnicalIndicatorAssessmentV1(ContractModel):
    schema_name: Literal["technical_indicator_assessment"] = (
        "technical_indicator_assessment"
    )
    schema_version: Literal["1.0"] = "1.0"
    assessed_at: datetime
    status: TechnicalAssessmentStatus
    analysis_ready: bool
    instrument_key: Annotated[str, Field(min_length=3, max_length=256)]
    currency: CurrencyCode
    interval: PriceInterval
    last_bar_age_seconds: NonNegativeInt
    policy: TechnicalIndicatorPolicyV1
    market_readiness: MarketReadinessAssessmentV1
    metrics: TechnicalIndicatorMetricsV1 | None = None
    blockers: tuple[TechnicalAssessmentBlocker, ...] = ()
    warnings: tuple[TechnicalAssessmentWarning, ...] = ()
    facts_only: Literal[True] = True
    no_price_forecast: Literal[True] = True
    no_investment_recommendation: Literal[True] = True
    technical_analysis_not_sufficient_alone: Literal[True] = True
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("assessed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("technical assessment timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_assessment(self) -> TechnicalIndicatorAssessmentV1:
        if len(set(self.blockers)) != len(self.blockers):
            raise ValueError("technical blockers must be unique")
        if len(set(self.warnings)) != len(self.warnings):
            raise ValueError("technical warnings must be unique")
        expected_ready = not self.blockers
        if self.analysis_ready is not expected_ready:
            raise ValueError("technical analysis readiness is inconsistent")
        expected_status = (
            TechnicalAssessmentStatus.READY
            if expected_ready
            else TechnicalAssessmentStatus.REJECTED
        )
        if self.status is not expected_status:
            raise ValueError("technical assessment status is inconsistent")
        if self.analysis_ready and self.metrics is None:
            raise ValueError("ready technical assessment requires metrics")
        return self
