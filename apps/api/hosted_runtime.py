from __future__ import annotations

from datetime import timedelta
import os

from fastapi import FastAPI

from apps.api.postgres_web_connection import (
    _BoundedWebConnectionPool,
    _configure_long_lived_web_connection,
)
from apps.api.hosted_app import (
    HostedRuntimeServicesV1,
    _hostname,
    _release_sha,
    _required_env,
    create_hosted_app,
)
from apps.api.hosted_database_runtime import (
    probe_hosted_runtime_database,
    validate_hosted_runtime_role,
)
from apps.api.telegram_auth import build_telegram_provider_auth
from apps.api.timeweb_postgres_tls import (
    connect_prepared_timeweb_postgres,
    prepare_timeweb_postgres_tls,
)
from omni_cio.persistence.migration import ConnectionLike
from omni_cio.web.persistence_v1 import PostgresWebSessionRegistryV1
from omni_cio.web.session_v1 import SessionPolicyV1
from omni_cio.web.telegram_auth_routes_v1 import (
    TELEGRAM_START_PATH,
    install_telegram_auth_routes_v1,
)


_RUNTIME_ENABLED_ENV = "OMNI_V10_HOSTED_RUNTIME"
_HOSTNAME_ENV = "OMNI_V10_PUBLIC_HOSTNAME"
_RELEASE_SHA_ENV = "OMNI_V10_RELEASE_SHA"
_DSN_ENV = "OMNI_V10_POSTGRES_DSN"
_RUNTIME_ROLE_ENV = "OMNI_V10_POSTGRES_RUNTIME_ROLE"
_TRUSTED_EDGE_TLS_ENV = "OMNI_V10_TRUSTED_EDGE_TLS_TERMINATED"
_CANDIDATE_HOSTNAME_ENV = "OMNI_V10_CANDIDATE_HOSTNAME"
_DATABASE_CONNECT_TIMEOUT_SECONDS = 15
_DATABASE_POOL_MAX_SIZE = 4
_DATABASE_POOL_ACQUIRE_TIMEOUT_SECONDS = 5.0
HOSTED_SESSION_POLICY = SessionPolicyV1(
    idle_lifetime=timedelta(hours=2),
    absolute_lifetime=timedelta(hours=24),
)


def _trusted_edge_tls_terminated() -> bool:
    raw = os.environ.get(_TRUSTED_EDGE_TLS_ENV, "").strip().lower()
    if raw in {"", "0", "false"}:
        return False
    if raw in {"1", "true"}:
        return True
    raise RuntimeError("HOSTED_RUNTIME_TRUSTED_EDGE_TLS_FLAG_INVALID")


def _optional_candidate_hostname() -> str | None:
    raw = os.environ.get(_CANDIDATE_HOSTNAME_ENV, "").strip()
    if not raw:
        return None
    return _hostname(raw)


def _open_runtime_database(database_dsn: str, runtime_role: str) -> ConnectionLike:
    raw_connection = connect_prepared_timeweb_postgres(
        database_dsn,
        failure_prefix="HOSTED_RUNTIME_DATABASE",
        connect_timeout=_DATABASE_CONNECT_TIMEOUT_SECONDS,
    )
    _configure_long_lived_web_connection(raw_connection)
    probe_hosted_runtime_database(
        raw_connection,
        expected_runtime_role=runtime_role,
    )
    return raw_connection


def create_app() -> FastAPI:
    """Create the provider-neutral Timeweb-targeted V10 Web/API runtime."""

    if os.environ.get(_RUNTIME_ENABLED_ENV, "").strip() != "1":
        raise RuntimeError("HOSTED_RUNTIME_NOT_ENABLED")
    hostname = _hostname(_required_env(_HOSTNAME_ENV))
    release_sha = _release_sha(_required_env(_RELEASE_SHA_ENV))
    runtime_role = validate_hosted_runtime_role(_required_env(_RUNTIME_ROLE_ENV))
    database_dsn = prepare_timeweb_postgres_tls(_required_env(_DSN_ENV))
    candidate_hostname = _optional_candidate_hostname()
    candidate_hosts = () if candidate_hostname is None else (candidate_hostname,)
    raw_connection = _open_runtime_database(database_dsn, runtime_role)
    connection = _BoundedWebConnectionPool(
        raw_connection,
        connect=lambda: _open_runtime_database(database_dsn, runtime_role),
        max_size=_DATABASE_POOL_MAX_SIZE,
        acquire_timeout_seconds=_DATABASE_POOL_ACQUIRE_TIMEOUT_SECONDS,
    )
    sessions = PostgresWebSessionRegistryV1(
        connection,
        policy=HOSTED_SESSION_POLICY,
    )
    provider_auth = build_telegram_provider_auth(
        connection=connection,
        sessions=sessions,
        canonical_origin=f"https://{hostname}",
    )
    return create_hosted_app(
        HostedRuntimeServicesV1(
            sessions=sessions,
            database_probe=lambda: probe_hosted_runtime_database(
                connection,
                expected_runtime_role=runtime_role,
            ),
            hostname=hostname,
            release_sha=release_sha,
            provider_auth=provider_auth,
            synthetic_preview=False,
            release_label="v10-timeweb-source-runtime",
            git_sha_source=_RELEASE_SHA_ENV,
            last_deploy_source="TIMEWEB_APP_PLATFORM",
            web_artifact_source="GITHUB_SOURCE_BUILD",
        ),
        additional_hosts=("localhost", *candidate_hosts),
        trusted_edge_tls_terminated=_trusted_edge_tls_terminated(),
        allow_insecure_loopback_livez=True,
        provider_start_paths=frozenset({TELEGRAM_START_PATH}),
        server_mutation_paths=frozenset(),
        provider_route_installer=install_telegram_auth_routes_v1,
    )
