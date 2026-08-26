from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
from typing import Any, Protocol
from urllib.parse import urlsplit

from fastapi import FastAPI, Request, Response
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from apps.api.app import (
    _SerializedWebConnection,
    _configure_long_lived_web_connection,
)
from apps.api.wp22a_phase5_auth import build_wp22a_phase5_provider_auth
from omni_cio.persistence.migration import connect_postgres
from omni_cio.web.browser_security_v1 import (
    BROWSER_CSRF_COOKIE,
    BROWSER_CSRF_HEADER,
    BROWSER_SESSION_COOKIE,
    BrowserCookiePolicyV1,
)
from omni_cio.web.persistence_v1 import PostgresWebSessionRegistryV1
from omni_cio.web.provider_auth_routes_v1 import (
    TELEGRAM_START_PATH,
    VK_ID_START_PATH,
    ProviderAuthRouteServicesV1,
    install_provider_auth_routes_v1,
)
from omni_cio.web.request_limits_v1 import (
    HostedRequestAbuseControlV1,
    is_session_token_candidate,
)
from omni_cio.web.session_v1 import SessionPolicyV1, SessionScopeV1


WEB_DIST = Path(__file__).resolve().parents[1] / "web" / "dist"
PREVIEW_STATUS_PATH = "/api/v10/web/preview-mode"
CSRF_COOKIE = BROWSER_CSRF_COOKIE
CSRF_HEADER = BROWSER_CSRF_HEADER
PREVIEW_TENANT_ID = "tenant:v1:synthetic_preview"
PREVIEW_USER_ID = "user:v1:synthetic_preview"
PREVIEW_SESSION_POLICY = SessionPolicyV1(
    idle_lifetime=timedelta(hours=2),
    absolute_lifetime=timedelta(hours=24),
)
_PROVIDER_START_PATHS = frozenset({TELEGRAM_START_PATH, VK_ID_START_PATH})
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_UNTRUSTED_FETCH_SITES = frozenset({"cross-site", "same-site"})
_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_HOST_PATTERN = re.compile(
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+"
)
_RENDER_HOST_SUFFIX = ".onrender.com"
_SESSION_SCOPE_STATE_ATTR = "_omni_v10_session_scope"
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

    def resolve(self, token: str | None, *, now: datetime) -> SessionScopeV1 | None: ...

    def revoke(self, token: str | None, *, now: datetime) -> bool: ...

    def revoke_all_for_user(self, user_id: str, *, now: datetime) -> int: ...


@dataclass(slots=True)
class HostedPreviewServicesV1:
    sessions: SessionRegistryLike
    database_probe: Callable[[], None]
    hostname: str
    release_sha: str
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)
    provider_auth: ProviderAuthRouteServicesV1 | None = None


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise RuntimeError("HOSTED_PREVIEW_CLOCK_NOT_UTC_AWARE")
    return value.astimezone(timezone.utc)


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name}_REQUIRED")
    return value


def _hostname(value: str) -> str:
    normalized = value.strip().lower().rstrip(".")
    if len(normalized) > 253 or _HOST_PATTERN.fullmatch(normalized) is None:
        raise RuntimeError("HOSTED_PREVIEW_HOST_INVALID")
    return normalized


def _release_sha(value: str) -> str:
    normalized = value.strip().lower()
    if _SHA_PATTERN.fullmatch(normalized) is None:
        raise RuntimeError("HOSTED_PREVIEW_RELEASE_SHA_INVALID")
    return normalized


def _origin_hostname(value: str) -> str | None:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme != "https"
        or parsed.username is not None
        or parsed.password is not None
        or not parsed.hostname
        or port not in {None, 443}
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        return None
    return parsed.hostname.lower().rstrip(".")


