from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from threading import Lock
from typing import Any, cast

import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1.market import MarketQuoteV1, MarketSourceV1, SourceAuthority
from omni_cio.contracts.v1.moex import (
    MoexIssQuoteErrorCode,
    MoexIssQuoteStatus,
    MoexIssTqbrQuoteCacheResultV1,
    MoexIssTqbrQuoteSnapshotV1,
    MoexQuoteCacheErrorCode,
    MoexQuoteCacheStatus,
)
from omni_cio.market.moex_iss_quote_cache_v1 import (
    MoexIssQuoteCacheError,
    MoexIssTqbrQuoteCacheV1,
)


NOW = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)


def _available_snapshot(
    *,
    secid: str = "SBER",
    retrieved_at: datetime = NOW,
    as_of: datetime | None = None,
    last_price: Decimal = Decimal("310.25"),
) -> MoexIssTqbrQuoteSnapshotV1:
    normalized = secid.upper()
    source = MarketSourceV1(
        provider="Moscow Exchange ISS",
        authority=SourceAuthority.OFFICIAL,
        retrieved_at=retrieved_at,
        source_id="ISS.stock.shares.TQBR.marketdata",
    )
    quote = MarketQuoteV1(
        instrument_key=f"MOEX:TQBR:{normalized}",
        currency="RUB",
        as_of=as_of or retrieved_at,
        source=source,
        last_price=last_price,
        best_bid=last_price - Decimal("0.05"),
        best_ask=last_price + Decimal("0.05"),
    )
    return MoexIssTqbrQuoteSnapshotV1(
        secid=normalized,
        retrieved_at=retrieved_at,
        status=MoexIssQuoteStatus.AVAILABLE,
        source=source,
        quote=quote,
        short_name=normalized,
        lot_size=10,
        decimals=2,
    )


def _unavailable_snapshot(
    *,
    secid: str = "SBER",
    retrieved_at: datetime = NOW,
    error_code: MoexIssQuoteErrorCode = MoexIssQuoteErrorCode.NETWORK_ERROR,
) -> MoexIssTqbrQuoteSnapshotV1:
    return MoexIssTqbrQuoteSnapshotV1(
        secid=secid,
        retrieved_at=retrieved_at,
        status=MoexIssQuoteStatus.UNAVAILABLE,
        error_code=error_code,
    )


def test_cache_result_contract_rejects_inconsistent_states() -> None:
    snapshot = _available_snapshot()
    fresh = MoexIssTqbrQuoteCacheResultV1(
        secid="sber",
        checked_at=NOW,
        status=MoexQuoteCacheStatus.FRESH,
        snapshot=snapshot,
        age_seconds=0,
        fresh_until=NOW + timedelta(seconds=60),
        stale_until=NOW + timedelta(seconds=900),
        refresh_attempted=True,
        refresh_succeeded=True,
        display_value_allowed=True,
    )

    assert fresh.secid == "SBER"
    assert fresh.public_unauthenticated_feed is True
    assert fresh.delayed_data_possible is True
    assert fresh.realtime_guaranteed is False
    assert fresh.informational_use_only is True
    assert fresh.trading_methods is False

    with pytest.raises(ValidationError):
        MoexIssTqbrQuoteCacheResultV1(
            secid="SBER",
            checked_at=NOW,
            status=MoexQuoteCacheStatus.STALE,
            snapshot=snapshot,
            age_seconds=61,
            fresh_until=NOW + timedelta(seconds=60),
            stale_until=NOW + timedelta(seconds=900),
            served_from_cache=True,
            stale_available=True,
            stale_value_exposed=False,
            refresh_attempted=True,
            refresh_succeeded=False,
            cache_error_code=MoexQuoteCacheErrorCode.REFRESH_FAILED,
            display_value_allowed=True,
        )

    with pytest.raises(ValidationError):
        MoexIssTqbrQuoteCacheResultV1(
            secid="SBER",
            checked_at=NOW,
            status=MoexQuoteCacheStatus.UNAVAILABLE,
            refresh_attempted=False,
            cache_error_code=MoexQuoteCacheErrorCode.EMPTY,
        )


