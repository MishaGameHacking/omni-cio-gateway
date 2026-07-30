from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from omni_cio.contracts.v1.decision_pro_forma_risk_binding import (
    ProFormaRiskIntentBindingV1,
)
from omni_cio.contracts.v1.final_decision_review import (
    FinalDecisionReviewShadowStatus,
)
from omni_cio.contracts.v1.final_decision_review_action_candidate import (
    FinalDecisionReviewActionCandidateStatus,
    FinalDecisionReviewOpenApiShadowV1,
)
from omni_cio.contracts.v1.final_decision_review_input import (
    FinalDecisionReviewInputPolicyV1,
    FinalDecisionReviewInputStatus,
)
from omni_cio.contracts.v1.final_decision_review_orchestration import (
    FinalDecisionReviewOrchestrationResultV1,
    FinalDecisionReviewOrchestrationStage,
    FinalDecisionReviewOrchestrationStatus,
)
from omni_cio.contracts.v1.final_decision_review_release import (
    FinalDecisionReviewReleasePolicyV1,
    FinalDecisionReviewReleaseStatus,
)
from omni_cio.contracts.v1.final_decision_review_route_plan import (
    FinalDecisionReviewProposedRouteV1,
    FinalDecisionReviewRoutePlanStatus,
)
from omni_cio.contracts.v1.final_decision_review_route_readiness import (
    FinalDecisionReviewRouteControlsV1,
    FinalDecisionReviewRouteReadinessStatus,
)
from omni_cio.decision.final_decision_review_v1 import (
    build_final_decision_review_shadow,
)
from omni_cio.release.final_decision_review_eligibility_v1 import (
    assess_final_decision_review_release_eligibility,
)
from omni_cio.release.final_decision_review_input_v1 import (
    bind_final_decision_review_read_only_input,
    build_final_decision_review_read_only_query,
)
from omni_cio.release.final_decision_review_openapi_shadow_v1 import (
    FinalDecisionReviewOpenApiShadowError,
    build_final_decision_review_openapi_shadow,
)
from omni_cio.release.final_decision_review_publisher_v1 import (
    FinalDecisionReviewPublisherError,
    publish_final_decision_review_source,
)
from omni_cio.release.final_decision_review_route_plan_v1 import (
    build_final_decision_review_route_implementation_plan,
)
from omni_cio.release.final_decision_review_route_readiness_v1 import (
    build_final_decision_review_route_readiness_dossier,
)
from omni_cio.release.final_decision_review_route_v1 import (
    FINAL_REVIEW_OPERATION_ID,
    FINAL_REVIEW_PATH,
    FINAL_REVIEW_SECURITY_SCHEME,
    FinalDecisionReviewSourceRegistryV1,
)
from omni_cio.release.read_only_contract_v1 import ReadOnlyReleaseError


_HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


