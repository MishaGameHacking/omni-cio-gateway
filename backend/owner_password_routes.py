"""Non-identifying password entrypoints for the bound owner installation."""
from __future__ import annotations

from contextlib import asynccontextmanager
import json
import os

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

try:
    from .owner_access import bind_owner
    from .owner_password import OwnerAuthError, OwnerPasswordStore, initialize
except ImportError:
    from owner_access import bind_owner
    from owner_password import OwnerAuthError, OwnerPasswordStore, initialize

NO_STORE = "no-store, private"
MAX_BODY_BYTES = 2048
LEGACY_EXACT_PATHS = {"/auth/session", "/api/auth/social/telegram/callback"}


def _error(error: OwnerAuthError) -> JSONResponse:
    headers = {"Cache-Control": NO_STORE, "X-Content-Type-Options": "nosniff"}
    if error.retry_after is not None:
        headers["Retry-After"] = str(error.retry_after)
    return JSONResponse({"detail": error.code}, status_code=error.status, headers=headers)


async def _payload(request: Request, allowed: set[str]) -> dict:
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_BODY_BYTES:
            raise OwnerAuthError("owner_auth_payload_invalid", 422)
        body.extend(chunk)
    try:
        data = json.loads(body)
    except (ValueError, UnicodeError) as exc:
        raise OwnerAuthError("owner_auth_payload_invalid", 422) from exc
    if not isinstance(data, dict) or not set(data).issubset(allowed):
        raise OwnerAuthError("owner_auth_payload_invalid", 422)
    if "device_name" in data and data["device_name"] is not None and not isinstance(data["device_name"], str):
        raise OwnerAuthError("invalid_device_name", 422)
    # Do not use a validation response that echoes supplied passwords.
    for key in allowed - {"device_name"}:
        if not isinstance(data.get(key), str):
            raise OwnerAuthError("owner_auth_payload_invalid", 422)
    return data


def install(app: FastAPI, legacy, identity) -> None:
    if getattr(app.state, "owner_password_installed", False):
        return
    store = OwnerPasswordStore(legacy.connect, session_ttl=legacy.SESSION_TTL,
                               bootstrap_secret=lambda: os.getenv("ANALYST_OWNER_BOOTSTRAP_SECRET", ""))
    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(instance):
        async with original_lifespan(instance) as state:
            initialize(legacy.connect)
            bind_owner(legacy.connect, identity)
            yield state

    @app.middleware("http")
    async def auth_boundary(request: Request, call_next):
        path = request.url.path
        owner_route = path.startswith("/auth/owner/")
        legacy_route = path.startswith("/auth/telegram/") or path in LEGACY_EXACT_PATHS
        if getattr(app.state, "single_owner_ready", False):
            if legacy_route and (await run_in_threadpool(store.configured)
                                 or not legacy.TELEGRAM_CLIENT_ID or not legacy.TELEGRAM_CLIENT_SECRET):
                return _error(OwnerAuthError("owner_password_login_required", 401))
            if owner_route and request.method != "GET":
                origin = request.headers.get("Origin")
                if origin is not None and origin != legacy.BACKEND_PUBLIC_URL:
                    return _error(OwnerAuthError("owner_credentials_invalid", 401))
        response = await call_next(request)
        if owner_route:
            response.headers["Cache-Control"] = NO_STORE
            response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    router = APIRouter(prefix="/auth/owner", tags=["Owner password"])

    @router.get("/status")
    async def status():
        return await run_in_threadpool(store.status)

    @router.post("/setup")
    async def setup(request: Request):
        try:
            payload = await _payload(request, {"password", "device_name"})
            return await run_in_threadpool(store.setup, **payload,
                                           authorization=request.headers.get("Authorization"),
                                           bootstrap=request.headers.get("X-Owner-Bootstrap"))
        except OwnerAuthError as error:
            return _error(error)

    @router.post("/login")
    async def login(request: Request):
        try:
            payload = await _payload(request, {"password", "device_name"})
            return await run_in_threadpool(store.login, **payload)
        except OwnerAuthError as error:
            return _error(error)

    @router.post("/password")
    async def change(request: Request):
        try:
            payload = await _payload(request, {"current_password", "new_password", "device_name"})
            return await run_in_threadpool(store.change, **payload,
                                           authorization=request.headers.get("Authorization"))
        except OwnerAuthError as error:
            return _error(error)

    app.router.lifespan_context = lifespan
    app.include_router(router)
    app.state.owner_password_installed = True
