from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json

import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1.alerting import (
    CbrKeyRateAlertDisposition,
    CbrKeyRateAlertEvaluationV1,
    CbrKeyRateAlertKind,
    CbrKeyRateAlertPolicyV1,
)
from omni_cio.contracts.v1.observability import (
    ExternalCallStatus,
    ExternalCallTelemetryV1,
    FreshnessTelemetry,
    ObservabilityEventV1,
    ObservabilityOutcome,
    ObservabilitySeverity,
)
from omni_cio.observability.cbr_key_rate_alert_policy_v1 import (
    CbrKeyRateAlertPolicyError,
    CbrKeyRateAlertPolicyEvaluatorV1,
)


NOW = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
CORRELATION_ID = "corr:cbralertpolicy"
SOURCE_EVENT = "macro.cbr_key_rate.source"
CACHE_EVENT = "macro.cbr_key_rate.cache"


def _event(
    *,
    event_name: str,
    occurred_at: datetime,
    outcome: ObservabilityOutcome,
    severity: ObservabilitySeverity,
    error_code: str | None = None,
    freshness: FreshnessTelemetry = FreshnessTelemetry.UNKNOWN,
    external_status: ExternalCallStatus = ExternalCallStatus.FAILURE,
) -> ObservabilityEventV1:
    return ObservabilityEventV1(
        occurred_at=occurred_at,
        event_name=event_name,
        severity=severity,
        component="macro.cbr_key_rate",
        outcome=outcome,
        correlation_id=CORRELATION_ID,
        duration_ms=Decimal("1.0"),
        external_call=ExternalCallTelemetryV1(
            provider="Bank of Russia DailyInfo",
            operation="KeyRateXML",
            status=external_status,
            latency_ms=(
                None
                if external_status is ExternalCallStatus.NOT_CALLED
                else Decimal("1.0")
            ),
            freshness=freshness,
        ),
        error_code=error_code,
    )


def _source_failure(at: datetime) -> ObservabilityEventV1:
    return _event(
        event_name=SOURCE_EVENT,
        occurred_at=at,
        outcome=ObservabilityOutcome.FAILURE,
        severity=ObservabilitySeverity.ERROR,
        error_code="CBR_KEY_RATE_NETWORK_ERROR",
    )


def _source_success(at: datetime) -> ObservabilityEventV1:
    return _event(
        event_name=SOURCE_EVENT,
        occurred_at=at,
        outcome=ObservabilityOutcome.SUCCESS,
        severity=ObservabilitySeverity.INFO,
        freshness=FreshnessTelemetry.FRESH,
        external_status=ExternalCallStatus.SUCCESS,
    )


def _cache_unavailable(at: datetime) -> ObservabilityEventV1:
    return _event(
        event_name=CACHE_EVENT,
        occurred_at=at,
        outcome=ObservabilityOutcome.FAILURE,
        severity=ObservabilitySeverity.ERROR,
        error_code="CBR_KEY_RATE_CACHE_UNAVAILABLE",
    )


def _cache_stale(at: datetime) -> ObservabilityEventV1:
    return _event(
        event_name=CACHE_EVENT,
        occurred_at=at,
        outcome=ObservabilityOutcome.DEGRADED,
        severity=ObservabilitySeverity.WARNING,
        error_code="CBR_KEY_RATE_STALE_EXPOSED",
        freshness=FreshnessTelemetry.STALE,
    )


def _cache_refresh_failure(at: datetime) -> ObservabilityEventV1:
    return _event(
        event_name=CACHE_EVENT,
        occurred_at=at,
        outcome=ObservabilityOutcome.DEGRADED,
        severity=ObservabilitySeverity.WARNING,
        error_code="CBR_KEY_RATE_REFRESH_FAILED",
        freshness=FreshnessTelemetry.FRESH,
    )


def _cache_success(at: datetime) -> ObservabilityEventV1:
    return _event(
        event_name=CACHE_EVENT,
        occurred_at=at,
        outcome=ObservabilityOutcome.SUCCESS,
        severity=ObservabilitySeverity.INFO,
        freshness=FreshnessTelemetry.FRESH,
        external_status=ExternalCallStatus.NOT_CALLED,
    )


