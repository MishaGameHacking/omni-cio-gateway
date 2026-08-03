from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, model_validator

from omni_cio.contracts.v1.common import ContractModel


class CioIntent(StrEnum):
    EXACT_ACTION = "exact_action"
    DIAGNOSTIC = "diagnostic"
    ANALYSIS = "analysis"
    PORTFOLIO_MANAGEMENT = "portfolio_management"
    RISK = "risk"
    RESEARCH = "research"
    CASH_ALLOCATION = "cash_allocation"
    PLAN_REVIEW = "plan_review"
    EXECUTION = "execution"
    MONITORING = "monitoring"
    UNKNOWN = "unknown"


class CioWorkflow(StrEnum):
    EXACT_ACTION = "exact_action"
    GATEWAY_DIAGNOSTIC = "gateway_diagnostic"
    CONNECTION_DIAGNOSTIC = "connection_diagnostic"
    PORTFOLIO_ANALYSIS = "portfolio_analysis"
    PORTFOLIO_MANAGEMENT = "portfolio_management"
    RISK_REVIEW = "risk_review"
    ASSET_RESEARCH = "asset_research"
    CASH_ALLOCATION = "cash_allocation"
    PLAN_REVIEW = "plan_review"
    EXECUTION_REQUEST = "execution_request"
    EXECUTION_CONFIRMATION = "execution_confirmation"
    MONITORING_REVIEW = "monitoring_review"
    UNRESOLVED = "unresolved"


class RouterConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RouterRequirement(StrEnum):
    GATEWAY_HEALTH = "gateway_health"
    CONNECTION = "connection"
    PORTFOLIO_SNAPSHOT = "portfolio_snapshot"
    CASH_LIQUIDITY = "cash_liquidity"
    PORTFOLIO_ANALYTICS = "portfolio_analytics"
    INSTRUMENT_IDENTITY = "instrument_identity"
    FRESH_MARKET = "fresh_market"
    OPERATIONS_HISTORY = "operations_history"
    FINAL_DECISION_REVIEW = "final_decision_review"
    REAL_TRADING_STATUS = "real_trading_status"
    SANDBOX_TRADING_STATUS = "sandbox_trading_status"
    POLICY_CONTEXT = "policy_context"


class ExecutionContour(StrEnum):
    NONE = "none"
    REAL = "real"
    SANDBOX = "sandbox"
    UNSPECIFIED = "unspecified"
    AMBIGUOUS = "ambiguous"


class ExecutionPhase(StrEnum):
    NONE = "none"
    REQUEST = "request"
    CONFIRMATION = "confirmation"


class ExecutionDirection(StrEnum):
    NONE = "none"
    BUY = "buy"
    SELL = "sell"
    AMBIGUOUS = "ambiguous"


class RouterClarificationCode(StrEnum):
    INTENT_NOT_RECOGNIZED = "intent_not_recognized"
    EXECUTION_CONTOUR_REQUIRED = "execution_contour_required"
    EXECUTION_CONTOUR_AMBIGUOUS = "execution_contour_ambiguous"
    EXECUTION_DIRECTION_REQUIRED = "execution_direction_required"
    EXECUTION_DIRECTION_AMBIGUOUS = "execution_direction_ambiguous"


ActionId = Annotated[
    str,
    Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{2,127}$"),
]


class IntentRouteV1(ContractModel):
    """Deterministic routing result; never an authorization to mutate broker state."""

    router_version: Literal["1.0"] = "1.0"
    primary_intent: CioIntent
    secondary_intents: tuple[CioIntent, ...] = ()
    workflow: CioWorkflow
    confidence: RouterConfidence
    requirements: tuple[RouterRequirement, ...] = ()
    exact_actions: tuple[ActionId, ...] = ()
    exact_action_scope_locked: bool = False
    clarification_required: bool = False
    clarification_code: RouterClarificationCode | None = None
    execution_contour: ExecutionContour = ExecutionContour.NONE
    execution_phase: ExecutionPhase = ExecutionPhase.NONE
    execution_direction: ExecutionDirection = ExecutionDirection.NONE
    owner_confirmation_required_for_write: bool = False
    router_read_only: Literal[True] = True
    execution_authorized: Literal[False] = False

    @model_validator(mode="after")
    def validate_route(self) -> IntentRouteV1:
        if len(self.secondary_intents) != len(set(self.secondary_intents)):
            raise ValueError("secondary intents must be unique")
        if self.primary_intent in self.secondary_intents:
            raise ValueError("primary intent cannot also be secondary")
        if len(self.requirements) != len(set(self.requirements)):
            raise ValueError("router requirements must be unique")
        if len(self.exact_actions) != len(set(self.exact_actions)):
            raise ValueError("exact actions must be unique")
        if self.clarification_required != (self.clarification_code is not None):
            raise ValueError("clarification flag must match clarification code")

        if self.primary_intent is CioIntent.EXACT_ACTION:
            if not self.exact_actions or not self.exact_action_scope_locked:
                raise ValueError("exact-action route requires a locked action scope")
            if self.workflow is not CioWorkflow.EXACT_ACTION:
                raise ValueError("exact-action intent requires exact-action workflow")
        elif self.exact_actions or self.exact_action_scope_locked:
            raise ValueError("only exact-action routes may carry exact actions")

        if self.primary_intent is CioIntent.UNKNOWN:
            if self.workflow is not CioWorkflow.UNRESOLVED:
                raise ValueError("unknown intent must remain unresolved")
            if not self.clarification_required:
                raise ValueError("unknown intent must request clarification")

        if self.primary_intent is CioIntent.EXECUTION:
            if self.execution_phase is ExecutionPhase.NONE:
                raise ValueError("execution intent requires an execution phase")
            if self.execution_contour is ExecutionContour.NONE:
                raise ValueError("execution intent requires a contour state")
            if not self.owner_confirmation_required_for_write:
                raise ValueError("execution intent must preserve owner confirmation gate")
            if self.workflow not in {
                CioWorkflow.EXECUTION_REQUEST,
                CioWorkflow.EXECUTION_CONFIRMATION,
            }:
                raise ValueError("execution intent has an invalid workflow")
        elif self.primary_intent is not CioIntent.EXACT_ACTION:
            if self.execution_contour is not ExecutionContour.NONE:
                raise ValueError("non-execution route cannot carry execution contour")
            if self.execution_phase is not ExecutionPhase.NONE:
                raise ValueError("non-execution route cannot carry execution phase")
            if self.execution_direction is not ExecutionDirection.NONE:
                raise ValueError("non-execution route cannot carry execution direction")
            if self.owner_confirmation_required_for_write:
                raise ValueError("non-execution route cannot require write confirmation")

        return self
