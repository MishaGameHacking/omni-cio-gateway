from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
from threading import RLock

from omni_cio.contracts.v1.moex import (
    MoexIssQuoteErrorCode,
    MoexIssQuoteStatus,
    MoexIssTqbrQuoteCacheResultV1,
    MoexIssTqbrQuoteSnapshotV1,
    MoexQuoteCacheErrorCode,
    MoexQuoteCacheStatus,
)
from omni_cio.market.moex_iss_quote_v1 import fetch_moex_iss_tqbr_quote


DEFAULT_MOEX_QUOTE_CACHE_FRESH_SECONDS = 60
DEFAULT_MOEX_QUOTE_CACHE_STALE_SECONDS = 900
DEFAULT_MOEX_QUOTE_CACHE_CAPACITY = 64
DEFAULT_MOEX_QUOTE_CACHE_FUTURE_TOLERANCE_SECONDS = 30

_SECID_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9._-]{0,35}$")


class MoexIssQuoteCacheError(ValueError):
    """The MOEX quote cache cannot be configured or queried safely."""


MoexIssQuoteLoaderV1 = Callable[..., MoexIssTqbrQuoteSnapshotV1]
MoexQuoteCacheKeyV1 = tuple[str, str]


@dataclass(frozen=True, slots=True)
class _MoexIssQuoteCacheEntryV1:
    snapshot: MoexIssTqbrQuoteSnapshotV1
    fresh_until: datetime
    stale_until: datetime


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if (
        not isinstance(result, datetime)
        or result.tzinfo is None
        or result.utcoffset() is None
    ):
        raise MoexIssQuoteCacheError("MOEX_QUOTE_CACHE_TIMESTAMP_INVALID")
    return result.astimezone(timezone.utc)


def _normalize_secid(value: str) -> str:
    if not isinstance(value, str):
        raise MoexIssQuoteCacheError("MOEX_QUOTE_CACHE_SECID_INVALID")
    normalized = value.strip().upper()
    if not _SECID_PATTERN.fullmatch(normalized):
        raise MoexIssQuoteCacheError("MOEX_QUOTE_CACHE_SECID_INVALID")
    return normalized


def _cache_key(secid: str) -> MoexQuoteCacheKeyV1:
    return "TQBR", _normalize_secid(secid)


def _age_seconds(
    snapshot: MoexIssTqbrQuoteSnapshotV1,
    checked_at: datetime,
) -> int:
    if snapshot.quote is None:
        raise MoexIssQuoteCacheError("MOEX_QUOTE_CACHE_SNAPSHOT_INVALID")
    return max(0, int((checked_at - snapshot.quote.as_of).total_seconds()))


