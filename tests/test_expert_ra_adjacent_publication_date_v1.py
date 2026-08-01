from datetime import datetime, timezone

import pytest

from omni_cio.contracts.v1.ratings import CreditRatingSourceErrorCode
from omni_cio.market.expert_ra_rating_actions_v1 import (
    ExpertRaRatingActionsSourceError,
    parse_expert_ra_issuer_rating_actions_html,
)


NOW = datetime(2026, 7, 31, 8, 0, tzinfo=timezone.utc)
_TITLE = "«Эксперт РА» подтвердил кредитный рейтинг АО «Тест» на уровне ruA"


def test_parser_accepts_immediately_adjacent_publication_date() -> None:
    payload = (
        "<html><body><h1>Рейтинговые действия</h1>"
        f'<a href="/releases/2026/jul31a">{_TITLE}</a>'
        "<span>31.07.2026</span>"
        "<h2>Аналитика</h2></body></html>"
    ).encode()

    result = parse_expert_ra_issuer_rating_actions_html(
        payload,
        retrieved_at=NOW,
    )

    assert len(result.records) == 1
    assert result.records[0].published_on.isoformat() == "2026-07-31"


def test_parser_rejects_non_adjacent_date_cross_association() -> None:
    payload = (
        "<html><body><h1>Рейтинговые действия</h1>"
        f'<a href="/releases/2026/jul31a">{_TITLE}</a>'
        "<span>unrelated visible content</span>"
        '<a href="/releases/2026/jul31a">31.07.2026</a>'
        "<h2>Аналитика</h2></body></html>"
    ).encode()

    with pytest.raises(
        ExpertRaRatingActionsSourceError,
        match=CreditRatingSourceErrorCode.TIMESTAMP_INVALID.value,
    ):
        parse_expert_ra_issuer_rating_actions_html(
            payload,
            retrieved_at=NOW,
        )
