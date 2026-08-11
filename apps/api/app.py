from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import re
from typing import Any, Iterator

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from t_tech.invest import Client

from omni_cio.persistence.migration import (
    apply_migrations,
    connect_postgres,
    current_migration_state,
    discover_migrations,
    require_postgres_18,
)
from omni_cio.web.api_v1 import WebApiServicesV1, create_web_api
from omni_cio.web.broker_vault_v1 import ReadBrokerConnectionVaultV1
from omni_cio.web.live_acceptance_v1 import (
    BrokerLiveAcceptanceServiceV1,
    PendingLiveAcceptanceEvidenceWriterV1,
)
from omni_cio.web.persistence_v1 import (
    PostgresBrokerConnectionRepositoryV1,
    PostgresWebSessionRegistryV1,
)
from omni_cio.web.provisioning_v1 import (
    BrokerProvisioningRegistryV1,
    BrokerProvisioningServiceV1,
)


WEB_ROOT = Path(__file__).resolve().parents[1] / "web"
WEB_DIST = WEB_ROOT / "dist"
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


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


def _client_factory_builder(token: str):
    @contextmanager
    def client_factory() -> Iterator[Any]:
        candidate = token
        try:
            with Client(candidate) as client:
                yield client
        finally:
            candidate = ""

    return client_factory


def create_local_private_app() -> FastAPI:
    """Create the local/private Web app without changing the protected app:app gateway."""
    private_acceptance = _private_acceptance_enabled()
    live_acceptance_enabled = _wp15_live_acceptance_enabled()
    if live_acceptance_enabled and not private_acceptance:
        raise RuntimeError("WP15_LIVE_REQUIRES_PRIVATE_ACCEPTANCE")

    connection = connect_postgres("")
    if live_acceptance_enabled:
        _verify_live_database(connection)
    else:
        apply_migrations(connection)
    sessions = PostgresWebSessionRegistryV1(connection)
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
            client_factory_builder=_client_factory_builder,
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
