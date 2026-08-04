from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
import hashlib
import json
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel
from omni_cio.contracts.v1.investment_policy import PolicyReferenceV1
from omni_cio.contracts.v1.meta_strategy import StrategyRegime
from omni_cio.contracts.v1.portfolio_optimizer import (
    OptimizerRebalanceLegV1,
    OptimizerTargetPositionV1,
)
from omni_cio.contracts.v1.portfolio_risk import PortfolioRiskStateV1


Sha256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
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
Ratio = Annotated[
    Decimal,
    Field(ge=Decimal("0"), le=Decimal("1"), allow_inf_nan=False),
]
PositiveInt = Annotated[int, Field(gt=0)]


class PortfolioPlanAction(StrEnum):
    BUY = "buy"
    SELL = "sell"
    NO_ACTION = "no_action"


class PlanCancellationCode(StrEnum):
    PLAN_EXPIRED = "plan_expired"
    PORTFOLIO_CHANGED = "portfolio_changed"
    POLICY_CHANGED = "policy_changed"
    CURRENT_RISK_CHANGED = "current_risk_changed"
    STRATEGY_CHANGED = "strategy_changed"
    OPTIMIZER_CHANGED = "optimizer_changed"
    TARGET_RISK_CHANGED = "target_risk_changed"
    MARKET_EVIDENCE_MISSING = "market_evidence_missing"
    MARKET_EVIDENCE_STALE = "market_evidence_stale"
    MARKET_EVIDENCE_FUTURE = "market_evidence_future"
    CLEAN_PRICE_DRIFT_EXCEEDED = "clean_price_drift_exceeded"
    ACCRUED_INTEREST_DRIFT_EXCEEDED = "accrued_interest_drift_exceeded"
    SPREAD_DRIFT_EXCEEDED = "spread_drift_exceeded"
    TURNOVER_CAPACITY_DROPPED = "turnover_capacity_dropped"
    TOP_OF_BOOK_DEPTH_DROPPED = "top_of_book_depth_dropped"
    FX_DRIFT_EXCEEDED = "fx_drift_exceeded"
    FRICTION_CHANGED = "friction_changed"
    ACCOUNT_ELIGIBILITY_CHANGED = "account_eligibility_changed"


class PlanReviewStatus(StrEnum):
    VALID = "valid"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class PortfolioPlanDriftToleranceV1(ContractModel):
    market_max_age_seconds: Annotated[int, Field(ge=30)] = 300
    future_tolerance_seconds: Annotated[int, Field(ge=0)] = 60
    max_clean_price_drift_bps: Bps = Decimal("50")
    max_accrued_interest_drift_bps: Bps = Decimal("10")
    max_spread_widening_bps: Bps = Decimal("50")
    minimum_turnover_ratio: Ratio = Decimal("0.50")
    minimum_top_of_book_depth_ratio: Ratio = Decimal("0.50")
    max_fx_drift_bps: Bps = Decimal("50")


class PortfolioPlanSettingsV1(ContractModel):
    validity_seconds: Annotated[int, Field(ge=60, le=3600)] = 900
    drift_tolerance: PortfolioPlanDriftToleranceV1 = PortfolioPlanDriftToleranceV1()


