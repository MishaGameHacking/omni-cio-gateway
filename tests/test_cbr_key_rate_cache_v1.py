from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from threading import Barrier, Lock
import time

import pytest
from pydantic import ValidationError

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
from omni_cio.market.cbr_key_rate_cache_v1 import (
    CbrKeyRateCacheError,
    CbrKeyRateCacheV1,
)


NOW = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
DATE_FROM = date(2025, 7, 30)
DATE_TO = date(2026, 7, 30)


def _available_snapshot(
    *,
    requested_from: date = DATE_FROM,
    requested_to: date = DATE_TO,
    retrieved_at: datetime = NOW,
    rate: str = "18.00",
) -> CbrKeyRateSnapshotV1:
    row = KeyRateObservationV1(
        effective_date=min(requested_to, date(2026, 7, 23)),
        rate_percent=Decimal(rate),
    )
    source = MarketSourceV1(
        provider="Bank of Russia DailyInfo",
        authority=SourceAuthority.OFFICIAL,
        retrieved_at=retrieved_at,
        source_id="DailyInfo.KeyRateXML",
    )
    return CbrKeyRateSnapshotV1(
        requested_from=requested_from,
        requested_to=requested_to,
        retrieved_at=retrieved_at,
        status=MacroDataStatus.AVAILABLE,
        source=source,
        observations=(row,),
        current=row,
    )


def _unavailable_snapshot(
    *,
    requested_from: date = DATE_FROM,
    requested_to: date = DATE_TO,
    retrieved_at: datetime = NOW,
    error_code: MacroDataErrorCode = MacroDataErrorCode.NETWORK_ERROR,
) -> CbrKeyRateSnapshotV1:
    return CbrKeyRateSnapshotV1(
        requested_from=requested_from,
        requested_to=requested_to,
        retrieved_at=retrieved_at,
        status=MacroDataStatus.UNAVAILABLE,
        error_code=error_code,
    )


class SequenceLoader:
    def __init__(self, *values: object) -> None:
        self.values = list(values)
        self.calls = 0

    def __call__(
        self,
        *,
        requested_from: date,
        requested_to: date,
        retrieved_at: datetime,
    ) -> CbrKeyRateSnapshotV1:
        self.calls += 1
        if not self.values:
            raise RuntimeError("unexpected extra call")
        value = self.values.pop(0)
        if isinstance(value, Exception):
            raise value
        if callable(value):
            value = value(requested_from, requested_to, retrieved_at)
        return value  # type: ignore[return-value]


def test_cache_registration_is_lazy_and_configuration_is_bounded() -> None:
    loader = SequenceLoader(_available_snapshot())
    cache = CbrKeyRateCacheV1(
        loader=loader,
        fresh_seconds=60,
        stale_seconds=120,
        capacity=2,
    )

    assert loader.calls == 0
    assert cache.active_entry_count(checked_at=NOW) == 0
    assert cache.fresh_seconds == 60
    assert cache.stale_seconds == 120
    assert cache.capacity == 2
    assert cache.trading_methods is False

    with pytest.raises(CbrKeyRateCacheError):
        CbrKeyRateCacheV1(loader=loader, fresh_seconds=0)
    with pytest.raises(CbrKeyRateCacheError):
        CbrKeyRateCacheV1(loader=loader, fresh_seconds=120, stale_seconds=60)


def test_first_refresh_is_fresh_and_second_read_uses_cache() -> None:
    loader = SequenceLoader(_available_snapshot())
    cache = CbrKeyRateCacheV1(loader=loader)

    first = cache.get(
        requested_from=DATE_FROM,
        requested_to=DATE_TO,
        checked_at=NOW,
    )
    second = cache.get(
        requested_from=DATE_FROM,
        requested_to=DATE_TO,
        checked_at=NOW + timedelta(minutes=30),
    )

    assert first.status is MacroCacheStatus.FRESH
    assert first.refresh_attempted is True
    assert first.refresh_succeeded is True
    assert first.served_from_cache is False
    assert second.status is MacroCacheStatus.FRESH
    assert second.refresh_attempted is False
    assert second.served_from_cache is True
    assert loader.calls == 1


