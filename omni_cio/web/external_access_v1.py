from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import ipaddress
import re
import secrets
from threading import RLock
import time
from typing import Any, Protocol
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from omni_cio.contracts.v1.domain import OWNER_TENANT_ID, OWNER_USER_ID
from omni_cio.web.api_v1 import SESSION_COOKIE
from omni_cio.web.session_v1 import SessionPolicyV1, SessionScopeV1


REMOTE_SESSION_COOKIE = "__Host-omni_v10_session"
CSRF_COOKIE = "__Host-omni_v10_csrf"
CSRF_HEADER = "X-Omni-CSRF"
TAILSCALE_LOGIN_HEADER = "Tailscale-User-Login"
REMOTE_SESSION_POLICY = SessionPolicyV1(
    idle_lifetime=timedelta(hours=2),
    absolute_lifetime=timedelta(hours=24),
)
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost"})
_TAILNET_HOST_PATTERN = re.compile(
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*\.ts\.net"
)
_REMOTE_VERIFIED_STATE = "wp22a_private_remote_verified"
_REMOTE_STATUS_PATH = "/api/v10/web/private-tailnet-login/status"
_SESSION_TERMINATION_PATHS = frozenset(
    {
        "/api/v10/web/session/logout",
        "/api/v10/web/session/revoke-all",
    }
)
_CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "base-uri 'none'; "
    "object-src 'none'; "
    "frame-ancestors 'none'; "
    "form-action 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'"
)


class SessionRegistryLike(Protocol):
    def create(
        self,
        *,
        user_id: str,
        tenant_id: str,
        now: datetime,
    ) -> tuple[str, SessionScopeV1]: ...

    def revoke(self, token: str | None, *, now: datetime) -> bool: ...


@dataclass(frozen=True, slots=True)
class ExternalAccessPolicyV1:
    canonical_host: str
    owner_login_sha256: str
    login_attempts: int = 5
    login_window_seconds: int = 60
    mutation_attempts: int = 120
    mutation_window_seconds: int = 60

    def __post_init__(self) -> None:
        host = self.canonical_host.strip().lower().rstrip(".")
        digest = self.owner_login_sha256.strip().lower()
        if len(host) > 253 or _TAILNET_HOST_PATTERN.fullmatch(host) is None:
            raise ValueError("WP22A_CANONICAL_HOST_INVALID")
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise ValueError("WP22A_OWNER_LOGIN_FINGERPRINT_INVALID")
        if (
            min(
                self.login_attempts,
                self.login_window_seconds,
                self.mutation_attempts,
                self.mutation_window_seconds,
            )
            <= 0
        ):
            raise ValueError("WP22A_RATE_LIMIT_INVALID")
        object.__setattr__(self, "canonical_host", host)
        object.__setattr__(self, "owner_login_sha256", digest)

    @property
    def canonical_origin(self) -> str:
        return f"https://{self.canonical_host}"


class FixedWindowLimiterV1:
    """Small process-local limiter for the Personal-node Web security boundary."""

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = RLock()

    def admit(
        self,
        key: str,
        *,
        limit: int,
        window_seconds: int,
        now_monotonic: float | None = None,
    ) -> bool:
        now = time.monotonic() if now_monotonic is None else float(now_monotonic)
        cutoff = now - float(window_seconds)
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                return False
            events.append(now)
            return True


def _normalized_login(value: str) -> str:
    return value.strip().casefold()


def _login_fingerprint(value: str) -> str:
    return hashlib.sha256(_normalized_login(value).encode("utf-8")).hexdigest()


def _is_loopback(request: Request) -> bool:
    client = request.client
    if client is None:
        return False
    try:
        return ipaddress.ip_address(client.host).is_loopback
    except ValueError:
        return False


