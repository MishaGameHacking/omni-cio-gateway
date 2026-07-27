from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import hmac
import json
import re
import time
from typing import Any

from .clients import GatewayClient, TelegramClient, UpstreamError
from .config import Settings


COMMANDS = [
    {"command": "help", "description": "Список безопасных команд"},
    {"command": "health", "description": "Проверить Telegram и Omni-CIO Gateway"},
    {"command": "connection", "description": "Проверить подключение к T-Invest"},
    {"command": "portfolio", "description": "Получить read-only снимок портфеля"},
    {"command": "cash", "description": "Проверить деньги и ликвидность"},
    {"command": "analytics", "description": "Получить аналитику портфеля"},
    {"command": "operations", "description": "Операции; пример: /operations 90"},
    {"command": "report", "description": "Запустить отчёт T-Invest за 31 день"},
    {"command": "report_status", "description": "Проверить готовность отчёта"},
]

HELP_TEXT = """Omni-CIO Telegram Companion v4.0.0

Доступные read-only команды:
/health — Telegram service и gateway
/connection — подключение к T-Invest
/portfolio — снимок портфеля
/cash — деньги и ликвидность
/analytics — структура портфеля
/operations [days] — аналитика операций, по умолчанию 90 дней
/report — запустить официальный отчёт за 31 день
/report_status [task_id] — проверить готовность отчёта
/help — эта справка

Бот не создаёт заявки и не совершает сделки.
trading_methods=false"""

_SECRET_KEY_RE = re.compile(r"token|secret|api[_-]?key|authorization", re.IGNORECASE)


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


def _mask_account(value: Any) -> Any:
    text = str(value or "")
    if text.startswith("***") or len(text) <= 4:
        return text
    return f"***{text[-4:]}"


def sanitize_payload(value: Any, path: tuple[str, ...] = ()) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            next_path = (*path, key_text.lower())
            if _SECRET_KEY_RE.search(key_text):
                result[key_text] = "[REDACTED]"
            elif key_text.lower() in {"account_id", "accountid"}:
                result[key_text] = _mask_account(item)
            elif key_text.lower() == "id" and "account" in path:
                result[key_text] = _mask_account(item)
            else:
                result[key_text] = sanitize_payload(item, next_path)
        return result
    if isinstance(value, list):
        return [sanitize_payload(item, path) for item in value]
    return value


def format_payload(title: str, payload: dict[str, Any], *, max_chars: int) -> str:
    safe = sanitize_payload(payload)
    rendered = json.dumps(safe, ensure_ascii=False, indent=2, sort_keys=False)
    prefix = f"{title}\n"
    warning = "\n\nОтвет сокращён. Полные данные доступны через Custom GPT или gateway."
    if len(prefix) + len(rendered) > max_chars:
        rendered = rendered[: max(0, max_chars - len(prefix) - len(warning))]
        rendered = rendered.rstrip() + warning
    return prefix + rendered


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
        try:
            response = await self._dispatch(user_id, command, args)
        except UpstreamError as exc:
            suffix = f" (HTTP {exc.status_code})" if exc.status_code else ""
            response = f"Ошибка {exc.component}{suffix}: {exc}"
        except ValueError as exc:
            response = f"Некорректные параметры: {exc}"
        except Exception:
            response = "Внутренняя ошибка Telegram Companion. Секретные данные не выведены."
        await self.telegram.send_message(chat_id, response)

    async def _dispatch(self, user_id: int, command: str, args: list[str]) -> str:
        if command in {"", "start", "help"}:
            return HELP_TEXT
        if command == "health":
            payload = await self.gateway.get("/health")
            return format_payload(
                "Omni-CIO Gateway",
                payload,
                max_chars=self.settings.max_response_chars,
            )
        if command == "connection":
            payload = await self.gateway.get("/connection")
            return format_payload("Подключение T-Invest", payload, max_chars=self.settings.max_response_chars)
        if command == "portfolio":
            payload = await self.gateway.get("/snapshot")
            return format_payload("Портфель", payload, max_chars=self.settings.max_response_chars)
        if command == "cash":
            payload = await self.gateway.get("/portfolio/cash-liquidity")
            return format_payload("Деньги и ликвидность", payload, max_chars=self.settings.max_response_chars)
        if command == "analytics":
            payload = await self.gateway.get("/portfolio/analytics")
            return format_payload("Аналитика портфеля", payload, max_chars=self.settings.max_response_chars)
        if command == "operations":
            days = self._parse_days(args, default=90, maximum=3650)
            payload = await self.gateway.get("/operations/analytics", params={"days": days})
            return format_payload("Операции", payload, max_chars=self.settings.max_response_chars)
        if command == "report":
            payload = await self.gateway.get(
                "/operations/broker-report-reconciliation",
                params={"days": 31, "wait_seconds": 0},
            )
            task_id = self._extract_task_id(payload)
            if task_id:
                self.report_tasks[user_id] = task_id
            return format_payload("Брокерский отчёт", payload, max_chars=self.settings.max_response_chars)
        if command == "report_status":
            task_id = args[0].strip() if args else self.report_tasks.get(user_id, "")
            if not task_id:
                return "Нет сохранённого task_id. Сначала выполните /report или передайте /report_status <task_id>."
            payload = await self.gateway.get(
                "/operations/broker-report-reconciliation",
                params={
                    "days": 31,
                    "task_id": task_id,
                    "wait_seconds": 10,
                },
            )
            if payload.get("status") != "pending":
                self.report_tasks.pop(user_id, None)
            return format_payload("Статус брокерского отчёта", payload, max_chars=self.settings.max_response_chars)
        return "Неизвестная команда. Используйте /help."

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
