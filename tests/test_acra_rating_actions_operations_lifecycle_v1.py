from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
import json
from threading import Lock

from pydantic import ValidationError
import pytest

from omni_cio.contracts.v1.acra_alerting import (
    AcraRatingActionsAlertDisposition,
    AcraRatingActionsAlertEvidenceV1,
    AcraRatingActionsAlertPolicyV1,
)
from omni_cio.contracts.v1.market import MarketSourceV1, RatingAction, SourceAuthority
from omni_cio.contracts.v1.ratings import (
    AcraIssuerRatingActionsCacheResultV1,
    AcraIssuerRatingActionsSnapshotV1,
    AcraIssuerRatingActionV1,
    CreditRatingCacheErrorCode,
    CreditRatingCacheStatus,
    CreditRatingOutlook,
    CreditRatingSourceErrorCode,
    CreditRatingSourceStatus,
)
from omni_cio.observability.acra_rating_actions_alert_policy_v1 import (
    AcraRatingActionsAlertPolicyEvaluatorV1,
)
from omni_cio.observability.acra_rating_actions_operations_lifecycle_v1 import (
    AcraRatingActionsOperationsLifecycleError,
    AcraRatingActionsOperationsLifecycleV1,
)


NOW = datetime(2026, 7, 31, 5, 0, tzinfo=timezone.utc)
CORRELATION = "corr:acraoperationsevidence"


def _source(*, retrieved_at: datetime) -> MarketSourceV1:
    return MarketSourceV1(
        provider="ACRA",
        authority=SourceAuthority.OFFICIAL,
        retrieved_at=retrieved_at,
        source_id="ACRA.press_releases.issuer_rating_actions",
    )


def _available_snapshot(
    *,
    retrieved_at: datetime = NOW,
) -> AcraIssuerRatingActionsSnapshotV1:
    source = _source(retrieved_at=retrieved_at)
    record = AcraIssuerRatingActionV1(
        subject_name="SAFE ISSUER",
        rating="A(RU)",
        action=RatingAction.AFFIRMED,
        outlook=CreditRatingOutlook.STABLE,
        published_on=date(2026, 7, 30),
        release_url="https://www.acra-ratings.ru/press-releases/100/?lang=en",
        source=source,
    )
    return AcraIssuerRatingActionsSnapshotV1(
        retrieved_at=retrieved_at,
        status=CreditRatingSourceStatus.AVAILABLE,
        source=source,
        records=(record,),
    )


def _unavailable_snapshot(
    *,
    retrieved_at: datetime,
) -> AcraIssuerRatingActionsSnapshotV1:
    return AcraIssuerRatingActionsSnapshotV1(
        retrieved_at=retrieved_at,
        status=CreditRatingSourceStatus.UNAVAILABLE,
        error_code=CreditRatingSourceErrorCode.NETWORK_ERROR,
    )


def _cache_result(
    status: str,
    *,
    checked_at: datetime,
) -> AcraIssuerRatingActionsCacheResultV1:
    snapshot = _available_snapshot()
    if status == "fresh":
        return AcraIssuerRatingActionsCacheResultV1(
            checked_at=checked_at,
            status=CreditRatingCacheStatus.FRESH,
            snapshot=snapshot,
            age_seconds=max(0, int((checked_at - NOW).total_seconds())),
            fresh_until=checked_at + timedelta(seconds=30),
            stale_until=checked_at + timedelta(minutes=30),
            served_from_cache=True,
            display_records_allowed=True,
        )
    if status == "stale":
        return AcraIssuerRatingActionsCacheResultV1(
            checked_at=checked_at,
            status=CreditRatingCacheStatus.STALE,
            snapshot=snapshot,
            age_seconds=max(0, int((checked_at - NOW).total_seconds())),
            fresh_until=checked_at - timedelta(seconds=1),
            stale_until=checked_at + timedelta(minutes=30),
            served_from_cache=True,
            stale_available=True,
            stale_value_exposed=True,
            refresh_attempted=True,
            source_error_code=CreditRatingSourceErrorCode.NETWORK_ERROR,
            cache_error_code=CreditRatingCacheErrorCode.REFRESH_FAILED,
            display_records_allowed=True,
        )
    return AcraIssuerRatingActionsCacheResultV1(
        checked_at=checked_at,
        status=CreditRatingCacheStatus.UNAVAILABLE,
        refresh_attempted=True,
        source_error_code=CreditRatingSourceErrorCode.NETWORK_ERROR,
        cache_error_code=CreditRatingCacheErrorCode.EMPTY,
        display_records_allowed=False,
    )


