from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import RLock

from omni_cio.contracts.v1.expert_ra_ratings import (
    ExpertRaIssuerRatingActionsCacheResultV1,
    ExpertRaIssuerRatingActionsSnapshotV1,
    ExpertRaIssuerRatingActionV1,
)
from omni_cio.contracts.v1.market import MarketSourceV1, SourceAuthority
from omni_cio.contracts.v1.ratings import (
    CreditRatingCacheErrorCode,
    CreditRatingCacheStatus,
    CreditRatingSourceErrorCode,
    CreditRatingSourceStatus,
)
from omni_cio.market.expert_ra_rating_actions_v1 import (
    EXPERT_RA_RATING_ACTIONS_PROVIDER,
    EXPERT_RA_RATING_ACTIONS_SOURCE_ID,
    fetch_expert_ra_issuer_rating_actions,
)


DEFAULT_EXPERT_RA_RATING_CACHE_FRESH_SECONDS = 900
DEFAULT_EXPERT_RA_RATING_CACHE_STALE_SECONDS = 86_400
DEFAULT_EXPERT_RA_RATING_CACHE_FUTURE_TOLERANCE_SECONDS = 30


class ExpertRaRatingActionsCacheError(ValueError):
    """The Expert RA rating-action cache cannot be configured or queried safely."""


ExpertRaRatingActionsLoaderV1 = Callable[..., ExpertRaIssuerRatingActionsSnapshotV1]


@dataclass(frozen=True, slots=True)
class _ExpertRaRatingActionsCacheEntryV1:
    snapshot: ExpertRaIssuerRatingActionsSnapshotV1
    fresh_until: datetime
    stale_until: datetime


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if (
        not isinstance(result, datetime)
        or result.tzinfo is None
        or result.utcoffset() is None
    ):
        raise ExpertRaRatingActionsCacheError(
            "EXPERT_RA_RATING_ACTIONS_CACHE_TIMESTAMP_INVALID"
        )
    return result.astimezone(timezone.utc)


def _age_seconds(
    snapshot: ExpertRaIssuerRatingActionsSnapshotV1,
    checked_at: datetime,
) -> int:
    return max(0, int((checked_at - snapshot.retrieved_at).total_seconds()))


def _safe_source_error_code(
    snapshot: ExpertRaIssuerRatingActionsSnapshotV1,
) -> CreditRatingSourceErrorCode | None:
    value = snapshot.error_code
    return value if isinstance(value, CreditRatingSourceErrorCode) else None


def _snapshot_timestamp_valid(
    snapshot: ExpertRaIssuerRatingActionsSnapshotV1,
) -> bool:
    value = snapshot.retrieved_at
    return (
        isinstance(value, datetime)
        and value.tzinfo is not None
        and value.utcoffset() is not None
    )


def _snapshot_contract_revalidates(
    snapshot: ExpertRaIssuerRatingActionsSnapshotV1,
) -> bool:
    """Reject validator-bypassed models before any cache identity/use decision."""
    try:
        validated = ExpertRaIssuerRatingActionsSnapshotV1.model_validate(
            snapshot.model_dump(mode="python", warnings="error")
        )
    except Exception:
        return False
    return validated == snapshot


