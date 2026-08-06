from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json

from pydantic import ValidationError
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
from omni_cio.contracts.v1.moex_alerting import (
    MoexQuoteAlertDisposition,
    MoexQuoteAlertKind,
    MoexQuoteAlertPolicyV1,
)
from omni_cio.contracts.v1.observability import (
    ExternalCallStatus,
    ExternalCallTelemetryV1,
    FreshnessTelemetry,
    ObservabilityOutcome,
    ObservabilitySeverity,
    SafeCountMetricV1,
)
from omni_cio.observability.moex_iss_quote_alert_policy_v1 import (
    MoexQuoteAlertPolicyError,
    MoexQuoteAlertPolicyEvaluatorV1,
)
from omni_cio.observability.moex_iss_quote_events_v1 import (
    build_moex_iss_quote_cache_event,
    build_moex_iss_quote_source_event,
)
from omni_cio.observability.safe_events_v1 import build_safe_event


NOW = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
CORRELATION = "corr:moexalertpolicy"


def _available_snapshot() -> MoexIssTqbrQuoteSnapshotV1:
    source = MarketSourceV1(
        provider="Moscow Exchange ISS",
        authority=SourceAuthority.OFFICIAL,
        retrieved_at=NOW,
        source_id="ISS.stock.shares.TQBR.marketdata",
    )
    return MoexIssTqbrQuoteSnapshotV1(
        secid="SBER",
        retrieved_at=NOW,
        status=MoexIssQuoteStatus.AVAILABLE,
        source=source,
        quote=MarketQuoteV1(
            instrument_key="MOEX:TQBR:SBER",
            currency="RUB",
            as_of=NOW - timedelta(minutes=15),
            source=source,
            last_price=Decimal("310.25"),
            best_bid=Decimal("310.20"),
            best_ask=Decimal("310.30"),
        ),
        short_name="Sberbank",
        lot_size=10,
        decimals=2,
    )


def _source_event(*, available: bool, at: datetime):
    snapshot = (
        _available_snapshot().model_copy(update={"retrieved_at": at})
        if available
        else MoexIssTqbrQuoteSnapshotV1(
            secid="SBER",
            retrieved_at=at,
            status=MoexIssQuoteStatus.UNAVAILABLE,
            error_code=MoexIssQuoteErrorCode.NETWORK_ERROR,
        )
    )
    return build_moex_iss_quote_source_event(
        snapshot,
        occurred_at=at,
        correlation_id=CORRELATION,
    )


def _cache_result(status: str, *, at: datetime) -> MoexIssTqbrQuoteCacheResultV1:
    snapshot = _available_snapshot()
    if status == "fresh_hit":
        return MoexIssTqbrQuoteCacheResultV1(
            secid="SBER",
            checked_at=at,
            status=MoexQuoteCacheStatus.FRESH,
            snapshot=snapshot,
            age_seconds=900,
            fresh_until=at + timedelta(seconds=30),
            stale_until=at + timedelta(seconds=300),
            served_from_cache=True,
            display_value_allowed=True,
        )
    if status == "refresh_failed_fresh":
        return MoexIssTqbrQuoteCacheResultV1(
            secid="SBER",
            checked_at=at,
            status=MoexQuoteCacheStatus.FRESH,
            snapshot=snapshot,
            age_seconds=900,
            fresh_until=at + timedelta(seconds=30),
            stale_until=at + timedelta(seconds=300),
            served_from_cache=True,
            refresh_attempted=True,
            refresh_succeeded=False,
            source_error_code=MoexIssQuoteErrorCode.NETWORK_ERROR,
            cache_error_code=MoexQuoteCacheErrorCode.REFRESH_FAILED,
            display_value_allowed=True,
        )
    if status == "stale":
        return MoexIssTqbrQuoteCacheResultV1(
            secid="SBER",
            checked_at=at,
            status=MoexQuoteCacheStatus.STALE,
            snapshot=snapshot,
            age_seconds=961,
            fresh_until=at - timedelta(seconds=1),
            stale_until=at + timedelta(seconds=300),
            served_from_cache=True,
            stale_available=True,
            stale_value_exposed=True,
            refresh_attempted=True,
            refresh_succeeded=False,
            source_error_code=MoexIssQuoteErrorCode.NETWORK_ERROR,
            cache_error_code=MoexQuoteCacheErrorCode.REFRESH_FAILED,
            display_value_allowed=True,
        )
    return MoexIssTqbrQuoteCacheResultV1(
        secid="SBER",
        checked_at=at,
        status=MoexQuoteCacheStatus.UNAVAILABLE,
        refresh_attempted=True,
        refresh_succeeded=False,
        source_error_code=MoexIssQuoteErrorCode.HTTP_ERROR,
        cache_error_code=MoexQuoteCacheErrorCode.EMPTY,
        display_value_allowed=False,
    )


