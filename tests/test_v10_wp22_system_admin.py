from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from omni_cio.contracts.v1.domain import OWNER_TENANT_ID
from omni_cio.web import system_admin_v1
from omni_cio.web.system_admin_v1 import (
    SystemAdminReadServiceV1,
    install_system_admin_routes,
)


NOW = datetime(2026, 8, 14, 9, 30, tzinfo=timezone.utc)


class _Cursor:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self._rows = rows
        self.rowcount = len(rows)

    def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self._rows)

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._rows[0] if self._rows else None


class _Connection:
    def __init__(self, *, jobs: list[tuple[Any, ...]] | None = None) -> None:
        self.jobs = jobs or []
        self.tenant_params: list[str] = []

    def execute(
        self,
        query: Any,
        params: Any = None,
        *,
        prepare: bool | None = None,
    ) -> _Cursor:
        del prepare
        sql = str(query)
        values = tuple(params or ())
        if values:
            self.tenant_params.append(str(values[0]))
        if "job_type = 'BACKUP'" in sql:
            return _Cursor([(NOW,)])
        if "job_type = %s" in sql:
            return _Cursor([("SUCCEEDED", None, NOW)])
        if "error_class IS NOT NULL" in sql:
            rows = [
                (row[0], row[1], row[4], row[5])
                for row in self.jobs
                if row[4] is not None
            ]
            return _Cursor(rows[: int(values[1])])
        if "FROM omni_cio_v10.jobs WHERE tenant_id" in sql:
            return _Cursor(self.jobs[: int(values[1])])
        raise AssertionError(f"unexpected query: {sql}")

    def transaction(self) -> Any:
        raise AssertionError("transaction is not expected in WP22 read service test")


class _BrokerRepository:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.tenant_requests: list[str] = []

    def list_read_connections(self, *, tenant_id: str) -> tuple[Any, ...]:
        self.tenant_requests.append(tenant_id)
        if self.fail:
            raise RuntimeError("SHOULD_NEVER_LEAK_BROKER_ERROR")
        return (SimpleNamespace(state="ACTIVE"),)


class _CommandResult:
    returncode = 0
    stdout = "a" * 40 + "\n"


def _runner(*args: Any, **kwargs: Any) -> _CommandResult:
    del args, kwargs
    return _CommandResult()


def _service(
    monkeypatch: Any,
    tmp_path: Path,
    *,
    connection: _Connection,
    broker_repository: _BrokerRepository,
    free_gib: int = 80,
) -> SystemAdminReadServiceV1:
    monkeypatch.delenv("REAL_TRADING_ENABLED", raising=False)
    monkeypatch.delenv("WATCHTOWER_ENABLED", raising=False)
    monkeypatch.delenv("OMNI_V10_LAST_DEPLOY_AT", raising=False)
    web_dist = tmp_path / "apps" / "web" / "dist"
    web_dist.mkdir(parents=True)
    index = web_dist / "index.html"
    index.write_text("<!doctype html>", encoding="utf-8")
    monkeypatch.setattr(
        system_admin_v1,
        "discover_migrations",
        lambda: (SimpleNamespace(version=3, sha256="f" * 64),),
    )
    monkeypatch.setattr(
        system_admin_v1,
        "current_migration_state",
        lambda connection: ((3, "f" * 64),),
    )
    monkeypatch.setattr(system_admin_v1.shutil, "which", lambda name: None)
    gib = 1024**3
    return SystemAdminReadServiceV1(
        connection,
        broker_repository=broker_repository,  # type: ignore[arg-type]
        repo_root=tmp_path,
        web_dist=web_dist,
        clock=lambda: NOW,
        disk_usage=lambda path: SimpleNamespace(
            total=100 * gib,
            used=(100 - free_gib) * gib,
            free=free_gib * gib,
        ),
        command_runner=_runner,
    )


