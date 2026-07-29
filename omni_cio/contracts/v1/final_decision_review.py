from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, SkipValidation, field_validator, model_validator

from omni_cio.contracts.v1.capacity import OrderSide
from omni_cio.contracts.v1.common import (
    AccountReference,
    ContractModel,
    CurrencyCode,
)
from omni_cio.contracts.v1.decision import DecisionAction
from omni_cio.contracts.v1.decision_capacity import CapacityDecisionGateStatus
from omni_cio.contracts.v1.decision_pro_forma_risk_binding import (
    ProFormaRiskIntentBindingV1,
)
from omni_cio.contracts.v1.risk import RiskOverallStatus


NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]
FiniteDecimal = Annotated[Decimal, Field(allow_inf_nan=False)]
Fingerprint = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
SafeCode = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")]


class FinalDecisionReviewDisposition(StrEnum):
    REVIEW_READY = "review_ready"
    WAIT_FOR_DATA = "wait_for_data"


class FinalDecisionReviewWarning(StrEnum):
    SOURCE_VALUES_NOT_RECOMPUTED = "source_values_not_recomputed"
    PROVENANCE_SANITIZED = "provenance_sanitized"
    RISK_DELTA_NOT_RETURN_FORECAST = "risk_delta_not_return_forecast"
    REVIEW_ONLY_NO_TRADE_AUTHORIZATION = "review_only_no_trade_authorization"


class FinalDecisionReviewShadowStatus(StrEnum):
    MATCH = "match"
    MISMATCH = "mismatch"


class FinalDecisionReviewShadowMismatch(StrEnum):
    STATUS = "status"
    READINESS = "readiness"
    OPTION = "option"
    ACTION = "action"
    DIRECTION = "direction"
    ACCOUNT = "account"
    FINGERPRINT = "fingerprint"
    RISK_APPROVAL = "risk_approval"
    SAFETY = "safety"


class FinalDecisionReviewIntentV1(ContractModel):
    request_id: Annotated[str, Field(min_length=1, max_length=128)]
    instrument_key: Annotated[str, Field(min_length=3, max_length=256)]
    side: OrderSide
    currency: CurrencyCode
    quantity_lots: PositiveInt
    lot_size: PositiveInt
    reference_price: FiniteDecimal
    intended_execution_days: PositiveInt
    units: PositiveInt
    order_notional: FiniteDecimal

    @model_validator(mode="after")
    def validate_intent(self) -> FinalDecisionReviewIntentV1:
        if self.units != self.quantity_lots * self.lot_size:
            raise ValueError("final review intent units do not reconcile")
        if self.order_notional != Decimal(self.units) * self.reference_price:
            raise ValueError("final review intent notional does not reconcile")
        return self


class FinalDecisionReviewRiskSummaryV1(ContractModel):
    current_status: RiskOverallStatus
    pro_forma_status: RiskOverallStatus
    current_breach_count: NonNegativeInt
    pro_forma_breach_count: NonNegativeInt
    breach_count_delta: int
    current_warning_count: NonNegativeInt
    pro_forma_warning_count: NonNegativeInt
    warning_count_delta: int
    current_unknown_count: NonNegativeInt
    pro_forma_unknown_count: NonNegativeInt
    unknown_count_delta: int
    status_changed: bool

    @model_validator(mode="after")
    def validate_summary(self) -> FinalDecisionReviewRiskSummaryV1:
        if self.breach_count_delta != (
            self.pro_forma_breach_count - self.current_breach_count
        ):
            raise ValueError("final review breach delta is inconsistent")
        if self.warning_count_delta != (
            self.pro_forma_warning_count - self.current_warning_count
        ):
            raise ValueError("final review warning delta is inconsistent")
        if self.unknown_count_delta != (
            self.pro_forma_unknown_count - self.current_unknown_count
        ):
            raise ValueError("final review unknown delta is inconsistent")
        if self.status_changed is (
            self.current_status is self.pro_forma_status
        ):
            raise ValueError("final review risk status flag is inconsistent")
        return self


class FinalDecisionReviewSourceV1(ContractModel):
    provider: Annotated[str, Field(min_length=1, max_length=128)]
    operation: Annotated[str, Field(min_length=1, max_length=128)]
    retrieved_at: datetime

    @field_validator("retrieved_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("final review source timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)


