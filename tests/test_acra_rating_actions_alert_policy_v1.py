from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
import json
from typing import cast

from pydantic import ValidationError
import pytest

from omni_cio.contracts.v1.acra_alerting import (
    AcraRatingActionsAlertDisposition,
    AcraRatingActionsAlertKind,
    AcraRatingActionsAlertPolicyV1,
)
from omni_cio.contracts.v1.market import MarketSourceV1, RatingAction, SourceAuthority
from omni_cio.contracts.v1.observability import (
    ObservabilityEventV1,
    ObservabilityOutcome,
)
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
    AcraRatingActionsAlertPolicyError,
    AcraRatingActionsAlertPolicyEvaluatorV1,
)
from omni_cio.observability.acra_rating_actions_events_v1 import (
    build_acra_rating_actions_cache_event,
    build_acra_rating_actions_source_event,
)
from omni_cio.observability.safe_events_v1 import build_safe_event


NOW = datetime(2026, 7, 31, 3, 0, tzinfo=timezone.utc)
CORRELATION = "corr:acraalertpolicy"


def _source() -> MarketSourceV1:
    return MarketSourceV1(
        provider="ACRA",
        authority=SourceAuthority.OFFICIAL,
        retrieved_at=NOW,
        source_id="ACRA.press_releases.issuer_rating_actions",
    )


def _available() -> AcraIssuerRatingActionsSnapshotV1:
    source = _source()
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
        retrieved_at=NOW,
        status=CreditRatingSourceStatus.AVAILABLE,
        source=source,
        records=(record,),
    )


def _unavailable() -> AcraIssuerRatingActionsSnapshotV1:
    return AcraIssuerRatingActionsSnapshotV1(
        retrieved_at=NOW,
        status=CreditRatingSourceStatus.UNAVAILABLE,
        error_code=CreditRatingSourceErrorCode.NETWORK_ERROR,
    )


def _source_event(*, available: bool, at: datetime) -> ObservabilityEventV1:
    snapshot = _available() if available else _unavailable()
    return build_acra_rating_actions_source_event(
        snapshot,
        occurred_at=at,
        correlation_id=CORRELATION,
    )


