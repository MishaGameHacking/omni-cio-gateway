from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json

import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1.alerting import (
    CbrKeyRateAlertDisposition,
    CbrKeyRateAlertEvidenceV1,
    CbrKeyRateAlertPolicyV1,
)
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
from omni_cio.observability.cbr_key_rate_alert_policy_v1 import (
    CbrKeyRateAlertPolicyEvaluatorV1,
)
from omni_cio.observability.cbr_key_rate_operations_lifecycle_v1 import (
    CbrKeyRateOperationsLifecycleError,
    CbrKeyRateOperationsLifecycleV1,
)


NOW = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
DATE_FROM = date(2025, 7, 30)
DATE_TO = date(2026, 7, 30)
CORRELATION_ID = "corr:cbroperationslife"


def _available_snapshot(at: datetime = NOW) -> CbrKeyRateSnapshotV1:
    row = KeyRateObservationV1(
        effective_date=date(2026, 7, 23),
        rate_percent=Decimal("18.00"),
    )
    return CbrKeyRateSnapshotV1(
        requested_from=DATE_FROM,
        requested_to=DATE_TO,
        retrieved_at=at,
        status=MacroDataStatus.AVAILABLE,
        source=MarketSourceV1(
            provider="Bank of Russia DailyInfo",
            authority=SourceAuthority.OFFICIAL,
            retrieved_at=at,
            source_id="DailyInfo.KeyRateXML",
        ),
        observations=(row,),
        current=row,
    )


def _unavailable_snapshot(at: datetime) -> CbrKeyRateSnapshotV1:
    return CbrKeyRateSnapshotV1(
        requested_from=DATE_FROM,
        requested_to=DATE_TO,
        retrieved_at=at,
        status=MacroDataStatus.UNAVAILABLE,
        error_code=MacroDataErrorCode.NETWORK_ERROR,
    )


