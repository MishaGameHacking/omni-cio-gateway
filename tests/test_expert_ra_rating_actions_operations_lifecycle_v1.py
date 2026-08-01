from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
import json
from typing import Any, cast

from pydantic import ValidationError
import pytest

from omni_cio.contracts.v1.expert_ra_alerting import (
    ExpertRaRatingActionsAlertDisposition,
    ExpertRaRatingActionsAlertEvidenceV1,
    ExpertRaRatingActionsAlertPolicyV1,
)
from omni_cio.contracts.v1.expert_ra_ratings import (
    ExpertRaIssuerRatingActionsCacheResultV1,
    ExpertRaIssuerRatingActionsSnapshotV1,
    ExpertRaIssuerRatingActionV1,
)
from omni_cio.contracts.v1.market import MarketSourceV1, RatingAction, SourceAuthority
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
from omni_cio.observability.expert_ra_rating_actions_events_v1 import (
    build_expert_ra_rating_actions_source_event,
)
from omni_cio.observability.expert_ra_rating_actions_operations_lifecycle_v1 import (
    ExpertRaRatingActionsOperationsLifecycleError,
    ExpertRaRatingActionsOperationsLifecycleV1,
)


NOW = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)
CORRELATION = "corr:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


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


def _evaluator(*, threshold: int = 2) -> ExpertRaRatingActionsAlertPolicyEvaluatorV1:
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

    assert pending.evaluations[0].disposition is (
        ExpertRaRatingActionsAlertDisposition.PENDING
    )
    assert pending.evidence == ()
    assert fired.evidence[0].disposition is (
        ExpertRaRatingActionsAlertDisposition.FIRED
    )
    assert recovered.evidence[0].disposition is (
        ExpertRaRatingActionsAlertDisposition.RECOVERED
    )
    assert fired.source_event_name == "market.expert_ra_rating_actions.source"
    assert lifecycle.evidence_count == 2
    assert lifecycle.evidence(
        checked_at=NOW + timedelta(seconds=2)
    ) == fired.evidence + recovered.evidence


def test_evidence_contract_rejects_non_terminal_and_correlation_fields() -> None:
    common = {
        "evidence_id": "expert-ra-evidence:" + "a" * 64,
        "recorded_at": NOW,
        "source_event_name": "market.expert_ra_rating_actions.source",
        "kind": "source_unavailable",
        "severity": "error",
        "consecutive_occurrences": 2,
        "threshold": 2,
    }
    with pytest.raises(ValidationError):
        ExpertRaRatingActionsAlertEvidenceV1(
            **common,
            disposition=ExpertRaRatingActionsAlertDisposition.PENDING,
            error_code="EXPERT_RA_RATING_ACTIONS_SOURCE_UNAVAILABLE",
        )
    with pytest.raises(ValidationError):
        ExpertRaRatingActionsAlertEvidenceV1(
            **common,
            disposition=ExpertRaRatingActionsAlertDisposition.FIRED,
            error_code=None,
        )
    with pytest.raises(ValidationError):
        ExpertRaRatingActionsAlertEvidenceV1(
            **common,
            disposition=ExpertRaRatingActionsAlertDisposition.RECOVERED,
            error_code="EXPERT_RA_RATING_ACTIONS_SOURCE_UNAVAILABLE",
        )
    with pytest.raises(ValidationError):
        ExpertRaRatingActionsAlertEvidenceV1(
            **common,
            disposition=ExpertRaRatingActionsAlertDisposition.FIRED,
            error_code="EXPERT_RA_RATING_ACTIONS_SOURCE_UNAVAILABLE",
            correlation_id=CORRELATION,
        )


