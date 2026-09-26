from __future__ import annotations

from collections import namedtuple
from contextlib import contextmanager
import math
import os
from pathlib import Path
import re
from typing import Any, Iterator

from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import grpc
from t_tech.invest import Client

from apps.api.postgres_web_connection import (
    _SerializedWebConnection,
    _configure_long_lived_web_connection,
)
from omni_cio.adapters.tinvest_connection_v1 import TInvestConnectionMarketReadAdapter
from omni_cio.persistence.migration import (
    ConnectionLike,
    apply_migrations,
    connect_postgres,
    current_migration_state,
    discover_migrations,
    require_postgres_18,
)
from omni_cio.web.api_v1 import WebApiServicesV1, create_web_api
from omni_cio.web.broker_vault_v1 import ReadBrokerConnectionVaultV1
from omni_cio.web.decision_plan_v1 import (
    DecisionPlanReadServiceV1,
    install_decision_plan_routes,
)
from omni_cio.web.live_acceptance_v1 import (
    BrokerLiveAcceptanceServiceV1,
    PendingLiveAcceptanceEvidenceWriterV1,
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
from omni_cio.web.research_dossiers_v1 import (
    ResearchDossierReadServiceV1,
    install_research_dossier_routes,
)
from omni_cio.web.session_v1 import SessionPolicyV1
from omni_cio.web.system_admin_v1 import (
    SystemAdminReadServiceV1,
    install_system_admin_routes,
)
from omni_cio.web.watchtower_incidents_v1 import (
    WatchtowerIncidentReadServiceV1,
    install_watchtower_incident_routes,
)


WEB_ROOT = Path(__file__).resolve().parents[1] / "web"
WEB_DIST = WEB_ROOT / "dist"
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_LOCAL_TRUSTED_HOSTS = ("127.0.0.1", "localhost")
_WP15_LIVE_RPC_TIMEOUT_SECONDS = 15.0
_WP18_READ_RPC_TIMEOUT_SECONDS = 15.0


class _ClientCallDetails(
    namedtuple(
        "_ClientCallDetailsBase",
        (
            "method",
            "timeout",
            "metadata",
            "credentials",
            "wait_for_ready",
            "compression",
        ),
    ),
    grpc.ClientCallDetails,
):
    __slots__ = ()


class _UnaryUnaryDeadlineInterceptor(grpc.UnaryUnaryClientInterceptor):
    """Apply a finite upper bound without widening an existing shorter RPC deadline."""

    def __init__(self, timeout_seconds: float) -> None:
        value = float(timeout_seconds)
        if not math.isfinite(value) or value <= 0:
            raise ValueError("RPC timeout must be finite and positive")
        self._timeout_seconds = value

    def intercept_unary_unary(
        self,
        continuation: Any,
        client_call_details: grpc.ClientCallDetails,
        request: Any,
    ) -> Any:
        existing_timeout = client_call_details.timeout
        effective_timeout = (
            self._timeout_seconds
            if existing_timeout is None
            else min(float(existing_timeout), self._timeout_seconds)
        )
        bounded_details = _ClientCallDetails(
            method=client_call_details.method,
            timeout=effective_timeout,
            metadata=client_call_details.metadata,
            credentials=client_call_details.credentials,
            wait_for_ready=getattr(client_call_details, "wait_for_ready", None),
            compression=getattr(client_call_details, "compression", None),
        )
        return continuation(bounded_details, request)


def _private_acceptance_enabled() -> bool:
    return os.environ.get("OMNI_V10_WEB_PRIVATE_ACCEPTANCE", "").strip() == "1"


def _wp15_live_acceptance_enabled() -> bool:
    return os.environ.get("OMNI_V10_WP15_LIVE_ACCEPTANCE", "").strip() == "1"


def _wp15_live_implementation_sha() -> str:
    value = os.environ.get("OMNI_V10_IMPLEMENTATION_SHA", "").strip().lower()
    if _GIT_SHA_RE.fullmatch(value) is None:
        raise RuntimeError("WP15_LIVE_IMPLEMENTATION_SHA_REQUIRED")
    return value


def _wp15_live_pending_evidence_path() -> Path:
    value = os.environ.get("OMNI_V10_WP15_LIVE_PENDING_EVIDENCE", "").strip()
    if not value:
        raise RuntimeError("WP15_LIVE_PENDING_EVIDENCE_PATH_REQUIRED")
    return Path(value)


def _verify_live_database(connection: Any) -> None:
    require_postgres_18(connection)
    expected = tuple((item.version, item.sha256) for item in discover_migrations())
    if current_migration_state(connection) != expected:
        raise RuntimeError("WP15_LIVE_DATABASE_MIGRATION_STATE_INVALID")


def _protect_local_hosts(app: FastAPI) -> None:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=list(_LOCAL_TRUSTED_HOSTS),
        www_redirect=False,
    )


