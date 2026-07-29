from __future__ import annotations

from datetime import date, datetime, timezone
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


NonNegativeDecimal = Annotated[
    Decimal,
    Field(ge=Decimal("0"), allow_inf_nan=False),
]
PositiveDecimal = Annotated[
    Decimal,
    Field(gt=Decimal("0"), allow_inf_nan=False),
]
NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]
MetricName = Annotated[str, Field(min_length=1, max_length=64)]


class EquityAccountingStandard(StrEnum):
    IFRS = "ifrs"
    RAS = "ras"
    US_GAAP = "us_gaap"
    OTHER = "other"


class EquityReportingPeriodKind(StrEnum):
    QUARTER = "quarter"
    HALF_YEAR = "half_year"
    NINE_MONTHS = "nine_months"
    ANNUAL = "annual"
    TTM = "ttm"


class EquityFundamentalStatus(StrEnum):
    READY = "ready"
    REJECTED = "rejected"


class EquityFundamentalBlocker(StrEnum):
    MARKET_RESEARCH_NOT_READY = "market_research_not_ready"
    REFERENCE_MISSING = "reference_missing"
    NOT_A_SHARE = "not_a_share"
    INSTRUMENT_IDENTITY_MISMATCH = "instrument_identity_mismatch"
    CURRENCY_MISMATCH = "currency_mismatch"
    UNTRUSTED_REPORT_SOURCE = "untrusted_report_source"
    UNTRUSTED_MARKET_CAP_SOURCE = "untrusted_market_cap_source"
    REPORT_FUTURE_TIMESTAMP = "report_future_timestamp"
    REPORT_STALE = "report_stale"
    REPORT_PERIOD_FUTURE = "report_period_future"
    MARKET_CAP_FUTURE_TIMESTAMP = "market_cap_future_timestamp"
    MARKET_CAP_STALE = "market_cap_stale"


class EquityFundamentalWarning(StrEnum):
    NEGATIVE_NET_INCOME = "negative_net_income"
    NEGATIVE_OPERATING_CASH_FLOW = "negative_operating_cash_flow"
    NEGATIVE_FREE_CASH_FLOW = "negative_free_cash_flow"
    NEGATIVE_EQUITY = "negative_equity"
    NON_POSITIVE_EBITDA = "non_positive_ebitda"
    NON_POSITIVE_OPERATING_PROFIT = "non_positive_operating_profit"
    DIVIDENDS_EXCEED_POSITIVE_NET_INCOME = (
        "dividends_exceed_positive_net_income"
    )
    NET_CASH_POSITION = "net_cash_position"
    EBITDA_NOT_PROVIDED = "ebitda_not_provided"
    OPERATING_PROFIT_NOT_PROVIDED = "operating_profit_not_provided"
    DIVIDENDS_NOT_PROVIDED = "dividends_not_provided"
    SHARES_OUTSTANDING_NOT_PROVIDED = "shares_outstanding_not_provided"
    ACCOUNTING_STANDARD_OTHER = "accounting_standard_other"
    MULTIPLES_NOT_FORECASTS = "multiples_not_forecasts"
    NO_CROSS_CURRENCY_AGGREGATION = "no_cross_currency_aggregation"


class EquityFundamentalPolicyV1(ContractModel):
    max_report_age_days: PositiveInt = 550
    max_market_cap_age_seconds: PositiveInt = 86_400
    future_tolerance_seconds: NonNegativeInt = 60
    trusted_authorities: tuple[SourceAuthority, ...] = (
        SourceAuthority.PRIMARY,
        SourceAuthority.OFFICIAL,
        SourceAuthority.REGULATED,
    )

    @model_validator(mode="after")
    def validate_policy(self) -> EquityFundamentalPolicyV1:
        if not self.trusted_authorities:
            raise ValueError("equity policy requires at least one trusted authority")
        if len(set(self.trusted_authorities)) != len(self.trusted_authorities):
            raise ValueError("equity policy trusted authorities must be unique")
        return self


