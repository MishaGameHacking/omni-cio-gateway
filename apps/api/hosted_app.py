from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
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

from omni_cio.web.browser_security_v1 import (
    BROWSER_CSRF_COOKIE,
    BROWSER_CSRF_HEADER,
    BROWSER_SESSION_COOKIE,
    BrowserCookiePolicyV1,
)
from omni_cio.web.telegram_auth_services_v1 import TelegramAuthRouteServicesV1
from omni_cio.web.request_limits_v1 import (
    HostedRequestAbuseControlV1,
    is_session_token_candidate,
)
from omni_cio.web.session_v1 import SessionScopeV1


WEB_DIST = Path(__file__).resolve().parents[1] / "web" / "dist"
HOSTED_STATUS_PATH = "/api/v10/web/preview-mode"
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_UNTRUSTED_FETCH_SITES = frozenset({"cross-site", "same-site"})
_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_HOST_PATTERN = re.compile(
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+"
)
_HEALTHZ_PATH = "/healthz"
_LIVEZ_PATH = "/livez"
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
    def resolve(self, token: str | None, *, now: datetime) -> SessionScopeV1 | None: ...

    def revoke(self, token: str | None, *, now: datetime) -> bool: ...

    def revoke_all_for_user(self, user_id: str, *, now: datetime) -> int: ...


@dataclass(slots=True)
class HostedRuntimeServicesV1:
    sessions: SessionRegistryLike
    database_probe: Callable[[], None]
    hostname: str
    release_sha: str
    provider_auth: TelegramAuthRouteServicesV1
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)
    browser_origin_hostname: str | None = None
    synthetic_preview: bool = False
    release_label: str = "v10-hosted-runtime"
    git_sha_source: str = "OMNI_V10_RELEASE_SHA"
    last_deploy_source: str = "HOSTED_RUNTIME"
    web_artifact_source: str = "GITHUB_SOURCE_BUILD"


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise RuntimeError("HOSTED_RUNTIME_CLOCK_NOT_UTC_AWARE")
    return value.astimezone(timezone.utc)


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name}_REQUIRED")
    return value


def _hostname(value: str) -> str:
    normalized = value.strip().lower().rstrip(".")
    if len(normalized) > 253 or _HOST_PATTERN.fullmatch(normalized) is None:
        raise RuntimeError("HOSTED_RUNTIME_HOST_INVALID")
    return normalized


def _release_sha(value: str) -> str:
    normalized = value.strip().lower()
    if _SHA_PATTERN.fullmatch(normalized) is None:
        raise RuntimeError("HOSTED_RUNTIME_RELEASE_SHA_INVALID")
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


def _now_iso(services: HostedRuntimeServicesV1) -> str:
    return _utc(services.now()).isoformat()


def _is_api_path(path: str) -> bool:
    return path.startswith("/api/") or path in {_HEALTHZ_PATH, _LIVEZ_PATH}


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


def _request_session_scope(request: Request) -> SessionScopeV1 | None:
    scope = getattr(request.state, _SESSION_SCOPE_STATE_ATTR, None)
    return scope if isinstance(scope, SessionScopeV1) else None


class HostedSecurityMiddlewareV1(BaseHTTPMiddleware):
    def __init__(
        self,
        app: Any,
        *,
        hostname: str,
        cookies: BrowserCookiePolicyV1,
        browser_origin_hostname: str | None = None,
        sessions: SessionRegistryLike,
        now: Callable[[], datetime],
        trusted_edge_tls_terminated: bool = False,
        provider_start_paths: frozenset[str] = frozenset(),
        server_mutation_paths: frozenset[str] = frozenset(),
        abuse: HostedRequestAbuseControlV1 | None = None,
    ) -> None:
        super().__init__(app)
        self._hostname = hostname
        self._browser_origin_hostname = _hostname(browser_origin_hostname or hostname)
        self._cookies = cookies
        self._sessions = sessions
        self._now = now
        self._trusted_edge_tls_terminated = trusted_edge_tls_terminated
        self._provider_start_paths = provider_start_paths
        self._server_mutation_paths = server_mutation_paths
        self._abuse = abuse or HostedRequestAbuseControlV1()

    def _transport_error(self, request: Request, *, api_path: bool) -> Response | None:
        # Never treat a client-controlled forwarded header as TLS authority. A managed
        # reverse-proxy boundary may terminate TLS only when source composition explicitly
        # marks that provider boundary as trusted.
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
        if request.url.path == _LIVEZ_PATH:
            return None
        if request.url.path == _HEALTHZ_PATH:
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
        if request.method == "POST" and request.url.path in self._server_mutation_paths:
            # Explicit server-to-server mutation paths own their separate authority
            # contract and bypass browser Origin/Fetch-Metadata/CSRF only after global
            # admission controls.
            return None
        if (
            _origin_hostname(request.headers.get("origin", ""))
            != self._browser_origin_hostname
        ):
            return _safe_error("ORIGIN_REQUIRED", 403, api_path=api_path)
        fetch_site = request.headers.get("sec-fetch-site", "").strip().lower()
        if fetch_site in _UNTRUSTED_FETCH_SITES:
            return _safe_error("FETCH_METADATA_REJECTED", 403, api_path=api_path)
        if request.url.path in self._provider_start_paths:
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