def test_source_threshold_deduplication_and_cooldown() -> None:
    evaluator = CbrKeyRateAlertPolicyEvaluatorV1(
        CbrKeyRateAlertPolicyV1(
            source_unavailable_threshold=3,
            cooldown_seconds=900,
        )
    )

    first = evaluator.evaluate(_source_failure(NOW))[0]
    second = evaluator.evaluate(_source_failure(NOW + timedelta(minutes=1)))[0]
    fired = evaluator.evaluate(_source_failure(NOW + timedelta(minutes=2)))[0]
    suppressed = evaluator.evaluate(_source_failure(NOW + timedelta(minutes=3)))[0]
    reminded = evaluator.evaluate(_source_failure(NOW + timedelta(minutes=17)))[0]

    assert first.disposition is CbrKeyRateAlertDisposition.PENDING
    assert first.consecutive_occurrences == 1
    assert second.disposition is CbrKeyRateAlertDisposition.PENDING
    assert fired.disposition is CbrKeyRateAlertDisposition.FIRED
    assert fired.kind is CbrKeyRateAlertKind.SOURCE_UNAVAILABLE
    assert suppressed.disposition is CbrKeyRateAlertDisposition.SUPPRESSED_COOLDOWN
    assert suppressed.cooldown_remaining_seconds == 840
    assert reminded.disposition is CbrKeyRateAlertDisposition.FIRED
    assert reminded.consecutive_occurrences == 5


def test_success_recovers_active_alert_and_resets_pending_count() -> None:
    evaluator = CbrKeyRateAlertPolicyEvaluatorV1(
        CbrKeyRateAlertPolicyV1(source_unavailable_threshold=2)
    )
    evaluator.evaluate(_source_failure(NOW))
    evaluator.evaluate(_source_failure(NOW + timedelta(minutes=1)))

    recovered = evaluator.evaluate(_source_success(NOW + timedelta(minutes=2)))
    restarted = evaluator.evaluate(_source_failure(NOW + timedelta(minutes=3)))[0]

    assert len(recovered) == 1
    assert recovered[0].disposition is CbrKeyRateAlertDisposition.RECOVERED
    assert recovered[0].kind is CbrKeyRateAlertKind.SOURCE_UNAVAILABLE
    assert restarted.disposition is CbrKeyRateAlertDisposition.PENDING
    assert restarted.consecutive_occurrences == 1


def test_cache_signal_change_recovers_active_sibling_before_new_pending() -> None:
    evaluator = CbrKeyRateAlertPolicyEvaluatorV1(
        CbrKeyRateAlertPolicyV1(
            stale_value_threshold=2,
            refresh_failure_threshold=2,
        )
    )
    evaluator.evaluate(_cache_stale(NOW))
    fired = evaluator.evaluate(_cache_stale(NOW + timedelta(minutes=1)))[0]

    changed = evaluator.evaluate(_cache_refresh_failure(NOW + timedelta(minutes=2)))

    assert fired.disposition is CbrKeyRateAlertDisposition.FIRED
    assert [item.disposition for item in changed] == [
        CbrKeyRateAlertDisposition.RECOVERED,
        CbrKeyRateAlertDisposition.PENDING,
    ]
    assert changed[0].kind is CbrKeyRateAlertKind.STALE_VALUE_EXPOSED
    assert changed[1].kind is CbrKeyRateAlertKind.REFRESH_FAILED_USING_FRESH_CACHE


def test_cache_success_recovers_unavailable_and_clears_pending_siblings() -> None:
    evaluator = CbrKeyRateAlertPolicyEvaluatorV1(
        CbrKeyRateAlertPolicyV1(cache_unavailable_threshold=1)
    )
    fired = evaluator.evaluate(_cache_unavailable(NOW))[0]
    recovered = evaluator.evaluate(_cache_success(NOW + timedelta(minutes=1)))
    ignored = evaluator.evaluate(_cache_success(NOW + timedelta(minutes=2)))[0]

    assert fired.disposition is CbrKeyRateAlertDisposition.FIRED
    assert recovered[0].disposition is CbrKeyRateAlertDisposition.RECOVERED
    assert recovered[0].kind is CbrKeyRateAlertKind.CACHE_UNAVAILABLE
    assert ignored.disposition is CbrKeyRateAlertDisposition.IGNORED
    assert evaluator.state_count == 0


