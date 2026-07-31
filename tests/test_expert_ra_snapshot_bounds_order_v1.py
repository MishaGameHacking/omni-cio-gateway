from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1.expert_ra_ratings import (
    ExpertRaIssuerRatingActionsSnapshotV1,
    ExpertRaIssuerRatingActionV1,
)
from omni_cio.contracts.v1.market import MarketSourceV1, RatingAction, SourceAuthority
from omni_cio.contracts.v1.ratings import CreditRatingSourceStatus


RETRIEVED_AT = datetime(2026, 7, 31, 8, 0, tzinfo=timezone.utc)
SOURCE = MarketSourceV1(
    provider="Expert RA",
    authority=SourceAuthority.OFFICIAL,
    retrieved_at=RETRIEVED_AT,
    source_id="EXPERT_RA.home.rating_actions",
)


def _record(day: int) -> ExpertRaIssuerRatingActionV1:
    return ExpertRaIssuerRatingActionV1(
        subject_name=f"АО «Эмитент {day:02d}»",
        rating="ruA",
        action=RatingAction.AFFIRMED,
        published_on=date(2026, 7, day),
        release_url=f"https://raexpert.ru/releases/2026/jul{day:02d}a",
        source=SOURCE,
    )


def test_snapshot_accepts_deterministic_newest_first_order() -> None:
    records = (_record(31), _record(30), _record(29))

    snapshot = ExpertRaIssuerRatingActionsSnapshotV1(
        retrieved_at=RETRIEVED_AT,
        status=CreditRatingSourceStatus.AVAILABLE,
        source=SOURCE,
        records=records,
    )

    assert snapshot.records == records


def test_snapshot_rejects_unsorted_direct_construction() -> None:
    with pytest.raises(ValidationError, match="sorted newest first"):
        ExpertRaIssuerRatingActionsSnapshotV1(
            retrieved_at=RETRIEVED_AT,
            status=CreditRatingSourceStatus.AVAILABLE,
            source=SOURCE,
            records=(_record(30), _record(31)),
        )


def test_snapshot_rejects_more_than_parser_record_limit() -> None:
    records = tuple(_record(day) for day in range(31, 0, -1))

    with pytest.raises(ValidationError):
        ExpertRaIssuerRatingActionsSnapshotV1(
            retrieved_at=RETRIEVED_AT,
            status=CreditRatingSourceStatus.AVAILABLE,
            source=SOURCE,
            records=records,
        )
