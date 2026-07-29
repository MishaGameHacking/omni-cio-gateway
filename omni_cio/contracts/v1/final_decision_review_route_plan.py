from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, SkipValidation, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel
from omni_cio.contracts.v1.final_decision_review_route_readiness import (
    FinalDecisionReviewRouteReadinessDossierV1,
    FinalDecisionReviewRouteReadinessStatus,
)


Sha256Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
SafeText = Annotated[str, Field(min_length=1, max_length=512)]
SafeReference = Annotated[str, Field(min_length=3, max_length=256)]


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


class FinalDecisionReviewRoutePlanStatus(StrEnum):
    READY_FOR_IMPLEMENTATION_REVIEW = "ready_for_implementation_review"
    BLOCKED = "blocked"


class FinalDecisionReviewAcceptanceStage(StrEnum):
    PRE_MERGE = "pre_merge"
    POST_DEPLOY = "post_deploy"
    GPT_EDITOR_PREVIEW = "gpt_editor_preview"
    ROLLBACK_DRILL = "rollback_drill"


class FinalDecisionReviewAcceptanceCheckCode(StrEnum):
    SOURCE_DOSSIER = "source_dossier"
    PROPOSED_CONTRACT = "proposed_contract"
    QUERY_ALLOWLIST = "query_allowlist"
    RESPONSE_CONTRACT = "response_contract"
    AUTHENTICATION = "authentication"
    OBSERVABILITY = "observability"
    PRE_MERGE_MATRIX = "pre_merge_matrix"
    POST_DEPLOY_MATRIX = "post_deploy_matrix"
    GPT_PREVIEW_MATRIX = "gpt_preview_matrix"
    ROLLBACK_MATRIX = "rollback_matrix"
    SAFETY_BOUNDARY = "safety_boundary"


class FinalDecisionReviewAcceptanceCheckStatus(StrEnum):
    PASS = "pass"
    BLOCK = "block"


class FinalDecisionReviewRoutePlanWarning(StrEnum):
    PLAN_IS_NOT_IMPLEMENTATION_AUTHORIZATION = (
        "plan_is_not_implementation_authorization"
    )
    PRODUCTION_DIFF_NOT_APPLIED = "production_diff_not_applied"
    DEPLOYMENT_NOT_PERFORMED = "deployment_not_performed"
    GPT_PREVIEW_NOT_PERFORMED = "gpt_preview_not_performed"
    SEPARATE_ROUTE_PR_REQUIRED = "separate_route_pr_required"
    NO_EXECUTION_AUTHORIZATION = "no_execution_authorization"


class FinalDecisionReviewProposedRouteV1(ContractModel):
    path: Literal["/decision/final-review"] = "/decision/final-review"
    method: Literal["get"] = "get"
    operation_id: Literal["getFinalDecisionReview"] = "getFinalDecisionReview"
    public: Literal[False] = False
    authentication_required: Literal[True] = True
    security_scheme: Literal["ApiKeyAuth"] = "ApiKeyAuth"
    request_body_present: Literal[False] = False
    query_parameters: tuple[str, ...] = (
        "account",
        "requested_option_id",
        "final_option_id",
        "intent_fingerprint",
        "instrument_count",
        "instrument_keys",
        "response_sha256",
        "action_candidate_sha256",
    )
    response_schema_name: Literal["FinalDecisionReviewResponseV1"] = (
        "FinalDecisionReviewResponseV1"
    )
    response_contract_name: Literal["final_decision_review_response"] = (
        "final_decision_review_response"
    )
    response_contract_version: Literal["1.0"] = "1.0"
    error_response_codes: tuple[int, ...] = (400, 401, 409, 422, 503)
    route_module: SafeReference = "app.py"
    orchestration_module: SafeReference = (
        "omni_cio/release/final_decision_review_route_handler_v1.py"
    )
    production_diff_applied: Literal[False] = False

    @model_validator(mode="after")
    def validate_contract(self) -> FinalDecisionReviewProposedRouteV1:
        if len(set(self.query_parameters)) != len(self.query_parameters):
            raise ValueError("proposed query parameters must be unique")
        if len(set(self.error_response_codes)) != len(self.error_response_codes):
            raise ValueError("proposed error response codes must be unique")
        if tuple(sorted(self.error_response_codes)) != self.error_response_codes:
            raise ValueError("proposed error response codes must be sorted")
        return self


