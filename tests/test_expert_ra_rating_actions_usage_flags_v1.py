from datetime import datetime, timezone

from omni_cio.contracts.v1.expert_ra_ratings import (
    ExpertRaIssuerRatingActionsSnapshotV1,
    ExpertRaIssuerRatingActionV1,
)
from omni_cio.contracts.v1.market import MarketSourceV1, RatingAction, SourceAuthority
from omni_cio.contracts.v1.ratings import CreditRatingSourceStatus


NOW = datetime(2026, 7, 31, 5, 45, tzinfo=timezone.utc)


def test_expert_ra_records_and_snapshots_are_informational_only() -> None:
    source = MarketSourceV1(
        provider="Expert RA",
        authority=SourceAuthority.OFFICIAL,
        retrieved_at=NOW,
        source_id="EXPERT_RA.home.rating_actions",
    )
    record = ExpertRaIssuerRatingActionV1(
        subject_name="АО «Тест»",
        rating="ruA",
        action=RatingAction.AFFIRMED,
        published_on=NOW.date(),
        release_url="https://raexpert.ru/releases/2026/jul31a",
        source=source,
    )
    snapshot = ExpertRaIssuerRatingActionsSnapshotV1(
        retrieved_at=NOW,
        status=CreditRatingSourceStatus.AVAILABLE,
        source=source,
        records=(record,),
    )

    for value in (record, snapshot):
        assert value.informational_use_only is True
        assert value.redistribution_authorized is False
        assert value.investment_recommendation is False
        assert value.trading_methods is False
