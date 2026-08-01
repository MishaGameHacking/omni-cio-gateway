from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import re

from omni_cio.contracts.v1.expert_ra_ratings import (
    ExpertRaIssuerRatingActionsCacheResultV1,
    ExpertRaIssuerRatingActionsSnapshotV1,
)
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
    CreditRatingCacheStatus,
    CreditRatingSourceStatus,
)
from omni_cio.observability.safe_events_v1 import build_safe_event


_EXPERT_RA_PROVIDER = "Expert RA"
_EXPERT_RA_OPERATION = "home.rating_actions"
_SOURCE_EVENT_NAME = "market.expert_ra_rating_actions.source"
_CACHE_EVENT_NAME = "market.expert_ra_rating_actions.cache"
_SOURCE_COMPONENT = "market.expert_ra_rating_actions_source"
_CACHE_COMPONENT = "market.expert_ra_rating_actions_cache"
_OPAQUE_CORRELATION_ID = re.compile(r"^corr:[a-p]{32}$")


class ExpertRaRatingActionsObservabilityError(ValueError):
    """Expert RA source/cache telemetry cannot be built safely."""


def _safe_duration(value: Decimal | None) -> Decimal | None:
    if value is not None and (
        not isinstance(value, Decimal) or not value.is_finite() or value < 0
    ):
        raise ExpertRaRatingActionsObservabilityError(
            "EXPERT_RA_RATING_ACTIONS_OBSERVABILITY_DURATION_INVALID"
        )
    return value


