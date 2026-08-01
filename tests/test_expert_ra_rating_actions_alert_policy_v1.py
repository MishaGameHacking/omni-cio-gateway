from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from typing import Any, cast

from pydantic import ValidationError
import pytest

from omni_cio.contracts.v1.expert_ra_alerting import (
    ExpertRaRatingActionsAlertDisposition,
    ExpertRaRatingActionsAlertEvaluationV1,
    ExpertRaRatingActionsAlertKind,
    ExpertRaRatingActionsAlertPolicyV1,
)
from omni_cio.contracts.v1.expert_ra_ratings import (
    ExpertRaIssuerRatingActionsCacheResultV1,
    ExpertRaIssuerRatingActionsSnapshotV1,
    ExpertRaIssuerRatingActionV1,
)
from omni_cio.contracts.v1.market import MarketSourceV1, RatingAction, SourceAuthority
from omni_cio.contracts.v1.observability import (
    ObservabilityEventV1,
    ObservabilityOutcome,
)
from omni_cio.contracts.v1.ratings import (
    CreditRatingCacheErrorCode,
    CreditRatingCacheStatus,
    CreditRatingOutlook,
    CreditRatingSourceErrorCode,
    CreditRatingSourceStatus,
)
from omni_cio.observability.expert_ra_rating_actions_alert_policy_v1 import (
    ExpertRaRatingActionsAlertPolicyError,
    ExpertRaRatingActionsAlertPolicyEvaluatorV1,
)
from omni_cio.observability.expert_ra_rating_actions_events_v1 import (
    build_expert_ra_rating_actions_cache_event,
    build_expert_ra_rating_actions_source_event,
)
from omni_cio.observability.safe_events_v1 import build_safe_event


NOW = datetime(2026, 8, 1, 8, 0, tzinfo=timezone.utc)
CORRELATION = "corr:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


def _source() -> MarketSourceV1:
    return MarketSourceV1(
        provider="Expert RA",
        authority=SourceAuthority.OFFICIAL,
        retrieved_at=NOW,
        source_id="EXPERT_RA.home.rating_actions",
    )


