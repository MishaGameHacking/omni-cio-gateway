from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
import hashlib
import hmac
from http.cookies import SimpleCookie
import re
from threading import RLock
import time
from typing import Final

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


CSRF_HEADER_NAME: Final[str] = "x-omni-csrf"
TAILSCALE_LOGIN_HEADER: Final[str] = "tailscale-user-login"
_TELEGRAM_INIT_DATA_HEADER: Final[str] = "x-telegram-init-data"
_SAFE_METHODS: Final[frozenset[str]] = frozenset({"GET", "HEAD", "OPTIONS"})
_LOGIN_PATH: Final[str] = "/api/v10/web/private-remote-login"
_HOST_RE = re.compile(r"^[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?\.ts\.net$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_CSRF_DOMAIN = b"omni-cio-v10-csrf-v1\x00"


def normalize_tailscale_login(value: str) -> str:
    normalized = value.strip().casefold()
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
        if _HOST_RE.fullmatch(host) is None:
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
            if not events:
                self._events.pop(key, None)
            return True


def _headers(scope: Scope) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_name, raw_value in scope.get("headers", []):
        name = raw_name.decode("latin-1").lower()
        value = raw_value.decode("latin-1")
        if name not in result:
            result[name] = value
    return result


def _host_without_port(value: str) -> str:
    raw = value.strip().lower().rstrip(".")
    if raw.startswith("["):
        return raw
    return raw.split(":", 1)[0].rstrip(".")


def _cookie_value(cookie_header: str, name: str) -> str | None:
    cookie = SimpleCookie()
    try:
        cookie.load(cookie_header)
    except Exception:
        return None
    morsel = cookie.get(name)
    return morsel.value if morsel is not None else None


class PrivateRemoteSecurityMiddlewareV1:
    """Fail-closed WP22A boundary for Tailscale Serve private remote access.

    This middleware is intentionally only for the dedicated private-remote app
    factory. The backend remains bound to loopback and Tailscale Serve is the
    TLS/network identity boundary. Tailscale identity is an outer Personal-node
    acceptance factor; it does not become an ordinary Omni-CIO product identity
    provider and cannot enable public multi-user mode.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        policy: PrivateRemoteSecurityPolicyV1,
        session_cookie_name: str,
    ) -> None:
        self._app = app
        self._policy = policy
        self._session_cookie_name = session_cookie_name
        self._limiter = _FixedWindowLimiter()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        headers = _headers(scope)
        host = _host_without_port(headers.get("host", ""))
        if not hmac.compare_digest(host, self._policy.expected_host):
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
        if _TELEGRAM_INIT_DATA_HEADER in headers or "tgWebAppData=" in query:
            await self._reject(send, 403, "TELEGRAM_MINI_APP_AUTH_NOT_ACTIVE")
            return

        origin = headers.get("origin")
        if origin is not None and not hmac.compare_digest(
            origin.rstrip("/"), self._policy.expected_origin
        ):
            await self._reject(send, 403, "ORIGIN_NOT_ALLOWED")
            return

        method = str(scope.get("method", "GET")).upper()
        path = str(scope.get("path", ""))
        if method not in _SAFE_METHODS:
            if origin is None or not hmac.compare_digest(
                origin.rstrip("/"), self._policy.expected_origin
            ):
                await self._reject(send, 403, "ORIGIN_REQUIRED")
                return

            now = time.monotonic()
            if path == _LOGIN_PATH:
                if not self._limiter.admit(
                    "owner-login",
                    maximum=self._policy.login_attempts_per_minute,
                    now=now,
                ):
                    await self._reject(send, 429, "LOGIN_RATE_LIMITED")
                    return
            else:
                session_token = _cookie_value(
                    headers.get("cookie", ""), self._session_cookie_name
                )
                supplied_csrf = headers.get(CSRF_HEADER_NAME, "")
                if session_token is None:
                    await self._reject(send, 401, "AUTHENTICATION_REQUIRED")
                    return
                expected_csrf = csrf_token_for_session(session_token)
                if not supplied_csrf or not hmac.compare_digest(
                    supplied_csrf, expected_csrf
                ):
                    await self._reject(send, 403, "CSRF_VALIDATION_FAILED")
                    return
                if not self._limiter.admit(
                    "owner-mutation",
                    maximum=self._policy.mutations_per_minute,
                    now=now,
                ):
                    await self._reject(send, 429, "API_MUTATION_RATE_LIMITED")
                    return

        await self._app(scope, receive, send)

    @staticmethod
    async def _reject(send: Send, status_code: int, detail: str) -> None:
        response = JSONResponse(
            {"detail": detail},
            status_code=status_code,
            headers={"Cache-Control": "no-store"},
        )
        await response({"type": "http"}, _empty_receive, send)


async def _empty_receive() -> dict[str, object]:
    return {"type": "http.request", "body": b"", "more_body": False}