class FinalDecisionReviewResponseV1(ContractModel):
    schema_name: Literal["final_decision_review_response"] = (
        "final_decision_review_response"
    )
    schema_version: Literal["1.0"] = "1.0"
    generated_at: datetime
    status: CapacityDecisionGateStatus
    disposition: FinalDecisionReviewDisposition
    review_ready: bool
    abstain: bool
    account: AccountReference
    requested_option_id: Annotated[str, Field(min_length=3, max_length=256)]
    final_option_id: Annotated[str, Field(min_length=3, max_length=256)]
    final_action: DecisionAction
    direction: OrderSide
    intent_fingerprint: Fingerprint
    instrument_count: PositiveInt
    intents: Annotated[tuple[FinalDecisionReviewIntentV1, ...], Field(min_length=1)]
    risk: FinalDecisionReviewRiskSummaryV1
    risk_change_approval_confirmed: bool
    primary_blocker: SafeCode | None = None
    blockers: tuple[SafeCode, ...] = ()
    source_warnings: tuple[SafeCode, ...] = ()
    response_warnings: tuple[FinalDecisionReviewWarning, ...]
    source_count: PositiveInt
    provenance: Annotated[tuple[FinalDecisionReviewSourceV1, ...], Field(min_length=1)]
    full_account_identifier_present: Literal[False] = False
    source_contracts_exposed: Literal[False] = False
    public_action_exposed: Literal[False] = False
    source_values_recomputed: Literal[False] = False
    option_selected_by_adapter: Literal[False] = False
    trade_authorized: Literal[False] = False
    order_created: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("generated_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("final review timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_response(self) -> FinalDecisionReviewResponseV1:
        if self.instrument_count != len(self.intents):
            raise ValueError("final review instrument count does not reconcile")
        request_ids = tuple(row.request_id for row in self.intents)
        instrument_keys = tuple(row.instrument_key for row in self.intents)
        if len(set(request_ids)) != len(request_ids):
            raise ValueError("final review request IDs must be unique")
        if len(set(instrument_keys)) != len(instrument_keys):
            raise ValueError("final review instruments must be unique")
        if any(row.side is not self.direction for row in self.intents):
            raise ValueError("final review intent direction is inconsistent")
        if len(set(self.blockers)) != len(self.blockers):
            raise ValueError("final review blockers must be unique")
        if len(set(self.source_warnings)) != len(self.source_warnings):
            raise ValueError("final review source warnings must be unique")
        if len(set(self.response_warnings)) != len(self.response_warnings):
            raise ValueError("final review response warnings must be unique")
        if self.source_count != len(self.provenance):
            raise ValueError("final review source count does not reconcile")
        source_keys = tuple(
            (row.provider, row.operation, row.retrieved_at)
            for row in self.provenance
        )
        if len(set(source_keys)) != len(source_keys):
            raise ValueError("final review provenance must be unique")

        expected_ready = not self.blockers
        expected_status = (
            CapacityDecisionGateStatus.READY
            if expected_ready
            else CapacityDecisionGateStatus.ABSTAIN
        )
        expected_disposition = (
            FinalDecisionReviewDisposition.REVIEW_READY
            if expected_ready
            else FinalDecisionReviewDisposition.WAIT_FOR_DATA
        )
        if self.review_ready is not expected_ready:
            raise ValueError("final review readiness is inconsistent")
        if self.abstain is expected_ready:
            raise ValueError("final review abstain state is inconsistent")
        if self.status is not expected_status:
            raise ValueError("final review status is inconsistent")
        if self.disposition is not expected_disposition:
            raise ValueError("final review disposition is inconsistent")
        if self.risk_change_approval_confirmed is not expected_ready:
            raise ValueError("final review risk approval is inconsistent")
        if expected_ready:
            if self.primary_blocker is not None:
                raise ValueError("ready final review cannot have primary blocker")
        else:
            if not self.blockers or self.primary_blocker != self.blockers[0]:
                raise ValueError("final review primary blocker must be first")
            if self.final_action is not DecisionAction.WAIT_FOR_DATA:
                raise ValueError("blocked final review must wait for data")

        required_warnings = {
            FinalDecisionReviewWarning.SOURCE_VALUES_NOT_RECOMPUTED,
            FinalDecisionReviewWarning.PROVENANCE_SANITIZED,
            FinalDecisionReviewWarning.RISK_DELTA_NOT_RETURN_FORECAST,
            FinalDecisionReviewWarning.REVIEW_ONLY_NO_TRADE_AUTHORIZATION,
        }
        if not required_warnings.issubset(self.response_warnings):
            raise ValueError("required final review warnings are missing")
        return self


class FinalDecisionReviewShadowValidationV1(ContractModel):
    schema_name: Literal["final_decision_review_shadow_validation"] = (
        "final_decision_review_shadow_validation"
    )
    schema_version: Literal["1.0"] = "1.0"
    validated_at: datetime
    source_binding: Annotated[ProFormaRiskIntentBindingV1, SkipValidation()]
    response: FinalDecisionReviewResponseV1
    status: FinalDecisionReviewShadowStatus
    shadow_valid: bool
    status_match: bool
    readiness_match: bool
    option_match: bool
    action_match: bool
    direction_match: bool
    account_match: bool
    fingerprint_match: bool
    risk_approval_match: bool
    safety_match: bool
    mismatches: tuple[FinalDecisionReviewShadowMismatch, ...] = ()
    shadow_only: Literal[True] = True
    route_added: Literal[False] = False
    trade_authorized: Literal[False] = False
    order_created: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("validated_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("final review shadow timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_shadow(self) -> FinalDecisionReviewShadowValidationV1:
        source = self.source_binding
        response = self.response
        expected_states = {
            FinalDecisionReviewShadowMismatch.STATUS: (
                response.status is source.status
            ),
            FinalDecisionReviewShadowMismatch.READINESS: (
                response.review_ready is source.review_ready
                and response.abstain is source.abstain
            ),
            FinalDecisionReviewShadowMismatch.OPTION: (
                response.final_option_id == source.final_option_id
                and response.requested_option_id == source.requested_option_id
            ),
            FinalDecisionReviewShadowMismatch.ACTION: (
                response.final_action is source.final_action
            ),
            FinalDecisionReviewShadowMismatch.DIRECTION: (
                response.direction is source.direction
            ),
            FinalDecisionReviewShadowMismatch.ACCOUNT: (
                response.account == source.scenario.account
            ),
            FinalDecisionReviewShadowMismatch.FINGERPRINT: (
                response.intent_fingerprint == source.intent_fingerprint
            ),
            FinalDecisionReviewShadowMismatch.RISK_APPROVAL: (
                response.risk_change_approval_confirmed
                is source.risk_change_approval_confirmed
            ),
            FinalDecisionReviewShadowMismatch.SAFETY: (
                not response.trade_authorized
                and not response.order_created
                and not response.execution_ready
                and not response.trading_methods
            ),
        }
        mirror_states = (
            (self.status_match, expected_states[FinalDecisionReviewShadowMismatch.STATUS]),
            (
                self.readiness_match,
                expected_states[FinalDecisionReviewShadowMismatch.READINESS],
            ),
            (self.option_match, expected_states[FinalDecisionReviewShadowMismatch.OPTION]),
            (self.action_match, expected_states[FinalDecisionReviewShadowMismatch.ACTION]),
            (
                self.direction_match,
                expected_states[FinalDecisionReviewShadowMismatch.DIRECTION],
            ),
            (self.account_match, expected_states[FinalDecisionReviewShadowMismatch.ACCOUNT]),
            (
                self.fingerprint_match,
                expected_states[FinalDecisionReviewShadowMismatch.FINGERPRINT],
            ),
            (
                self.risk_approval_match,
                expected_states[FinalDecisionReviewShadowMismatch.RISK_APPROVAL],
            ),
            (self.safety_match, expected_states[FinalDecisionReviewShadowMismatch.SAFETY]),
        )
        if any(observed is not expected for observed, expected in mirror_states):
            raise ValueError("final review shadow mirror is inconsistent")
        expected_mismatches = tuple(
            mismatch for mismatch, matches in expected_states.items() if not matches
        )
        if self.mismatches != expected_mismatches:
            raise ValueError("final review shadow mismatches are inconsistent")
        expected_valid = not expected_mismatches
        expected_status = (
            FinalDecisionReviewShadowStatus.MATCH
            if expected_valid
            else FinalDecisionReviewShadowStatus.MISMATCH
        )
        if self.shadow_valid is not expected_valid:
            raise ValueError("final review shadow validity is inconsistent")
        if self.status is not expected_status:
            raise ValueError("final review shadow status is inconsistent")
        return self
