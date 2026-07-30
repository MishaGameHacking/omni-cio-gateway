from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from omni_cio.contracts.v1.observability import (
    ExternalCallStatus,
    ExternalCallTelemetryV1,
    FreshnessTelemetry,
    ObservabilityEventV1,
    ObservabilityOutcome,
    ObservabilitySeverity,
    SafeCountMetricV1,
)
from omni_cio.contracts.v1.ratings import (
    AcraIssuerRatingActionsCacheResultV1,
    AcraIssuerRatingActionsSnapshotV1,
    CreditRatingCacheStatus,
    CreditRatingSourceStatus,
)
from omni_cio.observability.safe_events_v1 import build_safe_event


_ACRA_PROVIDER = "ACRA"
_ACRA_OPERATION = "press_releases.issuer_rating_actions"
_SOURCE_EVENT_NAME = "market.acra_rating_actions.source"
_CACHE_EVENT_NAME = "market.acra_rating_actions.cache"
_SOURCE_COMPONENT = "market.acra_rating_actions_source"
_CACHE_COMPONENT = "market.acra_rating_actions_cache"


class AcraRatingActionsObservabilityError(ValueError):
    """ACRA source/cache telemetry cannot be built safely."""


def _safe_duration(value: Decimal | None) -> Decimal | None:
    if value is not None and (
        not isinstance(value, Decimal) or not value.is_finite() or value < 0
    ):
        raise AcraRatingActionsObservabilityError(
            "ACRA_RATING_ACTIONS_OBSERVABILITY_DURATION_INVALID"
        )
    return value


def _metric(name: str, value: int | bool) -> SafeCountMetricV1:
    return SafeCountMetricV1(name=name, value=int(value))


def build_acra_rating_actions_source_event(
    snapshot: AcraIssuerRatingActionsSnapshotV1,
    *,
    duration_ms: Decimal | None = None,
    occurred_at: datetime | None = None,
    correlation_id: str | None = None,
) -> ObservabilityEventV1:
    """Build one allowlisted source event without rating-action content."""
    if not isinstance(snapshot, AcraIssuerRatingActionsSnapshotV1):
        raise AcraRatingActionsObservabilityError(
            "ACRA_RATING_ACTIONS_OBSERVABILITY_SOURCE_TYPE_INVALID"
        )
    latency = _safe_duration(duration_ms)
    available = snapshot.status is CreditRatingSourceStatus.AVAILABLE
    error_code = snapshot.error_code.value if snapshot.error_code is not None else None
    external_call = ExternalCallTelemetryV1(
        provider=_ACRA_PROVIDER,
        operation=_ACRA_OPERATION,
        status=(
            ExternalCallStatus.SUCCESS
            if available
            else ExternalCallStatus.FAILURE
        ),
        latency_ms=latency,
        freshness=(
            FreshnessTelemetry.FRESH
            if available
            else FreshnessTelemetry.UNKNOWN
        ),
    )
    return build_safe_event(
        event_name=_SOURCE_EVENT_NAME,
        component=_SOURCE_COMPONENT,
        outcome=(
            ObservabilityOutcome.SUCCESS
            if available
            else ObservabilityOutcome.FAILURE
        ),
        severity=(
            ObservabilitySeverity.INFO
            if available
            else ObservabilitySeverity.ERROR
        ),
        occurred_at=occurred_at,
        correlation_id=correlation_id,
        duration_ms=latency,
        external_call=external_call,
        error_code=error_code,
        metrics=(
            _metric("acra.record_count", len(snapshot.records)),
            _metric("acra.source_available", available),
            _metric("acra.fixed_official_source", snapshot.fixed_official_source),
            _metric("acra.issuer_scope_only", snapshot.issuer_scope_only),
        ),
    )


def _cache_event_state(
    result: AcraIssuerRatingActionsCacheResultV1,
) -> tuple[
    ObservabilityOutcome,
    ObservabilitySeverity,
    ExternalCallStatus,
    FreshnessTelemetry,
    str | None,
]:
    error_code = (
        result.source_error_code.value
        if result.source_error_code is not None
        else (
            result.cache_error_code.value
            if result.cache_error_code is not None
            else None
        )
    )
    if result.status is CreditRatingCacheStatus.FRESH:
        if result.refresh_attempted and not result.refresh_succeeded:
            return (
                ObservabilityOutcome.DEGRADED,
                ObservabilitySeverity.WARNING,
                ExternalCallStatus.FAILURE,
                FreshnessTelemetry.FRESH,
                error_code,
            )
        return (
            ObservabilityOutcome.SUCCESS,
            ObservabilitySeverity.INFO,
            (
                ExternalCallStatus.SUCCESS
                if result.refresh_attempted
                else ExternalCallStatus.NOT_CALLED
            ),
            FreshnessTelemetry.FRESH,
            None,
        )
    if result.status is CreditRatingCacheStatus.STALE:
        return (
            ObservabilityOutcome.DEGRADED,
            ObservabilitySeverity.WARNING,
            ExternalCallStatus.FAILURE,
            FreshnessTelemetry.STALE,
            error_code,
        )
    return (
        ObservabilityOutcome.FAILURE,
        ObservabilitySeverity.ERROR,
        (
            ExternalCallStatus.FAILURE
            if result.refresh_attempted
            else ExternalCallStatus.NOT_CALLED
        ),
        FreshnessTelemetry.UNKNOWN,
        error_code,
    )


def build_acra_rating_actions_cache_event(
    result: AcraIssuerRatingActionsCacheResultV1,
    *,
    duration_ms: Decimal | None = None,
    occurred_at: datetime | None = None,
    correlation_id: str | None = None,
) -> ObservabilityEventV1:
    """Build one cache event with operational status/count metadata only."""
    if not isinstance(result, AcraIssuerRatingActionsCacheResultV1):
        raise AcraRatingActionsObservabilityError(
            "ACRA_RATING_ACTIONS_OBSERVABILITY_CACHE_TYPE_INVALID"
        )
    latency = _safe_duration(duration_ms)
    outcome, severity, call_status, freshness, error_code = _cache_event_state(result)
    external_latency = latency if call_status is not ExternalCallStatus.NOT_CALLED else None
    external_call = ExternalCallTelemetryV1(
        provider=_ACRA_PROVIDER,
        operation=_ACRA_OPERATION,
        status=call_status,
        latency_ms=external_latency,
        freshness=freshness,
    )
    record_count = len(result.snapshot.records) if result.snapshot is not None else 0
    return build_safe_event(
        event_name=_CACHE_EVENT_NAME,
        component=_CACHE_COMPONENT,
        outcome=outcome,
        severity=severity,
        occurred_at=occurred_at,
        correlation_id=correlation_id,
        duration_ms=latency,
        external_call=external_call,
        error_code=error_code,
        metrics=(
            _metric("acra.record_count", record_count),
            _metric("acra.cache_hit", result.served_from_cache),
            _metric("acra.refresh_attempted", result.refresh_attempted),
            _metric("acra.refresh_succeeded", result.refresh_succeeded),
            _metric("acra.stale_available", result.stale_available),
            _metric("acra.stale_exposed", result.stale_value_exposed),
            _metric("acra.display_allowed", result.display_records_allowed),
            _metric("acra.fixed_official_source", result.fixed_official_source),
            _metric("acra.issuer_scope_only", result.issuer_scope_only),
        ),
    )
