from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from omni_cio.contracts.v1.moex import (
    MoexIssQuoteStatus,
    MoexIssTqbrQuoteCacheResultV1,
    MoexIssTqbrQuoteSnapshotV1,
    MoexQuoteCacheStatus,
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
from omni_cio.observability.safe_events_v1 import build_safe_event


_MOEX_PROVIDER = "Moscow Exchange ISS"
_MOEX_OPERATION = "TQBR public quote"
_SOURCE_EVENT_NAME = "market.moex_iss_tqbr_quote.source"
_CACHE_EVENT_NAME = "market.moex_iss_tqbr_quote.cache"
_SOURCE_COMPONENT = "market.moex_iss_tqbr_quote_source"
_CACHE_COMPONENT = "market.moex_iss_tqbr_quote_cache"


class MoexIssQuoteObservabilityError(ValueError):
    """MOEX quote telemetry cannot be built safely."""


def _safe_duration(value: Decimal | None) -> Decimal | None:
    if value is not None and (
        not isinstance(value, Decimal) or not value.is_finite() or value < 0
    ):
        raise MoexIssQuoteObservabilityError(
            "MOEX_ISS_QUOTE_OBSERVABILITY_DURATION_INVALID"
        )
    return value


def _metric(name: str, value: int | bool) -> SafeCountMetricV1:
    return SafeCountMetricV1(name=name, value=int(value))


def _feed_metrics() -> tuple[SafeCountMetricV1, ...]:
    return (
        _metric("moex.public_feed", True),
        _metric("moex.delayed_possible", True),
        _metric("moex.realtime_guaranteed", False),
        _metric("moex.informational_only", True),
    )


def build_moex_iss_quote_source_event(
    snapshot: MoexIssTqbrQuoteSnapshotV1,
    *,
    duration_ms: Decimal | None = None,
    occurred_at: datetime | None = None,
    correlation_id: str | None = None,
) -> ObservabilityEventV1:
    """Build one allowlisted source event without quote or identity payload."""
    if not isinstance(snapshot, MoexIssTqbrQuoteSnapshotV1):
        raise MoexIssQuoteObservabilityError(
            "MOEX_ISS_QUOTE_OBSERVABILITY_SOURCE_TYPE_INVALID"
        )
    latency = _safe_duration(duration_ms)
    available = snapshot.status is MoexIssQuoteStatus.AVAILABLE
    error_code = snapshot.error_code.value if snapshot.error_code is not None else None
    external_call = ExternalCallTelemetryV1(
        provider=_MOEX_PROVIDER,
        operation=_MOEX_OPERATION,
        status=(
            ExternalCallStatus.SUCCESS
            if available
            else ExternalCallStatus.FAILURE
        ),
        latency_ms=latency,
        freshness=FreshnessTelemetry.UNKNOWN,
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
            _metric("moex.source_available", available),
            *_feed_metrics(),
        ),
    )


def _cache_event_state(
    result: MoexIssTqbrQuoteCacheResultV1,
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
    if result.status is MoexQuoteCacheStatus.FRESH:
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
    if result.status is MoexQuoteCacheStatus.STALE:
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
        ExternalCallStatus.FAILURE,
        FreshnessTelemetry.UNKNOWN,
        error_code,
    )


def build_moex_iss_quote_cache_event(
    result: MoexIssTqbrQuoteCacheResultV1,
    *,
    duration_ms: Decimal | None = None,
    occurred_at: datetime | None = None,
    correlation_id: str | None = None,
) -> ObservabilityEventV1:
    """Build one cache event with status/count metadata only."""
    if not isinstance(result, MoexIssTqbrQuoteCacheResultV1):
        raise MoexIssQuoteObservabilityError(
            "MOEX_ISS_QUOTE_OBSERVABILITY_CACHE_TYPE_INVALID"
        )
    latency = _safe_duration(duration_ms)
    outcome, severity, call_status, freshness, error_code = _cache_event_state(result)
    external_latency = latency if call_status is not ExternalCallStatus.NOT_CALLED else None
    external_call = ExternalCallTelemetryV1(
        provider=_MOEX_PROVIDER,
        operation=_MOEX_OPERATION,
        status=call_status,
        latency_ms=external_latency,
        freshness=freshness,
    )
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
            _metric("moex.cache_hit", result.served_from_cache),
            _metric("moex.refresh_attempted", result.refresh_attempted),
            _metric("moex.refresh_succeeded", result.refresh_succeeded),
            _metric("moex.stale_available", result.stale_available),
            _metric("moex.stale_exposed", result.stale_value_exposed),
            _metric("moex.display_allowed", result.display_value_allowed),
            *_feed_metrics(),
        ),
    )
