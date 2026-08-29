from __future__ import annotations

import os
import re

from apps.api.app import _SerializedWebConnection, _configure_long_lived_web_connection
from apps.api.hosted_preview import (
    PREVIEW_SESSION_POLICY,
    HostedPreviewServicesV1,
    _hostname,
    _probe_hosted_preview_database,
    _release_sha,
    create_hosted_preview_app,
)
from omni_cio.persistence.migration import connect_postgres
from omni_cio.web.persistence_v1 import PostgresWebSessionRegistryV1


_INTERNAL_HOST = "omni-cio.internal"
_DSN_SECRET = "OMNI_V10_POSTGRES_DSN"
_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name}_REQUIRED")
    return value


def create_app():
    if os.environ.get("OMNI_V10_CLOUDFLARE_RUNTIME", "").strip() != "1":
        raise RuntimeError("CLOUDFLARE_RUNTIME_NOT_ENABLED")
    hostname = _hostname(_required_env("OMNI_V10_INTERNAL_HOSTNAME"))
    if hostname != _INTERNAL_HOST:
        raise RuntimeError("CLOUDFLARE_RUNTIME_INTERNAL_HOST_INVALID")
    release_sha = _release_sha(_required_env("OMNI_V10_RELEASE_SHA"))
    if _SHA_PATTERN.fullmatch(release_sha) is None:
        raise RuntimeError("CLOUDFLARE_RUNTIME_RELEASE_SHA_INVALID")

    raw_connection = connect_postgres(_required_env(_DSN_SECRET))
    _configure_long_lived_web_connection(raw_connection)
    connection = _SerializedWebConnection(raw_connection)
    _probe_hosted_preview_database(connection)
    sessions = PostgresWebSessionRegistryV1(
        connection,
        policy=PREVIEW_SESSION_POLICY,
    )

    # Product providers deliberately remain disabled here. CF-D may only compose
    # Telegram/VK after real provider registration, canonical public origin, secret
    # custody and live acceptance evidence exist. The public Cloudflare shell must
    # not turn infrastructure migration into an authentication bypass.
    return create_hosted_preview_app(
        HostedPreviewServicesV1(
            sessions=sessions,
            database_probe=lambda: _probe_hosted_preview_database(connection),
            hostname=hostname,
            release_sha=release_sha,
            provider_auth=None,
        ),
        trusted_edge_tls_terminated=False,
    )
