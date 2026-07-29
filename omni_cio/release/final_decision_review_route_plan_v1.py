from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from omni_cio.contracts.v1.final_decision_review_route_plan import (
    FinalDecisionReviewAcceptanceCaseV1,
    FinalDecisionReviewAcceptanceCheckCode,
    FinalDecisionReviewAcceptanceCheckStatus,
    FinalDecisionReviewAcceptanceStage,
    FinalDecisionReviewProposedRouteV1,
    FinalDecisionReviewRouteImplementationPlanV1,
    FinalDecisionReviewRoutePlanCheckV1,
    FinalDecisionReviewRoutePlanStatus,
    FinalDecisionReviewRoutePlanWarning,
)
from omni_cio.contracts.v1.final_decision_review_route_readiness import (
    FinalDecisionReviewRouteReadinessDossierV1,
    FinalDecisionReviewRouteReadinessStatus,
)


class FinalDecisionReviewRoutePlanError(ValueError):
    """The final-review route plan cannot be prepared safely."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise FinalDecisionReviewRoutePlanError(
            "FINAL_DECISION_REVIEW_ROUTE_PLAN_TIMESTAMP_MUST_BE_AWARE"
        )
    return result.astimezone(timezone.utc)


def _canonical_sha256(value: object) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _check(
    code: FinalDecisionReviewAcceptanceCheckCode,
    passed: bool,
    *,
    message: str,
    observed: str,
    expected: str,
) -> FinalDecisionReviewRoutePlanCheckV1:
    return FinalDecisionReviewRoutePlanCheckV1(
        code=code,
        status=(
            FinalDecisionReviewAcceptanceCheckStatus.PASS
            if passed
            else FinalDecisionReviewAcceptanceCheckStatus.BLOCK
        ),
        message=message,
        observed=observed,
        expected=expected,
    )


def default_final_decision_review_acceptance_cases() -> tuple[
    FinalDecisionReviewAcceptanceCaseV1, ...
]:
    """Return the complete unexecuted blocking acceptance matrix."""

    return (
        FinalDecisionReviewAcceptanceCaseV1(
            case_id="pre-merge.current-release-contract",
            stage=FinalDecisionReviewAcceptanceStage.PRE_MERGE,
            description="Run the current GET-only release guard on the route diff",
            expected_result="All existing Actions unchanged and exactly one private GET added",
            automated=True,
        ),
        FinalDecisionReviewAcceptanceCaseV1(
            case_id="pre-merge.full-regression-shield",
            stage=FinalDecisionReviewAcceptanceStage.PRE_MERGE,
            description="Run compile, lint, type, tests, coverage and security checks",
            expected_result="Every required check succeeds on the final route PR SHA",
            automated=True,
        ),
        FinalDecisionReviewAcceptanceCaseV1(
            case_id="pre-merge.read-only-handler-boundary",
            stage=FinalDecisionReviewAcceptanceStage.PRE_MERGE,
            description="Verify handler calls only the reviewed read-only orchestration",
            expected_result="No broker write method or execution surface is reachable",
            automated=True,
        ),
        FinalDecisionReviewAcceptanceCaseV1(
            case_id="post-deploy.render-source-commit",
            stage=FinalDecisionReviewAcceptanceStage.POST_DEPLOY,
            description="Compare Render source commit with the merged route commit",
            expected_result="Render deploy uses the exact reviewed merge commit",
            automated=False,
        ),
        FinalDecisionReviewAcceptanceCaseV1(
            case_id="post-deploy.health-contract",
            stage=FinalDecisionReviewAcceptanceStage.POST_DEPLOY,
            description="Verify cache-busted health response after deployment",
            expected_result="status ok, app:app, read-only true and trading methods false",
            automated=False,
        ),
        FinalDecisionReviewAcceptanceCaseV1(
            case_id="post-deploy.private-auth-negative",
            stage=FinalDecisionReviewAcceptanceStage.POST_DEPLOY,
            description="Call the route without valid private authentication",
            expected_result="Request is rejected without returning decision data",
            automated=True,
        ),
        FinalDecisionReviewAcceptanceCaseV1(
            case_id="post-deploy.exact-query-positive",
            stage=FinalDecisionReviewAcceptanceStage.POST_DEPLOY,
            description="Call the route with one exact reviewed query context",
            expected_result="Response matches FinalDecisionReviewResponseV1 and remains read-only",
            automated=True,
        ),
        FinalDecisionReviewAcceptanceCaseV1(
            case_id="post-deploy.substitution-negative",
            stage=FinalDecisionReviewAcceptanceStage.POST_DEPLOY,
            description="Substitute account, option, fingerprint and response digest",
            expected_result="Each substituted request is blocked fail-closed",
            automated=True,
        ),
        FinalDecisionReviewAcceptanceCaseV1(
            case_id="gpt-preview.schema-import",
            stage=FinalDecisionReviewAcceptanceStage.GPT_EDITOR_PREVIEW,
            description="Import the reviewed OpenAPI schema into GPT Editor",
            expected_result="Schema imports with one private getFinalDecisionReview Action",
            automated=False,
        ),
        FinalDecisionReviewAcceptanceCaseV1(
            case_id="gpt-preview.authenticated-call",
            stage=FinalDecisionReviewAcceptanceStage.GPT_EDITOR_PREVIEW,
            description="Run one authenticated Action in GPT Editor Preview",
            expected_result="Only the compact masked read-only response is returned",
            automated=False,
        ),
        FinalDecisionReviewAcceptanceCaseV1(
            case_id="gpt-preview.no-write-actions",
            stage=FinalDecisionReviewAcceptanceStage.GPT_EDITOR_PREVIEW,
            description="Inspect the full Action list after schema import",
            expected_result="No order, execution or funds-movement Action exists",
            automated=False,
        ),
        FinalDecisionReviewAcceptanceCaseV1(
            case_id="rollback.pin-known-good-commit",
            stage=FinalDecisionReviewAcceptanceStage.ROLLBACK_DRILL,
            description="Identify and record the last known-good deploy commit",
            expected_result="Rollback target is an immutable reviewed commit SHA",
            automated=False,
        ),
        FinalDecisionReviewAcceptanceCaseV1(
            case_id="rollback.restore-read-only-health",
            stage=FinalDecisionReviewAcceptanceStage.ROLLBACK_DRILL,
            description="Verify documented rollback restores the previous contract",
            expected_result="Health and GET-only release guard return to the known-good state",
            automated=False,
        ),
    )


def build_final_decision_review_route_implementation_plan(
    readiness_dossier: FinalDecisionReviewRouteReadinessDossierV1,
    *,
    proposed_route: FinalDecisionReviewProposedRouteV1 | None = None,
    acceptance_cases: tuple[FinalDecisionReviewAcceptanceCaseV1, ...] | None = None,
    prepared_at: datetime | None = None,
) -> FinalDecisionReviewRouteImplementationPlanV1:
    """Prepare the exact route plan without applying any production diff."""

    plan_time = _aware_utc(prepared_at)
    route = proposed_route or FinalDecisionReviewProposedRouteV1()
    cases = acceptance_cases or default_final_decision_review_acceptance_cases()
    dossier_sha = _canonical_sha256(readiness_dossier.model_dump(mode="json"))
    route_sha = _canonical_sha256(route.model_dump(mode="json"))

    source_dossier_confirmed = (
        readiness_dossier.status
        is FinalDecisionReviewRouteReadinessStatus.READY_FOR_ROUTE_REVIEW
        and readiness_dossier.ready_for_route_review
        and not readiness_dossier.blockers
    )
    proposed_contract_confirmed = (
        route.path == "/decision/final-review"
        and route.method == "get"
        and route.operation_id == "getFinalDecisionReview"
        and not route.public
        and route.authentication_required
        and not route.request_body_present
        and not route.production_diff_applied
    )
    query_allowlist_confirmed = (
        route.query_parameters
        == readiness_dossier.input_binding.policy.allowed_query_parameters
    )
    response_contract_confirmed = (
        route.response_contract_name == readiness_dossier.response.schema_name
        and route.response_contract_version
        == readiness_dossier.response.schema_version
    )
    authentication_confirmed = (
        route.security_scheme
        == readiness_dossier.controls.authentication_scheme
        and route.authentication_required
        and readiness_dossier.authentication_controls_confirmed
    )
    observability_confirmed = (
        readiness_dossier.observability_controls_confirmed
        and readiness_dossier.controls.correlation_id_required
        and readiness_dossier.controls.masked_account_logging_only
        and readiness_dossier.controls.sensitive_payload_logging_forbidden
    )
    observed_stages = {case.stage for case in cases}
    acceptance_matrix_complete = (
        observed_stages == set(FinalDecisionReviewAcceptanceStage)
        and len({case.case_id for case in cases}) == len(cases)
        and all(case.blocking and not case.executed and not case.passed for case in cases)
    )
    safety_boundary_confirmed = (
        not readiness_dossier.route_approval_granted
        and not readiness_dossier.production_route_added
        and not readiness_dossier.production_openapi_changed
        and not route.production_diff_applied
    )

    stage_counts = {
        stage: sum(1 for case in cases if case.stage is stage)
        for stage in FinalDecisionReviewAcceptanceStage
    }
    checks = (
        _check(
            FinalDecisionReviewAcceptanceCheckCode.SOURCE_DOSSIER,
            source_dossier_confirmed,
            message="PR-57 dossier must be ready and blocker-free",
            observed=readiness_dossier.status.value,
            expected="ready_for_route_review",
        ),
        _check(
            FinalDecisionReviewAcceptanceCheckCode.PROPOSED_CONTRACT,
            proposed_contract_confirmed,
            message="Proposed route must remain the exact private GET contract",
            observed=f"{route.method} {route.path} {route.operation_id}",
            expected="get /decision/final-review getFinalDecisionReview",
        ),
        _check(
            FinalDecisionReviewAcceptanceCheckCode.QUERY_ALLOWLIST,
            query_allowlist_confirmed,
            message="Proposed query parameters must equal the PR-56 allowlist",
            observed=str(len(route.query_parameters)),
            expected=str(
                len(readiness_dossier.input_binding.policy.allowed_query_parameters)
            ),
        ),
        _check(
            FinalDecisionReviewAcceptanceCheckCode.RESPONSE_CONTRACT,
            response_contract_confirmed,
            message="Proposed response contract must match the PR-53 response",
            observed=(
                f"{route.response_contract_name}/{route.response_contract_version}"
            ),
            expected=(
                f"{readiness_dossier.response.schema_name}/"
                f"{readiness_dossier.response.schema_version}"
            ),
        ),
        _check(
            FinalDecisionReviewAcceptanceCheckCode.AUTHENTICATION,
            authentication_confirmed,
            message="Private API-key authentication controls must remain exact",
            observed=route.security_scheme,
            expected=readiness_dossier.controls.authentication_scheme,
        ),
        _check(
            FinalDecisionReviewAcceptanceCheckCode.OBSERVABILITY,
            observability_confirmed,
            message="Safe observability controls must remain required",
            observed=readiness_dossier.controls.observability_contract_name,
            expected="ObservabilityEventV1",
        ),
        _check(
            FinalDecisionReviewAcceptanceCheckCode.PRE_MERGE_MATRIX,
            stage_counts[FinalDecisionReviewAcceptanceStage.PRE_MERGE] >= 3,
            message="Pre-merge acceptance must cover contract, CI and handler boundaries",
            observed=str(stage_counts[FinalDecisionReviewAcceptanceStage.PRE_MERGE]),
            expected=">=3",
        ),
        _check(
            FinalDecisionReviewAcceptanceCheckCode.POST_DEPLOY_MATRIX,
            stage_counts[FinalDecisionReviewAcceptanceStage.POST_DEPLOY] >= 4,
            message="Post-deploy acceptance must cover commit, health, auth and parity",
            observed=str(stage_counts[FinalDecisionReviewAcceptanceStage.POST_DEPLOY]),
            expected=">=4",
        ),
        _check(
            FinalDecisionReviewAcceptanceCheckCode.GPT_PREVIEW_MATRIX,
            stage_counts[FinalDecisionReviewAcceptanceStage.GPT_EDITOR_PREVIEW] >= 3,
            message="GPT Editor Preview acceptance must cover import, call and Action list",
            observed=str(
                stage_counts[FinalDecisionReviewAcceptanceStage.GPT_EDITOR_PREVIEW]
            ),
            expected=">=3",
        ),
        _check(
            FinalDecisionReviewAcceptanceCheckCode.ROLLBACK_MATRIX,
            stage_counts[FinalDecisionReviewAcceptanceStage.ROLLBACK_DRILL] >= 2,
            message="Rollback acceptance must cover target pinning and restored health",
            observed=str(
                stage_counts[FinalDecisionReviewAcceptanceStage.ROLLBACK_DRILL]
            ),
            expected=">=2",
        ),
        _check(
            FinalDecisionReviewAcceptanceCheckCode.SAFETY_BOUNDARY,
            safety_boundary_confirmed,
            message="The plan must not apply or authorize the route diff",
            observed=str(route.production_diff_applied).lower(),
            expected="false",
        ),
    )
    blockers = tuple(
        check.code
        for check in checks
        if check.status is FinalDecisionReviewAcceptanceCheckStatus.BLOCK
    )
    ready = not blockers and acceptance_matrix_complete
    return FinalDecisionReviewRouteImplementationPlanV1(
        prepared_at=plan_time,
        status=(
            FinalDecisionReviewRoutePlanStatus.READY_FOR_IMPLEMENTATION_REVIEW
            if ready
            else FinalDecisionReviewRoutePlanStatus.BLOCKED
        ),
        ready_for_implementation_review=ready,
        readiness_dossier=readiness_dossier,
        readiness_dossier_sha256=dossier_sha,
        proposed_route=route,
        proposed_route_sha256=route_sha,
        acceptance_cases=cases,
        source_dossier_confirmed=source_dossier_confirmed,
        proposed_contract_confirmed=proposed_contract_confirmed,
        query_allowlist_confirmed=query_allowlist_confirmed,
        response_contract_confirmed=response_contract_confirmed,
        authentication_confirmed=authentication_confirmed,
        observability_confirmed=observability_confirmed,
        acceptance_matrix_complete=acceptance_matrix_complete,
        safety_boundary_confirmed=safety_boundary_confirmed,
        checks=checks,
        primary_blocker=blockers[0] if blockers else None,
        blockers=blockers,
        warnings=tuple(FinalDecisionReviewRoutePlanWarning),
    )
