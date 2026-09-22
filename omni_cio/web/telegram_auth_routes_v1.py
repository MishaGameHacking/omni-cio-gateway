from __future__ import annotations

from fastapi import FastAPI, Request
from starlette.responses import Response

from omni_cio.web.identity_v1 import IdentityProviderV1
from omni_cio.web.provider_auth_routes_v1 import (
    ProviderAuthRouteServicesV1,
    _complete_provider_callback,
    _start_provider_auth,
)


TELEGRAM_START_PATH = "/api/v10/web/auth/telegram/start"
TELEGRAM_CALLBACK_PATH = "/api/v10/web/auth/telegram/callback"


def install_telegram_auth_routes_v1(
    app: FastAPI,
    *,
    services: ProviderAuthRouteServicesV1,
) -> None:
    """Install only the current Telegram human-login surface."""

    @app.post(TELEGRAM_START_PATH, include_in_schema=False)
    def telegram_start() -> Response:
        return _start_provider_auth(IdentityProviderV1.TELEGRAM, services)

    @app.get(TELEGRAM_CALLBACK_PATH, include_in_schema=False)
    def telegram_callback(request: Request) -> Response:
        return _complete_provider_callback(
            IdentityProviderV1.TELEGRAM,
            request,
            services,
        )