def test_wp22_status_is_bounded_tenant_scoped_and_secret_free(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    jobs = [
        (
            "WATCHTOWER" if index % 2 == 0 else "HEALTH",
            "FAILED_PERMANENT" if index < 10 else "SUCCEEDED",
            1,
            3,
            "PERMANENT" if index < 10 else None,
            NOW,
        )
        for index in range(20)
    ]
    connection = _Connection(jobs=jobs)
    broker = _BrokerRepository()
    service = _service(
        monkeypatch,
        tmp_path,
        connection=connection,
        broker_repository=broker,
    )

    payload = service.read(tenant_id=OWNER_TENANT_ID)

    assert payload["schema_version"] == "1.0.0"
    assert payload["database"]["exact_migration_state"] is True
    assert payload["database"]["current_migration"] == "0003"
    assert payload["backup"]["rpo_minutes"] == 60
    assert payload["backup"]["rto_minutes"] == 240
    assert payload["release"]["last_deploy_at"] is None
    assert payload["release"]["last_deploy_source"] == "unavailable"
    assert payload["release"]["web_artifact_at"] is not None
    assert payload["safety"] == {
        "mode": "READ_ONLY_DIAGNOSTIC",
        "real_execution_enabled": False,
        "trading_methods": False,
        "broker_write_authority": False,
        "public_ingress": False,
        "watchtower_enabled": False,
    }
    assert len(payload["recent_jobs"]) == 12
    assert len(payload["recent_errors"]) == 8
    assert broker.tenant_requests == [OWNER_TENANT_ID]
    assert OWNER_TENANT_ID in connection.tenant_params

    services = {item["id"]: item for item in payload["services"]}
    assert services["telegram"]["availability"] == "LOCKED_FUTURE_WP"
    assert services["ai"]["availability"] == "LOCKED_FUTURE_WP"
    assert services["t_invest"]["state"] == "READY"
    assert payload["state"] == "PARTIAL"

    serialized = repr(payload).lower()
    assert "token" not in serialized
    assert "password" not in serialized
    assert "authorization" not in serialized
    assert "broker-account" not in serialized


def test_wp22_deploy_time_requires_explicit_trusted_observation(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    service = _service(
        monkeypatch,
        tmp_path,
        connection=_Connection(),
        broker_repository=_BrokerRepository(),
    )
    monkeypatch.setenv("OMNI_V10_LAST_DEPLOY_AT", "2026-08-14T09:20:00Z")

    payload = service.read(tenant_id=OWNER_TENANT_ID)

    assert payload["release"]["last_deploy_at"] == "2026-08-14T09:20:00+00:00"
    assert payload["release"]["last_deploy_source"] == "omni_v10_last_deploy_at"


def test_wp22_degraded_state_masks_internal_failures_and_blocks_low_disk(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    connection = _Connection()
    broker = _BrokerRepository(fail=True)
    service = _service(
        monkeypatch,
        tmp_path,
        connection=connection,
        broker_repository=broker,
        free_gib=5,
    )
    monkeypatch.setattr(
        system_admin_v1,
        "current_migration_state",
        lambda connection: ((2, "e" * 64),),
    )

    payload = service.read(tenant_id=OWNER_TENANT_ID)

    assert payload["state"] == "BLOCKED"
    assert payload["database"]["state"] == "BLOCKED"
    assert payload["resources"]["disk"]["state"] == "BLOCKED"
    tinvest = next(item for item in payload["services"] if item["id"] == "t_invest")
    assert tinvest["availability"] == "NOT_AVAILABLE"
    assert "SHOULD_NEVER_LEAK" not in repr(payload)


def test_wp22_real_trading_runtime_violation_is_visible_and_blocking(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    connection = _Connection()
    broker = _BrokerRepository()
    service = _service(
        monkeypatch,
        tmp_path,
        connection=connection,
        broker_repository=broker,
    )
    monkeypatch.setenv("REAL_TRADING_ENABLED", "true")

    payload = service.read(tenant_id=OWNER_TENANT_ID)

    assert payload["safety"]["real_execution_enabled"] is True
    assert payload["state"] == "BLOCKED"


class _Sessions:
    def __init__(self, authenticated: bool) -> None:
        self.authenticated = authenticated

    def resolve(self, token: str | None, *, now: datetime) -> Any:
        del token, now
        if not self.authenticated:
            return None
        return SimpleNamespace(tenant_id=OWNER_TENANT_ID)


class _StatusService:
    def __init__(self) -> None:
        self.tenants: list[str] = []

    def read(self, *, tenant_id: str) -> dict[str, Any]:
        self.tenants.append(tenant_id)
        return {"schema_version": "1.0.0", "state": "READY"}


def test_wp22_route_requires_server_side_session_and_is_no_store() -> None:
    denied = FastAPI()
    install_system_admin_routes(
        denied,
        sessions=_Sessions(False),  # type: ignore[arg-type]
        service=_StatusService(),  # type: ignore[arg-type]
        now=lambda: NOW,
    )
    assert TestClient(denied).get("/api/v10/web/system-status").status_code == 401

    allowed = FastAPI()
    service = _StatusService()
    install_system_admin_routes(
        allowed,
        sessions=_Sessions(True),  # type: ignore[arg-type]
        service=service,  # type: ignore[arg-type]
        now=lambda: NOW,
    )
    response = TestClient(allowed).get("/api/v10/web/system-status")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    assert service.tenants == [OWNER_TENANT_ID]
