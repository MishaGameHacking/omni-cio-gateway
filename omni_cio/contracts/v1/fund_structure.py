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
from omni_cio.contracts.v1.portfolio import InstrumentType


Weight = Annotated[
    Decimal,
    Field(ge=Decimal("0"), le=Decimal("1"), allow_inf_nan=False),
]
PositiveDecimal = Annotated[
    Decimal,
    Field(gt=Decimal("0"), allow_inf_nan=False),
]
NonNegativeDecimal = Annotated[
    Decimal,
    Field(ge=Decimal("0"), allow_inf_nan=False),
]
NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]
MetricName = Annotated[str, Field(min_length=1, max_length=64)]


class FundStrategyKind(StrEnum):
    INDEX = "index"
    ACTIVE = "active"
    MONEY_MARKET = "money_market"
    COMMODITY = "commodity"
    MIXED = "mixed"
    OTHER = "other"


class FundReplicationMethod(StrEnum):
    FULL_PHYSICAL = "full_physical"
    OPTIMIZED_SAMPLING = "optimized_sampling"
    SYNTHETIC = "synthetic"
    ACTIVE_SELECTION = "active_selection"
    NOT_APPLICABLE = "not_applicable"


class FundStructuralStatus(StrEnum):
    READY = "ready"
    REJECTED = "rejected"


class FundStructuralBlocker(StrEnum):
    MARKET_RESEARCH_NOT_READY = "market_research_not_ready"
    REFERENCE_MISSING = "reference_missing"
    NOT_A_FUND = "not_a_fund"
    INSTRUMENT_IDENTITY_MISMATCH = "instrument_identity_mismatch"
    CURRENCY_MISMATCH = "currency_mismatch"
    UNTRUSTED_SOURCE = "untrusted_source"
    STRUCTURE_FUTURE_TIMESTAMP = "structure_future_timestamp"
    STRUCTURE_STALE = "structure_stale"
    FEE_FUTURE_TIMESTAMP = "fee_future_timestamp"
    FEE_STALE = "fee_stale"
    TRACKING_FUTURE_TIMESTAMP = "tracking_future_timestamp"
    TRACKING_STALE = "tracking_stale"


class FundStructuralWarning(StrEnum):
    HIGH_SINGLE_HOLDING_CONCENTRATION = "high_single_holding_concentration"
    HIGH_TOP_TEN_CONCENTRATION = "high_top_ten_concentration"
    HIGH_EXPENSE_RATIO = "high_expense_ratio"
    HIGH_TRACKING_ERROR = "high_tracking_error"
    LARGE_TRACKING_DIFFERENCE = "large_tracking_difference"
    TRACKING_STATISTICS_MISSING = "tracking_statistics_missing"
    DIRECT_HOLDING_OVERLAP = "direct_holding_overlap"
    DERIVATIVE_EXPOSURE_PRESENT = "derivative_exposure_present"
    FUND_OF_FUNDS_EXPOSURE_PRESENT = "fund_of_funds_exposure_present"
    SINGLE_CURRENCY_CONCENTRATION = "single_currency_concentration"
    SYNTHETIC_REPLICATION = "synthetic_replication"
    MANAGEMENT_COMPANY_RISK_NOT_SCORED = "management_company_risk_not_scored"
    STRUCTURE_IS_POINT_IN_TIME = "structure_is_point_in_time"
    METRICS_ARE_NOT_FORECASTS = "metrics_are_not_forecasts"


class FundStructuralPolicyV1(ContractModel):
    max_structure_age_days: PositiveInt = 45
    max_fee_age_days: PositiveInt = 550
    max_tracking_age_days: PositiveInt = 550
    future_tolerance_seconds: NonNegativeInt = 60
    max_single_holding_weight: Weight = Decimal("0.15")
    max_top_ten_weight: Weight = Decimal("0.70")
    max_total_expense_ratio_bps: NonNegativeDecimal = Decimal("150")
    max_tracking_error_bps: NonNegativeDecimal = Decimal("300")
    max_absolute_tracking_difference_bps: NonNegativeDecimal = Decimal("300")
    single_currency_warning_weight: Weight = Decimal("0.80")
    trusted_authorities: tuple[SourceAuthority, ...] = (
        SourceAuthority.PRIMARY,
        SourceAuthority.OFFICIAL,
        SourceAuthority.REGULATED,
    )

    @model_validator(mode="after")
    def validate_policy(self) -> FundStructuralPolicyV1:
        if not self.trusted_authorities:
            raise ValueError("fund policy requires at least one trusted authority")
        if len(set(self.trusted_authorities)) != len(self.trusted_authorities):
            raise ValueError("fund policy trusted authorities must be unique")
        return self


