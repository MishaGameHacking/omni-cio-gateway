from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


class UpstreamError(RuntimeError):
    def __init__(self, component: str, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.component = component
        self.status_code = status_code


@dataclass(slots=True)
class GatewayClient:
    base_url: str
    api_key: str
    timeout_seconds: float = 20.0
    transport: httpx.AsyncBaseTransport | None = None

    async def get(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.get(url, params=params, headers=headers)
        except httpx.HTTPError as exc:
            raise UpstreamError("omni_gateway", "Gateway connection failed") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise UpstreamError(
                "omni_gateway",
                "Gateway returned a non-JSON response",
                status_code=response.status_code,
            ) from exc

        if response.status_code >= 400:
            detail = payload.get("detail") if isinstance(payload, dict) else None
            message = "Gateway request failed"
            if isinstance(detail, dict):
                message = str(detail.get("message") or detail.get("code") or message)
            elif detail:
                message = str(detail)
            raise UpstreamError(
                "omni_gateway",
                message,
                status_code=response.status_code,
            )
        if not isinstance(payload, dict):
            raise UpstreamError("omni_gateway", "Gateway JSON must be an object")
        return payload


@dataclass(slots=True)
class TelegramClient:
    bot_token: str
    timeout_seconds: float = 20.0
    transport: httpx.AsyncBaseTransport | None = None

    @property
    def _api_base(self) -> str:
        return f"https://api.telegram.org/bot{self.bot_token}"

    async def call(self, method: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        # Never include the token-bearing URL in raised errors or logs.
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.post(
                    f"{self._api_base}/{method}",
                    json=payload or {},
                )
        except httpx.HTTPError as exc:
            raise UpstreamError("telegram", f"Telegram method {method} failed") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise UpstreamError(
                "telegram",
                f"Telegram method {method} returned non-JSON",
                status_code=response.status_code,
            ) from exc
        if response.status_code >= 400 or not data.get("ok", False):
            description = str(data.get("description") or "Telegram API error")
            raise UpstreamError(
                "telegram",
                description,
                status_code=response.status_code,
            )
        return data

    async def send_message(self, chat_id: int, text: str) -> None:
        for chunk in split_message(text):
            await self.call(
                "sendMessage",
                {
                    "chat_id": chat_id,
                    "text": chunk,
                    "disable_web_page_preview": True,
                },
            )

    async def set_webhook(self, *, url: str, secret_token: str) -> None:
        await self.call(
            "setWebhook",
            {
                "url": url,
                "secret_token": secret_token,
                "allowed_updates": ["message"],
                "drop_pending_updates": False,
                "max_connections": 20,
            },
        )

    async def set_commands(self, commands: list[dict[str, str]]) -> None:
        await self.call("setMyCommands", {"commands": commands})

    async def get_me(self) -> dict[str, Any]:
        return await self.call("getMe")


def split_message(text: str, *, limit: int = 3500) -> list[str]:
    clean = text.strip() or "—"
    if len(clean) <= limit:
        return [clean]
    chunks: list[str] = []
    remainder = clean
    while remainder:
        if len(remainder) <= limit:
            chunks.append(remainder)
            break
        split_at = remainder.rfind("\n", 0, limit)
        if split_at < limit // 2:
            split_at = limit
        chunks.append(remainder[:split_at].rstrip())
        remainder = remainder[split_at:].lstrip()
    return chunks
