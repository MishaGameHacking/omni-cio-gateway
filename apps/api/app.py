from __future__ import annotations

from collections import namedtuple
from collections.abc import Sequence
from contextlib import contextmanager
import math
import os
from pathlib import Path
import re
import threading
from typing import Any, Iterator

from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import grpc
from t_tech.invest import Client

from omni_cio.adapters.tinvest_connection_v1 import TInvestConnectionMarketReadAdapter
from omni_cio.persistence.migration import (
    ConnectionLike,
    CursorLike,
    TransactionContext,
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
from omni_cio.web.portfolio_dashboard_v1 import (
    PortfolioDashboardServiceV1,
    install_portfolio_dashboard_routes,
)
from omni_cio.web.provisioning_v1 import (
    BrokerProvisioningRegistryV1,
    BrokerProvisioningServiceV1,
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


class _SerializedCursor:
    def __init__(self, cursor: Any, lock: Any) -> None:
        self._cursor = cursor
        self._lock = lock
        self.rowcount = int(cursor.rowcount)

    def fetchone(self) -> Sequence[Any] | None:
        with self._lock:
            return self._cursor.fetchone()

    def fetchall(self) -> list[Sequence[Any]]:
        with self._lock:
            return list(self._cursor.fetchall())


class _SerializedTransaction:
    def __init__(self, connection: Any, lock: Any) -> None:
        self._connection = connection
        self._lock = lock
        self._transaction: Any | None = None

    def __enter__(self) -> Any:
        self._lock.acquire()
        try:
            self._transaction = self._connection.transaction()
            return self._transaction.__enter__()
        except BaseException:
            self._transaction = None
            self._lock.release()
            raise

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool | None:
        transaction = self._transaction
        if transaction is None:
            raise RuntimeError("WEB_RUNTIME_POSTGRES_TRANSACTION_UNAVAILABLE")
        try:
            return transaction.__exit__(exc_type, exc, traceback)
        finally:
            self._transaction = None
            self._lock.release()


class _SerializedWebConnection:
    """Preserve request transaction boundaries on one local Web PostgreSQL session."""

    def __init__(self, connection: Any) -> None:
        self._connection = connection
        self._lock = threading.RLock()

    def execute(
        self,
        query: Any,
        params: Sequence[Any] | None = None,
        *,
        prepare: bool | None = None,
    ) -> CursorLike:
        with self._lock:
            cursor = self._connection.execute(query, params, prepare=prepare)
            return _SerializedCursor(cursor, self._lock)

    def transaction(self) -> TransactionContext:
        return _SerializedTransaction(self._connection, self._lock)


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


def _configure_long_lived_web_connection(connection: Any) -> None:
    """Keep request transactions explicit instead of nesting under startup SELECTs."""
    try:
        connection.autocommit = True
    except Exception as exc:
        raise RuntimeError("WEB_RUNTIME_POSTGRES_AUTOCOMMIT_REQUIRED") from exc
    if getattr(connection, "autocommit", None) is not True:
        raise RuntimeError("WEB_RUNTIME_POSTGRES_AUTOCOMMIT_REQUIRED")


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


def create_local_private_app() -> FastAPI:
    """Create the local/private Web app without changing the protected app:app gateway."""
    private_acceptance = _private_acceptance_enabled()
    live_acceptance_enabled = _wp15_live_acceptance_enabled()
    if live_acceptance_enabled and not private_acceptance:
        raise RuntimeError("WP15_LIVE_REQUIRES_PRIVATE_ACCEPTANCE")

    raw_connection = connect_postgres("")
    _configure_long_lived_web_connection(raw_connection)
    if live_acceptance_enabled:
        _verify_live_database(raw_connection)
    else:
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
