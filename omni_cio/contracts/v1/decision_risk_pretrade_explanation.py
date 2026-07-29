from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, SkipValidation, field_validator, model_validator

from omni_cio.contracts.v1.capacity import OrderSide
from omni_cio.contracts.v1.common import ContractModel
from omni_cio.contracts.v1.decision import DecisionAction
from omni_cio.contracts.v1.decision_capacity import CapacityDecisionGateStatus
from omni_cio.contracts.v1.decision_capacity_directional_pretrade import (
    CapacityDirectionalPreTradeReviewV1,
)
from omni_cio.contracts.v1.risk import RiskOverallStatus, RiskPolicyEvaluationV1


NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]


class RiskPreTradeExplanationLayer(StrEnum):
    ACCOUNT_CONTEXT = "account_context"
    PORTFOLIO_RISK = "portfolio_risk"
    CAPACITY_INTENT = "capacity_intent"
    BROKER_PREVIEW = "broker_preview"
    DIRECTIONAL_REVIEW = "directional_review"


class RiskPreTradeExplanationLayerState(StrEnum):
    READY = "ready"
    WARNING = "warning"
    BLOCKED = "blocked"


class RiskPreTradeExplanationBlocker(StrEnum):
    ACCOUNT_CONTEXT_UNCONFIRMED = "account_context_unconfirmed"
    ACCOUNT_CONTEXT_MISMATCH = "account_context_mismatch"
    RISK_EVALUATION_NOT_READY = "risk_evaluation_not_ready"
    RISK_EVALUATION_STALE = "risk_evaluation_stale"
    RISK_EVALUATION_FROM_FUTURE = "risk_evaluation_from_future"
    DIRECTIONAL_REVIEW_NOT_READY = "directional_review_not_ready"
    DIRECTIONAL_REVIEW_STALE = "directional_review_stale"
    DIRECTIONAL_REVIEW_FROM_FUTURE = "directional_review_from_future"


class RiskPreTradeExplanationWarning(StrEnum):
    RISK_EVALUATION_NOT_PRO_FORMA_BOUND = "risk_evaluation_not_pro_forma_bound"
    RISK_POLICY_NON_PERSONALIZED = "risk_policy_non_personalized"
    RISK_WARNING_PRESENT = "risk_warning_present"
    RISK_UNKNOWN_PRESENT = "risk_unknown_present"
    SOURCE_CONTRACTS_RETAINED = "source_contracts_retained"
    REVIEW_ONLY_NO_ORDER_CREATED = "review_only_no_order_created"


class RiskPreTradeExplanationPolicyV1(ContractModel):
    risk_max_age_seconds: Annotated[int, Field(ge=1, le=86_400)] = 900
    directional_review_max_age_seconds: Annotated[
        int,
        Field(ge=1, le=86_400),
    ] = 180
    future_tolerance_seconds: Annotated[int, Field(ge=0, le=3_600)] = 60


class RiskPreTradeExplanationLayerV1(ContractModel):
    layer: RiskPreTradeExplanationLayer
    state: RiskPreTradeExplanationLayerState
    ready: bool
    blocker_count: NonNegativeInt
    warning_count: NonNegativeInt
    message: Annotated[str, Field(min_length=1, max_length=512)]

    @model_validator(mode="after")
    def validate_layer(self) -> RiskPreTradeExplanationLayerV1:
        if self.ready is (self.state is RiskPreTradeExplanationLayerState.BLOCKED):
            raise ValueError("explanation layer readiness is inconsistent")
        if self.state is RiskPreTradeExplanationLayerState.BLOCKED:
            if self.blocker_count == 0:
                raise ValueError("blocked explanation layer requires blocker")
        elif self.blocker_count != 0:
            raise ValueError("non-blocked explanation layer cannot have blocker")
        if (
            self.state is RiskPreTradeExplanationLayerState.WARNING
            and self.warning_count == 0
        ):
            raise ValueError("warning explanation layer requires warning")
        return self


