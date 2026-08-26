from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit

import httpx

from omni_cio.web.provider_auth_v1 import AuthorizationTransactionRegistryV1
from omni_cio.web.vk_id_oauth_v1 import (
    VK_ID_TOKEN_ENDPOINT,
    VkIdOauthConfigV1,
    VkIdOauthRuntimeV1,
)


NOW = datetime(2026, 8, 25, 21, 0, tzinfo=timezone.utc)
CLIENT_ID = "123456789"
CALLBACK = "https://omni.example/api/v10/web/auth/vk-id/callback"


def test_vkid_callback_data_cannot_rewrite_token_endpoint() -> None:
    requests: list[httpx.Request] = []
    hostile_device_id = "device&redirect_uri=https://evil.example/callback"

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        query = parse_qs(request.url.query.decode())
        return httpx.Response(
            200,
            json={
                "access_token": "fixture-access-material",
                "state": query["state"][0],
                "user_id": 424242,
            },
        )

    runtime = VkIdOauthRuntimeV1(
        config=VkIdOauthConfigV1(client_id=CLIENT_ID, redirect_uri=CALLBACK),
        transactions=AuthorizationTransactionRegistryV1(),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    start = runtime.start(now=NOW)
    state = parse_qs(urlsplit(start.authorization_url).query)["state"][0]

    runtime.complete(
        state=state,
        code="vk-code",
        browser_proof=start.browser_proof,
        device_id=hostile_device_id,
        now=NOW,
    )

    assert len(requests) == 1
    request = requests[0]
    expected = urlsplit(VK_ID_TOKEN_ENDPOINT)
    assert (request.url.scheme, request.url.host, request.url.path) == (
        expected.scheme,
        expected.hostname,
        expected.path,
    )
    query = parse_qs(request.url.query.decode())
    assert query["device_id"] == [hostile_device_id]
    assert query["redirect_uri"] == [CALLBACK]
