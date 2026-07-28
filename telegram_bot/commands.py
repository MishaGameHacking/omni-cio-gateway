from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
import hmac
import time
from typing import Any

from .clients import GatewayClient, TelegramClient, UpstreamError
from .config import Settings
from .formatters import (
    format_analytics,
    format_cash,
    format_connection,
    format_gateway_health,
    format_operations,
    format_portfolio,
    format_report,
    format_system_status,
)


COMMANDS = [
    {"command": "help", "description": "Список безопасных команд"},
    {"command": "status", "description": "Проверить всю цепочку Omni-CIO"},
    {"command": "health", "description": "Проверить Omni-CIO Gateway"},
    {"command": "connection", "description": "Проверить подключение к T-Invest"},
    {"command": "portfolio", "description": "Получить read-only снимок портфеля"},
    {"command": "cash", "description": "Проверить деньги и ликвидность"},
    {"command": "analytics", "description": "Получить аналитику портфеля"},
    {"command": "operations", "description": "Операции; пример: /operations 90"},
    {"command": "report", "description": "Запустить отчёт T-Invest за 31 день"},
    {"command": "report_status", "description": "Проверить готовность отчёта"},
]

HELP_TEXT = """Omni-CIO Telegram Companion v4.0.1

Доступные read-only команды:
/status — Telegram, Gateway и T-Invest
/health — состояние Omni-CIO Gateway
/connection — подключение к T-Invest
/portfolio — краткий снимок портфеля
/cash — деньги и ликвидность
/analytics — структура портфеля
/operations [days] — операции, по умолчанию 90 дней
/report — запустить официальный отчёт за 31 день
/report_status [task_id] — проверить готовность отчёта
/help — эта справка

При холодном запуске Render бот сам повторяет безопасный GET-запрос.
Бот не создаёт заявки и не совершает сделки.
trading_methods=false"""

_RETRYABLE_GATEWAY_STATUSES = {408, 425, 429, 500, 502, 503, 504}


def verify_webhook_secret(received: str | None, expected: str) -> bool:
    if not received or not expected:
        return False
    return hmac.compare_digest(received, expected)


def parse_command(text: str) -> tuple[str, list[str]]:
    parts = text.strip().split()
    if not parts:
        return "", []
    command = parts[0].lower()
    if command.startswith("/"):
        command = command[1:]
    if "@" in command:
        command = command.split("@", 1)[0]
    return command, parts[1:]


@dataclass(slots=True)
class UpdateDeduplicator:
    max_items: int = 512
    _queue: deque[int] = field(default_factory=deque)
    _seen: set[int] = field(default_factory=set)

    def first_time(self, update_id: int) -> bool:
        if update_id in self._seen:
            return False
        self._seen.add(update_id)
        self._queue.append(update_id)
        while len(self._queue) > self.max_items:
            old = self._queue.popleft()
            self._seen.discard(old)
        return True


@dataclass(slots=True)
class UserRateLimiter:
    interval_seconds: float
    _last_seen: dict[int, float] = field(default_factory=dict)

    def allow(self, user_id: int) -> bool:
        now = time.monotonic()
        previous = self._last_seen.get(user_id)
        if previous is not None and now - previous < self.interval_seconds:
            return False
        self._last_seen[user_id] = now
        return True


