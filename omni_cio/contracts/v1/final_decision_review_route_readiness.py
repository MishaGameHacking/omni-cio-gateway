from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, SkipValidation, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel
from omni_cio.contracts.v1.final_decision_review import FinalDecisionReviewResponseV1
from omni_cio.contracts.v1.final_decision_review_action_candidate import (
    FinalDecisionReviewActionCandidateStatus,
    FinalDecisionReviewOpenApiShadowV1,
)
from omni_cio.contracts.v1.final_decision_review_input import (
    FinalDecisionReviewInputBindingV1,
    FinalDecisionReviewInputStatus,
)
from omni_cio.contracts.v1.final_decision_review_release import (
    FinalDecisionReviewReleaseEligibilityV1,
    FinalDecisionReviewReleaseStatus,
)


Sha256Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
SafeReference = Annotated[str, Field(min_length=3, max_length=256)]
SafeText = Annotated[str, Field(min_length=1, max_length=512)]


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


class FinalDecisionReviewRouteReadinessStatus(StrEnum):
    READY_FOR_ROUTE_REVIEW = "ready_for_route_review"
    BLOCKED = "blocked"


class FinalDecisionReviewRouteReadinessCheckStatus(StrEnum):
    PASS = "pass"
    BLOCK = "block"


class FinalDecisionReviewRouteReadinessCheckCode(StrEnum):
    SOURCE_STATUSES = "source_statuses"
    RESPONSE_IDENTITY = "response_identity"
    CANDIDATE_IDENTITY = "candidate_identity"
    QUERY_IDENTITY = "query_identity"
    CONTEXT_PARITY = "context_parity"
    AUTHENTICATION = "authentication"
    ROLLBACK = "rollback"
    OBSERVABILITY = "observability"
    SAFETY_BOUNDARY = "safety_boundary"


class FinalDecisionReviewRouteReadinessWarning(StrEnum):
    DOSSIER_IS_NOT_ROUTE_APPROVAL = "dossier_is_not_route_approval"
    SEPARATE_PRODUCTION_REVIEW_REQUIRED = "separate_production_review_required"
    DEPLOYMENT_ACCEPTANCE_REQUIRED = "deployment_acceptance_required"
    GPT_EDITOR_PREVIEW_REQUIRED = "gpt_editor_preview_required"
    NO_EXECUTION_AUTHORIZATION = "no_execution_authorization"


class FinalDecisionReviewRouteControlsV1(ContractModel):
    authentication_scheme: Literal["ApiKeyAuth"] = "ApiKeyAuth"
    private_action: Literal[True] = True
    authentication_required: Literal[True] = True
    server_authorization_documented: bool = True
    rollback_runbook_reference: SafeReference = (
        "docs/operations/DEPLOYMENT_RUNBOOK.md"
    )
    rollback_commit_pinning_required: bool = True
    observability_contract_name: Literal["ObservabilityEventV1"] = (
        "ObservabilityEventV1"
    )
    correlation_id_required: bool = True
    masked_account_logging_only: bool = True
    sensitive_payload_logging_forbidden: bool = True
    deployment_health_path: Literal["/health"] = "/health"
    required_entrypoint: Literal["app:app"] = "app:app"
    production_route_reviewed: Literal[False] = False
    route_approval_granted: Literal[False] = False


class FinalDecisionReviewRouteReadinessCheckV1(ContractModel):
    code: FinalDecisionReviewRouteReadinessCheckCode
    status: FinalDecisionReviewRouteReadinessCheckStatus
    message: SafeText
    observed: Annotated[str, Field(min_length=1, max_length=1024)]
    expected: Annotated[str, Field(min_length=1, max_length=1024)]