def test_force_refresh_success_replaces_cached_value() -> None:
    loader = SequenceLoader(
        _available_snapshot(rate="18.00"),
        lambda start, end, checked: _available_snapshot(
            requested_from=start,
            requested_to=end,
            retrieved_at=checked,
            rate="17.00",
        ),
    )
    cache = CbrKeyRateCacheV1(loader=loader)
    cache.get(
        requested_from=DATE_FROM,
        requested_to=DATE_TO,
        checked_at=NOW,
    )

    refreshed = cache.get(
        requested_from=DATE_FROM,
        requested_to=DATE_TO,
        checked_at=NOW + timedelta(minutes=10),
        force_refresh=True,
    )

    assert refreshed.status is MacroCacheStatus.FRESH
    assert refreshed.refresh_succeeded is True
    assert refreshed.snapshot is not None
    assert refreshed.snapshot.current is not None
    assert refreshed.snapshot.current.rate_percent == Decimal("17.00")
    assert loader.calls == 2


def test_failed_force_refresh_preserves_explicit_fresh_cache_fallback() -> None:
    loader = SequenceLoader(
        _available_snapshot(),
        RuntimeError("private upstream failure"),
    )
    cache = CbrKeyRateCacheV1(loader=loader)
    cache.get(
        requested_from=DATE_FROM,
        requested_to=DATE_TO,
        checked_at=NOW,
    )

    result = cache.get(
        requested_from=DATE_FROM,
        requested_to=DATE_TO,
        checked_at=NOW + timedelta(minutes=10),
        force_refresh=True,
    )

    assert result.status is MacroCacheStatus.FRESH
    assert result.served_from_cache is True
    assert result.refresh_attempted is True
    assert result.refresh_succeeded is False
    assert result.cache_error_code is MacroCacheErrorCode.REFRESH_FAILED
    assert result.display_value_allowed is True


def test_stale_value_requires_explicit_allow_stale() -> None:
    loader = SequenceLoader(
        _available_snapshot(),
        _unavailable_snapshot(
            retrieved_at=NOW + timedelta(hours=2),
            error_code=MacroDataErrorCode.NETWORK_ERROR,
        ),
        _unavailable_snapshot(
            retrieved_at=NOW + timedelta(hours=2),
            error_code=MacroDataErrorCode.NETWORK_ERROR,
        ),
    )
    cache = CbrKeyRateCacheV1(
        loader=loader,
        fresh_seconds=3_600,
        stale_seconds=86_400,
    )
    cache.get(
        requested_from=DATE_FROM,
        requested_to=DATE_TO,
        checked_at=NOW,
    )

    blocked = cache.get(
        requested_from=DATE_FROM,
        requested_to=DATE_TO,
        checked_at=NOW + timedelta(hours=2),
    )
    allowed = cache.get(
        requested_from=DATE_FROM,
        requested_to=DATE_TO,
        checked_at=NOW + timedelta(hours=2),
        allow_stale=True,
    )

    assert blocked.status is MacroCacheStatus.UNAVAILABLE
    assert blocked.snapshot is None
    assert blocked.stale_available is True
    assert blocked.cache_error_code is MacroCacheErrorCode.STALE_NOT_ALLOWED
    assert blocked.display_value_allowed is False
    assert allowed.status is MacroCacheStatus.STALE
    assert allowed.snapshot is not None
    assert allowed.stale_value_exposed is True
    assert allowed.display_value_allowed is True
    assert allowed.source_error_code is MacroDataErrorCode.NETWORK_ERROR


