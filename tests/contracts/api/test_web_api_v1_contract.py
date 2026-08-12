from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from omni_cio.contracts.v1.domain import OWNER_TENANT_ID
from omni_cio.web.api_v1 import create_web_api
from omni_cio.web.persistence_v1 import PostgresBrokerConnectionRepositoryV1
from omni_cio.web.session_v1 import SessionRegistryV1


class _BrokerRepository:
    def list_read_connections(self, *, tenant_id: str) -> tuple[object, ...]:
        del tenant_id
        return ()


class _Provisioning:
    pass


class _Services:
    sessions = SessionRegistryV1()
    broker_repository = _BrokerRepository()
    provisioning = _Provisioning()
    providers = ()
    health_provider = staticmethod(lambda: None)
    now = staticmethod(__import__("datetime").datetime.now)
    private_test_identity_enabled = False
    secure_cookie = False


class _RowsCursor:
    rowcount = 0

    def fetchall(self) -> list[tuple[Any, ...]]:
        return []


class _CaptureConnection:
    def __init__(self) -> None:
        self.query = ""
        self.params: tuple[Any, ...] | None = None

    def execute(
        self,
        query: Any,
        params: tuple[Any, ...] | None = None,
        *,
        prepare: bool | None = None,
    ) -> _RowsCursor:
        del prepare
        self.query = str(query)
        self.params = params
        return _RowsCursor()


def test_web_api_schema_surface_is_exact_and_private_by_default() -> None:
    app = create_web_api(_Services())  # type: ignore[arg-type]
    route_methods = {
        (route.path, tuple(sorted(route.methods or ())))
        for route in app.routes
        if route.path.startswith("/api/v10/web/")
    }
    assert route_methods == {
        ("/api/v10/web/session", ("GET",)),
        ("/api/v10/web/auth/providers", ("GET",)),
        ("/api/v10/web/auth/{provider}/start", ("GET",)),
        ("/api/v10/web/private-test-login/status", ("GET",)),
        ("/api/v10/web/private-test-login", ("POST",)),
        ("/api/v10/web/session/logout", ("POST",)),
        ("/api/v10/web/session/revoke-all", ("POST",)),
        ("/api/v10/web/health", ("GET",)),
        ("/api/v10/web/broker-connections", ("GET",)),
        ("/api/v10/web/broker-connections/preview", ("POST",)),
        ("/api/v10/web/broker-connections/commit", ("POST",)),
        ("/api/v10/web/broker-connections/{connection_id}/replace", ("POST",)),
        ("/api/v10/web/broker-connections/{connection_id}", ("DELETE",)),
        ("/api/v10/web/wp15-live-acceptance/status", ("GET",)),
        ("/api/v10/web/wp15-live-acceptance/start", ("POST",)),
        ("/api/v10/web/wp15-live-acceptance/confirm", ("POST",)),
        ("/api/v10/web/wp15-live-acceptance/cancel", ("POST",)),
    }
    assert app.docs_url is None
    assert app.redoc_url is None
    assert app.openapi_url is None


def test_api_transport_has_no_public_bind_or_broker_write_surface() -> None:
    root = Path(__file__).resolve().parents[3]
    api_source = (root / "apps" / "api" / "app.py").read_text(encoding="utf-8")
    web_source = (root / "omni_cio" / "web" / "api_v1.py").read_text(encoding="utf-8")
    combined = f"{api_source}\n{web_source}".lower()

    for forbidden in (
        "0.0.0.0",
        "broker_trading",
        "stop_orders",
        ".orders",
        "withdraw",
        "currency_transfer",
        "pay_in",
        "cloudflared",
        "tailscale funnel",
    ):
        assert forbidden not in combined

    assert "create_local_private_app" in api_source
    assert "app = create_local_private_app" not in api_source


def test_local_private_app_uses_explicit_postgres_transactions() -> None:
    root = Path(__file__).resolve().parents[3]
    api_source = (root / "apps" / "api" / "app.py").read_text(encoding="utf-8")

    assert "WEB_RUNTIME_POSTGRES_AUTOCOMMIT_REQUIRED" in api_source
    assert "connection.autocommit = True" in api_source

    raw_open = api_source.index('raw_connection = connect_postgres("")')
    configure = api_source.index("_configure_long_lived_web_connection(raw_connection)")
    verify = api_source.index("_verify_live_database(raw_connection)")
    serialize = api_source.index("_SerializedWebConnection(raw_connection)")
    sessions = api_source.index("PostgresWebSessionRegistryV1(connection)")
    brokers = api_source.index("PostgresBrokerConnectionRepositoryV1(connection)")

    assert raw_open < configure < verify < serialize < sessions < brokers
    assert "threading.RLock()" in api_source
    assert "WEB_RUNTIME_POSTGRES_TRANSACTION_UNAVAILABLE" in api_source


def test_wp15_live_bootstrap_seeds_owner_identity_before_runtime() -> None:
    root = Path(__file__).resolve().parents[3]
    bootstrap = (
        root / "infrastructure" / "windows" / "bootstrap_wp15_live_database.py"
    ).read_text(encoding="utf-8")
    provisioner = (
        root / "infrastructure" / "windows" / "provision_wp15_live_web_acceptance.ps1"
    ).read_text(encoding="utf-8")
    contract = json.loads(
        (
            root
            / "docs"
            / "architecture"
            / "V10_WP15_LIVE_WEB_ACCEPTANCE_CONTRACT.json"
        ).read_text(encoding="utf-8")
    )

    assert "CanonicalDomainCatalogV1" in bootstrap
    assert "PostgresDomainRepository" in bootstrap
    assert "WP15_LIVE_OWNER_TENANT_INTEGRITY_INVALID" in bootstrap
    assert "WP15_LIVE_OWNER_USER_INTEGRITY_INVALID" in bootstrap
    assert "WP15_LIVE_OWNER_BOOTSTRAP_AUTOCOMMIT_REQUIRED" in bootstrap
    assert "connection.autocommit = True" in bootstrap
    assert bootstrap.index(
        "_configure_bootstrap_connection(connection)"
    ) < bootstrap.index("apply_migrations(connection)")
    assert bootstrap.index("apply_migrations(connection)") < bootstrap.index(
        "_ensure_owner_identity(connection)"
    )

    postgres = contract["postgresql"]
    assert postgres["owner_identity_seed_before_runtime"] is True
    assert postgres["owner_identity_seed_authority"] == "TEMPORARY_OWNER_ADMIN_ONLY"
    assert postgres["owner_bootstrap_connection_autocommit"] is True
    assert postgres["runtime_owner_identity_write_authority"] is False
    assert postgres["shared_connection_request_serialization"] is True
    assert "omni_cio_v10.tenants" not in provisioner
    assert "omni_cio_v10.users" not in provisioner


def test_settings_listing_excludes_revoked_broker_connections() -> None:
    connection = _CaptureConnection()
    repository = PostgresBrokerConnectionRepositoryV1(
        connection  # type: ignore[arg-type]
    )

    assert repository.list_read_connections(tenant_id=OWNER_TENANT_ID) == ()
    assert "c.state <> 'REVOKED'" in connection.query
    assert connection.params == (OWNER_TENANT_ID,)

    root = Path(__file__).resolve().parents[3]
    contract = json.loads(
        (
            root
            / "docs"
            / "architecture"
            / "V10_WP15_LIVE_WEB_ACCEPTANCE_CONTRACT.json"
        ).read_text(encoding="utf-8")
    )
    assert contract["broker"]["revoked_connections_exposed_to_active_settings"] is False