class FinalDecisionReviewOrchestrationError(ValueError):
    """The internal final-review chain cannot be composed safely."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise FinalDecisionReviewOrchestrationError(
            "FINAL_DECISION_REVIEW_ORCHESTRATION_TIMESTAMP_MUST_BE_AWARE"
        )
    return result.astimezone(timezone.utc)


def _blocker_value(value: object, fallback: str) -> str:
    if value is None:
        return fallback
    raw = getattr(value, "value", value)
    text = str(raw).strip()
    return text or fallback


def _production_pre_route_baseline(
    current_openapi_schema: Mapping[str, Any],
) -> dict[str, Any]:
    """Remove only the exact PR-61 route from a deep-copied production schema."""

    baseline = deepcopy(dict(current_openapi_schema))
    paths_raw = baseline.get("paths")
    if not isinstance(paths_raw, dict):
        raise FinalDecisionReviewOrchestrationError(
            "FINAL_DECISION_REVIEW_ORCHESTRATION_PATHS_REQUIRED"
        )
    path_item = paths_raw.get(FINAL_REVIEW_PATH)
    if not isinstance(path_item, dict):
        raise FinalDecisionReviewOrchestrationError(
            "FINAL_DECISION_REVIEW_ORCHESTRATION_PRODUCTION_ROUTE_REQUIRED"
        )
    exposed_methods = set(path_item).intersection(_HTTP_METHODS)
    operation = path_item.get("get")
    if exposed_methods != {"get"} or not isinstance(operation, dict):
        raise FinalDecisionReviewOrchestrationError(
            "FINAL_DECISION_REVIEW_ORCHESTRATION_ROUTE_METHOD_MISMATCH"
        )
    if operation.get("operationId") != FINAL_REVIEW_OPERATION_ID:
        raise FinalDecisionReviewOrchestrationError(
            "FINAL_DECISION_REVIEW_ORCHESTRATION_OPERATION_ID_MISMATCH"
        )
    if operation.get("security") != [{FINAL_REVIEW_SECURITY_SCHEME: []}]:
        raise FinalDecisionReviewOrchestrationError(
            "FINAL_DECISION_REVIEW_ORCHESTRATION_AUTH_MISMATCH"
        )
    if "requestBody" in operation:
        raise FinalDecisionReviewOrchestrationError(
            "FINAL_DECISION_REVIEW_ORCHESTRATION_REQUEST_BODY_FORBIDDEN"
        )
    query_names = tuple(
        parameter.get("name")
        for parameter in operation.get("parameters", [])
        if isinstance(parameter, dict) and parameter.get("in") == "query"
    )
    expected_query_names = FinalDecisionReviewProposedRouteV1().query_parameters
    if query_names != expected_query_names:
        raise FinalDecisionReviewOrchestrationError(
            "FINAL_DECISION_REVIEW_ORCHESTRATION_QUERY_CONTRACT_MISMATCH"
        )
    if not all(
        parameter.get("required") is True
        for parameter in operation.get("parameters", [])
        if isinstance(parameter, dict) and parameter.get("in") == "query"
    ):
        raise FinalDecisionReviewOrchestrationError(
            "FINAL_DECISION_REVIEW_ORCHESTRATION_QUERY_REQUIRED_MISMATCH"
        )
    paths_raw.pop(FINAL_REVIEW_PATH)
    return baseline


def _blocked(
    *,
    orchestrated_at: datetime,
    stage: FinalDecisionReviewOrchestrationStage,
    blocker: str,
    response_shadow: Any,
    release_eligibility: Any = None,
    action_shadow: FinalDecisionReviewOpenApiShadowV1 | None = None,
    input_binding: Any = None,
    readiness_dossier: Any = None,
    route_plan: Any = None,
) -> FinalDecisionReviewOrchestrationResultV1:
    return FinalDecisionReviewOrchestrationResultV1(
        orchestrated_at=orchestrated_at,
        status=FinalDecisionReviewOrchestrationStatus.BLOCKED,
        completed_stage=stage,
        published=False,
        primary_blocker=blocker,
        response_shadow=response_shadow,
        release_eligibility=release_eligibility,
        action_shadow=action_shadow,
        input_binding=input_binding,
        readiness_dossier=readiness_dossier,
        route_plan=route_plan,
    )


def orchestrate_final_decision_review_publication(
    source_binding: ProFormaRiskIntentBindingV1,
    current_openapi_schema: Mapping[str, Any],
    registry: FinalDecisionReviewSourceRegistryV1,
    *,
    expected_app_version: str,
    approved_hosts: frozenset[str],
    correlation_id: str,
    request_id: str | None = None,
    release_policy: FinalDecisionReviewReleasePolicyV1 | None = None,
    input_policy: FinalDecisionReviewInputPolicyV1 | None = None,
    route_controls: FinalDecisionReviewRouteControlsV1 | None = None,
    orchestrated_at: datetime | None = None,
) -> FinalDecisionReviewOrchestrationResultV1:
    """Compose PR-53 through PR-62 and publish only a fully reviewed source."""

    now = _aware_utc(orchestrated_at)
    response_shadow = build_final_decision_review_shadow(
        source_binding,
        generated_at=now,
    )
    response = response_shadow.response
    if (
        response_shadow.status is not FinalDecisionReviewShadowStatus.MATCH
        or not response_shadow.shadow_valid
        or response_shadow.mismatches
    ):
        blocker = (
            _blocker_value(
                response_shadow.mismatches[0],
                "final_decision_review_shadow_mismatch",
            )
            if response_shadow.mismatches
            else "final_decision_review_shadow_mismatch"
        )
        return _blocked(
            orchestrated_at=now,
            stage=FinalDecisionReviewOrchestrationStage.RESPONSE_SHADOW,
            blocker=blocker,
            response_shadow=response_shadow,
        )

    release_eligibility = assess_final_decision_review_release_eligibility(
        response,
        response_shadow,
        policy=release_policy,
        intended_http_method="GET",
        assessed_at=now,
    )
    if (
        release_eligibility.status is not FinalDecisionReviewReleaseStatus.ELIGIBLE
        or not release_eligibility.eligible
        or release_eligibility.blockers
    ):
        return _blocked(
            orchestrated_at=now,
            stage=FinalDecisionReviewOrchestrationStage.RELEASE_ELIGIBILITY,
            blocker=_blocker_value(
                release_eligibility.primary_blocker,
                "final_decision_review_release_ineligible",
            ),
            response_shadow=response_shadow,
            release_eligibility=release_eligibility,
        )

    try:
        pre_route_schema = _production_pre_route_baseline(current_openapi_schema)
        action_shadow = build_final_decision_review_openapi_shadow(
            pre_route_schema,
            release_eligibility,
            expected_app_version=expected_app_version,
            approved_hosts=approved_hosts,
            validated_at=now,
        )
    except (
        FinalDecisionReviewOrchestrationError,
        FinalDecisionReviewOpenApiShadowError,
        ReadOnlyReleaseError,
    ) as exc:
        return _blocked(
            orchestrated_at=now,
            stage=FinalDecisionReviewOrchestrationStage.ACTION_SHADOW,
            blocker=str(exc),
            response_shadow=response_shadow,
            release_eligibility=release_eligibility,
        )

    if (
        action_shadow.status
        is not FinalDecisionReviewActionCandidateStatus.SHADOW_VALID
        or not action_shadow.shadow_valid
        or action_shadow.blockers
    ):
        return _blocked(
            orchestrated_at=now,
            stage=FinalDecisionReviewOrchestrationStage.ACTION_SHADOW,
            blocker=_blocker_value(
                action_shadow.primary_blocker,
                "final_decision_review_action_shadow_blocked",
            ),
            response_shadow=response_shadow,
            release_eligibility=release_eligibility,
            action_shadow=action_shadow,
        )

    query = build_final_decision_review_read_only_query(response, action_shadow)
    input_binding = bind_final_decision_review_read_only_input(
        query,
        response,
        action_shadow,
        policy=input_policy,
        validated_at=now,
    )
    if (
        input_binding.status is not FinalDecisionReviewInputStatus.VALID
        or not input_binding.input_valid
        or input_binding.blockers
    ):
        return _blocked(
            orchestrated_at=now,
            stage=FinalDecisionReviewOrchestrationStage.INPUT_BINDING,
            blocker=_blocker_value(
                input_binding.primary_blocker,
                "final_decision_review_input_blocked",
            ),
            response_shadow=response_shadow,
            release_eligibility=release_eligibility,
            action_shadow=action_shadow,
            input_binding=input_binding,
        )

    readiness_dossier = build_final_decision_review_route_readiness_dossier(
        response,
        release_eligibility,
        action_shadow,
        input_binding,
        controls=route_controls,
        assessed_at=now,
    )
    if (
        readiness_dossier.status
        is not FinalDecisionReviewRouteReadinessStatus.READY_FOR_ROUTE_REVIEW
        or not readiness_dossier.ready_for_route_review
        or readiness_dossier.blockers
    ):
        return _blocked(
            orchestrated_at=now,
            stage=FinalDecisionReviewOrchestrationStage.ROUTE_READINESS,
            blocker=_blocker_value(
                readiness_dossier.primary_blocker,
                "final_decision_review_route_readiness_blocked",
            ),
            response_shadow=response_shadow,
            release_eligibility=release_eligibility,
            action_shadow=action_shadow,
            input_binding=input_binding,
            readiness_dossier=readiness_dossier,
        )

    route_plan = build_final_decision_review_route_implementation_plan(
        readiness_dossier,
        prepared_at=now,
    )
    if (
        route_plan.status
        is not FinalDecisionReviewRoutePlanStatus.READY_FOR_IMPLEMENTATION_REVIEW
        or not route_plan.ready_for_implementation_review
        or route_plan.blockers
    ):
        return _blocked(
            orchestrated_at=now,
            stage=FinalDecisionReviewOrchestrationStage.ROUTE_PLAN,
            blocker=_blocker_value(
                route_plan.primary_blocker,
                "final_decision_review_route_plan_blocked",
            ),
            response_shadow=response_shadow,
            release_eligibility=release_eligibility,
            action_shadow=action_shadow,
            input_binding=input_binding,
            readiness_dossier=readiness_dossier,
            route_plan=route_plan,
        )

    try:
        publication = publish_final_decision_review_source(
            registry,
            route_plan,
            input_binding,
            correlation_id=correlation_id,
            request_id=request_id,
            published_at=now,
        )
    except FinalDecisionReviewPublisherError as exc:
        return _blocked(
            orchestrated_at=now,
            stage=FinalDecisionReviewOrchestrationStage.PUBLICATION,
            blocker=str(exc),
            response_shadow=response_shadow,
            release_eligibility=release_eligibility,
            action_shadow=action_shadow,
            input_binding=input_binding,
            readiness_dossier=readiness_dossier,
            route_plan=route_plan,
        )

    return FinalDecisionReviewOrchestrationResultV1(
        orchestrated_at=now,
        status=FinalDecisionReviewOrchestrationStatus.PUBLISHED,
        completed_stage=FinalDecisionReviewOrchestrationStage.PUBLICATION,
        published=True,
        response_shadow=response_shadow,
        release_eligibility=release_eligibility,
        action_shadow=action_shadow,
        input_binding=input_binding,
        readiness_dossier=readiness_dossier,
        route_plan=route_plan,
        publication=publication,
    )
