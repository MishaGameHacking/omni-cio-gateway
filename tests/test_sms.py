from __future__ import annotations

import base64
import json
import urllib.parse
from unittest.mock import patch

import pytest

from omnicio.sms import SmsAeroSmsProvider, SmsDeliveryError


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_smsaero_send_uses_basic_auth_and_expected_payload() -> None:
    provider = SmsAeroSmsProvider(
        login="user@example.test",
        api_key="secret-key",
        sender="SMS Aero",
    )
    response = FakeResponse(
        {"success": True, "data": [{"id": 42}], "message": None}
    )

    with patch("urllib.request.urlopen", return_value=response) as urlopen:
        message_id = provider.send_otp("+79161234567", "654321")

    assert message_id == "42"
    request = urlopen.call_args.args[0]
    assert request.full_url == "https://gate.smsaero.ru/v2/sms/send"
    expected_auth = base64.b64encode(
        b"user@example.test:secret-key"
    ).decode("ascii")
    assert request.get_header("Authorization") == f"Basic {expected_auth}"

    params = urllib.parse.parse_qs(request.data.decode("utf-8"))
    assert params["number"] == ["79161234567"]
    assert params["sign"] == ["SMS Aero"]
    assert "654321" in params["text"][0]
    assert "OmniCIO" in params["text"][0]


def test_smsaero_test_send_uses_non_delivery_endpoint() -> None:
    provider = SmsAeroSmsProvider(
        login="user@example.test",
        api_key="test-key",
        sender="SMS Aero",
    )
    response = FakeResponse(
        {"success": True, "data": {"id": 7}, "message": None}
    )

    with patch("urllib.request.urlopen", return_value=response) as urlopen:
        message_id = provider.test_send("+79161234567")

    assert message_id == "7"
    request = urlopen.call_args.args[0]
    assert request.full_url == "https://gate.smsaero.ru/v2/sms/testsend"


def test_smsaero_rejects_unsuccessful_provider_response() -> None:
    provider = SmsAeroSmsProvider(
        login="user@example.test",
        api_key="test-key",
        sender="SMS Aero",
    )
    response = FakeResponse(
        {"success": False, "data": None, "message": "invalid api key"}
    )

    with (
        patch("urllib.request.urlopen", return_value=response),
        pytest.raises(SmsDeliveryError, match="rejected"),
    ):
        provider.test_send("+79161234567")