def _empty_portfolio(
    now: str,
    *,
    synthetic_preview: bool = True,
) -> dict[str, object]:
    warning_code = (
        "SYNTHETIC_PREVIEW_NO_BROKER_DATA"
        if synthetic_preview
        else "HOSTED_RUNTIME_NO_BROKER_DATA"
    )
    warning_message = (
        "Real broker and portfolio data are disabled in technical acceptance."
        if synthetic_preview
        else "Real broker and portfolio data are disabled in this hosted runtime."
    )
    return {
        "schema_version": "1.0.0",
        "generated_at": now,
        "state": "EMPTY",
        "connections": [],
        "accounts": [],
        "warnings": [
            {
                "code": warning_code,
                "severity": "info",
                "message": warning_message,
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


def _empty_decision(
    now: str,
    *,
    synthetic_preview: bool = True,
) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "generated_at": now,
        "state": "EMPTY",
        "reason": (
            "SYNTHETIC_PREVIEW_NO_PRIVATE_STATE"
            if synthetic_preview
            else "HOSTED_RUNTIME_NO_PRIVATE_STATE"
        ),
        "main_decision": None,
        "decision": None,
        "plan": None,
        "execution_authorized": False,
        "trading_methods": False,
    }


def _system_status(
    services: HostedRuntimeServicesV1,
    *,
    now: str,
) -> dict[str, object]:
    services.database_probe()
    return {
        "schema_version": "1.0.0",
        "generated_at": now,
        "state": "READY",
        "release": {
            "release": services.release_label,
            "git_sha": services.release_sha,
            "git_sha_source": services.git_sha_source,
            "last_deploy_at": None,
            "last_deploy_source": services.last_deploy_source,
            "web_artifact_at": None,
            "web_artifact_source": services.web_artifact_source,
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
                "label": "PostgreSQL 18",
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


class _HostedRuntimeRoutesV1:
    def __init__(
        self,
        services: HostedRuntimeServicesV1,
        provider_auth: TelegramAuthRouteServicesV1,
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

    def livez(self) -> Response:
        return JSONResponse(
            {
                "status": "ok",
                "release_sha": self._services.release_sha,
            }
        )

    def healthz(self) -> Response:
        try:
            self._services.database_probe()
        except Exception:
            return JSONResponse(
                {
                    "status": "unavailable",
                    "release_sha": self._services.release_sha,
                    "synthetic_preview": self._services.synthetic_preview,
                },
                status_code=503,
            )
        return JSONResponse(
            {
                "status": "ok",
                "release_sha": self._services.release_sha,
                "database": "READY",
                "synthetic_preview": self._services.synthetic_preview,
            }
        )

    def preview_mode(self) -> dict[str, object]:
        return {
            "enabled": False,
            "synthetic": self._services.synthetic_preview,
            "broker_credentials_enabled": False,
            "registration_enabled": self._provider_auth.registration_enabled,
            "label": (
                "Synthetic technical boundary"
                if self._services.synthetic_preview
                else "Hosted production boundary"
            ),
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
                row["reason"] = self._provider_auth.disabled_reason(descriptor.provider)
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
        detail = (
            "BROKER_CREDENTIALS_DISABLED_IN_SYNTHETIC_PREVIEW"
            if self._services.synthetic_preview
            else "BROKER_CREDENTIALS_DISABLED_IN_HOSTED_RUNTIME"
        )
        return _safe_error(detail, 403)

    def portfolio_dashboard(self, request: Request) -> Response:
        scope = _require_session(request)
        if isinstance(scope, Response):
            return scope
        return JSONResponse(
            _empty_portfolio(
                _now_iso(self._services),
                synthetic_preview=self._services.synthetic_preview,
            )
        )

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
        return JSONResponse(
            _empty_decision(
                _now_iso(self._services),
                synthetic_preview=self._services.synthetic_preview,
            )
        )

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
    routes: _HostedRuntimeRoutesV1,
) -> None:
    app.add_exception_handler(Exception, routes.unhandled_exception)
    app.add_api_route(_LIVEZ_PATH, routes.livez, methods=["GET"])
    app.add_api_route(_HEALTHZ_PATH, routes.healthz, methods=["GET"])
    app.add_api_route(HOSTED_STATUS_PATH, routes.preview_mode, methods=["GET"])
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
    services: HostedRuntimeServicesV1,
    *,
    web_dist: Path,
) -> str:
    hostname = _hostname(services.hostname)
    services.release_sha = _release_sha(services.release_sha)
    services.database_probe()
    if not web_dist.is_dir() or not (web_dist / "index.html").is_file():
        raise RuntimeError("HOSTED_RUNTIME_WEB_BUILD_MISSING")
    return hostname


def create_hosted_app(
    services: HostedRuntimeServicesV1,
    *,
    web_dist: Path = WEB_DIST,
    additional_hosts: tuple[str, ...] = (),
    trusted_edge_tls_terminated: bool = False,
    provider_start_paths: frozenset[str] = frozenset(),
    server_mutation_paths: frozenset[str] = frozenset(),
    provider_route_installer: Callable[..., None],
) -> FastAPI:
    hostname = _validate_hosted_runtime_inputs(
        services,
        web_dist=web_dist,
    )
    app = FastAPI(
        title="Omni-CIO V10 hosted runtime",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    routes = _HostedRuntimeRoutesV1(
        services,
        services.provider_auth,
        web_dist,
    )
    provider_route_installer(app, services=services.provider_auth)

    assets = web_dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="web-assets")
    _register_hosted_routes(app, routes)

    app.add_middleware(
        HostedSecurityMiddlewareV1,
        hostname=hostname,
        cookies=services.provider_auth.cookies,
        browser_origin_hostname=services.browser_origin_hostname,
        sessions=services.sessions,
        now=services.now,
        trusted_edge_tls_terminated=trusted_edge_tls_terminated,
        provider_start_paths=provider_start_paths,
        server_mutation_paths=server_mutation_paths,
        abuse=HostedRequestAbuseControlV1(),
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[hostname, *additional_hosts],
        www_redirect=False,
    )
    return app