class MoexIssTqbrQuoteCacheV1:
    """Bounded single-flight cache with explicit stale/unavailable semantics."""

    internal_only = True
    public_unauthenticated_feed = True
    delayed_data_possible = True
    realtime_guaranteed = False
    informational_use_only = True
    raw_json_stored = False
    credentials_present = False
    full_account_identifier_present = False
    broker_write_called = False
    trade_authorized = False
    order_created = False
    trading_methods = False

    def __init__(
        self,
        *,
        loader: MoexIssQuoteLoaderV1 = fetch_moex_iss_tqbr_quote,
        fresh_seconds: int = DEFAULT_MOEX_QUOTE_CACHE_FRESH_SECONDS,
        stale_seconds: int = DEFAULT_MOEX_QUOTE_CACHE_STALE_SECONDS,
        capacity: int = DEFAULT_MOEX_QUOTE_CACHE_CAPACITY,
        future_tolerance_seconds: int = (
            DEFAULT_MOEX_QUOTE_CACHE_FUTURE_TOLERANCE_SECONDS
        ),
    ) -> None:
        if not callable(loader):
            raise MoexIssQuoteCacheError("MOEX_QUOTE_CACHE_LOADER_INVALID")
        if (
            isinstance(fresh_seconds, bool)
            or not isinstance(fresh_seconds, int)
            or not 1 <= fresh_seconds <= 3_600
        ):
            raise MoexIssQuoteCacheError("MOEX_QUOTE_CACHE_FRESH_TTL_INVALID")
        if (
            isinstance(stale_seconds, bool)
            or not isinstance(stale_seconds, int)
            or not fresh_seconds <= stale_seconds <= 86_400
        ):
            raise MoexIssQuoteCacheError("MOEX_QUOTE_CACHE_STALE_TTL_INVALID")
        if (
            isinstance(capacity, bool)
            or not isinstance(capacity, int)
            or not 1 <= capacity <= 1_024
        ):
            raise MoexIssQuoteCacheError("MOEX_QUOTE_CACHE_CAPACITY_INVALID")
        if (
            isinstance(future_tolerance_seconds, bool)
            or not isinstance(future_tolerance_seconds, int)
            or not 0 <= future_tolerance_seconds <= 3_600
        ):
            raise MoexIssQuoteCacheError(
                "MOEX_QUOTE_CACHE_FUTURE_TOLERANCE_INVALID"
            )
        self._loader = loader
        self._fresh_ttl = timedelta(seconds=fresh_seconds)
        self._stale_ttl = timedelta(seconds=stale_seconds)
        self._future_tolerance = timedelta(seconds=future_tolerance_seconds)
        self._capacity = capacity
        self._entries: OrderedDict[
            MoexQuoteCacheKeyV1,
            _MoexIssQuoteCacheEntryV1,
        ] = OrderedDict()
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
        key: MoexQuoteCacheKeyV1,
    ) -> _MoexIssQuoteCacheEntryV1 | None:
        entry = self._entries.get(key)
        if entry is not None:
            self._entries.move_to_end(key)
        return entry

    def _store(
        self,
        key: MoexQuoteCacheKeyV1,
        snapshot: MoexIssTqbrQuoteSnapshotV1,
    ) -> _MoexIssQuoteCacheEntryV1:
        entry = _MoexIssQuoteCacheEntryV1(
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
        key: MoexQuoteCacheKeyV1,
        entry: _MoexIssQuoteCacheEntryV1,
        checked_at: datetime,
        served_from_cache: bool,
        refresh_attempted: bool,
        refresh_succeeded: bool,
        source_error_code: MoexIssQuoteErrorCode | None = None,
        cache_error_code: MoexQuoteCacheErrorCode | None = None,
    ) -> MoexIssTqbrQuoteCacheResultV1:
        return MoexIssTqbrQuoteCacheResultV1(
            secid=key[1],
            checked_at=checked_at,
            status=MoexQuoteCacheStatus.FRESH,
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
        key: MoexQuoteCacheKeyV1,
        entry: _MoexIssQuoteCacheEntryV1 | None,
        checked_at: datetime,
        allow_stale: bool,
        source_error_code: MoexIssQuoteErrorCode | None,
        cache_error_code: MoexQuoteCacheErrorCode,
    ) -> MoexIssTqbrQuoteCacheResultV1:
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
            return MoexIssTqbrQuoteCacheResultV1(
                secid=key[1],
                checked_at=checked_at,
                status=MoexQuoteCacheStatus.STALE,
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
            MoexQuoteCacheErrorCode.STALE_NOT_ALLOWED
            if stale_available and not allow_stale
            else cache_error_code
        )
        return MoexIssTqbrQuoteCacheResultV1(
            secid=key[1],
            checked_at=checked_at,
            status=MoexQuoteCacheStatus.UNAVAILABLE,
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

    @staticmethod
    def _identity_matches(
        snapshot: MoexIssTqbrQuoteSnapshotV1,
        key: MoexQuoteCacheKeyV1,
    ) -> bool:
        return (
            snapshot.secid == key[1]
            and snapshot.board_id == key[0]
            and (
                snapshot.quote is None
                or snapshot.quote.instrument_key == f"MOEX:{key[0]}:{key[1]}"
            )
        )

    def get(
        self,
        *,
        secid: str,
        checked_at: datetime | None = None,
        force_refresh: bool = False,
        allow_stale: bool = False,
    ) -> MoexIssTqbrQuoteCacheResultV1:
        """Return one explicit fresh/stale/unavailable view for exact TQBR SECID."""
        key = _cache_key(secid)
        now = _aware_utc(checked_at)
        if type(force_refresh) is not bool or type(allow_stale) is not bool:
            raise MoexIssQuoteCacheError("MOEX_QUOTE_CACHE_FLAG_INVALID")

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
                    secid=key[1],
                    retrieved_at=now,
                )
            except Exception:
                return self._stale_or_unavailable_result(
                    key=key,
                    entry=entry,
                    checked_at=now,
                    allow_stale=allow_stale,
                    source_error_code=None,
                    cache_error_code=MoexQuoteCacheErrorCode.REFRESH_FAILED,
                )

            if not isinstance(snapshot, MoexIssTqbrQuoteSnapshotV1):
                return self._stale_or_unavailable_result(
                    key=key,
                    entry=entry,
                    checked_at=now,
                    allow_stale=allow_stale,
                    source_error_code=None,
                    cache_error_code=MoexQuoteCacheErrorCode.REFRESH_TYPE_INVALID,
                )
            if not self._identity_matches(snapshot, key):
                return self._stale_or_unavailable_result(
                    key=key,
                    entry=entry,
                    checked_at=now,
                    allow_stale=allow_stale,
                    source_error_code=snapshot.error_code,
                    cache_error_code=(
                        MoexQuoteCacheErrorCode.REFRESH_IDENTITY_MISMATCH
                    ),
                )
            if snapshot.retrieved_at - now > self._future_tolerance:
                return self._stale_or_unavailable_result(
                    key=key,
                    entry=entry,
                    checked_at=now,
                    allow_stale=allow_stale,
                    source_error_code=snapshot.error_code,
                    cache_error_code=MoexQuoteCacheErrorCode.REFRESH_FROM_FUTURE,
                )
            if (
                snapshot.quote is not None
                and snapshot.quote.as_of - now > self._future_tolerance
            ):
                return self._stale_or_unavailable_result(
                    key=key,
                    entry=entry,
                    checked_at=now,
                    allow_stale=allow_stale,
                    source_error_code=snapshot.error_code,
                    cache_error_code=MoexQuoteCacheErrorCode.REFRESH_FROM_FUTURE,
                )
            if snapshot.status is MoexIssQuoteStatus.UNAVAILABLE:
                return self._stale_or_unavailable_result(
                    key=key,
                    entry=entry,
                    checked_at=now,
                    allow_stale=allow_stale,
                    source_error_code=snapshot.error_code,
                    cache_error_code=(
                        MoexQuoteCacheErrorCode.EMPTY
                        if entry is None
                        else MoexQuoteCacheErrorCode.EXPIRED
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

            selected_entry: _MoexIssQuoteCacheEntryV1 | None = refreshed
            if now >= refreshed.stale_until:
                self._entries.pop(key, None)
                selected_entry = None
            return self._stale_or_unavailable_result(
                key=key,
                entry=selected_entry,
                checked_at=now,
                allow_stale=allow_stale,
                source_error_code=None,
                cache_error_code=MoexQuoteCacheErrorCode.REFRESH_STALE,
            )

    def active_entry_count(self, *, checked_at: datetime | None = None) -> int:
        now = _aware_utc(checked_at)
        with self._lock:
            self._prune(now)
            return len(self._entries)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