def _cache_event(status: str, *, at: datetime):
    return build_moex_iss_quote_cache_event(
        _cache_result(status, at=at),
        occurred_at=at,
        correlation_id=CORRELATION,
    )


def _policy(**updates: int) -> MoexQuoteAlertPolicyV1:
    values = {
        "source_unavailable_threshold": 2,
        "cache_unavailable_threshold": 2,
        "stale_value_threshold": 2,
        "refresh_failure_threshold": 2,
        "cooldown_seconds": 60,
        "state_retention_seconds": 60,
    }
    values.update(updates)
    return MoexQuoteAlertPolicyV1(**values)


def test_policy_is_global_and_has_no_financial_or_notification_controls() -> None:
    policy = MoexQuoteAlertPolicyV1()
    assert policy.scope == "global_moex_tqbr_feed"
    assert policy.capacity == 4
    assert policy.instrument_identity_present is False
    assert policy.financial_thresholds_present is False
    assert policy.external_notifications_enabled is False
    assert policy.trading_methods is False
    with pytest.raises(ValidationError):
        MoexQuoteAlertPolicyV1(capacity=5)


def test_source_threshold_fire_cooldown_and_recovery() -> None:
    evaluator = MoexQuoteAlertPolicyEvaluatorV1(_policy())

    pending = evaluator.evaluate(_source_event(available=False, at=NOW))[0]
    fired = evaluator.evaluate(
        _source_event(available=False, at=NOW + timedelta(seconds=1))
    )[0]
    suppressed = evaluator.evaluate(
        _source_event(available=False, at=NOW + timedelta(seconds=2))
    )[0]
    recovered = evaluator.evaluate(
        _source_event(available=True, at=NOW + timedelta(seconds=3))
    )[0]

    assert pending.disposition is MoexQuoteAlertDisposition.PENDING
    assert fired.disposition is MoexQuoteAlertDisposition.FIRED
    assert fired.kind is MoexQuoteAlertKind.SOURCE_UNAVAILABLE
    assert suppressed.disposition is MoexQuoteAlertDisposition.SUPPRESSED_COOLDOWN
    assert suppressed.cooldown_remaining_seconds == 59
    assert recovered.disposition is MoexQuoteAlertDisposition.RECOVERED
    assert recovered.kind is MoexQuoteAlertKind.SOURCE_UNAVAILABLE
    assert evaluator.state_count == 0


def test_all_cache_operational_signals_map_to_global_kinds() -> None:
    cases = {
        "unavailable": MoexQuoteAlertKind.CACHE_UNAVAILABLE,
        "stale": MoexQuoteAlertKind.STALE_VALUE_EXPOSED,
        "refresh_failed_fresh": (
            MoexQuoteAlertKind.REFRESH_FAILED_USING_FRESH_CACHE
        ),
    }
    for status, expected in cases.items():
        evaluator = MoexQuoteAlertPolicyEvaluatorV1(_policy())
        evaluation = evaluator.evaluate(_cache_event(status, at=NOW))[0]
        assert evaluation.kind is expected
        assert evaluation.scope == "global_moex_tqbr_feed"
        assert evaluation.disposition is MoexQuoteAlertDisposition.PENDING
        assert evaluation.instrument_identity_present is False
        assert evaluation.financial_thresholds_present is False
        assert evaluation.external_notification_sent is False


def test_cache_signal_recovers_active_sibling_before_new_pending_state() -> None:
    evaluator = MoexQuoteAlertPolicyEvaluatorV1(_policy(stale_value_threshold=1))
    fired = evaluator.evaluate(_cache_event("stale", at=NOW))[0]
    assert fired.disposition is MoexQuoteAlertDisposition.FIRED

    evaluations = evaluator.evaluate(
        _cache_event("unavailable", at=NOW + timedelta(seconds=1))
    )
    assert [item.disposition for item in evaluations] == [
        MoexQuoteAlertDisposition.RECOVERED,
        MoexQuoteAlertDisposition.PENDING,
    ]
    assert evaluations[0].kind is MoexQuoteAlertKind.STALE_VALUE_EXPOSED
    assert evaluations[1].kind is MoexQuoteAlertKind.CACHE_UNAVAILABLE


def test_healthy_cache_event_recovers_active_cache_signal() -> None:
    evaluator = MoexQuoteAlertPolicyEvaluatorV1(_policy(cache_unavailable_threshold=1))
    evaluator.evaluate(_cache_event("unavailable", at=NOW))
    recovered = evaluator.evaluate(
        _cache_event("fresh_hit", at=NOW + timedelta(seconds=1))
    )[0]
    assert recovered.disposition is MoexQuoteAlertDisposition.RECOVERED
    assert recovered.kind is MoexQuoteAlertKind.CACHE_UNAVAILABLE


