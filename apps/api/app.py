from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
from typing import Any, Iterator

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from t_tech.invest import Client

from omni_cio.persistence.migration import apply_migrations, connect_postgres
from omni_cio.web.api_v1 import WebApiServicesV1, create_web_api
from omni_cio.web.broker_vault_v1 import ReadBrokerConnectionVaultV1
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


def _private_acceptance_enabled() -> bool:
    return os.environ.get("OMNI_V10_WEB_PRIVATE_ACCEPTANCE", "").strip() == "1"


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
    """Create the local/private WP17 app without changing the protected app:app gateway."""
    connection = connect_postgres("")
    apply_migrations(connection)
    sessions = PostgresWebSessionRegistryV1(connection)
    broker_repository = PostgresBrokerConnectionRepositoryV1(connection)
    provisioning = BrokerProvisioningServiceV1(
        registry=BrokerProvisioningRegistryV1(),
        repository=broker_repository,
        vault=ReadBrokerConnectionVaultV1(),
        client_factory_builder=_client_factory_builder,
    )
    app = create_web_api(
        WebApiServicesV1(
            sessions=sessions,
            broker_repository=broker_repository,
            provisioning=provisioning,
            private_test_identity_enabled=_private_acceptance_enabled(),
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
