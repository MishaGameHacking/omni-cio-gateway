from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import secrets
from typing import Any

from fastapi import FastAPI

from apps.api.app import (
    _SerializedWebConnection,
    _configure_long_lived_web_connection,
)
from apps.api.cf_d_database_bootstrap import CF_D_DATABASE_BOOTSTRAP_PATH
from apps.api.hosted_app import (
    HostedRuntimeServicesV1,
    HostedSecurityMiddlewareV1,
    SessionRegistryLike,
    _hostname as _runtime_hostname,
    _release_sha as _runtime_release_sha,
    _required_env,
    create_hosted_app,
)
from apps.api.hosted_database_runtime import probe_hosted_runtime_database
from apps.api.wp22a_phase5_auth import build_wp22a_phase5_provider_auth
from omni_cio.persistence.hosted_synthetic_scope_v1 import (
    SYNTHETIC_TENANT_ID as PREVIEW_TENANT_ID,
    SYNTHETIC_USER_ID as PREVIEW_USER_ID,
    record_sha256 as _record_sha256,
    verify_synthetic_scope as _verify_synthetic_scope,
)
from omni_cio.persistence.migration import connect_postgres
from omni_cio.web.browser_security_v1 import (
    BROWSER_CSRF_COOKIE,
    BROWSER_CSRF_HEADER,
    BrowserCookiePolicyV1,
)
from omni_cio.web.identity_v1 import IdentityProviderV1
from omni_cio.web.persistence_v1 import PostgresWebSessionRegistryV1
from omni_cio.web.provider_auth_routes_v1 import (
    TELEGRAM_START_PATH,
    VK_ID_START_PATH,
    ProviderAuthRouteServicesV1,
    install_provider_auth_routes_v1,
)
from omni_cio.web.request_limits_v1 import HostedRequestAbuseControlV1
from omni_cio.web.session_v1 import SessionPolicyV1


WEB_DIST = Path(__file__).resolve().parents[1] / "web" / "dist"
PREVIEW_STATUS_PATH = "/api/v10/web/preview-mode"
CSRF_COOKIE = BROWSER_CSRF_COOKIE
CSRF_HEADER = BROWSER_CSRF_HEADER
PREVIEW_SESSION_POLICY = SessionPolicyV1(
    idle_lifetime=timedelta(hours=2),
    absolute_lifetime=timedelta(hours=24),
)
_PROVIDER_START_PATHS = frozenset({TELEGRAM_START_PATH, VK_ID_START_PATH})
_SERVER_MUTATION_PATHS = frozenset({CF_D_DATABASE_BOOTSTRAP_PATH})
_RENDER_HOST_SUFFIX = ".onrender.com"
_HISTORICAL_RUNTIME_ROLE = "omni_cio_hosted_api"


@dataclass(slots=True)
class HostedPreviewServicesV1:
    sessions: SessionRegistryLike
    database_probe: Callable[[], None]
    hostname: str
    release_sha: str
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)
    provider_auth: ProviderAuthRouteServicesV1 | None = None
    browser_origin_hostname: str | None = None


def _hostname(value: str) -> str:
    try:
        return _runtime_hostname(value)
    except RuntimeError as exc:
        raise RuntimeError("HOSTED_PREVIEW_HOST_INVALID") from exc


def _release_sha(value: str) -> str:
    try:
        return _runtime_release_sha(value)
    except RuntimeError as exc:
        raise RuntimeError("HOSTED_PREVIEW_RELEASE_SHA_INVALID") from exc


def _disabled_provider_auth(
    services: HostedPreviewServicesV1,
) -> ProviderAuthRouteServicesV1:
    historical_providers = (
        IdentityProviderV1.TELEGRAM,
        IdentityProviderV1.VK_ID,
    )
    return ProviderAuthRouteServicesV1(
        runtimes=(),
        authentication=None,
        cookies=BrowserCookiePolicyV1(
            csrf_binding_key=secrets.token_bytes(32),
            allowed_providers=historical_providers,
        ),
        now=services.now,
        descriptor_providers=historical_providers,
    )


