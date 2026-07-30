from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from threading import RLock

from omni_cio.contracts.v1.macro import (
    CbrKeyRateCacheResultV1,
    CbrKeyRateSnapshotV1,
    MacroCacheErrorCode,
    MacroCacheStatus,
    MacroDataErrorCode,
    MacroDataStatus,
)
from omni_cio.market.cbr_key_rate_v1 import fetch_cbr_key_rate


DEFAULT_CBR_KEY_RATE_CACHE_FRESH_SECONDS = 3_600
DEFAULT_CBR_KEY_RATE_CACHE_STALE_SECONDS = 86_400
DEFAULT_CBR_KEY_RATE_CACHE_CAPACITY = 16
DEFAULT_CBR_KEY_RATE_CACHE_FUTURE_TOLERANCE_SECONDS = 30


class CbrKeyRateCacheError(ValueError):
    """The key-rate cache cannot be configured or queried safely."""


CbrKeyRateLoaderV1 = Callable[..., CbrKeyRateSnapshotV1]
CacheKeyV1 = tuple[date, date]


@dataclass(frozen=True, slots=True)
class _CbrKeyRateCacheEntryV1:
    snapshot: CbrKeyRateSnapshotV1
    fresh_until: datetime
    stale_until: datetime


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if (
        not isinstance(result, datetime)
        or result.tzinfo is None
        or result.utcoffset() is None
    ):
        raise CbrKeyRateCacheError("CBR_KEY_RATE_CACHE_TIMESTAMP_INVALID")
    return result.astimezone(timezone.utc)


def _validate_range(requested_from: date, requested_to: date) -> CacheKeyV1:
    if (
        not isinstance(requested_from, date)
        or not isinstance(requested_to, date)
        or requested_from > requested_to
    ):
        raise CbrKeyRateCacheError("CBR_KEY_RATE_CACHE_RANGE_INVALID")
    return requested_from, requested_to


def _age_seconds(snapshot: CbrKeyRateSnapshotV1, checked_at: datetime) -> int:
    return max(0, int((checked_at - snapshot.retrieved_at).total_seconds()))