def _record_sha256(payload: dict[str, object]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _now_iso(services: HostedPreviewServicesV1) -> str:
    return _utc(services.now()).isoformat()


def _is_api_path(path: str) -> bool:
    return path.startswith("/api/") or path == "/healthz"


def _merge_vary(response: Response, *required: str) -> None:
    existing = response.headers.get("Vary", "")
    values = [value.strip() for value in existing.split(",") if value.strip()]
    seen = {value.lower() for value in values}
    for value in required:
        key = value.lower()
        if key not in seen:
            values.append(value)
            seen.add(key)
    response.headers["Vary"] = ", ".join(values)


def _harden_response(response: Response, *, api_path: bool) -> Response:
    response.headers["Strict-Transport-Security"] = "max-age=31536000"
    response.headers["Content-Security-Policy"] = _CONTENT_SECURITY_POLICY
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Cache-Control"] = "no-store" if api_path else "no-cache"
    _merge_vary(response, "Origin", "Sec-Fetch-Site")
    return response


def _safe_error(detail: str, status_code: int, *, api_path: bool = True) -> Response:
    return _harden_response(
        JSONResponse({"detail": detail}, status_code=status_code),
        api_path=api_path,
    )


def _rate_error(*, retry_after_seconds: int, api_path: bool = True) -> Response:
    response = JSONResponse(
        {"detail": "RATE_LIMITED"},
        status_code=429,
        headers={"Retry-After": str(retry_after_seconds)},
    )
    return _harden_response(response, api_path=api_path)


def _disabled_provider_auth(
    services: HostedPreviewServicesV1,
) -> ProviderAuthRouteServicesV1:
    return ProviderAuthRouteServicesV1(
        runtimes=(),
        authentication=None,
        cookies=BrowserCookiePolicyV1(csrf_binding_key=secrets.token_bytes(32)),
        now=services.now,
    )


def _request_session_scope(request: Request) -> SessionScopeV1 | None:
    scope = getattr(request.state, _SESSION_SCOPE_STATE_ATTR, None)
    return scope if isinstance(scope, SessionScopeV1) else None


class HostedPreviewSecurityMiddlewareV1(BaseHTTPMiddleware):
    def __init__(
        self,
        app: Any,
        *,
        hostname: str,
        cookies: BrowserCookiePolicyV1,
        sessions: SessionRegistryLike,
        now: Callable[[], datetime],
        trusted_edge_tls_terminated: bool = False,
        abuse: HostedRequestAbuseControlV1 | None = None,
    ) -> None:
        super().__init__(app)
        self._hostname = hostname
        self._cookies = cookies
        self._sessions = sessions
        self._now = now
        self._trusted_edge_tls_terminated = trusted_edge_tls_terminated
        self._abuse = abuse or HostedRequestAbuseControlV1()

    def _transport_error(self, request: Request, *, api_path: bool) -> Response | None:
        # Never treat a client-controlled forwarded header as TLS authority. On the
        # accepted Render Web Service the managed edge terminates public TLS and
        # forwards to a port that Render documents as not directly Internet-reachable;
        # that provider boundary is asserted by source composition instead.
        if (
            request.url.scheme.lower() != "https"
            and not self._trusted_edge_tls_terminated
        ):
            return _safe_error("HTTPS_REQUIRED", 403, api_path=api_path)
        return None

    def _resolve_session(self, request: Request) -> Response | None:
        session_token = request.cookies.get(BROWSER_SESSION_COOKIE)
        scope: SessionScopeV1 | None = None
        if is_session_token_candidate(session_token):
            try:
                scope = self._sessions.resolve(
                    session_token,
                    now=_utc(self._now()),
                )
            except Exception:
                return _safe_error("SESSION_LOOKUP_UNAVAILABLE", 503)
        setattr(request.state, _SESSION_SCOPE_STATE_ATTR, scope)
        verified_token = session_token if scope is not None else None
        if not self._abuse.admit_request_class(verified_session_token=verified_token):
            return _rate_error(
                retry_after_seconds=self._abuse.policy.retry_after_seconds,
                api_path=True,
            )
        return None

    def _admission_error(self, request: Request, *, api_path: bool) -> Response | None:
        if request.url.path == "/healthz":
            if self._abuse.admit_health():
                return None
            return _rate_error(
                retry_after_seconds=self._abuse.policy.retry_after_seconds,
                api_path=True,
            )
        if not api_path:
            return None
        if not self._abuse.admit_global():
            return _rate_error(
                retry_after_seconds=self._abuse.policy.retry_after_seconds,
                api_path=True,
            )
        return self._resolve_session(request)

    def _csrf_valid(self, request: Request) -> bool:
        session_token = request.cookies.get(BROWSER_SESSION_COOKIE, "")
        cookie = request.cookies.get(BROWSER_CSRF_COOKIE, "")
        header = request.headers.get(BROWSER_CSRF_HEADER, "")
        if not session_token or not cookie or not header:
            return False
        if not secrets.compare_digest(cookie, header):
            return False
        return self._cookies.csrf_matches(
            session_token=session_token,
            csrf_token=cookie,
        )

    def _mutation_error(self, request: Request, *, api_path: bool) -> Response | None:
        if request.method in _SAFE_METHODS:
            return None
        if _origin_hostname(request.headers.get("origin", "")) != self._hostname:
            return _safe_error("ORIGIN_REQUIRED", 403, api_path=api_path)
        fetch_site = request.headers.get("sec-fetch-site", "").strip().lower()
        if fetch_site in _UNTRUSTED_FETCH_SITES:
            return _safe_error("FETCH_METADATA_REJECTED", 403, api_path=api_path)
        if request.url.path in _PROVIDER_START_PATHS:
            return None
        if not self._csrf_valid(request):
            return _safe_error("CSRF_REJECTED", 403, api_path=api_path)
        return None

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[..., Any],
    ) -> Response:
        api_path = _is_api_path(request.url.path)
        error = self._transport_error(request, api_path=api_path)
        if error is None:
            error = self._admission_error(request, api_path=api_path)
        if error is None:
            error = self._mutation_error(request, api_path=api_path)
        if error is not None:
            return error
        response = await call_next(request)
        return _harden_response(response, api_path=api_path)


