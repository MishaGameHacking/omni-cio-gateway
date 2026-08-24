from __future__ import annotations

from datetime import datetime, timezone
import json
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from omni_cio.web.identity_v1 import IdentityProviderV1, VerifiedExternalIdentityV1
from omni_cio.web.provider_auth_v1 import (
    AuthorizationTransactionRegistryV1,
    ProviderAuthenticationRuntimeLike,
    ProviderAuthorizationError,
)
from omni_cio.web.telegram_oidc_v1 import (
    TelegramOidcConfigV1,
    TelegramOidcError,
    TelegramOidcRuntimeV1,
)
from omni_cio.web.vk_id_oauth_v1 import (
    VK_ID_AUTHORIZATION_ENDPOINT,
    VK_ID_TOKEN_ENDPOINT,
    VkIdOauthConfigV1,
    VkIdOauthError,
    VkIdOauthRuntimeV1,
)

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
CLIENT_ID = "123456789"
CALLBACK = "https://omni.example/api/v10/web/auth/vk-id/callback"
TELEGRAM_CALLBACK = "https://omni.example/api/v10/web/auth/telegram/callback"
TELEGRAM_AUTH_FIXTURE = "fixture-" + "telegram-client-material"


def _config() -> VkIdOauthConfigV1:
    return VkIdOauthConfigV1(client_id=CLIENT_ID, redirect_uri=CALLBACK)


def _assert_runtime_contract(runtime: ProviderAuthenticationRuntimeLike) -> None:
    assert runtime.provider in {IdentityProviderV1.TELEGRAM, IdentityProviderV1.VK_ID}


def test_vk_and_telegram_conform_to_provider_runtime_contract() -> None:
    registry = AuthorizationTransactionRegistryV1()
    _assert_runtime_contract(VkIdOauthRuntimeV1(config=_config(), transactions=registry))
    _assert_runtime_contract(
        TelegramOidcRuntimeV1(
            config=TelegramOidcConfigV1(
                client_id=CLIENT_ID,
                client_secret=TELEGRAM_AUTH_FIXTURE,
                redirect_uri=TELEGRAM_CALLBACK,
            ),
            transactions=registry,
        )
    )


def test_start_builds_current_vkid_pkce_authorization_url() -> None:
    runtime = VkIdOauthRuntimeV1(
        config=_config(),
        transactions=AuthorizationTransactionRegistryV1(),
    )

    url = runtime.start(now=NOW)
    parsed = urlsplit(url)
    expected = urlsplit(VK_ID_AUTHORIZATION_ENDPOINT)
    query = parse_qs(parsed.query, keep_blank_values=True)

    assert (parsed.scheme, parsed.netloc, parsed.path) == (
        expected.scheme,
        expected.netloc,
        expected.path,
    )
    assert query["client_id"] == [CLIENT_ID]
    assert query["app_id"] == [CLIENT_ID]
    assert query["redirect_uri"] == [CALLBACK]
    assert query["response_type"] == ["code"]
    assert query["code_challenge_method"] == ["s256"]
    assert len(query["state"][0]) >= 43
    assert len(query["code_challenge"][0]) == 43
    assert query["prompt"] == [""]
    assert "code_verifier" not in query
    assert "scope" not in query


