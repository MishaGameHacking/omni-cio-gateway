from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

from omni_cio.contracts.v1.research_evidence import (
    EvidenceCoverageProbeV1,
    EvidenceRecordV1,
    ResearchSourceLoadV1,
    ResearchTargetV1,
)


class ResearchSourceAdapter(Protocol):
    def fetch(
        self,
        *,
        target: ResearchTargetV1,
        retrieved_at: datetime | None = None,
        lookback_days: int = 730,
        lookahead_days: int = 370,
    ) -> tuple[tuple[EvidenceRecordV1, ...], tuple[EvidenceCoverageProbeV1, ...]]: ...


class ResearchRefreshRateLimited(RuntimeError):
    """A forced refresh was requested before the bounded refresh window opened."""


@dataclass(frozen=True)
class _CacheEntry:
    fetched_at: datetime
    expires_at: datetime
    next_refresh_at: datetime
    records: tuple[EvidenceRecordV1, ...]
    probes: tuple[EvidenceCoverageProbeV1, ...]


class ResearchEvidenceCacheV1:
    """Small in-process cache for source facts; failed/degraded fetches are never cached."""

    def __init__(
        self,
        *,
        ttl_seconds: int = 3600,
        min_refresh_interval_seconds: int = 30,
        max_entries: int = 128,
    ) -> None:
        if ttl_seconds < 60 or ttl_seconds > 86_400:
            raise ValueError("research cache TTL must be between 60 and 86400 seconds")
        if min_refresh_interval_seconds < 1 or min_refresh_interval_seconds > 3600:
            raise ValueError("research refresh interval must be between 1 and 3600 seconds")
        if min_refresh_interval_seconds > ttl_seconds:
            raise ValueError("research refresh interval cannot exceed cache TTL")
        if max_entries < 1 or max_entries > 4096:
            raise ValueError("research cache max_entries must be between 1 and 4096")
        self._ttl = timedelta(seconds=ttl_seconds)
        self._min_refresh = timedelta(seconds=min_refresh_interval_seconds)
        self._max_entries = max_entries
        self._entries: dict[tuple[str, str, str, str], _CacheEntry] = {}

    @staticmethod
    def _now(value: datetime | None) -> datetime:
        result = value or datetime.now(timezone.utc)
        if result.tzinfo is None or result.utcoffset() is None:
            raise ValueError("research cache timestamp must be timezone-aware")
        return result.astimezone(timezone.utc)

    @staticmethod
    def _key(target: ResearchTargetV1) -> tuple[str, str, str, str]:
        source_id = target.asset_uid_source.source_id if target.asset_uid_source else ""
        return (
            target.instrument_uid,
            target.instrument_type.value,
            target.asset_uid or "",
            source_id,
        )

    def _evict_if_needed(self) -> None:
        while len(self._entries) >= self._max_entries:
            oldest_key = min(
                self._entries,
                key=lambda key: (self._entries[key].fetched_at, key),
            )
            del self._entries[oldest_key]

    def load(
        self,
        adapter: ResearchSourceAdapter,
        *,
        target: ResearchTargetV1,
        now: datetime | None = None,
        force_refresh: bool = False,
        lookback_days: int = 730,
        lookahead_days: int = 370,
    ) -> ResearchSourceLoadV1:
        timestamp = self._now(now)
        key = self._key(target)
        entry = self._entries.get(key)

        if entry is not None and timestamp < entry.expires_at and not force_refresh:
            return ResearchSourceLoadV1(
                target=target,
                loaded_at=timestamp,
                source_fetched_at=entry.fetched_at,
                expires_at=entry.expires_at,
                next_refresh_at=entry.next_refresh_at,
                cache_hit=True,
                source_calls=0,
                cacheable=True,
                records=entry.records,
                probes=entry.probes,
            )

        if force_refresh and entry is not None and timestamp < entry.next_refresh_at:
            raise ResearchRefreshRateLimited(
                f"RESEARCH_REFRESH_RATE_LIMITED_UNTIL:{entry.next_refresh_at.isoformat()}"
            )

        records, probes = adapter.fetch(
            target=target,
            retrieved_at=timestamp,
            lookback_days=lookback_days,
            lookahead_days=lookahead_days,
        )
        source_calls = len(probes)
        cacheable = bool(probes) and all(probe.success for probe in probes)
        expires_at = timestamp + self._ttl if cacheable else timestamp
        next_refresh_at = timestamp + self._min_refresh

        if cacheable:
            if key not in self._entries:
                self._evict_if_needed()
            self._entries[key] = _CacheEntry(
                fetched_at=timestamp,
                expires_at=expires_at,
                next_refresh_at=next_refresh_at,
                records=records,
                probes=probes,
            )
        else:
            self._entries.pop(key, None)

        return ResearchSourceLoadV1(
            target=target,
            loaded_at=timestamp,
            source_fetched_at=timestamp,
            expires_at=expires_at,
            next_refresh_at=next_refresh_at,
            cache_hit=False,
            source_calls=source_calls,
            cacheable=cacheable,
            records=records,
            probes=probes,
        )
