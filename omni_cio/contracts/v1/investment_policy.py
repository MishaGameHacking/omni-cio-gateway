from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel, CurrencyCode
from omni_cio.contracts.v1.portfolio import InstrumentType


UnitInterval = Annotated[Decimal, Field(ge=0, le=1, allow_inf_nan=False)]
PositiveYears = Annotated[Decimal, Field(gt=0, le=100, allow_inf_nan=False)]
NonNegativeMoney = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
PolicyVersion = Annotated[str, Field(pattern=r"^[1-9][0-9]{0,5}$")]
MarketCode = Annotated[str, Field(pattern=r"^[A-Z0-9][A-Z0-9_.-]{1,31}$")]
CreditRating = Annotated[str, Field(min_length=1, max_length=32)]


class InvestmentObjective(StrEnum):
    CAPITAL_PRESERVATION = "capital_preservation"
    PRESERVE_PURCHASING_POWER = "preserve_purchasing_power"
    REAL_CAPITAL_GROWTH = "real_capital_growth"
    INCOME = "income"
    BALANCED_GROWTH_INCOME = "balanced_growth_income"


class RiskLevel(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class PolicyLifecycle(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUPERSEDED = "superseded"


class TaxConstraintStatus(StrEnum):
    UNKNOWN = "unknown"
    NONE = "none"
    REVIEWED = "reviewed"


class AccountPolicyType(StrEnum):
    UNKNOWN = "unknown"
    BROKERAGE = "brokerage"
    IIS = "iis"
    OTHER = "other"


class PolicyField(StrEnum):
    OBJECTIVE = "objective"
    TIME_HORIZON = "time_horizon"
    LIQUIDITY_RESERVE = "liquidity_reserve"
    RISK_WILLINGNESS = "risk_willingness"
    RISK_CAPACITY = "risk_capacity"
    MAX_DRAWDOWN = "max_drawdown"
    MAX_POSITION_WEIGHT = "max_position_weight"
    MAX_GROUP_WEIGHT = "max_group_weight"
    MAX_SECTOR_WEIGHT = "max_sector_weight"
    MAX_CURRENCY_WEIGHT = "max_currency_weight"
    MINIMUM_CREDIT_QUALITY = "minimum_credit_quality"
    ALLOWED_MARKETS = "allowed_markets"
    ALLOWED_INSTRUMENT_TYPES = "allowed_instrument_types"
    TAX_STATUS = "tax_status"
    ACCOUNT_TYPE = "account_type"
    REBALANCE_BAND = "rebalance_band"


class PolicySourceKind(StrEnum):
    OWNER_INPUT = "owner_input"
    VERIFIED_ACCOUNT_DATA = "verified_account_data"
    SYSTEM_SAFE_DEFAULT = "system_safe_default"


class PolicyFieldProvenanceV1(ContractModel):
    field: PolicyField
    source_kind: PolicySourceKind
    owner_confirmed: bool
    confirmed_at: datetime
    source_id: Annotated[str | None, Field(max_length=96)] = None

    @field_validator("confirmed_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("confirmed_at must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("source_id")
    @classmethod
    def reject_account_like_source_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        compact = value.replace("-", "").replace("_", "")
        if compact.isdigit() and len(compact) >= 10:
            raise ValueError("source_id must not contain a full account identifier")
        return value


class LiquidityReserveV1(ContractModel):
    amount: NonNegativeMoney
    currency: CurrencyCode

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value


class InvestmentPolicyStatementV1(ContractModel):
    """Versioned owner policy. Missing personal inputs remain explicit None values."""

    schema_version: Literal["1.0"] = "1.0"
    policy_id: Annotated[
        str,
        Field(pattern=r"^ips_[a-z0-9][a-z0-9_-]{2,63}$"),
    ]
    version: PolicyVersion
    lifecycle: PolicyLifecycle
    created_at: datetime
    effective_at: datetime
    review_due_at: datetime
    supersedes_version: PolicyVersion | None = None
    base_currency: CurrencyCode = "RUB"

    objective: InvestmentObjective | None = None
    time_horizon_years: PositiveYears | None = None
    liquidity_reserve: LiquidityReserveV1 | None = None
    risk_willingness: RiskLevel | None = None
    risk_capacity: RiskLevel | None = None
    max_drawdown: UnitInterval | None = None

    max_position_weight: UnitInterval | None = None
    max_group_weight: UnitInterval | None = None
    max_sector_weight: UnitInterval | None = None
    max_currency_weight: UnitInterval | None = None

    minimum_credit_rating: CreditRating | None = None
    credit_rating_scale: Annotated[str | None, Field(max_length=32)] = None

    allowed_markets: tuple[MarketCode, ...] = ()
    allowed_instrument_types: tuple[InstrumentType, ...] = ()
    prohibited_instrument_types: tuple[InstrumentType, ...] = ()

    tax_constraint_status: TaxConstraintStatus = TaxConstraintStatus.UNKNOWN
    account_type: AccountPolicyType = AccountPolicyType.UNKNOWN
    rebalance_band_weight: UnitInterval | None = None

    provenance: tuple[PolicyFieldProvenanceV1, ...] = ()

    allow_margin: Literal[False] = False
    allow_short_sales: Literal[False] = False
    allow_withdrawals: Literal[False] = False
    allow_transfers: Literal[False] = False
    allow_autonomous_real_execution: Literal[False] = False

    @field_validator("created_at", "effective_at", "review_due_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("policy timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("base_currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("allowed_markets", mode="before")
    @classmethod
    def normalize_markets(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("allowed_markets must be a collection of market codes")
        return tuple(sorted({str(item).strip().upper() for item in value}))

    @field_validator("allowed_instrument_types", "prohibited_instrument_types", mode="before")
    @classmethod
    def normalize_instrument_types(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("instrument types must be a collection")
        return tuple(sorted(set(value), key=str))

    @model_validator(mode="after")
    def validate_policy(self) -> InvestmentPolicyStatementV1:
        if self.created_at > self.effective_at:
            raise ValueError("created_at cannot be after effective_at")
        if self.review_due_at <= self.effective_at:
            raise ValueError("review_due_at must be after effective_at")
        if self.review_due_at > self.effective_at + timedelta(days=366):
            raise ValueError("IPS review interval cannot exceed one year")
        if self.version == "1" and self.supersedes_version is not None:
            raise ValueError("first IPS version cannot supersede another version")
        if self.supersedes_version is not None and int(self.supersedes_version) >= int(self.version):
            raise ValueError("supersedes_version must be older than version")
        if set(self.allowed_instrument_types) & set(self.prohibited_instrument_types):
            raise ValueError("instrument type cannot be both allowed and prohibited")
        if (
            self.liquidity_reserve is not None
            and self.liquidity_reserve.currency != self.base_currency
        ):
            raise ValueError("liquidity reserve must use the policy base currency")
        if self.rebalance_band_weight is not None and self.rebalance_band_weight > Decimal("0.50"):
            raise ValueError("rebalance band cannot exceed 50%")
        if self.max_group_weight is not None and self.max_position_weight is not None:
            if self.max_group_weight < self.max_position_weight:
                raise ValueError("group limit cannot be below single-position limit")
        if self.max_sector_weight is not None and self.max_position_weight is not None:
            if self.max_sector_weight < self.max_position_weight:
                raise ValueError("sector limit cannot be below single-position limit")
        if InstrumentType.BOND in self.allowed_instrument_types:
            if bool(self.minimum_credit_rating) != bool(self.credit_rating_scale):
                raise ValueError(
                    "bond policy requires both minimum credit rating and rating scale"
                )
        if len(self.provenance) != len({row.field for row in self.provenance}):
            raise ValueError("policy provenance may contain at most one row per field")
        return self


class PolicyReferenceV1(ContractModel):
    policy_id: Annotated[
        str,
        Field(pattern=r"^ips_[a-z0-9][a-z0-9_-]{2,63}$"),
    ]
    version: PolicyVersion
    fingerprint_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class PolicyReadinessStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    NOT_EFFECTIVE = "not_effective"
    REVIEW_DUE = "review_due"
    SUPERSEDED = "superseded"


class PolicyReadinessBlocker(StrEnum):
    LIFECYCLE_NOT_ACTIVE = "lifecycle_not_active"
    POLICY_NOT_EFFECTIVE = "policy_not_effective"
    POLICY_REVIEW_DUE = "policy_review_due"
    POLICY_SUPERSEDED = "policy_superseded"
    MISSING_REQUIRED_FIELD = "missing_required_field"
    MISSING_PROVENANCE = "missing_provenance"
    OWNER_CONFIRMATION_REQUIRED = "owner_confirmation_required"


class InvestmentPolicyAssessmentV1(ContractModel):
    assessed_at: datetime
    reference: PolicyReferenceV1
    status: PolicyReadinessStatus
    ready_for_personal_sizing: bool
    missing_fields: tuple[PolicyField, ...] = ()
    missing_provenance: tuple[PolicyField, ...] = ()
    unconfirmed_owner_fields: tuple[PolicyField, ...] = ()
    blockers: tuple[PolicyReadinessBlocker, ...] = ()
    annual_review_required: bool
    execution_permissions_unchanged: Literal[True] = True

    @field_validator("assessed_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("assessed_at must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_assessment(self) -> InvestmentPolicyAssessmentV1:
        if len(self.blockers) != len(set(self.blockers)):
            raise ValueError("readiness blockers must be unique")
        if self.ready_for_personal_sizing != (not self.blockers):
            raise ValueError("personal-sizing readiness must match blockers")
        if self.ready_for_personal_sizing and self.status is not PolicyReadinessStatus.READY:
            raise ValueError("ready sizing requires READY policy status")
        return self
