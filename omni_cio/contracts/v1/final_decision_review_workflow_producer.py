from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, SkipValidation, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel
from omni_cio.contracts.v1.decision_capacity_directional_pretrade import (
    CapacityDirectionalPreTradeReviewV1,
)
from omni_cio.contracts.v1.decision_risk_pretrade_explanation import (
    RiskPreTradeExplanationEnvelopeV1,
)
from omni_cio.contracts.v1.final_decision_review_workflow_bridge import (
    FinalDecisionReviewWorkflowBridgeResultV1,
    FinalDecisionReviewWorkflowBridgeStatus,
)


SafeBlocker = Annotated[str, Field(min_length=1, max_length=256)]


class FinalDecisionReviewWorkflowProducerStatus(StrEnum):
    PUBLISHED = "published"
    BLOCKED = "blocked"


class FinalDecisionReviewWorkflowProducerStage(StrEnum):
    DIRECTIONAL_REVIEW = "directional_review"
    RISK_EXPLANATION = "risk_explanation"
    WORKFLOW_BRIDGE = "workflow_bridge"


class FinalDecisionReviewWorkflowProducerResultV1(ContractModel):
    schema_name: Literal["final_decision_review_workflow_producer_result"] = (
        "final_decision_review_workflow_producer_result"
    )
    schema_version: Literal["1.0"] = "1.0"
    produced_at: datetime
    status: FinalDecisionReviewWorkflowProducerStatus
    completed_stage: FinalDecisionReviewWorkflowProducerStage
    published: bool
    primary_blocker: SafeBlocker | None = None
    directional_review: Annotated[
        CapacityDirectionalPreTradeReviewV1 | None,
        SkipValidation(),
    ] = None
    risk_explanation: Annotated[
        RiskPreTradeExplanationEnvelopeV1 | None,
        SkipValidation(),
    ] = None
    workflow_bridge: Annotated[
        FinalDecisionReviewWorkflowBridgeResultV1 | None,
        SkipValidation(),
    ] = None
    registry_active_sources: Annotated[int, Field(ge=0)]
    input_direction_count: Annotated[int, Field(ge=0, le=2)]
    internal_only: Literal[True] = True
    live_read_only_producer_registered: Literal[True] = True
    source_authority_rechecked: Literal[True] = True
    freshness_rechecked: Literal[True] = True
    account_context_rechecked: Literal[True] = True
    exact_intent_rechecked: Literal[True] = True
    http_route_created: Literal[False] = False
    request_body_created: Literal[False] = False
    production_schema_mutated: Literal[False] = False
    external_broker_called: Literal[False] = False
    source_values_recomputed: Literal[False] = False
    trade_authorized: Literal[False] = False
    order_created: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("produced_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("workflow producer timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_result(self) -> FinalDecisionReviewWorkflowProducerResultV1:
        if self.directional_review is None:
            if (
                self.completed_stage
                is not FinalDecisionReviewWorkflowProducerStage.DIRECTIONAL_REVIEW
            ):
                raise ValueError("missing directional review requires first stage")
            if self.risk_explanation is not None or self.workflow_bridge is not None:
                raise ValueError("later producer artifacts require directional review")
        elif self.risk_explanation is None:
            if (
                self.completed_stage
                is not FinalDecisionReviewWorkflowProducerStage.RISK_EXPLANATION
            ):
                raise ValueError("missing explanation requires explanation stage")
            if self.workflow_bridge is not None:
                raise ValueError("workflow bridge requires risk explanation")
        elif self.workflow_bridge is None:
            if (
                self.completed_stage
                is not FinalDecisionReviewWorkflowProducerStage.WORKFLOW_BRIDGE
            ):
                raise ValueError("missing bridge requires bridge stage")
        elif (
            self.completed_stage
            is not FinalDecisionReviewWorkflowProducerStage.WORKFLOW_BRIDGE
        ):
            raise ValueError("complete producer must end at workflow bridge")

        expected_published = (
            self.workflow_bridge is not None
            and self.workflow_bridge.status
            is FinalDecisionReviewWorkflowBridgeStatus.PUBLISHED
            and self.workflow_bridge.published
            and self.workflow_bridge.primary_blocker is None
        )
        expected_status = (
            FinalDecisionReviewWorkflowProducerStatus.PUBLISHED
            if expected_published
            else FinalDecisionReviewWorkflowProducerStatus.BLOCKED
        )
        expected_blocker = (
            None
            if expected_published
            else (
                self.workflow_bridge.primary_blocker
                if self.workflow_bridge is not None
                else self.primary_blocker
            )
        )
        if self.published is not expected_published:
            raise ValueError("workflow producer publication mirror is inconsistent")
        if self.status is not expected_status:
            raise ValueError("workflow producer status mirror is inconsistent")
        if self.primary_blocker != expected_blocker:
            raise ValueError("workflow producer blocker mirror is inconsistent")
        if expected_published and self.registry_active_sources < 1:
            raise ValueError("published producer requires active registry source")
        return self
