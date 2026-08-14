from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from email.header import decode_header
import hashlib
import hmac
from http.cookies import SimpleCookie
import ipaddress
import re
from threading import RLock
import time
from typing import Final, Protocol

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from omni_cio.contracts.v1.domain import OWNER_TENANT_ID, OWNER_USER_ID
from omni_cio.web.session_v1 import SessionScopeV1


CSRF_HEADER_NAME: Final[str] = "x-omni-csrf"
TAILSCALE_LOGIN_HEADER: Final[str] = "tailscale-user-login"
_TELEGRAM_INIT_DATA_HEADER: Final[str] = "x-telegram-init-data"
_SAFE_METHODS: Final[frozenset[str]] = frozenset({"GET", "HEAD", "OPTIONS"})
_LOGIN_PATH: Final[str] = "/api/v10/web/private-remote-login"
_HOST_RE = re.compile(r"^[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?\.ts\.net$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_CSRF_DOMAIN = b"omni-cio-v10-csrf-v1\x00"
_REMOTE_RESPONSE_HEADERS: Final[tuple[tuple[bytes, bytes], ...]] = (
    (b"cache-control", b"no-store"),
    (b"strict-transport-security", b"max-age=31536000"),
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
)


class RemoteSessionRegistryLike(Protocol):
    def create(
        self,
        *,
        user_id: str,
        tenant_id: str,
        now: datetime,
    ) -> tuple[str, SessionScopeV1]: ...

    def resolve(self, token: str | None, *, now: datetime) -> SessionScopeV1 | None: ...

    def revoke(self, token: str | None, *, now: datetime) -> bool: ...


def _decode_rfc2047(value: str) -> str:
    result: list[str] = []
    try:
        for item, charset in decode_header(value):
            if isinstance(item, bytes):
                result.append(item.decode(charset or "ascii", errors="strict"))
            else:
                result.append(item)
    except (LookupError, UnicodeError) as exc:
        raise ValueError("TAILSCALE_OWNER_LOGIN_INVALID") from exc
    return "".join(result)


def normalize_tailscale_login(value: str) -> str:
    normalized = _decode_rfc2047(value).strip()
    if not normalized or len(normalized) > 320 or "\x00" in normalized:
        raise ValueError("TAILSCALE_OWNER_LOGIN_INVALID")
    return normalized


def tailscale_login_sha256(value: str) -> str:
    return hashlib.sha256(normalize_tailscale_login(value).encode("utf-8")).hexdigest()


def csrf_token_for_session(session_token: str) -> str:
    if not session_token:
        raise ValueError("SESSION_TOKEN_REQUIRED")
    return hashlib.sha256(_CSRF_DOMAIN + session_token.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class PrivateRemoteSecurityPolicyV1:
    expected_host: str
    owner_login_sha256: str
    login_attempts_per_minute: int = 6
    mutations_per_minute: int = 60

    def __post_init__(self) -> None:
        host = self.expected_host.strip().lower().rstrip(".")
        owner = self.owner_login_sha256.strip().lower()
        if (
            _HOST_RE.fullmatch(host) is None
            or ".." in host
            or host.startswith(".")
            or host.endswith(".")
        ):
            raise ValueError("WP22A_TAILSCALE_HOST_INVALID")
        if _SHA256_RE.fullmatch(owner) is None:
            raise ValueError("WP22A_OWNER_LOGIN_FINGERPRINT_INVALID")
        if not 1 <= self.login_attempts_per_minute <= 60:
            raise ValueError("WP22A_LOGIN_RATE_LIMIT_INVALID")
        if not 1 <= self.mutations_per_minute <= 600:
            raise ValueError("WP22A_MUTATION_RATE_LIMIT_INVALID")
        object.__setattr__(self, "expected_host", host)
        object.__setattr__(self, "owner_login_sha256", owner)

    @property
    def expected_origin(self) -> str:
        return f"https://{self.expected_host}"


class _FixedWindowLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = RLock()

    def admit(self, key: str, *, maximum: int, now: float) -> bool:
        cutoff = now - 60.0
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= maximum:
                return False
            events.append(now)
            return True


def _headers(scope: Scope) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_name, raw_value in scope.get("headers", []):
        name = raw_name.decode("latin-1").lower()
        value = raw_value.decode("latin-1")
        if name not in result:
            result[name] = value
    return result


def _host_header_allowed(value: str, expected_host: str) -> bool:
    raw = value.strip().lower()
    return hmac.compare_digest(raw, expected_host) or hmac.compare_digest(
        raw, f"{expected_host}:443"
    )


def _cookie_value(cookie_header: str, name: str) -> str | None:
    cookie = SimpleCookie()
    try:
        cookie.load(cookie_header)
    except Exception:
        return None
    morsel = cookie.get(name)
    return morsel.value if morsel is not None else None


def _is_loopback_host(value: str) -> bool:
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


def _is_loopback_request(request: Request) -> bool:
    client = request.client
    return client is not None and _is_loopback_host(client.host)


def _scope_client_is_loopback(scope: Scope) -> bool:
    client = scope.get("client")
    if client is None:
        return False
    return _is_loopback_host(str(client[0]))


def _utc_now(now: Callable[[], datetime]) -> datetime:
    value = now()
    if value.tzinfo is None or value.utcoffset() is None:
        raise RuntimeError("WP22A_REMOTE_CLOCK_NOT_UTC_AWARE")
    return value.astimezone(timezone.utc)


def install_private_remote_session_routes(
    app: FastAPI,
    *,
    sessions: RemoteSessionRegistryLike,
    session_cookie_name: str,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> None:
    """Install Personal-owner private acceptance session bootstrap routes.

    Tailscale is deliberately not registered as an ordinary product identity
    provider. The enclosing WP22A middleware proves the outer private-network
    OWNER identity before these routes are reachable; this installer only
    creates a revocable Omni-CIO server-side browser session.
    """

    @app.get("/api/v10/web/private-remote-login/status")
    def private_remote_login_status(request: Request) -> dict[str, bool]:
        return {"enabled": _is_loopback_request(request)}

    @app.post("/api/v10/web/private-remote-login")
    def private_remote_login(request: Request, response: Response) -> dict[str, bool]:
        if not _is_loopback_request(request):
            raise HTTPException(status_code=404, detail="NOT_FOUND")
        current = _utc_now(now)
        sessions.revoke(request.cookies.get(session_cookie_name), now=current)
        token, scope = sessions.create(
            user_id=OWNER_USER_ID,
            tenant_id=OWNER_TENANT_ID,
            now=current,
        )
        response.set_cookie(
            session_cookie_name,
            token,
            httponly=True,
            secure=True,
            samesite="strict",
            path="/",
            max_age=max(1, int((scope.expires_at - current).total_seconds())),
        )
        response.headers["Cache-Control"] = "no-store"
        return {"ok": True}

    @app.get("/api/v10/web/session/csrf")
    def session_csrf(request: Request) -> JSONResponse:
        token = request.cookies.get(session_cookie_name)
        current = _utc_now(now)
        if token is None or sessions.resolve(token, now=current) is None:
            raise HTTPException(
                status_code=401,
                detail="AUTHENTICATION_REQUIRED",
            )
        return JSONResponse(
            {"csrf_token": csrf_token_for_session(token)},
            headers={"Cache-Control": "no-store"},
        )


class PrivateRemoteSecurityMiddlewareV1:
    """Fail-closed WP22A boundary for Tailscale Serve private remote access.

    The dedicated backend remains loopback-only. Tailscale Serve terminates TLS,
    strips spoofed Tailscale identity headers, and adds the authenticated tailnet
    user identity before forwarding to this process. This middleware adds exact
    Host/origin/OWNER checks, live server-session validation, session-bound CSRF,
    and bounded mutation/login rates.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        policy: PrivateRemoteSecurityPolicyV1,
        session_cookie_name: str,
        sessions: RemoteSessionRegistryLike,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._app = app
        self._policy = policy
        self._session_cookie_name = session_cookie_name
        self._sessions = sessions
        self._now = now
        self._limiter = _FixedWindowLimiter()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        if not _scope_client_is_loopback(scope):
            await self._reject(send, 403, "BACKEND_PEER_NOT_LOOPBACK")
            return

        headers = _headers(scope)
        if not _host_header_allowed(
            headers.get("host", ""), self._policy.expected_host
        ):
            await self._reject(send, 400, "HOST_NOT_ALLOWED")
            return

        login = headers.get(TAILSCALE_LOGIN_HEADER, "")
        try:
            login_digest = tailscale_login_sha256(login)
        except ValueError:
            await self._reject(send, 403, "PRIVATE_REMOTE_OWNER_REQUIRED")
            return
        if not hmac.compare_digest(login_digest, self._policy.owner_login_sha256):
            await self._reject(send, 403, "PRIVATE_REMOTE_OWNER_REQUIRED")
            return

        query = scope.get("query_string", b"").decode("latin-1", errors="ignore")
        if _TELEGRAM_INIT_DATA_HEADER in headers or "tgwebappdata=" in query.lower():
            await self._reject(send, 403, "TELEGRAM_MINI_APP_AUTH_NOT_ACTIVE")
            return

        origin = headers.get("origin")
        if origin is not None and not hmac.compare_digest(
            origin, self._policy.expected_origin
        ):
            await self._reject(send, 403, "ORIGIN_NOT_ALLOWED")
            return

        method = str(scope.get("method", "GET")).upper()
        path = str(scope.get("path", ""))
        session_token: str | None = None
        session_scope: SessionScopeV1 | None = None
        if path != _LOGIN_PATH:
            session_token = _cookie_value(
                headers.get("cookie", ""), self._session_cookie_name
            )
            if session_token is not None:
                session_scope = self._sessions.resolve(
                    session_token,
                    now=_utc_now(self._now),
                )
                if session_scope is not None and (
                    session_scope.user_id != OWNER_USER_ID
                    or session_scope.tenant_id != OWNER_TENANT_ID
                ):
                    await self._reject(send, 403, "PRIVATE_REMOTE_OWNER_SESSION_REQUIRED")
                    return

        if method not in _SAFE_METHODS:
            if origin is None or not hmac.compare_digest(
                origin, self._policy.expected_origin
            ):
                await self._reject(send, 403, "ORIGIN_REQUIRED")
                return

            monotonic_now = time.monotonic()
            if path == _LOGIN_PATH:
                if not self._limiter.admit(
                    "owner-login",
                    maximum=self._policy.login_attempts_per_minute,
                    now=monotonic_now,
                ):
                    await self._reject(send, 429, "LOGIN_RATE_LIMITED")
                    return
            else:
                if session_token is None or session_scope is None:
                    await self._reject(send, 401, "AUTHENTICATION_REQUIRED")
                    return
                supplied_csrf = headers.get(CSRF_HEADER_NAME, "")
                expected_csrf = csrf_token_for_session(session_token)
                if not supplied_csrf or not hmac.compare_digest(
                    supplied_csrf, expected_csrf
                ):
                    await self._reject(send, 403, "CSRF_VALIDATION_FAILED")
                    return
                if not self._limiter.admit(
                    "owner-mutation",
                    maximum=self._policy.mutations_per_minute,
                    now=monotonic_now,
                ):
                    await self._reject(send, 429, "API_MUTATION_RATE_LIMITED")
                    return

        async def send_with_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                existing = {name.lower() for name, _ in message.get("headers", [])}
                response_headers = list(message.get("headers", []))
                for name, value in _REMOTE_RESPONSE_HEADERS:
                    if name not in existing:
                        response_headers.append((name, value))
                message = {**message, "headers": response_headers}
            await send(message)

        await self._app(scope, receive, send_with_security_headers)

    @staticmethod
    async def _reject(send: Send, status_code: int, detail: str) -> None:
        body = (f'{{"detail":"{detail}"}}').encode("utf-8")
        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("ascii")),
            *_REMOTE_RESPONSE_HEADERS,
        ]
        await send(
            {
                "type": "http.response.start",
                "status": status_code,
                "headers": headers,
            }
        )
        await send({"type": "http.response.body", "body": body})
