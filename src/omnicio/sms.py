"""SMS provider boundary."""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Protocol


class SmsDeliveryError(RuntimeError):
    """Raised when an SMS provider does not confirm delivery acceptance."""


class SmsProvider(Protocol):
    def send_otp(self, phone: str, code: str) -> str | None:
        """Send an OTP and return the provider message identifier."""


@dataclass(frozen=True, slots=True)
class DisabledSmsProvider:
    def send_otp(self, phone: str, code: str) -> str | None:
        raise SmsDeliveryError("SMS provider is disabled")


@dataclass(frozen=True, slots=True)
class SmsAeroSmsProvider:
    login: str
    api_key: str
    sender: str
    timeout_seconds: int = 10

    base_url: str = "https://gate.smsaero.ru/v2"

    def send_otp(self, phone: str, code: str) -> str | None:
        payload = self._request(
            "sms/send",
            {
                "number": phone.lstrip("+"),
                "sign": self.sender,
                "text": (
                    f"OmniCIO: код входа {code}. "
                    "Никому не сообщайте этот код."
                ),
            },
        )
        return _message_id(payload)

    def test_send(self, phone: str) -> str | None:
        """Exercise SMS Aero test delivery without sending an SMS or charging balance."""
        payload = self._request(
            "sms/testsend",
            {
                "number": phone.lstrip("+"),
                "sign": self.sender,
                "text": "OmniCIO API test",
            },
        )
        return _message_id(payload)

    def _request(self, method: str, params: dict[str, str]) -> object:
        if not self.login or not self.api_key or not self.sender:
            raise SmsDeliveryError("SMS provider credentials are incomplete")

        credentials = base64.b64encode(
            f"{self.login}:{self.api_key}".encode()
        ).decode("ascii")
        request = urllib.request.Request(
            f"{self.base_url}/{method}",
            data=urllib.parse.urlencode(params).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise SmsDeliveryError(f"SMS provider HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            # Do not auto-retry an ambiguous send. A retry may duplicate a live SMS.
            raise SmsDeliveryError(
                f"SMS provider result is ambiguous: {type(exc).__name__}"
            ) from exc

        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError as exc:
            raise SmsDeliveryError("SMS provider returned invalid JSON") from exc

        if not isinstance(parsed, dict) or parsed.get("success") is not True:
            raise SmsDeliveryError("SMS provider rejected the request")
        return parsed.get("data")


def _message_id(data: object) -> str | None:
    if isinstance(data, list) and data and isinstance(data[0], dict):
        message_id = data[0].get("id")
    elif isinstance(data, dict):
        message_id = data.get("id")
    else:
        message_id = None
    return str(message_id) if message_id is not None else None


def build_sms_provider(
    name: str,
    *,
    login: str,
    token: str,
    sender: str,
) -> SmsProvider:
    if name == "smsaero":
        return SmsAeroSmsProvider(login=login, api_key=token, sender=sender)
    if name == "disabled":
        return DisabledSmsProvider()
    raise SmsDeliveryError(f"unsupported SMS provider: {name}")
