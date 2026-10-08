from __future__ import annotations

import io
import json
import urllib.error
import urllib.parse
from unittest.mock import patch

import pytest

from omnicio.vkid import VKIDClient, VKIDRejected, VKIDUnavailable


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, limit: int = -1) -> bytes:
        body = json.dumps(self.payload).encode()
        return body if limit < 0 else body[:limit]


def test_authorization_url_uses_oauth21_pkce_parameters() -> None:
    client = VKIDClient(
        app_id="123456",
        redirect_uri="https://omnicio.ru/api/auth/vkid/callback",
    )

    url = client.authorization_url(
        state="state-123",
        code_challenge="challenge-123",
    )
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "id.vk.ru"
    assert parsed.path == "/authorize"
    assert params["client_id"] == ["123456"]
    assert params["app_id"] == ["123456"]
    assert params["response_type"] == ["code"]
    assert params["state"] == ["state-123"]
    assert params["code_challenge"] == ["challenge-123"]
    assert params["code_challenge_method"] == ["s256"]
    assert params["redirect_uri"] == [
        "https://omnicio.ru/api/auth/vkid/callback"
    ]


def test_exchange_code_returns_provider_verified_user_id() -> None:
    client = VKIDClient(
        app_id="123456",
        redirect_uri="https://omnicio.ru/api/auth/vkid/callback",
    )
    response = FakeResponse(
        {
            "state": "state-123",
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "user_id": 987654321,
        }
    )

    with patch("urllib.request.OpenerDirector.open", return_value=response) as urlopen:
        identity = client.exchange_code(
            code="authorization-code",
            device_id="device-1",
            code_verifier="v" * 64,
            expected_state="state-123",
        )

    assert identity.user_id == "987654321"
    request = urlopen.call_args.args[0]
    params = urllib.parse.parse_qs(urllib.parse.urlparse(request.full_url).query)
    body = urllib.parse.parse_qs(request.data.decode())
    assert params["grant_type"] == ["authorization_code"]
    assert params["client_id"] == ["123456"]
    assert params["state"] == ["state-123"]
    assert params["device_id"] == ["device-1"]
    assert params["code_verifier"] == ["v" * 64]
    assert body == {"code": ["authorization-code"]}


def test_exchange_code_rejects_state_mismatch() -> None:
    client = VKIDClient(
        app_id="123456",
        redirect_uri="https://omnicio.ru/api/auth/vkid/callback",
    )
    response = FakeResponse(
        {
            "state": "other-state",
            "access_token": "access-token",
            "user_id": 987654321,
        }
    )

    with (
        patch("urllib.request.OpenerDirector.open", return_value=response),
        pytest.raises(VKIDRejected, match="state mismatch"),
    ):
        client.exchange_code(
            code="authorization-code",
            device_id="device-1",
            code_verifier="v" * 64,
            expected_state="state-123",
        )


@pytest.mark.parametrize("user_id", ["", "0", "-1", "not-a-number", "²", "１２３", "9" * 129])
def test_exchange_code_rejects_invalid_user_id(user_id: str) -> None:
    client = VKIDClient(
        app_id="123456",
        redirect_uri="https://omnicio.ru/api/auth/vkid/callback",
    )
    response = FakeResponse(
        {
            "state": "state-123",
            "access_token": "access-token",
            "user_id": user_id,
        }
    )

    with (
        patch("urllib.request.OpenerDirector.open", return_value=response),
        pytest.raises(VKIDRejected, match="valid user id"),
    ):
        client.exchange_code(
            code="authorization-code",
            device_id="device-1",
            code_verifier="v" * 64,
            expected_state="state-123",
        )


def test_provider_401_is_rejected_without_response_body_leakage() -> None:
    error = urllib.error.HTTPError(
        "https://id.vk.ru/oauth2/auth",
        401,
        "Unauthorized",
        {},
        io.BytesIO(b'{"error":"secret provider details"}'),
    )
    client = VKIDClient(
        app_id="123456",
        redirect_uri="https://omnicio.ru/api/auth/vkid/callback",
    )

    with (
        patch("urllib.request.OpenerDirector.open", side_effect=error),
        pytest.raises(VKIDRejected, match="HTTP 401"),
    ):
        client.exchange_code(
            code="bad-code",
            device_id="device-1",
            code_verifier="v" * 64,
            expected_state="state-123",
        )


def test_invalid_app_id_fails_before_network_call() -> None:
    client = VKIDClient(
        app_id="not-numeric",
        redirect_uri="https://omnicio.ru/api/auth/vkid/callback",
    )

    with (
        patch("urllib.request.OpenerDirector.open") as urlopen,
        pytest.raises(VKIDRejected, match="app id"),
    ):
        client.authorization_url(
            state="state-123",
            code_challenge="challenge-123",
        )

    urlopen.assert_not_called()


@pytest.mark.parametrize(
    "body", [b" " * 65_537, b'\xff', b'{"id":' + b'9' * 5000 + b'}'],
    ids=["oversized-response", "invalid-utf8", "oversized-json-integer"],
)
def test_malformed_or_oversized_identity_response_fails_closed(body: bytes) -> None:
    client = VKIDClient("123", "https://omnicio.ru/api/auth/vkid/callback")
    with (
        patch("urllib.request.OpenerDirector.open", return_value=io.BytesIO(body)) as request,
        pytest.raises(VKIDUnavailable),
    ):
        client.exchange_code(code="synthetic-code", device_id="device",
                             code_verifier="v" * 64, expected_state="state")
    request.assert_called_once()