def _require_session(request: Request) -> SessionScopeV1 | Response:
    scope = _request_session_scope(request)
    if scope is None:
        return _safe_error("AUTHENTICATION_REQUIRED", 401)
    return scope


def _verify_synthetic_scope(connection: Any) -> None:
    """Verify provider-seeded Phase-4 fixture without using it as auth authority."""
    created = datetime(2026, 8, 21, tzinfo=timezone.utc)
    user_payload: dict[str, object] = {
        "schema_version": "1.0",
        "identity_version": 1,
        "user_id": PREVIEW_USER_ID,
        "tenant_id": PREVIEW_TENANT_ID,
        "role": "user",
        "created_at": created.isoformat(),
    }
    row = connection.execute(
        "SELECT tenant_id, schema_version, identity_version, role, record_sha256 "
        "FROM omni_cio_v10.users WHERE user_id = %s",
        (PREVIEW_USER_ID,),
    ).fetchone()
    expected = (
        PREVIEW_TENANT_ID,
        "1.0",
        1,
        "user",
        _record_sha256(user_payload),
    )
    if row != expected:
        raise RuntimeError("HOSTED_PREVIEW_SYNTHETIC_SCOPE_DRIFT")


def _probe_runtime_database(connection: Any) -> None:
    version = connection.execute("SHOW server_version_num").fetchone()
    if version is None or int(version[0]) // 10000 != 18:
        raise RuntimeError("HOSTED_PREVIEW_POSTGRES18_REQUIRED")

    role = connection.execute(
        "SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, "
        "rolreplication, rolbypassrls FROM pg_catalog.pg_roles "
        "WHERE rolname = current_user"
    ).fetchone()
    if role != (
        "omni_cio_hosted_api",
        True,
        False,
        False,
        False,
        False,
        False,
    ):
        raise RuntimeError("HOSTED_PREVIEW_RUNTIME_ROLE_DRIFT")

    memberships = connection.execute(
        "SELECT count(*) FROM pg_catalog.pg_auth_members m "
        "JOIN pg_catalog.pg_roles r ON r.oid = m.member "
        "WHERE r.rolname = current_user"
    ).fetchone()
    if memberships is None or int(memberships[0]) != 0:
        raise RuntimeError("HOSTED_PREVIEW_RUNTIME_MEMBERSHIP_FORBIDDEN")

    required = connection.execute(
        "SELECT to_regclass('omni_cio_v10.tenants'), "
        "to_regclass('omni_cio_v10.users'), "
        "to_regclass('omni_cio_v10.web_sessions')"
    ).fetchone()
    if required is None or any(value is None for value in required):
        raise RuntimeError("HOSTED_PREVIEW_SCHEMA_INCOMPLETE")

    rows = connection.execute(
        "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity "
        "FROM pg_catalog.pg_class c "
        "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'omni_cio_v10' "
        "AND c.relname = ANY(%s) ORDER BY c.relname",
        (
            [
                "broker_accounts",
                "broker_connection_accounts",
                "broker_connections",
            ],
        ),
    ).fetchall()
    if len(rows) != 3 or any(not bool(row[1]) or not bool(row[2]) for row in rows):
        raise RuntimeError("HOSTED_PREVIEW_FORCE_RLS_REQUIRED")


