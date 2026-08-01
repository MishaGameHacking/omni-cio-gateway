from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from threading import Lock
import time
from typing import Any, cast

import pytest
from pydantic import ValidationError

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
from omni_cio.market.expert_ra_rating_actions_cache_v1 import (
    ExpertRaIssuerRatingActionsCacheV1,
    ExpertRaRatingActionsCacheError,
)
from omni_cio.market.expert_ra_rating_actions_v1 import (
    EXPERT_RA_RATING_ACTIONS_SOURCE_ID,
)


NOW = datetime(2026, 8, 1, 6, 30, tzinfo=timezone.utc)
PUBLISHED_ON = date(2026, 7, 31)


def _source(retrieved_at: datetime) -> MarketSourceV1:
    return MarketSourceV1(
        provider="Expert RA",
        authority=SourceAuthority.OFFICIAL,
        retrieved_at=retrieved_at,
        source_id=EXPERT_RA_RATING_ACTIONS_SOURCE_ID,
    )


def _record(
    retrieved_at: datetime,
    *,
    suffix: str = "a",
    rating: str = "ruA",
) -> ExpertRaIssuerRatingActionV1:
    source = _source(retrieved_at)
    return ExpertRaIssuerRatingActionV1(
        subject_name=f"АО «Эмитент {suffix.upper()}»",
        rating=rating,
        action=RatingAction.AFFIRMED,
        outlook=CreditRatingOutlook.STABLE,
        published_on=PUBLISHED_ON,
        release_url=f"https://raexpert.ru/releases/2026/jul31{suffix}",
        source=source,
    )


def _available(
    retrieved_at: datetime,
    *,
    suffixes: tuple[str, ...] = ("a",),
) -> ExpertRaIssuerRatingActionsSnapshotV1:
    source = _source(retrieved_at)
    records = tuple(
        sorted(
            (_record(retrieved_at, suffix=suffix) for suffix in suffixes),
            key=lambda item: (item.published_on, item.release_url),
            reverse=True,
        )
    )
    return ExpertRaIssuerRatingActionsSnapshotV1(
        retrieved_at=retrieved_at,
        status=CreditRatingSourceStatus.AVAILABLE,
        source=source,
        records=records,
    )


def _unavailable(
    retrieved_at: datetime,
    *,
    error_code: CreditRatingSourceErrorCode = (
        CreditRatingSourceErrorCode.NETWORK_ERROR
    ),
) -> ExpertRaIssuerRatingActionsSnapshotV1:
    return ExpertRaIssuerRatingActionsSnapshotV1(
        retrieved_at=retrieved_at,
        status=CreditRatingSourceStatus.UNAVAILABLE,
        error_code=error_code,
    )


class _SequencedLoader:
    def __init__(self, values: list[object], *, delay_seconds: float = 0.0) -> None:
        self._values = list(values)
        self._delay_seconds = delay_seconds
        self._lock = Lock()
        self.calls = 0

    def __call__(
        self,
        *,
        retrieved_at: datetime,
    ) -> ExpertRaIssuerRatingActionsSnapshotV1:
        del retrieved_at
        with self._lock:
            self.calls += 1
            value = self._values.pop(0)
        if self._delay_seconds:
            time.sleep(self._delay_seconds)
        if isinstance(value, BaseException):
            raise value
        return cast(ExpertRaIssuerRatingActionsSnapshotV1, value)


def test_cache_result_contract_rejects_impossible_fresh_state() -> None:
    snapshot = _available(NOW)
    with pytest.raises(ValidationError):
        ExpertRaIssuerRatingActionsCacheResultV1(
            checked_at=NOW + timedelta(minutes=20),
            status=CreditRatingCacheStatus.FRESH,
            snapshot=snapshot,
            age_seconds=1_200,
            fresh_until=NOW + timedelta(minutes=15),
            stale_until=NOW + timedelta(days=1),
            served_from_cache=True,
            display_records_allowed=True,
        )


def test_initial_refresh_then_fresh_cache_hit_uses_retrieval_time() -> None:
    loader = _SequencedLoader([_available(NOW)])
    cache = ExpertRaIssuerRatingActionsCacheV1(
        loader=loader,
        fresh_seconds=900,
        stale_seconds=3_600,
    )

    refreshed = cache.get(checked_at=NOW)
    cached = cache.get(checked_at=NOW + timedelta(seconds=30))

    assert refreshed.status is CreditRatingCacheStatus.FRESH
    assert refreshed.refresh_attempted is True
    assert refreshed.refresh_succeeded is True
    assert refreshed.served_from_cache is False
    assert cached.status is CreditRatingCacheStatus.FRESH
    assert cached.served_from_cache is True
    assert cached.refresh_attempted is False
    assert cached.age_seconds == 30
    assert cached.snapshot is not None
    assert cached.snapshot.records[0].published_on == PUBLISHED_ON
    assert loader.calls == 1


