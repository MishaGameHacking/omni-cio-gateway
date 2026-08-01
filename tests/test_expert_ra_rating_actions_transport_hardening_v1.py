from datetime import datetime, timezone
import inspect

import httpx

from omni_cio.contracts.v1.ratings import (
    CreditRatingSourceErrorCode,
    CreditRatingSourceStatus,
)
from omni_cio.market.expert_ra_rating_actions_v1 import (
    DEFAULT_EXPERT_RA_TIMEOUT_SECONDS,
    EXPERT_RA_RATING_ACTIONS_ENDPOINT,
    fetch_expert_ra_issuer_rating_actions,
)


NOW = datetime(2026, 7, 31, 6, 0, tzinfo=timezone.utc)
PAYLOAD = (
    "<html><body><h1>Рейтинговые действия</h1>"
    '<a href="/releases/2026/jul31a">'
    "«Эксперт РА» подтвердил кредитный рейтинг АО «Тест» на уровне ruA"
    '</a><a href="/releases/2026/jul31a">31.07.2026</a>'
    "<h2>Аналитика</h2></body></html>"
).encode()


def test_source_accepts_transport_but_not_shared_client() -> None:
    parameters = inspect.signature(fetch_expert_ra_issuer_rating_actions).parameters
    assert "transport" in parameters
    assert "client" not in parameters


def test_mock_transport_receives_allowlisted_public_request() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            content=PAYLOAD,
        )

    result = fetch_expert_ra_issuer_rating_actions(
        transport=httpx.MockTransport(handler),
        retrieved_at=NOW,
    )

    assert result.status is CreditRatingSourceStatus.AVAILABLE
    assert len(requests) == 1
    assert set(requests[0].headers) == {"host", "accept", "user-agent"}
    assert requests[0].headers["accept"] == "text/html,application/xhtml+xml"
    assert requests[0].headers["user-agent"] == "omni-cio-gateway/1.0"
    assert requests[0].extensions["timeout"] == httpx.Timeout(
        DEFAULT_EXPERT_RA_TIMEOUT_SECONDS
    ).as_dict()


def test_redirect_is_not_followed() -> None:
    urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        return httpx.Response(
            302,
            headers={"location": "https://example.com/test-target"},
        )

    result = fetch_expert_ra_issuer_rating_actions(
        transport=httpx.MockTransport(handler),
        retrieved_at=NOW,
    )

    assert urls == [EXPERT_RA_RATING_ACTIONS_ENDPOINT]
    assert result.status is CreditRatingSourceStatus.UNAVAILABLE
    assert result.error_code is CreditRatingSourceErrorCode.HTTP_ERROR
