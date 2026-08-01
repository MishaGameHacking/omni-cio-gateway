from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1.expert_ra_ratings import ExpertRaIssuerRatingActionV1
from omni_cio.contracts.v1.market import MarketSourceV1, RatingAction, SourceAuthority
from omni_cio.contracts.v1.ratings import CreditRatingOutlook


RETRIEVED_AT = datetime(2026, 7, 31, 8, 30, tzinfo=timezone.utc)
PUBLISHED_ON = date(2026, 7, 31)


def _source() -> MarketSourceV1:
    return MarketSourceV1(
        provider="Expert RA",
        authority=SourceAuthority.OFFICIAL,
        retrieved_at=RETRIEVED_AT,
        source_id="EXPERT_RA.home.rating_actions",
    )


def _record(outlook: CreditRatingOutlook | None) -> ExpertRaIssuerRatingActionV1:
    return ExpertRaIssuerRatingActionV1(
        subject_name="АО «Тест»",
        rating="ruA",
        action=RatingAction.AFFIRMED,
        outlook=outlook,
        published_on=PUBLISHED_ON,
        release_url="https://raexpert.ru/releases/2026/jul31a",
        source=_source(),
    )


@pytest.mark.parametrize(
    "outlook",
    [
        None,
        CreditRatingOutlook.STABLE,
        CreditRatingOutlook.POSITIVE,
        CreditRatingOutlook.NEGATIVE,
        CreditRatingOutlook.DEVELOPING,
    ],
)
def test_contract_accepts_only_parser_supported_outlooks(
    outlook: CreditRatingOutlook | None,
) -> None:
    record = _record(outlook)
    assert record.outlook is outlook


def test_contract_rejects_under_revision_as_expert_ra_outlook() -> None:
    with pytest.raises(ValidationError):
        _record(CreditRatingOutlook.UNDER_REVISION)