def test_first_refresh_and_fresh_hit_are_explicit() -> None:
    calls = 0

    def loader(*, secid: str, retrieved_at: datetime) -> MoexIssTqbrQuoteSnapshotV1:
        nonlocal calls
        calls += 1
        return _available_snapshot(secid=secid, retrieved_at=retrieved_at)

    cache = MoexIssTqbrQuoteCacheV1(loader=loader)
    refreshed = cache.get(secid=" sber ", checked_at=NOW)
    hit = cache.get(secid="SBER", checked_at=NOW + timedelta(seconds=30))

    assert calls == 1
    assert refreshed.status is MoexQuoteCacheStatus.FRESH
    assert refreshed.served_from_cache is False
    assert refreshed.refresh_attempted is True
    assert refreshed.refresh_succeeded is True
    assert hit.status is MoexQuoteCacheStatus.FRESH
    assert hit.served_from_cache is True
    assert hit.refresh_attempted is False
    assert hit.refresh_succeeded is False
    assert hit.age_seconds == 30


def test_quote_age_uses_as_of_but_ttl_uses_retrieved_at() -> None:
    market_time = NOW - timedelta(minutes=15)

    def loader(*, secid: str, retrieved_at: datetime) -> MoexIssTqbrQuoteSnapshotV1:
        return _available_snapshot(
            secid=secid,
            retrieved_at=retrieved_at,
            as_of=market_time,
        )

    result = MoexIssTqbrQuoteCacheV1(loader=loader).get(
        secid="SBER",
        checked_at=NOW,
    )

    assert result.age_seconds == 900
    assert result.fresh_until == NOW + timedelta(seconds=60)
    assert result.stale_until == NOW + timedelta(seconds=900)
    assert result.realtime_guaranteed is False


def test_failed_force_refresh_keeps_still_fresh_cached_snapshot_explicit() -> None:
    calls = 0

    def loader(*, secid: str, retrieved_at: datetime) -> MoexIssTqbrQuoteSnapshotV1:
        nonlocal calls
        calls += 1
        if calls == 1:
            return _available_snapshot(secid=secid, retrieved_at=retrieved_at)
        raise RuntimeError("private upstream failure")

    cache = MoexIssTqbrQuoteCacheV1(loader=loader)
    original = cache.get(secid="SBER", checked_at=NOW)
    fallback = cache.get(
        secid="SBER",
        checked_at=NOW + timedelta(seconds=30),
        force_refresh=True,
    )

    assert original.snapshot is not None
    assert fallback.status is MoexQuoteCacheStatus.FRESH
    assert fallback.snapshot == original.snapshot
    assert fallback.served_from_cache is True
    assert fallback.refresh_attempted is True
    assert fallback.refresh_succeeded is False
    assert fallback.cache_error_code is MoexQuoteCacheErrorCode.REFRESH_FAILED