def _probe_hosted_preview_database(connection: Any) -> None:
    _probe_runtime_database(connection)
    _verify_synthetic_scope(connection)


def _empty_portfolio(now: str) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "generated_at": now,
        "state": "EMPTY",
        "connections": [],
        "accounts": [],
        "warnings": [
            {
                "code": "SYNTHETIC_PREVIEW_NO_BROKER_DATA",
                "severity": "info",
                "message": (
                    "Real broker and portfolio data are disabled in technical "
                    "acceptance."
                ),
            }
        ],
        "calculation_policy": {
            "decimal_transport": "canonical_decimal_string",
            "cross_currency_aggregation": "forbidden_without_explicit_fx",
            "broker_position_value": "broker_reported",
            "current_market_value": "read_only_quote_when_authorized",
            "weights": "within_position_currency_only",
        },
    }


def _empty_watchtower(now: str) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "generated_at": now,
        "state": "EMPTY",
        "truncated": False,
        "counts": {
            "total": 0,
            "active": 0,
            "resolved": 0,
            "critical": 0,
            "reopened": 0,
            "missing_alert_metadata": 0,
        },
        "incidents": [],
    }


def _empty_research(now: str) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "generated_at": now,
        "state": "EMPTY",
        "truncated": False,
        "invalid_dossier_count": 0,
        "duplicate_dossier_count": 0,
        "dossiers": [],
    }


def _empty_decision(now: str) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "generated_at": now,
        "state": "EMPTY",
        "reason": "SYNTHETIC_PREVIEW_NO_PRIVATE_STATE",
        "main_decision": None,
        "decision": None,
        "plan": None,
        "execution_authorized": False,
        "trading_methods": False,
    }


def _system_status(
    services: HostedPreviewServicesV1,
    *,
    now: str,
) -> dict[str, object]:
    services.database_probe()
    return {
        "schema_version": "1.0.0",
        "generated_at": now,
        "state": "READY",
        "release": {
            "release": "v10-phase5-synthetic-technical-auth",
            "git_sha": services.release_sha,
            "git_sha_source": "RENDER_GIT_COMMIT",
            "last_deploy_at": None,
            "last_deploy_source": "RENDER_MANAGED",
            "web_artifact_at": None,
            "web_artifact_source": "RENDER_BUILD",
        },
        "database": {
            "state": "READY",
            "availability": "AVAILABLE",
            "current_migration": "0005_browser_bound_provider_auth",
            "expected_migration": "0005_browser_bound_provider_auth",
            "migration_count": 5,
            "exact_migration_state": True,
        },
        "backup": {
            "state": "BLOCKED",
            "availability": "NOT_CONFIGURED",
            "last_success_at": None,
            "rpo_minutes": 0,
            "rto_minutes": 0,
        },
        "resources": {
            "disk": {
                "state": "DEGRADED",
                "availability": "NOT_AVAILABLE",
                "free_gib": None,
                "free_percent": None,
                "warning_threshold_gib": 0,
                "block_threshold_gib": 0,
            },
            "temperature": {
                "state": "DEGRADED",
                "availability": "NOT_AVAILABLE",
                "gpu_c": None,
                "limit_c": 0,
            },
        },
        "safety": {
            "mode": "READ_ONLY_DIAGNOSTIC",
            "real_execution_enabled": False,
            "trading_methods": False,
            "broker_write_authority": False,
            "public_ingress": False,
            "watchtower_enabled": False,
        },
        "services": [
            {
                "id": "application",
                "label": "V10 Web technical acceptance",
                "state": "READY",
                "availability": "AVAILABLE",
                "detail": "Provider-only React/FastAPI technical boundary is online.",
                "observed_at": now,
            },
            {
                "id": "database",
                "label": "Neon PostgreSQL 18",
                "state": "READY",
                "availability": "AVAILABLE",
                "detail": "Least-privilege runtime and session storage verified.",
                "observed_at": now,
            },
            {
                "id": "broker",
                "label": "T-Invest connector",
                "state": "BLOCKED",
                "availability": "LOCKED_FUTURE_WP",
                "detail": "Real credentials and public connector are disabled.",
                "observed_at": now,
            },
        ],
        "recent_jobs": [],
        "recent_errors": [],
        "limits": {"recent_jobs": 20, "recent_errors": 20},
    }


