from datetime import datetime, timezone

import pytest

from omni_cio.contracts.v1.ratings import CreditRatingSourceErrorCode
from omni_cio.market.expert_ra_rating_actions_v1 import (
    ExpertRaRatingActionsSourceError,
    parse_expert_ra_issuer_rating_actions_html,
)


NOW = datetime(2026, 7, 31, 6, 55, tzinfo=timezone.utc)
_TITLE = (
    "«Эксперт РА» подтвердил кредитный рейтинг "
    "АО «Тест» на уровне ruA"
)


def _parse(payload: str):
    return parse_expert_ra_issuer_rating_actions_html(
        payload.encode(),
        retrieved_at=NOW,
    )


def test_anchor_without_href_cannot_open_rating_action_scope() -> None:
    payload = (
        "<html><body><a>Рейтинговые действия</a>"
        f'<a href="/releases/2026/jul31a">{_TITLE}</a>'
        "<span>31.07.2026</span>"
        '<h2><a href="/researches/">Аналитика</a></h2>'
        "</body></html>"
    )

    with pytest.raises(
        ExpertRaRatingActionsSourceError,
        match=CreditRatingSourceErrorCode.SCHEMA_INVALID.value,
    ):
        _parse(payload)


def test_anchor_without_href_cannot_close_rating_action_scope() -> None:
    payload = (
        "<html><body><h1>Рейтинговые действия</h1>"
        f'<a href="/releases/2026/jul31a">{_TITLE}</a>'
        "<span>31.07.2026</span>"
        "<h2><a>Аналитика</a></h2>"
        "</body></html>"
    )

    with pytest.raises(
        ExpertRaRatingActionsSourceError,
        match=CreditRatingSourceErrorCode.SCHEMA_INVALID.value,
    ):
        _parse(payload)


def test_action_anchor_without_href_fails_closed() -> None:
    payload = (
        "<html><body><h1>Рейтинговые действия</h1>"
        f"<a>{_TITLE}</a><span>31.07.2026</span>"
        "<h2>Аналитика</h2></body></html>"
    )

    with pytest.raises(
        ExpertRaRatingActionsSourceError,
        match=CreditRatingSourceErrorCode.URL_INVALID.value,
    ):
        _parse(payload)


@pytest.mark.parametrize(
    ("date_href", "error_code"),
    [
        (
            "https://example.com/releases/2026/jul31a",
            CreditRatingSourceErrorCode.URL_INVALID,
        ),
        (
            "/releases/2026/jul30a",
            CreditRatingSourceErrorCode.IDENTITY_INVALID,
        ),
    ],
)
def test_linked_publication_date_must_match_action_release_identity(
    date_href: str,
    error_code: CreditRatingSourceErrorCode,
) -> None:
    payload = (
        "<html><body><h1>Рейтинговые действия</h1>"
        f'<a href="/releases/2026/jul31a">{_TITLE}</a>'
        f'<a href="{date_href}">31.07.2026</a>'
        "<h2>Аналитика</h2></body></html>"
    )

    with pytest.raises(
        ExpertRaRatingActionsSourceError,
        match=error_code.value,
    ):
        _parse(payload)


def test_linked_publication_date_accepts_exact_same_release() -> None:
    payload = (
        "<html><body><h1>Рейтинговые действия</h1>"
        f'<a href="/releases/2026/jul31a">{_TITLE}</a>'
        '<a href="https://www.raexpert.ru/releases/2026/jul31a">'
        "31.07.2026</a>"
        '<h2><a href="/researches/">Аналитика</a></h2>'
        "</body></html>"
    )

    result = _parse(payload)

    assert len(result.records) == 1
    assert result.records[0].release_url == (
        "https://raexpert.ru/releases/2026/jul31a"
    )