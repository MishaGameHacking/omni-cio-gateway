from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
from typing import Any, cast

import pytest

from omni_cio.contracts.v1.expert_ra_ratings import (
    ExpertRaIssuerRatingActionsCacheResultV1,
    ExpertRaIssuerRatingActionsSnapshotV1,
    ExpertRaIssuerRatingActionV1,
)
from omni_cio.contracts.v1.market import MarketSourceV1, RatingAction, SourceAuthority
from omni_cio.contracts.v1.observability import (
    ExternalCallStatus,
    FreshnessTelemetry,
    ObservabilityEventV1,
    ObservabilityOutcome,
    ObservabilitySeverity,
)
from omni_cio.contracts.v1.ratings import (
    CreditRatingCacheErrorCode,
    CreditRatingCacheStatus,
    CreditRatingOutlook,
    CreditRatingSourceErrorCode,
    CreditRatingSourceStatus,
)
from omni_cio.observability.expert_ra_rating_actions_events_v1 import (
    ExpertRaRatingActionsObservabilityError,
    build_expert_ra_rating_actions_cache_event,
    build_expert_ra_rating_actions_source_event,
)


NOW = datetime(2026, 8, 1, 7, 0, tzinfo=timezone.utc)
CORRELATION_ID = "corr:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


def _source() -> MarketSourceV1:
    return MarketSourceV1(
        provider="Expert RA",
        authority=SourceAuthority.OFFICIAL,
        retrieved_at=NOW,
        source_id="EXPERT_RA.home.rating_actions",
    )


def _available_snapshot() -> ExpertRaIssuerRatingActionsSnapshotV1:
    source = _source()
    record = ExpertRaIssuerRatingActionV1(
        subject_name="СЕКРЕТНЫЙ ТЕСТОВЫЙ ЭМИТЕНТ",
        rating="ruA",
        action=RatingAction.AFFIRMED,
        outlook=CreditRatingOutlook.NEGATIVE,
        published_on=date(2026, 7, 31),
        release_url="https://raexpert.ru/releases/2026/jul31a",
        source=source,
    )
    return ExpertRaIssuerRatingActionsSnapshotV1(
        retrieved_at=NOW,
        status=CreditRatingSourceStatus.AVAILABLE,
        source=source,
        records=(record,),
    )


def _unavailable_snapshot() -> ExpertRaIssuerRatingActionsSnapshotV1:
    return ExpertRaIssuerRatingActionsSnapshotV1(
        retrieved_at=NOW,
        status=CreditRatingSourceStatus.UNAVAILABLE,
        error_code=CreditRatingSourceErrorCode.NETWORK_ERROR,
    )


def _fresh_result(
    *,
    served_from_cache: bool,
    refresh_attempted: bool,
    refresh_succeeded: bool,
    cache_error_code: CreditRatingCacheErrorCode | None = None,
) -> ExpertRaIssuerRatingActionsCacheResultV1:
    return ExpertRaIssuerRatingActionsCacheResultV1(
        checked_at=NOW + timedelta(seconds=30),
        status=CreditRatingCacheStatus.FRESH,
        snapshot=_available_snapshot(),
        age_seconds=30,
        fresh_until=NOW + timedelta(minutes=15),
        stale_until=NOW + timedelta(days=1),
        served_from_cache=served_from_cache,
        refresh_attempted=refresh_attempted,
        refresh_succeeded=refresh_succeeded,
        cache_error_code=cache_error_code,
        display_records_allowed=True,
    )


def _stale_result() -> ExpertRaIssuerRatingActionsCacheResultV1:
    return ExpertRaIssuerRatingActionsCacheResultV1(
        checked_at=NOW + timedelta(minutes=16),
        status=CreditRatingCacheStatus.STALE,
        snapshot=_available_snapshot(),
        age_seconds=960,
        fresh_until=NOW + timedelta(minutes=15),
        stale_until=NOW + timedelta(days=1),
        served_from_cache=True,
        stale_available=True,
        stale_value_exposed=True,
        refresh_attempted=True,
        refresh_succeeded=False,
        source_error_code=CreditRatingSourceErrorCode.NETWORK_ERROR,
        cache_error_code=CreditRatingCacheErrorCode.REFRESH_FAILED,
        display_records_allowed=True,
    )


