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
    except (ValueError, RecursionError) as exc:
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


def _lifespan(original_lifespan, connect, identity):
    @asynccontextmanager
    async def lifespan(instance):
        async with original_lifespan(instance) as state:
            initialize(connect)
            bind_owner(connect, identity)
            yield state
    return lifespan


class OwnerAuthBoundary:
    def __init__(self, app, store, legacy):
        self.app, self.store, self.legacy = app, store, legacy

    async def _legacy_disabled(self, path: str) -> bool:
        if not (path.startswith("/auth/telegram/") or path in LEGACY_EXACT_PATHS):
            return False
        return (not self.legacy.TELEGRAM_CLIENT_ID or not self.legacy.TELEGRAM_CLIENT_SECRET
                or await run_in_threadpool(self.store.configured))

    def _origin_denied(self, request: Request, owner_route: bool) -> bool:
        if not owner_route or request.method == "GET":
            return False
        origin = request.headers.get("Origin")
        return origin is not None and origin != self.legacy.BACKEND_PUBLIC_URL

    async def __call__(self, request: Request, call_next):
        path = request.url.path
        owner_route = path.startswith("/auth/owner/")
        if getattr(self.app.state, "single_owner_ready", False):
            if await self._legacy_disabled(path):
                return _error(OwnerAuthError("owner_password_login_required", 401))
            if self._origin_denied(request, owner_route):
                return _error(OwnerAuthError("owner_credentials_invalid", 401))
        response = await call_next(request)
        if owner_route:
            response.headers["Cache-Control"] = NO_STORE
            response.headers["X-Content-Type-Options"] = "nosniff"
        return response



class OwnerAuthEndpoints:
    def __init__(self, store):
        self.store = store

    async def status(self):
        return await run_in_threadpool(self.store.status)

    async def _invoke(self, request: Request, operation, fields: set[str], **credentials):
        try:
            payload = await _payload(request, fields)
            return await run_in_threadpool(operation, **payload, **credentials)
        except OwnerAuthError as error:
            return _error(error)

    async def setup(self, request: Request):
        return await self._invoke(request, self.store.setup, {"password", "device_name"},
                                  authorization=request.headers.get("Authorization"),
                                  bootstrap=request.headers.get("X-Owner-Bootstrap"))

    async def login(self, request: Request):
        return await self._invoke(request, self.store.login, {"password", "device_name"},
                                  authorization=request.headers.get("Authorization"))

    async def change(self, request: Request):
        return await self._invoke(request, self.store.change, {"current_password", "new_password", "device_name"},
                                  authorization=request.headers.get("Authorization"))


def install(app: FastAPI, legacy, identity) -> None:
    if getattr(app.state, "owner_password_installed", False):
        return
    store = OwnerPasswordStore(legacy.connect, session_ttl=legacy.SESSION_TTL,
                               bootstrap_secret=lambda: os.getenv("ANALYST_OWNER_BOOTSTRAP_SECRET", ""))
    app.router.lifespan_context = _lifespan(app.router.lifespan_context, legacy.connect, identity)
    app.middleware("http")(OwnerAuthBoundary(app, store, legacy))
    endpoints = OwnerAuthEndpoints(store)
    router = APIRouter(prefix="/auth/owner", tags=["Owner password"])
    router.add_api_route("/status", endpoints.status, methods=["GET"])
    router.add_api_route("/setup", endpoints.setup, methods=["POST"])
    router.add_api_route("/login", endpoints.login, methods=["POST"])
    router.add_api_route("/password", endpoints.change, methods=["POST"])
    app.include_router(router)
    app.state.owner_password_installed = True
