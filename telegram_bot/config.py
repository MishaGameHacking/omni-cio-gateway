from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
import re
from typing import Mapping

from . import TELEGRAM_COMPANION_VERSION


_WEBHOOK_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{1,256}$")


def _truthy(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_int_set(raw: str | None) -> frozenset[int]:
    values: set[int] = set()
    for item in (raw or "").replace(";", ",").split(","):
        item = item.strip()
        if not item:
            continue
        try:
            parsed = int(item)
        except ValueError as exc:
            raise ValueError("TELEGRAM_ALLOWED_USER_IDS must contain integers") from exc
        if parsed <= 0:
            raise ValueError("TELEGRAM_ALLOWED_USER_IDS must contain positive integers")
        values.add(parsed)
    return frozenset(values)


@dataclass(frozen=True, slots=True)
class Settings:
    telegram_bot_token: str
    telegram_webhook_secret: str
    telegram_allowed_user_ids: frozenset[int]
    omni_gateway_url: str
    omni_gateway_api_key: str
    public_base_url: str
    auto_configure: bool = True
    request_timeout_seconds: float = 20.0
    max_response_chars: int = 12_000
    min_request_interval_seconds: float = 1.5
    gateway_retry_attempts: int = 2
    gateway_retry_delay_seconds: float = 5.0
    version: str = TELEGRAM_COMPANION_VERSION

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        source = os.environ if env is None else env
        public_base_url = (
            source.get("TELEGRAM_PUBLIC_BASE_URL")
            or source.get("RENDER_EXTERNAL_URL")
            or ""
        ).strip().rstrip("/")
        gateway_key = (
            source.get("OMNI_GATEWAY_API_KEY")
            or source.get("GATEWAY_API_KEY")
            or ""
        ).strip()
        return cls(
            telegram_bot_token=source.get("TELEGRAM_BOT_TOKEN", "").strip(),
            telegram_webhook_secret=source.get("TELEGRAM_WEBHOOK_SECRET", "").strip(),
            telegram_allowed_user_ids=_parse_int_set(
                source.get("TELEGRAM_ALLOWED_USER_IDS")
            ),
            omni_gateway_url=source.get("OMNI_GATEWAY_URL", "").strip().rstrip("/"),
            omni_gateway_api_key=gateway_key,
            public_base_url=public_base_url,
            auto_configure=_truthy(
                source.get("TELEGRAM_AUTO_CONFIGURE"),
                default=True,
            ),
            request_timeout_seconds=float(
                source.get("TELEGRAM_REQUEST_TIMEOUT_SECONDS", "20")
            ),
            max_response_chars=int(
                source.get("TELEGRAM_MAX_RESPONSE_CHARS", "12000")
            ),
            min_request_interval_seconds=float(
                source.get("TELEGRAM_MIN_REQUEST_INTERVAL_SECONDS", "1.5")
            ),
            gateway_retry_attempts=max(
                0,
                int(source.get("TELEGRAM_GATEWAY_RETRY_ATTEMPTS", "2")),
            ),
            gateway_retry_delay_seconds=max(
                0.0,
                float(source.get("TELEGRAM_GATEWAY_RETRY_DELAY_SECONDS", "5")),
            ),
        )

    @property
    def webhook_secret_token(self) -> str:
        """Return a Telegram-compatible secret token without exposing the source seed."""
        if not self.telegram_webhook_secret:
            return ""
        if _WEBHOOK_TOKEN_RE.fullmatch(self.telegram_webhook_secret):
            return self.telegram_webhook_secret
        return hashlib.sha256(self.telegram_webhook_secret.encode("utf-8")).hexdigest()

    @property
    def webhook_url(self) -> str:
        if not self.public_base_url:
            return ""
        return f"{self.public_base_url}/telegram/webhook"

    @property
    def missing_required(self) -> tuple[str, ...]:
        missing: list[str] = []
        if not self.telegram_bot_token:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not self.telegram_webhook_secret:
            missing.append("TELEGRAM_WEBHOOK_SECRET")
        if not self.telegram_allowed_user_ids:
            missing.append("TELEGRAM_ALLOWED_USER_IDS")
        if not self.omni_gateway_url:
            missing.append("OMNI_GATEWAY_URL")
        if not self.omni_gateway_api_key:
            missing.append("OMNI_GATEWAY_API_KEY")
        if not self.public_base_url:
            missing.append("TELEGRAM_PUBLIC_BASE_URL or RENDER_EXTERNAL_URL")
        return tuple(missing)

    @property
    def ready(self) -> bool:
        return not self.missing_required
