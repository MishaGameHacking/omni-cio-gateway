"""SMS provider boundary."""

from __future__ import annotations

import json
import urllib.error
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
class MtsExolveSmsProvider:
    token: str
    sender: str
    timeout_seconds: int = 10

    endpoint: str = "https://api.exolve.ru/messaging/v1/SendSMS"

    def send_otp(self, phone: str, code: str) -> str | None:
        if not self.token or not self.sender:
            raise SmsDeliveryError("SMS provider credentials are incomplete")

        payload = {
            "number": self.sender.lstrip("+"),
            "destination": phone.lstrip("+"),
            "text": f"Код входа OmniCIO: {code}. Никому не сообщайте этот код.",
        }
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            safe_body = exc.read().decode("utf-8", errors="replace")[:300]
            raise SmsDeliveryError(
                f"SMS provider HTTP {exc.code}: {safe_body}"
            ) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            # Do not auto-retry an ambiguous send. A retry may duplicate the SMS.
            raise SmsDeliveryError(
                f"SMS provider result is ambiguous: {type(exc).__name__}"
            ) from exc

        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError as exc:
            raise SmsDeliveryError("SMS provider returned invalid JSON") from exc

        message_id = parsed.get("message_id")
        return str(message_id) if message_id is not None else None


def build_sms_provider(name: str, *, token: str, sender: str) -> SmsProvider:
    if name == "mts_exolve":
        return MtsExolveSmsProvider(token=token, sender=sender)
    if name == "disabled":
        return DisabledSmsProvider()
    raise SmsDeliveryError(f"unsupported SMS provider: {name}")