class FinalDecisionReviewAcceptanceCaseV1(ContractModel):
    case_id: Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,127}$")]
    stage: FinalDecisionReviewAcceptanceStage
    description: SafeText
    expected_result: SafeText
    automated: bool
    blocking: Literal[True] = True
    executed: Literal[False] = False
    passed: Literal[False] = False


class FinalDecisionReviewRoutePlanCheckV1(ContractModel):
    code: FinalDecisionReviewAcceptanceCheckCode
    status: FinalDecisionReviewAcceptanceCheckStatus
    message: SafeText
    observed: Annotated[str, Field(min_length=1, max_length=1024)]
    expected: Annotated[str, Field(min_length=1, max_length=1024)]


class FinalDecisionReviewRouteImplementationPlanV1(ContractModel):
    schema_name: Literal["final_decision_review_route_implementation_plan"] = (
        "final_decision_review_route_implementation_plan"
    )
    schema_version: Literal["1.0"] = "1.0"
    prepared_at: datetime
    status: FinalDecisionReviewRoutePlanStatus
    ready_for_implementation_review: bool
    readiness_dossier: Annotated[
        FinalDecisionReviewRouteReadinessDossierV1,
        SkipValidation(),
    ]
    readiness_dossier_sha256: Sha256Digest
    proposed_route: FinalDecisionReviewProposedRouteV1
    proposed_route_sha256: Sha256Digest
    acceptance_cases: Annotated[
        tuple[FinalDecisionReviewAcceptanceCaseV1, ...],
        Field(min_length=1),
    ]
    source_dossier_confirmed: bool
    proposed_contract_confirmed: bool
    query_allowlist_confirmed: bool
    response_contract_confirmed: bool
    authentication_confirmed: bool
    observability_confirmed: bool
    acceptance_matrix_complete: bool
    safety_boundary_confirmed: bool
    checks: Annotated[tuple[FinalDecisionReviewRoutePlanCheckV1, ...], Field(min_length=1)]
    primary_blocker: FinalDecisionReviewAcceptanceCheckCode | None = None
    blockers: tuple[FinalDecisionReviewAcceptanceCheckCode, ...] = ()
    warnings: tuple[FinalDecisionReviewRoutePlanWarning, ...]
    implementation_authorized: Literal[False] = False
    route_approval_granted: Literal[False] = False
    production_route_added: Literal[False] = False
    production_openapi_changed: Literal[False] = False
    deployment_performed: Literal[False] = False
    gpt_preview_performed: Literal[False] = False
    trade_authorized: Literal[False] = False
    order_created: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("prepared_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("route implementation plan timestamp must be aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_plan(self) -> FinalDecisionReviewRouteImplementationPlanV1:
        dossier_sha = _canonical_sha256(
            self.readiness_dossier.model_dump(mode="json")
        )
        route_sha = _canonical_sha256(self.proposed_route.model_dump(mode="json"))
        if self.readiness_dossier_sha256 != dossier_sha:
            raise ValueError("route plan dossier digest is inconsistent")
        if self.proposed_route_sha256 != route_sha:
            raise ValueError("route plan proposed contract digest is inconsistent")

        case_ids = tuple(case.case_id for case in self.acceptance_cases)
        if len(set(case_ids)) != len(case_ids):
            raise ValueError("route plan acceptance case IDs must be unique")
        required_stages = set(FinalDecisionReviewAcceptanceStage)
        observed_stages = {case.stage for case in self.acceptance_cases}
        if observed_stages != required_stages:
            raise ValueError("route plan acceptance stages are incomplete")
        if any(case.executed or case.passed for case in self.acceptance_cases):
            raise ValueError("route plan cannot report unexecuted acceptance as complete")

        check_codes = tuple(check.code for check in self.checks)
        if len(set(check_codes)) != len(check_codes):
            raise ValueError("route plan checks must be unique")
        if set(check_codes) != set(FinalDecisionReviewAcceptanceCheckCode):
            raise ValueError("route plan checks are incomplete")
        expected_blockers = tuple(
            check.code
            for check in self.checks
            if check.status is FinalDecisionReviewAcceptanceCheckStatus.BLOCK
        )
        if self.blockers != expected_blockers:
            raise ValueError("route plan blockers do not match checks")
        expected_primary = self.blockers[0] if self.blockers else None
        if self.primary_blocker is not expected_primary:
            raise ValueError("route plan primary blocker is inconsistent")
        if len(set(self.blockers)) != len(self.blockers):
            raise ValueError("route plan blockers must be unique")
        if set(self.warnings) != set(FinalDecisionReviewRoutePlanWarning):
            raise ValueError("route plan warnings are incomplete")
        if len(set(self.warnings)) != len(self.warnings):
            raise ValueError("route plan warnings must be unique")

        expected_source = (
            self.readiness_dossier.status
            is FinalDecisionReviewRouteReadinessStatus.READY_FOR_ROUTE_REVIEW
            and self.readiness_dossier.ready_for_route_review
            and not self.readiness_dossier.blockers
        )
        if self.source_dossier_confirmed is not expected_source:
            raise ValueError("route plan source dossier mirror is inconsistent")

        expected_contract = (
            self.proposed_route.path == "/decision/final-review"
            and self.proposed_route.method == "get"
            and self.proposed_route.operation_id == "getFinalDecisionReview"
            and not self.proposed_route.public
            and self.proposed_route.authentication_required
            and not self.proposed_route.request_body_present
            and not self.proposed_route.production_diff_applied
        )
        if self.proposed_contract_confirmed is not expected_contract:
            raise ValueError("route plan proposed contract mirror is inconsistent")
        expected_query_allowlist = (
            self.proposed_route.query_parameters
            == self.readiness_dossier.input_binding.policy.allowed_query_parameters
        )
        if self.query_allowlist_confirmed is not expected_query_allowlist:
            raise ValueError("route plan query allowlist mirror is inconsistent")
        expected_response_contract = (
            self.proposed_route.response_contract_name
            == self.readiness_dossier.response.schema_name
            and self.proposed_route.response_contract_version
            == self.readiness_dossier.response.schema_version
        )
        if self.response_contract_confirmed is not expected_response_contract:
            raise ValueError("route plan response contract mirror is inconsistent")
        expected_authentication = (
            self.proposed_route.security_scheme
            == self.readiness_dossier.controls.authentication_scheme
            and self.proposed_route.authentication_required
            and self.readiness_dossier.authentication_controls_confirmed
        )
        if self.authentication_confirmed is not expected_authentication:
            raise ValueError("route plan authentication mirror is inconsistent")
        expected_observability = (
            self.readiness_dossier.observability_controls_confirmed
            and self.readiness_dossier.controls.correlation_id_required
            and self.readiness_dossier.controls.masked_account_logging_only
            and self.readiness_dossier.controls.sensitive_payload_logging_forbidden
        )
        if self.observability_confirmed is not expected_observability:
            raise ValueError("route plan observability mirror is inconsistent")
        expected_matrix = observed_stages == required_stages and all(
            case.blocking for case in self.acceptance_cases
        )
        if self.acceptance_matrix_complete is not expected_matrix:
            raise ValueError("route plan acceptance matrix mirror is inconsistent")
        expected_safety = (
            not self.readiness_dossier.route_approval_granted
            and not self.readiness_dossier.production_route_added
            and not self.readiness_dossier.production_openapi_changed
            and not self.proposed_route.production_diff_applied
        )
        if self.safety_boundary_confirmed is not expected_safety:
            raise ValueError("route plan safety boundary mirror is inconsistent")

        flags = (
            self.source_dossier_confirmed,
            self.proposed_contract_confirmed,
            self.query_allowlist_confirmed,
            self.response_contract_confirmed,
            self.authentication_confirmed,
            self.observability_confirmed,
            self.acceptance_matrix_complete,
            self.safety_boundary_confirmed,
        )
        expected_ready = all(flags) and not self.blockers
        if self.ready_for_implementation_review is not expected_ready:
            raise ValueError("route plan decision is inconsistent")
        expected_status = (
            FinalDecisionReviewRoutePlanStatus.READY_FOR_IMPLEMENTATION_REVIEW
            if expected_ready
            else FinalDecisionReviewRoutePlanStatus.BLOCKED
        )
        if self.status is not expected_status:
            raise ValueError("route plan status is inconsistent")
        return self