def _unavailable_result() -> ExpertRaIssuerRatingActionsCacheResultV1:
    return ExpertRaIssuerRatingActionsCacheResultV1(
        checked_at=NOW,
        status=CreditRatingCacheStatus.UNAVAILABLE,
        refresh_attempted=True,
        refresh_succeeded=False,
        source_error_code=CreditRatingSourceErrorCode.HTTP_ERROR,
        cache_error_code=CreditRatingCacheErrorCode.EMPTY,
        display_records_allowed=False,
    )


def _metrics(event: ObservabilityEventV1) -> dict[str, int]:
    return {metric.name: metric.value for metric in event.metrics}


def _assert_sensitive_rating_payload_absent(event: ObservabilityEventV1) -> None:
    serialized = json.dumps(
        event.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
    )
    forbidden = (
        "СЕКРЕТНЫЙ ТЕСТОВЫЙ ЭМИТЕНТ",
        "ruA",
        "negative",
        "affirmed",
        "jul31a",
        "2026-07-31",
        "subject_name",
        "rating_scale",
        "release_url",
        "published_on",
        "raw_html",
    )
    for value in forbidden:
        assert value not in serialized
    assert event.account is None
    assert event.request_id is None
    assert event.action_id is None
    assert event.exception_type is None
    assert event.contains_sensitive_payload is False
    assert event.trading_methods is False


def test_available_source_event_contains_only_safe_operational_counts() -> None:
    event = build_expert_ra_rating_actions_source_event(
        _available_snapshot(),
        duration_ms=Decimal("12.5"),
        occurred_at=NOW,
        correlation_id=CORRELATION_ID,
    )

    assert event.outcome is ObservabilityOutcome.SUCCESS
    assert event.severity is ObservabilitySeverity.INFO
    assert event.external_call is not None
    assert event.external_call.provider == "Expert RA"
    assert event.external_call.operation == "home.rating_actions"
    assert event.external_call.status is ExternalCallStatus.SUCCESS
    assert event.external_call.freshness is FreshnessTelemetry.FRESH
    assert _metrics(event) == {
        "expert_ra.record_count": 1,
        "expert_ra.source_available": 1,
        "expert_ra.fixed_official_source": 1,
        "expert_ra.issuer_scope_only": 1,
        "expert_ra.identity_resolution_required": 1,
        "expert_ra.cross_agency_identity_merged": 0,
    }
    _assert_sensitive_rating_payload_absent(event)


def test_unavailable_source_event_is_redacted_failure() -> None:
    event = build_expert_ra_rating_actions_source_event(
        _unavailable_snapshot(),
        occurred_at=NOW,
        correlation_id=CORRELATION_ID,
    )

    assert event.outcome is ObservabilityOutcome.FAILURE
    assert event.severity is ObservabilitySeverity.ERROR
    assert event.error_code == CreditRatingSourceErrorCode.NETWORK_ERROR.value
    assert event.external_call is not None
    assert event.external_call.status is ExternalCallStatus.FAILURE
    assert _metrics(event)["expert_ra.record_count"] == 0
    _assert_sensitive_rating_payload_absent(event)


