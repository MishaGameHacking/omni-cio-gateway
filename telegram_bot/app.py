from __future__ import annotations

from contextlib import asynccontextmanager
import os
from typing import Any, AsyncIterator

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request

from . import TELEGRAM_COMPANION_VERSION
from .clients import GatewayClient, TelegramClient, UpstreamError
from .commands import COMMANDS, CommandRouter, verify_webhook_secret
from .config import Settings


async def configure_telegram(app: FastAPI) -> None:
    settings: Settings = app.state.settings
    app.state.bootstrap = {
        "status": "disabled" if not settings.auto_configure else "not_configured",
        "webhook_configured": False,
        "commands_configured": False,
        "bot_verified": False,
        "error": None,
    }
    if not settings.auto_configure:
        return
    if not settings.ready:
        app.state.bootstrap["status"] = "missing_configuration"
        return

    telegram: TelegramClient = app.state.telegram
    try:
        await telegram.get_me()
        app.state.bootstrap["bot_verified"] = True
        await telegram.set_commands(COMMANDS)
        app.state.bootstrap["commands_configured"] = True
        await telegram.set_webhook(
            url=settings.webhook_url,
            secret_token=settings.webhook_secret_token,
        )
        app.state.bootstrap["webhook_configured"] = True
        app.state.bootstrap["status"] = "ok"
    except UpstreamError as exc:
        app.state.bootstrap["status"] = "error"
        app.state.bootstrap["error"] = {
            "component": exc.component,
            "message": str(exc),
            "status_code": exc.status_code,
        }


def create_app(
    settings: Settings | None = None,
    *,
    telegram_client: TelegramClient | None = None,
    gateway_client: GatewayClient | None = None,
) -> FastAPI:
    resolved = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        await configure_telegram(application)
        yield

    application = FastAPI(
        title="Omni-CIO Telegram Companion",
        version=TELEGRAM_COMPANION_VERSION,
        description=(
            "Read-only Telegram control center for Omni-CIO Gateway. "
            "It cannot create, submit, replace, or cancel orders."
        ),
        lifespan=lifespan,
    )
    application.state.settings = resolved
    application.state.telegram = telegram_client or TelegramClient(
        bot_token=resolved.telegram_bot_token,
        timeout_seconds=resolved.request_timeout_seconds,
    )
    application.state.gateway = gateway_client or GatewayClient(
        base_url=resolved.omni_gateway_url,
        api_key=resolved.omni_gateway_api_key,
        timeout_seconds=resolved.request_timeout_seconds,
    )
    application.state.router = CommandRouter(
        settings=resolved,
        telegram=application.state.telegram,
        gateway=application.state.gateway,
    )
    application.state.bootstrap = {
        "status": "starting",
        "webhook_configured": False,
        "commands_configured": False,
        "bot_verified": False,
        "error": None,
    }

    @application.get("/health", operation_id="telegramCompanionHealth")
    async def health() -> dict[str, Any]:
        bootstrap = application.state.bootstrap
        ready = resolved.ready and bootstrap.get("status") in {"ok", "disabled"}
        return {
            "status": "ok" if ready else "degraded",
            "version": TELEGRAM_COMPANION_VERSION,
            "service": "telegram_companion",
            "configured": resolved.ready,
            "missing_configuration": list(resolved.missing_required),
            "bootstrap": bootstrap,
            "allowed_users_count": len(resolved.telegram_allowed_user_ids),
            "gateway_url_configured": bool(resolved.omni_gateway_url),
            "webhook_url_configured": bool(resolved.webhook_url),
            "reliability": {
                "gateway_retry_attempts": resolved.gateway_retry_attempts,
                "gateway_retry_delay_seconds": resolved.gateway_retry_delay_seconds,
                "friendly_output": True,
                "safe_message_splitting": True,
            },
            "build": {
                "commit_sha": os.getenv("RENDER_GIT_COMMIT", "local"),
                "entrypoint": "telegram_bot.app:app",
                "deployment_platform": "render" if os.getenv("RENDER") else "local",
            },
            "read_only": True,
            "trading_methods": False,
        }

    @application.post("/telegram/webhook", include_in_schema=False)
    async def telegram_webhook(
        request: Request,
        background_tasks: BackgroundTasks,
        x_telegram_bot_api_secret_token: str | None = Header(default=None),
    ) -> dict[str, bool]:
        if not verify_webhook_secret(
            x_telegram_bot_api_secret_token,
            resolved.webhook_secret_token,
        ):
            raise HTTPException(status_code=403, detail="Invalid webhook secret")
        try:
            update = await request.json()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON") from exc
        if not isinstance(update, dict):
            raise HTTPException(status_code=400, detail="Update must be an object")
        background_tasks.add_task(application.state.router.handle_update, update)
        return {"ok": True}

    return application


app = create_app()