def _evaluator(*, threshold: int = 2) -> AcraRatingActionsAlertPolicyEvaluatorV1:
    return AcraRatingActionsAlertPolicyEvaluatorV1(
        AcraRatingActionsAlertPolicyV1(
            source_unavailable_threshold=threshold,
            cache_unavailable_threshold=threshold,
            stale_records_threshold=threshold,
            refresh_failure_threshold=threshold,
            cooldown_seconds=60,
            state_retention_seconds=600,
        )
    )


def test_pending_does_not_create_evidence_but_fired_and_recovered_do() -> None:
    lifecycle = AcraRatingActionsOperationsLifecycleV1(evaluator=_evaluator())

    pending = lifecycle.observe_source(
        _unavailable_snapshot(retrieved_at=NOW),
        correlation_id=CORRELATION,
    )
    fired = lifecycle.observe_source(
        _unavailable_snapshot(retrieved_at=NOW + timedelta(seconds=1)),
        correlation_id=CORRELATION,
    )
    recovered = lifecycle.observe_source(
        _available_snapshot(retrieved_at=NOW + timedelta(seconds=2)),
        correlation_id=CORRELATION,
    )

    assert pending.evaluations[0].disposition is AcraRatingActionsAlertDisposition.PENDING
    assert pending.evidence == ()
    assert fired.evidence[0].disposition is AcraRatingActionsAlertDisposition.FIRED
    assert recovered.evidence[0].disposition is AcraRatingActionsAlertDisposition.RECOVERED
    assert lifecycle.evidence_count == 2
    assert lifecycle.evidence(
        checked_at=NOW + timedelta(seconds=2)
    ) == fired.evidence + recovered.evidence


def test_evidence_contract_rejects_non_terminal_dispositions() -> None:
    with pytest.raises(ValidationError):
        AcraRatingActionsAlertEvidenceV1(
            evidence_id="acra-alert-evidence:abcdefgh",
            recorded_at=NOW,
            correlation_id=CORRELATION,
            source_event_name="market.acra_rating_actions.source",
            disposition=AcraRatingActionsAlertDisposition.PENDING,
            kind="source_unavailable",
            severity="error",
            consecutive_occurrences=1,
            threshold=2,
            error_code="ACRA_RATING_ACTIONS_SOURCE_UNAVAILABLE",
        )


def test_event_sink_runs_before_evidence_sink_under_one_call() -> None:
    order: list[str] = []
    lifecycle = AcraRatingActionsOperationsLifecycleV1(
        evaluator=_evaluator(threshold=1),
        event_sink=lambda event: order.append(f"event:{event.event_name}"),
        evidence_sink=lambda item: order.append(f"evidence:{item.disposition.value}"),
    )

    batch = lifecycle.observe_source(
        _unavailable_snapshot(retrieved_at=NOW),
        correlation_id=CORRELATION,
    )

    assert batch.sink_failure_count == 0
    assert order == [
        "event:market.acra_rating_actions.source",
        "evidence:fired",
    ]


def test_sink_exceptions_are_reduced_to_count_without_exception_text() -> None:
    def broken_event_sink(_event) -> None:
        raise RuntimeError("private upstream text")

    def broken_evidence_sink(_evidence) -> None:
        raise RuntimeError("private evidence text")

    lifecycle = AcraRatingActionsOperationsLifecycleV1(
        evaluator=_evaluator(threshold=1),
        event_sink=broken_event_sink,
        evidence_sink=broken_evidence_sink,
    )
    batch = lifecycle.observe_cache(
        _cache_result("unavailable", checked_at=NOW),
        correlation_id=CORRELATION,
    )

    assert batch.sink_failure_count == 2
    serialized = json.dumps(
        {
            "event": batch.event.model_dump(mode="json"),
            "evaluations": [item.model_dump(mode="json") for item in batch.evaluations],
            "evidence": [item.model_dump(mode="json") for item in batch.evidence],
            "sink_failure_count": batch.sink_failure_count,
        },
        sort_keys=True,
    )
    assert "private upstream text" not in serialized
    assert "private evidence text" not in serialized


def test_cache_fired_and_recovered_evidence_use_global_scope() -> None:
    lifecycle = AcraRatingActionsOperationsLifecycleV1(
        evaluator=_evaluator(threshold=1)
    )
    fired = lifecycle.observe_cache(
        _cache_result("stale", checked_at=NOW),
        correlation_id=CORRELATION,
    )
    recovered = lifecycle.observe_cache(
        _cache_result("fresh", checked_at=NOW + timedelta(seconds=1)),
        correlation_id=CORRELATION,
    )

    assert fired.evidence[0].scope == "global_acra_rating_actions_feed"
    assert recovered.evidence[0].scope == "global_acra_rating_actions_feed"
    assert fired.evidence[0].issuer_identity_present is False
    assert fired.evidence[0].rating_values_present is False
    assert fired.evidence[0].financial_values_present is False
    assert fired.evidence[0].external_notification_sent is False


