from datetime import datetime, timezone

from pydantic import ValidationError
import pytest

from omni_cio.contracts.v1.expert_ra_ratings import (
    ExpertRaIssuerRatingActionV1,
)
from omni_cio.contracts.v1.market import MarketSourceV1, RatingAction, SourceAuthority


NOW = datetime(2026, 7, 31, 6, 15, tzinfo=timezone.utc)


def _source() -> MarketSourceV1:
    return MarketSourceV1(
        provider="Expert RA",
        authority=SourceAuthority.OFFICIAL,
        retrieved_at=NOW,
        source_id="EXPERT_RA.home.rating_actions",
    )


def _record(url: str) -> ExpertRaIssuerRatingActionV1:
    return ExpertRaIssuerRatingActionV1(
        subject_name="АО «Тест»",
        rating="ruA",
        action=RatingAction.AFFIRMED,
        published_on=NOW.date(),
        release_url=url,
        source=_source(),
    )


def test_contract_accepts_only_canonical_expert_ra_release_identity() -> None:
    valid = _record("https://raexpert.ru/releases/2026/jul31a")
    assert valid.release_url == "https://raexpert.ru/releases/2026/jul31a"

    for invalid in (
        "https://www.raexpert.ru/releases/2026/jul31a",
        "https://raexpert.ru/releases/2026/jul31a/",
        "https://raexpert.ru/releases/2026/jul31a?tracking=1",
        "https://raexpert.ru/releases/2026/not-a-release",
        "https://raexpert.ru/releases/../../private",
        "https://example.com/releases/2026/jul31a",
    ):
        with pytest.raises(ValidationError):
            _record(invalid)