class EquityFundamentalEvidenceV1(ContractModel):
    schema_name: Literal["equity_fundamental_evidence"] = (
        "equity_fundamental_evidence"
    )
    schema_version: Literal["1.0"] = "1.0"
    instrument_key: Annotated[str, Field(min_length=3, max_length=256)]
    currency: CurrencyCode
    accounting_standard: EquityAccountingStandard
    period_kind: EquityReportingPeriodKind
    period_start: date
    period_end: date
    published_at: datetime
    report_source: MarketSourceV1
    revenue: NonNegativeDecimal
    operating_profit: FiniteDecimal | None = None
    ebitda: FiniteDecimal | None = None
    net_income: FiniteDecimal
    operating_cash_flow: FiniteDecimal
    capital_expenditure: NonNegativeDecimal
    free_cash_flow: FiniteDecimal
    total_debt: NonNegativeDecimal
    cash_and_equivalents: NonNegativeDecimal
    total_equity: FiniteDecimal
    dividends_paid: NonNegativeDecimal | None = None
    market_cap: PositiveDecimal
    market_cap_as_of: datetime
    market_cap_source: MarketSourceV1
    shares_outstanding: PositiveDecimal | None = None
    evidence_complete: Literal[True] = True
    forecast_data_included: Literal[False] = False
    no_cross_currency_aggregation: Literal[True] = True
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("published_at", "market_cap_as_of")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("equity evidence timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_evidence(self) -> EquityFundamentalEvidenceV1:
        if self.period_end < self.period_start:
            raise ValueError("equity evidence period end precedes start")
        if self.report_source.retrieved_at < self.published_at:
            raise ValueError("equity report was retrieved before publication")
        if self.market_cap_source.retrieved_at < self.market_cap_as_of:
            raise ValueError("equity market cap was retrieved before its timestamp")
        expected_fcf = self.operating_cash_flow - self.capital_expenditure
        if self.free_cash_flow != expected_fcf:
            raise ValueError("equity free cash flow does not reconcile")
        return self


class EquityFundamentalMetricsV1(ContractModel):
    currency: CurrencyCode
    revenue: NonNegativeDecimal
    operating_profit: FiniteDecimal | None = None
    ebitda: FiniteDecimal | None = None
    net_income: FiniteDecimal
    operating_cash_flow: FiniteDecimal
    capital_expenditure: NonNegativeDecimal
    free_cash_flow: FiniteDecimal
    total_debt: NonNegativeDecimal
    cash_and_equivalents: NonNegativeDecimal
    net_debt: FiniteDecimal
    total_equity: FiniteDecimal
    dividends_paid: NonNegativeDecimal | None = None
    market_cap: PositiveDecimal
    net_margin: FiniteDecimal | None = None
    operating_margin: FiniteDecimal | None = None
    ebitda_margin: FiniteDecimal | None = None
    free_cash_flow_margin: FiniteDecimal | None = None
    net_debt_to_ebitda: FiniteDecimal | None = None
    earnings_yield: FiniteDecimal
    free_cash_flow_yield: FiniteDecimal
    price_to_earnings: PositiveDecimal | None = None
    price_to_book: PositiveDecimal | None = None
    dividend_payout_ratio: NonNegativeDecimal | None = None
    unavailable_metrics: tuple[MetricName, ...] = ()
    exact_decimal_arithmetic: Literal[True] = True
    no_cross_currency_aggregation: Literal[True] = True

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_metrics(self) -> EquityFundamentalMetricsV1:
        if self.net_debt != self.total_debt - self.cash_and_equivalents:
            raise ValueError("equity net debt does not reconcile")
        if self.earnings_yield != self.net_income / self.market_cap:
            raise ValueError("equity earnings yield does not reconcile")
        if self.free_cash_flow_yield != self.free_cash_flow / self.market_cap:
            raise ValueError("equity free cash flow yield does not reconcile")
        if len(set(self.unavailable_metrics)) != len(self.unavailable_metrics):
            raise ValueError("equity unavailable metrics must be unique")
        return self


class EquityFundamentalAssessmentV1(ContractModel):
    schema_name: Literal["equity_fundamental_assessment"] = (
        "equity_fundamental_assessment"
    )
    schema_version: Literal["1.0"] = "1.0"
    assessed_at: datetime
    status: EquityFundamentalStatus
    analysis_ready: bool
    instrument_key: Annotated[str, Field(min_length=3, max_length=256)]
    currency: CurrencyCode
    report_age_days: NonNegativeInt
    market_cap_age_seconds: NonNegativeInt
    policy: EquityFundamentalPolicyV1
    market_readiness: MarketReadinessAssessmentV1
    metrics: EquityFundamentalMetricsV1
    blockers: tuple[EquityFundamentalBlocker, ...] = ()
    warnings: tuple[EquityFundamentalWarning, ...] = ()
    facts_only: Literal[True] = True
    no_price_forecast: Literal[True] = True
    no_investment_recommendation: Literal[True] = True
    no_cross_currency_aggregation: Literal[True] = True
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("assessed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("equity assessment timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_assessment(self) -> EquityFundamentalAssessmentV1:
        if len(set(self.blockers)) != len(self.blockers):
            raise ValueError("equity blockers must be unique")
        if len(set(self.warnings)) != len(self.warnings):
            raise ValueError("equity warnings must be unique")
        expected_ready = not self.blockers
        if self.analysis_ready is not expected_ready:
            raise ValueError("equity analysis readiness is inconsistent")
        expected_status = (
            EquityFundamentalStatus.READY
            if expected_ready
            else EquityFundamentalStatus.REJECTED
        )
        if self.status != expected_status:
            raise ValueError("equity assessment status is inconsistent")
        if self.metrics.currency != self.currency:
            raise ValueError("equity assessment currency does not match metrics")
        return self