class FinalDecisionReviewRouteReadinessDossierV1(ContractModel):
    schema_name: Literal["final_decision_review_route_readiness_dossier"] = (
        "final_decision_review_route_readiness_dossier"
    )
    schema_version: Literal["1.0"] = "1.0"
    assessed_at: datetime
    status: FinalDecisionReviewRouteReadinessStatus
    ready_for_route_review: bool
    response: Annotated[FinalDecisionReviewResponseV1, SkipValidation()]
    release_eligibility: Annotated[
        FinalDecisionReviewReleaseEligibilityV1,
        SkipValidation(),
    ]
    action_shadow: Annotated[FinalDecisionReviewOpenApiShadowV1, SkipValidation()]
    input_binding: Annotated[FinalDecisionReviewInputBindingV1, SkipValidation()]
    controls: FinalDecisionReviewRouteControlsV1
    response_sha256: Sha256Digest
    action_candidate_sha256: Sha256Digest
    query_sha256: Sha256Digest
    source_statuses_confirmed: bool
    response_identity_confirmed: bool
    candidate_identity_confirmed: bool
    query_identity_confirmed: bool
    context_parity_confirmed: bool
    authentication_controls_confirmed: bool
    rollback_controls_confirmed: bool
    observability_controls_confirmed: bool
    safety_boundary_confirmed: bool
    checks: Annotated[
        tuple[FinalDecisionReviewRouteReadinessCheckV1, ...],
        Field(min_length=1),
    ]
    primary_blocker: FinalDecisionReviewRouteReadinessCheckCode | None = None
    blockers: tuple[FinalDecisionReviewRouteReadinessCheckCode, ...] = ()
    warnings: tuple[FinalDecisionReviewRouteReadinessWarning, ...]
    route_approval_granted: Literal[False] = False
    production_route_added: Literal[False] = False
    production_openapi_changed: Literal[False] = False
    public_action_created: Literal[False] = False
    source_values_recomputed: Literal[False] = False
    trade_authorized: Literal[False] = False
    order_created: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("assessed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("route-readiness timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_dossier(self) -> FinalDecisionReviewRouteReadinessDossierV1:
        response_sha = _canonical_sha256(self.response.model_dump(mode="json"))
        candidate_sha = _canonical_sha256(
            self.action_shadow.candidate.model_dump(mode="json")
        )
        query_sha = _canonical_sha256(
            self.input_binding.query.model_dump(mode="json")
        )
        if self.response_sha256 != response_sha:
            raise ValueError("route-readiness response digest is inconsistent")
        if self.action_candidate_sha256 != candidate_sha:
            raise ValueError("route-readiness candidate digest is inconsistent")
        if self.query_sha256 != query_sha:
            raise ValueError("route-readiness query digest is inconsistent")

        check_codes = tuple(check.code for check in self.checks)
        if len(set(check_codes)) != len(check_codes):
            raise ValueError("route-readiness checks must be unique")
        if set(check_codes) != set(FinalDecisionReviewRouteReadinessCheckCode):
            raise ValueError("route-readiness checks are incomplete")
        expected_blockers = tuple(
            check.code
            for check in self.checks
            if check.status is FinalDecisionReviewRouteReadinessCheckStatus.BLOCK
        )
        if self.blockers != expected_blockers:
            raise ValueError("route-readiness blockers do not match checks")
        if len(set(self.blockers)) != len(self.blockers):
            raise ValueError("route-readiness blockers must be unique")
        expected_primary = self.blockers[0] if self.blockers else None
        if self.primary_blocker is not expected_primary:
            raise ValueError("route-readiness primary blocker is inconsistent")
        if set(self.warnings) != set(FinalDecisionReviewRouteReadinessWarning):
            raise ValueError("route-readiness warnings are incomplete")
        if len(set(self.warnings)) != len(self.warnings):
            raise ValueError("route-readiness warnings must be unique")

        expected_source_statuses = (
            self.release_eligibility.status
            is FinalDecisionReviewReleaseStatus.ELIGIBLE
            and self.release_eligibility.eligible
            and self.action_shadow.status
            is FinalDecisionReviewActionCandidateStatus.SHADOW_VALID
            and self.action_shadow.shadow_valid
            and self.input_binding.status is FinalDecisionReviewInputStatus.VALID
            and self.input_binding.input_valid
        )
        if self.source_statuses_confirmed is not expected_source_statuses:
            raise ValueError("route-readiness source status mirror is inconsistent")

        expected_response_identity = (
            self.release_eligibility.response_sha256 == response_sha
            and self.action_shadow.release_eligibility.response_sha256
            == response_sha
            and self.input_binding.response_sha256 == response_sha
            and self.input_binding.query.response_sha256 == response_sha
        )
        if self.response_identity_confirmed is not expected_response_identity:
            raise ValueError("route-readiness response identity mirror is inconsistent")
        expected_candidate_identity = (
            self.input_binding.action_candidate_sha256 == candidate_sha
            and self.input_binding.query.action_candidate_sha256 == candidate_sha
        )
        if self.candidate_identity_confirmed is not expected_candidate_identity:
            raise ValueError("route-readiness candidate identity mirror is inconsistent")
        expected_query_identity = self.input_binding.query_sha256 == query_sha
        if self.query_identity_confirmed is not expected_query_identity:
            raise ValueError("route-readiness query identity mirror is inconsistent")

        query = self.input_binding.query
        expected_context = (
            query.account == self.response.account
            and query.requested_option_id == self.response.requested_option_id
            and query.final_option_id == self.response.final_option_id
            and query.intent_fingerprint == self.response.intent_fingerprint
            and query.instrument_count == self.response.instrument_count
            and query.instrument_keys
            == tuple(row.instrument_key for row in self.response.intents)
        )
        if self.context_parity_confirmed is not expected_context:
            raise ValueError("route-readiness context mirror is inconsistent")

        candidate = self.action_shadow.candidate
        expected_authentication = (
            candidate.private_action is False
            if hasattr(candidate, "private_action")
            else not candidate.public
        )
        expected_authentication = (
            expected_authentication
            and candidate.authentication_required
            and candidate.security_scheme == self.controls.authentication_scheme
            and self.controls.private_action
            and self.controls.authentication_required
            and self.controls.server_authorization_documented
        )
        if self.authentication_controls_confirmed is not expected_authentication:
            raise ValueError("route-readiness authentication mirror is inconsistent")

        expected_rollback = (
            self.controls.rollback_runbook_reference
            == "docs/operations/DEPLOYMENT_RUNBOOK.md"
            and self.controls.rollback_commit_pinning_required
        )
        if self.rollback_controls_confirmed is not expected_rollback:
            raise ValueError("route-readiness rollback mirror is inconsistent")
        expected_observability = (
            self.controls.observability_contract_name == "ObservabilityEventV1"
            and self.controls.correlation_id_required
            and self.controls.masked_account_logging_only
            and self.controls.sensitive_payload_logging_forbidden
            and self.controls.deployment_health_path == "/health"
            and self.controls.required_entrypoint == "app:app"
        )
        if self.observability_controls_confirmed is not expected_observability:
            raise ValueError("route-readiness observability mirror is inconsistent")

        expected_safety = (
            not self.release_eligibility.route_approval_granted
            and not self.release_eligibility.route_added
            and not self.release_eligibility.openapi_changed
            and not self.action_shadow.production_schema_mutated
            and not self.action_shadow.route_added
            and not self.action_shadow.openapi_changed
            and not self.action_shadow.public_action_created
            and not self.input_binding.route_added
            and not self.input_binding.openapi_changed
            and not self.input_binding.public_action_created
            and not self.controls.production_route_reviewed
            and not self.controls.route_approval_granted
        )
        if self.safety_boundary_confirmed is not expected_safety:
            raise ValueError("route-readiness safety mirror is inconsistent")

        flags = (
            self.source_statuses_confirmed,
            self.response_identity_confirmed,
            self.candidate_identity_confirmed,
            self.query_identity_confirmed,
            self.context_parity_confirmed,
            self.authentication_controls_confirmed,
            self.rollback_controls_confirmed,
            self.observability_controls_confirmed,
            self.safety_boundary_confirmed,
        )
        expected_ready = all(flags) and not self.blockers
        if self.ready_for_route_review is not expected_ready:
            raise ValueError("route-readiness decision is inconsistent")
        expected_status = (
            FinalDecisionReviewRouteReadinessStatus.READY_FOR_ROUTE_REVIEW
            if expected_ready
            else FinalDecisionReviewRouteReadinessStatus.BLOCKED
        )
        if self.status is not expected_status:
            raise ValueError("route-readiness status is inconsistent")
        return self