def test_retention_pruning_capacity_eviction_and_clear() -> None:
    lifecycle = AcraRatingActionsOperationsLifecycleV1(
        evaluator=_evaluator(threshold=1),
        retention_seconds=60,
        capacity=2,
    )
    first = lifecycle.observe_source(
        _unavailable_snapshot(retrieved_at=NOW),
        correlation_id=CORRELATION,
    ).evidence[0]
    lifecycle.observe_source(
        _available_snapshot(retrieved_at=NOW + timedelta(seconds=1)),
        correlation_id=CORRELATION,
    )
    lifecycle.observe_source(
        _unavailable_snapshot(retrieved_at=NOW + timedelta(seconds=61)),
        correlation_id=CORRELATION,
    )

    retained = lifecycle.evidence(checked_at=NOW + timedelta(seconds=61))
    assert len(retained) <= 2
    assert first.evidence_id not in {item.evidence_id for item in retained}

    lifecycle.clear()
    assert lifecycle.evidence_count == 0
    assert lifecycle.evidence(checked_at=NOW + timedelta(seconds=62)) == ()


def test_invalid_configuration_fails_closed() -> None:
    with pytest.raises(AcraRatingActionsOperationsLifecycleError):
        AcraRatingActionsOperationsLifecycleV1(retention_seconds=59)
    with pytest.raises(AcraRatingActionsOperationsLifecycleError):
        AcraRatingActionsOperationsLifecycleV1(capacity=0)
    with pytest.raises(AcraRatingActionsOperationsLifecycleError):
        AcraRatingActionsOperationsLifecycleV1(
            event_sink="not-callable"  # type: ignore[arg-type]
        )
    with pytest.raises(AcraRatingActionsOperationsLifecycleError):
        AcraRatingActionsOperationsLifecycleV1(
            evidence_sink=object()  # type: ignore[arg-type]
        )


def test_evidence_serialization_excludes_rating_and_issuer_payload() -> None:
    lifecycle = AcraRatingActionsOperationsLifecycleV1(
        evaluator=_evaluator(threshold=1)
    )
    item = lifecycle.observe_cache(
        _cache_result("stale", checked_at=NOW),
        correlation_id=CORRELATION,
    ).evidence[0]
    serialized = json.dumps(item.model_dump(mode="json"), sort_keys=True)

    for forbidden in (
        "SAFE ISSUER",
        "A(RU)",
        '"stable"',
        '"affirmed"',
        "press-releases/100",
        "published_on",
        "release_url",
        "subject_name",
        '"rating":',
        '"outlook":',
        '"account":',
        "raw_html",
        "exception",
    ):
        assert forbidden not in serialized
    assert item.contains_sensitive_payload is False
    assert item.trading_methods is False


def test_concurrent_calls_preserve_event_then_evidence_pair_order() -> None:
    order: list[str] = []
    order_lock = Lock()

    def event_sink(event) -> None:
        with order_lock:
            order.append(f"event:{event.correlation_id}")

    def evidence_sink(evidence) -> None:
        with order_lock:
            order.append(f"evidence:{evidence.correlation_id}")

    lifecycle = AcraRatingActionsOperationsLifecycleV1(
        evaluator=_evaluator(threshold=1),
        event_sink=event_sink,
        evidence_sink=evidence_sink,
        capacity=64,
    )
    correlations = [f"corr:acraoperation{letter}" for letter in "abcdefgh"]

    def observe(correlation: str) -> None:
        lifecycle.observe_source(
            _unavailable_snapshot(retrieved_at=NOW),
            correlation_id=correlation,
        )
        lifecycle.observe_source(
            _available_snapshot(retrieved_at=NOW),
            correlation_id=correlation,
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(observe, correlations))

    for index, entry in enumerate(order):
        if entry.startswith("evidence:"):
            correlation = entry.removeprefix("evidence:")
            assert index > 0
            assert order[index - 1] == f"event:{correlation}"


def test_module_has_no_route_notification_startup_or_write_surface() -> None:
    import omni_cio.observability.acra_rating_actions_operations_lifecycle_v1 as module

    for forbidden in (
        "app",
        "router",
        "startup",
        "webhook",
        "send_email",
        "telegram",
        "pager",
        "create_order",
        "post_order",
        "cancel_order",
    ):
        assert not hasattr(module, forbidden)