def _client_factory_builder(
    token: str,
    *,
    rpc_timeout_seconds: float | None = None,
):
    interceptors = (
        [_UnaryUnaryDeadlineInterceptor(rpc_timeout_seconds)]
        if rpc_timeout_seconds is not None
        else None
    )

    @contextmanager
    def client_factory() -> Iterator[Any]:
        candidate = token
        try:
            if interceptors is None:
                context = Client(candidate)
            else:
                context = Client(candidate, interceptors=interceptors)
            with context as client:
                yield client
        finally:
            candidate = ""

    return client_factory


def _live_client_factory_builder(token: str):
    return _client_factory_builder(
        token,
        rpc_timeout_seconds=_WP15_LIVE_RPC_TIMEOUT_SECONDS,
    )


def _dashboard_adapter_builder(
    token: str,
    expected_account_fingerprint_sha256: str,
) -> TInvestConnectionMarketReadAdapter:
    return TInvestConnectionMarketReadAdapter(
        client_factory=_client_factory_builder(
            token,
            rpc_timeout_seconds=_WP18_READ_RPC_TIMEOUT_SECONDS,
        ),
        expected_account_fingerprint_sha256=expected_account_fingerprint_sha256,
    )


def create_local_private_app(
    *,
    session_policy: SessionPolicyV1 | None = None,
    verify_existing_database: bool = False,
) -> FastAPI:
    """Create the local/private Web app without changing the protected app:app gateway."""
    private_acceptance = _private_acceptance_enabled()
    live_acceptance_enabled = _wp15_live_acceptance_enabled()
    if live_acceptance_enabled and not private_acceptance:
        raise RuntimeError("WP15_LIVE_REQUIRES_PRIVATE_ACCEPTANCE")

    raw_connection = connect_postgres("")
    _configure_long_lived_web_connection(raw_connection)
    if live_acceptance_enabled or verify_existing_database:
        _verify_live_database(raw_connection)
    else:
        apply_migrations(raw_connection)
    connection: ConnectionLike = _SerializedWebConnection(raw_connection)
    if session_policy is None:
        sessions = PostgresWebSessionRegistryV1(connection)
    else:
        sessions = PostgresWebSessionRegistryV1(
            connection,
            policy=session_policy,
        )
    broker_repository = PostgresBrokerConnectionRepositoryV1(connection)
    vault = ReadBrokerConnectionVaultV1()
    provisioning = BrokerProvisioningServiceV1(
        registry=BrokerProvisioningRegistryV1(),
        repository=broker_repository,
        vault=vault,
        client_factory_builder=_client_factory_builder,
    )
    live_acceptance = None
    if live_acceptance_enabled:
        live_acceptance = BrokerLiveAcceptanceServiceV1(
            repository=broker_repository,
            vault=vault,
            client_factory_builder=_live_client_factory_builder,
            evidence_writer=PendingLiveAcceptanceEvidenceWriterV1(
                _wp15_live_pending_evidence_path()
            ),
            implementation_sha=_wp15_live_implementation_sha(),
        )
    app = create_web_api(
        WebApiServicesV1(
            sessions=sessions,
            broker_repository=broker_repository,
            provisioning=provisioning,
            live_acceptance=live_acceptance,
            private_test_identity_enabled=private_acceptance,
            secure_cookie=False,
        )
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
    _protect_local_hosts(app)

    if not WEB_DIST.is_dir() or not (WEB_DIST / "index.html").is_file():
        raise RuntimeError("WP17_WEB_BUILD_MISSING")
    assets = WEB_DIST / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="web-assets")

    @app.get("/{path:path}", include_in_schema=False)
    def web_fallback(path: str) -> FileResponse:
        del path
        return FileResponse(WEB_DIST / "index.html")

    return app
