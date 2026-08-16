from __future__ import annotations

import os

from fastapi import FastAPI

from apps.api.app import (
    _SerializedWebConnection,
    _configure_long_lived_web_connection,
    create_local_private_app,
)
from omni_cio.persistence.migration import connect_postgres
from omni_cio.web.external_access_v1 import (
    ExternalAccessPolicyV1,
    install_private_remote_access_v1,
)
from omni_cio.web.persistence_v1 import PostgresWebSessionRegistryV1


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name}_REQUIRED")
    return value


def create_private_remote_app() -> FastAPI:
    """Wrap the accepted single Web App with the WP22A clientless boundary.

    Cloudflare Access remains an outer OWNER-private gate. It does not enable
    public multi-user activation, broker write authority, or a second Web App.
    The local origin stays on loopback and uses the existing PostgreSQL-backed
    server-side session registry.
    """
    if os.environ.get("OMNI_V10_WEB_EXTERNAL_ACCESS", "").strip() != "1":
        raise RuntimeError("WP22A_EXTERNAL_ACCESS_NOT_ENABLED")

    policy = ExternalAccessPolicyV1(
        canonical_host=_required_env("OMNI_V10_WEB_EXTERNAL_HOST"),
    )
    app = create_local_private_app()

    raw_connection = connect_postgres("")
    _configure_long_lived_web_connection(raw_connection)
    sessions = PostgresWebSessionRegistryV1(_SerializedWebConnection(raw_connection))
    install_private_remote_access_v1(app, sessions=sessions, policy=policy)
    return app
