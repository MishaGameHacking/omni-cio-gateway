from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import (
    ContractMetadata,
    ContractModel,
    CurrencyCode,
    FiniteDecimal,
)
from omni_cio.contracts.v1.portfolio import InstrumentType


UnitInterval = Annotated[
    Decimal,
    Field(ge=Decimal("0"), le=Decimal("1"), allow_inf_nan=False),
]
PositiveDecimal = Annotated[
    Decimal,
    Field(gt=Decimal("0"), allow_inf_nan=False),
]
NegativeShock = Annotated[
    Decimal,
    Field(gt=Decimal("-1"), lt=Decimal("0"), allow_inf_nan=False),
]
NonNegativeInt = Annotated[int, Field(ge=0)]


class RiskPolicyProfile(StrEnum):
    CONSERVATIVE_CAPITAL_PRESERVATION = "conservative_capital_preservation"


class RiskCheckStatus(StrEnum):
    PASS = "pass"
    WARNING = "warning"
    BREACH = "breach"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class RiskSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    BLOCK = "block"


class RiskOverallStatus(StrEnum):
    PASS = "pass"
    WARNING = "warning"
    BREACH = "breach"
    UNKNOWN = "unknown"


class RiskMissingInputCode(StrEnum):
    ISSUER = "issuer"
    SECTOR = "sector"
    LIQUIDITY = "liquidity"
    CREDIT_RATING = "credit_rating"
    BOND_DURATION = "bond_duration"
    MAX_DRAWDOWN = "max_drawdown"
    FX_RATES = "fx_rates"
    RISK_CLASSIFICATION = "risk_classification"


class RiskCheckCode(StrEnum):
    DATA_QUALITY = "data_quality"
    ALLOWED_CURRENCY = "allowed_currency"
    NON_BASE_CURRENCY_WEIGHT = "non_base_currency_weight"
    CASH_RESERVE = "cash_reserve"
    POSITION_WEIGHT = "position_weight"
    ASSET_CLASS_WEIGHT = "asset_class_weight"
    TOP5_CONCENTRATION = "top5_concentration"
    HHI_CONCENTRATION = "hhi_concentration"
    STRESS_LOSS = "stress_loss"
    ALLOWED_INSTRUMENT_TYPE = "allowed_instrument_type"
    INSTRUMENT_ALLOWLIST = "instrument_allowlist"
    INSTRUMENT_DENYLIST = "instrument_denylist"
    ISSUER_WEIGHT = "issuer_weight"
    SECTOR_WEIGHT = "sector_weight"
    HIGH_RISK_WEIGHT = "high_risk_weight"
    ILLIQUID_WEIGHT = "illiquid_weight"
    CREDIT_RATING = "credit_rating"
    BOND_DURATION = "bond_duration"
    MAX_DRAWDOWN = "max_drawdown"
    ORDER_WEIGHT = "order_weight"
    DAILY_TURNOVER = "daily_turnover"
    MARGIN_TRADING = "margin_trading"
    SHORT_SALES = "short_sales"
    DERIVATIVES = "derivatives"
    CURRENCY_OPERATIONS = "currency_operations"


class ConservativeRiskPolicyV1(ContractModel):
    policy_name: Annotated[str, Field(min_length=1, max_length=128)]
    policy_version: Annotated[str, Field(pattern=r"^1\.[0-9]+$")]
    profile: RiskPolicyProfile
    personalized: bool
    base_currency: CurrencyCode
    allowed_currencies: tuple[CurrencyCode, ...]
    allowed_instrument_types: tuple[InstrumentType, ...]
    prohibited_instrument_types: tuple[InstrumentType, ...]
    allowed_instrument_keys: tuple[
        Annotated[str, Field(min_length=3, max_length=256)], ...
    ] = ()
    prohibited_instrument_keys: tuple[
        Annotated[str, Field(min_length=3, max_length=256)], ...
    ] = ()
    max_position_weight: UnitInterval
    max_issuer_weight: UnitInterval
    max_sector_weight: UnitInterval
    max_asset_class_weight: UnitInterval
    max_top5_invested_weight: UnitInterval
    max_hhi_invested: UnitInterval
    min_cash_reserve_weight: UnitInterval
    max_high_risk_weight: UnitInterval
    max_illiquid_weight: UnitInterval
    max_non_base_currency_weight: UnitInterval
    minimum_credit_rating: Annotated[str, Field(min_length=1, max_length=32)]
    max_duration_years: PositiveDecimal
    max_drawdown: UnitInterval
    stress_shock: NegativeShock
    max_stress_loss_ratio: UnitInterval
    max_order_weight: UnitInterval
    max_daily_turnover_weight: UnitInterval
    allow_margin: bool
    allow_short_sales: bool
    allow_derivatives: bool
    allow_currency_operations: bool

    @field_validator("base_currency", mode="before")
    @classmethod
    def normalize_base_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("allowed_currencies", mode="before")
    @classmethod
    def normalize_allowed_currencies(cls, value: object) -> object:
        if isinstance(value, (list, tuple)):
            return tuple(
                item.upper() if isinstance(item, str) else item
                for item in value
            )
        return value

    @model_validator(mode="after")
    def validate_policy(self) -> ConservativeRiskPolicyV1:
        if self.personalized:
            raise ValueError(
                "default conservative policy must not be personalized"
            )
        if len(self.allowed_currencies) != len(set(self.allowed_currencies)):
            raise ValueError("allowed currencies must be unique")
        if self.base_currency not in self.allowed_currencies:
            raise ValueError("base currency must be allowed")
        allowed_types = set(self.allowed_instrument_types)
        prohibited_types = set(self.prohibited_instrument_types)
        if allowed_types & prohibited_types:
            raise ValueError(
                "allowed and prohibited instrument types overlap"
            )
        if set(self.allowed_instrument_keys) & set(
            self.prohibited_instrument_keys
        ):
            raise ValueError(
                "allowed and prohibited instrument keys overlap"
            )
        if any(
            (
                self.allow_margin,
                self.allow_short_sales,
                self.allow_derivatives,
                self.allow_currency_operations,
            )
        ):
            raise ValueError(
                "conservative policy cannot enable high-risk execution"
            )
        return self


