from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel
from omni_cio.contracts.v1.final_decision_review import (
    FinalDecisionReviewShadowValidationV1,
)
from omni_cio.contracts.v1.final_decision_review_action_candidate import (
    FinalDecisionReviewOpenApiShadowV1,
)
from omni_cio.contracts.v1.final_decision_review_input import (
    FinalDecisionReviewInputBindingV1,
)
from omni_cio.contracts.v1.final_decision_review_publisher import (
    FinalDecisionReviewPublicationResultV1,
)
from omni_cio.contracts.v1.final_decision_review_release import (
    FinalDecisionReviewReleaseEligibilityV1,
)
from omni_cio.contracts.v1.final_decision_review_route_plan import (
    FinalDecisionReviewRouteImplementationPlanV1,
)
from omni_cio.contracts.v1.final_decision_review_route_readiness import (
    FinalDecisionReviewRouteReadinessDossierV1,
)


class FinalDecisionReviewOrchestrationStatus(StrEnum):
    PUBLISHED = "published"
    BLOCKED = "blocked"


class FinalDecisionReviewOrchestrationStage(StrEnum):
    RESPONSE_SHADOW = "response_shadow"
    RELEASE_ELIGIBILITY = "release_eligibility"
    ACTION_SHADOW = "action_shadow"
    INPUT_BINDING = "input_binding"
    ROUTE_READINESS = "route_readiness"
    ROUTE_PLAN = "route_plan"
    PUBLICATION = "publication"


class FinalDecisionReviewOrchestrationResultV1(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    orchestrated_at: datetime
    status: FinalDecisionReviewOrchestrationStatus
    completed_stage: FinalDecisionReviewOrchestrationStage
    published: bool
    primary_blocker: Annotated[str | None, Field(min_length=1, max_length=128)] = None
    response_shadow: FinalDecisionReviewShadowValidationV1
    release_eligibility: FinalDecisionReviewReleaseEligibilityV1 | None = None
    action_shadow: FinalDecisionReviewOpenApiShadowV1 | None = None
    input_binding: FinalDecisionReviewInputBindingV1 | None = None
    readiness_dossier: FinalDecisionReviewRouteReadinessDossierV1 | None = None
    route_plan: FinalDecisionReviewRouteImplementationPlanV1 | None = None
    publication: FinalDecisionReviewPublicationResultV1 | None = None
    internal_only: Literal[True] = True
    production_schema_mutated: Literal[False] = False
    http_route_created: Literal[False] = False
    external_broker_called: Literal[False] = False
    source_values_recomputed: Literal[False] = False
    trade_authorized: Literal[False] = False
    order_created: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("orchestrated_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("orchestration timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_orchestration(self) -> FinalDecisionReviewOrchestrationResultV1:
        artifacts = (
            self.release_eligibility,
            self.action_shadow,
            self.input_binding,
            self.readiness_dossier,
            self.route_plan,
        )
        seen_none = False
        for artifact in artifacts:
            if artifact is None:
                seen_none = True
            elif seen_none:
                raise ValueError("orchestration artifacts must form a contiguous chain")

        if self.status is FinalDecisionReviewOrchestrationStatus.PUBLISHED:
            if not self.published:
                raise ValueError("published orchestration requires published=true")
            if self.completed_stage is not FinalDecisionReviewOrchestrationStage.PUBLICATION:
                raise ValueError("published orchestration must complete publication")
            if self.primary_blocker is not None:
                raise ValueError("published orchestration cannot have a blocker")
            if any(artifact is None for artifact in artifacts):
                raise ValueError("published orchestration requires every source artifact")
            if self.publication is None:
                raise ValueError("published orchestration requires publication result")
        else:
            if self.published:
                raise ValueError("blocked orchestration cannot be published")
            if self.primary_blocker is None:
                raise ValueError("blocked orchestration requires a primary blocker")
            if self.publication is not None:
                raise ValueError("blocked orchestration cannot contain publication")

        response = self.response_shadow.response
        if (
            response.trade_authorized
            or response.order_created
            or response.execution_ready
            or response.trading_methods
        ):
            raise ValueError("orchestration response must remain read-only")
        if self.publication is not None and (
            self.publication.external_broker_called
            or self.publication.trade_authorized
            or self.publication.order_created
            or self.publication.execution_ready
            or self.publication.trading_methods
        ):
            raise ValueError("orchestration publication must remain read-only")
        return self