def test_irrelevant_event_is_ignored_without_state() -> None:
    event = build_safe_event(
        event_name="system.unrelated.health",
        component="system.unrelated",
        outcome=ObservabilityOutcome.SUCCESS,
        occurred_at=NOW,
        correlation_id=CORRELATION,
    )
    evaluator = MoexQuoteAlertPolicyEvaluatorV1()
    result = evaluator.evaluate(event)[0]
    assert result.disposition is MoexQuoteAlertDisposition.IGNORED
    assert evaluator.state_count == 0


def test_forged_known_event_is_rejected_fail_closed() -> None:
    forged = build_safe_event(
        event_name="market.moex_iss_tqbr_quote.source",
        component="market.moex_iss_tqbr_quote_source",
        outcome=ObservabilityOutcome.FAILURE,
        severity=ObservabilitySeverity.ERROR,
        occurred_at=NOW,
        correlation_id=CORRELATION,
        error_code="MOEX_QUOTE_SOURCE_UNAVAILABLE",
        external_call=ExternalCallTelemetryV1(
            provider="Moscow Exchange ISS",
            operation="TQBR public quote",
            status=ExternalCallStatus.FAILURE,
            freshness=FreshnessTelemetry.UNKNOWN,
        ),
        metrics=(SafeCountMetricV1(name="moex.source_available", value=0),),
    )
    with pytest.raises(
        MoexQuoteAlertPolicyError,
        match="MOEX_ALERT_EVENT_CONTRACT_INVALID",
    ):
        MoexQuoteAlertPolicyEvaluatorV1().evaluate(forged)


def test_out_of_order_signal_fails_closed() -> None:
    evaluator = MoexQuoteAlertPolicyEvaluatorV1(_policy())
    evaluator.evaluate(_source_event(available=False, at=NOW + timedelta(seconds=5)))
    with pytest.raises(MoexQuoteAlertPolicyError, match="OUT_OF_ORDER"):
        evaluator.evaluate(_source_event(available=False, at=NOW))


def test_pending_state_expires_after_retention_and_clear_resets_state() -> None:
    evaluator = MoexQuoteAlertPolicyEvaluatorV1(_policy())
    evaluator.evaluate(_source_event(available=False, at=NOW))
    assert evaluator.state_count == 1

    unrelated = build_safe_event(
        event_name="system.unrelated.health",
        component="system.unrelated",
        outcome=ObservabilityOutcome.SUCCESS,
        occurred_at=NOW + timedelta(seconds=61),
        correlation_id=CORRELATION,
    )
    evaluator.evaluate(unrelated)
    assert evaluator.state_count == 0

    evaluator.evaluate(_source_event(available=False, at=NOW + timedelta(seconds=62)))
    evaluator.clear()
    assert evaluator.state_count == 0


def test_concurrent_equal_timestamp_updates_are_serialized() -> None:
    evaluator = MoexQuoteAlertPolicyEvaluatorV1(
        _policy(source_unavailable_threshold=1, cooldown_seconds=60)
    )
    events = [_source_event(available=False, at=NOW) for _ in range(20)]
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda event: evaluator.evaluate(event)[0], events))

    dispositions = [result.disposition for result in results]
    assert dispositions.count(MoexQuoteAlertDisposition.FIRED) == 1
    assert dispositions.count(MoexQuoteAlertDisposition.SUPPRESSED_COOLDOWN) == 19
    assert evaluator.state_count == 1


def test_evaluation_serialization_has_no_market_identity_or_price_payload() -> None:
    evaluator = MoexQuoteAlertPolicyEvaluatorV1(_policy())
    evaluation = evaluator.evaluate(_cache_event("stale", at=NOW))[0]
    serialized = json.dumps(evaluation.model_dump(mode="json"), sort_keys=True)
    for forbidden in (
        "SBER",
        "310.25",
        "310.20",
        "310.30",
        "secid",
        "instrument_key",
        "last_price",
        "best_bid",
        "best_ask",
        "as_of",
        "account",
        "raw_json",
    ):
        assert forbidden not in serialized
    assert evaluation.contains_sensitive_payload is False
    assert evaluation.trading_methods is False


def test_module_has_no_external_transport_or_write_surface() -> None:
    import omni_cio.observability.moex_iss_quote_alert_policy_v1 as module

    for forbidden in (
        "app",
        "router",
        "emit",
        "webhook",
        "send_email",
        "telegram",
        "pager",
        "create_order",
        "post_order",
        "cancel_order",
    ):
        assert not hasattr(module, forbidden)
