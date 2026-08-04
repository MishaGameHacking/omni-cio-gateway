from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
import hashlib
import json
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel, CurrencyCode
from omni_cio.contracts.v1.investment_policy import PolicyReferenceV1
from omni_cio.contracts.v1.meta_strategy import StrategyComponentKind, StrategyRegime
from omni_cio.contracts.v1.portfolio import InstrumentType
from omni_cio.contracts.v1.portfolio_risk import (
    PortfolioRiskAssessmentV1,
    RiskBlockerCode,
    RiskPositionV1,
)


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
Bps = Annotated[
    Decimal,
    Field(ge=Decimal("0"), le=Decimal("10000"), allow_inf_nan=False),
]
PositiveInt = Annotated[int, Field(gt=0)]
NonNegativeInt = Annotated[int, Field(ge=0)]


class OptimizerBlockerCode(StrEnum):
    STRATEGY_NOT_READY = "strategy_not_ready"
    STRATEGY_BINDING_MISMATCH = "strategy_binding_mismatch"
    RISK_BINDING_MISMATCH = "risk_binding_mismatch"
    POLICY_BINDING_MISMATCH = "policy_binding_mismatch"
    PORTFOLIO_BINDING_MISMATCH = "portfolio_binding_mismatch"
    ASSET_UNIVERSE_INCOMPLETE = "asset_universe_incomplete"
    REQUIRED_COMPONENT_UNAVAILABLE = "required_component_unavailable"
    ACCOUNT_ELIGIBILITY_UNKNOWN = "account_eligibility_unknown"
    ACCOUNT_INELIGIBLE = "account_ineligible"
    FRICTION_EVIDENCE_MISSING = "friction_evidence_missing"
    FRICTION_EVIDENCE_STALE = "friction_evidence_stale"
    FRICTION_EVIDENCE_FUTURE = "friction_evidence_future"
    MARKET_EVIDENCE_MISSING = "market_evidence_missing"
    MARKET_EVIDENCE_STALE = "market_evidence_stale"
    MARKET_EVIDENCE_FUTURE = "market_evidence_future"
    MARKET_PRICE_BINDING_MISMATCH = "market_price_binding_mismatch"
    ACCRUED_INTEREST_EVIDENCE_MISSING = "accrued_interest_evidence_missing"
    SPREAD_TOO_WIDE = "spread_too_wide"
    ZERO_SAFE_CAPACITY = "zero_safe_capacity"
    LIQUIDITY_RESERVE_UNFUNDED = "liquidity_reserve_unfunded"
    RISK_REVALIDATION_BASELINE_MISMATCH = "risk_revalidation_baseline_mismatch"
    TARGET_RISK_NOT_READY = "target_risk_not_ready"
    TARGET_POLICY_BREACH = "target_policy_breach"


class OptimizerWarningCode(StrEnum):
    MICROPOSITION_SKIPPED = "microposition_skipped"
    LOT_ROUNDING_RESIDUAL_CASH = "lot_rounding_residual_cash"
    COMPONENT_BUDGET_LEFT_AS_CASH = "component_budget_left_as_cash"
    STAGED_EXECUTION_REQUIRED = "staged_execution_required"
    CAPACITY_SCALED = "capacity_scaled"
    CASH_RESERVE_SCALED_BUYS = "cash_reserve_scaled_buys"
    PARTIAL_FILL_AWARE = "partial_fill_aware"
    NO_ACTION_SELECTED = "no_action_selected"


class OptimizerScenarioKind(StrEnum):
    CURRENT = "current"
    TARGET = "target"
    NO_ACTION = "no_action"


class OptimizerTradeSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OptimizerMarketEvidenceV1(ContractModel):
    stable_key: Annotated[str, Field(min_length=3, max_length=256)]
    as_of: datetime
    source_sha256: Sha256
    clean_unit_price_base: PositiveDecimal
    accrued_interest_per_lot_base: NonNegativeDecimal | None = None
    spread_bps: Bps
    average_daily_turnover_base: PositiveDecimal
    top_of_book_depth_base: PositiveDecimal

    @field_validator("as_of")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("optimizer market timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)


class OptimizerAssetV1(ContractModel):
    stable_key: Annotated[str, Field(min_length=3, max_length=256)]
    component: StrategyComponentKind
    current_lots: NonNegativeInt
    lot_size: PositiveInt
    native_currency: CurrencyCode
    base_currency: CurrencyCode
    unit_full_value_native: PositiveDecimal
    unit_full_value_base: PositiveDecimal
    risk_template: RiskPositionV1
    account_eligible: bool | None
    commission_bps: Bps | None = None
    estimated_sell_tax_bps: Bps | None = None
    friction_as_of: datetime | None = None
    friction_source_sha256s: tuple[Sha256, ...] = ()
    market_evidence: OptimizerMarketEvidenceV1 | None = None

    @field_validator("native_currency", "base_currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("friction_as_of")
    @classmethod
    def normalize_friction_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("optimizer friction timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("friction_source_sha256s", mode="before")
    @classmethod
    def normalize_friction_sources(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("optimizer friction sources must be a collection")
        return tuple(sorted(set(value)))

    @model_validator(mode="after")
    def validate_asset(self) -> OptimizerAssetV1:
        if self.component is StrategyComponentKind.LIQUIDITY_RESERVE:
            raise ValueError("liquidity reserve is cash, not an optimizer asset")
        if self.risk_template.stable_key != self.stable_key:
            raise ValueError("optimizer asset must bind risk-template identity")
        if self.risk_template.native_currency != self.native_currency:
            raise ValueError("optimizer asset native currency mismatch")
        if self.risk_template.base_currency != self.base_currency:
            raise ValueError("optimizer asset base currency mismatch")

        evidence = self.market_evidence
        if evidence is not None:
            if evidence.stable_key != self.stable_key:
                raise ValueError("optimizer market evidence identity mismatch")
            if self.risk_template.instrument_type is InstrumentType.BOND:
                if evidence.accrued_interest_per_lot_base is not None:
                    expected_full_base = evidence.clean_unit_price_base + (
                        evidence.accrued_interest_per_lot_base / Decimal(self.lot_size)
                    )
                    if self.unit_full_value_base != expected_full_base:
                        raise ValueError(
                            "bond full unit value must equal clean price plus accrued interest"
                        )
            else:
                if evidence.accrued_interest_per_lot_base is not None:
                    raise ValueError("non-bond market evidence cannot carry accrued interest")
                if self.unit_full_value_base != evidence.clean_unit_price_base:
                    raise ValueError("non-bond full unit value must equal clean market price")

        current_units = self.current_lots * self.lot_size
        expected_native = Decimal(current_units) * self.unit_full_value_native
        expected_base = Decimal(current_units) * self.unit_full_value_base
        if self.risk_template.native_market_value != expected_native:
            raise ValueError("current native value does not reconcile to lots")
        if self.risk_template.base_market_value != expected_base:
            raise ValueError("current base value does not reconcile to lots")

        if self.native_currency == self.base_currency:
            if self.unit_full_value_native != self.unit_full_value_base:
                raise ValueError("base-currency full unit values must match")
        else:
            if self.risk_template.fx is None:
                raise ValueError("cross-currency optimizer asset requires risk FX")
            if (
                self.unit_full_value_base
                != self.unit_full_value_native * self.risk_template.fx.rate_to_base
            ):
                raise ValueError("optimizer full unit value does not reconcile to FX")
        return self


class PortfolioOptimizerSettingsV1(ContractModel):
    market_max_age_seconds: Annotated[int, Field(ge=30)] = 300
    friction_max_age_seconds: Annotated[int, Field(ge=60)] = 86400
    future_tolerance_seconds: Annotated[int, Field(ge=0)] = 60
    maximum_spread_bps: Bps = Decimal("250")
    maximum_daily_turnover_participation: Annotated[
        Decimal,
        Field(gt=Decimal("0"), le=Decimal("0.50"), allow_inf_nan=False),
    ] = Decimal("0.05")
    maximum_top_of_book_participation: Annotated[
        Decimal,
        Field(gt=Decimal("0"), le=Decimal("1"), allow_inf_nan=False),
    ] = Decimal("0.25")
    maximum_staging_days: Annotated[int, Field(ge=1, le=20)] = 5
    minimum_meaningful_position_weight: UnitWeight = Decimal("0.02")
    maximum_target_positions: Annotated[int, Field(ge=1, le=100)] = 20
    money_quantum: PositiveDecimal = Decimal("0.01")
    weight_quantum: PositiveDecimal = Decimal("0.00000001")


class OptimizerTargetPositionV1(ContractModel):
    stable_key: Annotated[str, Field(min_length=3, max_length=256)]
    component: StrategyComponentKind
    current_lots: NonNegativeInt
    target_lots: NonNegativeInt
    lot_size: PositiveInt
    desired_weight: UnitWeight
    current_value_base: NonNegativeDecimal
    target_value_base: NonNegativeDecimal
    target_weight: UnitWeight

    @model_validator(mode="after")
    def validate_target(self) -> OptimizerTargetPositionV1:
        if self.current_lots < 0 or self.target_lots < 0:
            raise ValueError("optimizer lots cannot be negative")
        return self


class OptimizerRebalanceLegV1(ContractModel):
    trade_id: Annotated[
        str,
        Field(pattern=r"^trade_[a-z0-9][a-z0-9_-]{2,63}$"),
    ]
    stable_key: Annotated[str, Field(min_length=3, max_length=256)]
    component: StrategyComponentKind
    side: OptimizerTradeSide
    current_lots: NonNegativeInt
    target_lots: NonNegativeInt
    quantity_lots: PositiveInt
    lot_size: PositiveInt
    reference_clean_unit_price_base: PositiveDecimal
    gross_notional_base: PositiveDecimal
    accrued_interest_per_lot_base: NonNegativeDecimal
    accrued_interest_base: NonNegativeDecimal
    settlement_notional_base: PositiveDecimal
    commission_bps: Bps
    commission_base: NonNegativeDecimal
    estimated_sell_tax_bps: Bps
    estimated_tax_base: NonNegativeDecimal
    cash_delta_base: Decimal
    required_execution_days: PositiveInt
    daily_turnover_participation: NonNegativeDecimal
    top_of_book_participation: NonNegativeDecimal
    staged_execution_required: bool
    partial_fill_aware: Literal[True] = True
    market_source_sha256: Sha256
    friction_source_sha256s: Annotated[tuple[Sha256, ...], Field(min_length=1)]

    @field_validator("friction_source_sha256s", mode="before")
    @classmethod
    def normalize_sources(cls, value: object) -> object:
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("optimizer leg friction sources must be a collection")
        result = tuple(sorted(set(value)))
        if not result:
            raise ValueError("optimizer leg friction sources cannot be empty")
        return result

    @model_validator(mode="after")
    def validate_leg(self) -> OptimizerRebalanceLegV1:
        expected_lots = abs(self.target_lots - self.current_lots)
        if self.quantity_lots != expected_lots:
            raise ValueError("optimizer leg quantity does not reconcile")
        if self.side is OptimizerTradeSide.BUY and self.target_lots <= self.current_lots:
            raise ValueError("BUY leg must increase lots")
        if self.side is OptimizerTradeSide.SELL and self.target_lots >= self.current_lots:
            raise ValueError("SELL leg must decrease lots")

        expected_gross = (
            Decimal(self.quantity_lots * self.lot_size)
            * self.reference_clean_unit_price_base
        )
        if self.gross_notional_base != expected_gross:
            raise ValueError("optimizer leg clean notional does not reconcile")
        expected_accrued = (
            Decimal(self.quantity_lots) * self.accrued_interest_per_lot_base
        )
        if self.accrued_interest_base != expected_accrued:
            raise ValueError("optimizer leg accrued interest does not reconcile")
        expected_settlement = self.gross_notional_base + self.accrued_interest_base
        if self.settlement_notional_base != expected_settlement:
            raise ValueError("optimizer leg settlement notional does not reconcile")

        if self.side is OptimizerTradeSide.BUY and self.estimated_tax_base != 0:
            raise ValueError("BUY leg cannot carry estimated sell tax")
        expected_cash = (
            -(self.settlement_notional_base + self.commission_base)
            if self.side is OptimizerTradeSide.BUY
            else self.settlement_notional_base
            - self.commission_base
            - self.estimated_tax_base
        )
        if self.cash_delta_base != expected_cash:
            raise ValueError("optimizer leg cash delta does not reconcile")
        if self.staged_execution_required != (self.required_execution_days > 1):
            raise ValueError("staged execution flag does not reconcile")
        return self


class OptimizerScenarioV1(ContractModel):
    kind: OptimizerScenarioKind
    portfolio_value_base: PositiveDecimal
    cash_base: NonNegativeDecimal
    securities_value_base: NonNegativeDecimal
    position_count: NonNegativeInt
    turnover_base: NonNegativeDecimal
    commission_base: NonNegativeDecimal
    estimated_tax_base: NonNegativeDecimal
    policy_compliant: bool
    risk_assessment_sha256: Sha256 | None = None
    risk_blockers: tuple[RiskBlockerCode, ...] = ()

    @field_validator("risk_blockers", mode="before")
    @classmethod
    def normalize_risk_blockers(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("optimizer scenario risk blockers must be a collection")
        return tuple(sorted(set(value), key=str))

    @model_validator(mode="after")
    def validate_value(self) -> OptimizerScenarioV1:
        if self.portfolio_value_base != self.cash_base + self.securities_value_base:
            raise ValueError("optimizer scenario value does not reconcile")
        return self


class PortfolioOptimizerResultV1(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    optimized_at: datetime
    portfolio_snapshot_sha256: Sha256
    policy_reference: PolicyReferenceV1
    current_risk_assessment_sha256: Sha256
    strategy_selection_sha256: Sha256
    selected_regime: StrategyRegime
    targets: tuple[OptimizerTargetPositionV1, ...]
    legs: tuple[OptimizerRebalanceLegV1, ...]
    scenarios: Annotated[
        tuple[OptimizerScenarioV1, ...],
        Field(min_length=3, max_length=3),
    ]
    blockers: tuple[OptimizerBlockerCode, ...] = ()
    warnings: tuple[OptimizerWarningCode, ...] = ()
    target_risk_assessment: PortfolioRiskAssessmentV1 | None = None
    optimizer_ready: bool
    plan_eligible: bool
    optimizer_sha256: Sha256
    trading_methods: Literal[False] = False

    @field_validator("optimized_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("optimizer timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("targets", mode="before")
    @classmethod
    def normalize_targets(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("optimizer targets must be a collection")
        return tuple(sorted(value, key=lambda row: _item_key(row, "stable_key")))

    @field_validator("legs", mode="before")
    @classmethod
    def normalize_legs(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("optimizer legs must be a collection")
        return tuple(sorted(value, key=lambda row: _item_key(row, "trade_id")))

    @field_validator("scenarios", mode="before")
    @classmethod
    def normalize_scenarios(cls, value: object) -> object:
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("optimizer scenarios must be a collection")
        return tuple(sorted(value, key=lambda row: _item_key(row, "kind")))

    @field_validator("blockers", mode="before")
    @classmethod
    def normalize_blockers(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("optimizer blockers must be a collection")
        return tuple(sorted(set(value), key=str))

    @field_validator("warnings", mode="before")
    @classmethod
    def normalize_warnings(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("optimizer warnings must be a collection")
        return tuple(sorted(set(value), key=str))

    @model_validator(mode="after")
    def validate_result(self) -> PortfolioOptimizerResultV1:
        kinds = [row.kind for row in self.scenarios]
        if set(kinds) != set(OptimizerScenarioKind) or len(kinds) != len(set(kinds)):
            raise ValueError("optimizer must contain CURRENT/TARGET/NO_ACTION scenarios")
        trade_ids = [row.trade_id for row in self.legs]
        if len(trade_ids) != len(set(trade_ids)):
            raise ValueError("optimizer trade IDs must be unique")
        target_keys = [row.stable_key for row in self.targets]
        if len(target_keys) != len(set(target_keys)):
            raise ValueError("optimizer target stable keys must be unique")

        expected_ready = not self.blockers
        if self.optimizer_ready != expected_ready:
            raise ValueError("optimizer readiness must match blockers")
        if self.target_risk_assessment is not None:
            if (
                self.target_risk_assessment.portfolio_snapshot_sha256
                != self.portfolio_snapshot_sha256
            ):
                raise ValueError("target risk portfolio binding mismatch")
            if self.target_risk_assessment.policy_reference != self.policy_reference:
                raise ValueError("target risk policy binding mismatch")
        if self.plan_eligible:
            if not self.optimizer_ready or not self.legs:
                raise ValueError("plan eligibility requires ready optimizer with trade legs")
            if (
                self.target_risk_assessment is None
                or not self.target_risk_assessment.plan_eligible
            ):
                raise ValueError("plan eligibility requires WP8 target risk approval")
        if self.optimizer_sha256 != portfolio_optimizer_sha256(self):
            raise ValueError("optimizer SHA-256 does not match canonical payload")
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


def portfolio_optimizer_sha256(result: PortfolioOptimizerResultV1) -> str:
    payload = result.model_dump(mode="json", exclude={"optimizer_sha256"})
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
