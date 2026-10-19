"""Single-owner ASGI factory for the new, empty Timeweb installation.

Run: uvicorn owner_app:create_app --factory --workers 1
The shared legacy module remains an internal implementation, not the deployment
entry point. No owner, no startup. No imports of old user databases.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
import sqlite3
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

try:
    from .owner_access import DENIED, OwnerConfigurationError, OwnerIdentity, bind_owner
except ImportError:
    from owner_access import DENIED, OwnerConfigurationError, OwnerIdentity, bind_owner

MESSAGE = "Эта установка Analyst AI доступна только её владельцу."


def _denial(request: Request):
    link = "analystai://auth?error=" + DENIED
    if request.url.path.endswith("/callback"):
        return HTMLResponse(
            '<!doctype html><html lang="ru"><meta name="viewport" content="width=device-width">'
            '<title>Analyst AI</title><p>' + MESSAGE + '</p><a href="' + link
            + '">Вернуться в Analyst AI</a></html>', status_code=403,
            headers={"Cache-Control": "no-store, private", "Referrer-Policy": "no-referrer",
                     "Content-Security-Policy": "default-src 'none'; base-uri 'none'; frame-ancestors 'none'"},
        )
    payload = {"detail": DENIED, "message": MESSAGE}
    if request.url.path == "/auth/telegram/complete":
        payload["deep_link"] = link
    return JSONResponse(payload, status_code=403, headers={"Cache-Control": "no-store, private"})


def configure_app(app: FastAPI, connect: Callable, initialize: Callable,
                  identity: OwnerIdentity) -> FastAPI:
    """Wrap real startup, routes and errors without disabling auth or the queue."""
    configured = getattr(app.state, "single_owner_identity", None)
    if configured is not None:
        if configured != identity:
            raise OwnerConfigurationError("owner_app_already_bound")
        return app
    original_lifespan = app.router.lifespan_context
    original_integrity = app.exception_handlers.get(sqlite3.IntegrityError)
    app.state.single_owner_identity = identity
    app.state.single_owner_ready = False

    @asynccontextmanager
    async def owner_lifespan(instance):
        initialize()
        bind_owner(connect, identity)  # Before the original scheduler can start.
        try:
            async with original_lifespan(instance) as state:
                bind_owner(connect, identity)  # Cover tables added by its migrations.
                instance.state.single_owner_ready = True
                try:
                    yield state
                finally:
                    instance.state.single_owner_ready = False
        finally:
            instance.state.single_owner_ready = False

    @app.middleware("http")
    async def require_startup(request: Request, call_next):
        # Uvicorn --lifespan off must not accidentally bypass owner binding.
        if not app.state.single_owner_ready:
            return JSONResponse({"detail": "owner_installation_not_ready"}, status_code=503,
                                headers={"Cache-Control": "no-store, private"})
        return await call_next(request)

    @app.exception_handler(sqlite3.IntegrityError)
    async def integrity_error(request: Request, error: sqlite3.IntegrityError):
        if str(error) == DENIED:
            return _denial(request)
        if original_integrity is not None:
            return await original_integrity(request, error)
        return JSONResponse({"detail": "database_integrity_error"}, status_code=500,
                            headers={"Cache-Control": "no-store, private"})

    app.router.lifespan_context = owner_lifespan
    return app


def create_app() -> FastAPI:
    identity = OwnerIdentity.from_environment()
    try:
        from . import telegram_browser_app as browser
    except ImportError:
        import telegram_browser_app as browser
    return configure_app(browser.app, browser.legacy.connect, browser.legacy.init_db, identity)