def test_evidence_id_is_deterministic_across_independent_lifecycles() -> None:
    first = ExpertRaRatingActionsOperationsLifecycleV1(
        evaluator=_evaluator(threshold=1)
    )
    second = ExpertRaRatingActionsOperationsLifecycleV1(
        evaluator=_evaluator(threshold=1)
    )

    first_item = first.observe_source(
        _unavailable_snapshot(retrieved_at=NOW),
        correlation_id="corr:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    ).evidence[0]
    second_item = second.observe_source(
        _unavailable_snapshot(retrieved_at=NOW),
        correlation_id="corr:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    ).evidence[0]

    assert first_item == second_item
    assert first_item.evidence_id.startswith("expert-ra-evidence:")
    token = first_item.evidence_id.removeprefix("expert-ra-evidence:")
    assert len(token) == 64
    assert all(character in "abcdefghijklmnop" for character in token)


def test_evidence_sink_runs_after_store_and_does_not_receive_event() -> None:
    observed: list[tuple[str, int]] = []
    lifecycle: ExpertRaRatingActionsOperationsLifecycleV1

    def sink(item: ExpertRaRatingActionsAlertEvidenceV1) -> None:
        observed.append((item.evidence_id, lifecycle.evidence_count))

    lifecycle = ExpertRaRatingActionsOperationsLifecycleV1(
        evaluator=_evaluator(threshold=1),
        evidence_sink=sink,
    )
    batch = lifecycle.observe_source(
        _unavailable_snapshot(retrieved_at=NOW),
        correlation_id=CORRELATION,
    )

    assert batch.sink_failure_count == 0
    assert observed == [(batch.evidence[0].evidence_id, 1)]
    assert not hasattr(batch, "event")


def test_sink_exception_is_reduced_to_count_without_exception_text() -> None:
    def broken_sink(_evidence: ExpertRaRatingActionsAlertEvidenceV1) -> None:
        raise RuntimeError("private evidence text")

    lifecycle = ExpertRaRatingActionsOperationsLifecycleV1(
        evaluator=_evaluator(threshold=1),
        evidence_sink=broken_sink,
    )
    batch = lifecycle.observe_cache(
        _cache_result("unavailable", checked_at=NOW),
        correlation_id=CORRELATION,
    )

    assert batch.sink_failure_count == 1
    serialized = json.dumps(
        {
            "source_event_name": batch.source_event_name,
            "evaluations": [
                item.model_dump(mode="json") for item in batch.evaluations
            ],
            "evidence": [item.model_dump(mode="json") for item in batch.evidence],
            "sink_failure_count": batch.sink_failure_count,
        },
        sort_keys=True,
    )
    assert "private evidence text" not in serialized


def test_evidence_serialization_excludes_correlation_and_rating_action_payload() -> None:
    lifecycle = ExpertRaRatingActionsOperationsLifecycleV1(
        evaluator=_evaluator(threshold=1)
    )
    item = lifecycle.observe_cache(
        _cache_result("stale", checked_at=NOW),
        correlation_id=CORRELATION,
    ).evidence[0]
    serialized = json.dumps(
        item.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
    )

    for forbidden in (
        CORRELATION,
        "correlation_id",
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
    ):
        assert forbidden not in serialized
    assert item.correlation_id_present is False
    assert item.issuer_identity_present is False
    assert item.rating_values_present is False
    assert item.action_identity_present is False
    assert item.release_identity_present is False
    assert item.publication_date_present is False
    assert item.financial_values_present is False
    assert item.raw_source_payload_present is False
    assert item.trading_methods is False


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
    assert fired.evidence[0].error_code is not None
    assert recovered.evidence[0].error_code is None


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
    assert len(retained) <= 2
    assert first.evidence_id not in {item.evidence_id for item in retained}

    lifecycle.clear()
    assert lifecycle.evidence_count == 0
    assert lifecycle.evidence(checked_at=NOW + timedelta(seconds=62)) == ()


def test_invalid_configuration_and_input_types_fail_closed() -> None:
    class EvaluatorSubclass(ExpertRaRatingActionsAlertPolicyEvaluatorV1):
        pass

    with pytest.raises(ExpertRaRatingActionsOperationsLifecycleError):
        ExpertRaRatingActionsOperationsLifecycleV1(evaluator=cast(Any, {}))
    with pytest.raises(ExpertRaRatingActionsOperationsLifecycleError):
        ExpertRaRatingActionsOperationsLifecycleV1(
            evaluator=EvaluatorSubclass()
        )
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
        lifecycle.observe_source(cast(Any, {}))
    with pytest.raises(ExpertRaRatingActionsOperationsLifecycleError):
        lifecycle.observe_cache(cast(Any, {}))
    with pytest.raises(ExpertRaRatingActionsOperationsLifecycleError):
        lifecycle.evidence(checked_at=datetime(2026, 8, 1, 9, 0))


def test_terminal_evaluation_binding_is_revalidated() -> None:
    lifecycle = ExpertRaRatingActionsOperationsLifecycleV1(
        evaluator=_evaluator(threshold=1)
    )
    event = build_expert_ra_rating_actions_source_event(
        _unavailable_snapshot(retrieved_at=NOW),
        occurred_at=NOW,
        correlation_id=CORRELATION,
    )
    evaluation = lifecycle._evaluator.evaluate(event)[0]
    forged_time = evaluation.model_copy(
        update={"evaluated_at": NOW + timedelta(seconds=1)}
    )
    forged_error = evaluation.model_copy(update={"error_code": "FORGED_ERROR"})

    with pytest.raises(ExpertRaRatingActionsOperationsLifecycleError):
        lifecycle._validated_terminal_evaluation(event, forged_time)
    with pytest.raises(ExpertRaRatingActionsOperationsLifecycleError):
        lifecycle._validated_terminal_evaluation(event, forged_error)


def test_recording_same_terminal_evaluation_is_idempotent() -> None:
    lifecycle = ExpertRaRatingActionsOperationsLifecycleV1(
        evaluator=_evaluator(threshold=1)
    )
    event = build_expert_ra_rating_actions_source_event(
        _unavailable_snapshot(retrieved_at=NOW),
        occurred_at=NOW,
        correlation_id=CORRELATION,
    )
    evaluation = lifecycle._evaluator.evaluate(event)[0]

    first, first_is_new = lifecycle._record(event, evaluation)
    second, second_is_new = lifecycle._record(event, evaluation)

    assert first_is_new is True
    assert second_is_new is False
    assert first == second
    assert lifecycle.evidence_count == 1


def test_concurrent_same_timestamp_failures_create_one_fired_evidence() -> None:
    lifecycle = ExpertRaRatingActionsOperationsLifecycleV1(
        evaluator=_evaluator(threshold=1),
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

    fired = [item for batch in batches for item in batch.evidence]
    assert len(fired) == 1
    assert lifecycle.evidence_count == 1

    recovered = lifecycle.observe_source(
        _available_snapshot(retrieved_at=NOW),
        correlation_id=CORRELATION,
    )
    assert recovered.evidence[0].disposition is (
        ExpertRaRatingActionsAlertDisposition.RECOVERED
    )
    assert lifecycle.evidence_count == 2


def test_module_has_no_route_event_sink_notification_or_write_surface() -> None:
    import omni_cio.observability.expert_ra_rating_actions_operations_lifecycle_v1 as module

    for forbidden in (
        "app",
        "router",
        "startup",
        "EventSinkV1",
        "webhook",
        "send_email",
        "telegram",
        "pager",
        "create_order",
        "post_order",
        "cancel_order",
    ):
        assert not hasattr(module, forbidden)