class _HostedPreviewRoutesV1:
    def __init__(
        self,
        services: HostedPreviewServicesV1,
        provider_auth: ProviderAuthRouteServicesV1,
        web_dist: Path,
    ) -> None:
        self._services = services
        self._provider_auth = provider_auth
        self._web_dist = web_dist

    def unhandled_exception(self, request: Request, exc: Exception) -> Response:
        del exc
        return _safe_error(
            "INTERNAL_ERROR",
            500,
            api_path=_is_api_path(request.url.path),
        )

    def healthz(self) -> Response:
        try:
            self._services.database_probe()
        except Exception:
            return JSONResponse(
                {
                    "status": "unavailable",
                    "release_sha": self._services.release_sha,
                    "synthetic_preview": True,
                },
                status_code=503,
            )
        return JSONResponse(
            {
                "status": "ok",
                "release_sha": self._services.release_sha,
                "database": "READY",
                "synthetic_preview": True,
            }
        )

    def preview_mode(self) -> dict[str, object]:
        return {
            "enabled": False,
            "synthetic": True,
            "broker_credentials_enabled": False,
            "registration_enabled": False,
            "label": "Synthetic technical boundary",
        }

    def session_view(self, request: Request) -> Response:
        token = request.cookies.get(BROWSER_SESSION_COOKIE, "")
        scope = _request_session_scope(request)
        csrf = request.cookies.get(BROWSER_CSRF_COOKIE, "")
        if (
            scope is None
            or not token
            or not self._provider_auth.cookies.csrf_matches(
                session_token=token,
                csrf_token=csrf,
            )
        ):
            return JSONResponse({"authenticated": False})
        return JSONResponse(
            {
                "authenticated": True,
                "expires_at": scope.expires_at.isoformat(),
                "csrf_token": csrf,
            }
        )

    def providers(self) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
        for descriptor in self._provider_auth.descriptors():
            row: dict[str, object] = {
                "provider": descriptor.provider.value,
                "enabled": descriptor.enabled,
            }
            if not descriptor.enabled:
                row["reason"] = "NOT_CONFIGURED"
            result.append(row)
        return result

    def logout(self, request: Request) -> Response:
        scope = _require_session(request)
        if isinstance(scope, Response):
            return scope
        self._services.sessions.revoke(
            request.cookies.get(BROWSER_SESSION_COOKIE),
            now=_utc(self._services.now()),
        )
        result = JSONResponse({"ok": True})
        result.delete_cookie(BROWSER_SESSION_COOKIE, path="/", secure=True)
        result.delete_cookie(BROWSER_CSRF_COOKIE, path="/", secure=True)
        return result

    def revoke_all(self, request: Request) -> Response:
        scope = _require_session(request)
        if isinstance(scope, Response):
            return scope
        self._services.sessions.revoke_all_for_user(
            scope.user_id,
            now=_utc(self._services.now()),
        )
        result = JSONResponse({"ok": True})
        result.delete_cookie(BROWSER_SESSION_COOKIE, path="/", secure=True)
        result.delete_cookie(BROWSER_CSRF_COOKIE, path="/", secure=True)
        return result

    def health(self, request: Request) -> Response:
        scope = _require_session(request)
        if isinstance(scope, Response):
            return scope
        try:
            self._services.database_probe()
        except Exception:
            return JSONResponse(
                {
                    "state": "OFFLINE",
                    "freshness": "UNKNOWN",
                    "checked_at": _now_iso(self._services),
                },
                status_code=503,
            )
        return JSONResponse(
            {
                "state": "READY",
                "freshness": "FRESH",
                "checked_at": _now_iso(self._services),
            }
        )

    def broker_connections(self, request: Request) -> Response:
        scope = _require_session(request)
        if isinstance(scope, Response):
            return scope
        return JSONResponse([])

    def live_acceptance_status(self, request: Request) -> Response:
        scope = _require_session(request)
        if isinstance(scope, Response):
            return scope
        return JSONResponse({"enabled": False})

    def broker_mutation_disabled(
        self,
        request: Request,
        connection_id: str | None = None,
    ) -> Response:
        del connection_id
        scope = _require_session(request)
        if isinstance(scope, Response):
            return scope
        return _safe_error("BROKER_CREDENTIALS_DISABLED_IN_SYNTHETIC_PREVIEW", 403)

    def portfolio_dashboard(self, request: Request) -> Response:
        scope = _require_session(request)
        if isinstance(scope, Response):
            return scope
        return JSONResponse(_empty_portfolio(_now_iso(self._services)))

    def watchtower_incidents(self, request: Request) -> Response:
        scope = _require_session(request)
        if isinstance(scope, Response):
            return scope
        return JSONResponse(_empty_watchtower(_now_iso(self._services)))

    def research_dossiers(self, request: Request) -> Response:
        scope = _require_session(request)
        if isinstance(scope, Response):
            return scope
        return JSONResponse(_empty_research(_now_iso(self._services)))

    def decision_plan(self, request: Request) -> Response:
        scope = _require_session(request)
        if isinstance(scope, Response):
            return scope
        return JSONResponse(_empty_decision(_now_iso(self._services)))

    def system_status(self, request: Request) -> Response:
        scope = _require_session(request)
        if isinstance(scope, Response):
            return scope
        try:
            payload = _system_status(
                self._services,
                now=_now_iso(self._services),
            )
        except Exception:
            return _safe_error("SYSTEM_STATUS_UNAVAILABLE", 503)
        return JSONResponse(payload)

    def unknown_api_path(self, path: str) -> Response:
        del path
        return _safe_error("NOT_FOUND", 404)

    def web_fallback(self, path: str) -> FileResponse:
        del path
        return FileResponse(self._web_dist / "index.html")