def _available() -> ExpertRaIssuerRatingActionsSnapshotV1:
    source = _source()
    record = ExpertRaIssuerRatingActionV1(
        subject_name="АО «НЕ ДОЛЖНО ПОПАСТЬ В ALERT»",
        rating="ruA",
        action=RatingAction.AFFIRMED,
        outlook=CreditRatingOutlook.STABLE,
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


def _unavailable() -> ExpertRaIssuerRatingActionsSnapshotV1:
    return ExpertRaIssuerRatingActionsSnapshotV1(
        retrieved_at=NOW,
        status=CreditRatingSourceStatus.UNAVAILABLE,
        error_code=CreditRatingSourceErrorCode.NETWORK_ERROR,
    )


def _source_event(*, available: bool, at: datetime) -> ObservabilityEventV1:
    snapshot = _available() if available else _unavailable()
    return build_expert_ra_rating_actions_source_event(
        snapshot,
        occurred_at=at,
        correlation_id=CORRELATION,
    )


def _cache_result(
    state: str,
    *,
    at: datetime,
) -> ExpertRaIssuerRatingActionsCacheResultV1:
    if state == "fresh_hit":
        return ExpertRaIssuerRatingActionsCacheResultV1(
            checked_at=at,
            status=CreditRatingCacheStatus.FRESH,
            snapshot=_available(),
            age_seconds=max(0, int((at - NOW).total_seconds())),
            fresh_until=at + timedelta(seconds=30),
            stale_until=at + timedelta(minutes=30),
            served_from_cache=True,
            display_records_allowed=True,
        )
    if state == "fresh_refresh":
        return ExpertRaIssuerRatingActionsCacheResultV1(
            checked_at=at,
            status=CreditRatingCacheStatus.FRESH,
            snapshot=_available(),
            age_seconds=max(0, int((at - NOW).total_seconds())),
            fresh_until=at + timedelta(seconds=30),
            stale_until=at + timedelta(minutes=30),
            refresh_attempted=True,
            refresh_succeeded=True,
            display_records_allowed=True,
        )
    if state == "refresh_failed_fresh":
        return ExpertRaIssuerRatingActionsCacheResultV1(
            checked_at=at,
            status=CreditRatingCacheStatus.FRESH,
            snapshot=_available(),
            age_seconds=max(0, int((at - NOW).total_seconds())),
            fresh_until=at + timedelta(seconds=30),
            stale_until=at + timedelta(minutes=30),
            served_from_cache=True,
            refresh_attempted=True,
            source_error_code=CreditRatingSourceErrorCode.NETWORK_ERROR,
            cache_error_code=CreditRatingCacheErrorCode.REFRESH_FAILED,
            display_records_allowed=True,
        )
    if state == "stale":
        return ExpertRaIssuerRatingActionsCacheResultV1(
            checked_at=at,
            status=CreditRatingCacheStatus.STALE,
            snapshot=_available(),
            age_seconds=max(0, int((at - NOW).total_seconds())),
            fresh_until=at - timedelta(seconds=1),
            stale_until=at + timedelta(minutes=30),
            served_from_cache=True,
            stale_available=True,
            stale_value_exposed=True,
            refresh_attempted=True,
            source_error_code=CreditRatingSourceErrorCode.NETWORK_ERROR,
            cache_error_code=CreditRatingCacheErrorCode.REFRESH_FAILED,
            display_records_allowed=True,
        )
    if state == "hidden_stale":
        return ExpertRaIssuerRatingActionsCacheResultV1(
            checked_at=at,
            status=CreditRatingCacheStatus.UNAVAILABLE,
            fresh_until=at - timedelta(seconds=1),
            stale_until=at + timedelta(minutes=30),
            stale_available=True,
            refresh_attempted=True,
            source_error_code=CreditRatingSourceErrorCode.NETWORK_ERROR,
            cache_error_code=CreditRatingCacheErrorCode.STALE_NOT_ALLOWED,
            display_records_allowed=False,
        )
    return ExpertRaIssuerRatingActionsCacheResultV1(
        checked_at=at,
        status=CreditRatingCacheStatus.UNAVAILABLE,
        refresh_attempted=True,
        source_error_code=CreditRatingSourceErrorCode.NETWORK_ERROR,
        cache_error_code=CreditRatingCacheErrorCode.EMPTY,
        display_records_allowed=False,
    )


def _cache_event(state: str, *, at: datetime) -> ObservabilityEventV1:
    return build_expert_ra_rating_actions_cache_event(
        _cache_result(state, at=at),
        occurred_at=at,
        correlation_id=CORRELATION,
    )


def _policy(**updates: int) -> ExpertRaRatingActionsAlertPolicyV1:
    values = {
        "source_unavailable_threshold": 2,
        "cache_unavailable_threshold": 2,
        "stale_records_threshold": 2,
        "refresh_failure_threshold": 2,
        "cooldown_seconds": 60,
        "state_retention_seconds": 60,
    }
    values.update(updates)
    return ExpertRaRatingActionsAlertPolicyV1(**values)


def test_policy_is_global_without_identity_rating_action_financial_or_delivery() -> None:
    policy = ExpertRaRatingActionsAlertPolicyV1()
    evaluator = ExpertRaRatingActionsAlertPolicyEvaluatorV1(policy)

    assert policy.scope == "global_expert_ra_rating_actions_feed"
    assert policy.capacity == 4
    assert policy.issuer_identity_present is False
    assert policy.rating_values_present is False
    assert policy.action_identity_present is False
    assert policy.rating_thresholds_present is False
    assert policy.financial_thresholds_present is False
    assert policy.external_notifications_enabled is False
    assert policy.broker_write_called is False
    assert evaluator.rating_values_present is False
    assert evaluator.action_identity_present is False
    assert evaluator.trading_methods is False
    with pytest.raises(ValidationError):
        ExpertRaRatingActionsAlertPolicyV1(capacity=5)


def test_source_threshold_fire_cooldown_and_recovery() -> None:
    evaluator = ExpertRaRatingActionsAlertPolicyEvaluatorV1(_policy())

    first = evaluator.evaluate(_source_event(available=False, at=NOW))[0]
    second = evaluator.evaluate(
        _source_event(available=False, at=NOW + timedelta(seconds=1))
    )[0]
    third = evaluator.evaluate(
        _source_event(available=False, at=NOW + timedelta(seconds=2))
    )[0]
    recovered = evaluator.evaluate(
        _source_event(available=True, at=NOW + timedelta(seconds=3))
    )[0]

    assert first.disposition is ExpertRaRatingActionsAlertDisposition.PENDING
    assert second.disposition is ExpertRaRatingActionsAlertDisposition.FIRED
    assert second.kind is ExpertRaRatingActionsAlertKind.SOURCE_UNAVAILABLE
    assert third.disposition is (
        ExpertRaRatingActionsAlertDisposition.SUPPRESSED_COOLDOWN
    )
    assert third.cooldown_remaining_seconds == 59
    assert recovered.disposition is ExpertRaRatingActionsAlertDisposition.RECOVERED
    assert recovered.kind is ExpertRaRatingActionsAlertKind.SOURCE_UNAVAILABLE
    assert recovered.error_code is None
    assert evaluator.state_count == 0


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("unavailable", ExpertRaRatingActionsAlertKind.CACHE_UNAVAILABLE),
        ("hidden_stale", ExpertRaRatingActionsAlertKind.CACHE_UNAVAILABLE),
        ("stale", ExpertRaRatingActionsAlertKind.STALE_RECORDS_EXPOSED),
        (
            "refresh_failed_fresh",
            ExpertRaRatingActionsAlertKind.REFRESH_FAILED_USING_FRESH_CACHE,
        ),
    ],
)
def test_cache_conditions_map_to_global_operational_kinds(
    state: str,
    expected: ExpertRaRatingActionsAlertKind,
) -> None:
    evaluator = ExpertRaRatingActionsAlertPolicyEvaluatorV1(_policy())
    evaluation = evaluator.evaluate(_cache_event(state, at=NOW))[0]

    assert evaluation.kind is expected
    assert evaluation.disposition is ExpertRaRatingActionsAlertDisposition.PENDING
    assert evaluation.scope == "global_expert_ra_rating_actions_feed"
    assert evaluation.issuer_identity_present is False
    assert evaluation.rating_values_present is False
    assert evaluation.action_identity_present is False
    assert evaluation.rating_thresholds_present is False
    assert evaluation.financial_thresholds_present is False
    assert evaluation.external_notification_sent is False
    assert evaluation.broker_write_called is False