def test_unsupported_event_is_ignored_without_state() -> None:
    evaluator = CbrKeyRateAlertPolicyEvaluatorV1()
    event = _event(
        event_name="portfolio.snapshot.loaded",
        occurred_at=NOW,
        outcome=ObservabilityOutcome.SUCCESS,
        severity=ObservabilitySeverity.INFO,
        external_status=ExternalCallStatus.NOT_CALLED,
    )

    result = evaluator.evaluate(event)[0]

    assert result.disposition is CbrKeyRateAlertDisposition.IGNORED
    assert evaluator.state_count == 0


def test_out_of_order_event_fails_closed() -> None:
    evaluator = CbrKeyRateAlertPolicyEvaluatorV1()
    evaluator.evaluate(_source_failure(NOW + timedelta(minutes=1)))

    with pytest.raises(CbrKeyRateAlertPolicyError, match="OUT_OF_ORDER"):
        evaluator.evaluate(_source_failure(NOW))


def test_state_retention_prunes_abandoned_pending_alert() -> None:
    evaluator = CbrKeyRateAlertPolicyEvaluatorV1(
        CbrKeyRateAlertPolicyV1(state_retention_seconds=60)
    )
    evaluator.evaluate(_source_failure(NOW))
    evaluator.evaluate(
        _event(
            event_name="portfolio.snapshot.loaded",
            occurred_at=NOW + timedelta(seconds=61),
            outcome=ObservabilityOutcome.SUCCESS,
            severity=ObservabilitySeverity.INFO,
            external_status=ExternalCallStatus.NOT_CALLED,
        )
    )

    assert evaluator.state_count == 0


def test_concurrent_equal_timestamp_events_fire_once_then_deduplicate() -> None:
    evaluator = CbrKeyRateAlertPolicyEvaluatorV1(
        CbrKeyRateAlertPolicyV1(
            source_unavailable_threshold=2,
            cooldown_seconds=900,
        )
    )

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(
            executor.map(
                evaluator.evaluate,
                [_source_failure(NOW)] * 8,
            )
        )

    dispositions = [batch[0].disposition for batch in results]
    assert dispositions.count(CbrKeyRateAlertDisposition.FIRED) == 1
    assert dispositions.count(CbrKeyRateAlertDisposition.PENDING) == 1
    assert dispositions.count(CbrKeyRateAlertDisposition.SUPPRESSED_COOLDOWN) == 6


def test_evaluation_serialization_excludes_financial_and_sensitive_payload() -> None:
    evaluator = CbrKeyRateAlertPolicyEvaluatorV1(
        CbrKeyRateAlertPolicyV1(cache_unavailable_threshold=1)
    )
    evaluation = evaluator.evaluate(_cache_unavailable(NOW))[0]
    serialized = json.dumps(evaluation.model_dump(mode="json"), sort_keys=True)

    assert evaluation.contains_sensitive_payload is False
    assert evaluation.trading_methods is False
    assert "rate_percent" not in serialized
    assert "effective_date" not in serialized
    assert "requested_from" not in serialized
    assert "requested_to" not in serialized
    assert "account" not in serialized
    assert "xml" not in serialized.lower()
    assert "soap" not in serialized.lower()


def test_contract_and_evaluator_reject_invalid_inputs() -> None:
    with pytest.raises(ValidationError):
        CbrKeyRateAlertPolicyV1(source_unavailable_threshold=0)
    with pytest.raises(ValidationError):
        CbrKeyRateAlertEvaluationV1(
            evaluated_at=NOW,
            source_event_name=SOURCE_EVENT,
            disposition=CbrKeyRateAlertDisposition.SUPPRESSED_COOLDOWN,
            kind=CbrKeyRateAlertKind.SOURCE_UNAVAILABLE,
            severity=ObservabilitySeverity.ERROR,
            consecutive_occurrences=3,
            threshold=3,
            cooldown_remaining_seconds=0,
            error_code="CBR_KEY_RATE_NETWORK_ERROR",
        )
    with pytest.raises(CbrKeyRateAlertPolicyError):
        CbrKeyRateAlertPolicyEvaluatorV1().evaluate(  # type: ignore[arg-type]
            {"event": "unsafe"}
        )


def test_alert_policy_module_has_no_route_webhook_or_write_surface() -> None:
    import omni_cio.observability.cbr_key_rate_alert_policy_v1 as module

    assert not hasattr(module, "app")
    assert not hasattr(module, "router")
    assert not hasattr(module, "webhook")
    assert not hasattr(module, "requests")
    assert not hasattr(module, "create_order")
    assert not hasattr(module, "post_order")
