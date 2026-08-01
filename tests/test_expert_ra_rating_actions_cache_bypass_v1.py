from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, cast

from omni_cio.contracts.v1.expert_ra_ratings import (
    ExpertRaIssuerRatingActionsSnapshotV1,
)
from omni_cio.contracts.v1.market import MarketSourceV1, SourceAuthority
from omni_cio.contracts.v1.ratings import (
    CreditRatingCacheErrorCode,
    CreditRatingCacheStatus,
    CreditRatingSourceStatus,
)
from omni_cio.market.expert_ra_rating_actions_cache_v1 import (
    ExpertRaIssuerRatingActionsCacheV1,
)
from omni_cio.market.expert_ra_rating_actions_v1 import (
    EXPERT_RA_RATING_ACTIONS_SOURCE_ID,
)


NOW = datetime(2026, 8, 1, 6, 30, tzinfo=timezone.utc)


def _source() -> MarketSourceV1:
    return MarketSourceV1(
        provider="Expert RA",
        authority=SourceAuthority.OFFICIAL,
        retrieved_at=NOW,
        source_id=EXPERT_RA_RATING_ACTIONS_SOURCE_ID,
    )


def _result_for(snapshot: ExpertRaIssuerRatingActionsSnapshotV1):
    def loader(*, retrieved_at: datetime) -> ExpertRaIssuerRatingActionsSnapshotV1:
        del retrieved_at
        return snapshot

    return ExpertRaIssuerRatingActionsCacheV1(loader=loader).get(checked_at=NOW)


def test_model_construct_malformed_timestamp_fails_closed_without_exception() -> None:
    malformed = ExpertRaIssuerRatingActionsSnapshotV1.model_construct(
        retrieved_at=cast(Any, "not-a-timestamp"),
        status=CreditRatingSourceStatus.AVAILABLE,
        source=None,
        records=(),
        error_code=None,
    )

    result = _result_for(malformed)

    assert result.status is CreditRatingCacheStatus.UNAVAILABLE
    assert result.snapshot is None
    assert (
        result.cache_error_code
        is CreditRatingCacheErrorCode.REFRESH_SOURCE_MISMATCH
    )


def test_model_construct_arbitrary_source_and_record_fail_closed() -> None:
    malformed = ExpertRaIssuerRatingActionsSnapshotV1.model_construct(
        retrieved_at=NOW,
        status=CreditRatingSourceStatus.AVAILABLE,
        source=cast(Any, object()),
        records=cast(Any, (object(),)),
        error_code=None,
    )

    result = _result_for(malformed)

    assert result.status is CreditRatingCacheStatus.UNAVAILABLE
    assert result.snapshot is None
    assert (
        result.cache_error_code
        is CreditRatingCacheErrorCode.REFRESH_SOURCE_MISMATCH
    )


def test_model_construct_arbitrary_record_with_valid_source_fails_closed() -> None:
    malformed = ExpertRaIssuerRatingActionsSnapshotV1.model_construct(
        retrieved_at=NOW,
        status=CreditRatingSourceStatus.AVAILABLE,
        source=_source(),
        records=cast(Any, (object(),)),
        error_code=None,
    )

    result = _result_for(malformed)

    assert result.status is CreditRatingCacheStatus.UNAVAILABLE
    assert result.snapshot is None
    assert (
        result.cache_error_code
        is CreditRatingCacheErrorCode.REFRESH_SOURCE_MISMATCH
    )


def test_model_construct_malformed_unavailable_shape_fails_closed() -> None:
    malformed = ExpertRaIssuerRatingActionsSnapshotV1.model_construct(
        retrieved_at=NOW,
        status=CreditRatingSourceStatus.UNAVAILABLE,
        source=_source(),
        records=cast(Any, (object(),)),
        error_code=cast(Any, "not-a-source-error"),
    )

    result = _result_for(malformed)

    assert result.status is CreditRatingCacheStatus.UNAVAILABLE
    assert result.snapshot is None
    assert (
        result.cache_error_code
        is CreditRatingCacheErrorCode.REFRESH_SOURCE_MISMATCH
    )
    assert result.source_error_code is None