class RiskPreTradeExplanationEnvelopeV1(ContractModel):
    schema_name: Literal["risk_pretrade_explanation_envelope"] = (
        "risk_pretrade_explanation_envelope"
    )
    schema_version: Literal["1.0"] = "1.0"
    assessed_at: datetime
    status: CapacityDecisionGateStatus
    review_ready: bool
    abstain: bool
    direction: OrderSide
    risk_evaluation: Annotated[RiskPolicyEvaluationV1, SkipValidation()]
    directional_review: Annotated[
        CapacityDirectionalPreTradeReviewV1,
        SkipValidation(),
    ]
    policy: RiskPreTradeExplanationPolicyV1
    no_action_option_id: Annotated[str, Field(min_length=3, max_length=256)]
    final_option_id: Annotated[str, Field(min_length=3, max_length=256)]
    final_action: DecisionAction
    risk_overall_status: RiskOverallStatus
    risk_decision_ready: bool
    risk_breach_count: NonNegativeInt
    risk_warning_count: NonNegativeInt
    risk_unknown_count: NonNegativeInt
    account_context_confirmed: bool
    source_account_count: NonNegativeInt
    layers: Annotated[
        tuple[RiskPreTradeExplanationLayerV1, ...],
        Field(min_length=5, max_length=5),
    ]
    primary_blocking_layer: RiskPreTradeExplanationLayer | None = None
    blockers: tuple[RiskPreTradeExplanationBlocker, ...] = ()
    warnings: tuple[RiskPreTradeExplanationWarning, ...] = ()
    risk_change_approval_confirmed: Literal[False] = False
    option_selected_by_envelope: Literal[False] = False
    order_created: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("assessed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("risk/pretrade explanation timestamp must be aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_envelope(self) -> RiskPreTradeExplanationEnvelopeV1:
        risk = self.risk_evaluation
        review = self.directional_review
        if self.direction is not review.direction:
            raise ValueError("explanation direction does not match review")
        if self.no_action_option_id != review.no_action_option_id:
            raise ValueError("explanation no-action option does not reconcile")
        if self.risk_overall_status is not risk.overall_status:
            raise ValueError("risk status mirror is inconsistent")
        if self.risk_decision_ready is not risk.decision_ready:
            raise ValueError("risk readiness mirror is inconsistent")
        if (
            self.risk_breach_count,
            self.risk_warning_count,
            self.risk_unknown_count,
        ) != (
            risk.breach_count,
            risk.warning_count,
            risk.unknown_count,
        ):
            raise ValueError("risk counters do not reconcile")
        if len(set(self.blockers)) != len(self.blockers):
            raise ValueError("risk/pretrade blockers must be unique")
        if len(set(self.warnings)) != len(self.warnings):
            raise ValueError("risk/pretrade warnings must be unique")

        risk_age = (self.assessed_at - risk.metadata.retrieved_at).total_seconds()
        review_age = (self.assessed_at - review.assessed_at).total_seconds()
        expected_blocker_states = (
            (
                RiskPreTradeExplanationBlocker.RISK_EVALUATION_NOT_READY,
                not risk.decision_ready,
            ),
            (
                RiskPreTradeExplanationBlocker.RISK_EVALUATION_STALE,
                risk_age > self.policy.risk_max_age_seconds,
            ),
            (
                RiskPreTradeExplanationBlocker.RISK_EVALUATION_FROM_FUTURE,
                risk_age < -self.policy.future_tolerance_seconds,
            ),
            (
                RiskPreTradeExplanationBlocker.DIRECTIONAL_REVIEW_NOT_READY,
                not review.gate_ready,
            ),
            (
                RiskPreTradeExplanationBlocker.DIRECTIONAL_REVIEW_STALE,
                review_age > self.policy.directional_review_max_age_seconds,
            ),
            (
                RiskPreTradeExplanationBlocker.DIRECTIONAL_REVIEW_FROM_FUTURE,
                review_age < -self.policy.future_tolerance_seconds,
            ),
        )
        for blocker, expected_present in expected_blocker_states:
            if (blocker in self.blockers) != expected_present:
                raise ValueError(f"explanation blocker {blocker.value} is inconsistent")

        account_unconfirmed = (
            RiskPreTradeExplanationBlocker.ACCOUNT_CONTEXT_UNCONFIRMED
            in self.blockers
        )
        account_mismatch = (
            RiskPreTradeExplanationBlocker.ACCOUNT_CONTEXT_MISMATCH
            in self.blockers
        )
        if self.account_context_confirmed is (account_unconfirmed or account_mismatch):
            raise ValueError("account context confirmation is inconsistent")
        if self.account_context_confirmed and self.source_account_count != 1:
            raise ValueError("confirmed account context requires one source account")
        if account_unconfirmed and self.source_account_count != 0:
            raise ValueError("unconfirmed account context requires no source account")
        if account_mismatch and self.source_account_count == 0:
            raise ValueError("account mismatch requires observed source account")

        expected_layer_order = tuple(RiskPreTradeExplanationLayer)
        if tuple(row.layer for row in self.layers) != expected_layer_order:
            raise ValueError("explanation layers must use canonical order")
        layer_by_name = {row.layer: row for row in self.layers}
        expected_account_ready = self.account_context_confirmed
        expected_risk_ready = not any(
            blocker
            in (
                RiskPreTradeExplanationBlocker.RISK_EVALUATION_NOT_READY,
                RiskPreTradeExplanationBlocker.RISK_EVALUATION_STALE,
                RiskPreTradeExplanationBlocker.RISK_EVALUATION_FROM_FUTURE,
            )
            for blocker in self.blockers
        )
        expected_capacity_ready = review.base_intent_gate.gate_ready
        expected_broker_ready = (
            review.source_gate_ready
            and review.source_coverage_complete
            and review.exact_intent_binding_confirmed
        )
        expected_directional_ready = review.gate_ready and not any(
            blocker
            in (
                RiskPreTradeExplanationBlocker.DIRECTIONAL_REVIEW_STALE,
                RiskPreTradeExplanationBlocker.DIRECTIONAL_REVIEW_FROM_FUTURE,
            )
            for blocker in self.blockers
        )
        expected_readiness = {
            RiskPreTradeExplanationLayer.ACCOUNT_CONTEXT: expected_account_ready,
            RiskPreTradeExplanationLayer.PORTFOLIO_RISK: expected_risk_ready,
            RiskPreTradeExplanationLayer.CAPACITY_INTENT: expected_capacity_ready,
            RiskPreTradeExplanationLayer.BROKER_PREVIEW: expected_broker_ready,
            RiskPreTradeExplanationLayer.DIRECTIONAL_REVIEW: expected_directional_ready,
        }
        for layer, ready in expected_readiness.items():
            if layer_by_name[layer].ready is not ready:
                raise ValueError(f"explanation layer {layer.value} readiness is inconsistent")

        if any(not ready for ready in expected_readiness.values()):
            if self.primary_blocking_layer is None:
                raise ValueError("blocked explanation requires primary layer")
            if expected_readiness[self.primary_blocking_layer]:
                raise ValueError("primary blocking layer must be blocked")
        elif self.primary_blocking_layer is not None:
            raise ValueError("ready explanation cannot have primary blocker")

        expected_ready = not self.blockers and all(expected_readiness.values())
        expected_status = (
            CapacityDecisionGateStatus.READY
            if expected_ready
            else CapacityDecisionGateStatus.ABSTAIN
        )
        if self.review_ready is not expected_ready:
            raise ValueError("explanation readiness is inconsistent")
        if self.abstain is expected_ready:
            raise ValueError("explanation abstain state is inconsistent")
        if self.status is not expected_status:
            raise ValueError("explanation status is inconsistent")
        if expected_ready:
            if self.final_option_id != review.final_option_id:
                raise ValueError("ready explanation changed review option")
            if self.final_action is not review.final_action:
                raise ValueError("ready explanation changed review action")
        else:
            if self.final_option_id != self.no_action_option_id:
                raise ValueError("blocked explanation must use no action")
            if self.final_action is not DecisionAction.WAIT_FOR_DATA:
                raise ValueError("blocked explanation must wait for data")

        required_warnings = {
            RiskPreTradeExplanationWarning.RISK_EVALUATION_NOT_PRO_FORMA_BOUND,
            RiskPreTradeExplanationWarning.SOURCE_CONTRACTS_RETAINED,
            RiskPreTradeExplanationWarning.REVIEW_ONLY_NO_ORDER_CREATED,
        }
        if not required_warnings.issubset(self.warnings):
            raise ValueError("required explanation warnings are missing")
        if (
            RiskPreTradeExplanationWarning.RISK_POLICY_NON_PERSONALIZED
            in self.warnings
        ) is (not risk.policy.personalized):
            pass
        else:
            raise ValueError("risk personalization warning is inconsistent")
        if (
            RiskPreTradeExplanationWarning.RISK_WARNING_PRESENT in self.warnings
        ) != (risk.warning_count > 0 or risk.overall_status is RiskOverallStatus.WARNING):
            raise ValueError("risk warning presence is inconsistent")
        if (
            RiskPreTradeExplanationWarning.RISK_UNKNOWN_PRESENT in self.warnings
        ) != (risk.unknown_count > 0):
            raise ValueError("risk unknown presence is inconsistent")
        return self
