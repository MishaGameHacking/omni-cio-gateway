from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

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
from omni_cio.contracts.v1.final_decision_review_route_readiness import (
    FinalDecisionReviewRouteControlsV1,
    FinalDecisionReviewRouteReadinessCheckCode,
    FinalDecisionReviewRouteReadinessCheckStatus,
    FinalDecisionReviewRouteReadinessCheckV1,
    FinalDecisionReviewRouteReadinessDossierV1,
    FinalDecisionReviewRouteReadinessStatus,
    FinalDecisionReviewRouteReadinessWarning,
)


class FinalDecisionReviewRouteReadinessError(ValueError):
    """The final-review production-route dossier cannot be built safely."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise FinalDecisionReviewRouteReadinessError(
            "FINAL_DECISION_REVIEW_ROUTE_READINESS_TIMESTAMP_MUST_BE_AWARE"
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
    code: FinalDecisionReviewRouteReadinessCheckCode,
    passed: bool,
    *,
    message: str,
    observed: str,
    expected: str,
) -> FinalDecisionReviewRouteReadinessCheckV1:
    return FinalDecisionReviewRouteReadinessCheckV1(
        code=code,
        status=(
            FinalDecisionReviewRouteReadinessCheckStatus.PASS
            if passed
            else FinalDecisionReviewRouteReadinessCheckStatus.BLOCK
        ),
        message=message,
        observed=observed,
        expected=expected,
    )


def build_final_decision_review_route_readiness_dossier(
    response: FinalDecisionReviewResponseV1,
    release_eligibility: FinalDecisionReviewReleaseEligibilityV1,
    action_shadow: FinalDecisionReviewOpenApiShadowV1,
    input_binding: FinalDecisionReviewInputBindingV1,
    *,
    controls: FinalDecisionReviewRouteControlsV1 | None = None,
    assessed_at: datetime | None = None,
) -> FinalDecisionReviewRouteReadinessDossierV1:
    """Compose PR-53 through PR-56 evidence without creating a route."""

    assessment_time = _aware_utc(assessed_at)
    route_controls = controls or FinalDecisionReviewRouteControlsV1()
    response_sha = _canonical_sha256(response.model_dump(mode="json"))
    candidate_sha = _canonical_sha256(
        action_shadow.candidate.model_dump(mode="json")
    )
    query_sha = _canonical_sha256(
        input_binding.query.model_dump(mode="json")
    )

    source_statuses_confirmed = (
        release_eligibility.status is FinalDecisionReviewReleaseStatus.ELIGIBLE
        and release_eligibility.eligible
        and action_shadow.status
        is FinalDecisionReviewActionCandidateStatus.SHADOW_VALID
        and action_shadow.shadow_valid
        and input_binding.status is FinalDecisionReviewInputStatus.VALID
        and input_binding.input_valid
    )
    response_identity_confirmed = (
        release_eligibility.response_sha256 == response_sha
        and action_shadow.release_eligibility.response_sha256 == response_sha
        and input_binding.response_sha256 == response_sha
        and input_binding.query.response_sha256 == response_sha
    )
    candidate_identity_confirmed = (
        input_binding.action_candidate_sha256 == candidate_sha
        and input_binding.query.action_candidate_sha256 == candidate_sha
    )
    query_identity_confirmed = input_binding.query_sha256 == query_sha

    query = input_binding.query
    context_parity_confirmed = (
        query.account == response.account
        and query.requested_option_id == response.requested_option_id
        and query.final_option_id == response.final_option_id
        and query.intent_fingerprint == response.intent_fingerprint
        and query.instrument_count == response.instrument_count
        and query.instrument_keys
        == tuple(row.instrument_key for row in response.intents)
    )

    candidate = action_shadow.candidate
    authentication_controls_confirmed = (
        not candidate.public
        and candidate.authentication_required
        and candidate.security_scheme == route_controls.authentication_scheme
        and route_controls.private_action
        and route_controls.authentication_required
        and route_controls.server_authorization_documented
    )
    rollback_controls_confirmed = (
        route_controls.rollback_runbook_reference
        == "docs/operations/DEPLOYMENT_RUNBOOK.md"
        and route_controls.rollback_commit_pinning_required
    )
    observability_controls_confirmed = (
        route_controls.observability_contract_name == "ObservabilityEventV1"
        and route_controls.correlation_id_required
        and route_controls.masked_account_logging_only
        and route_controls.sensitive_payload_logging_forbidden
        and route_controls.deployment_health_path == "/health"
        and route_controls.required_entrypoint == "app:app"
    )
    safety_boundary_confirmed = (
        not release_eligibility.route_approval_granted
        and not release_eligibility.route_added
        and not release_eligibility.openapi_changed
        and not action_shadow.production_schema_mutated
        and not action_shadow.route_added
        and not action_shadow.openapi_changed
        and not action_shadow.public_action_created
        and not input_binding.route_added
        and not input_binding.openapi_changed
        and not input_binding.public_action_created
        and not route_controls.production_route_reviewed
        and not route_controls.route_approval_granted
    )

    checks = (
        _check(
            FinalDecisionReviewRouteReadinessCheckCode.SOURCE_STATUSES,
            source_statuses_confirmed,
            message="All PR-54 through PR-56 source decisions must be valid",
            observed=(
                f"{release_eligibility.status.value}|"
                f"{action_shadow.status.value}|{input_binding.status.value}"
            ),
            expected="eligible|shadow_valid|valid",
        ),
        _check(
            FinalDecisionReviewRouteReadinessCheckCode.RESPONSE_IDENTITY,
            response_identity_confirmed,
            message="Every source must identify the same PR-53 response",
            observed=input_binding.response_sha256,
            expected=response_sha,
        ),
        _check(
            FinalDecisionReviewRouteReadinessCheckCode.CANDIDATE_IDENTITY,
            candidate_identity_confirmed,
            message="PR-56 must identify the exact PR-55 Action candidate",
            observed=input_binding.action_candidate_sha256,
            expected=candidate_sha,
        ),
        _check(
            FinalDecisionReviewRouteReadinessCheckCode.QUERY_IDENTITY,
            query_identity_confirmed,
            message="PR-56 query digest must remain canonical and exact",
            observed=input_binding.query_sha256,
            expected=query_sha,
        ),
        _check(
            FinalDecisionReviewRouteReadinessCheckCode.CONTEXT_PARITY,
            context_parity_confirmed,
            message="Account, options, fingerprint and instruments must match",
            observed=query.intent_fingerprint,
            expected=response.intent_fingerprint,
        ),
        _check(
            FinalDecisionReviewRouteReadinessCheckCode.AUTHENTICATION,
            authentication_controls_confirmed,
            message="Candidate must remain private and API-key authenticated",
            observed=(
                f"public={candidate.public};auth={candidate.security_scheme}"
            ),
            expected="public=false;auth=ApiKeyAuth",
        ),
        _check(
            FinalDecisionReviewRouteReadinessCheckCode.ROLLBACK,
            rollback_controls_confirmed,
            message="Deployment rollback control must be documented",
            observed=route_controls.rollback_runbook_reference,
            expected="docs/operations/DEPLOYMENT_RUNBOOK.md",
        ),
        _check(
            FinalDecisionReviewRouteReadinessCheckCode.OBSERVABILITY,
            observability_controls_confirmed,
            message="Safe traceable observability controls must be present",
            observed=route_controls.observability_contract_name,
            expected="ObservabilityEventV1",
        ),
        _check(
            FinalDecisionReviewRouteReadinessCheckCode.SAFETY_BOUNDARY,
            safety_boundary_confirmed,
            message="No source may add or approve the production route",
            observed=str(route_controls.route_approval_granted).lower(),
            expected="false",
        ),
    )
    blockers = tuple(
        check.code
        for check in checks
        if check.status is FinalDecisionReviewRouteReadinessCheckStatus.BLOCK
    )
    ready_for_review = not blockers
    return FinalDecisionReviewRouteReadinessDossierV1(
        assessed_at=assessment_time,
        status=(
            FinalDecisionReviewRouteReadinessStatus.READY_FOR_ROUTE_REVIEW
            if ready_for_review
            else FinalDecisionReviewRouteReadinessStatus.BLOCKED
        ),
        ready_for_route_review=ready_for_review,
        response=response,
        release_eligibility=release_eligibility,
        action_shadow=action_shadow,
        input_binding=input_binding,
        controls=route_controls,
        response_sha256=response_sha,
        action_candidate_sha256=candidate_sha,
        query_sha256=query_sha,
        source_statuses_confirmed=source_statuses_confirmed,
        response_identity_confirmed=response_identity_confirmed,
        candidate_identity_confirmed=candidate_identity_confirmed,
        query_identity_confirmed=query_identity_confirmed,
        context_parity_confirmed=context_parity_confirmed,
        authentication_controls_confirmed=authentication_controls_confirmed,
        rollback_controls_confirmed=rollback_controls_confirmed,
        observability_controls_confirmed=observability_controls_confirmed,
        safety_boundary_confirmed=safety_boundary_confirmed,
        checks=checks,
        primary_blocker=blockers[0] if blockers else None,
        blockers=blockers,
        warnings=tuple(FinalDecisionReviewRouteReadinessWarning),
    )