def test_failed_force_refresh_keeps_still_fresh_cache_explicit() -> None:
    loader = _SequencedLoader([_available(NOW), RuntimeError("private detail")])
    cache = ExpertRaIssuerRatingActionsCacheV1(
        loader=loader,
        fresh_seconds=900,
        stale_seconds=3_600,
    )
    cache.get(checked_at=NOW)

    result = cache.get(
        checked_at=NOW + timedelta(seconds=10),
        force_refresh=True,
    )

    assert result.status is CreditRatingCacheStatus.FRESH
    assert result.served_from_cache is True
    assert result.refresh_attempted is True
    assert result.refresh_succeeded is False
    assert result.cache_error_code is CreditRatingCacheErrorCode.REFRESH_FAILED
    assert "private detail" not in result.model_dump_json()


def test_stale_records_are_hidden_without_explicit_permission() -> None:
    loader = _SequencedLoader(
        [
            _available(NOW),
            _unavailable(NOW + timedelta(minutes=16)),
            _unavailable(NOW + timedelta(minutes=16, seconds=1)),
        ]
    )
    cache = ExpertRaIssuerRatingActionsCacheV1(
        loader=loader,
        fresh_seconds=900,
        stale_seconds=3_600,
    )
    cache.get(checked_at=NOW)

    hidden = cache.get(checked_at=NOW + timedelta(minutes=16))
    exposed = cache.get(
        checked_at=NOW + timedelta(minutes=16, seconds=1),
        allow_stale=True,
    )

    assert hidden.status is CreditRatingCacheStatus.UNAVAILABLE
    assert hidden.snapshot is None
    assert hidden.stale_available is True
    assert hidden.stale_value_exposed is False
    assert hidden.cache_error_code is CreditRatingCacheErrorCode.STALE_NOT_ALLOWED
    assert exposed.status is CreditRatingCacheStatus.STALE
    assert exposed.snapshot is not None
    assert exposed.stale_available is True
    assert exposed.stale_value_exposed is True
    assert exposed.display_records_allowed is True


def test_expired_entry_is_pruned_before_failed_refresh() -> None:
    loader = _SequencedLoader(
        [
            _available(NOW),
            _unavailable(NOW + timedelta(hours=2)),
        ]
    )
    cache = ExpertRaIssuerRatingActionsCacheV1(
        loader=loader,
        fresh_seconds=60,
        stale_seconds=120,
    )
    cache.get(checked_at=NOW)

    result = cache.get(
        checked_at=NOW + timedelta(hours=2),
        allow_stale=True,
    )

    assert result.status is CreditRatingCacheStatus.UNAVAILABLE
    assert result.snapshot is None
    assert result.stale_available is False
    assert result.cache_error_code is CreditRatingCacheErrorCode.EMPTY
    assert cache.active_entry_count(checked_at=NOW + timedelta(hours=2)) == 0


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            {"not": "a snapshot"},
            CreditRatingCacheErrorCode.REFRESH_TYPE_INVALID,
        ),
        (
            _unavailable(NOW),
            CreditRatingCacheErrorCode.EMPTY,
        ),
    ],
)
def test_initial_invalid_or_unavailable_refresh_fails_closed(
    value: object,
    expected: CreditRatingCacheErrorCode,
) -> None:
    loader = _SequencedLoader([value])
    cache = ExpertRaIssuerRatingActionsCacheV1(loader=loader)

    result = cache.get(checked_at=NOW)

    assert result.status is CreditRatingCacheStatus.UNAVAILABLE
    assert result.snapshot is None
    assert result.cache_error_code is expected
    assert result.display_records_allowed is False


def test_future_snapshot_fails_closed() -> None:
    future = _available(NOW + timedelta(minutes=5))
    cache = ExpertRaIssuerRatingActionsCacheV1(
        loader=_SequencedLoader([future]),
        future_tolerance_seconds=30,
    )

    result = cache.get(checked_at=NOW)

    assert result.cache_error_code is CreditRatingCacheErrorCode.REFRESH_FROM_FUTURE
    assert result.snapshot is None


