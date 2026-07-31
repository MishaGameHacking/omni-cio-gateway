from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import cast

import pytest

from omni_cio.contracts.v1.acra_alerting import (
    AcraRatingActionsAlertDisposition,
    AcraRatingActionsAlertKind,
    AcraRatingActionsAlertPolicyV1,
)
from omni_cio.contracts.v1.market import MarketSourceV1, RatingAction, SourceAuthority
from omni_cio.contracts.v1.observability import ObservabilityEventV1
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

NOW = datetime(2026, 7, 31, 3, 0, tzinfo=timezone.utc)


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


def _cache(status: CreditRatingCacheStatus, *, at: datetime = NOW) -> AcraIssuerRatingActionsCacheResultV1:
    if status is CreditRatingCacheStatus.FRESH:
        return AcraIssuerRatingActionsCacheResultV1(
            checked_at=at,
            status=status,
            snapshot=_available(),
            age_seconds=max(0, int((at - NOW).total_seconds())),
            fresh_until=NOW + timedelta(minutes=15),
            stale_until=NOW + timedelta(days=1),
            served_from_cache=True,
            display_records_allowed=True,
        )
    if status is CreditRatingCacheStatus.STALE:
        return AcraIssuerRatingActionsCacheResultV1(
            checked_at=at,
            status=status,
            snapshot=_available(),
            age_seconds=max(0, int((at - NOW).total_seconds())),
            fresh_until=NOW + timedelta(minutes=15),
            stale_until=NOW + timedelta(days=1),
            served_from_cache=True,
            stale_available=True,
            stale_value_exposed=True,
            refresh_attempted=True,
            source_error_code=CreditRatingSourceErrorCode.NETWORK_ERROR,
            cache_error_code=CreditRatingCacheErrorCode.REFRESH_FAILED,
            display_records_allowed=True,
        )
    return AcraIssuerRatingActionsCacheResultV1(
        checked_at=at,
        status=status,
        refresh_attempted=True,
        source_error_code=CreditRatingSourceErrorCode.NETWORK_ERROR,
        cache_error_code=CreditRatingCacheErrorCode.EMPTY,
        display_records_allowed=False,
    )


def test_source_threshold_fire_cooldown_and_recovery() -> None:
    policy = AcraRatingActionsAlertPolicyV1(source_unavailable_threshold=2, cooldown_seconds=60)
    evaluator = AcraRatingActionsAlertPolicyEvaluatorV1(policy)
    first = evaluator.evaluate(build_acra_rating_actions_source_event(_unavailable(), occurred_at=NOW))[0]
    second = evaluator.evaluate(build_acra_rating_actions_source_event(_unavailable(), occurred_at=NOW + timedelta(seconds=1)))[0]
    third = evaluator.evaluate(build_acra_rating_actions_source_event(_unavailable(), occurred_at=NOW + timedelta(seconds=2)))[0]
    recovered = evaluator.evaluate(build_acra_rating_actions_source_event(_available(), occurred_at=NOW + timedelta(seconds=3)))[0]
    assert first.disposition is AcraRatingActionsAlertDisposition.PENDING
    assert second.disposition is AcraRatingActionsAlertDisposition.FIRED
    assert third.disposition is AcraRatingActionsAlertDisposition.SUPPRESSED_COOLDOWN
    assert recovered.disposition is AcraRatingActionsAlertDisposition.RECOVERED
    assert recovered.kind is AcraRatingActionsAlertKind.SOURCE_UNAVAILABLE


def test_cache_conditions_are_global_operational_only() -> None:
    evaluator = AcraRatingActionsAlertPolicyEvaluatorV1(
        AcraRatingActionsAlertPolicyV1(
            cache_unavailable_threshold=1,
            stale_records_threshold=1,
            refresh_failure_threshold=1,
        )
    )
    unavailable = evaluator.evaluate(build_acra_rating_actions_cache_event(_cache(CreditRatingCacheStatus.UNAVAILABLE), occurred_at=NOW))[0]
    stale = evaluator.evaluate(build_acra_rating_actions_cache_event(_cache(CreditRatingCacheStatus.STALE, at=NOW + timedelta(minutes=16)), occurred_at=NOW + timedelta(minutes=16)))[-1]
    assert unavailable.kind is AcraRatingActionsAlertKind.CACHE_UNAVAILABLE
    assert unavailable.disposition is AcraRatingActionsAlertDisposition.FIRED
    assert stale.kind is AcraRatingActionsAlertKind.STALE_RECORDS_EXPOSED
    assert stale.disposition is AcraRatingActionsAlertDisposition.FIRED
    payload = stale.model_dump_json()
    for forbidden in ("SAFE ISSUER", "A(RU)", "stable", "press-releases/100"):
        assert forbidden not in payload


def test_unknown_event_is_ignored_and_forged_known_event_fails_closed() -> None:
    evaluator = AcraRatingActionsAlertPolicyEvaluatorV1()
    unknown = build_acra_rating_actions_source_event(_available(), occurred_at=NOW).model_copy(update={"event_name": "other.event"})
    assert evaluator.evaluate(unknown)[0].disposition is AcraRatingActionsAlertDisposition.IGNORED
    forged = build_acra_rating_actions_source_event(_available(), occurred_at=NOW).model_copy(update={"component": "forged"})
    with pytest.raises(AcraRatingActionsAlertPolicyError):
        evaluator.evaluate(forged)


def test_out_of_order_and_type_fail_closed() -> None:
    evaluator = AcraRatingActionsAlertPolicyEvaluatorV1(AcraRatingActionsAlertPolicyV1(source_unavailable_threshold=1))
    evaluator.evaluate(build_acra_rating_actions_source_event(_unavailable(), occurred_at=NOW + timedelta(seconds=2)))
    with pytest.raises(AcraRatingActionsAlertPolicyError):
        evaluator.evaluate(build_acra_rating_actions_source_event(_unavailable(), occurred_at=NOW))
    with pytest.raises(AcraRatingActionsAlertPolicyError):
        evaluator.evaluate(cast(ObservabilityEventV1, object()))


def test_policy_has_no_identity_rating_financial_or_delivery_surface() -> None:
    policy = AcraRatingActionsAlertPolicyV1()
    evaluator = AcraRatingActionsAlertPolicyEvaluatorV1(policy)
    assert policy.scope == "global_acra_rating_actions_feed"
    assert policy.capacity == 4
    assert policy.issuer_identity_present is False
    assert policy.rating_thresholds_present is False
    assert policy.financial_thresholds_present is False
    assert policy.external_notifications_enabled is False
    assert evaluator.trading_methods is False
    evaluator.clear()
    assert evaluator.state_count == 0