class ExpertRaIssuerRatingActionsCacheV1:
    """Single-flight fixed-source cache with explicit stale/unavailable semantics."""

    internal_only = True
    fixed_official_source = True
    issuer_scope_only = True
    agency_specific_scale_only = True
    subject_identity_resolution_required = True
    cross_agency_identity_merged = False
    informational_use_only = True
    redistribution_authorized = False
    investment_recommendation = False
    raw_html_stored = False
    credentials_present = False
    full_account_identifier_present = False
    broker_write_called = False
    trade_authorized = False
    order_created = False
    trading_methods = False

    def __init__(
        self,
        *,
        loader: ExpertRaRatingActionsLoaderV1 = fetch_expert_ra_issuer_rating_actions,
        fresh_seconds: int = DEFAULT_EXPERT_RA_RATING_CACHE_FRESH_SECONDS,
        stale_seconds: int = DEFAULT_EXPERT_RA_RATING_CACHE_STALE_SECONDS,
        future_tolerance_seconds: int = (
            DEFAULT_EXPERT_RA_RATING_CACHE_FUTURE_TOLERANCE_SECONDS
        ),
    ) -> None:
        if not callable(loader):
            raise ExpertRaRatingActionsCacheError(
                "EXPERT_RA_RATING_ACTIONS_CACHE_LOADER_INVALID"
            )
        if (
            isinstance(fresh_seconds, bool)
            or not isinstance(fresh_seconds, int)
            or not 1 <= fresh_seconds <= 86_400
        ):
            raise ExpertRaRatingActionsCacheError(
                "EXPERT_RA_RATING_ACTIONS_CACHE_FRESH_TTL_INVALID"
            )
        if (
            isinstance(stale_seconds, bool)
            or not isinstance(stale_seconds, int)
            or not fresh_seconds <= stale_seconds <= 604_800
        ):
            raise ExpertRaRatingActionsCacheError(
                "EXPERT_RA_RATING_ACTIONS_CACHE_STALE_TTL_INVALID"
            )
        if (
            isinstance(future_tolerance_seconds, bool)
            or not isinstance(future_tolerance_seconds, int)
            or not 0 <= future_tolerance_seconds <= 3_600
        ):
            raise ExpertRaRatingActionsCacheError(
                "EXPERT_RA_RATING_ACTIONS_CACHE_FUTURE_TOLERANCE_INVALID"
            )
        self._loader = loader
        self._fresh_ttl = timedelta(seconds=fresh_seconds)
        self._stale_ttl = timedelta(seconds=stale_seconds)
        self._future_tolerance = timedelta(seconds=future_tolerance_seconds)
        self._entry: _ExpertRaRatingActionsCacheEntryV1 | None = None
        self._lock = RLock()

    @property
    def fresh_seconds(self) -> int:
        return int(self._fresh_ttl.total_seconds())

    @property
    def stale_seconds(self) -> int:
        return int(self._stale_ttl.total_seconds())

    @property
    def capacity(self) -> int:
        return 1

    def _prune(self, checked_at: datetime) -> None:
        if self._entry is not None and checked_at >= self._entry.stale_until:
            self._entry = None

    def _store(
        self,
        snapshot: ExpertRaIssuerRatingActionsSnapshotV1,
    ) -> _ExpertRaRatingActionsCacheEntryV1:
        entry = _ExpertRaRatingActionsCacheEntryV1(
            snapshot=snapshot,
            fresh_until=snapshot.retrieved_at + self._fresh_ttl,
            stale_until=snapshot.retrieved_at + self._stale_ttl,
        )
        self._entry = entry
        return entry

    @staticmethod
    def _record_identity_valid(
        record: ExpertRaIssuerRatingActionV1,
        snapshot: ExpertRaIssuerRatingActionsSnapshotV1,
    ) -> bool:
        return (
            isinstance(record, ExpertRaIssuerRatingActionV1)
            and isinstance(snapshot.source, MarketSourceV1)
            and record.source == snapshot.source
            and record.agency == "EXPERT_RA"
            and record.scope == "issuer"
            and record.identity_resolution_required is True
            and record.trading_methods is False
        )

    @classmethod
    def _snapshot_identity_valid(
        cls,
        snapshot: ExpertRaIssuerRatingActionsSnapshotV1,
    ) -> bool:
        if (
            not _snapshot_contract_revalidates(snapshot)
            or snapshot.status is not CreditRatingSourceStatus.AVAILABLE
            or not _snapshot_timestamp_valid(snapshot)
            or not isinstance(snapshot.source, MarketSourceV1)
            or snapshot.source.authority is not SourceAuthority.OFFICIAL
            or snapshot.source.provider != EXPERT_RA_RATING_ACTIONS_PROVIDER
            or snapshot.source.source_id != EXPERT_RA_RATING_ACTIONS_SOURCE_ID
            or snapshot.source.retrieved_at != snapshot.retrieved_at
            or not isinstance(snapshot.records, tuple)
            or not snapshot.records
            or not all(
                isinstance(record, ExpertRaIssuerRatingActionV1)
                for record in snapshot.records
            )
            or snapshot.error_code is not None
            or snapshot.subject_identity_resolution_required is not True
            or snapshot.cross_agency_identity_merged is not False
            or snapshot.trading_methods is not False
        ):
            return False
        release_urls = tuple(record.release_url for record in snapshot.records)
        if len(set(release_urls)) != len(release_urls):
            return False
        if not all(
            cls._record_identity_valid(record, snapshot)
            for record in snapshot.records
        ):
            return False
        expected_order = tuple(
            sorted(
                snapshot.records,
                key=lambda item: (item.published_on, item.release_url),
                reverse=True,
            )
        )
        return snapshot.records == expected_order

    @staticmethod
    def _unavailable_snapshot_valid(
        snapshot: ExpertRaIssuerRatingActionsSnapshotV1,
    ) -> bool:
        return (
            _snapshot_contract_revalidates(snapshot)
            and snapshot.status is CreditRatingSourceStatus.UNAVAILABLE
            and _snapshot_timestamp_valid(snapshot)
            and snapshot.source is None
            and isinstance(snapshot.records, tuple)
            and not snapshot.records
            and isinstance(snapshot.error_code, CreditRatingSourceErrorCode)
        )

    def _fresh_result(
        self,
        *,
        entry: _ExpertRaRatingActionsCacheEntryV1,
        checked_at: datetime,
        served_from_cache: bool,
        refresh_attempted: bool,
        refresh_succeeded: bool,
        source_error_code: CreditRatingSourceErrorCode | None = None,
        cache_error_code: CreditRatingCacheErrorCode | None = None,
    ) -> ExpertRaIssuerRatingActionsCacheResultV1:
        return ExpertRaIssuerRatingActionsCacheResultV1(
            checked_at=checked_at,
            status=CreditRatingCacheStatus.FRESH,
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
            display_records_allowed=True,
        )

    def _stale_or_unavailable_result(
        self,
        *,
        entry: _ExpertRaRatingActionsCacheEntryV1 | None,
        checked_at: datetime,
        allow_stale: bool,
        source_error_code: CreditRatingSourceErrorCode | None,
        cache_error_code: CreditRatingCacheErrorCode,
    ) -> ExpertRaIssuerRatingActionsCacheResultV1:
        if entry is not None and checked_at < entry.fresh_until:
            return self._fresh_result(
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
            return ExpertRaIssuerRatingActionsCacheResultV1(
                checked_at=checked_at,
                status=CreditRatingCacheStatus.STALE,
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
                display_records_allowed=True,
            )

        effective_error = (
            CreditRatingCacheErrorCode.STALE_NOT_ALLOWED
            if stale_available and not allow_stale
            else cache_error_code
        )
        return ExpertRaIssuerRatingActionsCacheResultV1(
            checked_at=checked_at,
            status=CreditRatingCacheStatus.UNAVAILABLE,
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
            display_records_allowed=False,
        )

    def get(
        self,
        *,
        checked_at: datetime | None = None,
        force_refresh: bool = False,
        allow_stale: bool = False,
    ) -> ExpertRaIssuerRatingActionsCacheResultV1:
        """Return one explicit fresh/stale/unavailable view for the fixed source."""
        now = _aware_utc(checked_at)
        if type(force_refresh) is not bool or type(allow_stale) is not bool:
            raise ExpertRaRatingActionsCacheError(
                "EXPERT_RA_RATING_ACTIONS_CACHE_FLAG_INVALID"
            )

        with self._lock:
            self._prune(now)
            entry = self._entry
            if entry is not None and now < entry.fresh_until and not force_refresh:
                return self._fresh_result(
                    entry=entry,
                    checked_at=now,
                    served_from_cache=True,
                    refresh_attempted=False,
                    refresh_succeeded=False,
                )

            try:
                snapshot = self._loader(retrieved_at=now)
            except Exception:
                return self._stale_or_unavailable_result(
                    entry=entry,
                    checked_at=now,
                    allow_stale=allow_stale,
                    source_error_code=None,
                    cache_error_code=CreditRatingCacheErrorCode.REFRESH_FAILED,
                )

            if not isinstance(snapshot, ExpertRaIssuerRatingActionsSnapshotV1):
                return self._stale_or_unavailable_result(
                    entry=entry,
                    checked_at=now,
                    allow_stale=allow_stale,
                    source_error_code=None,
                    cache_error_code=CreditRatingCacheErrorCode.REFRESH_TYPE_INVALID,
                )
            if not _snapshot_timestamp_valid(snapshot):
                return self._stale_or_unavailable_result(
                    entry=entry,
                    checked_at=now,
                    allow_stale=allow_stale,
                    source_error_code=None,
                    cache_error_code=CreditRatingCacheErrorCode.REFRESH_SOURCE_MISMATCH,
                )
            source_error_code = _safe_source_error_code(snapshot)
            if snapshot.retrieved_at - now > self._future_tolerance:
                return self._stale_or_unavailable_result(
                    entry=entry,
                    checked_at=now,
                    allow_stale=allow_stale,
                    source_error_code=source_error_code,
                    cache_error_code=CreditRatingCacheErrorCode.REFRESH_FROM_FUTURE,
                )
            if snapshot.status is CreditRatingSourceStatus.UNAVAILABLE:
                if not self._unavailable_snapshot_valid(snapshot):
                    return self._stale_or_unavailable_result(
                        entry=entry,
                        checked_at=now,
                        allow_stale=allow_stale,
                        source_error_code=source_error_code,
                        cache_error_code=(
                            CreditRatingCacheErrorCode.REFRESH_SOURCE_MISMATCH
                        ),
                    )
                return self._stale_or_unavailable_result(
                    entry=entry,
                    checked_at=now,
                    allow_stale=allow_stale,
                    source_error_code=source_error_code,
                    cache_error_code=(
                        CreditRatingCacheErrorCode.EMPTY
                        if entry is None
                        else CreditRatingCacheErrorCode.EXPIRED
                    ),
                )
            if not self._snapshot_identity_valid(snapshot):
                return self._stale_or_unavailable_result(
                    entry=entry,
                    checked_at=now,
                    allow_stale=allow_stale,
                    source_error_code=source_error_code,
                    cache_error_code=CreditRatingCacheErrorCode.REFRESH_SOURCE_MISMATCH,
                )

            refreshed = self._store(snapshot)
            if now < refreshed.fresh_until:
                return self._fresh_result(
                    entry=refreshed,
                    checked_at=now,
                    served_from_cache=False,
                    refresh_attempted=True,
                    refresh_succeeded=True,
                )
            selected_entry: _ExpertRaRatingActionsCacheEntryV1 | None = refreshed
            if now >= refreshed.stale_until:
                self._entry = None
                selected_entry = None
            return self._stale_or_unavailable_result(
                entry=selected_entry,
                checked_at=now,
                allow_stale=allow_stale,
                source_error_code=None,
                cache_error_code=CreditRatingCacheErrorCode.REFRESH_STALE,
            )

    def active_entry_count(self, *, checked_at: datetime | None = None) -> int:
        now = _aware_utc(checked_at)
        with self._lock:
            self._prune(now)
            return 1 if self._entry is not None else 0

    def clear(self) -> None:
        with self._lock:
            self._entry = None
