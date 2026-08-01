from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
import json
from threading import Lock
from types import MethodType
from typing import Any, cast

from pydantic import ValidationError
import pytest

from omni_cio.contracts.v1.expert_ra_alerting import (
    ExpertRaRatingActionsAlertDisposition,
    ExpertRaRatingActionsAlertEvaluationV1,
    ExpertRaRatingActionsAlertEvidenceV1,
    ExpertRaRatingActionsAlertPolicyV1,
)
from omni_cio.contracts.v1.expert_ra_ratings import (
    ExpertRaIssuerRatingActionV1,
    ExpertRaIssuerRatingActionsCacheResultV1,
    ExpertRaIssuerRatingActionsSnapshotV1,
)
from omni_cio.contracts.v1.market import MarketSourceV1, RatingAction, SourceAuthority
from omni_cio.contracts.v1.observability import ObservabilityEventV1
from omni_cio.contracts.v1.ratings import (
    CreditRatingCacheErrorCode,
    CreditRatingCacheStatus,
    CreditRatingOutlook,
    CreditRatingSourceErrorCode,
    CreditRatingSourceStatus,
)
from omni_cio.observability.expert_ra_rating_actions_alert_policy_v1 import (
    ExpertRaRatingActionsAlertPolicyEvaluatorV1,
)
from omni_cio.observability.expert_ra_rating_actions_operations_lifecycle_v1 import (
    ExpertRaRatingActionsOperationsLifecycleError,
    ExpertRaRatingActionsOperationsLifecycleV1,
)


NOW = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)
CORRELATION = "corr:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
SECOND_CORRELATION = "corr:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"


def _source(*, retrieved_at: datetime) -> MarketSourceV1:
    return MarketSourceV1(
        provider="Expert RA",
        authority=SourceAuthority.OFFICIAL,
        retrieved_at=retrieved_at,
        source_id="EXPERT_RA.home.rating_actions",
    )


def _available_snapshot(
    *,
    retrieved_at: datetime = NOW,
) -> ExpertRaIssuerRatingActionsSnapshotV1:
    source = _source(retrieved_at=retrieved_at)
    record = ExpertRaIssuerRatingActionV1(
        subject_name="АО «НЕ ДОЛЖНО ПОПАСТЬ В EVIDENCE»",
        rating="ruA",
        action=RatingAction.AFFIRMED,
        outlook=CreditRatingOutlook.STABLE,
        published_on=date(2026, 7, 31),
        release_url="https://raexpert.ru/releases/2026/jul31a",
        source=source,
    )
    return ExpertRaIssuerRatingActionsSnapshotV1(
        retrieved_at=retrieved_at,
        status=CreditRatingSourceStatus.AVAILABLE,
        source=source,
        records=(record,),
    )


def _unavailable_snapshot(
    *,
    retrieved_at: datetime,
) -> ExpertRaIssuerRatingActionsSnapshotV1:
    return ExpertRaIssuerRatingActionsSnapshotV1(
        retrieved_at=retrieved_at,
        status=CreditRatingSourceStatus.UNAVAILABLE,
        error_code=CreditRatingSourceErrorCode.NETWORK_ERROR,
    )


