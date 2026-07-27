from __future__ import annotations

from dataclasses import replace
from typing import Any

from fastapi.testclient import TestClient

from telegram_bot.app import create_app
from telegram_bot.config import Settings


class FakeTelegram:
    def __init__(self) -> None:
        self.messages: list[tuple[int, str]] = []
        self.webhooks: list[tuple[str, str]] = []
        self.commands: list[list[dict[str, str]]] = []
        self.get_me_calls = 0

    async def send_message(self, chat_id: int, text: str) -> None:
        self.messages.append((chat_id, text))

    async def get_me(self) -> dict[str, Any]:
        self.get_me_calls += 1
        return {"ok": True, "result": {"username": "omni_test_bot"}}

    async def set_webhook(self, *, url: str, secret_token: str) -> None:
        self.webhooks.append((url, secret_token))

    async def set_commands(self, commands: list[dict[str, str]]) -> None:
        self.commands.append(commands)


class FakeGateway:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any] | None]] = []
        self.responses: list[dict[str, Any]] = []

    async def get(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.calls.append((path, params))
        if self.responses:
            return self.responses.pop(0)
        return {
            "status": "ok",
            "version": "3.9.1",
            "account": {"id": "123456789", "masked_id": "***6789"},
            "trading_methods": False,
        }


def settings(*, auto_configure: bool = False, allowed: frozenset[int] | None = None) -> Settings:
    return Settings(
        telegram_bot_token="telegram-test-token",
        telegram_webhook_secret="webhook_secret_123",
        telegram_allowed_user_ids=allowed if allowed is not None else frozenset({42}),
        omni_gateway_url="https://gateway.example",
        omni_gateway_api_key="gateway-test-key",
        public_base_url="https://telegram.example",
        auto_configure=auto_configure,
        min_request_interval_seconds=0,
    )


def update(text: str, *, user_id: int = 42, chat_type: str = "private", update_id: int = 1) -> dict[str, Any]:
    return {
        "update_id": update_id,
        "message": {
            "message_id": 100,
            "from": {"id": user_id, "is_bot": False},
            "chat": {"id": user_id, "type": chat_type},
            "text": text,
        },
    }


def post(client: TestClient, payload: dict[str, Any], *, secret: str = "webhook_secret_123"):
    return client.post(
        "/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": secret},
    )


def test_health_exposes_read_only_contract_without_secrets() -> None:
    telegram = FakeTelegram()
    gateway = FakeGateway()
    app = create_app(settings(), telegram_client=telegram, gateway_client=gateway)
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["version"] == "4.0.0"
    assert payload["build"]["entrypoint"] == "telegram_bot.app:app"
    assert payload["read_only"] is True
    assert payload["trading_methods"] is False
    rendered = response.text
    assert "telegram-test-token" not in rendered
    assert "gateway-test-key" not in rendered
    assert "webhook_secret_123" not in rendered


def test_startup_auto_configures_commands_and_secret_webhook() -> None:
    telegram = FakeTelegram()
    app = create_app(settings(auto_configure=True), telegram_client=telegram, gateway_client=FakeGateway())
    with TestClient(app) as client:
        health = client.get("/health").json()
    assert telegram.get_me_calls == 1
    assert telegram.webhooks == [
        ("https://telegram.example/telegram/webhook", "webhook_secret_123")
    ]
    assert telegram.commands and any(item["command"] == "portfolio" for item in telegram.commands[0])
    assert health["bootstrap"]["status"] == "ok"


def test_invalid_render_generated_secret_is_normalized_for_telegram() -> None:
    configured = replace(settings(), telegram_webhook_secret="base64+/=")
    assert configured.webhook_secret_token != "base64+/="
    assert len(configured.webhook_secret_token) == 64
    assert configured.webhook_secret_token.isalnum()


def test_webhook_rejects_wrong_secret() -> None:
    app = create_app(settings(), telegram_client=FakeTelegram(), gateway_client=FakeGateway())
    with TestClient(app) as client:
        response = post(client, update("/health"), secret="wrong")
    assert response.status_code == 403


def test_unauthorized_user_never_reaches_gateway() -> None:
    telegram = FakeTelegram()
    gateway = FakeGateway()
    app = create_app(settings(), telegram_client=telegram, gateway_client=gateway)
    with TestClient(app) as client:
        response = post(client, update("/portfolio", user_id=99))
    assert response.status_code == 200
    assert gateway.calls == []
    assert telegram.messages == [(99, "Доступ запрещён.")]


def test_health_command_calls_only_gateway_get_and_masks_account_id() -> None:
    telegram = FakeTelegram()
    gateway = FakeGateway()
    app = create_app(settings(), telegram_client=telegram, gateway_client=gateway)
    with TestClient(app) as client:
        response = post(client, update("/health"))
    assert response.status_code == 200
    assert gateway.calls == [("/health", None)]
    assert len(telegram.messages) == 1
    text = telegram.messages[0][1]
    assert '"trading_methods": false' in text
    assert "123456789" not in text
    assert "***6789" in text


def test_report_task_is_reused_by_report_status() -> None:
    telegram = FakeTelegram()
    gateway = FakeGateway()
    gateway.responses = [
        {
            "status": "pending",
            "version": "3.9.1",
            "report_generation": {"status": "pending", "task_id": "task-abc"},
            "complete": False,
            "trading_methods": False,
        },
        {
            "status": "ok",
            "version": "3.9.1",
            "report_generation": {"status": "ready", "task_id": "task-abc"},
            "complete": True,
            "trading_methods": False,
        },
    ]
    app = create_app(settings(), telegram_client=telegram, gateway_client=gateway)
    with TestClient(app) as client:
        first = post(client, update("/report", update_id=10))
        second = post(client, update("/report_status", update_id=11))
    assert first.status_code == 200 and second.status_code == 200
    assert gateway.calls == [
        (
            "/operations/broker-report-reconciliation",
            {"days": 31, "wait_seconds": 0},
        ),
        (
            "/operations/broker-report-reconciliation",
            {"days": 31, "task_id": "task-abc", "wait_seconds": 10},
        ),
    ]
    assert len(telegram.messages) == 2
    assert "task-abc" in telegram.messages[0][1]
    assert '"complete": true' in telegram.messages[1][1]


def test_duplicate_update_is_ignored() -> None:
    telegram = FakeTelegram()
    gateway = FakeGateway()
    app = create_app(settings(), telegram_client=telegram, gateway_client=gateway)
    payload = update("/portfolio", update_id=77)
    with TestClient(app) as client:
        post(client, payload)
        post(client, payload)
    assert gateway.calls == [("/snapshot", None)]
    assert len(telegram.messages) == 1