def test_fresh_cache_hit_records_not_called_and_no_external_latency() -> None:
    event = build_expert_ra_rating_actions_cache_event(
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
    assert _metrics(event)["expert_ra.cache_hit"] == 1
    assert _metrics(event)["expert_ra.display_allowed"] == 1
    _assert_sensitive_rating_payload_absent(event)


def test_successful_refresh_records_external_success() -> None:
    event = build_expert_ra_rating_actions_cache_event(
        _fresh_result(
            served_from_cache=False,
            refresh_attempted=True,
            refresh_succeeded=True,
        ),
        duration_ms=Decimal("9.0"),
        occurred_at=NOW,
        correlation_id=CORRELATION_ID,
    )

    assert event.external_call is not None
    assert event.external_call.status is ExternalCallStatus.SUCCESS
    assert event.external_call.latency_ms == Decimal("9.0")
    assert event.error_code is None
    _assert_sensitive_rating_payload_absent(event)


def test_failed_force_refresh_with_fresh_cache_is_degraded() -> None:
    event = build_expert_ra_rating_actions_cache_event(
        _fresh_result(
            served_from_cache=True,
            refresh_attempted=True,
            refresh_succeeded=False,
            cache_error_code=CreditRatingCacheErrorCode.REFRESH_FAILED,
        ),
        occurred_at=NOW,
        correlation_id=CORRELATION_ID,
    )

    assert event.outcome is ObservabilityOutcome.DEGRADED
    assert event.severity is ObservabilitySeverity.WARNING
    assert event.error_code == CreditRatingCacheErrorCode.REFRESH_FAILED.value
    assert event.external_call is not None
    assert event.external_call.freshness is FreshnessTelemetry.FRESH
    _assert_sensitive_rating_payload_absent(event)


def test_stale_and_unavailable_cache_events_are_explicit() -> None:
    stale = build_expert_ra_rating_actions_cache_event(
        _stale_result(), occurred_at=NOW, correlation_id=CORRELATION_ID
    )
    unavailable = build_expert_ra_rating_actions_cache_event(
        _unavailable_result(), occurred_at=NOW, correlation_id=CORRELATION_ID
    )

    assert stale.outcome is ObservabilityOutcome.DEGRADED
    assert stale.external_call is not None
    assert stale.external_call.freshness is FreshnessTelemetry.STALE
    assert _metrics(stale)["expert_ra.stale_exposed"] == 1
    assert unavailable.outcome is ObservabilityOutcome.FAILURE
    assert unavailable.external_call is not None
    assert unavailable.external_call.freshness is FreshnessTelemetry.UNKNOWN
    assert _metrics(unavailable)["expert_ra.display_allowed"] == 0
    _assert_sensitive_rating_payload_absent(stale)
    _assert_sensitive_rating_payload_absent(unavailable)


def test_builders_reject_wrong_types_invalid_duration_and_free_form_trace() -> None:
    with pytest.raises(ExpertRaRatingActionsObservabilityError):
        build_expert_ra_rating_actions_source_event(  # type: ignore[arg-type]
            {"raw": "payload"}
        )
    with pytest.raises(ExpertRaRatingActionsObservabilityError):
        build_expert_ra_rating_actions_cache_event(  # type: ignore[arg-type]
            {"raw": "payload"}
        )
    with pytest.raises(ExpertRaRatingActionsObservabilityError):
        build_expert_ra_rating_actions_source_event(
            _available_snapshot(), duration_ms=Decimal("-1")
        )
    with pytest.raises(ExpertRaRatingActionsObservabilityError):
        build_expert_ra_rating_actions_cache_event(
            _unavailable_result(), duration_ms=Decimal("NaN")
        )
    with pytest.raises(ExpertRaRatingActionsObservabilityError):
        build_expert_ra_rating_actions_source_event(
            _available_snapshot(),
            correlation_id="corr:PRIVATE_ISSUER_NAME_123456789",
        )


def test_validator_bypassed_source_and_cache_models_are_rejected() -> None:
    forged_source = _available_snapshot().model_copy(update={"raw_html_stored": True})
    forged_cache = _fresh_result(
        served_from_cache=True,
        refresh_attempted=False,
        refresh_succeeded=False,
    ).model_copy(update={"trading_methods": True})

    with pytest.raises(ExpertRaRatingActionsObservabilityError):
        build_expert_ra_rating_actions_source_event(cast(Any, forged_source))
    with pytest.raises(ExpertRaRatingActionsObservabilityError):
        build_expert_ra_rating_actions_cache_event(cast(Any, forged_cache))


def test_automatic_correlation_id_remains_opaque() -> None:
    event = build_expert_ra_rating_actions_source_event(
        _available_snapshot(), occurred_at=NOW
    )

    assert event.correlation_id.startswith("corr:")
    assert len(event.correlation_id) == 37
    assert all(character in "abcdefghijklmnop" for character in event.correlation_id[5:])
    _assert_sensitive_rating_payload_absent(event)


def test_observability_module_is_pure_and_has_no_write_or_emit_surface() -> None:
    import omni_cio.observability.expert_ra_rating_actions_events_v1 as module

    for forbidden in (
        "app",
        "router",
        "emit",
        "startup",
        "create_order",
        "post_order",
        "cancel_order",
        "send_email",
        "send_telegram",
        "webhook",
    ):
        assert not hasattr(module, forbidden)
