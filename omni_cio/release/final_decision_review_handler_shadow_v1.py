from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal

from omni_cio.contracts.v1.final_decision_review_handler_shadow import (
    FinalDecisionReviewHandlerErrorCode,
    FinalDecisionReviewHandlerErrorMappingV1,
    FinalDecisionReviewHandlerHttpStatus,
    FinalDecisionReviewHandlerShadowResultV1,
    FinalDecisionReviewHandlerShadowStatus,
)
from omni_cio.contracts.v1.final_decision_review_input import (
    FinalDecisionReviewInputBindingV1,
    FinalDecisionReviewInputStatus,
)
from omni_cio.contracts.v1.final_decision_review_route_plan import (
    FinalDecisionReviewRouteImplementationPlanV1,
    FinalDecisionReviewRoutePlanStatus,
)
from omni_cio.contracts.v1.observability import (
    CircuitBreakerState,
    ExternalCallStatus,
    ExternalCallTelemetryV1,
    FreshnessTelemetry,
    ObservabilityEventV1,
    ObservabilityOutcome,
    ObservabilitySeverity,
    SafeCountMetricV1,
)


class FinalDecisionReviewHandlerShadowError(ValueError):
    """The final-review handler shadow cannot be evaluated safely."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise FinalDecisionReviewHandlerShadowError(
            "FINAL_DECISION_REVIEW_HANDLER_SHADOW_TIMESTAMP_MUST_BE_AWARE"
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


def final_decision_review_handler_error_mapping() -> tuple[
    FinalDecisionReviewHandlerErrorMappingV1, ...
]:
    """Return the complete fixed framework and handler error mapping."""

    return (
        FinalDecisionReviewHandlerErrorMappingV1(
            error_code=FinalDecisionReviewHandlerErrorCode.INVALID_REQUEST,
            http_status=FinalDecisionReviewHandlerHttpStatus.BAD_REQUEST,
            description="Canonical request parameters are missing or malformed",
        ),
        FinalDecisionReviewHandlerErrorMappingV1(
            error_code=FinalDecisionReviewHandlerErrorCode.AUTHENTICATION_REQUIRED,
            http_status=FinalDecisionReviewHandlerHttpStatus.UNAUTHORIZED,
            description="Private API-key authentication is absent or rejected",
        ),
        FinalDecisionReviewHandlerErrorMappingV1(
            error_code=FinalDecisionReviewHandlerErrorCode.SOURCE_CONFLICT,
            http_status=FinalDecisionReviewHandlerHttpStatus.CONFLICT,
            description="Reviewed query or source identity does not reconcile",
        ),
        FinalDecisionReviewHandlerErrorMappingV1(
            error_code=FinalDecisionReviewHandlerErrorCode.SCHEMA_VALIDATION,
            http_status=FinalDecisionReviewHandlerHttpStatus.UNPROCESSABLE_ENTITY,
            description="Framework request validation rejects the query schema",
        ),
        FinalDecisionReviewHandlerErrorMappingV1(
            error_code=FinalDecisionReviewHandlerErrorCode.SOURCE_UNAVAILABLE,
            http_status=FinalDecisionReviewHandlerHttpStatus.SERVICE_UNAVAILABLE,
            description="Reviewed route plan or final response source is unavailable",
        ),
    )


def _observability_event(
    *,
    handled_at: datetime,
    route_plan: FinalDecisionReviewRouteImplementationPlanV1,
    correlation_id: str,
    request_id: str | None,
    status: FinalDecisionReviewHandlerShadowStatus,
    error_code: FinalDecisionReviewHandlerErrorCode | None,
) -> ObservabilityEventV1:
    response = route_plan.readiness_dossier.response
    if status is FinalDecisionReviewHandlerShadowStatus.SUCCESS:
        severity = ObservabilitySeverity.INFO
        outcome = ObservabilityOutcome.SUCCESS
    elif status is FinalDecisionReviewHandlerShadowStatus.REJECTED:
        severity = ObservabilitySeverity.WARNING
        outcome = ObservabilityOutcome.REJECTED
    else:
        severity = ObservabilitySeverity.ERROR
        outcome = ObservabilityOutcome.FAILURE
    return ObservabilityEventV1(
        occurred_at=handled_at,
        event_name="final_review.route_handler_shadow",
        severity=severity,
        component="final_review_handler_shadow",
        outcome=outcome,
        correlation_id=correlation_id,
        request_id=request_id,
        action_id=None,
        account=response.account,
        duration_ms=Decimal("0"),
        external_call=ExternalCallTelemetryV1(
            provider="internal",
            operation="final_review_handler_shadow",
            status=ExternalCallStatus.NOT_CALLED,
            retry_count=0,
            circuit_breaker_state=CircuitBreakerState.NOT_APPLICABLE,
            freshness=FreshnessTelemetry.NOT_APPLICABLE,
        ),
        error_code=error_code.value if error_code is not None else None,
        metrics=(
            SafeCountMetricV1(
                name="instrument_count",
                value=response.instrument_count,
            ),
            SafeCountMetricV1(
                name="route_plan_blocker_count",
                value=len(route_plan.blockers),
            ),
        ),
    )


def evaluate_final_decision_review_handler_shadow(
    route_plan: FinalDecisionReviewRouteImplementationPlanV1,
    input_binding: FinalDecisionReviewInputBindingV1,
    *,
    authentication_confirmed: bool,
    source_available: bool = True,
    correlation_id: str,
    request_id: str | None = None,
    handled_at: datetime | None = None,
) -> FinalDecisionReviewHandlerShadowResultV1:
    """Model route-handler behavior without registering or invoking a route."""

    shadow_time = _aware_utc(handled_at)
    plan_sha = _canonical_sha256(route_plan.model_dump(mode="json"))
    binding_sha = _canonical_sha256(input_binding.model_dump(mode="json"))
    source_binding = route_plan.readiness_dossier.input_binding

    route_plan_confirmed = (
        route_plan.status
        is FinalDecisionReviewRoutePlanStatus.READY_FOR_IMPLEMENTATION_REVIEW
        and route_plan.ready_for_implementation_review
        and not route_plan.blockers
    )
    input_binding_confirmed = (
        input_binding.status is FinalDecisionReviewInputStatus.VALID
        and input_binding.input_valid
        and not input_binding.blockers
    )
    source_identity_confirmed = (
        input_binding.query_sha256 == source_binding.query_sha256
        and input_binding.response_sha256 == source_binding.response_sha256
        and input_binding.action_candidate_sha256
        == source_binding.action_candidate_sha256
        and input_binding.query == source_binding.query
    )

    response = None
    response_sha: str | None = None
    error_code: FinalDecisionReviewHandlerErrorCode | None = None
    error_message: str | None = None
    if not authentication_confirmed:
        status = FinalDecisionReviewHandlerShadowStatus.REJECTED
        http_status = FinalDecisionReviewHandlerHttpStatus.UNAUTHORIZED
        error_code = FinalDecisionReviewHandlerErrorCode.AUTHENTICATION_REQUIRED
        error_message = "Private authentication was not confirmed"
    elif not route_plan_confirmed or not source_available:
        status = FinalDecisionReviewHandlerShadowStatus.UNAVAILABLE
        http_status = FinalDecisionReviewHandlerHttpStatus.SERVICE_UNAVAILABLE
        error_code = FinalDecisionReviewHandlerErrorCode.SOURCE_UNAVAILABLE
        error_message = "Reviewed route plan or response source is unavailable"
    elif not input_binding_confirmed or not source_identity_confirmed:
        status = FinalDecisionReviewHandlerShadowStatus.REJECTED
        http_status = FinalDecisionReviewHandlerHttpStatus.CONFLICT
        error_code = FinalDecisionReviewHandlerErrorCode.SOURCE_CONFLICT
        error_message = "Reviewed input identity does not reconcile"
    else:
        status = FinalDecisionReviewHandlerShadowStatus.SUCCESS
        http_status = FinalDecisionReviewHandlerHttpStatus.OK
        response = route_plan.readiness_dossier.response
        response_sha = _canonical_sha256(response.model_dump(mode="json"))

    event = _observability_event(
        handled_at=shadow_time,
        route_plan=route_plan,
        correlation_id=correlation_id,
        request_id=request_id,
        status=status,
        error_code=error_code,
    )
    return FinalDecisionReviewHandlerShadowResultV1(
        handled_at=shadow_time,
        status=status,
        http_status=http_status,
        response=response,
        error_code=error_code,
        error_message=error_message,
        route_plan=route_plan,
        input_binding=input_binding,
        route_plan_sha256=plan_sha,
        input_binding_sha256=binding_sha,
        response_sha256=response_sha,
        authentication_confirmed=authentication_confirmed,
        route_plan_confirmed=route_plan_confirmed,
        input_binding_confirmed=input_binding_confirmed,
        source_identity_confirmed=source_identity_confirmed,
        source_available=source_available,
        error_mapping=final_decision_review_handler_error_mapping(),
        observability_event=event,
    )