class PlanMarketBaselineV1(ContractModel):
    stable_key: Annotated[str, Field(min_length=3, max_length=256)]
    lot_size: PositiveInt
    market_source_sha256: Sha256
    market_as_of: datetime
    clean_unit_price_base: PositiveDecimal
    accrued_interest_per_lot_base: NonNegativeDecimal | None = None
    spread_bps: Bps
    average_daily_turnover_base: PositiveDecimal
    top_of_book_depth_base: PositiveDecimal
    friction_as_of: datetime
    friction_source_sha256s: Annotated[tuple[Sha256, ...], Field(min_length=1)]
    commission_bps: Bps
    estimated_sell_tax_bps: Bps
    account_eligible: Literal[True]
    fx_rate_to_base: PositiveDecimal | None = None
    fx_source_sha256: Sha256 | None = None
    fx_as_of: datetime | None = None

    @field_validator("market_as_of", "friction_as_of")
    @classmethod
    def normalize_required_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("plan evidence timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("fx_as_of")
    @classmethod
    def normalize_optional_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("plan FX timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("friction_source_sha256s", mode="before")
    @classmethod
    def normalize_sources(cls, value: object) -> object:
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("plan friction sources must be a collection")
        result = tuple(sorted(set(value)))
        if not result:
            raise ValueError("plan friction sources cannot be empty")
        return result

    @model_validator(mode="after")
    def validate_fx(self) -> PlanMarketBaselineV1:
        supplied = (
            self.fx_rate_to_base is not None,
            self.fx_source_sha256 is not None,
            self.fx_as_of is not None,
        )
        if any(supplied) and not all(supplied):
            raise ValueError("plan FX baseline must be complete or absent")
        return self


class PlanMarketObservationV1(ContractModel):
    stable_key: Annotated[str, Field(min_length=3, max_length=256)]
    observed_at: datetime
    market_source_sha256: Sha256
    clean_unit_price_base: PositiveDecimal
    accrued_interest_per_lot_base: NonNegativeDecimal | None = None
    spread_bps: Bps
    average_daily_turnover_base: PositiveDecimal
    top_of_book_depth_base: PositiveDecimal
    friction_source_sha256s: Annotated[tuple[Sha256, ...], Field(min_length=1)]
    commission_bps: Bps
    estimated_sell_tax_bps: Bps
    account_eligible: bool | None
    fx_rate_to_base: PositiveDecimal | None = None
    fx_source_sha256: Sha256 | None = None
    fx_as_of: datetime | None = None

    @field_validator("observed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("plan market observation timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("fx_as_of")
    @classmethod
    def normalize_optional_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("plan observed FX timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("friction_source_sha256s", mode="before")
    @classmethod
    def normalize_sources(cls, value: object) -> object:
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("observed friction sources must be a collection")
        result = tuple(sorted(set(value)))
        if not result:
            raise ValueError("observed friction sources cannot be empty")
        return result

    @model_validator(mode="after")
    def validate_fx(self) -> PlanMarketObservationV1:
        supplied = (
            self.fx_rate_to_base is not None,
            self.fx_source_sha256 is not None,
            self.fx_as_of is not None,
        )
        if any(supplied) and not all(supplied):
            raise ValueError("observed FX state must be complete or absent")
        return self


class PortfolioPlanLegV1(ContractModel):
    sequence: PositiveInt
    action: PortfolioPlanAction
    optimizer_leg: OptimizerRebalanceLegV1 | None = None

    @model_validator(mode="after")
    def validate_leg(self) -> PortfolioPlanLegV1:
        if self.action is PortfolioPlanAction.NO_ACTION:
            if self.optimizer_leg is not None:
                raise ValueError("NO_ACTION plan leg cannot carry optimizer trade leg")
            return self
        if self.optimizer_leg is None:
            raise ValueError("actionable plan leg requires exact optimizer leg")
        expected = PortfolioPlanAction(self.optimizer_leg.side.value)
        if self.action is not expected:
            raise ValueError("plan action must match optimizer trade side")
        return self


class PlanCancellationConditionV1(ContractModel):
    code: PlanCancellationCode
    hard_cancel: Literal[True] = True


class PortfolioPlanV1(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    object_type: Literal["PORTFOLIO_PLAN"] = "PORTFOLIO_PLAN"
    created_at: datetime
    expires_at: datetime
    portfolio_snapshot_sha256: Sha256
    policy_reference: PolicyReferenceV1
    current_risk_assessment_sha256: Sha256
    strategy_selection_sha256: Sha256
    optimizer_sha256: Sha256
    target_risk_assessment_sha256: Sha256
    selected_regime: StrategyRegime
    targets: tuple[OptimizerTargetPositionV1, ...]
    legs: Annotated[tuple[PortfolioPlanLegV1, ...], Field(min_length=1)]
    market_baselines: tuple[PlanMarketBaselineV1, ...]
    current_value_base: PositiveDecimal
    target_value_base: PositiveDecimal
    current_cash_base: NonNegativeDecimal
    target_cash_base: NonNegativeDecimal
    total_clean_turnover_base: NonNegativeDecimal
    total_accrued_interest_base: NonNegativeDecimal
    total_settlement_turnover_base: NonNegativeDecimal
    total_commission_base: NonNegativeDecimal
    total_estimated_tax_base: NonNegativeDecimal
    risk_before: PortfolioRiskStateV1
    risk_after: PortfolioRiskStateV1
    drift_tolerance: PortfolioPlanDriftToleranceV1
    cancellation_conditions: Annotated[
        tuple[PlanCancellationConditionV1, ...],
        Field(min_length=18, max_length=18),
    ]
    approval_required: bool
    owner_approval_phrase: Annotated[str, Field(min_length=16, max_length=96)] | None
    plan_sha256: Sha256
    execution_authorized: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("created_at", "expires_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("portfolio plan timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("targets", mode="before")
    @classmethod
    def normalize_targets(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("portfolio plan targets must be a collection")
        return tuple(sorted(value, key=lambda row: _item_key(row, "stable_key")))

    @field_validator("legs", mode="before")
    @classmethod
    def normalize_legs(cls, value: object) -> object:
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("portfolio plan legs must be a collection")
        return tuple(sorted(value, key=lambda row: int(_item_key(row, "sequence"))))

    @field_validator("market_baselines", mode="before")
    @classmethod
    def normalize_baselines(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("portfolio plan market baselines must be a collection")
        return tuple(sorted(value, key=lambda row: _item_key(row, "stable_key")))

    @field_validator("cancellation_conditions", mode="before")
    @classmethod
    def normalize_conditions(cls, value: object) -> object:
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("plan cancellation conditions must be a collection")
        return tuple(sorted(value, key=lambda row: _item_key(row, "code")))

    @model_validator(mode="after")
    def validate_plan(self) -> PortfolioPlanV1:
        if self.expires_at <= self.created_at:
            raise ValueError("portfolio plan expiry must be after creation")
        sequences = [row.sequence for row in self.legs]
        if sequences != list(range(1, len(self.legs) + 1)):
            raise ValueError("portfolio plan sequences must be contiguous from one")

        actions = [row.action for row in self.legs]
        no_action = PortfolioPlanAction.NO_ACTION in actions
        if no_action and (len(actions) != 1 or actions[0] is not PortfolioPlanAction.NO_ACTION):
            raise ValueError("NO_ACTION plan cannot mix with actionable legs")
        actionable_legs = tuple(row for row in self.legs if row.optimizer_leg is not None)
        baseline_keys = [row.stable_key for row in self.market_baselines]
        if len(baseline_keys) != len(set(baseline_keys)):
            raise ValueError("plan market baselines must have unique stable keys")
        expected_baselines = {
            row.optimizer_leg.stable_key
            for row in actionable_legs
            if row.optimizer_leg is not None
        }
        if set(baseline_keys) != expected_baselines:
            raise ValueError("plan baselines must match actionable plan legs exactly")

        clean = sum(
            (row.optimizer_leg.gross_notional_base for row in actionable_legs if row.optimizer_leg),
            Decimal("0"),
        )
        accrued = sum(
            (row.optimizer_leg.accrued_interest_base for row in actionable_legs if row.optimizer_leg),
            Decimal("0"),
        )
        settlement = sum(
            (row.optimizer_leg.settlement_notional_base for row in actionable_legs if row.optimizer_leg),
            Decimal("0"),
        )
        commission = sum(
            (row.optimizer_leg.commission_base for row in actionable_legs if row.optimizer_leg),
            Decimal("0"),
        )
        tax = sum(
            (row.optimizer_leg.estimated_tax_base for row in actionable_legs if row.optimizer_leg),
            Decimal("0"),
        )
        if self.total_clean_turnover_base != clean:
            raise ValueError("plan clean turnover does not reconcile")
        if self.total_accrued_interest_base != accrued:
            raise ValueError("plan accrued interest does not reconcile")
        if self.total_settlement_turnover_base != settlement:
            raise ValueError("plan settlement turnover does not reconcile")
        if self.total_commission_base != commission:
            raise ValueError("plan commission does not reconcile")
        if self.total_estimated_tax_base != tax:
            raise ValueError("plan estimated tax does not reconcile")

        condition_codes = [row.code for row in self.cancellation_conditions]
        if set(condition_codes) != set(PlanCancellationCode):
            raise ValueError("portfolio plan must declare every cancellation condition")
        if len(condition_codes) != len(set(condition_codes)):
            raise ValueError("portfolio plan cancellation codes must be unique")

        expected_approval = not no_action
        if self.approval_required != expected_approval:
            raise ValueError("portfolio plan approval requirement does not match actionability")
        if self.approval_required:
            expected_phrase = owner_approval_phrase(self.plan_sha256)
            if self.owner_approval_phrase != expected_phrase:
                raise ValueError("owner approval phrase must bind exact plan SHA")
        elif self.owner_approval_phrase is not None:
            raise ValueError("NO_ACTION plan cannot request owner approval")

        if self.plan_sha256 != portfolio_plan_sha256(self):
            raise ValueError("portfolio plan SHA-256 does not match canonical payload")
        return self


class PortfolioPlanReviewInputV1(ContractModel):
    reviewed_at: datetime
    portfolio_snapshot_sha256: Sha256
    policy_reference: PolicyReferenceV1
    current_risk_assessment_sha256: Sha256
    strategy_selection_sha256: Sha256
    optimizer_sha256: Sha256
    target_risk_assessment_sha256: Sha256
    market_observations: tuple[PlanMarketObservationV1, ...] = ()

    @field_validator("reviewed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("plan review timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("market_observations", mode="before")
    @classmethod
    def normalize_observations(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("plan market observations must be a collection")
        return tuple(sorted(value, key=lambda row: _item_key(row, "stable_key")))

    @model_validator(mode="after")
    def validate_unique_observations(self) -> PortfolioPlanReviewInputV1:
        keys = [row.stable_key for row in self.market_observations]
        if len(keys) != len(set(keys)):
            raise ValueError("plan market observations must have unique stable keys")
        return self


class PlanMarketDriftResultV1(ContractModel):
    stable_key: Annotated[str, Field(min_length=3, max_length=256)]
    clean_price_drift_bps: Bps | None = None
    accrued_interest_drift_bps: Bps | None = None
    spread_widening_bps: Bps | None = None
    turnover_ratio: Ratio | None = None
    top_of_book_depth_ratio: Ratio | None = None
    fx_drift_bps: Bps | None = None
    cancellation_codes: tuple[PlanCancellationCode, ...] = ()

    @field_validator("cancellation_codes", mode="before")
    @classmethod
    def normalize_codes(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("plan drift cancellation codes must be a collection")
        return tuple(sorted(set(value), key=str))


class PortfolioPlanReviewV1(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    reviewed_at: datetime
    plan_sha256: Sha256
    status: PlanReviewStatus
    expired: bool
    drift_results: tuple[PlanMarketDriftResultV1, ...]
    cancellation_codes: tuple[PlanCancellationCode, ...] = ()
    plan_valid: bool
    expected_owner_approval_phrase: Annotated[str, Field(min_length=16, max_length=96)] | None
    execution_authorized: Literal[False] = False
    review_sha256: Sha256
    trading_methods: Literal[False] = False

    @field_validator("reviewed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("portfolio plan review timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("drift_results", mode="before")
    @classmethod
    def normalize_drifts(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("portfolio plan drift results must be a collection")
        return tuple(sorted(value, key=lambda row: _item_key(row, "stable_key")))

    @field_validator("cancellation_codes", mode="before")
    @classmethod
    def normalize_codes(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("portfolio plan review cancellations must be a collection")
        return tuple(sorted(set(value), key=str))

    @model_validator(mode="after")
    def validate_review(self) -> PortfolioPlanReviewV1:
        expected_valid = not self.cancellation_codes
        if self.plan_valid != expected_valid:
            raise ValueError("plan review validity must match cancellation codes")
        expected_status = (
            PlanReviewStatus.EXPIRED
            if self.expired
            else PlanReviewStatus.VALID
            if expected_valid
            else PlanReviewStatus.CANCELLED
        )
        if self.status is not expected_status:
            raise ValueError("plan review status does not match validity state")
        if not self.plan_valid and self.expected_owner_approval_phrase is not None:
            raise ValueError("invalid plan review cannot expose approval phrase")
        if self.review_sha256 != portfolio_plan_review_sha256(self):
            raise ValueError("portfolio plan review SHA-256 mismatch")
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


def portfolio_plan_sha256(plan: PortfolioPlanV1) -> str:
    payload = plan.model_dump(
        mode="json",
        exclude={"plan_sha256", "owner_approval_phrase"},
    )
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def owner_approval_phrase(plan_sha256: str) -> str:
    return f"ПОДТВЕРЖДАЮ ПЛАН {plan_sha256[:12].upper()}"


def portfolio_plan_review_sha256(review: PortfolioPlanReviewV1) -> str:
    payload = review.model_dump(mode="json", exclude={"review_sha256"})
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