def test_cache_signal_recovers_active_sibling_before_new_pending_state() -> None:
    evaluator = ExpertRaRatingActionsAlertPolicyEvaluatorV1(
        _policy(stale_records_threshold=1)
    )
    fired = evaluator.evaluate(_cache_event("stale", at=NOW))[0]
    assert fired.disposition is ExpertRaRatingActionsAlertDisposition.FIRED

    evaluations = evaluator.evaluate(
        _cache_event("unavailable", at=NOW + timedelta(seconds=1))
    )
    assert [item.disposition for item in evaluations] == [
        ExpertRaRatingActionsAlertDisposition.RECOVERED,
        ExpertRaRatingActionsAlertDisposition.PENDING,
    ]
    assert evaluations[0].kind is (
        ExpertRaRatingActionsAlertKind.STALE_RECORDS_EXPOSED
    )
    assert evaluations[1].kind is ExpertRaRatingActionsAlertKind.CACHE_UNAVAILABLE


def test_healthy_cache_event_recovers_active_cache_signal() -> None:
    evaluator = ExpertRaRatingActionsAlertPolicyEvaluatorV1(
        _policy(cache_unavailable_threshold=1)
    )
    evaluator.evaluate(_cache_event("unavailable", at=NOW))
    recovered = evaluator.evaluate(
        _cache_event("fresh_hit", at=NOW + timedelta(seconds=1))
    )[0]

    assert recovered.disposition is ExpertRaRatingActionsAlertDisposition.RECOVERED
    assert recovered.kind is ExpertRaRatingActionsAlertKind.CACHE_UNAVAILABLE


def test_fresh_refresh_and_unknown_event_are_ignored_without_state() -> None:
    evaluator = ExpertRaRatingActionsAlertPolicyEvaluatorV1()
    healthy = evaluator.evaluate(_cache_event("fresh_refresh", at=NOW))[0]
    unknown = build_safe_event(
        event_name="system.unrelated.health",
        component="system.unrelated",
        outcome=ObservabilityOutcome.SUCCESS,
        occurred_at=NOW + timedelta(seconds=1),
        correlation_id=CORRELATION,
    )
    ignored = evaluator.evaluate(unknown)[0]

    assert healthy.disposition is ExpertRaRatingActionsAlertDisposition.IGNORED
    assert ignored.disposition is ExpertRaRatingActionsAlertDisposition.IGNORED
    assert evaluator.state_count == 0


