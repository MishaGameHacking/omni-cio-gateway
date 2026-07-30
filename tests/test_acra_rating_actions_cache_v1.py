from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from threading import Lock
import time
from typing import Any, cast

import pytest
from pydantic import ValidationError

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
from omni_cio.market.acra_rating_actions_cache_v1 import (
    AcraIssuerRatingActionsCacheV1,
    AcraRatingActionsCacheError,
)


NOW = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)


def _source(retrieved_at: datetime) -> MarketSourceV1:
    return MarketSourceV1(
        provider="ACRA",
        authority=SourceAuthority.OFFICIAL,
        retrieved_at=retrieved_at,
        source_id="ACRA.press_releases.issuer_rating_actions",
    )


def _record(
    retrieved_at: datetime,
    *,
    release_id: int = 100,
    rating: str = "A(RU)",
) -> AcraIssuerRatingActionV1:
    source = _source(retrieved_at)
    return AcraIssuerRatingActionV1(
        subject_name=f"ISSUER {release_id}",
        rating=rating,
        action=RatingAction.AFFIRMED,
        outlook=CreditRatingOutlook.STABLE,
        published_on=date(2026, 7, 29),
        release_url=(
            f"https://www.acra-ratings.ru/press-releases/{release_id}/?lang=en"
        ),
        source=source,
    )


def _available(
    retrieved_at: datetime,
    *,
    release_ids: tuple[int, ...] = (100,),
) -> AcraIssuerRatingActionsSnapshotV1:
    source = _source(retrieved_at)
    records = tuple(
        _record(retrieved_at, release_id=release_id)
        for release_id in release_ids
    )
    return AcraIssuerRatingActionsSnapshotV1(
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
) -> AcraIssuerRatingActionsSnapshotV1:
    return AcraIssuerRatingActionsSnapshotV1(
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
    ) -> AcraIssuerRatingActionsSnapshotV1:
        del retrieved_at
        with self._lock:
            self.calls += 1
            value = self._values.pop(0)
        if self._delay_seconds:
            time.sleep(self._delay_seconds)
        if isinstance(value, BaseException):
            raise value
        return cast(AcraIssuerRatingActionsSnapshotV1, value)


def test_snapshot_contract_rejects_duplicate_release_urls() -> None:
    source = _source(NOW)
    record = _record(NOW)
    with pytest.raises(ValidationError):
        AcraIssuerRatingActionsSnapshotV1(
            retrieved_at=NOW,
            status=CreditRatingSourceStatus.AVAILABLE,
            source=source,
            records=(record, record),
        )


def test_cache_result_contract_rejects_impossible_fresh_state() -> None:
    snapshot = _available(NOW)
    with pytest.raises(ValidationError):
        AcraIssuerRatingActionsCacheResultV1(
            checked_at=NOW + timedelta(minutes=20),
            status=CreditRatingCacheStatus.FRESH,
            snapshot=snapshot,
            age_seconds=1_200,
            fresh_until=NOW + timedelta(minutes=15),
            stale_until=NOW + timedelta(days=1),
            served_from_cache=True,
            display_records_allowed=True,
        )


def test_initial_refresh_then_fresh_cache_hit_calls_loader_once() -> None:
    loader = _SequencedLoader([_available(NOW)])
    cache = AcraIssuerRatingActionsCacheV1(
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
    assert loader.calls == 1


def test_failed_force_refresh_keeps_still_fresh_cache_explicit() -> None:
    loader = _SequencedLoader([_available(NOW), RuntimeError("private detail")])
    cache = AcraIssuerRatingActionsCacheV1(
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
    cache = AcraIssuerRatingActionsCacheV1(
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
    assert (
        hidden.cache_error_code
        is CreditRatingCacheErrorCode.STALE_NOT_ALLOWED
    )
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
    cache = AcraIssuerRatingActionsCacheV1(
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
    cache = AcraIssuerRatingActionsCacheV1(loader=loader)

    result = cache.get(checked_at=NOW)

    assert result.status is CreditRatingCacheStatus.UNAVAILABLE
    assert result.snapshot is None
    assert result.cache_error_code is expected
    assert result.display_records_allowed is False


def test_future_and_source_mismatched_snapshots_fail_closed() -> None:
    future = _available(NOW + timedelta(minutes=5))
    valid = _available(NOW)
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
    future_cache = AcraIssuerRatingActionsCacheV1(
        loader=_SequencedLoader([future]),
        future_tolerance_seconds=30,
    )
    mismatch_cache = AcraIssuerRatingActionsCacheV1(
        loader=_SequencedLoader([wrong_source])
    )

    future_result = future_cache.get(checked_at=NOW)
    mismatch_result = mismatch_cache.get(checked_at=NOW)

    assert (
        future_result.cache_error_code
        is CreditRatingCacheErrorCode.REFRESH_FROM_FUTURE
    )
    assert (
        mismatch_result.cache_error_code
        is CreditRatingCacheErrorCode.REFRESH_SOURCE_MISMATCH
    )


def test_concurrent_initial_reads_use_single_flight_refresh() -> None:
    loader = _SequencedLoader([_available(NOW)], delay_seconds=0.03)
    cache = AcraIssuerRatingActionsCacheV1(loader=loader)

    def read(_: int) -> CreditRatingCacheStatus:
        return cache.get(checked_at=NOW).status

    with ThreadPoolExecutor(max_workers=12) as pool:
        statuses = list(pool.map(read, range(24)))

    assert statuses == [CreditRatingCacheStatus.FRESH] * 24
    assert loader.calls == 1


def test_clear_and_configuration_guards() -> None:
    cache = AcraIssuerRatingActionsCacheV1(
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
        with pytest.raises(AcraRatingActionsCacheError):
            AcraIssuerRatingActionsCacheV1(**kwargs)


def test_cache_rejects_non_boolean_flags_and_naive_time() -> None:
    cache = AcraIssuerRatingActionsCacheV1(
        loader=_SequencedLoader([_available(NOW)])
    )
    with pytest.raises(AcraRatingActionsCacheError):
        cache.get(checked_at=NOW, force_refresh=cast(Any, 1))
    with pytest.raises(AcraRatingActionsCacheError):
        cache.get(checked_at=datetime(2026, 7, 30, 12, 0))


def test_cache_module_has_no_route_startup_or_write_surface() -> None:
    import omni_cio.market.acra_rating_actions_cache_v1 as module

    assert not hasattr(module, "app")
    assert not hasattr(module, "router")
    assert not hasattr(module, "startup")
    assert not hasattr(module, "create_order")
    assert not hasattr(module, "post_order")
    assert not hasattr(module, "cancel_order")