class CbrKeyRateCacheV1:
    """Bounded single-flight cache with explicit stale/unavailable semantics."""

    internal_only = True
    raw_xml_stored = False
    credentials_present = False
    full_account_identifier_present = False
    broker_write_called = False
    trade_authorized = False
    order_created = False
    trading_methods = False

    def __init__(
        self,
        *,
        loader: CbrKeyRateLoaderV1 = fetch_cbr_key_rate,
        fresh_seconds: int = DEFAULT_CBR_KEY_RATE_CACHE_FRESH_SECONDS,
        stale_seconds: int = DEFAULT_CBR_KEY_RATE_CACHE_STALE_SECONDS,
        capacity: int = DEFAULT_CBR_KEY_RATE_CACHE_CAPACITY,
        future_tolerance_seconds: int = (
            DEFAULT_CBR_KEY_RATE_CACHE_FUTURE_TOLERANCE_SECONDS
        ),
    ) -> None:
        if not callable(loader):
            raise CbrKeyRateCacheError("CBR_KEY_RATE_CACHE_LOADER_INVALID")
        if not 1 <= fresh_seconds <= 86_400:
            raise CbrKeyRateCacheError("CBR_KEY_RATE_CACHE_FRESH_TTL_INVALID")
        if not fresh_seconds <= stale_seconds <= 604_800:
            raise CbrKeyRateCacheError("CBR_KEY_RATE_CACHE_STALE_TTL_INVALID")
        if not 1 <= capacity <= 256:
            raise CbrKeyRateCacheError("CBR_KEY_RATE_CACHE_CAPACITY_INVALID")
        if not 0 <= future_tolerance_seconds <= 3_600:
            raise CbrKeyRateCacheError(
                "CBR_KEY_RATE_CACHE_FUTURE_TOLERANCE_INVALID"
            )
        self._loader = loader
        self._fresh_ttl = timedelta(seconds=fresh_seconds)
        self._stale_ttl = timedelta(seconds=stale_seconds)
        self._future_tolerance = timedelta(seconds=future_tolerance_seconds)
        self._capacity = capacity
        self._entries: OrderedDict[CacheKeyV1, _CbrKeyRateCacheEntryV1] = (
            OrderedDict()
        )
        self._lock = RLock()

    @property
    def fresh_seconds(self) -> int:
        return int(self._fresh_ttl.total_seconds())

    @property
    def stale_seconds(self) -> int:
        return int(self._stale_ttl.total_seconds())

    @property
    def capacity(self) -> int:
        return self._capacity

    def _prune(self, checked_at: datetime) -> None:
        expired = [
            key
            for key, entry in self._entries.items()
            if checked_at >= entry.stale_until
        ]
        for key in expired:
            self._entries.pop(key, None)

    def _entry_for(
        self,
        key: CacheKeyV1,
    ) -> _CbrKeyRateCacheEntryV1 | None:
        entry = self._entries.get(key)
        if entry is not None:
            self._entries.move_to_end(key)
        return entry

    def _store(
        self,
        key: CacheKeyV1,
        snapshot: CbrKeyRateSnapshotV1,
    ) -> _CbrKeyRateCacheEntryV1:
        entry = _CbrKeyRateCacheEntryV1(
            snapshot=snapshot,
            fresh_until=snapshot.retrieved_at + self._fresh_ttl,
            stale_until=snapshot.retrieved_at + self._stale_ttl,
        )
        self._entries[key] = entry
        self._entries.move_to_end(key)
        while len(self._entries) > self._capacity:
            self._entries.popitem(last=False)
        return entry

    def _fresh_result(
        self,
        *,
        key: CacheKeyV1,
        entry: _CbrKeyRateCacheEntryV1,
        checked_at: datetime,
        served_from_cache: bool,
        refresh_attempted: bool,
        refresh_succeeded: bool,
        source_error_code: MacroDataErrorCode | None = None,
        cache_error_code: MacroCacheErrorCode | None = None,
    ) -> CbrKeyRateCacheResultV1:
        return CbrKeyRateCacheResultV1(
            requested_from=key[0],
            requested_to=key[1],
            checked_at=checked_at,
            status=MacroCacheStatus.FRESH,
            snapshot=entry.snapshot,
            age_seconds=_age_seconds(entry.snapshot, checked_at),
            fresh_until=entry.fresh_until,
            stale_until=entry.stale_until,
            served_from_cache=served_from_cache,
            stale_available=False,
            stale_value_exposed=False,
            refresh_attempted=refresh_attempted,
            refresh_succeeded=refresh_succeeded,
            source_error_code=source_error_code,
            cache_error_code=cache_error_code,
            display_value_allowed=True,
        )

    def _stale_or_unavailable_result(
        self,
        *,
        key: CacheKeyV1,
        entry: _CbrKeyRateCacheEntryV1 | None,
        checked_at: datetime,
        allow_stale: bool,
        source_error_code: MacroDataErrorCode | None,
        cache_error_code: MacroCacheErrorCode,
    ) -> CbrKeyRateCacheResultV1:
        if entry is not None and checked_at < entry.fresh_until:
            return self._fresh_result(
                key=key,
                entry=entry,
                checked_at=checked_at,
                served_from_cache=True,
                refresh_attempted=True,
                refresh_succeeded=False,
                source_error_code=source_error_code,
                cache_error_code=cache_error_code,
            )
        stale_available = entry is not None and checked_at < entry.stale_until
        if stale_available and allow_stale and entry is not None:
            return CbrKeyRateCacheResultV1(
                requested_from=key[0],
                requested_to=key[1],
                checked_at=checked_at,
                status=MacroCacheStatus.STALE,
                snapshot=entry.snapshot,
                age_seconds=_age_seconds(entry.snapshot, checked_at),
                fresh_until=entry.fresh_until,
                stale_until=entry.stale_until,
                served_from_cache=True,
                stale_available=True,
                stale_value_exposed=True,
                refresh_attempted=True,
                refresh_succeeded=False,
                source_error_code=source_error_code,
                cache_error_code=cache_error_code,
                display_value_allowed=True,
            )
        effective_error = (
            MacroCacheErrorCode.STALE_NOT_ALLOWED
            if stale_available and not allow_stale
            else cache_error_code
        )
        return CbrKeyRateCacheResultV1(
            requested_from=key[0],
            requested_to=key[1],
            checked_at=checked_at,
            status=MacroCacheStatus.UNAVAILABLE,
            snapshot=None,
            age_seconds=None,
            fresh_until=entry.fresh_until if stale_available and entry else None,
            stale_until=entry.stale_until if stale_available and entry else None,
            served_from_cache=False,
            stale_available=stale_available,
            stale_value_exposed=False,
            refresh_attempted=True,
            refresh_succeeded=False,
            source_error_code=source_error_code,
            cache_error_code=effective_error,
            display_value_allowed=False,
        )

    def get(
        self,
        *,
        requested_from: date,
        requested_to: date,
        checked_at: datetime | None = None,
        force_refresh: bool = False,
        allow_stale: bool = False,
    ) -> CbrKeyRateCacheResultV1:
        """Return one explicit fresh/stale/unavailable view for an exact range."""
        key = _validate_range(requested_from, requested_to)
        now = _aware_utc(checked_at)
        if type(force_refresh) is not bool or type(allow_stale) is not bool:
            raise CbrKeyRateCacheError("CBR_KEY_RATE_CACHE_FLAG_INVALID")

        with self._lock:
            self._prune(now)
            entry = self._entry_for(key)
            if entry is not None and now < entry.fresh_until and not force_refresh:
                return self._fresh_result(
                    key=key,
                    entry=entry,
                    checked_at=now,
                    served_from_cache=True,
                    refresh_attempted=False,
                    refresh_succeeded=False,
                )

            try:
                snapshot = self._loader(
                    requested_from=requested_from,
                    requested_to=requested_to,
                    retrieved_at=now,
                )
            except Exception:
                return self._stale_or_unavailable_result(
                    key=key,
                    entry=entry,
                    checked_at=now,
                    allow_stale=allow_stale,
                    source_error_code=None,
                    cache_error_code=MacroCacheErrorCode.REFRESH_FAILED,
                )

            if not isinstance(snapshot, CbrKeyRateSnapshotV1):
                return self._stale_or_unavailable_result(
                    key=key,
                    entry=entry,
                    checked_at=now,
                    allow_stale=allow_stale,
                    source_error_code=None,
                    cache_error_code=MacroCacheErrorCode.REFRESH_TYPE_INVALID,
                )
            if (
                snapshot.requested_from != requested_from
                or snapshot.requested_to != requested_to
            ):
                return self._stale_or_unavailable_result(
                    key=key,
                    entry=entry,
                    checked_at=now,
                    allow_stale=allow_stale,
                    source_error_code=snapshot.error_code,
                    cache_error_code=MacroCacheErrorCode.REFRESH_RANGE_MISMATCH,
                )
            if snapshot.retrieved_at - now > self._future_tolerance:
                return self._stale_or_unavailable_result(
                    key=key,
                    entry=entry,
                    checked_at=now,
                    allow_stale=allow_stale,
                    source_error_code=snapshot.error_code,
                    cache_error_code=MacroCacheErrorCode.REFRESH_FROM_FUTURE,
                )
            if snapshot.status is MacroDataStatus.UNAVAILABLE:
                return self._stale_or_unavailable_result(
                    key=key,
                    entry=entry,
                    checked_at=now,
                    allow_stale=allow_stale,
                    source_error_code=snapshot.error_code,
                    cache_error_code=(
                        MacroCacheErrorCode.EMPTY
                        if entry is None
                        else MacroCacheErrorCode.EXPIRED
                    ),
                )

            refreshed = self._store(key, snapshot)
            if now < refreshed.fresh_until:
                return self._fresh_result(
                    key=key,
                    entry=refreshed,
                    checked_at=now,
                    served_from_cache=False,
                    refresh_attempted=True,
                    refresh_succeeded=True,
                )
            selected_entry: _CbrKeyRateCacheEntryV1 | None = refreshed
            if now >= refreshed.stale_until:
                self._entries.pop(key, None)
                selected_entry = None
            return self._stale_or_unavailable_result(
                key=key,
                entry=selected_entry,
                checked_at=now,
                allow_stale=allow_stale,
                source_error_code=None,
                cache_error_code=MacroCacheErrorCode.REFRESH_STALE,
            )

    def active_entry_count(self, *, checked_at: datetime | None = None) -> int:
        now = _aware_utc(checked_at)
        with self._lock:
            self._prune(now)
            return len(self._entries)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
