from datetime import datetime, timezone

import pytest

from omni_cio.contracts.v1.market import RatingAction
from omni_cio.contracts.v1.ratings import CreditRatingSourceErrorCode
from omni_cio.market.expert_ra_rating_actions_v1 import (
    ExpertRaRatingActionsSourceError,
    parse_expert_ra_issuer_rating_actions_html,
)


NOW = datetime(2026, 7, 31, 9, 0, tzinfo=timezone.utc)


def _page(title: str) -> bytes:
    return (
        "<html><body><h1>Рейтинговые действия</h1>"
        f'<a href="/releases/2026/jul22">{title}</a>'
        "<span>22.07.2026</span>"
        "<h2>Аналитика</h2></body></html>"
    ).encode()


def test_parser_accepts_official_withdrawal_with_watch_status_removed() -> None:
    result = parse_expert_ra_issuer_rating_actions_html(
        _page(
            '«Эксперт РА» отозвал без подтверждения кредитный рейтинг '
            'ООО "Восток-Ойл" и снял статус «под наблюдением»'
        ),
        retrieved_at=NOW,
    )

    assert len(result.records) == 1
    record = result.records[0]
    assert record.subject_name == 'ООО "Восток-Ойл"'
    assert record.action is RatingAction.WITHDRAWN
    assert record.rating is None
    assert record.outlook is None


def test_parser_rejects_unknown_withdrawal_suffix() -> None:
    with pytest.raises(
        ExpertRaRatingActionsSourceError,
        match=CreditRatingSourceErrorCode.SCHEMA_INVALID.value,
    ):
        parse_expert_ra_issuer_rating_actions_html(
            _page(
                '«Эксперт РА» отозвал без подтверждения кредитный рейтинг '
                'ООО "Восток-Ойл" и добавил неизвестный статус'
            ),
            retrieved_at=NOW,
        )
