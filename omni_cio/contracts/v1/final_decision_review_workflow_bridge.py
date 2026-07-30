from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, SkipValidation, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel
from omni_cio.contracts.v1.decision_pro_forma_risk_binding import (
    ProFormaRiskIntentBindingV1,
    ProFormaRiskScenarioV1,
)
from omni_cio.contracts.v1.final_decision_review_orchestration import (
    FinalDecisionReviewOrchestrationResultV1,
    FinalDecisionReviewOrchestrationStatus,
)


SafeBlocker = Annotated[str, Field(min_length=1, max_length=256)]


class FinalDecisionReviewWorkflowBridgeStatus(StrEnum):
    PUBLISHED = "published"
    BLOCKED = "blocked"


class FinalDecisionReviewWorkflowBridgeStage(StrEnum):
    SCENARIO = "scenario"
    BINDING = "binding"
    ORCHESTRATION = "orchestration"


class FinalDecisionReviewWorkflowBridgeResultV1(ContractModel):
    schema_name: Literal["final_decision_review_workflow_bridge_result"] = (
        "final_decision_review_workflow_bridge_result"
    )
    schema_version: Literal["1.0"] = "1.0"
    bridged_at: datetime
    status: FinalDecisionReviewWorkflowBridgeStatus
    completed_stage: FinalDecisionReviewWorkflowBridgeStage
    published: bool
    primary_blocker: SafeBlocker | None = None
    scenario: Annotated[ProFormaRiskScenarioV1 | None, SkipValidation()] = None
    source_binding: Annotated[ProFormaRiskIntentBindingV1 | None, SkipValidation()] = None
    orchestration: Annotated[
        FinalDecisionReviewOrchestrationResultV1 | None,
        SkipValidation(),
    ] = None
    registry_active_sources: Annotated[int, Field(ge=0)]
    internal_only: Literal[True] = True
    production_bridge_registered: Literal[True] = True
    http_route_created: Literal[False] = False
    request_body_created: Literal[False] = False
    production_schema_mutated: Literal[False] = False
    external_broker_called: Literal[False] = False
    source_values_recomputed: Literal[False] = False
    trade_authorized: Literal[False] = False
    order_created: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("bridged_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("workflow bridge timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_result(self) -> FinalDecisionReviewWorkflowBridgeResultV1:
        if self.scenario is None:
            if self.completed_stage is not FinalDecisionReviewWorkflowBridgeStage.SCENARIO:
                raise ValueError("missing scenario requires scenario stage")
            if self.source_binding is not None or self.orchestration is not None:
                raise ValueError("later bridge artifacts require scenario")
        elif self.source_binding is None:
            if self.completed_stage is not FinalDecisionReviewWorkflowBridgeStage.BINDING:
                raise ValueError("missing binding requires binding stage")
            if self.orchestration is not None:
                raise ValueError("orchestration requires source binding")
        elif self.orchestration is None:
            if self.completed_stage is not FinalDecisionReviewWorkflowBridgeStage.ORCHESTRATION:
                raise ValueError("missing orchestration requires orchestration stage")
        elif self.completed_stage is not FinalDecisionReviewWorkflowBridgeStage.ORCHESTRATION:
            raise ValueError("complete bridge must end at orchestration")

        expected_published = (
            self.orchestration is not None
            and self.orchestration.status
            is FinalDecisionReviewOrchestrationStatus.PUBLISHED
            and self.orchestration.published
            and self.orchestration.primary_blocker is None
        )
        expected_status = (
            FinalDecisionReviewWorkflowBridgeStatus.PUBLISHED
            if expected_published
            else FinalDecisionReviewWorkflowBridgeStatus.BLOCKED
        )
        expected_blocker = (
            None
            if expected_published
            else (
                self.orchestration.primary_blocker
                if self.orchestration is not None
                else self.primary_blocker
            )
        )
        if self.published is not expected_published:
            raise ValueError("workflow bridge publication mirror is inconsistent")
        if self.status is not expected_status:
            raise ValueError("workflow bridge status mirror is inconsistent")
        if self.primary_blocker != expected_blocker:
            raise ValueError("workflow bridge blocker mirror is inconsistent")
        if expected_published and self.registry_active_sources < 1:
            raise ValueError("published bridge requires an active source")
        return self