class HostedPreviewSecurityMiddlewareV1(HostedSecurityMiddlewareV1):
    """Historical preview adapter over the current hosted security core."""

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
        abuse: HostedRequestAbuseControlV1 | None = None,
    ) -> None:
        super().__init__(
            app,
            hostname=hostname,
            cookies=cookies,
            browser_origin_hostname=browser_origin_hostname,
            sessions=sessions,
            now=now,
            trusted_edge_tls_terminated=trusted_edge_tls_terminated,
            provider_start_paths=_PROVIDER_START_PATHS,
            server_mutation_paths=_SERVER_MUTATION_PATHS,
            abuse=abuse,
        )


_PREVIEW_DATABASE_ERRORS = {
    "HOSTED_RUNTIME_POSTGRES18_REQUIRED": "HOSTED_PREVIEW_POSTGRES18_REQUIRED",
    "HOSTED_RUNTIME_DATABASE_ROLE_DRIFT": "HOSTED_PREVIEW_RUNTIME_ROLE_DRIFT",
    "HOSTED_RUNTIME_DATABASE_MEMBERSHIP_FORBIDDEN": (
        "HOSTED_PREVIEW_RUNTIME_MEMBERSHIP_FORBIDDEN"
    ),
    "HOSTED_RUNTIME_DATABASE_SCHEMA_INCOMPLETE": "HOSTED_PREVIEW_SCHEMA_INCOMPLETE",
    "HOSTED_RUNTIME_DATABASE_FORCE_RLS_REQUIRED": "HOSTED_PREVIEW_FORCE_RLS_REQUIRED",
}


def _probe_runtime_database(connection: Any) -> None:
    try:
        probe_hosted_runtime_database(
            connection,
            expected_runtime_role=_HISTORICAL_RUNTIME_ROLE,
        )
    except RuntimeError as exc:
        translated = _PREVIEW_DATABASE_ERRORS.get(str(exc))
        if translated is None:
            raise
        raise RuntimeError(translated) from exc


def _probe_hosted_preview_database(connection: Any) -> None:
    _probe_runtime_database(connection)
    _verify_synthetic_scope(connection)


def _validate_preview_inputs(
    services: HostedPreviewServicesV1,
    *,
    web_dist: Path,
    trusted_edge_tls_terminated: bool,
) -> tuple[str, str]:
    hostname = _hostname(services.hostname)
    release_sha = _release_sha(services.release_sha)
    if trusted_edge_tls_terminated and not hostname.endswith(_RENDER_HOST_SUFFIX):
        raise RuntimeError("HOSTED_PREVIEW_TRUSTED_EDGE_INVALID")
    if not web_dist.is_dir() or not (web_dist / "index.html").is_file():
        raise RuntimeError("HOSTED_PREVIEW_WEB_BUILD_MISSING")
    return hostname, release_sha


def create_hosted_preview_app(
    services: HostedPreviewServicesV1,
    *,
    web_dist: Path = WEB_DIST,
    additional_hosts: tuple[str, ...] = (),
    trusted_edge_tls_terminated: bool = False,
) -> FastAPI:
    """Historical compatibility wrapper; current hosted behavior has one implementation."""

    hostname, release_sha = _validate_preview_inputs(
        services,
        web_dist=web_dist,
        trusted_edge_tls_terminated=trusted_edge_tls_terminated,
    )
    provider_auth = services.provider_auth or _disabled_provider_auth(services)
    runtime_services = HostedRuntimeServicesV1(
        sessions=services.sessions,
        database_probe=services.database_probe,
        hostname=hostname,
        release_sha=release_sha,
        provider_auth=provider_auth,
        now=services.now,
        browser_origin_hostname=services.browser_origin_hostname,
        synthetic_preview=True,
        release_label="v10-phase5-synthetic-technical-auth",
        git_sha_source="RENDER_GIT_COMMIT",
        last_deploy_source="RENDER_MANAGED",
        web_artifact_source="RENDER_BUILD",
        database_label="Neon PostgreSQL 18",
    )
    return create_hosted_app(
        runtime_services,
        web_dist=web_dist,
        additional_hosts=additional_hosts,
        trusted_edge_tls_terminated=trusted_edge_tls_terminated,
        provider_start_paths=_PROVIDER_START_PATHS,
        server_mutation_paths=_SERVER_MUTATION_PATHS,
        include_livez=False,
        provider_route_installer=install_provider_auth_routes_v1,
    )


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