def _cache_result(
    status: str,
    *,
    checked_at: datetime,
) -> ExpertRaIssuerRatingActionsCacheResultV1:
    snapshot = _available_snapshot()
    if status == "fresh":
        return ExpertRaIssuerRatingActionsCacheResultV1(
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
        return ExpertRaIssuerRatingActionsCacheResultV1(
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
    return ExpertRaIssuerRatingActionsCacheResultV1(
        checked_at=checked_at,
        status=CreditRatingCacheStatus.UNAVAILABLE,
        refresh_attempted=True,
        source_error_code=CreditRatingSourceErrorCode.NETWORK_ERROR,
        cache_error_code=CreditRatingCacheErrorCode.EMPTY,
        display_records_allowed=False,
    )


def _evaluator(
    *,
    threshold: int = 2,
) -> ExpertRaRatingActionsAlertPolicyEvaluatorV1:
    return ExpertRaRatingActionsAlertPolicyEvaluatorV1(
        ExpertRaRatingActionsAlertPolicyV1(
            source_unavailable_threshold=threshold,
            cache_unavailable_threshold=threshold,
            stale_records_threshold=threshold,
            refresh_failure_threshold=threshold,
            cooldown_seconds=60,
            state_retention_seconds=600,
        )
    )


def test_pending_does_not_create_evidence_but_fired_and_recovered_do() -> None:
    lifecycle = ExpertRaRatingActionsOperationsLifecycleV1(evaluator=_evaluator())

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

    assert (
        pending.evaluations[0].disposition
        is ExpertRaRatingActionsAlertDisposition.PENDING
    )
    assert pending.evidence == ()
    assert fired.evidence[0].disposition is ExpertRaRatingActionsAlertDisposition.FIRED
    assert (
        recovered.evidence[0].disposition
        is ExpertRaRatingActionsAlertDisposition.RECOVERED
    )
    assert lifecycle.evidence_count == 2
    assert lifecycle.evidence(checked_at=NOW + timedelta(seconds=2)) == (
        fired.evidence + recovered.evidence
    )


def test_batch_discards_event_payload_and_correlation_identity() -> None:
    batch = ExpertRaRatingActionsOperationsLifecycleV1(
        evaluator=_evaluator(threshold=1)
    ).observe_source(
        _unavailable_snapshot(retrieved_at=NOW),
        correlation_id=CORRELATION,
    )

    assert batch.source_event_name == "market.expert_ra_rating_actions.source"
    assert not hasattr(batch, "event")
    assert not hasattr(batch.evidence[0], "correlation_id")
    serialized = json.dumps(
        {
            "source_event_name": batch.source_event_name,
            "evaluations": [item.model_dump(mode="json") for item in batch.evaluations],
            "evidence": [item.model_dump(mode="json") for item in batch.evidence],
        },
        sort_keys=True,
    )
    assert CORRELATION not in serialized
    assert '"correlation_id"' not in serialized


def test_evidence_contract_rejects_non_terminal_or_unbound_identity() -> None:
    common: dict[str, object] = {
        "evidence_id": "expert-ra-evidence:" + "a" * 64,
        "recorded_at": NOW,
        "source_event_name": "market.expert_ra_rating_actions.source",
        "disposition": ExpertRaRatingActionsAlertDisposition.FIRED,
        "kind": "source_unavailable",
        "severity": "error",
        "consecutive_occurrences": 2,
        "threshold": 2,
        "error_code": "EXPERT_RA_RATING_ACTIONS_SOURCE_UNAVAILABLE",
    }
    valid = ExpertRaRatingActionsAlertEvidenceV1(**common)
    assert valid.correlation_id_present is False

    for update in (
        {"evidence_id": "expert-ra-evidence:" + "q" * 64},
        {"evidence_id": "expert-ra-alert-evidence:" + "a" * 32},
        {"correlation_id": CORRELATION},
        {"correlation_id_present": True},
        {"source_event_name": "market.expert_ra_rating_actions.cache"},
        {"severity": "warning"},
        {"disposition": ExpertRaRatingActionsAlertDisposition.PENDING},
        {
            "disposition": ExpertRaRatingActionsAlertDisposition.RECOVERED,
            "error_code": "EXPERT_RA_RATING_ACTIONS_SOURCE_UNAVAILABLE",
        },
    ):
        with pytest.raises(ValidationError):
            ExpertRaRatingActionsAlertEvidenceV1(**(common | update))


def test_evidence_id_is_deterministic_and_correlation_independent() -> None:
    first = (
        ExpertRaRatingActionsOperationsLifecycleV1(evaluator=_evaluator(threshold=1))
        .observe_source(
            _unavailable_snapshot(retrieved_at=NOW),
            correlation_id=CORRELATION,
        )
        .evidence[0]
    )
    second = (
        ExpertRaRatingActionsOperationsLifecycleV1(evaluator=_evaluator(threshold=1))
        .observe_source(
            _unavailable_snapshot(retrieved_at=NOW),
            correlation_id=SECOND_CORRELATION,
        )
        .evidence[0]
    )

    assert first == second
    assert first.evidence_id.startswith("expert-ra-evidence:")
    token = first.evidence_id.removeprefix("expert-ra-evidence:")
    assert len(token) == 64
    assert set(token) <= set("abcdefghijklmnop")


def test_only_new_terminal_evidence_is_handed_to_sink() -> None:
    evaluator = _evaluator(threshold=1)

    def fixed_evaluate(
        _self: ExpertRaRatingActionsAlertPolicyEvaluatorV1,
        event: ObservabilityEventV1,
    ) -> tuple[ExpertRaRatingActionsAlertEvaluationV1, ...]:
        return (
            ExpertRaRatingActionsAlertEvaluationV1(
                evaluated_at=event.occurred_at,
                source_event_name=event.event_name,
                disposition=ExpertRaRatingActionsAlertDisposition.FIRED,
                kind="source_unavailable",
                severity="error",
                consecutive_occurrences=1,
                threshold=1,
                error_code=CreditRatingSourceErrorCode.NETWORK_ERROR.value,
            ),
        )

    setattr(evaluator, "evaluate", MethodType(fixed_evaluate, evaluator))
    handed_off: list[ExpertRaRatingActionsAlertEvidenceV1] = []
    lifecycle = ExpertRaRatingActionsOperationsLifecycleV1(
        evaluator=evaluator,
        evidence_sink=handed_off.append,
    )

    first = lifecycle.observe_source(
        _unavailable_snapshot(retrieved_at=NOW),
        correlation_id=CORRELATION,
    )
    repeated = lifecycle.observe_source(
        _unavailable_snapshot(retrieved_at=NOW),
        correlation_id=SECOND_CORRELATION,
    )

    assert first.evidence == repeated.evidence
    assert handed_off == [first.evidence[0]]
    assert lifecycle.evidence_count == 1


def test_sink_exceptions_are_reduced_to_count_without_exception_text() -> None:
    def broken_evidence_sink(_evidence: ExpertRaRatingActionsAlertEvidenceV1) -> None:
        raise RuntimeError("private evidence text")

    lifecycle = ExpertRaRatingActionsOperationsLifecycleV1(
        evaluator=_evaluator(threshold=1),
        evidence_sink=broken_evidence_sink,
    )
    batch = lifecycle.observe_cache(
        _cache_result("unavailable", checked_at=NOW),
        correlation_id=CORRELATION,
    )

    assert batch.sink_failure_count == 1
    serialized = json.dumps(
        {
            "source_event_name": batch.source_event_name,
            "evaluations": [item.model_dump(mode="json") for item in batch.evaluations],
            "evidence": [item.model_dump(mode="json") for item in batch.evidence],
            "sink_failure_count": batch.sink_failure_count,
        },
        sort_keys=True,
    )
    assert "private evidence text" not in serialized


def test_cache_fired_and_recovered_evidence_use_global_scope() -> None:
    lifecycle = ExpertRaRatingActionsOperationsLifecycleV1(
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

    assert fired.evidence[0].scope == "global_expert_ra_rating_actions_feed"
    assert recovered.evidence[0].scope == "global_expert_ra_rating_actions_feed"
    assert fired.evidence[0].issuer_identity_present is False
    assert fired.evidence[0].rating_values_present is False
    assert fired.evidence[0].action_identity_present is False
    assert fired.evidence[0].financial_values_present is False
    assert fired.evidence[0].external_notification_sent is False
    assert fired.evidence[0].broker_write_called is False


def test_retention_pruning_capacity_eviction_and_clear() -> None:
    lifecycle = ExpertRaRatingActionsOperationsLifecycleV1(
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
    assert len(retained) == 2
    assert first.evidence_id not in {item.evidence_id for item in retained}

    lifecycle.clear()
    assert lifecycle.evidence_count == 0
    assert lifecycle.evidence(checked_at=NOW + timedelta(seconds=62)) == ()


def test_invalid_configuration_and_timestamps_fail_closed() -> None:
    with pytest.raises(ExpertRaRatingActionsOperationsLifecycleError):
        ExpertRaRatingActionsOperationsLifecycleV1(evaluator=cast(Any, {}))
    unsafe_evaluator = _evaluator()
    setattr(unsafe_evaluator, "global_scope_only", False)
    with pytest.raises(ExpertRaRatingActionsOperationsLifecycleError):
        ExpertRaRatingActionsOperationsLifecycleV1(evaluator=unsafe_evaluator)
    with pytest.raises(ExpertRaRatingActionsOperationsLifecycleError):
        ExpertRaRatingActionsOperationsLifecycleV1(retention_seconds=True)
    with pytest.raises(ExpertRaRatingActionsOperationsLifecycleError):
        ExpertRaRatingActionsOperationsLifecycleV1(capacity=True)
    with pytest.raises(ExpertRaRatingActionsOperationsLifecycleError):
        ExpertRaRatingActionsOperationsLifecycleV1(retention_seconds=59)
    with pytest.raises(ExpertRaRatingActionsOperationsLifecycleError):
        ExpertRaRatingActionsOperationsLifecycleV1(capacity=0)
    with pytest.raises(ExpertRaRatingActionsOperationsLifecycleError):
        ExpertRaRatingActionsOperationsLifecycleV1(
            evidence_sink=object()  # type: ignore[arg-type]
        )
    lifecycle = ExpertRaRatingActionsOperationsLifecycleV1()
    with pytest.raises(ExpertRaRatingActionsOperationsLifecycleError):
        lifecycle.evidence(checked_at=cast(Any, 0))
    with pytest.raises(TypeError):
        ExpertRaRatingActionsOperationsLifecycleV1(
            event_sink=cast(Any, lambda _event: None)
        )  # type: ignore[call-arg]


def test_evidence_serialization_excludes_rating_and_issuer_payload() -> None:
    lifecycle = ExpertRaRatingActionsOperationsLifecycleV1(
        evaluator=_evaluator(threshold=1)
    )
    item = lifecycle.observe_cache(
        _cache_result("stale", checked_at=NOW),
        correlation_id=CORRELATION,
    ).evidence[0]
    serialized = json.dumps(item.model_dump(mode="json"), sort_keys=True)

    for forbidden in (
        "АО «НЕ ДОЛЖНО ПОПАСТЬ В EVIDENCE»",
        "ruA",
        '"stable"',
        '"affirmed"',
        "jul31a",
        "published_on",
        "release_url",
        "subject_name",
        '"rating":',
        '"outlook":',
        '"account":',
        "raw_html",
        "exception",
        CORRELATION,
    ):
        assert forbidden not in serialized
    assert item.contains_sensitive_payload is False
    assert item.trading_methods is False


def test_concurrent_identical_signals_produce_one_terminal_record() -> None:
    handed_off: list[ExpertRaRatingActionsAlertEvidenceV1] = []
    sink_lock = Lock()

    def evidence_sink(item: ExpertRaRatingActionsAlertEvidenceV1) -> None:
        with sink_lock:
            handed_off.append(item)

    lifecycle = ExpertRaRatingActionsOperationsLifecycleV1(
        evaluator=_evaluator(threshold=1),
        evidence_sink=evidence_sink,
        capacity=64,
    )
    correlations = [f"corr:{letter * 32}" for letter in "abcdefgh"]

    def observe(correlation: str):
        return lifecycle.observe_source(
            _unavailable_snapshot(retrieved_at=NOW),
            correlation_id=correlation,
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        batches = list(executor.map(observe, correlations))

    assert sum(len(batch.evidence) for batch in batches) == 1
    assert lifecycle.evidence_count == 1
    assert handed_off == list(lifecycle.evidence(checked_at=NOW))


def test_lifecycle_rejects_wrong_typed_source_and_cache_inputs() -> None:
    lifecycle = ExpertRaRatingActionsOperationsLifecycleV1()
    with pytest.raises(ExpertRaRatingActionsOperationsLifecycleError):
        lifecycle.observe_source(cast(Any, {}))
    with pytest.raises(ExpertRaRatingActionsOperationsLifecycleError):
        lifecycle.observe_cache(cast(Any, {}))


def test_module_has_no_route_notification_startup_or_write_surface() -> None:
    import omni_cio.observability.expert_ra_rating_actions_operations_lifecycle_v1 as module

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