def _local_host_matches(value: str) -> bool:
    candidate = value.strip().lower().rstrip(".")
    if candidate.endswith(":"):
        return False
    try:
        parsed = urlsplit(f"//{candidate}")
        _ = parsed.port
    except ValueError:
        return False
    return (
        parsed.username is None
        and parsed.password is None
        and parsed.hostname in _LOCAL_HOSTS
        and parsed.path == ""
        and not parsed.query
        and not parsed.fragment
    )


def _remote_host_matches(value: str, canonical_host: str) -> bool:
    candidate = value.strip().lower()
    return candidate in {
        canonical_host,
        f"{canonical_host}.",
        f"{canonical_host}:443",
        f"{canonical_host}.:443",
    }


def _origin_host(value: str) -> str | None:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        return None
    if port not in {None, 443}:
        return None
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        return None
    return parsed.hostname.lower().rstrip(".")


def _replace_scope_header(request: Request, target: bytes, value: bytes) -> None:
    headers: list[tuple[bytes, bytes]] = []
    replaced = False
    for name, current in request.scope.get("headers", []):
        if name.lower() == target:
            if not replaced:
                headers.append((target, value))
                replaced = True
        else:
            headers.append((name, current))
    if not replaced:
        headers.append((target, value))
    request.scope["headers"] = headers


def _rewrite_host_to_loopback(request: Request) -> None:
    _replace_scope_header(request, b"host", b"127.0.0.1")


def _rewrite_remote_session_for_inner_app(request: Request) -> None:
    token = request.cookies.get(REMOTE_SESSION_COOKIE)
    raw_cookie = request.headers.get("cookie", "")
    pairs: list[str] = []
    for item in raw_cookie.split(";"):
        candidate = item.strip()
        if not candidate:
            continue
        name = candidate.split("=", 1)[0].strip()
        if name == SESSION_COOKIE:
            continue
        pairs.append(candidate)
    if token:
        pairs.append(f"{SESSION_COOKIE}={token}")
    _replace_scope_header(request, b"cookie", "; ".join(pairs).encode("latin-1"))


def _remote_request_verified(request: Request) -> bool:
    return bool(getattr(request.state, _REMOTE_VERIFIED_STATE, False))


def _harden_remote_response(response: Response, *, path: str) -> Response:
    response.headers["Strict-Transport-Security"] = "max-age=31536000"
    response.headers["Content-Security-Policy"] = _CONTENT_SECURITY_POLICY
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Cache-Control"] = "no-store"
    if path in _SESSION_TERMINATION_PATHS:
        response.delete_cookie(
            REMOTE_SESSION_COOKIE,
            path="/",
            secure=True,
            httponly=True,
            samesite="strict",
        )
        response.delete_cookie(
            CSRF_COOKIE,
            path="/",
            secure=True,
            httponly=False,
            samesite="strict",
        )
    return response


def _remote_error(detail: str, status_code: int, *, path: str) -> Response:
    return _harden_remote_response(
        JSONResponse({"detail": detail}, status_code=status_code),
        path=path,
    )