def test_stale_value_requires_explicit_allow_stale() -> None:
    calls = 0

    def loader(*, secid: str, retrieved_at: datetime) -> MoexIssTqbrQuoteSnapshotV1:
        nonlocal calls
        calls += 1
        if calls == 1:
            return _available_snapshot(secid=secid, retrieved_at=retrieved_at)
        return _unavailable_snapshot(secid=secid, retrieved_at=retrieved_at)

    blocked_cache = MoexIssTqbrQuoteCacheV1(loader=loader)
    blocked_cache.get(secid="SBER", checked_at=NOW)
    blocked = blocked_cache.get(
        secid="SBER",
        checked_at=NOW + timedelta(seconds=61),
        allow_stale=False,
    )

    assert blocked.status is MoexQuoteCacheStatus.UNAVAILABLE
    assert blocked.snapshot is None
    assert blocked.stale_available is True
    assert blocked.stale_value_exposed is False
    assert blocked.display_value_allowed is False
    assert blocked.cache_error_code is MoexQuoteCacheErrorCode.STALE_NOT_ALLOWED
    assert blocked.source_error_code is MoexIssQuoteErrorCode.NETWORK_ERROR

    allowed_calls = 0

    def allowed_loader(
        *,
        secid: str,
        retrieved_at: datetime,
    ) -> MoexIssTqbrQuoteSnapshotV1:
        nonlocal allowed_calls
        allowed_calls += 1
        if allowed_calls == 1:
            return _available_snapshot(secid=secid, retrieved_at=retrieved_at)
        return _unavailable_snapshot(secid=secid, retrieved_at=retrieved_at)

    allowed_cache = MoexIssTqbrQuoteCacheV1(loader=allowed_loader)
    allowed_cache.get(secid="SBER", checked_at=NOW)
    allowed = allowed_cache.get(
        secid="SBER",
        checked_at=NOW + timedelta(seconds=61),
        allow_stale=True,
    )

    assert allowed.status is MoexQuoteCacheStatus.STALE
    assert allowed.snapshot is not None
    assert allowed.served_from_cache is True
    assert allowed.stale_available is True
    assert allowed.stale_value_exposed is True
    assert allowed.display_value_allowed is True
    assert allowed.source_error_code is MoexIssQuoteErrorCode.NETWORK_ERROR


def test_expired_entry_is_pruned_and_not_exposed() -> None:
    calls = 0

    def loader(*, secid: str, retrieved_at: datetime) -> MoexIssTqbrQuoteSnapshotV1:
        nonlocal calls
        calls += 1
        if calls == 1:
            return _available_snapshot(secid=secid, retrieved_at=retrieved_at)
        return _unavailable_snapshot(secid=secid, retrieved_at=retrieved_at)

    cache = MoexIssTqbrQuoteCacheV1(loader=loader)
    cache.get(secid="SBER", checked_at=NOW)
    expired = cache.get(
        secid="SBER",
        checked_at=NOW + timedelta(seconds=900),
        allow_stale=True,
    )

    assert expired.status is MoexQuoteCacheStatus.UNAVAILABLE
    assert expired.stale_available is False
    assert expired.snapshot is None
    assert expired.fresh_until is None
    assert expired.stale_until is None
    assert expired.cache_error_code is MoexQuoteCacheErrorCode.EMPTY
    assert cache.active_entry_count(checked_at=NOW + timedelta(seconds=900)) == 0


def test_single_flight_refresh_under_concurrency() -> None:
    calls = 0
    counter_lock = Lock()

    def loader(*, secid: str, retrieved_at: datetime) -> MoexIssTqbrQuoteSnapshotV1:
        nonlocal calls
        with counter_lock:
            calls += 1
        return _available_snapshot(secid=secid, retrieved_at=retrieved_at)

    cache = MoexIssTqbrQuoteCacheV1(loader=loader)
    with ThreadPoolExecutor(max_workers=12) as executor:
        results = list(
            executor.map(
                lambda _: cache.get(secid="SBER", checked_at=NOW),
                range(12),
            )
        )

    assert calls == 1
    assert all(result.status is MoexQuoteCacheStatus.FRESH for result in results)
    assert sum(not result.served_from_cache for result in results) == 1
    assert sum(result.served_from_cache for result in results) == 11


def test_identity_type_and_future_refresh_fail_closed() -> None:
    wrong_identity = MoexIssTqbrQuoteCacheV1(
        loader=lambda **_: _available_snapshot(secid="GAZP")
    ).get(secid="SBER", checked_at=NOW)
    assert wrong_identity.status is MoexQuoteCacheStatus.UNAVAILABLE
    assert (
        wrong_identity.cache_error_code
        is MoexQuoteCacheErrorCode.REFRESH_IDENTITY_MISMATCH
    )

    wrong_type = MoexIssTqbrQuoteCacheV1(
        loader=cast(Any, lambda **_: {"status": "available"})
    ).get(secid="SBER", checked_at=NOW)
    assert wrong_type.cache_error_code is MoexQuoteCacheErrorCode.REFRESH_TYPE_INVALID

    future = MoexIssTqbrQuoteCacheV1(
        loader=lambda **_: _available_snapshot(
            retrieved_at=NOW + timedelta(seconds=31),
            as_of=NOW + timedelta(seconds=31),
        )
    ).get(secid="SBER", checked_at=NOW)
    assert future.cache_error_code is MoexQuoteCacheErrorCode.REFRESH_FROM_FUTURE


