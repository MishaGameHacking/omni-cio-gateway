from datetime import datetime, timezone

import pytest

from omni_cio.contracts.v1.ratings import CreditRatingSourceErrorCode
from omni_cio.market.expert_ra_rating_actions_v1 import (
    ExpertRaRatingActionsSourceError,
    parse_expert_ra_issuer_rating_actions_html,
)


NOW = datetime(2026, 7, 31, 7, 0, tzinfo=timezone.utc)
_VALID_ACTION = (
    '<a href="/releases/2026/jul31a">'
    "«Эксперт РА» подтвердил кредитный рейтинг АО «Тест» на уровне ruA"
    "</a><span>31.07.2026</span>"
)


@pytest.mark.parametrize(
    "truncated_tail",
    [
        '<a href="/releases/2026/jul30a">незакрытая ссылка',
        "<script>незакрытый скрипт",
        "<style>незакрытый стиль",
        "<noscript>незакрытый noscript",
    ],
)
def test_parser_rejects_truncated_open_state(truncated_tail: str) -> None:
    payload = (
        "<html><body><h1>Рейтинговые действия</h1>"
        f"{_VALID_ACTION}"
        f"{truncated_tail}"
    ).encode()

    with pytest.raises(
        ExpertRaRatingActionsSourceError,
        match=CreditRatingSourceErrorCode.HTML_INVALID.value,
    ):
        parse_expert_ra_issuer_rating_actions_html(
            payload,
            retrieved_at=NOW,
        )


@pytest.mark.parametrize("wrong_closing_tag", ["style", "script"])
def test_parser_rejects_mismatched_ignored_tag(
    wrong_closing_tag: str,
) -> None:
    payload = (
        f"<html><body><noscript></{wrong_closing_tag}>"
        "<h1>Рейтинговые действия</h1>"
        f"{_VALID_ACTION}"
        "<h2>Аналитика</h2></body></html>"
    ).encode()

    with pytest.raises(
        ExpertRaRatingActionsSourceError,
        match=CreditRatingSourceErrorCode.HTML_INVALID.value,
    ):
        parse_expert_ra_issuer_rating_actions_html(
            payload,
            retrieved_at=NOW,
        )
