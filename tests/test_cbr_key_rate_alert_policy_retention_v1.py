from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from omni_cio.contracts.v1.alerting import (
    CbrKeyRateAlertDisposition,
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
    CbrKeyRateAlertPolicyEvaluatorV1,
)


NOW = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)


def _source_failure(at: datetime) -> ObservabilityEventV1:
    return ObservabilityEventV1(
        occurred_at=at,
        event_name="macro.cbr_key_rate.source",
        severity=ObservabilitySeverity.ERROR,
        component="macro.cbr_key_rate",
        outcome=ObservabilityOutcome.FAILURE,
        correlation_id="corr:cbralertretain",
        duration_ms=Decimal("1.0"),
        external_call=ExternalCallTelemetryV1(
            provider="Bank of Russia DailyInfo",
            operation="KeyRateXML",
            status=ExternalCallStatus.FAILURE,
            latency_ms=Decimal("1.0"),
            freshness=FreshnessTelemetry.UNKNOWN,
        ),
        error_code="CBR_KEY_RATE_NETWORK_ERROR",
    )


def test_pending_state_expires_at_configured_retention() -> None:
    evaluator = CbrKeyRateAlertPolicyEvaluatorV1(
        CbrKeyRateAlertPolicyV1(
            source_unavailable_threshold=3,
            cooldown_seconds=900,
            state_retention_seconds=60,
        )
    )
    first = evaluator.evaluate(_source_failure(NOW))[0]
    restarted = evaluator.evaluate(_source_failure(NOW + timedelta(seconds=61)))[0]

    assert first.disposition is CbrKeyRateAlertDisposition.PENDING
    assert restarted.disposition is CbrKeyRateAlertDisposition.PENDING
    assert restarted.consecutive_occurrences == 1


def test_active_state_survives_short_retention_until_cooldown_ends() -> None:
    evaluator = CbrKeyRateAlertPolicyEvaluatorV1(
        CbrKeyRateAlertPolicyV1(
            source_unavailable_threshold=1,
            cooldown_seconds=900,
            state_retention_seconds=60,
        )
    )
    fired = evaluator.evaluate(_source_failure(NOW))[0]
    suppressed = evaluator.evaluate(_source_failure(NOW + timedelta(seconds=61)))[0]

    assert fired.disposition is CbrKeyRateAlertDisposition.FIRED
    assert suppressed.disposition is CbrKeyRateAlertDisposition.SUPPRESSED_COOLDOWN
    assert suppressed.cooldown_remaining_seconds == 839