def _cache_result(
    state: str,
    *,
    at: datetime,
) -> AcraIssuerRatingActionsCacheResultV1:
    if state == "fresh_hit":
        return AcraIssuerRatingActionsCacheResultV1(
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
        return AcraIssuerRatingActionsCacheResultV1(
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
        return AcraIssuerRatingActionsCacheResultV1(
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
        return AcraIssuerRatingActionsCacheResultV1(
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
        return AcraIssuerRatingActionsCacheResultV1(
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
    return AcraIssuerRatingActionsCacheResultV1(
        checked_at=at,
        status=CreditRatingCacheStatus.UNAVAILABLE,
        refresh_attempted=True,
        source_error_code=CreditRatingSourceErrorCode.NETWORK_ERROR,
        cache_error_code=CreditRatingCacheErrorCode.EMPTY,
        display_records_allowed=False,
    )


def _cache_event(state: str, *, at: datetime) -> ObservabilityEventV1:
    return build_acra_rating_actions_cache_event(
        _cache_result(state, at=at),
        occurred_at=at,
        correlation_id=CORRELATION,
    )


def _policy(**updates: int) -> AcraRatingActionsAlertPolicyV1:
    values = {
        "source_unavailable_threshold": 2,
        "cache_unavailable_threshold": 2,
        "stale_records_threshold": 2,
        "refresh_failure_threshold": 2,
        "cooldown_seconds": 60,
        "state_retention_seconds": 60,
    }
    values.update(updates)
    return AcraRatingActionsAlertPolicyV1(**values)


def test_policy_is_global_without_identity_rating_financial_or_delivery_controls() -> None:
    policy = AcraRatingActionsAlertPolicyV1()
    evaluator = AcraRatingActionsAlertPolicyEvaluatorV1(policy)
    assert policy.scope == "global_acra_rating_actions_feed"
    assert policy.capacity == 4
    assert policy.issuer_identity_present is False
    assert policy.rating_thresholds_present is False
    assert policy.financial_thresholds_present is False
    assert policy.external_notifications_enabled is False
    assert evaluator.rating_values_present is False
    assert evaluator.trading_methods is False
    with pytest.raises(ValidationError):
        AcraRatingActionsAlertPolicyV1(capacity=5)


def test_source_threshold_fire_cooldown_and_recovery() -> None:
    evaluator = AcraRatingActionsAlertPolicyEvaluatorV1(_policy())

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

    assert first.disposition is AcraRatingActionsAlertDisposition.PENDING
    assert second.disposition is AcraRatingActionsAlertDisposition.FIRED
    assert second.kind is AcraRatingActionsAlertKind.SOURCE_UNAVAILABLE
    assert third.disposition is AcraRatingActionsAlertDisposition.SUPPRESSED_COOLDOWN
    assert third.cooldown_remaining_seconds == 59
    assert recovered.disposition is AcraRatingActionsAlertDisposition.RECOVERED
    assert recovered.kind is AcraRatingActionsAlertKind.SOURCE_UNAVAILABLE
    assert evaluator.state_count == 0


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("unavailable", AcraRatingActionsAlertKind.CACHE_UNAVAILABLE),
        ("hidden_stale", AcraRatingActionsAlertKind.CACHE_UNAVAILABLE),
        ("stale", AcraRatingActionsAlertKind.STALE_RECORDS_EXPOSED),
        (
            "refresh_failed_fresh",
            AcraRatingActionsAlertKind.REFRESH_FAILED_USING_FRESH_CACHE,
        ),
    ],
)
def test_cache_conditions_map_to_global_operational_kinds(
    state: str,
    expected: AcraRatingActionsAlertKind,
) -> None:
    evaluator = AcraRatingActionsAlertPolicyEvaluatorV1(_policy())
    evaluation = evaluator.evaluate(_cache_event(state, at=NOW))[0]
    assert evaluation.kind is expected
    assert evaluation.disposition is AcraRatingActionsAlertDisposition.PENDING
    assert evaluation.scope == "global_acra_rating_actions_feed"
    assert evaluation.issuer_identity_present is False
    assert evaluation.rating_values_present is False
    assert evaluation.rating_thresholds_present is False
    assert evaluation.external_notification_sent is False


def test_cache_signal_recovers_active_sibling_before_new_pending_state() -> None:
    evaluator = AcraRatingActionsAlertPolicyEvaluatorV1(
        _policy(stale_records_threshold=1)
    )
    fired = evaluator.evaluate(_cache_event("stale", at=NOW))[0]
    assert fired.disposition is AcraRatingActionsAlertDisposition.FIRED

    evaluations = evaluator.evaluate(
        _cache_event("unavailable", at=NOW + timedelta(seconds=1))
    )
    assert [item.disposition for item in evaluations] == [
        AcraRatingActionsAlertDisposition.RECOVERED,
        AcraRatingActionsAlertDisposition.PENDING,
    ]
    assert evaluations[0].kind is AcraRatingActionsAlertKind.STALE_RECORDS_EXPOSED
    assert evaluations[1].kind is AcraRatingActionsAlertKind.CACHE_UNAVAILABLE


def test_healthy_cache_event_recovers_active_cache_signal() -> None:
    evaluator = AcraRatingActionsAlertPolicyEvaluatorV1(
        _policy(cache_unavailable_threshold=1)
    )
    evaluator.evaluate(_cache_event("unavailable", at=NOW))
    recovered = evaluator.evaluate(
        _cache_event("fresh_hit", at=NOW + timedelta(seconds=1))
    )[0]
    assert recovered.disposition is AcraRatingActionsAlertDisposition.RECOVERED
    assert recovered.kind is AcraRatingActionsAlertKind.CACHE_UNAVAILABLE


def test_fresh_refresh_and_unknown_event_are_ignored_without_state() -> None:
    evaluator = AcraRatingActionsAlertPolicyEvaluatorV1()
    healthy = evaluator.evaluate(_cache_event("fresh_refresh", at=NOW))[0]
    unknown = build_safe_event(
        event_name="system.unrelated.health",
        component="system.unrelated",
        outcome=ObservabilityOutcome.SUCCESS,
        occurred_at=NOW + timedelta(seconds=1),
        correlation_id=CORRELATION,
    )
    ignored = evaluator.evaluate(unknown)[0]
    assert healthy.disposition is AcraRatingActionsAlertDisposition.IGNORED
    assert ignored.disposition is AcraRatingActionsAlertDisposition.IGNORED
    assert evaluator.state_count == 0


def test_forged_known_events_fail_closed_before_state_change() -> None:
    evaluator = AcraRatingActionsAlertPolicyEvaluatorV1()
    valid = _cache_event("stale", at=NOW)
    wrong_component = valid.model_copy(update={"component": "forged"})
    duplicate_metric = valid.model_copy(
        update={"metrics": valid.metrics + (valid.metrics[0],)}
    )
    wrong_stale_profile = valid.model_copy(
        update={
            "metrics": tuple(
                metric.model_copy(update={"value": 0})
                if metric.name == "acra.stale_available"
                else metric
                for metric in valid.metrics
            )
        }
    )
    for event in (wrong_component, duplicate_metric, wrong_stale_profile):
        with pytest.raises(
            AcraRatingActionsAlertPolicyError,
            match="CONTRACT_INVALID",
        ):
            evaluator.evaluate(event)
    assert evaluator.state_count == 0


def test_out_of_order_and_type_fail_closed() -> None:
    evaluator = AcraRatingActionsAlertPolicyEvaluatorV1(_policy())
    evaluator.evaluate(
        _source_event(available=False, at=NOW + timedelta(seconds=2))
    )
    with pytest.raises(AcraRatingActionsAlertPolicyError, match="OUT_OF_ORDER"):
        evaluator.evaluate(_source_event(available=False, at=NOW))
    with pytest.raises(AcraRatingActionsAlertPolicyError, match="TYPE_INVALID"):
        evaluator.evaluate(cast(ObservabilityEventV1, object()))


def test_pending_state_expires_after_retention_and_clear_resets_state() -> None:
    evaluator = AcraRatingActionsAlertPolicyEvaluatorV1(_policy())
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

    evaluator.evaluate(
        _source_event(available=False, at=NOW + timedelta(seconds=62))
    )
    evaluator.clear()
    assert evaluator.state_count == 0


def test_concurrent_threshold_updates_are_serialized() -> None:
    evaluator = AcraRatingActionsAlertPolicyEvaluatorV1(
        _policy(source_unavailable_threshold=1, cooldown_seconds=60)
    )
    events = [
        _source_event(available=False, at=NOW + timedelta(microseconds=index))
        for index in range(20)
    ]
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda event: evaluator.evaluate(event)[0], events))

    dispositions = [result.disposition for result in results]
    assert dispositions.count(AcraRatingActionsAlertDisposition.FIRED) == 1
    assert (
        dispositions.count(AcraRatingActionsAlertDisposition.SUPPRESSED_COOLDOWN)
        == 19
    )
    assert evaluator.state_count == 1


def test_evaluation_serialization_excludes_rating_and_issuer_payload() -> None:
    evaluator = AcraRatingActionsAlertPolicyEvaluatorV1(_policy())
    evaluation = evaluator.evaluate(_cache_event("stale", at=NOW))[0]
    payload = json.dumps(evaluation.model_dump(mode="json"), sort_keys=True)
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
    ):
        assert forbidden not in payload
    assert evaluation.contains_sensitive_payload is False
    assert evaluation.trading_methods is False


def test_module_has_no_external_transport_route_startup_or_write_surface() -> None:
    import omni_cio.observability.acra_rating_actions_alert_policy_v1 as module

    for forbidden in (
        "app",
        "router",
        "startup",
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
