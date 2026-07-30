from __future__ import annotations

import re
from datetime import datetime, timezone
from threading import RLock

from omni_cio.contracts.v1.final_decision_review_input import (
    FinalDecisionReviewInputBindingV1,
)
from omni_cio.contracts.v1.final_decision_review_publisher import (
    FinalDecisionReviewPublicationDisposition,
    FinalDecisionReviewPublicationResultV1,
)
from omni_cio.contracts.v1.final_decision_review_route_plan import (
    FinalDecisionReviewRouteImplementationPlanV1,
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
from omni_cio.release.final_decision_review_route_v1 import (
    FinalDecisionReviewRouteError,
    FinalDecisionReviewSourceLookupStatus,
    FinalDecisionReviewSourceRegistryV1,
)


_TRACE_IDENTIFIER = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{7,127}$")
_PUBLISHER_ATTRIBUTE = "_final_decision_review_publisher_v1"


class FinalDecisionReviewPublisherError(ValueError):
    """A reviewed final response cannot be published into the internal registry."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise FinalDecisionReviewPublisherError(
            "FINAL_DECISION_REVIEW_PUBLISHER_TIMESTAMP_MUST_BE_AWARE"
        )
    return result.astimezone(timezone.utc)


def _validate_trace_identifiers(
    *,
    correlation_id: str,
    request_id: str | None,
) -> None:
    if _TRACE_IDENTIFIER.fullmatch(correlation_id) is None:
        raise FinalDecisionReviewPublisherError(
            "FINAL_DECISION_REVIEW_PUBLISHER_CORRELATION_ID_INVALID"
        )
    if request_id is not None and _TRACE_IDENTIFIER.fullmatch(request_id) is None:
        raise FinalDecisionReviewPublisherError(
            "FINAL_DECISION_REVIEW_PUBLISHER_REQUEST_ID_INVALID"
        )


def _validate_exact_context(
    route_plan: FinalDecisionReviewRouteImplementationPlanV1,
    input_binding: FinalDecisionReviewInputBindingV1,
) -> None:
    dossier = route_plan.readiness_dossier
    response = dossier.response
    query = input_binding.query
    expected_instruments = tuple(row.instrument_key for row in response.intents)
    exact_context = (
        query.account == response.account
        and query.requested_option_id == response.requested_option_id
        and query.final_option_id == response.final_option_id
        and query.intent_fingerprint == response.intent_fingerprint
        and query.instrument_count == response.instrument_count
        and query.instrument_keys == expected_instruments
        and input_binding.query_sha256 == dossier.query_sha256
        and input_binding.response_sha256 == dossier.response_sha256
        and input_binding.action_candidate_sha256
        == dossier.action_candidate_sha256
    )
    if not exact_context:
        raise FinalDecisionReviewPublisherError(
            "FINAL_DECISION_REVIEW_PUBLISHER_CONTEXT_MISMATCH"
        )


class FinalDecisionReviewPublisherV1:
    """Trusted process-local publisher for the PR-61 bounded source registry."""

    def __init__(self, registry: FinalDecisionReviewSourceRegistryV1) -> None:
        self._registry = registry
        self._lock = RLock()

    @property
    def registry(self) -> FinalDecisionReviewSourceRegistryV1:
        return self._registry

    def publish(
        self,
        route_plan: FinalDecisionReviewRouteImplementationPlanV1,
        input_binding: FinalDecisionReviewInputBindingV1,
        *,
        correlation_id: str,
        request_id: str | None = None,
        published_at: datetime | None = None,
    ) -> FinalDecisionReviewPublicationResultV1:
        now = _aware_utc(published_at)
        _validate_trace_identifiers(
            correlation_id=correlation_id,
            request_id=request_id,
        )
        _validate_exact_context(route_plan, input_binding)
        query = input_binding.query

        with self._lock:
            before = self._registry.lookup(
                account=query.account.masked_id,
                requested_option_id=query.requested_option_id,
                final_option_id=query.final_option_id,
                intent_fingerprint=query.intent_fingerprint,
                instrument_count=query.instrument_count,
                instrument_keys=query.instrument_keys,
                requested_at=now,
            )
            source_replaced = (
                before.status is FinalDecisionReviewSourceLookupStatus.FOUND
            )
            active_before = before.active_source_count
            try:
                source = self._registry.publish(
                    route_plan,
                    input_binding,
                    published_at=now,
                )
            except FinalDecisionReviewRouteError as exc:
                raise FinalDecisionReviewPublisherError(str(exc)) from exc
            active_after = self._registry.active_source_count(checked_at=now)
            expected_without_eviction = active_before + (0 if source_replaced else 1)
            evicted_sources = max(0, expected_without_eviction - active_after)

        disposition = (
            FinalDecisionReviewPublicationDisposition.REPLACED
            if source_replaced
            else FinalDecisionReviewPublicationDisposition.PUBLISHED
        )
        event = ObservabilityEventV1(
            occurred_at=now,
            event_name="final.review.publisher",
            severity=ObservabilitySeverity.INFO,
            component="final_review_publisher",
            outcome=ObservabilityOutcome.SUCCESS,
            correlation_id=correlation_id,
            request_id=request_id,
            account=query.account,
            external_call=ExternalCallTelemetryV1(
                provider="internal_registry",
                operation="publish_final_decision_review_source",
                status=ExternalCallStatus.NOT_CALLED,
                circuit_breaker_state=CircuitBreakerState.NOT_APPLICABLE,
                freshness=FreshnessTelemetry.NOT_APPLICABLE,
            ),
            metrics=(
                SafeCountMetricV1(
                    name="registry.active.sources",
                    value=active_after,
                ),
                SafeCountMetricV1(
                    name="registry.evicted.sources",
                    value=evicted_sources,
                ),
                SafeCountMetricV1(
                    name="source.replaced",
                    value=int(source_replaced),
                ),
                SafeCountMetricV1(
                    name="instrument.count",
                    value=query.instrument_count,
                ),
            ),
        )
        return FinalDecisionReviewPublicationResultV1(
            disposition=disposition,
            published_at=source.published_at,
            expires_at=source.expires_at,
            account=query.account,
            query_sha256=input_binding.query_sha256,
            response_sha256=input_binding.response_sha256,
            action_candidate_sha256=input_binding.action_candidate_sha256,
            instrument_count=query.instrument_count,
            source_replaced=source_replaced,
            registry_active_sources=active_after,
            registry_evicted_sources=evicted_sources,
            observability_event=event,
        )


_PUBLISHER_ATTACHMENT_LOCK = RLock()


def publisher_for_registry(
    registry: FinalDecisionReviewSourceRegistryV1,
) -> FinalDecisionReviewPublisherV1:
    """Return one concurrency guard attached to each process-local registry."""

    with _PUBLISHER_ATTACHMENT_LOCK:
        publisher = getattr(registry, _PUBLISHER_ATTRIBUTE, None)
        if not isinstance(publisher, FinalDecisionReviewPublisherV1):
            publisher = FinalDecisionReviewPublisherV1(registry)
            setattr(registry, _PUBLISHER_ATTRIBUTE, publisher)
        return publisher


def publish_final_decision_review_source(
    registry: FinalDecisionReviewSourceRegistryV1,
    route_plan: FinalDecisionReviewRouteImplementationPlanV1,
    input_binding: FinalDecisionReviewInputBindingV1,
    *,
    correlation_id: str,
    request_id: str | None = None,
    published_at: datetime | None = None,
) -> FinalDecisionReviewPublicationResultV1:
    """Publish through the shared internal publisher for a registry."""

    return publisher_for_registry(registry).publish(
        route_plan,
        input_binding,
        correlation_id=correlation_id,
        request_id=request_id,
        published_at=published_at,
    )