def test_expired_entry_is_pruned_and_never_exposed() -> None:
    loader = SequenceLoader(
        _available_snapshot(),
        RuntimeError("refresh failed"),
    )
    cache = CbrKeyRateCacheV1(
        loader=loader,
        fresh_seconds=60,
        stale_seconds=120,
    )
    cache.get(
        requested_from=DATE_FROM,
        requested_to=DATE_TO,
        checked_at=NOW,
    )

    result = cache.get(
        requested_from=DATE_FROM,
        requested_to=DATE_TO,
        checked_at=NOW + timedelta(seconds=121),
        allow_stale=True,
    )

    assert result.status is MacroCacheStatus.UNAVAILABLE
    assert result.snapshot is None
    assert result.stale_available is False
    assert result.cache_error_code is MacroCacheErrorCode.REFRESH_FAILED
    assert cache.active_entry_count(checked_at=NOW + timedelta(seconds=121)) == 0


def test_unavailable_source_without_cache_is_redacted() -> None:
    loader = SequenceLoader(
        _unavailable_snapshot(error_code=MacroDataErrorCode.HTTP_ERROR)
    )
    cache = CbrKeyRateCacheV1(loader=loader)

    result = cache.get(
        requested_from=DATE_FROM,
        requested_to=DATE_TO,
        checked_at=NOW,
    )

    assert result.status is MacroCacheStatus.UNAVAILABLE
    assert result.source_error_code is MacroDataErrorCode.HTTP_ERROR
    assert result.cache_error_code is MacroCacheErrorCode.EMPTY
    assert result.snapshot is None
    assert result.raw_xml_stored is False


def test_invalid_type_range_and_future_snapshot_fail_closed() -> None:
    wrong_range = _available_snapshot(
        requested_from=date(2025, 1, 1),
        requested_to=DATE_TO,
    )
    future = _available_snapshot(retrieved_at=NOW + timedelta(minutes=2))
    cases: tuple[tuple[object, MacroCacheErrorCode], ...] = (
        ({"raw": "payload"}, MacroCacheErrorCode.REFRESH_TYPE_INVALID),
        (wrong_range, MacroCacheErrorCode.REFRESH_RANGE_MISMATCH),
        (future, MacroCacheErrorCode.REFRESH_FROM_FUTURE),
    )

    for value, expected in cases:
        cache = CbrKeyRateCacheV1(loader=SequenceLoader(value))
        result = cache.get(
            requested_from=DATE_FROM,
            requested_to=DATE_TO,
            checked_at=NOW,
        )
        assert result.status is MacroCacheStatus.UNAVAILABLE
        assert result.cache_error_code is expected
        assert result.snapshot is None


def test_source_returning_old_available_data_is_explicitly_stale() -> None:
    old = _available_snapshot(retrieved_at=NOW - timedelta(hours=2))
    allowed = CbrKeyRateCacheV1(
        loader=SequenceLoader(old),
        fresh_seconds=3_600,
        stale_seconds=86_400,
    ).get(
        requested_from=DATE_FROM,
        requested_to=DATE_TO,
        checked_at=NOW,
        allow_stale=True,
    )
    blocked = CbrKeyRateCacheV1(
        loader=SequenceLoader(old),
        fresh_seconds=3_600,
        stale_seconds=86_400,
    ).get(
        requested_from=DATE_FROM,
        requested_to=DATE_TO,
        checked_at=NOW,
        allow_stale=False,
    )

    assert allowed.status is MacroCacheStatus.STALE
    assert allowed.cache_error_code is MacroCacheErrorCode.REFRESH_STALE
    assert blocked.status is MacroCacheStatus.UNAVAILABLE
    assert blocked.cache_error_code is MacroCacheErrorCode.STALE_NOT_ALLOWED


