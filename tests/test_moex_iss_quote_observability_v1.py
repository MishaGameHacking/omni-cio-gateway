from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json

import pytest

from omni_cio.contracts.v1.market import MarketQuoteV1, MarketSourceV1, SourceAuthority
from omni_cio.contracts.v1.moex import (
    MoexIssQuoteErrorCode,
    MoexIssQuoteStatus,
    MoexIssTqbrQuoteCacheResultV1,
    MoexIssTqbrQuoteSnapshotV1,
    MoexQuoteCacheErrorCode,
    MoexQuoteCacheStatus,
)
from omni_cio.contracts.v1.observability import (
    ExternalCallStatus,
    FreshnessTelemetry,
    ObservabilityEventV1,
    ObservabilityOutcome,
    ObservabilitySeverity,
)
from omni_cio.observability.moex_iss_quote_events_v1 import (
    MoexIssQuoteObservabilityError,
    build_moex_iss_quote_cache_event,
    build_moex_iss_quote_source_event,
)


NOW = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
CORRELATION_ID = "corr:moexquoteevent"


def _available_snapshot() -> MoexIssTqbrQuoteSnapshotV1:
    source = MarketSourceV1(
        provider="Moscow Exchange ISS",
        authority=SourceAuthority.OFFICIAL,
        retrieved_at=NOW,
        source_id="ISS.stock.shares.TQBR.marketdata",
    )
    quote = MarketQuoteV1(
        instrument_key="MOEX:TQBR:SBER",
        currency="RUB",
        as_of=NOW - timedelta(minutes=15),
        source=source,
        last_price=Decimal("310.25"),
        best_bid=Decimal("310.20"),
        best_ask=Decimal("310.30"),
    )
    return MoexIssTqbrQuoteSnapshotV1(
        secid="SBER",
        retrieved_at=NOW,
        status=MoexIssQuoteStatus.AVAILABLE,
        source=source,
        quote=quote,
        short_name="Сбербанк",
        lot_size=10,
        decimals=2,
    )


def _unavailable_snapshot() -> MoexIssTqbrQuoteSnapshotV1:
    return MoexIssTqbrQuoteSnapshotV1(
        secid="SBER",
        retrieved_at=NOW,
        status=MoexIssQuoteStatus.UNAVAILABLE,
        error_code=MoexIssQuoteErrorCode.NETWORK_ERROR,
    )


def _fresh_result(
    *,
    served_from_cache: bool,
    refresh_attempted: bool,
    refresh_succeeded: bool,
    cache_error_code: MoexQuoteCacheErrorCode | None = None,
) -> MoexIssTqbrQuoteCacheResultV1:
    return MoexIssTqbrQuoteCacheResultV1(
        secid="SBER",
        checked_at=NOW + timedelta(seconds=30),
        status=MoexQuoteCacheStatus.FRESH,
        snapshot=_available_snapshot(),
        age_seconds=930,
        fresh_until=NOW + timedelta(seconds=60),
        stale_until=NOW + timedelta(seconds=900),
        served_from_cache=served_from_cache,
        refresh_attempted=refresh_attempted,
        refresh_succeeded=refresh_succeeded,
        cache_error_code=cache_error_code,
        display_value_allowed=True,
    )


def _stale_result() -> MoexIssTqbrQuoteCacheResultV1:
    return MoexIssTqbrQuoteCacheResultV1(
        secid="SBER",
        checked_at=NOW + timedelta(seconds=61),
        status=MoexQuoteCacheStatus.STALE,
        snapshot=_available_snapshot(),
        age_seconds=961,
        fresh_until=NOW + timedelta(seconds=60),
        stale_until=NOW + timedelta(seconds=900),
        served_from_cache=True,
        stale_available=True,
        stale_value_exposed=True,
        refresh_attempted=True,
        refresh_succeeded=False,
        source_error_code=MoexIssQuoteErrorCode.NETWORK_ERROR,
        cache_error_code=MoexQuoteCacheErrorCode.REFRESH_FAILED,
        display_value_allowed=True,
    )


def _unavailable_result() -> MoexIssTqbrQuoteCacheResultV1:
    return MoexIssTqbrQuoteCacheResultV1(
        secid="SBER",
        checked_at=NOW,
        status=MoexQuoteCacheStatus.UNAVAILABLE,
        refresh_attempted=True,
        refresh_succeeded=False,
        source_error_code=MoexIssQuoteErrorCode.HTTP_ERROR,
        cache_error_code=MoexQuoteCacheErrorCode.EMPTY,
        display_value_allowed=False,
    )


def _metrics(event: ObservabilityEventV1) -> dict[str, int]:
    return {metric.name: metric.value for metric in event.metrics}


def _assert_no_quote_or_identity_payload(event: ObservabilityEventV1) -> None:
    serialized = json.dumps(event.model_dump(mode="json"), sort_keys=True)
    forbidden = (
        "SBER",
        "310.25",
        "310.20",
        "310.30",
        "last_price",
        "best_bid",
        "best_ask",
        "instrument_key",
        "secid",
        "short_name",
        "lot_size",
        "as_of",
        "raw_json",
        "account",
    )
    for value in forbidden:
        assert value not in serialized
    assert event.account is None
    assert event.contains_sensitive_payload is False
    assert event.trading_methods is False


