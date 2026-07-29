from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, SkipValidation, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel
from omni_cio.contracts.v1.final_decision_review_release import (
    FinalDecisionReviewReleaseEligibilityV1,
)
from omni_cio.contracts.v1.release import ReadOnlyReleaseManifestV1


PositiveInt = Annotated[int, Field(gt=0)]
Sha256Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class FinalDecisionReviewActionCandidateStatus(StrEnum):
    SHADOW_VALID = "shadow_valid"
    SHADOW_BLOCKED = "shadow_blocked"


class FinalDecisionReviewActionCandidateBlocker(StrEnum):
    RELEASE_NOT_ELIGIBLE = "release_not_eligible"
    CURRENT_MANIFEST_NOT_READ_ONLY = "current_manifest_not_read_only"
    PATH_ALREADY_EXISTS = "path_already_exists"
    OPERATION_ID_ALREADY_EXISTS = "operation_id_already_exists"
    CANDIDATE_ACTION_MISSING = "candidate_action_missing"
    ACTION_COUNT_MISMATCH = "action_count_mismatch"
    EXISTING_ACTIONS_CHANGED = "existing_actions_changed"
    RESPONSE_SCHEMA_MISMATCH = "response_schema_mismatch"
    SHADOW_MANIFEST_INVALID = "shadow_manifest_invalid"


class FinalDecisionReviewActionCandidateWarning(StrEnum):
    SHADOW_ONLY = "shadow_only"
    NO_PRODUCTION_ROUTE = "no_production_route"
    OPENAPI_NOT_MODIFIED = "openapi_not_modified"
    SEPARATE_PRODUCTION_REVIEW_REQUIRED = "separate_production_review_required"
    NO_EXECUTION_AUTHORIZATION = "no_execution_authorization"


class FinalDecisionReviewGetActionCandidateV1(ContractModel):
    schema_name: Literal["final_decision_review_get_action_candidate"] = (
        "final_decision_review_get_action_candidate"
    )
    schema_version: Literal["1.0"] = "1.0"
    path: Literal["/decision/final-review"] = "/decision/final-review"
    method: Literal["get"] = "get"
    operation_id: Literal["getFinalDecisionReview"] = "getFinalDecisionReview"
    summary: Literal["Get the final read-only decision review"] = (
        "Get the final read-only decision review"
    )
    public: Literal[False] = False
    authentication_required: Literal[True] = True
    security_scheme: Literal["ApiKeyAuth"] = "ApiKeyAuth"
    response_schema_name: Literal["FinalDecisionReviewResponseV1"] = (
        "FinalDecisionReviewResponseV1"
    )
    response_contract_name: Literal["final_decision_review_response"] = (
        "final_decision_review_response"
    )
    response_contract_version: Literal["1.0"] = "1.0"
    response_schema_sha256: Sha256Digest
    release_eligibility_sha256: Sha256Digest
    request_body_present: Literal[False] = False
    mutation_parameters_present: Literal[False] = False
    trading_semantics_present: Literal[False] = False
    route_added: Literal[False] = False
    openapi_changed: Literal[False] = False
    trade_authorized: Literal[False] = False
    order_created: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False


class FinalDecisionReviewOpenApiShadowV1(ContractModel):
    schema_name: Literal["final_decision_review_openapi_shadow"] = (
        "final_decision_review_openapi_shadow"
    )
    schema_version: Literal["1.0"] = "1.0"
    validated_at: datetime
    status: FinalDecisionReviewActionCandidateStatus
    shadow_valid: bool
    candidate: FinalDecisionReviewGetActionCandidateV1
    release_eligibility: Annotated[
        FinalDecisionReviewReleaseEligibilityV1,
        SkipValidation(),
    ]
    current_manifest: Annotated[ReadOnlyReleaseManifestV1, SkipValidation()]
    shadow_manifest: Annotated[ReadOnlyReleaseManifestV1 | None, SkipValidation()] = None
    current_action_count: PositiveInt
    shadow_action_count: PositiveInt | None = None
    candidate_action_present: bool
    existing_actions_unchanged: bool
    response_schema_match: bool
    primary_blocker: FinalDecisionReviewActionCandidateBlocker | None = None
    blockers: tuple[FinalDecisionReviewActionCandidateBlocker, ...] = ()
    warnings: tuple[FinalDecisionReviewActionCandidateWarning, ...]
    shadow_only: Literal[True] = True
    production_schema_mutated: Literal[False] = False
    route_added: Literal[False] = False
    openapi_changed: Literal[False] = False
    public_action_created: Literal[False] = False
    source_values_recomputed: Literal[False] = False
    trade_authorized: Literal[False] = False
    order_created: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("validated_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("OpenAPI shadow timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_shadow(self) -> FinalDecisionReviewOpenApiShadowV1:
        if self.current_action_count != self.current_manifest.action_count:
            raise ValueError("current shadow action count is inconsistent")
        if self.shadow_manifest is None:
            if self.shadow_action_count is not None:
                raise ValueError("blocked shadow cannot report an action count")
        elif self.shadow_action_count != self.shadow_manifest.action_count:
            raise ValueError("shadow action count is inconsistent")

        if len(set(self.blockers)) != len(self.blockers):
            raise ValueError("OpenAPI shadow blockers must be unique")
        expected_primary = self.blockers[0] if self.blockers else None
        if self.primary_blocker is not expected_primary:
            raise ValueError("OpenAPI shadow primary blocker is inconsistent")
        if set(self.warnings) != set(FinalDecisionReviewActionCandidateWarning):
            raise ValueError("OpenAPI shadow warnings are incomplete")
        if len(set(self.warnings)) != len(self.warnings):
            raise ValueError("OpenAPI shadow warnings must be unique")

        expected_valid = (
            not self.blockers
            and self.shadow_manifest is not None
            and self.candidate_action_present
            and self.existing_actions_unchanged
            and self.response_schema_match
        )
        if self.shadow_valid is not expected_valid:
            raise ValueError("OpenAPI shadow decision is inconsistent")
        expected_status = (
            FinalDecisionReviewActionCandidateStatus.SHADOW_VALID
            if expected_valid
            else FinalDecisionReviewActionCandidateStatus.SHADOW_BLOCKED
        )
        if self.status is not expected_status:
            raise ValueError("OpenAPI shadow status is inconsistent")
        return self