def test_model_construct_source_and_order_bypasses_fail_closed() -> None:
    valid = _available(NOW, suffixes=("b", "a"))
    wrong_source = valid.model_construct(
        retrieved_at=valid.retrieved_at,
        status=valid.status,
        source=MarketSourceV1(
            provider="Other Agency",
            authority=SourceAuthority.OFFICIAL,
            retrieved_at=NOW,
            source_id="other.source",
        ),
        records=valid.records,
        error_code=None,
    )
    unsorted = valid.model_construct(
        retrieved_at=valid.retrieved_at,
        status=valid.status,
        source=valid.source,
        records=tuple(reversed(valid.records)),
        error_code=None,
    )

    for snapshot in (wrong_source, unsorted):
        cache = ExpertRaIssuerRatingActionsCacheV1(
            loader=_SequencedLoader([snapshot])
        )
        result = cache.get(checked_at=NOW)
        assert result.status is CreditRatingCacheStatus.UNAVAILABLE
        assert (
            result.cache_error_code
            is CreditRatingCacheErrorCode.REFRESH_SOURCE_MISMATCH
        )


def test_model_construct_cross_agency_identity_flag_fails_closed() -> None:
    valid = _available(NOW)
    forged = valid.model_construct(
        retrieved_at=valid.retrieved_at,
        status=valid.status,
        source=valid.source,
        records=valid.records,
        error_code=None,
        subject_identity_resolution_required=True,
        cross_agency_identity_merged=True,
        trading_methods=False,
    )
    cache = ExpertRaIssuerRatingActionsCacheV1(
        loader=_SequencedLoader([forged])
    )

    result = cache.get(checked_at=NOW)

    assert result.status is CreditRatingCacheStatus.UNAVAILABLE
    assert (
        result.cache_error_code
        is CreditRatingCacheErrorCode.REFRESH_SOURCE_MISMATCH
    )


def test_concurrent_initial_reads_use_single_flight_refresh() -> None:
    loader = _SequencedLoader([_available(NOW)], delay_seconds=0.03)
    cache = ExpertRaIssuerRatingActionsCacheV1(loader=loader)

    def read(_: int) -> CreditRatingCacheStatus:
        return cache.get(checked_at=NOW).status

    with ThreadPoolExecutor(max_workers=12) as pool:
        statuses = list(pool.map(read, range(24)))

    assert statuses == [CreditRatingCacheStatus.FRESH] * 24
    assert loader.calls == 1


def test_clear_and_configuration_guards() -> None:
    cache = ExpertRaIssuerRatingActionsCacheV1(
        loader=_SequencedLoader([_available(NOW)])
    )
    cache.get(checked_at=NOW)
    assert cache.active_entry_count(checked_at=NOW) == 1
    cache.clear()
    assert cache.active_entry_count(checked_at=NOW) == 0
    assert cache.capacity == 1

    invalid_values: tuple[dict[str, Any], ...] = (
        {"fresh_seconds": True},
        {"fresh_seconds": 0},
        {"fresh_seconds": 100, "stale_seconds": 99},
        {"future_tolerance_seconds": -1},
        {"loader": cast(Any, object())},
    )
    for kwargs in invalid_values:
        with pytest.raises(ExpertRaRatingActionsCacheError):
            ExpertRaIssuerRatingActionsCacheV1(**kwargs)


def test_cache_rejects_non_boolean_flags_and_naive_time() -> None:
    cache = ExpertRaIssuerRatingActionsCacheV1(
        loader=_SequencedLoader([_available(NOW)])
    )
    with pytest.raises(ExpertRaRatingActionsCacheError):
        cache.get(checked_at=NOW, force_refresh=cast(Any, 1))
    with pytest.raises(ExpertRaRatingActionsCacheError):
        cache.get(checked_at=datetime(2026, 8, 1, 6, 30))


def test_cache_privacy_and_usage_flags_are_conservative() -> None:
    cache = ExpertRaIssuerRatingActionsCacheV1(
        loader=_SequencedLoader([_available(NOW)])
    )
    result = cache.get(checked_at=NOW)

    assert cache.internal_only is True
    assert cache.agency_specific_scale_only is True
    assert cache.subject_identity_resolution_required is True
    assert cache.cross_agency_identity_merged is False
    assert cache.informational_use_only is True
    assert cache.redistribution_authorized is False
    assert cache.investment_recommendation is False
    assert cache.trading_methods is False
    assert result.subject_identity_resolution_required is True
    assert result.cross_agency_identity_merged is False
    assert result.trading_methods is False


def test_cache_module_has_no_route_startup_generic_adapter_or_write_surface() -> None:
    import omni_cio.market.expert_ra_rating_actions_cache_v1 as module

    for forbidden in (
        "app",
        "router",
        "startup",
        "multi_agency",
        "agency_url",
        "create_order",
        "post_order",
        "cancel_order",
    ):
        assert not hasattr(module, forbidden)