def test_newly_loaded_old_snapshot_is_not_silently_fresh() -> None:
    old_retrieval = NOW - timedelta(seconds=61)

    def loader(*, secid: str, retrieved_at: datetime) -> MoexIssTqbrQuoteSnapshotV1:
        return _available_snapshot(
            secid=secid,
            retrieved_at=old_retrieval,
            as_of=old_retrieval - timedelta(minutes=15),
        )

    blocked = MoexIssTqbrQuoteCacheV1(loader=loader).get(
        secid="SBER",
        checked_at=NOW,
        allow_stale=False,
    )
    assert blocked.status is MoexQuoteCacheStatus.UNAVAILABLE
    assert blocked.stale_available is True
    assert blocked.cache_error_code is MoexQuoteCacheErrorCode.STALE_NOT_ALLOWED

    allowed = MoexIssTqbrQuoteCacheV1(loader=loader).get(
        secid="SBER",
        checked_at=NOW,
        allow_stale=True,
    )
    assert allowed.status is MoexQuoteCacheStatus.STALE
    assert allowed.cache_error_code is MoexQuoteCacheErrorCode.REFRESH_STALE


def test_capacity_eviction_key_isolation_clear_and_restart_state() -> None:
    calls: list[str] = []

    def loader(*, secid: str, retrieved_at: datetime) -> MoexIssTqbrQuoteSnapshotV1:
        calls.append(secid)
        return _available_snapshot(secid=secid, retrieved_at=retrieved_at)

    cache = MoexIssTqbrQuoteCacheV1(loader=loader, capacity=2)
    cache.get(secid="SBER", checked_at=NOW)
    cache.get(secid="GAZP", checked_at=NOW)
    cache.get(secid="LKOH", checked_at=NOW)

    assert cache.active_entry_count(checked_at=NOW) == 2
    cache.get(secid="SBER", checked_at=NOW)
    assert calls == ["SBER", "GAZP", "LKOH", "SBER"]

    cache.clear()
    assert cache.active_entry_count(checked_at=NOW) == 0
    restarted = MoexIssTqbrQuoteCacheV1(loader=loader)
    assert restarted.active_entry_count(checked_at=NOW) == 0


def test_configuration_flags_and_input_guards_fail_before_loader() -> None:
    with pytest.raises(MoexIssQuoteCacheError):
        MoexIssTqbrQuoteCacheV1(fresh_seconds=True)
    with pytest.raises(MoexIssQuoteCacheError):
        MoexIssTqbrQuoteCacheV1(fresh_seconds=61, stale_seconds=60)
    with pytest.raises(MoexIssQuoteCacheError):
        MoexIssTqbrQuoteCacheV1(capacity=0)

    called = False

    def loader(**_: object) -> MoexIssTqbrQuoteSnapshotV1:
        nonlocal called
        called = True
        return _available_snapshot()

    cache = MoexIssTqbrQuoteCacheV1(loader=loader)
    with pytest.raises(MoexIssQuoteCacheError):
        cache.get(secid="../SBER", checked_at=NOW)
    with pytest.raises(MoexIssQuoteCacheError):
        cache.get(secid="SBER", checked_at=NOW, allow_stale=cast(Any, 1))
    assert called is False


def test_cache_module_has_no_route_startup_or_broker_write_surface() -> None:
    import omni_cio.market.moex_iss_quote_cache_v1 as module

    assert not hasattr(module, "app")
    assert not hasattr(module, "router")
    assert not hasattr(module, "startup")
    assert not hasattr(module, "create_order")
    assert not hasattr(module, "post_order")
    assert not hasattr(module, "cancel_order")