def _stale_result(at: datetime) -> CbrKeyRateCacheResultV1:
    snapshot = _available_snapshot(NOW)
    return CbrKeyRateCacheResultV1(
        requested_from=DATE_FROM,
        requested_to=DATE_TO,
        checked_at=at,
        status=MacroCacheStatus.STALE,
        snapshot=snapshot,
        age_seconds=int((at - snapshot.retrieved_at).total_seconds()),
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


def _source_lifecycle(
    *,
    threshold: int = 2,
    event_sink=None,
    evidence_sink=None,
    retention_seconds: int = 86_400,
    capacity: int = 64,
) -> CbrKeyRateOperationsLifecycleV1:
    evaluator = CbrKeyRateAlertPolicyEvaluatorV1(
        CbrKeyRateAlertPolicyV1(
            source_unavailable_threshold=threshold,
            stale_value_threshold=1,
            cooldown_seconds=900,
        )
    )
    return CbrKeyRateOperationsLifecycleV1(
        evaluator=evaluator,
        event_sink=event_sink,
        evidence_sink=evidence_sink,
        retention_seconds=retention_seconds,
        capacity=capacity,
    )


def test_source_event_evaluation_and_evidence_order_is_deterministic() -> None:
    sink_order: list[tuple[str, str]] = []
    lifecycle = _source_lifecycle(
        event_sink=lambda event: sink_order.append(("event", event.event_name)),
        evidence_sink=lambda item: sink_order.append(
            ("evidence", item.disposition.value)
        ),
    )

    pending = lifecycle.observe_source(
        _unavailable_snapshot(NOW),
        correlation_id=CORRELATION_ID,
    )
    fired = lifecycle.observe_source(
        _unavailable_snapshot(NOW + timedelta(minutes=1)),
        correlation_id=CORRELATION_ID,
    )

    assert pending.evidence == ()
    assert pending.evaluations[0].disposition is CbrKeyRateAlertDisposition.PENDING
    assert fired.evaluations[0].disposition is CbrKeyRateAlertDisposition.FIRED
    assert len(fired.evidence) == 1
    assert fired.evidence[0].disposition is CbrKeyRateAlertDisposition.FIRED
    assert sink_order[-2:] == [
        ("event", "macro.cbr_key_rate.source"),
        ("evidence", "fired"),
    ]
    assert lifecycle.evidence_count == 1


def test_cooldown_suppression_is_not_persisted_but_recovery_is() -> None:
    lifecycle = _source_lifecycle(threshold=1)

    fired = lifecycle.observe_source(
        _unavailable_snapshot(NOW),
        correlation_id=CORRELATION_ID,
    )
    suppressed = lifecycle.observe_source(
        _unavailable_snapshot(NOW + timedelta(minutes=1)),
        correlation_id=CORRELATION_ID,
    )
    recovered = lifecycle.observe_source(
        _available_snapshot(NOW + timedelta(minutes=2)),
        correlation_id=CORRELATION_ID,
    )

    assert len(fired.evidence) == 1
    assert suppressed.evidence == ()
    assert suppressed.evaluations[0].disposition is (
        CbrKeyRateAlertDisposition.SUPPRESSED_COOLDOWN
    )
    assert len(recovered.evidence) == 1
    assert recovered.evidence[0].disposition is CbrKeyRateAlertDisposition.RECOVERED
    assert [item.disposition for item in lifecycle.evidence()] == [
        CbrKeyRateAlertDisposition.FIRED,
        CbrKeyRateAlertDisposition.RECOVERED,
    ]


def test_cache_result_flows_through_safe_event_and_alert_policy() -> None:
    lifecycle = _source_lifecycle()

    batch = lifecycle.observe_cache(
        _stale_result(NOW + timedelta(hours=2)),
        duration_ms=Decimal("4.5"),
        correlation_id=CORRELATION_ID,
    )

    assert batch.event.event_name == "macro.cbr_key_rate.cache"
    assert batch.event.duration_ms == Decimal("4.5")
    assert batch.evaluations[0].disposition is CbrKeyRateAlertDisposition.FIRED
    assert batch.evidence[0].kind.value == "stale_value_exposed"


def test_evidence_retention_capacity_and_clear_are_bounded() -> None:
    lifecycle = _source_lifecycle(
        threshold=1,
        retention_seconds=60,
        capacity=1,
    )
    lifecycle.observe_source(
        _unavailable_snapshot(NOW),
        correlation_id=CORRELATION_ID,
    )
    lifecycle.observe_source(
        _available_snapshot(NOW + timedelta(seconds=1)),
        correlation_id=CORRELATION_ID,
    )

    retained = lifecycle.evidence(checked_at=NOW + timedelta(seconds=1))
    assert len(retained) == 1
    assert retained[0].disposition is CbrKeyRateAlertDisposition.RECOVERED
    assert lifecycle.evidence(checked_at=NOW + timedelta(seconds=62)) == ()

    lifecycle.observe_source(
        _unavailable_snapshot(NOW + timedelta(seconds=63)),
        correlation_id=CORRELATION_ID,
    )
    lifecycle.clear()
    assert lifecycle.evidence_count == 0


def test_sink_failures_are_redacted_and_do_not_break_evidence() -> None:
    def fail_event(_event) -> None:
        raise RuntimeError("upstream payload must not escape")

    def fail_evidence(_evidence) -> None:
        raise RuntimeError("account 123456 must not escape")

    lifecycle = _source_lifecycle(
        threshold=1,
        event_sink=fail_event,
        evidence_sink=fail_evidence,
    )
    batch = lifecycle.observe_source(
        _unavailable_snapshot(NOW),
        correlation_id=CORRELATION_ID,
    )

    assert batch.sink_failure_count == 2
    assert len(batch.evidence) == 1
    serialized = json.dumps(batch.evidence[0].model_dump(mode="json"), sort_keys=True)
    assert "upstream payload" not in serialized
    assert "123456" not in serialized


def test_concurrent_events_create_one_fired_evidence_inside_cooldown() -> None:
    lifecycle = _source_lifecycle(threshold=2)

    with ThreadPoolExecutor(max_workers=8) as executor:
        batches = list(
            executor.map(
                lambda _: lifecycle.observe_source(
                    _unavailable_snapshot(NOW),
                    correlation_id=CORRELATION_ID,
                ),
                range(8),
            )
        )

    dispositions = [batch.evaluations[0].disposition for batch in batches]
    assert dispositions.count(CbrKeyRateAlertDisposition.PENDING) == 1
    assert dispositions.count(CbrKeyRateAlertDisposition.FIRED) == 1
    assert dispositions.count(CbrKeyRateAlertDisposition.SUPPRESSED_COOLDOWN) == 6
    assert sum(len(batch.evidence) for batch in batches) == 1
    assert lifecycle.evidence_count == 1


def test_evidence_contract_rejects_non_evidence_dispositions() -> None:
    with pytest.raises(ValidationError):
        CbrKeyRateAlertEvidenceV1(
            evidence_id="evidence:abcdefgh",
            recorded_at=NOW,
            correlation_id=CORRELATION_ID,
            source_event_name="macro.cbr_key_rate.source",
            disposition=CbrKeyRateAlertDisposition.PENDING,
            kind="source_unavailable",
            severity="error",
            consecutive_occurrences=1,
            threshold=2,
        )


def test_lifecycle_rejects_invalid_configuration_and_timestamp() -> None:
    with pytest.raises(CbrKeyRateOperationsLifecycleError):
        CbrKeyRateOperationsLifecycleV1(retention_seconds=59)
    with pytest.raises(CbrKeyRateOperationsLifecycleError):
        CbrKeyRateOperationsLifecycleV1(capacity=0)
    with pytest.raises(CbrKeyRateOperationsLifecycleError):
        CbrKeyRateOperationsLifecycleV1(event_sink=object())  # type: ignore[arg-type]

    lifecycle = _source_lifecycle()
    with pytest.raises(CbrKeyRateOperationsLifecycleError):
        lifecycle.evidence(checked_at=datetime(2026, 7, 30, 12, 0))


def test_evidence_serialization_has_no_financial_or_sensitive_payload() -> None:
    lifecycle = _source_lifecycle(threshold=1)
    evidence = lifecycle.observe_source(
        _unavailable_snapshot(NOW),
        correlation_id=CORRELATION_ID,
    ).evidence[0]
    serialized = json.dumps(evidence.model_dump(mode="json"), sort_keys=True)

    assert evidence.contains_sensitive_payload is False
    assert evidence.trading_methods is False
    assert "rate_percent" not in serialized
    assert "18.00" not in serialized
    assert "effective_date" not in serialized
    assert "requested_from" not in serialized
    assert "requested_to" not in serialized
    assert "account" not in serialized
    assert "xml" not in serialized.lower()
    assert "soap" not in serialized.lower()


def test_operations_lifecycle_has_no_route_notification_or_write_surface() -> None:
    import omni_cio.observability.cbr_key_rate_operations_lifecycle_v1 as module

    assert not hasattr(module, "app")
    assert not hasattr(module, "router")
    assert not hasattr(module, "webhook")
    assert not hasattr(module, "requests")
    assert not hasattr(module, "send_email")
    assert not hasattr(module, "create_order")
    assert not hasattr(module, "post_order")
