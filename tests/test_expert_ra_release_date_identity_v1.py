from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1.expert_ra_ratings import (
    ExpertRaIssuerRatingActionsSnapshotV1,
    ExpertRaIssuerRatingActionV1,
)
from omni_cio.contracts.v1.market import MarketSourceV1, RatingAction, SourceAuthority
from omni_cio.contracts.v1.ratings import (
    CreditRatingSourceErrorCode,
    CreditRatingSourceStatus,
)
from omni_cio.market.expert_ra_rating_actions_v1 import (
    EXPERT_RA_RATING_ACTIONS_SOURCE_ID,
    ExpertRaRatingActionsSourceError,
    parse_expert_ra_issuer_rating_actions_html,
)


NOW = datetime(2026, 7, 31, 5, 30, tzinfo=timezone.utc)


def _source(*, retrieved_at: datetime = NOW) -> MarketSourceV1:
    return MarketSourceV1(
        provider="Expert RA",
        authority=SourceAuthority.OFFICIAL,
        retrieved_at=retrieved_at,
        source_id=EXPERT_RA_RATING_ACTIONS_SOURCE_ID,
    )


def _record(
    *,
    release_url: str,
    published_on: date,
    source: MarketSourceV1 | None = None,
) -> ExpertRaIssuerRatingActionV1:
    return ExpertRaIssuerRatingActionV1(
        subject_name="АО «Тест»",
        rating="ruA",
        action=RatingAction.AFFIRMED,
        published_on=published_on,
        release_url=release_url,
        source=source or _source(),
    )


@pytest.mark.parametrize(
    ("release_url", "published_on"),
    [
        ("https://raexpert.ru/releases/2026/xyz30a", date(2026, 7, 30)),
        ("https://raexpert.ru/releases/2026/feb31a", date(2026, 2, 28)),
        ("https://raexpert.ru/releases/2026/jul30a", date(2026, 7, 29)),
    ],
)
def test_contract_rejects_invalid_or_mismatched_release_dates(
    release_url: str,
    published_on: date,
) -> None:
    with pytest.raises(ValidationError):
        _record(release_url=release_url, published_on=published_on)


def test_contract_accepts_calendar_valid_matching_release_date() -> None:
    record = _record(
        release_url="https://raexpert.ru/releases/2024/feb29a",
        published_on=date(2024, 2, 29),
    )
    assert record.published_on == date(2024, 2, 29)


def test_contract_rejects_publication_beyond_retrieval_tolerance() -> None:
    with pytest.raises(ValidationError):
        _record(
            release_url="https://raexpert.ru/releases/2026/aug02a",
            published_on=date(2026, 8, 2),
        )


def test_snapshot_requires_exact_source_retrieval_timestamp() -> None:
    source = _source()
    record = _record(
        release_url="https://raexpert.ru/releases/2026/jul30a",
        published_on=date(2026, 7, 30),
        source=source,
    )
    with pytest.raises(ValidationError):
        ExpertRaIssuerRatingActionsSnapshotV1(
            retrieved_at=NOW + timedelta(seconds=1),
            status=CreditRatingSourceStatus.AVAILABLE,
            source=source,
            records=(record,),
        )


@pytest.mark.parametrize(
    ("href", "published_on"),
    [
        ("/releases/2026/xyz30a", "30.07.2026"),
        ("/releases/2026/jul30a", "29.07.2026"),
    ],
)
def test_parser_fails_closed_on_release_date_identity_drift(
    href: str,
    published_on: str,
) -> None:
    payload = (
        "<html><body><h1>Рейтинговые действия</h1>"
        f'<a href="{href}">'
        "«Эксперт РА» подтвердил кредитный рейтинг АО «Тест» на уровне ruA"
        f"</a><span>{published_on}</span>"
        "<h2>Аналитика</h2></body></html>"
    ).encode()
    with pytest.raises(
        ExpertRaRatingActionsSourceError,
        match=CreditRatingSourceErrorCode.SCHEMA_INVALID.value,
    ):
        parse_expert_ra_issuer_rating_actions_html(payload, retrieved_at=NOW)