def test_available_source_event_contains_only_safe_operational_metadata() -> None:
    event = build_moex_iss_quote_source_event(
        _available_snapshot(),
        duration_ms=Decimal("12.5"),
        occurred_at=NOW,
        correlation_id=CORRELATION_ID,
    )

    assert event.outcome is ObservabilityOutcome.SUCCESS
    assert event.severity is ObservabilitySeverity.INFO
    assert event.external_call is not None
    assert event.external_call.status is ExternalCallStatus.SUCCESS
    assert event.external_call.freshness is FreshnessTelemetry.UNKNOWN
    assert event.external_call.latency_ms == Decimal("12.5")
    assert event.error_code is None
    assert _metrics(event) == {
        "moex.source_available": 1,
        "moex.public_feed": 1,
        "moex.delayed_possible": 1,
        "moex.realtime_guaranteed": 0,
        "moex.informational_only": 1,
    }
    _assert_no_quote_or_identity_payload(event)


def test_unavailable_source_event_is_redacted_failure() -> None:
    event = build_moex_iss_quote_source_event(
        _unavailable_snapshot(),
        occurred_at=NOW,
        correlation_id=CORRELATION_ID,
    )

    assert event.outcome is ObservabilityOutcome.FAILURE
    assert event.severity is ObservabilitySeverity.ERROR
    assert event.error_code == MoexIssQuoteErrorCode.NETWORK_ERROR.value
    assert event.external_call is not None
    assert event.external_call.status is ExternalCallStatus.FAILURE
    assert _metrics(event)["moex.source_available"] == 0
    assert event.exception_type is None
    _assert_no_quote_or_identity_payload(event)


def test_fresh_cache_hit_records_not_called_without_external_latency() -> None:
    event = build_moex_iss_quote_cache_event(
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
    assert event.external_call.freshness is FreshnessTelemetry.FRESH
    assert event.duration_ms == Decimal("2.0")
    assert event.error_code is None
    assert _metrics(event) == {
        "moex.cache_hit": 1,
        "moex.refresh_attempted": 0,
        "moex.refresh_succeeded": 0,
        "moex.stale_available": 0,
        "moex.stale_exposed": 0,
        "moex.display_allowed": 1,
        "moex.public_feed": 1,
        "moex.delayed_possible": 1,
        "moex.realtime_guaranteed": 0,
        "moex.informational_only": 1,
    }
    _assert_no_quote_or_identity_payload(event)


def test_successful_refresh_records_external_success() -> None:
    event = build_moex_iss_quote_cache_event(
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


def test_failed_force_refresh_with_fresh_cache_is_degraded_warning() -> None:
    event = build_moex_iss_quote_cache_event(
        _fresh_result(
            served_from_cache=True,
            refresh_attempted=True,
            refresh_succeeded=False,
            cache_error_code=MoexQuoteCacheErrorCode.REFRESH_FAILED,
        ),
        occurred_at=NOW,
        correlation_id=CORRELATION_ID,
    )

    assert event.outcome is ObservabilityOutcome.DEGRADED
    assert event.severity is ObservabilitySeverity.WARNING
    assert event.error_code == MoexQuoteCacheErrorCode.REFRESH_FAILED.value
    assert event.external_call is not None
    assert event.external_call.status is ExternalCallStatus.FAILURE
    assert event.external_call.freshness is FreshnessTelemetry.FRESH


def test_stale_and_unavailable_cache_events_are_explicit() -> None:
    stale = build_moex_iss_quote_cache_event(
        _stale_result(),
        occurred_at=NOW,
        correlation_id=CORRELATION_ID,
    )
    unavailable = build_moex_iss_quote_cache_event(
        _unavailable_result(),
        occurred_at=NOW,
        correlation_id=CORRELATION_ID,
    )

    assert stale.outcome is ObservabilityOutcome.DEGRADED
    assert stale.severity is ObservabilitySeverity.WARNING
    assert stale.external_call is not None
    assert stale.external_call.freshness is FreshnessTelemetry.STALE
    assert stale.error_code == MoexIssQuoteErrorCode.NETWORK_ERROR.value
    assert _metrics(stale)["moex.stale_available"] == 1
    assert _metrics(stale)["moex.stale_exposed"] == 1

    assert unavailable.outcome is ObservabilityOutcome.FAILURE
    assert unavailable.severity is ObservabilitySeverity.ERROR
    assert unavailable.external_call is not None
    assert unavailable.external_call.status is ExternalCallStatus.FAILURE
    assert unavailable.external_call.freshness is FreshnessTelemetry.UNKNOWN
    assert unavailable.error_code == MoexIssQuoteErrorCode.HTTP_ERROR.value
    assert _metrics(unavailable)["moex.display_allowed"] == 0
    _assert_no_quote_or_identity_payload(stale)
    _assert_no_quote_or_identity_payload(unavailable)


def test_events_reject_wrong_types_and_invalid_duration() -> None:
    with pytest.raises(MoexIssQuoteObservabilityError):
        build_moex_iss_quote_source_event(  # type: ignore[arg-type]
            {"raw": "payload"}
        )
    with pytest.raises(MoexIssQuoteObservabilityError):
        build_moex_iss_quote_cache_event(  # type: ignore[arg-type]
            {"raw": "payload"}
        )
    with pytest.raises(MoexIssQuoteObservabilityError):
        build_moex_iss_quote_source_event(
            _available_snapshot(),
            duration_ms=Decimal("-1"),
        )
    with pytest.raises(MoexIssQuoteObservabilityError):
        build_moex_iss_quote_cache_event(
            _unavailable_result(),
            duration_ms=Decimal("NaN"),
        )


def test_observability_module_is_pure_and_has_no_route_or_write_surface() -> None:
    import omni_cio.observability.moex_iss_quote_events_v1 as module

    assert not hasattr(module, "app")
    assert not hasattr(module, "router")
    assert not hasattr(module, "emit")
    assert not hasattr(module, "startup")
    assert not hasattr(module, "create_order")
    assert not hasattr(module, "post_order")
    assert not hasattr(module, "cancel_order")
