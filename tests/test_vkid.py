from __future__ import annotations

import io
import json
import urllib.error
import urllib.parse
from unittest.mock import patch

import pytest

from omnicio.vkid import VKIDClient, VKIDRejected


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


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


def test_exchange_code_requires_matching_returned_state() -> None:
    client = VKIDClient(
        app_id="123456",
        redirect_uri="https://omnicio.ru/api/auth/vkid/callback",
    )
    response = FakeResponse(
        {
            "state": "state-123",
            "access_token": "access-token",
            "refresh_token": "refresh-token",
        }
    )

    with patch("urllib.request.urlopen", return_value=response) as urlopen:
        token = client.exchange_code(
            code="authorization-code",
            device_id="device-1",
            code_verifier="v" * 64,
            expected_state="state-123",
        )

    assert token == "access-token"
    request = urlopen.call_args.args[0]
    params = urllib.parse.parse_qs(urllib.parse.urlparse(request.full_url).query)
    body = urllib.parse.parse_qs(request.data.decode())
    assert params["grant_type"] == ["authorization_code"]
    assert params["client_id"] == ["123456"]
    assert params["state"] == ["state-123"]
    assert params["device_id"] == ["device-1"]
    assert params["code_verifier"] == ["v" * 64]
    assert body == {"code": ["authorization-code"]}


def test_user_info_extracts_nested_owner_id_without_exposing_tokens() -> None:
    client = VKIDClient(
        app_id="123456",
        redirect_uri="https://omnicio.ru/api/auth/vkid/callback",
    )
    response = FakeResponse(
        {
            "user": {
                "user_id": "987654321",
                "first_name": "Owner",
            }
        }
    )

    with patch("urllib.request.urlopen", return_value=response) as urlopen:
        user = client.user_info("access-token")

    assert user.user_id == "987654321"
    request = urlopen.call_args.args[0]
    body = urllib.parse.parse_qs(request.data.decode())
    assert body == {"access_token": ["access-token"]}


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
        patch("urllib.request.urlopen", side_effect=error),
        pytest.raises(VKIDRejected, match="HTTP 401"),
    ):
        client.exchange_code(
            code="bad-code",
            device_id="device-1",
            code_verifier="v" * 64,
            expected_state="state-123",
        )
