from datetime import datetime, timezone

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
_SENTINEL = "test-sentinel"


class _InjectedClientAuth(httpx.Auth):
    def auth_flow(self, request: httpx.Request):
        request.headers["X-Test-Injected"] = _SENTINEL
        yield request


def test_injected_client_credentials_are_isolated_from_public_request() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            content=PAYLOAD,
        )

    with httpx.Client(
        transport=httpx.MockTransport(handler),
        auth=_InjectedClientAuth(),
        headers={
            "Authorization": _SENTINEL,
            "Cookie": _SENTINEL,
            "Proxy-Authorization": _SENTINEL,
            "X-API-Key": _SENTINEL,
        },
        cookies={"test-cookie": _SENTINEL},
    ) as client:
        result = fetch_expert_ra_issuer_rating_actions(
            client=client,
            retrieved_at=NOW,
        )

    assert result.status is CreditRatingSourceStatus.AVAILABLE
    assert len(requests) == 1
    for header in (
        "authorization",
        "cookie",
        "proxy-authorization",
        "x-api-key",
        "x-test-injected",
    ):
        assert requests[0].headers.get(header) is None
    assert requests[0].headers["accept"] == "text/html,application/xhtml+xml"
    assert requests[0].headers["user-agent"] == "omni-cio-gateway/1.0"
    assert requests[0].extensions["timeout"] == httpx.Timeout(
        DEFAULT_EXPERT_RA_TIMEOUT_SECONDS
    ).as_dict()


def test_redirect_is_not_followed_even_when_injected_client_allows_redirects() -> None:
    urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        return httpx.Response(
            302,
            headers={"location": "https://example.com/test-target"},
        )

    with httpx.Client(
        transport=httpx.MockTransport(handler),
        follow_redirects=True,
    ) as client:
        result = fetch_expert_ra_issuer_rating_actions(
            client=client,
            retrieved_at=NOW,
        )

    assert urls == [EXPERT_RA_RATING_ACTIONS_ENDPOINT]
    assert result.status is CreditRatingSourceStatus.UNAVAILABLE
    assert result.error_code is CreditRatingSourceErrorCode.HTTP_ERROR