@dataclass(slots=True)
class CommandRouter:
    settings: Settings
    telegram: TelegramClient
    gateway: GatewayClient
    deduplicator: UpdateDeduplicator = field(default_factory=UpdateDeduplicator)
    report_tasks: dict[int, str] = field(default_factory=dict)
    rate_limiter: UserRateLimiter | None = None

    def __post_init__(self) -> None:
        if self.rate_limiter is None:
            self.rate_limiter = UserRateLimiter(
                self.settings.min_request_interval_seconds
            )

    async def handle_update(self, update: dict[str, Any]) -> None:
        update_id = int(update.get("update_id", 0) or 0)
        if update_id and not self.deduplicator.first_time(update_id):
            return

        message = update.get("message")
        if not isinstance(message, dict):
            return
        chat = message.get("chat")
        sender = message.get("from")
        text = message.get("text")
        if not isinstance(chat, dict) or not isinstance(sender, dict) or not isinstance(text, str):
            return

        chat_id = int(chat.get("id", 0) or 0)
        user_id = int(sender.get("id", 0) or 0)
        if not chat_id or not user_id:
            return
        if chat.get("type") != "private":
            await self.telegram.send_message(chat_id, "Бот работает только в личном чате.")
            return
        if user_id not in self.settings.telegram_allowed_user_ids:
            await self.telegram.send_message(chat_id, "Доступ запрещён.")
            return
        assert self.rate_limiter is not None
        if not self.rate_limiter.allow(user_id):
            await self.telegram.send_message(chat_id, "Слишком частые запросы. Повторите через пару секунд.")
            return

        command, args = parse_command(text)
        await self._typing(chat_id)
        try:
            response = await self._dispatch(chat_id, user_id, command, args)
        except UpstreamError as exc:
            response = self._friendly_upstream_error(exc)
        except ValueError as exc:
            response = f"Некорректные параметры: {exc}"
        except Exception:
            response = "Внутренняя ошибка Telegram Companion. Секретные данные не выведены."
        await self.telegram.send_message(chat_id, response)

    async def _typing(self, chat_id: int) -> None:
        try:
            await self.telegram.send_chat_action(chat_id, "typing")
        except (AttributeError, UpstreamError):
            # Typing status is only a convenience and must never block a command.
            return

    async def _gateway_get(
        self,
        chat_id: int,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        attempts = self.settings.gateway_retry_attempts + 1
        for attempt in range(attempts):
            try:
                return await self.gateway.get(path, params=params)
            except UpstreamError as exc:
                is_retryable = (
                    exc.component == "omni_gateway"
                    and (
                        exc.status_code is None
                        or exc.status_code in _RETRYABLE_GATEWAY_STATUSES
                    )
                )
                if not is_retryable or attempt >= attempts - 1:
                    raise
                if attempt == 0:
                    try:
                        await self.telegram.send_message(
                            chat_id,
                            "⏳ Основной сервер просыпается. Повторяю безопасный запрос…",
                        )
                    except UpstreamError:
                        pass
                delay = self.settings.gateway_retry_delay_seconds * (attempt + 1)
                if delay > 0:
                    await asyncio.sleep(delay)
                await self._typing(chat_id)
        raise UpstreamError("omni_gateway", "Gateway retry policy exhausted")

    async def _dispatch(
        self,
        chat_id: int,
        user_id: int,
        command: str,
        args: list[str],
    ) -> str:
        if command in {"", "start", "help"}:
            return HELP_TEXT
        if command == "status":
            health = await self._gateway_get(chat_id, "/health")
            try:
                connection = await self._gateway_get(chat_id, "/connection")
            except UpstreamError as exc:
                return format_system_status(
                    health,
                    None,
                    connection_error=self._friendly_upstream_error(exc),
                )
            return format_system_status(health, connection)
        if command == "health":
            payload = await self._gateway_get(chat_id, "/health")
            return format_gateway_health(payload)
        if command == "connection":
            payload = await self._gateway_get(chat_id, "/connection")
            return format_connection(payload)
        if command == "portfolio":
            payload = await self._gateway_get(chat_id, "/snapshot")
            return format_portfolio(payload)
        if command == "cash":
            payload = await self._gateway_get(chat_id, "/portfolio/cash-liquidity")
            return format_cash(payload)
        if command == "analytics":
            payload = await self._gateway_get(chat_id, "/portfolio/analytics")
            return format_analytics(payload)
        if command == "operations":
            days = self._parse_days(args, default=90, maximum=3650)
            payload = await self._gateway_get(
                chat_id,
                "/operations/analytics",
                params={"days": days},
            )
            return format_operations(payload, days=days)
        if command == "report":
            payload = await self._gateway_get(
                chat_id,
                "/operations/broker-report-reconciliation",
                params={"days": 31, "wait_seconds": 0},
            )
            task_id = self._extract_task_id(payload)
            if task_id:
                self.report_tasks[user_id] = task_id
            return format_report(payload)
        if command == "report_status":
            task_id = args[0].strip() if args else self.report_tasks.get(user_id, "")
            if not task_id:
                return "Нет сохранённого task_id. Сначала выполните /report или передайте /report_status <task_id>."
            payload = await self._gateway_get(
                chat_id,
                "/operations/broker-report-reconciliation",
                params={
                    "days": 31,
                    "task_id": task_id,
                    "wait_seconds": 10,
                },
            )
            if payload.get("status") != "pending":
                self.report_tasks.pop(user_id, None)
            return format_report(payload, status_command=True)
        return "Неизвестная команда. Используйте /help."

    @staticmethod
    def _friendly_upstream_error(exc: UpstreamError) -> str:
        suffix = f" (HTTP {exc.status_code})" if exc.status_code else ""
        if exc.component == "omni_gateway":
            return (
                f"⚠️ Не удалось получить данные от Omni-CIO Gateway{suffix}. "
                "Повторите команду через минуту или выполните /status."
            )
        return f"⚠️ Ошибка внешнего сервиса {exc.component}{suffix}: {exc}"

    @staticmethod
    def _parse_days(args: list[str], *, default: int, maximum: int) -> int:
        if not args:
            return default
        try:
            days = int(args[0])
        except ValueError as exc:
            raise ValueError("days должен быть целым числом") from exc
        if not 1 <= days <= maximum:
            raise ValueError(f"days должен быть в диапазоне 1..{maximum}")
        return days

    @staticmethod
    def _extract_task_id(payload: dict[str, Any]) -> str:
        generation = payload.get("report_generation")
        if not isinstance(generation, dict):
            return ""
        return str(generation.get("task_id", "") or "").strip()
