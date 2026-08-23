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
from omni_cio.persistence.migration import connect_postgres
from omni_cio.web.api_v1 import SESSION_COOKIE
from omni_cio.web.persistence_v1 import PostgresWebSessionRegistryV1
from omni_cio.web.session_v1 import SessionPolicyV1, SessionScopeV1


WEB_DIST = Path(__file__).resolve().parents[1] / "web" / "dist"
PREVIEW_LOGIN_PATH = "/api/v10/web/preview-login"
PREVIEW_STATUS_PATH = "/api/v10/web/preview-mode"
CSRF_COOKIE = "__Host-omni_v10_csrf"
CSRF_HEADER = "X-Omni-CSRF"
PREVIEW_TENANT_ID = "tenant:v1:synthetic_preview"
PREVIEW_USER_ID = "user:v1:synthetic_preview"
PREVIEW_SESSION_POLICY = SessionPolicyV1(
    idle_lifetime=timedelta(hours=2),
    absolute_lifetime=timedelta(hours=24),
)
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_HOST_PATTERN = re.compile(
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+"
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


def _harden_response(response: Response, *, api_path: bool) -> Response:
    response.headers["Strict-Transport-Security"] = "max-age=31536000"
    response.headers["Content-Security-Policy"] = _CONTENT_SECURITY_POLICY
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Cache-Control"] = "no-store" if api_path else "no-cache"
    return response


def _safe_error(detail: str, status_code: int, *, api_path: bool = True) -> Response:
    return _harden_response(
        JSONResponse({"detail": detail}, status_code=status_code),
        api_path=api_path,
    )


class HostedPreviewSecurityMiddlewareV1(BaseHTTPMiddleware):
    def __init__(self, app: Any, *, hostname: str) -> None:
        super().__init__(app)
        self._hostname = hostname

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[..., Any],
    ) -> Response:
        forwarded = request.headers.get("x-forwarded-proto", "").strip().lower()
        scheme = forwarded or request.url.scheme.lower()
        api_path = (
            request.url.path.startswith("/api/") or request.url.path == "/healthz"
        )
        if scheme != "https":
            return _safe_error("HTTPS_REQUIRED", 403, api_path=api_path)

        if request.method not in _SAFE_METHODS:
            if _origin_hostname(request.headers.get("origin", "")) != self._hostname:
                return _safe_error("ORIGIN_REQUIRED", 403, api_path=api_path)
            if request.url.path != PREVIEW_LOGIN_PATH:
                cookie = request.cookies.get(CSRF_COOKIE, "")
                header = request.headers.get(CSRF_HEADER, "")
                if (
                    not cookie
                    or not header
                    or not secrets.compare_digest(cookie, header)
                ):
                    return _safe_error("CSRF_REJECTED", 403, api_path=api_path)

        response = await call_next(request)
        return _harden_response(response, api_path=api_path)


def _require_session(
    request: Request,
    services: HostedPreviewServicesV1,
) -> SessionScopeV1 | Response:
    scope = services.sessions.resolve(
        request.cookies.get(SESSION_COOKIE),
        now=_utc(services.now()),
    )
    if scope is None:
        return _safe_error("AUTHENTICATION_REQUIRED", 401)
    if scope.user_id != PREVIEW_USER_ID or scope.tenant_id != PREVIEW_TENANT_ID:
        return _safe_error("SYNTHETIC_PREVIEW_SCOPE_REQUIRED", 403)
    return scope


def _verify_synthetic_scope(connection: Any) -> None:
    """Verify provider-seeded preview identity without widening runtime authority."""
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
                "message": "Real broker and portfolio data are disabled in preview.",
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
            "release": "v10-phase4-synthetic-preview",
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
            "current_migration": "0004_product_identity_multi_tenant",
            "expected_migration": "0004_product_identity_multi_tenant",
            "migration_count": 4,
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
                "label": "V10 Web preview",
                "state": "READY",
                "availability": "AVAILABLE",
                "detail": "Synthetic React/FastAPI preview is online.",
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