def _safe_correlation_id(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or _OPAQUE_CORRELATION_ID.fullmatch(value) is None:
        raise ExpertRaRatingActionsObservabilityError(
            "EXPERT_RA_RATING_ACTIONS_OBSERVABILITY_CORRELATION_ID_INVALID"
        )
    return value


def _metric(name: str, value: int | bool) -> SafeCountMetricV1:
    return SafeCountMetricV1(name=name, value=int(value))


def _validated_snapshot(
    value: ExpertRaIssuerRatingActionsSnapshotV1,
) -> ExpertRaIssuerRatingActionsSnapshotV1:
    if not isinstance(value, ExpertRaIssuerRatingActionsSnapshotV1):
        raise ExpertRaRatingActionsObservabilityError(
            "EXPERT_RA_RATING_ACTIONS_OBSERVABILITY_SOURCE_TYPE_INVALID"
        )
    try:
        validated = ExpertRaIssuerRatingActionsSnapshotV1.model_validate(
            value.model_dump(mode="python", warnings="error")
        )
    except Exception as exc:
        raise ExpertRaRatingActionsObservabilityError(
            "EXPERT_RA_RATING_ACTIONS_OBSERVABILITY_SOURCE_INVALID"
        ) from None
    if validated != value:
        raise ExpertRaRatingActionsObservabilityError(
            "EXPERT_RA_RATING_ACTIONS_OBSERVABILITY_SOURCE_INVALID"
        )
    return validated


def _validated_cache_result(
    value: ExpertRaIssuerRatingActionsCacheResultV1,
) -> ExpertRaIssuerRatingActionsCacheResultV1:
    if not isinstance(value, ExpertRaIssuerRatingActionsCacheResultV1):
        raise ExpertRaRatingActionsObservabilityError(
            "EXPERT_RA_RATING_ACTIONS_OBSERVABILITY_CACHE_TYPE_INVALID"
        )
    try:
        validated = ExpertRaIssuerRatingActionsCacheResultV1.model_validate(
            value.model_dump(mode="python", warnings="error")
        )
    except Exception as exc:
        raise ExpertRaRatingActionsObservabilityError(
            "EXPERT_RA_RATING_ACTIONS_OBSERVABILITY_CACHE_INVALID"
        ) from None
    if validated != value:
        raise ExpertRaRatingActionsObservabilityError(
            "EXPERT_RA_RATING_ACTIONS_OBSERVABILITY_CACHE_INVALID"
        )
    return validated


def build_expert_ra_rating_actions_source_event(
    snapshot: ExpertRaIssuerRatingActionsSnapshotV1,
    *,
    duration_ms: Decimal | None = None,
    occurred_at: datetime | None = None,
    correlation_id: str | None = None,
) -> ObservabilityEventV1:
    """Build one allowlisted source event without issuer/rating content."""
    safe_snapshot = _validated_snapshot(snapshot)
    latency = _safe_duration(duration_ms)
    opaque_correlation_id = _safe_correlation_id(correlation_id)
    available = safe_snapshot.status is CreditRatingSourceStatus.AVAILABLE
    error_code = (
        safe_snapshot.error_code.value
        if safe_snapshot.error_code is not None
        else None
    )
    external_call = ExternalCallTelemetryV1(
        provider=_EXPERT_RA_PROVIDER,
        operation=_EXPERT_RA_OPERATION,
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
        correlation_id=opaque_correlation_id,
        duration_ms=latency,
        external_call=external_call,
        error_code=error_code,
        metrics=(
            _metric("expert_ra.record_count", len(safe_snapshot.records)),
            _metric("expert_ra.source_available", available),
            _metric(
                "expert_ra.fixed_official_source",
                safe_snapshot.fixed_official_source,
            ),
            _metric("expert_ra.issuer_scope_only", safe_snapshot.issuer_scope_only),
            _metric(
                "expert_ra.identity_resolution_required",
                safe_snapshot.subject_identity_resolution_required,
            ),
            _metric(
                "expert_ra.cross_agency_identity_merged",
                safe_snapshot.cross_agency_identity_merged,
            ),
        ),
    )


def _cache_event_state(
    result: ExpertRaIssuerRatingActionsCacheResultV1,
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


def build_expert_ra_rating_actions_cache_event(
    result: ExpertRaIssuerRatingActionsCacheResultV1,
    *,
    duration_ms: Decimal | None = None,
    occurred_at: datetime | None = None,
    correlation_id: str | None = None,
) -> ObservabilityEventV1:
    """Build cache telemetry from operational state/count metadata only."""
    safe_result = _validated_cache_result(result)
    latency = _safe_duration(duration_ms)
    opaque_correlation_id = _safe_correlation_id(correlation_id)
    outcome, severity, call_status, freshness, error_code = _cache_event_state(
        safe_result
    )
    external_latency = (
        latency if call_status is not ExternalCallStatus.NOT_CALLED else None
    )
    external_call = ExternalCallTelemetryV1(
        provider=_EXPERT_RA_PROVIDER,
        operation=_EXPERT_RA_OPERATION,
        status=call_status,
        latency_ms=external_latency,
        freshness=freshness,
    )
    record_count = (
        len(safe_result.snapshot.records)
        if safe_result.snapshot is not None
        else 0
    )
    return build_safe_event(
        event_name=_CACHE_EVENT_NAME,
        component=_CACHE_COMPONENT,
        outcome=outcome,
        severity=severity,
        occurred_at=occurred_at,
        correlation_id=opaque_correlation_id,
        duration_ms=latency,
        external_call=external_call,
        error_code=error_code,
        metrics=(
            _metric("expert_ra.record_count", record_count),
            _metric("expert_ra.cache_hit", safe_result.served_from_cache),
            _metric(
                "expert_ra.refresh_attempted",
                safe_result.refresh_attempted,
            ),
            _metric(
                "expert_ra.refresh_succeeded",
                safe_result.refresh_succeeded,
            ),
            _metric("expert_ra.stale_available", safe_result.stale_available),
            _metric("expert_ra.stale_exposed", safe_result.stale_value_exposed),
            _metric(
                "expert_ra.display_allowed",
                safe_result.display_records_allowed,
            ),
            _metric(
                "expert_ra.fixed_official_source",
                safe_result.fixed_official_source,
            ),
            _metric("expert_ra.issuer_scope_only", safe_result.issuer_scope_only),
            _metric(
                "expert_ra.identity_resolution_required",
                safe_result.subject_identity_resolution_required,
            ),
            _metric(
                "expert_ra.cross_agency_identity_merged",
                safe_result.cross_agency_identity_merged,
            ),
        ),
    )
