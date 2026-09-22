from __future__ import annotations

from datetime import timedelta
import os

from fastapi import FastAPI

from apps.api.app import _SerializedWebConnection, _configure_long_lived_web_connection
from apps.api.hosted_preview import (
    HostedPreviewServicesV1,
    _hostname,
    _probe_runtime_database,
    _release_sha,
    _required_env,
    create_hosted_preview_app,
)
from apps.api.telegram_auth import build_telegram_provider_auth
from omni_cio.persistence.migration import connect_postgres
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
HOSTED_SESSION_POLICY = SessionPolicyV1(
    idle_lifetime=timedelta(hours=2),
    absolute_lifetime=timedelta(hours=24),
)


def create_app() -> FastAPI:
    """Create the provider-neutral Timeweb-targeted V10 Web/API runtime."""

    if os.environ.get(_RUNTIME_ENABLED_ENV, "").strip() != "1":
        raise RuntimeError("HOSTED_RUNTIME_NOT_ENABLED")
    hostname = _hostname(_required_env(_HOSTNAME_ENV))
    release_sha = _release_sha(_required_env(_RELEASE_SHA_ENV))
    raw_connection = connect_postgres(_required_env(_DSN_ENV))
    _configure_long_lived_web_connection(raw_connection)
    connection = _SerializedWebConnection(raw_connection)
    _probe_runtime_database(connection)
    sessions = PostgresWebSessionRegistryV1(
        connection,
        policy=HOSTED_SESSION_POLICY,
    )
    provider_auth = build_telegram_provider_auth(
        connection=connection,
        sessions=sessions,
        canonical_origin=f"https://{hostname}",
    )
    return create_hosted_preview_app(
        HostedPreviewServicesV1(
            sessions=sessions,
            database_probe=lambda: _probe_runtime_database(connection),
            hostname=hostname,
            release_sha=release_sha,
            provider_auth=provider_auth,
            synthetic_preview=False,
            release_label="v10-timeweb-source-runtime",
            git_sha_source=_RELEASE_SHA_ENV,
            last_deploy_source="TIMEWEB_APP_PLATFORM",
            web_artifact_source="GITHUB_SOURCE_BUILD",
        ),
        additional_hosts=("localhost",),
        trusted_edge_tls_terminated=True,
        trusted_edge_hostname_suffix=None,
        provider_start_paths=frozenset({TELEGRAM_START_PATH}),
        server_mutation_paths=frozenset(),
        provider_route_installer=install_telegram_auth_routes_v1,
    )