def create_hosted_preview_app(
    services: HostedPreviewServicesV1,
    *,
    web_dist: Path = WEB_DIST,
    additional_hosts: tuple[str, ...] = (),
) -> FastAPI:
    hostname = _hostname(services.hostname)
    services.release_sha = _release_sha(services.release_sha)
    services.database_probe()

    if not web_dist.is_dir() or not (web_dist / "index.html").is_file():
        raise RuntimeError("HOSTED_PREVIEW_WEB_BUILD_MISSING")

    app = FastAPI(
        title="Omni-CIO V10 synthetic hosted preview",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.get("/healthz")
    def healthz() -> Response:
        try:
            services.database_probe()
        except Exception:
            return JSONResponse(
                {
                    "status": "unavailable",
                    "release_sha": services.release_sha,
                    "synthetic_preview": True,
                },
                status_code=503,
            )
        return JSONResponse(
            {
                "status": "ok",
                "release_sha": services.release_sha,
                "database": "READY",
                "synthetic_preview": True,
            }
        )

    @app.get(PREVIEW_STATUS_PATH)
    def preview_mode() -> dict[str, object]:
        return {
            "enabled": True,
            "synthetic": True,
            "broker_credentials_enabled": False,
            "registration_enabled": False,
            "label": "Безопасная публичная демонстрация",
        }

    @app.get("/api/v10/web/session")
    def session_view(request: Request) -> Response:
        scope = services.sessions.resolve(
            request.cookies.get(SESSION_COOKIE),
            now=_utc(services.now()),
        )
        csrf = request.cookies.get(CSRF_COOKIE, "")
        if scope is None or not csrf:
            return JSONResponse({"authenticated": False})
        if scope.user_id != PREVIEW_USER_ID or scope.tenant_id != PREVIEW_TENANT_ID:
            return JSONResponse({"authenticated": False})
        result = JSONResponse(
            {
                "authenticated": True,
                "user_label": "DEMO USER",
                "tenant_label": "SYNTHETIC PREVIEW",
                "expires_at": scope.expires_at.isoformat(),
            }
        )
        result.headers[CSRF_HEADER] = csrf
        return result

    @app.get("/api/v10/web/auth/providers")
    def providers() -> list[dict[str, object]]:
        return [
            {
                "provider": "telegram",
                "enabled": False,
                "reason": "NOT_CONFIGURED",
            },
            {
                "provider": "vk_id",
                "enabled": False,
                "reason": "NOT_CONFIGURED",
            },
        ]

    @app.get("/api/v10/web/private-test-login/status")
    def private_test_status() -> dict[str, bool]:
        return {"enabled": False}

    @app.get("/api/v10/web/private-external-login/status")
    def private_remote_status() -> dict[str, bool]:
        return {"enabled": False}

    @app.post(PREVIEW_LOGIN_PATH)
    def preview_login(request: Request, response: Response) -> dict[str, bool]:
        issued = _utc(services.now())
        services.sessions.revoke(
            request.cookies.get(SESSION_COOKIE),
            now=issued,
        )
        token, scope = services.sessions.create(
            user_id=PREVIEW_USER_ID,
            tenant_id=PREVIEW_TENANT_ID,
            now=issued,
        )
        csrf = secrets.token_urlsafe(32)
        max_age = max(1, int((scope.expires_at - issued).total_seconds()))
        response.set_cookie(
            SESSION_COOKIE,
            token,
            secure=True,
            httponly=True,
            samesite="strict",
            path="/",
            max_age=max_age,
        )
        response.set_cookie(
            CSRF_COOKIE,
            csrf,
            secure=True,
            httponly=True,
            samesite="strict",
            path="/",
            max_age=max_age,
        )
        response.headers[CSRF_HEADER] = csrf
        return {"ok": True}

    @app.post("/api/v10/web/session/logout")
    def logout(request: Request) -> Response:
        scope = _require_session(request, services)
        if isinstance(scope, Response):
            return scope
        services.sessions.revoke(
            request.cookies.get(SESSION_COOKIE),
            now=_utc(services.now()),
        )
        result = JSONResponse({"ok": True})
        result.delete_cookie(SESSION_COOKIE, path="/", secure=True)
        result.delete_cookie(CSRF_COOKIE, path="/", secure=True)
        return result

    @app.post("/api/v10/web/session/revoke-all")
    def revoke_all(request: Request) -> Response:
        scope = _require_session(request, services)
        if isinstance(scope, Response):
            return scope
        services.sessions.revoke(
            request.cookies.get(SESSION_COOKIE),
            now=_utc(services.now()),
        )
        result = JSONResponse({"ok": True})
        result.delete_cookie(SESSION_COOKIE, path="/", secure=True)
        result.delete_cookie(CSRF_COOKIE, path="/", secure=True)
        return result

    @app.get("/api/v10/web/health")
    def health(request: Request) -> Response:
        scope = _require_session(request, services)
        if isinstance(scope, Response):
            return scope
        try:
            services.database_probe()
        except Exception:
            return JSONResponse(
                {
                    "state": "OFFLINE",
                    "freshness": "UNKNOWN",
                    "checked_at": _now_iso(services),
                },
                status_code=503,
            )
        return JSONResponse(
            {
                "state": "READY",
                "freshness": "FRESH",
                "checked_at": _now_iso(services),
            }
        )

    @app.get("/api/v10/web/broker-connections")
    def broker_connections(request: Request) -> Response:
        scope = _require_session(request, services)
        if isinstance(scope, Response):
            return scope
        return JSONResponse([])

    @app.get("/api/v10/web/wp15-live-acceptance/status")
    def live_acceptance_status(request: Request) -> Response:
        scope = _require_session(request, services)
        if isinstance(scope, Response):
            return scope
        return JSONResponse({"enabled": False})

    @app.post("/api/v10/web/broker-connections/preview")
    @app.post("/api/v10/web/broker-connections/commit")
    @app.post("/api/v10/web/broker-connections/{connection_id}/replace")
    @app.delete("/api/v10/web/broker-connections/{connection_id}")
    def broker_mutation_disabled(
        request: Request,
        connection_id: str | None = None,
    ) -> Response:
        del connection_id
        scope = _require_session(request, services)
        if isinstance(scope, Response):
            return scope
        return _safe_error("BROKER_CREDENTIALS_DISABLED_IN_SYNTHETIC_PREVIEW", 403)

    @app.get("/api/v10/web/portfolio-dashboard")
    def portfolio_dashboard(request: Request) -> Response:
        scope = _require_session(request, services)
        if isinstance(scope, Response):
            return scope
        return JSONResponse(_empty_portfolio(_now_iso(services)))

    @app.get("/api/v10/web/watchtower-incidents")
    def watchtower_incidents(request: Request) -> Response:
        scope = _require_session(request, services)
        if isinstance(scope, Response):
            return scope
        return JSONResponse(_empty_watchtower(_now_iso(services)))

    @app.get("/api/v10/web/research-dossiers")
    def research_dossiers(request: Request) -> Response:
        scope = _require_session(request, services)
        if isinstance(scope, Response):
            return scope
        return JSONResponse(_empty_research(_now_iso(services)))

    @app.get("/api/v10/web/decision-plan")
    def decision_plan(request: Request) -> Response:
        scope = _require_session(request, services)
        if isinstance(scope, Response):
            return scope
        return JSONResponse(_empty_decision(_now_iso(services)))

    @app.get("/api/v10/web/system-status")
    def system_status(request: Request) -> Response:
        scope = _require_session(request, services)
        if isinstance(scope, Response):
            return scope
        try:
            payload = _system_status(
                services,
                now=_now_iso(services),
            )
        except Exception:
            return _safe_error("SYSTEM_STATUS_UNAVAILABLE", 503)
        return JSONResponse(payload)

    @app.api_route(
        "/api/{path:path}",
        methods=["GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"],
        include_in_schema=False,
    )
    def unknown_api_path(path: str) -> Response:
        del path
        return _safe_error("NOT_FOUND", 404)

    assets = web_dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="web-assets")

    @app.get("/{path:path}", include_in_schema=False)
    def web_fallback(path: str) -> FileResponse:
        del path
        return FileResponse(web_dist / "index.html")

    app.add_middleware(
        HostedPreviewSecurityMiddlewareV1,
        hostname=hostname,
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
    return create_hosted_preview_app(
        HostedPreviewServicesV1(
            sessions=sessions,
            database_probe=lambda: _probe_hosted_preview_database(connection),
            hostname=hostname,
            release_sha=release_sha,
        )
    )