def _register_hosted_routes(
    app: FastAPI,
    routes: _HostedPreviewRoutesV1,
) -> None:
    app.add_exception_handler(Exception, routes.unhandled_exception)
    app.add_api_route("/healthz", routes.healthz, methods=["GET"])
    app.add_api_route(PREVIEW_STATUS_PATH, routes.preview_mode, methods=["GET"])
    app.add_api_route("/api/v10/web/session", routes.session_view, methods=["GET"])
    app.add_api_route("/api/v10/web/auth/providers", routes.providers, methods=["GET"])
    app.add_api_route("/api/v10/web/session/logout", routes.logout, methods=["POST"])
    app.add_api_route(
        "/api/v10/web/session/revoke-all",
        routes.revoke_all,
        methods=["POST"],
    )
    app.add_api_route("/api/v10/web/health", routes.health, methods=["GET"])
    app.add_api_route(
        "/api/v10/web/broker-connections",
        routes.broker_connections,
        methods=["GET"],
    )
    app.add_api_route(
        "/api/v10/web/wp15-live-acceptance/status",
        routes.live_acceptance_status,
        methods=["GET"],
    )
    app.add_api_route(
        "/api/v10/web/broker-connections/preview",
        routes.broker_mutation_disabled,
        methods=["POST"],
    )
    app.add_api_route(
        "/api/v10/web/broker-connections/commit",
        routes.broker_mutation_disabled,
        methods=["POST"],
    )
    app.add_api_route(
        "/api/v10/web/broker-connections/{connection_id}/replace",
        routes.broker_mutation_disabled,
        methods=["POST"],
    )
    app.add_api_route(
        "/api/v10/web/broker-connections/{connection_id}",
        routes.broker_mutation_disabled,
        methods=["DELETE"],
    )
    app.add_api_route(
        "/api/v10/web/portfolio-dashboard",
        routes.portfolio_dashboard,
        methods=["GET"],
    )
    app.add_api_route(
        "/api/v10/web/watchtower-incidents",
        routes.watchtower_incidents,
        methods=["GET"],
    )
    app.add_api_route(
        "/api/v10/web/research-dossiers",
        routes.research_dossiers,
        methods=["GET"],
    )
    app.add_api_route(
        "/api/v10/web/decision-plan",
        routes.decision_plan,
        methods=["GET"],
    )
    app.add_api_route(
        "/api/v10/web/system-status",
        routes.system_status,
        methods=["GET"],
    )
    app.add_api_route(
        "/api/{path:path}",
        routes.unknown_api_path,
        methods=["GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"],
        include_in_schema=False,
    )
    app.add_api_route(
        "/{path:path}",
        routes.web_fallback,
        methods=["GET"],
        include_in_schema=False,
    )


