from datetime import datetime, timezone

import pytest

from omni_cio.contracts.v1.ratings import CreditRatingSourceErrorCode
from omni_cio.market.expert_ra_rating_actions_v1 import (
    ExpertRaRatingActionsSourceError,
    parse_expert_ra_issuer_rating_actions_html,
)


NOW = datetime(2026, 7, 31, 6, 30, tzinfo=timezone.utc)
_ACTION = (
    '<a href="/releases/2026/jul31a">'
    "«Эксперт РА» подтвердил кредитный рейтинг АО «Тест» на уровне ruA"
    "</a><span>31.07.2026</span>"
)
_AFTER_BOUNDARY_ACTION = (
    '<a href="/releases/2026/jul30a">'
    "«Эксперт РА» подтвердил кредитный рейтинг АО «Вне секции» на уровне ruA"
    "</a><span>30.07.2026</span>"
)


def test_parser_accepts_canonical_linked_analytics_boundary() -> None:
    payload = (
        "<html><body><h1>Рейтинговые действия</h1>"
        f"{_ACTION}"
        '<h2><a href="/researches/">Аналитика</a></h2>'
        f"{_AFTER_BOUNDARY_ACTION}"
        "</body></html>"
    ).encode()

    result = parse_expert_ra_issuer_rating_actions_html(
        payload,
        retrieved_at=NOW,
    )

    assert [record.subject_name for record in result.records] == ["АО «Тест»"]


@pytest.mark.parametrize(
    "analytics_href",
    [
        "https://example.com/researches/",
        "/researches/?tracking=1",
        "/researches/#analytics",
        "/other/",
    ],
)
def test_parser_rejects_noncanonical_linked_analytics_boundary(
    analytics_href: str,
) -> None:
    payload = (
        "<html><body><h1>Рейтинговые действия</h1>"
        f"{_ACTION}"
        f'<h2><a href="{analytics_href}">Аналитика</a></h2>'
        "</body></html>"
    ).encode()

    with pytest.raises(
        ExpertRaRatingActionsSourceError,
        match=CreditRatingSourceErrorCode.SCHEMA_INVALID.value,
    ):
        parse_expert_ra_issuer_rating_actions_html(
            payload,
            retrieved_at=NOW,
        )


def test_linked_navigation_label_cannot_open_rating_action_scope() -> None:
    payload = (
        '<nav><a href="/ratings/">Рейтинговые действия</a></nav>'
        f"{_ACTION}"
        '<h2><a href="/researches/">Аналитика</a></h2>'
    ).encode()

    with pytest.raises(
        ExpertRaRatingActionsSourceError,
        match=CreditRatingSourceErrorCode.SCHEMA_INVALID.value,
    ):
        parse_expert_ra_issuer_rating_actions_html(
            payload,
            retrieved_at=NOW,
        )
