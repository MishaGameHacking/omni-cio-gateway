from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from apps.api.app import (
    WEB_DIST,
    _SerializedWebConnection,
    _client_factory_builder,
    _configure_long_lived_web_connection,
    _dashboard_adapter_builder,
)
from omni_cio.persistence.migration import ConnectionLike, apply_migrations, connect_postgres
from omni_cio.web.api_v1 import SESSION_COOKIE, WebApiServicesV1, create_web_api
from omni_cio.web.broker_vault_v1 import ReadBrokerConnectionVaultV1
from omni_cio.web.decision_plan_v1 import (
    DecisionPlanReadServiceV1,
    install_decision_plan_routes,
)
from omni_cio.web.persistence_v1 import (
    PostgresBrokerConnectionRepositoryV1,
    PostgresWebSessionRegistryV1,
)
from omni_cio.web.portfolio_dashboard_v1 import (
    PortfolioDashboardServiceV1,
    install_portfolio_dashboard_routes,
)
from omni_cio.web.provisioning_v1 import (
    BrokerProvisioningRegistryV1,
    BrokerProvisioningServiceV1,
)
from omni_cio.web.remote_security_v1 import (
    PrivateRemoteSecurityMiddlewareV1,
    PrivateRemoteSecurityPolicyV1,
    install_private_remote_session_routes,
)
from omni_cio.web.research_dossiers_v1 import (
    ResearchDossierReadServiceV1,
    install_research_dossier_routes,
)
from omni_cio.web.system_admin_v1 import (
    SystemAdminReadServiceV1,
    install_system_admin_routes,
)
from omni_cio.web.watchtower_incidents_v1 import (
    WatchtowerIncidentReadServiceV1,
    install_watchtower_incident_routes,
)


def _required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name}_REQUIRED")
    return value


def _forbid_enabled_environment(name: str) -> None:
    value = os.environ.get(name, "").strip().casefold()
    if value in {"1", "true", "yes", "on"}:
        raise RuntimeError(f"{name}_MUST_REMAIN_DISABLED")


def create_private_remote_app() -> FastAPI:
    """Create the WP22A Tailscale-Serve-only Personal Web composition.

    This is the same source-controlled Web application and data/control plane as
    the accepted local/private app. It changes only the outer transport/session
    security composition for private tailnet reachability. The Uvicorn launcher
    is required to keep this factory bound to 127.0.0.1.
    """

    _forbid_enabled_environment("OMNI_V10_WEB_PRIVATE_ACCEPTANCE")
    _forbid_enabled_environment("OMNI_V10_WP15_LIVE_ACCEPTANCE")
    _forbid_enabled_environment("OMNI_V10_WP22A_PUBLIC_INGRESS")
    _forbid_enabled_environment("PUBLIC_MULTI_USER_ENABLED")
    _forbid_enabled_environment("REAL_TRADING_ENABLED")

    policy = PrivateRemoteSecurityPolicyV1(
        expected_host=_required_environment("OMNI_V10_TAILSCALE_HOST"),
        owner_login_sha256=_required_environment(
            "OMNI_V10_TAILSCALE_OWNER_LOGIN_SHA256"
        ),
    )

    raw_connection = connect_postgres("")
    _configure_long_lived_web_connection(raw_connection)
    apply_migrations(raw_connection)
    connection: ConnectionLike = _SerializedWebConnection(raw_connection)
    sessions = PostgresWebSessionRegistryV1(connection)
    broker_repository = PostgresBrokerConnectionRepositoryV1(connection)
    vault = ReadBrokerConnectionVaultV1()
    provisioning = BrokerProvisioningServiceV1(
        registry=BrokerProvisioningRegistryV1(),
        repository=broker_repository,
        vault=vault,
        client_factory_builder=_client_factory_builder,
    )

    app = create_web_api(
        WebApiServicesV1(
            sessions=sessions,
            broker_repository=broker_repository,
            provisioning=provisioning,
            live_acceptance=None,
            private_test_identity_enabled=False,
            secure_cookie=True,
        )
    )
    install_private_remote_session_routes(
        app,
        sessions=sessions,
        session_cookie_name=SESSION_COOKIE,
    )
    install_portfolio_dashboard_routes(
        app,
        sessions=sessions,
        service=PortfolioDashboardServiceV1(
            repository=broker_repository,
            vault=vault,
            adapter_builder=_dashboard_adapter_builder,
        ),
    )
    install_watchtower_incident_routes(
        app,
        sessions=sessions,
        service=WatchtowerIncidentReadServiceV1(connection),
    )
    install_research_dossier_routes(
        app,
        sessions=sessions,
        service=ResearchDossierReadServiceV1(connection),
    )
    install_decision_plan_routes(
        app,
        sessions=sessions,
        service=DecisionPlanReadServiceV1(connection),
    )
    install_system_admin_routes(
        app,
        sessions=sessions,
        service=SystemAdminReadServiceV1(
            connection,
            broker_repository=broker_repository,
            repo_root=Path(__file__).resolve().parents[2],
            web_dist=WEB_DIST,
        ),
    )

    if not WEB_DIST.is_dir() or not (WEB_DIST / "index.html").is_file():
        raise RuntimeError("WP17_WEB_BUILD_MISSING")
    assets = WEB_DIST / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="web-assets")

    @app.get("/{path:path}", include_in_schema=False)
    def web_fallback(path: str) -> FileResponse:
        del path
        return FileResponse(WEB_DIST / "index.html")

    app.add_middleware(
        PrivateRemoteSecurityMiddlewareV1,
        policy=policy,
        session_cookie_name=SESSION_COOKIE,
    )
    return app