def _validate_hosted_runtime_inputs(
    services: HostedPreviewServicesV1,
    *,
    web_dist: Path,
    trusted_edge_tls_terminated: bool,
) -> str:
    hostname = _hostname(services.hostname)
    services.release_sha = _release_sha(services.release_sha)
    services.database_probe()
    if trusted_edge_tls_terminated and not hostname.endswith(_RENDER_HOST_SUFFIX):
        raise RuntimeError("HOSTED_PREVIEW_TRUSTED_EDGE_INVALID")
    if not web_dist.is_dir() or not (web_dist / "index.html").is_file():
        raise RuntimeError("HOSTED_PREVIEW_WEB_BUILD_MISSING")
    return hostname


def create_hosted_preview_app(
    services: HostedPreviewServicesV1,
    *,
    web_dist: Path = WEB_DIST,
    additional_hosts: tuple[str, ...] = (),
    trusted_edge_tls_terminated: bool = False,
) -> FastAPI:
    hostname = _validate_hosted_runtime_inputs(
        services,
        web_dist=web_dist,
        trusted_edge_tls_terminated=trusted_edge_tls_terminated,
    )
    provider_auth = services.provider_auth or _disabled_provider_auth(services)
    app = FastAPI(
        title="Omni-CIO V10 hosted technical acceptance",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    routes = _HostedPreviewRoutesV1(services, provider_auth, web_dist)
    install_provider_auth_routes_v1(app, services=provider_auth)

    assets = web_dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="web-assets")
    _register_hosted_routes(app, routes)

    app.add_middleware(
        HostedPreviewSecurityMiddlewareV1,
        hostname=hostname,
        cookies=provider_auth.cookies,
        sessions=services.sessions,
        now=services.now,
        trusted_edge_tls_terminated=trusted_edge_tls_terminated,
        abuse=HostedRequestAbuseControlV1(),
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[hostname, *additional_hosts],
        www_redirect=False,
    )
    return app


def create_app() -> FastAPI:
    if os.environ.get("OMNI_V10_HOSTED_PREVIEW", "").strip() != "1":
        raise RuntimeError("HOSTED_PREVIEW_NOT_ENABLED")
    hostname = _hostname(_required_env("RENDER_EXTERNAL_HOSTNAME"))
    release_sha = _release_sha(_required_env("RENDER_GIT_COMMIT"))
    raw_connection = connect_postgres(_required_env("OMNI_V10_POSTGRES_DSN"))
    _configure_long_lived_web_connection(raw_connection)
    connection = _SerializedWebConnection(raw_connection)
    _probe_hosted_preview_database(connection)
    sessions = PostgresWebSessionRegistryV1(
        connection,
        policy=PREVIEW_SESSION_POLICY,
    )
    provider_auth = build_wp22a_phase5_provider_auth(
        connection=connection,
        sessions=sessions,
        canonical_origin=f"https://{hostname}",
    )
    return create_hosted_preview_app(
        HostedPreviewServicesV1(
            sessions=sessions,
            database_probe=lambda: _probe_hosted_preview_database(connection),
            hostname=hostname,
            release_sha=release_sha,
            provider_auth=provider_auth,
        ),
        trusted_edge_tls_terminated=True,
    )