def test_capacity_evicts_oldest_exact_range() -> None:
    def dynamic(start: date, end: date, checked: datetime) -> CbrKeyRateSnapshotV1:
        return _available_snapshot(
            requested_from=start,
            requested_to=end,
            retrieved_at=checked,
        )

    loader = SequenceLoader(dynamic, dynamic, dynamic, dynamic)
    cache = CbrKeyRateCacheV1(loader=loader, capacity=2)
    ranges = (
        (date(2026, 1, 1), date(2026, 1, 31)),
        (date(2026, 2, 1), date(2026, 2, 28)),
        (date(2026, 3, 1), date(2026, 3, 31)),
    )
    for start, end in ranges:
        cache.get(
            requested_from=start,
            requested_to=end,
            checked_at=NOW,
        )

    assert cache.active_entry_count(checked_at=NOW) == 2
    cache.get(
        requested_from=ranges[0][0],
        requested_to=ranges[0][1],
        checked_at=NOW,
    )
    assert loader.calls == 4


def test_concurrent_reads_perform_one_single_flight_refresh() -> None:
    barrier = Barrier(6)
    call_lock = Lock()
    calls = 0

    def loader(
        *,
        requested_from: date,
        requested_to: date,
        retrieved_at: datetime,
    ) -> CbrKeyRateSnapshotV1:
        nonlocal calls
        with call_lock:
            calls += 1
        time.sleep(0.05)
        return _available_snapshot(
            requested_from=requested_from,
            requested_to=requested_to,
            retrieved_at=retrieved_at,
        )

    cache = CbrKeyRateCacheV1(loader=loader)

    def worker() -> CbrKeyRateCacheResultV1:
        barrier.wait()
        return cache.get(
            requested_from=DATE_FROM,
            requested_to=DATE_TO,
            checked_at=NOW,
        )

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(worker) for _ in range(6)]
        results = [future.result() for future in futures]

    assert calls == 1
    assert all(result.status is MacroCacheStatus.FRESH for result in results)
    assert sum(result.refresh_attempted for result in results) == 1


def test_clear_restart_flags_and_input_guards() -> None:
    cache = CbrKeyRateCacheV1(loader=SequenceLoader(_available_snapshot()))
    cache.get(
        requested_from=DATE_FROM,
        requested_to=DATE_TO,
        checked_at=NOW,
    )
    assert cache.active_entry_count(checked_at=NOW) == 1
    cache.clear()
    assert cache.active_entry_count(checked_at=NOW) == 0
    assert CbrKeyRateCacheV1(loader=SequenceLoader()).active_entry_count(
        checked_at=NOW
    ) == 0

    with pytest.raises(CbrKeyRateCacheError):
        cache.get(
            requested_from=DATE_TO,
            requested_to=DATE_FROM,
            checked_at=NOW,
        )
    with pytest.raises(CbrKeyRateCacheError):
        cache.get(
            requested_from=DATE_FROM,
            requested_to=DATE_TO,
            checked_at=NOW,
            allow_stale=1,  # type: ignore[arg-type]
        )


def test_cache_contract_rejects_silent_stale_display() -> None:
    snapshot = _available_snapshot()
    with pytest.raises(ValidationError):
        CbrKeyRateCacheResultV1(
            requested_from=DATE_FROM,
            requested_to=DATE_TO,
            checked_at=NOW + timedelta(hours=2),
            status=MacroCacheStatus.STALE,
            snapshot=snapshot,
            age_seconds=7_200,
            fresh_until=NOW + timedelta(hours=1),
            stale_until=NOW + timedelta(days=1),
            served_from_cache=True,
            stale_available=True,
            stale_value_exposed=False,
            refresh_attempted=True,
            refresh_succeeded=False,
            cache_error_code=MacroCacheErrorCode.REFRESH_FAILED,
            display_value_allowed=True,
        )


def test_cache_has_no_route_or_broker_write_surface() -> None:
    import omni_cio.market.cbr_key_rate_cache_v1 as module

    assert not hasattr(module, "app")
    assert not hasattr(module, "router")
    assert not hasattr(module, "create_order")
    assert not hasattr(module, "post_order")