def test_complete_exchanges_code_and_returns_only_verified_vkid_identity() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.method == "POST"
        assert str(request.url).startswith(VK_ID_TOKEN_ENDPOINT + "?")
        query = parse_qs(request.url.query.decode())
        assert query["grant_type"] == ["authorization_code"]
        assert query["redirect_uri"] == [CALLBACK]
        assert query["client_id"] == [CLIENT_ID]
        assert query["device_id"] == ["vk-device-42"]
        assert len(query["code_verifier"][0]) >= 43
        assert request.content.decode() == "code=vk-code"
        return httpx.Response(
            200,
            json={
                "access_token": "fixture-access-material",
                "refresh_token": "fixture-refresh-material",
                "state": query["state"][0],
                "user_id": 424242,
                "token_type": "Bearer",
                "expires_in": 900,
                "scope": "",
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    runtime = VkIdOauthRuntimeV1(
        config=_config(),
        transactions=AuthorizationTransactionRegistryV1(),
        client=client,
    )
    start = runtime.start(now=NOW)
    state = parse_qs(urlsplit(start).query)["state"][0]

    identity = runtime.complete(
        state=state,
        code="vk-code",
        device_id="vk-device-42",
        now=NOW,
    )

    assert identity == VerifiedExternalIdentityV1(
        provider=IdentityProviderV1.VK_ID,
        subject="424242",
    )
    assert len(requests) == 1
    assert "access" not in repr(identity).lower()
    assert "refresh" not in repr(identity).lower()
    with pytest.raises(ProviderAuthorizationError, match="AUTH_TRANSACTION_NOT_FOUND"):
        runtime.complete(
            state=state,
            code="vk-code",
            device_id="vk-device-42",
            now=NOW,
        )
    assert len(requests) == 1


@pytest.mark.parametrize(
    "device_id",
    [None, "", " ", "\n", "x" * 513],
)
def test_invalid_device_id_is_rejected_before_state_is_consumed(
    device_id: str | None,
) -> None:
    registry = AuthorizationTransactionRegistryV1()
    runtime = VkIdOauthRuntimeV1(config=_config(), transactions=registry)
    state = parse_qs(urlsplit(runtime.start(now=NOW)).query)["state"][0]

    with pytest.raises(VkIdOauthError, match="VK_ID_DEVICE_ID_INVALID"):
        runtime.complete(
            state=state,
            code="vk-code",
            device_id=device_id,
            now=NOW,
        )
    assert registry.pending_count(now=NOW) == 1


def test_invalid_code_is_rejected_before_state_is_consumed() -> None:
    registry = AuthorizationTransactionRegistryV1()
    runtime = VkIdOauthRuntimeV1(config=_config(), transactions=registry)
    state = parse_qs(urlsplit(runtime.start(now=NOW)).query)["state"][0]

    with pytest.raises(VkIdOauthError, match="VK_ID_CODE_INVALID"):
        runtime.complete(
            state=state,
            code="contains space",
            device_id="vk-device-42",
            now=NOW,
        )
    assert registry.pending_count(now=NOW) == 1


def test_provider_state_mismatch_fails_closed_after_consuming_transaction() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json={
                "access_token": "fixture-access-material",
                "state": "different-state",
                "user_id": 42,
            },
        )

    registry = AuthorizationTransactionRegistryV1()
    runtime = VkIdOauthRuntimeV1(
        config=_config(),
        transactions=registry,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    state = parse_qs(urlsplit(runtime.start(now=NOW)).query)["state"][0]

    with pytest.raises(VkIdOauthError, match="VK_ID_STATE_MISMATCH"):
        runtime.complete(
            state=state,
            code="vk-code",
            device_id="vk-device-42",
            now=NOW,
        )
    with pytest.raises(ProviderAuthorizationError, match="AUTH_TRANSACTION_NOT_FOUND"):
        runtime.complete(
            state=state,
            code="vk-code",
            device_id="vk-device-42",
            now=NOW,
        )
    assert calls == 1


def test_provider_error_payload_is_generic_and_consumes_transaction() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"error": "invalid_request", "state": "provider-state"},
        )

    runtime = VkIdOauthRuntimeV1(
        config=_config(),
        transactions=AuthorizationTransactionRegistryV1(),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    state = parse_qs(urlsplit(runtime.start(now=NOW)).query)["state"][0]

    with pytest.raises(VkIdOauthError, match="VK_ID_PROVIDER_RESPONSE_INVALID"):
        runtime.complete(
            state=state,
            code="vk-code",
            device_id="vk-device-42",
            now=NOW,
        )
    with pytest.raises(ProviderAuthorizationError, match="AUTH_TRANSACTION_NOT_FOUND"):
        runtime.complete(
            state=state,
            code="vk-code",
            device_id="vk-device-42",
            now=NOW,
        )


def test_network_error_is_generic_and_transaction_stays_consumed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("fixture provider unavailable", request=request)

    runtime = VkIdOauthRuntimeV1(
        config=_config(),
        transactions=AuthorizationTransactionRegistryV1(),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    state = parse_qs(urlsplit(runtime.start(now=NOW)).query)["state"][0]

    with pytest.raises(VkIdOauthError, match="VK_ID_NETWORK_ERROR"):
        runtime.complete(
            state=state,
            code="vk-code",
            device_id="vk-device-42",
            now=NOW,
        )
    with pytest.raises(ProviderAuthorizationError, match="AUTH_TRANSACTION_NOT_FOUND"):
        runtime.complete(
            state=state,
            code="vk-code",
            device_id="vk-device-42",
            now=NOW,
        )


def test_provider_response_is_bounded_before_json_parse() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={
                "content-type": "application/json",
                "content-length": "999999",
            },
            content=b"{}",
        )

    runtime = VkIdOauthRuntimeV1(
        config=_config(),
        transactions=AuthorizationTransactionRegistryV1(),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    state = parse_qs(urlsplit(runtime.start(now=NOW)).query)["state"][0]

    with pytest.raises(VkIdOauthError, match="VK_ID_PROVIDER_RESPONSE_TOO_LARGE"):
        runtime.complete(
            state=state,
            code="vk-code",
            device_id="vk-device-42",
            now=NOW,
        )


def test_duplicate_provider_json_members_are_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = b'{"state":"a","state":"b","user_id":42}'
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            content=payload,
        )

    runtime = VkIdOauthRuntimeV1(
        config=_config(),
        transactions=AuthorizationTransactionRegistryV1(),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    state = parse_qs(urlsplit(runtime.start(now=NOW)).query)["state"][0]

    with pytest.raises(VkIdOauthError, match="VK_ID_PROVIDER_JSON_INVALID"):
        runtime.complete(
            state=state,
            code="vk-code",
            device_id="vk-device-42",
            now=NOW,
        )


@pytest.mark.parametrize(
    "response_patch",
    [
        {"access_token": None},
        {"access_token": ""},
        {"user_id": None},
        {"user_id": True},
        {"user_id": 0},
        {"user_id": "42"},
    ],
)
def test_ambiguous_token_identity_fields_fail_closed(
    response_patch: dict[str, object],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        query = parse_qs(request.url.query.decode())
        payload: dict[str, object] = {
            "access_token": "fixture-access-material",
            "state": query["state"][0],
            "user_id": 42,
        }
        payload.update(response_patch)
        return httpx.Response(200, json=payload)

    runtime = VkIdOauthRuntimeV1(
        config=_config(),
        transactions=AuthorizationTransactionRegistryV1(),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    state = parse_qs(urlsplit(runtime.start(now=NOW)).query)["state"][0]

    with pytest.raises(VkIdOauthError, match="VK_ID_TOKEN_RESPONSE_INVALID"):
        runtime.complete(
            state=state,
            code="vk-code",
            device_id="vk-device-42",
            now=NOW,
        )


def test_wrong_provider_state_cannot_be_consumed_by_vkid() -> None:
    registry = AuthorizationTransactionRegistryV1()
    telegram = registry.begin(
        provider=IdentityProviderV1.TELEGRAM,
        redirect_uri=TELEGRAM_CALLBACK,
        now=NOW,
    )
    runtime = VkIdOauthRuntimeV1(config=_config(), transactions=registry)

    with pytest.raises(
        ProviderAuthorizationError,
        match="AUTH_TRANSACTION_PROVIDER_MISMATCH",
    ):
        runtime.complete(
            state=telegram.state,
            code="vk-code",
            device_id="vk-device-42",
            now=NOW,
        )
    assert registry.pending_count(now=NOW) == 1


def test_telegram_rejects_vkid_device_id_without_consuming_state() -> None:
    registry = AuthorizationTransactionRegistryV1()
    runtime = TelegramOidcRuntimeV1(
        config=TelegramOidcConfigV1(
            client_id=CLIENT_ID,
            client_secret=TELEGRAM_AUTH_FIXTURE,
            redirect_uri=TELEGRAM_CALLBACK,
        ),
        transactions=registry,
    )
    state = parse_qs(urlsplit(runtime.start(now=NOW)).query)["state"][0]

    with pytest.raises(TelegramOidcError, match="TELEGRAM_OIDC_CALLBACK_INVALID"):
        runtime.complete(
            state=state,
            code="telegram-code",
            device_id="vk-device-42",
            now=NOW,
        )
    assert registry.pending_count(now=NOW) == 1


def test_vkid_config_is_fail_closed_and_contains_no_secret_field() -> None:
    with pytest.raises(ValueError, match="VK_ID_CLIENT_ID_INVALID"):
        VkIdOauthConfigV1(client_id="not-numeric", redirect_uri=CALLBACK)
    with pytest.raises(ValueError, match="VK_ID_REDIRECT_URI_INVALID"):
        VkIdOauthConfigV1(client_id=CLIENT_ID, redirect_uri="http://omni.example/cb")
    with pytest.raises(ValueError, match="VK_ID_TIMEOUT_INVALID"):
        VkIdOauthConfigV1(
            client_id=CLIENT_ID,
            redirect_uri=CALLBACK,
            timeout_seconds=60.0,
        )
    assert "secret" not in repr(_config()).lower()
