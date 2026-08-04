from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
import hashlib
import json
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel, CurrencyCode, FiniteDecimal
from omni_cio.contracts.v1.investment_policy import PolicyReferenceV1
from omni_cio.contracts.v1.portfolio import InstrumentType


Sha256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
UnitWeight = Annotated[
    Decimal,
    Field(ge=Decimal("0"), le=Decimal("1"), allow_inf_nan=False),
]
NonNegativeDecimal = Annotated[
    Decimal,
    Field(ge=Decimal("0"), allow_inf_nan=False),
]
PositiveDecimal = Annotated[
    Decimal,
    Field(gt=Decimal("0"), allow_inf_nan=False),
]
Shock = Annotated[
    Decimal,
    Field(gt=Decimal("-1"), le=Decimal("0"), allow_inf_nan=False),
]


class RiskVectorKind(StrEnum):
    PERMANENT_LOSS = "permanent_loss"
    MARKET = "market"
    CONCENTRATION = "concentration"
    LIQUIDITY = "liquidity"
    CREDIT = "credit"
    CURRENCY = "currency"
    INFLATION_OPPORTUNITY = "inflation_opportunity"
    DATA_QUALITY = "data_quality"


class RiskSeverity(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    BREACH = "breach"
    UNKNOWN = "unknown"


class RiskExposureDimension(StrEnum):
    POSITION = "position"
    ISSUER = "issuer"
    GROUP = "group"
    SECTOR = "sector"
    ASSET_CLASS = "asset_class"
    CURRENCY = "currency"


class RiskLimitSource(StrEnum):
    IPS = "ips"
    OWNER_OVERLAY = "owner_overlay"
    SYSTEM_GUARDRAIL = "system_guardrail"


class RiskExposureMode(StrEnum):
    DIRECT = "direct"
    FUND_LOOKTHROUGH = "fund_lookthrough"


class PermanentLossStatus(StrEnum):
    PASS = "pass"
    WATCH = "watch"
    BLOCK = "block"
    UNKNOWN = "unknown"


class RiskBlockerCode(StrEnum):
    IPS_NOT_READY = "ips_not_ready"
    POLICY_BINDING_MISMATCH = "policy_binding_mismatch"
    PORTFOLIO_VALUE_NON_POSITIVE = "portfolio_value_non_positive"
    FX_PROVENANCE_MISSING = "fx_provenance_missing"
    EXPOSURE_INCOMPLETE = "exposure_incomplete"
    FUND_XRAY_REQUIRED = "fund_xray_required"
    FUND_XRAY_NOT_READY = "fund_xray_not_ready"
    CREDIT_EVIDENCE_REQUIRED = "credit_evidence_required"
    CREDIT_NOT_READY = "credit_not_ready"
    ACTIVE_DEFAULT = "active_default"
    CREDIT_FLOOR_BREACH = "credit_floor_breach"
    LIQUIDITY_RESERVE_BREACH = "liquidity_reserve_breach"
    POSITION_LIMIT_BREACH = "position_limit_breach"
    ISSUER_LIMIT_BREACH = "issuer_limit_breach"
    GROUP_LIMIT_BREACH = "group_limit_breach"
    SECTOR_LIMIT_BREACH = "sector_limit_breach"
    ASSET_CLASS_LIMIT_BREACH = "asset_class_limit_breach"
    CURRENCY_LIMIT_BREACH = "currency_limit_breach"
    MAX_DRAWDOWN_BREACH = "max_drawdown_breach"
    PERMANENT_LOSS_BLOCK = "permanent_loss_block"
    PERMANENT_LOSS_UNKNOWN = "permanent_loss_unknown"
    LIQUIDITY_EVIDENCE_MISSING = "liquidity_evidence_missing"
    LIQUIDITY_EVIDENCE_STALE = "liquidity_evidence_stale"
    TRADE_BINDING_MISMATCH = "trade_binding_mismatch"
    NEGATIVE_AFTER_VALUE = "negative_after_value"


class RiskExposureSliceV1(ContractModel):
    dimension: RiskExposureDimension
    bucket_key: Annotated[str, Field(min_length=1, max_length=256)]
    weight_within_position: UnitWeight


class RiskFxConversionV1(ContractModel):
    native_currency: CurrencyCode
    base_currency: CurrencyCode
    rate_to_base: PositiveDecimal
    source_sha256: Sha256
    as_of: datetime

    @field_validator("native_currency", "base_currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("as_of")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("FX as_of must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_cross_currency(self) -> RiskFxConversionV1:
        if self.native_currency == self.base_currency:
            raise ValueError("FX conversion is only valid for cross-currency positions")
        return self


class PositionLiquidityRiskInputV1(ContractModel):
    daily_exit_capacity_base: NonNegativeDecimal | None = None
    spread_bps: NonNegativeDecimal | None = None
    as_of: datetime
    source_sha256: Sha256

    @field_validator("as_of")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("liquidity as_of must be timezone-aware")
        return value.astimezone(timezone.utc)


class PositionCreditRiskInputV1(ContractModel):
    credit_passport_sha256: Sha256
    decision_ready: bool
    policy_floor_passed: bool
    active_default_event: bool


class PositionPermanentLossInputV1(ContractModel):
    status: PermanentLossStatus
    evidence_sha256s: tuple[Sha256, ...] = ()

    @field_validator("evidence_sha256s", mode="before")
    @classmethod
    def normalize_sources(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("permanent-loss evidence hashes must be a collection")
        return tuple(sorted(set(value)))


class RiskPositionV1(ContractModel):
    stable_key: Annotated[str, Field(min_length=3, max_length=256)]
    instrument_type: InstrumentType
    native_currency: CurrencyCode
    native_market_value: NonNegativeDecimal
    base_currency: CurrencyCode
    base_market_value: NonNegativeDecimal
    fx: RiskFxConversionV1 | None = None
    exposure_mode: RiskExposureMode
    exposures: Annotated[tuple[RiskExposureSliceV1, ...], Field(min_length=1)]
    fund_xray_sha256: Sha256 | None = None
    fund_xray_decision_ready: bool | None = None
    liquidity: PositionLiquidityRiskInputV1 | None = None
    credit: PositionCreditRiskInputV1 | None = None
    permanent_loss: PositionPermanentLossInputV1

    @field_validator("native_currency", "base_currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("exposures", mode="before")
    @classmethod
    def normalize_exposures(cls, value: object) -> object:
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("risk exposures must be a collection")
        return tuple(
            sorted(
                value,
                key=lambda row: (
                    _item_key(row, "dimension"),
                    _item_key(row, "bucket_key"),
                ),
            )
        )

    @model_validator(mode="after")
    def validate_position(self) -> RiskPositionV1:
        if self.native_currency == self.base_currency:
            if self.fx is not None:
                raise ValueError("base-currency position cannot carry FX conversion")
            if self.base_market_value != self.native_market_value:
                raise ValueError("base-currency market value must equal native value")
        else:
            if self.fx is None:
                raise ValueError("cross-currency position requires explicit FX provenance")
            if (
                self.fx.native_currency != self.native_currency
                or self.fx.base_currency != self.base_currency
            ):
                raise ValueError("FX currencies do not match position currencies")
            if self.base_market_value != self.native_market_value * self.fx.rate_to_base:
                raise ValueError("base market value does not reconcile to explicit FX rate")

        keys = [(row.dimension, row.bucket_key) for row in self.exposures]
        if len(keys) != len(set(keys)):
            raise ValueError("risk exposure buckets must be unique per dimension")
        totals: dict[RiskExposureDimension, Decimal] = {}
        for row in self.exposures:
            totals[row.dimension] = (
                totals.get(row.dimension, Decimal("0")) + row.weight_within_position
            )
        if any(
            abs(total - Decimal("1")) > Decimal("0.0001")
            for total in totals.values()
        ):
            raise ValueError("each supplied exposure dimension must reconcile to 100%")

        if self.exposure_mode is RiskExposureMode.FUND_LOOKTHROUGH:
            if self.instrument_type is not InstrumentType.ETF:
                raise ValueError("fund look-through mode requires ETF instrument")
            if self.fund_xray_sha256 is None or self.fund_xray_decision_ready is None:
                raise ValueError("fund look-through requires X-Ray identity/readiness")
        else:
            if self.instrument_type is InstrumentType.ETF:
                raise ValueError("ETF risk position requires fund look-through mode")
            if (
                self.fund_xray_sha256 is not None
                or self.fund_xray_decision_ready is not None
            ):
                raise ValueError("direct position cannot carry fund X-Ray fields")

        if self.instrument_type is InstrumentType.BOND and self.credit is None:
            raise ValueError("bond risk position requires credit evidence")
        if self.instrument_type is not InstrumentType.BOND and self.credit is not None:
            raise ValueError("non-bond risk position cannot carry credit evidence")
        return self


class PortfolioRiskInputV1(ContractModel):
    portfolio_snapshot_sha256: Sha256
    policy_reference: PolicyReferenceV1
    base_currency: CurrencyCode
    cash_base: NonNegativeDecimal
    positions: tuple[RiskPositionV1, ...]
    data_quality_codes: tuple[
        Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]{2,63}$")], ...
    ] = ()

    @field_validator("base_currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("positions", mode="before")
    @classmethod
    def normalize_positions(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("risk positions must be a collection")
        return tuple(sorted(value, key=lambda row: _item_key(row, "stable_key")))

    @field_validator("data_quality_codes", mode="before")
    @classmethod
    def normalize_codes(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("data quality codes must be a collection")
        return tuple(sorted({str(item).strip().upper() for item in value}))

    @model_validator(mode="after")
    def validate_portfolio(self) -> PortfolioRiskInputV1:
        keys = [row.stable_key for row in self.positions]
        if len(keys) != len(set(keys)):
            raise ValueError("risk positions must have unique stable keys")
        if any(row.base_currency != self.base_currency for row in self.positions):
            raise ValueError("all position base currencies must match portfolio base currency")
        return self

    @property
    def total_value_base(self) -> Decimal:
        return self.cash_base + sum(
            (row.base_market_value for row in self.positions),
            Decimal("0"),
        )


class RiskLimitV1(ContractModel):
    dimension: RiskExposureDimension
    max_weight: UnitWeight
    source: RiskLimitSource
    hard: bool
    owner_confirmed: bool = False

    @model_validator(mode="after")
    def validate_limit(self) -> RiskLimitV1:
        if (
            self.dimension is RiskExposureDimension.POSITION
            and self.source is not RiskLimitSource.IPS
        ):
            raise ValueError("position limit outside IPS is not supported")
        if self.source is RiskLimitSource.SYSTEM_GUARDRAIL and (
            self.hard or self.owner_confirmed
        ):
            raise ValueError("system guardrail cannot impersonate owner hard policy")
        if self.source is RiskLimitSource.OWNER_OVERLAY and not self.owner_confirmed:
            raise ValueError("owner overlay requires explicit owner confirmation")
        if self.source is RiskLimitSource.IPS and not self.owner_confirmed:
            raise ValueError("IPS-derived hard limit must be owner-confirmed")
        return self


class RiskEngineSettingsV1(ContractModel):
    additional_limits: tuple[RiskLimitV1, ...] = ()
    max_exit_days_soft: PositiveDecimal = Decimal("5")
    max_spread_bps_soft: NonNegativeDecimal = Decimal("200")
    liquidity_max_age_seconds: Annotated[int, Field(ge=30)] = 300
    future_tolerance_seconds: Annotated[int, Field(ge=0)] = 60

    @field_validator("additional_limits", mode="before")
    @classmethod
    def normalize_limits(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("additional risk limits must be a collection")
        return tuple(
            sorted(
                value,
                key=lambda row: (
                    _item_key(row, "dimension"),
                    _item_key(row, "source"),
                ),
            )
        )

    @model_validator(mode="after")
    def validate_limits(self) -> RiskEngineSettingsV1:
        keys = [(row.dimension, row.source) for row in self.additional_limits]
        if len(keys) != len(set(keys)):
            raise ValueError("additional limits must be unique by dimension/source")
        return self


class MacroRiskAssumptionsV1(ContractModel):
    annual_inflation_rate: UnitWeight | None = None
    annual_cash_opportunity_rate: UnitWeight | None = None


class StressBucketShockV1(ContractModel):
    bucket_key: Annotated[str, Field(min_length=1, max_length=256)]
    shock: Shock


class StressScenarioDefinitionV1(ContractModel):
    scenario_id: Annotated[
        str,
        Field(pattern=r"^stress_[a-z0-9][a-z0-9_-]{2,63}$"),
    ]
    name: Annotated[str, Field(min_length=1, max_length=128)]
    dimension: RiskExposureDimension
    default_shock: Shock = Decimal("0")
    bucket_shocks: tuple[StressBucketShockV1, ...] = ()

    @field_validator("bucket_shocks", mode="before")
    @classmethod
    def normalize_shocks(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("stress bucket shocks must be a collection")
        return tuple(sorted(value, key=lambda row: _item_key(row, "bucket_key")))

    @model_validator(mode="after")
    def validate_shocks(self) -> StressScenarioDefinitionV1:
        keys = [row.bucket_key for row in self.bucket_shocks]
        if len(keys) != len(set(keys)):
            raise ValueError("stress scenario bucket shocks must have unique keys")
        return self


class ProposedTradeRiskEffectV1(ContractModel):
    trade_id: Annotated[
        str,
        Field(pattern=r"^trade_[a-z0-9][a-z0-9_-]{2,63}$"),
    ]
    stable_key: Annotated[str, Field(min_length=3, max_length=256)]
    expected_before_value_base: NonNegativeDecimal
    cash_delta_base: FiniteDecimal
    after_position: RiskPositionV1 | None = None

    @model_validator(mode="after")
    def validate_identity(self) -> ProposedTradeRiskEffectV1:
        if (
            self.after_position is not None
            and self.after_position.stable_key != self.stable_key
        ):
            raise ValueError("after-position identity must match proposed trade stable key")
        return self


class ConcentrationRowV1(ContractModel):
    dimension: RiskExposureDimension
    bucket_key: Annotated[str, Field(min_length=1, max_length=256)]
    weight: UnitWeight
    applicable_limit: UnitWeight | None = None
    limit_source: RiskLimitSource | None = None
    hard_limit: bool = False
    breached: bool = False

    @model_validator(mode="after")
    def validate_limit(self) -> ConcentrationRowV1:
        if (self.applicable_limit is None) != (self.limit_source is None):
            raise ValueError("concentration limit and source must be supplied together")
        if self.applicable_limit is None and (self.hard_limit or self.breached):
            raise ValueError("concentration cannot breach an absent limit")
        if (
            self.applicable_limit is not None
            and self.breached != (self.weight > self.applicable_limit)
        ):
            raise ValueError("concentration breach flag must reconcile")
        return self


class ConcentrationSummaryV1(ContractModel):
    top_1_weight: UnitWeight
    top_3_weight: UnitWeight
    top_5_weight: UnitWeight
    rows: tuple[ConcentrationRowV1, ...]


class LiquidityPositionResultV1(ContractModel):
    stable_key: Annotated[str, Field(min_length=3, max_length=256)]
    position_weight: UnitWeight
    exit_days: NonNegativeDecimal | None = None
    spread_bps: NonNegativeDecimal | None = None
    stale: bool = False
    unknown: bool = False


class StressScenarioResultV1(ContractModel):
    scenario_id: Annotated[
        str,
        Field(pattern=r"^stress_[a-z0-9][a-z0-9_-]{2,63}$"),
    ]
    portfolio_change_base: FiniteDecimal
    portfolio_change_weight: Annotated[
        Decimal,
        Field(ge=Decimal("-1"), le=Decimal("0"), allow_inf_nan=False),
    ]
    max_drawdown_limit: UnitWeight | None = None
    drawdown_breach: bool = False

    @model_validator(mode="after")
    def validate_drawdown(self) -> StressScenarioResultV1:
        if self.max_drawdown_limit is None and self.drawdown_breach:
            raise ValueError("drawdown cannot breach an absent policy limit")
        if self.max_drawdown_limit is not None:
            expected = abs(self.portfolio_change_weight) > self.max_drawdown_limit
            if self.drawdown_breach != expected:
                raise ValueError("drawdown breach flag must reconcile")
        return self


class RiskVectorV1(ContractModel):
    kind: RiskVectorKind
    severity: RiskSeverity
    hard_breach: bool
    metrics: tuple[Annotated[str, Field(min_length=1, max_length=256)], ...] = ()
    evidence_codes: tuple[
        Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]{2,63}$")], ...
    ] = ()

    @field_validator("metrics", mode="before")
    @classmethod
    def normalize_metrics(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("risk vector metrics must be a collection")
        return tuple(sorted(set(str(item) for item in value)))

    @field_validator("evidence_codes", mode="before")
    @classmethod
    def normalize_codes(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("risk vector evidence codes must be a collection")
        return tuple(sorted({str(item).strip().upper() for item in value}))

    @model_validator(mode="after")
    def validate_severity(self) -> RiskVectorV1:
        if self.hard_breach and self.severity is not RiskSeverity.BREACH:
            raise ValueError("hard breach vector must use BREACH severity")
        return self


class PortfolioRiskStateV1(ContractModel):
    total_value_base: PositiveDecimal
    cash_base: NonNegativeDecimal
    cash_weight: UnitWeight
    concentration: ConcentrationSummaryV1
    liquidity: tuple[LiquidityPositionResultV1, ...]
    stress: tuple[StressScenarioResultV1, ...]
    vectors: Annotated[tuple[RiskVectorV1, ...], Field(min_length=8, max_length=8)]
    blockers: tuple[RiskBlockerCode, ...] = ()
    policy_compliant: bool

    @field_validator("vectors", mode="before")
    @classmethod
    def normalize_vectors(cls, value: object) -> object:
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("risk vectors must be a collection")
        return tuple(sorted(value, key=lambda row: _item_key(row, "kind")))

    @field_validator("blockers", mode="before")
    @classmethod
    def normalize_blockers(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("risk blockers must be a collection")
        return tuple(sorted(set(value), key=str))

    @model_validator(mode="after")
    def validate_state(self) -> PortfolioRiskStateV1:
        kinds = [row.kind for row in self.vectors]
        if set(kinds) != set(RiskVectorKind) or len(kinds) != len(set(kinds)):
            raise ValueError("risk state must contain exactly one vector of every kind")
        hard_breach = any(row.hard_breach for row in self.vectors)
        if self.policy_compliant == hard_breach:
            raise ValueError("policy compliance must be inverse of hard breach presence")
        return self


class PortfolioRiskAssessmentV1(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    assessed_at: datetime
    portfolio_snapshot_sha256: Sha256
    policy_reference: PolicyReferenceV1
    before: PortfolioRiskStateV1
    after: PortfolioRiskStateV1
    proposed_trade_ids: tuple[
        Annotated[str, Field(pattern=r"^trade_[a-z0-9][a-z0-9_-]{2,63}$")], ...
    ] = ()
    new_blockers: tuple[RiskBlockerCode, ...] = ()
    resolved_blockers: tuple[RiskBlockerCode, ...] = ()
    decision_ready: bool
    plan_eligible: bool
    assessment_sha256: Sha256
    trading_methods: Literal[False] = False

    @field_validator("assessed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("risk assessment timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("proposed_trade_ids", mode="before")
    @classmethod
    def normalize_trade_ids(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("proposed trade IDs must be a collection")
        return tuple(sorted(set(value)))

    @field_validator("new_blockers", "resolved_blockers", mode="before")
    @classmethod
    def normalize_blockers(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("risk blocker deltas must be collections")
        return tuple(sorted(set(value), key=str))

    @model_validator(mode="after")
    def validate_assessment(self) -> PortfolioRiskAssessmentV1:
        if set(self.new_blockers) != set(self.after.blockers) - set(
            self.before.blockers
        ):
            raise ValueError("new blockers do not reconcile to before/after states")
        if set(self.resolved_blockers) != set(self.before.blockers) - set(
            self.after.blockers
        ):
            raise ValueError("resolved blockers do not reconcile to before/after states")
        if self.plan_eligible != (self.decision_ready and self.after.policy_compliant):
            raise ValueError("plan eligibility must require ready and compliant after-state")
        if self.assessment_sha256 != portfolio_risk_sha256(self):
            raise ValueError("assessment SHA-256 does not match canonical payload")
        return self


def _item_key(row: object, attribute: str) -> str:
    if isinstance(row, dict):
        value = row.get(attribute)
    else:
        value = getattr(row, attribute, None)
    if isinstance(value, StrEnum):
        return value.value
    return str(value)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def portfolio_risk_sha256(assessment: PortfolioRiskAssessmentV1) -> str:
    payload = assessment.model_dump(mode="json", exclude={"assessment_sha256"})
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
