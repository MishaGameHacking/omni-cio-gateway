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

    endpoint: str = "https://gate.smsaero.ru/v2/sms/send"

    def send_otp(self, phone: str, code: str) -> str | None:
        if not self.login or not self.api_key or not self.sender:
            raise SmsDeliveryError("SMS provider credentials are incomplete")

        encoded = urllib.parse.urlencode(
            {
                "number": phone.lstrip("+"),
                "sign": self.sender,
                "text": (
                    f"OmniCIO: код входа {code}. "
                    "Никому не сообщайте этот код."
                ),
            }
        ).encode("utf-8")
        credentials = base64.b64encode(
            f"{self.login}:{self.api_key}".encode("utf-8")
        ).decode("ascii")
        request = urllib.request.Request(
            self.endpoint,
            data=encoded,
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
            # Do not auto-retry an ambiguous send. A retry may duplicate the SMS.
            raise SmsDeliveryError(
                f"SMS provider result is ambiguous: {type(exc).__name__}"
            ) from exc

        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError as exc:
            raise SmsDeliveryError("SMS provider returned invalid JSON") from exc

        if parsed.get("success") is not True:
            raise SmsDeliveryError("SMS provider rejected the message")

        data = parsed.get("data")
        if isinstance(data, list) and data:
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
