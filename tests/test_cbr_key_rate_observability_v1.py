from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json

import pytest

from omni_cio.contracts.v1.macro import (
    CbrKeyRateCacheResultV1,
    CbrKeyRateSnapshotV1,
    KeyRateObservationV1,
    MacroCacheErrorCode,
    MacroCacheStatus,
    MacroDataErrorCode,
    MacroDataStatus,
)
from omni_cio.contracts.v1.market import MarketSourceV1, SourceAuthority
from omni_cio.contracts.v1.observability import (
    ExternalCallStatus,
    FreshnessTelemetry,
    ObservabilityOutcome,
    ObservabilitySeverity,
)
from omni_cio.observability.cbr_key_rate_events_v1 import (
    CbrKeyRateObservabilityError,
    build_cbr_key_rate_cache_event,
    build_cbr_key_rate_source_event,
)


NOW = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
DATE_FROM = date(2025, 7, 30)
DATE_TO = date(2026, 7, 30)
CORRELATION_ID = "corr:cbrkeyrateevent"


def _available_snapshot() -> CbrKeyRateSnapshotV1:
    row = KeyRateObservationV1(
        effective_date=date(2026, 7, 23),
        rate_percent=Decimal("18.00"),
    )
    source = MarketSourceV1(
        provider="Bank of Russia DailyInfo",
        authority=SourceAuthority.OFFICIAL,
        retrieved_at=NOW,
        source_id="DailyInfo.KeyRateXML",
    )
    return CbrKeyRateSnapshotV1(
        requested_from=DATE_FROM,
        requested_to=DATE_TO,
        retrieved_at=NOW,
        status=MacroDataStatus.AVAILABLE,
        source=source,
        observations=(row,),
        current=row,
    )


def _unavailable_snapshot() -> CbrKeyRateSnapshotV1:
    return CbrKeyRateSnapshotV1(
        requested_from=DATE_FROM,
        requested_to=DATE_TO,
        retrieved_at=NOW,
        status=MacroDataStatus.UNAVAILABLE,
        error_code=MacroDataErrorCode.NETWORK_ERROR,
    )


def _fresh_result(
    *,
    served_from_cache: bool,
    refresh_attempted: bool,
    refresh_succeeded: bool,
    cache_error_code: MacroCacheErrorCode | None = None,
) -> CbrKeyRateCacheResultV1:
    return CbrKeyRateCacheResultV1(
        requested_from=DATE_FROM,
        requested_to=DATE_TO,
        checked_at=NOW + timedelta(minutes=10),
        status=MacroCacheStatus.FRESH,
        snapshot=_available_snapshot(),
        age_seconds=600,
        fresh_until=NOW + timedelta(hours=1),
        stale_until=NOW + timedelta(days=1),
        served_from_cache=served_from_cache,
        stale_available=False,
        stale_value_exposed=False,
        refresh_attempted=refresh_attempted,
        refresh_succeeded=refresh_succeeded,
        cache_error_code=cache_error_code,
        display_value_allowed=True,
    )


def _stale_result() -> CbrKeyRateCacheResultV1:
    return CbrKeyRateCacheResultV1(
        requested_from=DATE_FROM,
        requested_to=DATE_TO,
        checked_at=NOW + timedelta(hours=2),
        status=MacroCacheStatus.STALE,
        snapshot=_available_snapshot(),
        age_seconds=7_200,
        fresh_until=NOW + timedelta(hours=1),
        stale_until=NOW + timedelta(days=1),
        served_from_cache=True,
        stale_available=True,
        stale_value_exposed=True,
        refresh_attempted=True,
        refresh_succeeded=False,
        source_error_code=MacroDataErrorCode.NETWORK_ERROR,
        cache_error_code=MacroCacheErrorCode.EXPIRED,
        display_value_allowed=True,
    )


def _unavailable_result() -> CbrKeyRateCacheResultV1:
    return CbrKeyRateCacheResultV1(
        requested_from=DATE_FROM,
        requested_to=DATE_TO,
        checked_at=NOW,
        status=MacroCacheStatus.UNAVAILABLE,
        snapshot=None,
        age_seconds=None,
        fresh_until=None,
        stale_until=None,
        served_from_cache=False,
        stale_available=False,
        stale_value_exposed=False,
        refresh_attempted=True,
        refresh_succeeded=False,
        source_error_code=MacroDataErrorCode.HTTP_ERROR,
        cache_error_code=MacroCacheErrorCode.EMPTY,
        display_value_allowed=False,
    )


def _metrics(event: object) -> dict[str, int]:
    return {
        metric.name: metric.value
        for metric in event.metrics  # type: ignore[attr-defined]
    }


def test_available_source_event_contains_counts_but_not_rate_payload() -> None:
    event = build_cbr_key_rate_source_event(
        _available_snapshot(),
        duration_ms=Decimal("12.5"),
        occurred_at=NOW,
        correlation_id=CORRELATION_ID,
    )

    assert event.outcome is ObservabilityOutcome.SUCCESS
    assert event.severity is ObservabilitySeverity.INFO
    assert event.external_call is not None
    assert event.external_call.status is ExternalCallStatus.SUCCESS
    assert event.external_call.freshness is FreshnessTelemetry.FRESH
    assert event.external_call.latency_ms == Decimal("12.5")
    assert _metrics(event) == {
        "cbr.observation_count": 1,
        "cbr.source_available": 1,
    }
    serialized = json.dumps(event.model_dump(mode="json"), sort_keys=True)
    assert "rate_percent" not in serialized
    assert "18.00" not in serialized
    assert "effective_date" not in serialized
    assert "requested_from" not in serialized
    assert "requested_to" not in serialized
    assert "xml" not in serialized.lower()
    assert event.account is None
    assert event.contains_sensitive_payload is False
    assert event.trading_methods is False


