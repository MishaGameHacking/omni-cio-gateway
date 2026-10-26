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

NO_STORE = "no-store, private"
MESSAGE = "Эта установка Analyst AI доступна только её владельцу."

# Only these static CSS bytes are admitted by the denial page CSP.
DENIAL_STYLE = """
  :root {
    color-scheme: dark;
    --bg: #050E1C;
    --surface: #0A1A2C;
    --text: #EDF5FF;
    --muted: #ACC3DC;
    --primary: #A99AFF;
    --on-primary: #1B0D45;
    --primary-container: #403199;
    --on-primary-container: #FFFFFF;
    --surface-container: #0D2136;
    --outline: #88A4C5;
    --outline-variant: #294763;
    --danger: #FF99B2;
    --disabled-ink: #99AEC7;
    --disabled-container: #152B41;
  }
  body { min-height:100vh; display:grid; place-items:center; margin:0;
         padding:20px; box-sizing:border-box; background:var(--bg); background-image:radial-gradient(ellipse at top,#122449,transparent 65%);
         color:var(--text); font:16px/1.5 system-ui,sans-serif; }
  main { text-align:center; max-width:440px; }
  a,a:visited { display:block; margin-top:22px; padding:14px 20px; border-radius:12px;
               background:var(--primary); color:var(--on-primary); font-weight:600; text-decoration:none; }
  a:hover,a:active { background:color-mix(in srgb,var(--on-primary) 8%,var(--primary)); }
  a:focus-visible { outline:3px solid var(--primary); outline-offset:3px; }
  small { color:var(--muted); }
  ::selection { color:var(--on-primary-container); background:var(--primary-container); }
"""
DENIAL_STYLE_SHA256 = '0gMolE7YQwIJQYH9/+4LXXlSIDTrivmA9Ic4Ld6+9Ao='


def _denial(request: Request):
    link = "analystai://auth?error=" + DENIED
    if request.url.path.endswith("/callback"):
        return HTMLResponse(
            '<!doctype html><html lang="ru"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width">'
            '<meta name="color-scheme" content="dark"><title>Analyst AI</title>'
            '<style>' + DENIAL_STYLE + '</style></head><body><main><p>' + MESSAGE + '</p><a href="' + link
            + '">Вернуться в Analyst AI</a></main></body></html>', status_code=403,
            headers={"Cache-Control": NO_STORE, "Referrer-Policy": "no-referrer",
                     "Content-Security-Policy": "default-src 'none'; style-src 'sha256-" + DENIAL_STYLE_SHA256
                     + "'; base-uri 'none'; frame-ancestors 'none'"},
        )
    payload = {"detail": DENIED, "message": MESSAGE}
    if request.url.path == "/auth/telegram/complete":
        payload["deep_link"] = link
    return JSONResponse(payload, status_code=403, headers={"Cache-Control": NO_STORE})


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
                                headers={"Cache-Control": NO_STORE})
        return await call_next(request)

    @app.exception_handler(sqlite3.IntegrityError)
    async def integrity_error(request: Request, error: sqlite3.IntegrityError):
        if str(error) == DENIED:
            return _denial(request)
        if original_integrity is not None:
            return await original_integrity(request, error)
        return JSONResponse({"detail": "database_integrity_error"}, status_code=500,
                            headers={"Cache-Control": NO_STORE})

    app.router.lifespan_context = owner_lifespan
    return app


def create_app() -> FastAPI:
    identity = OwnerIdentity.from_environment()
    try:
        from . import telegram_browser_app as browser
    except ImportError:
        import telegram_browser_app as browser
    return configure_app(browser.app, browser.legacy.connect, browser.legacy.init_db, identity)
