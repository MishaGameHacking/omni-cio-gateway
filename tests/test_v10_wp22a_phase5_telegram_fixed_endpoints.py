from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit

import httpx

from omni_cio.web.identity_v1 import IdentityProviderV1, VerifiedExternalIdentityV1
from omni_cio.web.provider_auth_v1 import AuthorizationTransactionRegistryV1
from omni_cio.web.telegram_oidc_v1 import (
    TELEGRAM_OIDC_JWKS_ENDPOINT,
    TELEGRAM_OIDC_TOKEN_ENDPOINT,
    TelegramOidcConfigV1,
    TelegramOidcRuntimeV1,
    _bounded_jwks_response,
)


NOW = datetime(2026, 8, 25, 21, 0, tzinfo=timezone.utc)
CLIENT_ID = "123456789"
CLIENT_SECRET = "fixture-client-secret-value"
CALLBACK = "https://omni.example/api/v10/web/auth/telegram/callback"


class FixtureVerifier:
    def verify(
        self,
        id_token: str,
        *,
        expected_nonce: str,
        now: datetime,
        client: httpx.Client,
    ) -> VerifiedExternalIdentityV1:
        del expected_nonce, now, client
        assert id_token == "fixture-id-token"
        return VerifiedExternalIdentityV1(
            provider=IdentityProviderV1.TELEGRAM,
            subject="424242",
        )


def test_telegram_callback_data_cannot_rewrite_token_endpoint() -> None:
    requests: list[httpx.Request] = []
    hostile_code = "code&redirect_uri=https://evil.example/callback"

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"id_token": "fixture-id-token"})

    runtime = TelegramOidcRuntimeV1(
        config=TelegramOidcConfigV1(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            redirect_uri=CALLBACK,
        ),
        transactions=AuthorizationTransactionRegistryV1(),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        verifier=FixtureVerifier(),
    )
    start = runtime.start(now=NOW)
    state = parse_qs(urlsplit(start.authorization_url).query)["state"][0]

    identity = runtime.complete(
        state=state,
        code=hostile_code,
        browser_proof=start.browser_proof,
        now=NOW,
    )

    assert identity.subject == "424242"
    assert len(requests) == 1
    request = requests[0]
    expected = urlsplit(TELEGRAM_OIDC_TOKEN_ENDPOINT)
    assert request.method == "POST"
    assert (request.url.scheme, request.url.host, request.url.path) == (
        expected.scheme,
        expected.hostname,
        expected.path,
    )
    form = parse_qs(request.content.decode())
    assert form["code"] == [hostile_code]
    assert form["redirect_uri"] == [CALLBACK]


def test_telegram_jwks_fetch_uses_fixed_endpoint() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"keys": []})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert _bounded_jwks_response(client, timeout_seconds=1.0) == {"keys": []}

    assert len(requests) == 1
    request = requests[0]
    expected = urlsplit(TELEGRAM_OIDC_JWKS_ENDPOINT)
    assert request.method == "GET"
    assert (request.url.scheme, request.url.host, request.url.path) == (
        expected.scheme,
        expected.hostname,
        expected.path,
    )
    assert request.url.query == b""