def test_unavailable_source_event_is_redacted_failure() -> None:
    event = build_cbr_key_rate_source_event(
        _unavailable_snapshot(),
        occurred_at=NOW,
        correlation_id=CORRELATION_ID,
    )

    assert event.outcome is ObservabilityOutcome.FAILURE
    assert event.severity is ObservabilitySeverity.ERROR
    assert event.error_code == MacroDataErrorCode.NETWORK_ERROR.value
    assert event.external_call is not None
    assert event.external_call.status is ExternalCallStatus.FAILURE
    assert event.external_call.freshness is FreshnessTelemetry.UNKNOWN
    assert _metrics(event)["cbr.observation_count"] == 0
    assert event.exception_type is None


def test_fresh_cache_hit_records_not_called_without_external_latency() -> None:
    event = build_cbr_key_rate_cache_event(
        _fresh_result(
            served_from_cache=True,
            refresh_attempted=False,
            refresh_succeeded=False,
        ),
        duration_ms=Decimal("2.0"),
        occurred_at=NOW,
        correlation_id=CORRELATION_ID,
    )

    assert event.outcome is ObservabilityOutcome.SUCCESS
    assert event.external_call is not None
    assert event.external_call.status is ExternalCallStatus.NOT_CALLED
    assert event.external_call.latency_ms is None
    assert event.duration_ms == Decimal("2.0")
    assert event.error_code is None
    assert _metrics(event) == {
        "cbr.observation_count": 1,
        "cbr.cache_hit": 1,
        "cbr.refresh_attempted": 0,
        "cbr.refresh_succeeded": 0,
        "cbr.stale_exposed": 0,
        "cbr.display_allowed": 1,
    }


def test_successful_refresh_records_external_success() -> None:
    event = build_cbr_key_rate_cache_event(
        _fresh_result(
            served_from_cache=False,
            refresh_attempted=True,
            refresh_succeeded=True,
        ),
        duration_ms=Decimal("9.0"),
        occurred_at=NOW,
        correlation_id=CORRELATION_ID,
    )

    assert event.outcome is ObservabilityOutcome.SUCCESS
    assert event.external_call is not None
    assert event.external_call.status is ExternalCallStatus.SUCCESS
    assert event.external_call.latency_ms == Decimal("9.0")
    assert event.external_call.freshness is FreshnessTelemetry.FRESH


def test_failed_forced_refresh_with_fresh_cache_is_degraded_warning() -> None:
    event = build_cbr_key_rate_cache_event(
        _fresh_result(
            served_from_cache=True,
            refresh_attempted=True,
            refresh_succeeded=False,
            cache_error_code=MacroCacheErrorCode.REFRESH_FAILED,
        ),
        occurred_at=NOW,
        correlation_id=CORRELATION_ID,
    )

    assert event.outcome is ObservabilityOutcome.DEGRADED
    assert event.severity is ObservabilitySeverity.WARNING
    assert event.error_code == MacroCacheErrorCode.REFRESH_FAILED.value
    assert event.external_call is not None
    assert event.external_call.status is ExternalCallStatus.FAILURE
    assert event.external_call.freshness is FreshnessTelemetry.FRESH


def test_stale_and_unavailable_cache_events_are_explicit() -> None:
    stale = build_cbr_key_rate_cache_event(
        _stale_result(),
        occurred_at=NOW,
        correlation_id=CORRELATION_ID,
    )
    unavailable = build_cbr_key_rate_cache_event(
        _unavailable_result(),
        occurred_at=NOW,
        correlation_id=CORRELATION_ID,
    )

    assert stale.outcome is ObservabilityOutcome.DEGRADED
    assert stale.severity is ObservabilitySeverity.WARNING
    assert stale.external_call is not None
    assert stale.external_call.freshness is FreshnessTelemetry.STALE
    assert stale.error_code == MacroDataErrorCode.NETWORK_ERROR.value
    assert _metrics(stale)["cbr.stale_exposed"] == 1

    assert unavailable.outcome is ObservabilityOutcome.FAILURE
    assert unavailable.severity is ObservabilitySeverity.ERROR
    assert unavailable.external_call is not None
    assert unavailable.external_call.status is ExternalCallStatus.FAILURE
    assert unavailable.error_code == MacroDataErrorCode.HTTP_ERROR.value
    assert _metrics(unavailable)["cbr.display_allowed"] == 0
    assert _metrics(unavailable)["cbr.observation_count"] == 0


def test_events_reject_wrong_types_and_invalid_duration() -> None:
    with pytest.raises(CbrKeyRateObservabilityError):
        build_cbr_key_rate_source_event({"raw": "payload"})  # type: ignore[arg-type]
    with pytest.raises(CbrKeyRateObservabilityError):
        build_cbr_key_rate_cache_event({"raw": "payload"})  # type: ignore[arg-type]
    with pytest.raises(CbrKeyRateObservabilityError):
        build_cbr_key_rate_source_event(
            _available_snapshot(),
            duration_ms=Decimal("-1"),
        )
    with pytest.raises(CbrKeyRateObservabilityError):
        build_cbr_key_rate_cache_event(
            _unavailable_result(),
            duration_ms=Decimal("NaN"),
        )


def test_observability_module_has_no_route_or_write_surface() -> None:
    import omni_cio.observability.cbr_key_rate_events_v1 as module

    assert not hasattr(module, "app")
    assert not hasattr(module, "router")
    assert not hasattr(module, "create_order")
    assert not hasattr(module, "post_order")