class RiskCheckV1(ContractModel):
    check_id: Annotated[
        str,
        Field(pattern=r"^[a-z0-9][a-z0-9_.:-]{2,255}$"),
    ]
    code: RiskCheckCode
    status: RiskCheckStatus
    severity: RiskSeverity
    message: Annotated[str, Field(min_length=1, max_length=512)]
    currency: CurrencyCode | None = None
    subject: Annotated[str | None, Field(max_length=256)] = None
    observed_value: FiniteDecimal | None = None
    limit_value: FiniteDecimal | None = None
    missing_data: tuple[RiskMissingInputCode, ...] = ()

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_check(self) -> RiskCheckV1:
        if self.status == RiskCheckStatus.UNKNOWN and not self.missing_data:
            raise ValueError(
                "unknown risk check requires missing-data codes"
            )
        if self.status != RiskCheckStatus.UNKNOWN and self.missing_data:
            raise ValueError(
                "only unknown checks may contain missing-data codes"
            )
        if self.status in (
            RiskCheckStatus.PASS,
            RiskCheckStatus.WARNING,
            RiskCheckStatus.BREACH,
        ):
            if self.observed_value is None or self.limit_value is None:
                raise ValueError(
                    "threshold checks require observed and limit values"
                )
        if (
            self.status == RiskCheckStatus.NOT_APPLICABLE
            and self.severity != RiskSeverity.INFO
        ):
            raise ValueError(
                "not-applicable checks must be informational"
            )
        return self


class RiskPolicyEvaluationV1(ContractModel):
    metadata: ContractMetadata
    policy: ConservativeRiskPolicyV1
    overall_status: RiskOverallStatus
    decision_ready: bool
    checks: tuple[RiskCheckV1, ...]
    breach_count: NonNegativeInt
    warning_count: NonNegativeInt
    unknown_count: NonNegativeInt
    no_cross_currency_aggregation: bool

    @model_validator(mode="after")
    def validate_evaluation(self) -> RiskPolicyEvaluationV1:
        if self.metadata.schema_name != "risk_policy_evaluation":
            raise ValueError(
                "schema_name must be risk_policy_evaluation"
            )
        ids = [check.check_id for check in self.checks]
        if len(ids) != len(set(ids)):
            raise ValueError("risk check IDs must be unique")
        breaches = sum(
            check.status == RiskCheckStatus.BREACH
            for check in self.checks
        )
        warnings = sum(
            check.status == RiskCheckStatus.WARNING
            for check in self.checks
        )
        unknowns = sum(
            check.status == RiskCheckStatus.UNKNOWN
            for check in self.checks
        )
        if (breaches, warnings, unknowns) != (
            self.breach_count,
            self.warning_count,
            self.unknown_count,
        ):
            raise ValueError(
                "risk status counters do not match checks"
            )

        blocking_breach = any(
            check.status == RiskCheckStatus.BREACH
            and check.severity == RiskSeverity.BLOCK
            for check in self.checks
        )
        blocking_unknown = any(
            check.status == RiskCheckStatus.UNKNOWN
            and check.severity == RiskSeverity.BLOCK
            for check in self.checks
        )
        expected_ready = not blocking_breach and not blocking_unknown
        if self.decision_ready != expected_ready:
            raise ValueError(
                "decision_ready does not match blocking checks"
            )

        if blocking_breach:
            expected_status = RiskOverallStatus.BREACH
        elif blocking_unknown:
            expected_status = RiskOverallStatus.UNKNOWN
        elif breaches or warnings:
            expected_status = RiskOverallStatus.WARNING
        else:
            expected_status = RiskOverallStatus.PASS
        if self.overall_status != expected_status:
            raise ValueError(
                "overall risk status does not match checks"
            )
        if not self.no_cross_currency_aggregation:
            raise ValueError("cross-currency aggregation is forbidden")
        return self