def test_known_event_forgery_fails_closed_before_state_change() -> None:
    evaluator = ExpertRaRatingActionsAlertPolicyEvaluatorV1()
    valid = _cache_event("stale", at=NOW)
    wrong_component = valid.model_copy(update={"component": "forged"})
    duplicate_metric = valid.model_copy(
        update={"metrics": valid.metrics + (valid.metrics[0],)}
    )
    wrong_identity_flag = valid.model_copy(
        update={
            "metrics": tuple(
                metric.model_copy(update={"value": 1})
                if metric.name == "expert_ra.cross_agency_identity_merged"
                else metric
                for metric in valid.metrics
            )
        }
    )
    free_form_trace = valid.model_copy(
        update={"correlation_id": "corr:issuer_name_leak"}
    )
    bypass_sensitive = valid.model_copy(update={"contains_sensitive_payload": True})

    for event in (
        wrong_component,
        duplicate_metric,
        wrong_identity_flag,
        free_form_trace,
        bypass_sensitive,
    ):
        with pytest.raises(ExpertRaRatingActionsAlertPolicyError):
            evaluator.evaluate(cast(Any, event))
        assert evaluator.state_count == 0


def test_wrong_type_and_out_of_order_known_signal_fail_closed() -> None:
    evaluator = ExpertRaRatingActionsAlertPolicyEvaluatorV1(
        _policy(source_unavailable_threshold=1)
    )
    with pytest.raises(ExpertRaRatingActionsAlertPolicyError):
        evaluator.evaluate(cast(Any, {"not": "an event"}))

    evaluator.evaluate(_source_event(available=False, at=NOW + timedelta(seconds=2)))
    with pytest.raises(ExpertRaRatingActionsAlertPolicyError):
        evaluator.evaluate(_source_event(available=False, at=NOW))


def test_retention_prunes_inactive_pending_state() -> None:
    evaluator = ExpertRaRatingActionsAlertPolicyEvaluatorV1(
        _policy(source_unavailable_threshold=3, state_retention_seconds=60)
    )
    pending = evaluator.evaluate(_source_event(available=False, at=NOW))[0]
    assert pending.disposition is ExpertRaRatingActionsAlertDisposition.PENDING
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


def test_evaluation_contract_rejects_impossible_states() -> None:
    with pytest.raises(ValidationError):
        ExpertRaRatingActionsAlertEvaluationV1(
            evaluated_at=NOW,
            source_event_name="market.expert_ra_rating_actions.source",
            disposition=ExpertRaRatingActionsAlertDisposition.PENDING,
            kind=ExpertRaRatingActionsAlertKind.SOURCE_UNAVAILABLE,
            severity="error",
            consecutive_occurrences=2,
            threshold=2,
        )
    with pytest.raises(ValidationError):
        ExpertRaRatingActionsAlertEvaluationV1(
            evaluated_at=NOW,
            source_event_name="market.expert_ra_rating_actions.source",
            disposition=ExpertRaRatingActionsAlertDisposition.IGNORED,
            error_code="SHOULD_NOT_EXIST",
        )


def test_concurrent_source_failures_are_serialized_and_bounded() -> None:
    evaluator = ExpertRaRatingActionsAlertPolicyEvaluatorV1(
        _policy(source_unavailable_threshold=100, cooldown_seconds=0)
    )

    def evaluate(index: int) -> int:
        event = _source_event(
            available=False,
            at=NOW + timedelta(microseconds=index),
        )
        return evaluator.evaluate(event)[0].consecutive_occurrences

    with ThreadPoolExecutor(max_workers=8) as pool:
        counts = list(pool.map(evaluate, range(20)))

    assert sorted(counts) == list(range(1, 21))
    assert evaluator.state_count == 1


def test_alert_policy_module_has_no_route_notification_or_broker_write_surface() -> None:
    import omni_cio.observability.expert_ra_rating_actions_alert_policy_v1 as module

    for forbidden in (
        "app",
        "router",
        "startup",
        "emit",
        "webhook",
        "send_email",
        "send_telegram",
        "create_order",
        "post_order",
        "cancel_order",
    ):
        assert not hasattr(module, forbidden)