class ExternalAccessSecurityMiddlewareV1(BaseHTTPMiddleware):
    def __init__(
        self,
        app: Any,
        *,
        policy: ExternalAccessPolicyV1,
        limiter: FixedWindowLimiterV1,
    ) -> None:
        super().__init__(app)
        self._policy = policy
        self._limiter = limiter

    async def dispatch(
        self, request: Request, call_next: Callable[..., Any]
    ) -> Response:
        raw_host = request.headers.get("host", "")
        remote_request = _remote_host_matches(raw_host, self._policy.canonical_host)
        if not remote_request:
            if not _local_host_matches(raw_host):
                return JSONResponse({"detail": "INVALID_HOST"}, status_code=400)
            if request.method == "GET" and request.url.path == _REMOTE_STATUS_PATH:
                return JSONResponse({"enabled": False})
            return await call_next(request)

        if not _is_loopback(request):
            return _remote_error(
                "UNTRUSTED_PROXY_PATH",
                403,
                path=request.url.path,
            )

        is_status = request.method == "GET" and request.url.path == _REMOTE_STATUS_PATH
        identity = request.headers.get(TAILSCALE_LOGIN_HEADER, "")
        fingerprint = _login_fingerprint(identity)
        if not is_status and not secrets.compare_digest(
            fingerprint, self._policy.owner_login_sha256
        ):
            return _remote_error(
                "OWNER_IDENTITY_REQUIRED",
                403,
                path=request.url.path,
            )

        if request.method not in _SAFE_METHODS:
            origin = request.headers.get("origin", "")
            if _origin_host(origin) != self._policy.canonical_host:
                return _remote_error("ORIGIN_REQUIRED", 403, path=request.url.path)

            is_login = request.url.path == "/api/v10/web/private-tailnet-login"
            if not is_login:
                csrf_cookie = request.cookies.get(CSRF_COOKIE, "")
                csrf_header = request.headers.get(CSRF_HEADER, "")
                if (
                    not csrf_cookie
                    or not csrf_header
                    or not secrets.compare_digest(csrf_cookie, csrf_header)
                ):
                    return _remote_error("CSRF_REJECTED", 403, path=request.url.path)
                key = "mutation:" + fingerprint
                if not self._limiter.admit(
                    key,
                    limit=self._policy.mutation_attempts,
                    window_seconds=self._policy.mutation_window_seconds,
                ):
                    return _remote_error("RATE_LIMITED", 429, path=request.url.path)

        if is_status:
            return _harden_remote_response(
                JSONResponse({"enabled": True}),
                path=request.url.path,
            )

        setattr(request.state, _REMOTE_VERIFIED_STATE, True)
        _rewrite_remote_session_for_inner_app(request)
        _rewrite_host_to_loopback(request)
        response = await call_next(request)
        return _harden_remote_response(response, path=request.url.path)


def install_private_remote_access_v1(
    app: FastAPI,
    *,
    sessions: SessionRegistryLike,
    policy: ExternalAccessPolicyV1,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> None:
    limiter = FixedWindowLimiterV1()
    app.add_middleware(
        ExternalAccessSecurityMiddlewareV1,
        policy=policy,
        limiter=limiter,
    )

    @app.post("/api/v10/web/private-tailnet-login")
    def private_tailnet_login(request: Request, response: Response) -> dict[str, bool]:
        if not _remote_request_verified(request):
            raise HTTPException(status_code=404, detail="NOT_FOUND")
        login = request.headers.get(TAILSCALE_LOGIN_HEADER, "")
        fingerprint = _login_fingerprint(login)
        if not limiter.admit(
            "login:" + fingerprint,
            limit=policy.login_attempts,
            window_seconds=policy.login_window_seconds,
        ):
            raise HTTPException(status_code=429, detail="RATE_LIMITED")
        if not secrets.compare_digest(fingerprint, policy.owner_login_sha256):
            raise HTTPException(status_code=403, detail="OWNER_IDENTITY_REQUIRED")

        issued = now()
        if issued.tzinfo is None or issued.utcoffset() is None:
            raise RuntimeError("WP22A_CLOCK_NOT_UTC_AWARE")
        issued = issued.astimezone(timezone.utc)
        sessions.revoke(request.cookies.get(REMOTE_SESSION_COOKIE), now=issued)
        token, scope = sessions.create(
            user_id=OWNER_USER_ID,
            tenant_id=OWNER_TENANT_ID,
            now=issued,
        )
        csrf = secrets.token_urlsafe(32)
        max_age = max(1, int((scope.expires_at - issued).total_seconds()))
        response.set_cookie(
            REMOTE_SESSION_COOKIE,
            token,
            httponly=True,
            secure=True,
            samesite="strict",
            path="/",
            max_age=max_age,
        )
        response.set_cookie(
            CSRF_COOKIE,
            csrf,
            httponly=False,
            secure=True,
            samesite="strict",
            path="/",
            max_age=max_age,
        )
        return {"ok": True}
