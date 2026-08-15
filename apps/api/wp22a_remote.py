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
    REMOTE_SESSION_POLICY,
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
    """Wrap the accepted local Web app with the WP22A tailnet-only security gate.

    This is still the same source-controlled Web App. It intentionally does not
    enable public ingress or public multi-user activation.
    """
    if os.environ.get("OMNI_V10_WEB_PRIVATE_REMOTE", "").strip() != "1":
        raise RuntimeError("WP22A_PRIVATE_REMOTE_NOT_ENABLED")

    policy = ExternalAccessPolicyV1(
        canonical_host=_required_env("OMNI_V10_WEB_EXTERNAL_HOST"),
        owner_login_sha256=_required_env("OMNI_V10_TAILSCALE_OWNER_LOGIN_SHA256"),
    )
    app = create_local_private_app(
        session_policy=REMOTE_SESSION_POLICY,
        verify_existing_database=True,
    )

    raw_connection = connect_postgres("")
    _configure_long_lived_web_connection(raw_connection)
    sessions = PostgresWebSessionRegistryV1(
        _SerializedWebConnection(raw_connection),
        policy=REMOTE_SESSION_POLICY,
    )
    install_private_remote_access_v1(app, sessions=sessions, policy=policy)
    return app