class FundHoldingV1(ContractModel):
    name: Annotated[str, Field(min_length=1, max_length=256)]
    instrument_type: InstrumentType
    currency: CurrencyCode
    weight: Weight
    stable_key: Annotated[str | None, Field(min_length=3, max_length=256)] = None
    issuer_id: Annotated[str | None, Field(max_length=128)] = None

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_identity(self) -> FundHoldingV1:
        identity_required = self.instrument_type not in (
            InstrumentType.CURRENCY,
            InstrumentType.OTHER,
        )
        if identity_required and self.stable_key is None:
            raise ValueError("fund holding requires stable_key for this instrument type")
        return self


class FundCurrencyExposureV1(ContractModel):
    currency: CurrencyCode
    weight: Weight

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value


class FundStructuralEvidenceV1(ContractModel):
    schema_name: Literal["fund_structural_evidence"] = "fund_structural_evidence"
    schema_version: Literal["1.0"] = "1.0"
    instrument_key: Annotated[str, Field(min_length=3, max_length=256)]
    currency: CurrencyCode
    strategy_kind: FundStrategyKind
    replication_method: FundReplicationMethod
    management_company: Annotated[str, Field(min_length=1, max_length=256)]
    benchmark_name: Annotated[str | None, Field(max_length=256)] = None
    structure_as_of: datetime
    structure_source: MarketSourceV1
    fee_as_of: datetime
    fee_source: MarketSourceV1
    tracking_as_of: datetime | None = None
    tracking_source: MarketSourceV1 | None = None
    total_expense_ratio_bps: NonNegativeDecimal
    tracking_difference_bps: FiniteDecimal | None = None
    tracking_error_bps: NonNegativeDecimal | None = None
    holdings: tuple[FundHoldingV1, ...]
    currency_exposures: tuple[FundCurrencyExposureV1, ...]
    evidence_complete: Literal[True] = True
    forecast_data_included: Literal[False] = False
    no_cross_currency_aggregation: Literal[True] = True
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("structure_as_of", "fee_as_of", "tracking_as_of")
    @classmethod
    def normalize_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("fund evidence timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_evidence(self) -> FundStructuralEvidenceV1:
        if not self.holdings:
            raise ValueError("fund evidence requires at least one holding")
        if not self.currency_exposures:
            raise ValueError("fund evidence requires currency exposures")
        if sum((item.weight for item in self.holdings), Decimal("0")) != Decimal("1"):
            raise ValueError("fund holding weights must sum exactly to one")
        if (
            sum(
                (item.weight for item in self.currency_exposures),
                Decimal("0"),
            )
            != Decimal("1")
        ):
            raise ValueError("fund currency exposure weights must sum exactly to one")
        holding_keys = [item.stable_key for item in self.holdings if item.stable_key]
        if len(set(holding_keys)) != len(holding_keys):
            raise ValueError("fund holding stable keys must be unique")
        exposure_currencies = [item.currency for item in self.currency_exposures]
        if len(set(exposure_currencies)) != len(exposure_currencies):
            raise ValueError("fund currency exposures must be unique")
        if self.structure_source.retrieved_at < self.structure_as_of:
            raise ValueError("fund structure was retrieved before its as_of timestamp")
        if self.fee_source.retrieved_at < self.fee_as_of:
            raise ValueError("fund fee was retrieved before its as_of timestamp")
        tracking_fields_present = any(
            value is not None
            for value in (
                self.tracking_as_of,
                self.tracking_source,
                self.tracking_difference_bps,
                self.tracking_error_bps,
            )
        )
        tracking_fields_complete = all(
            value is not None
            for value in (
                self.tracking_as_of,
                self.tracking_source,
                self.tracking_difference_bps,
                self.tracking_error_bps,
            )
        )
        if tracking_fields_present and not tracking_fields_complete:
            raise ValueError("fund tracking evidence must be supplied as one complete set")
        if (
            self.tracking_source is not None
            and self.tracking_as_of is not None
            and self.tracking_source.retrieved_at < self.tracking_as_of
        ):
            raise ValueError("fund tracking data was retrieved before its as_of timestamp")
        if self.strategy_kind is FundStrategyKind.INDEX and not self.benchmark_name:
            raise ValueError("index fund evidence requires benchmark_name")
        if (
            self.replication_method is FundReplicationMethod.ACTIVE_SELECTION
            and self.strategy_kind is not FundStrategyKind.ACTIVE
        ):
            raise ValueError("active selection replication requires active strategy")
        return self


class FundStructuralMetricsV1(ContractModel):
    holding_count: PositiveInt
    top_1_weight: Weight
    top_5_weight: Weight
    top_10_weight: Weight
    herfindahl_index: PositiveDecimal
    effective_holding_count: PositiveDecimal
    direct_overlap_weight: Weight
    overlapping_holding_count: NonNegativeInt
    derivative_exposure_weight: Weight
    fund_of_funds_exposure_weight: Weight
    cash_or_currency_weight: Weight
    total_expense_ratio_bps: NonNegativeDecimal
    tracking_difference_bps: FiniteDecimal | None = None
    tracking_error_bps: NonNegativeDecimal | None = None
    dominant_currency: CurrencyCode
    dominant_currency_weight: Weight
    currency_count: PositiveInt
    spread_bps: NonNegativeDecimal | None = None
    turnover_24h: NonNegativeDecimal | None = None
    overlapping_instrument_keys: tuple[
        Annotated[str, Field(min_length=3, max_length=256)], ...
    ] = ()
    unavailable_metrics: tuple[MetricName, ...] = ()
    exact_decimal_arithmetic: Literal[True] = True
    no_cross_currency_aggregation: Literal[True] = True

    @field_validator("dominant_currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_metrics(self) -> FundStructuralMetricsV1:
        if self.effective_holding_count != Decimal("1") / self.herfindahl_index:
            raise ValueError("effective holding count does not reconcile")
        if self.overlapping_holding_count != len(self.overlapping_instrument_keys):
            raise ValueError("fund overlap count does not reconcile")
        if len(set(self.overlapping_instrument_keys)) != len(
            self.overlapping_instrument_keys
        ):
            raise ValueError("fund overlapping instrument keys must be unique")
        if len(set(self.unavailable_metrics)) != len(self.unavailable_metrics):
            raise ValueError("fund unavailable metrics must be unique")
        return self


class FundStructuralAssessmentV1(ContractModel):
    schema_name: Literal["fund_structural_assessment"] = (
        "fund_structural_assessment"
    )
    schema_version: Literal["1.0"] = "1.0"
    assessed_at: datetime
    status: FundStructuralStatus
    analysis_ready: bool
    instrument_key: Annotated[str, Field(min_length=3, max_length=256)]
    currency: CurrencyCode
    structure_age_days: NonNegativeInt
    fee_age_days: NonNegativeInt
    tracking_age_days: NonNegativeInt | None = None
    policy: FundStructuralPolicyV1
    market_readiness: MarketReadinessAssessmentV1
    metrics: FundStructuralMetricsV1
    blockers: tuple[FundStructuralBlocker, ...] = ()
    warnings: tuple[FundStructuralWarning, ...] = ()
    facts_only: Literal[True] = True
    no_price_forecast: Literal[True] = True
    no_investment_recommendation: Literal[True] = True
    point_in_time_structure: Literal[True] = True
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("assessed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("fund assessment timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_assessment(self) -> FundStructuralAssessmentV1:
        if len(set(self.blockers)) != len(self.blockers):
            raise ValueError("fund blockers must be unique")
        if len(set(self.warnings)) != len(self.warnings):
            raise ValueError("fund warnings must be unique")
        expected_ready = not self.blockers
        if self.analysis_ready is not expected_ready:
            raise ValueError("fund analysis readiness is inconsistent")
        expected_status = (
            FundStructuralStatus.READY
            if expected_ready
            else FundStructuralStatus.REJECTED
        )
        if self.status is not expected_status:
            raise ValueError("fund assessment status is inconsistent")
        return self
