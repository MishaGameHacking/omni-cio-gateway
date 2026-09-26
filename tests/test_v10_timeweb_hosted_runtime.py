from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
import pytest

import apps.api.hosted_runtime as hosted_runtime

from apps.api.hosted_app import (
    HostedRuntimeServicesV1,
    _system_status,
    create_hosted_app,
)
from apps.api.hosted_database_runtime import (
    probe_hosted_runtime_database,
    validate_hosted_runtime_role,
)
from apps.api.hosted_runtime import (
    HOSTED_SESSION_POLICY,
    _optional_candidate_hostname,
    _trusted_edge_tls_terminated,
)
from apps.api.postgres_web_connection import (
    _BoundedWebConnectionPool,
    _SerializedWebConnection,
)
from apps.api.telegram_auth import (
    TelegramAuthConfigurationError,
    build_telegram_provider_auth,
)
from omni_cio.persistence.migration import discover_migrations
from omni_cio.web.browser_security_v1 import BrowserCookiePolicyV1
from omni_cio.web.identity_v1 import (
    ORDINARY_LOGIN_PROVIDERS,
    IdentityProviderV1,
)
from omni_cio.web.telegram_auth_services_v1 import TelegramAuthRouteServicesV1
from omni_cio.web.session_v1 import SessionRegistryV1


HOSTNAME = "omnicio.ru"
RELEASE_SHA = "a" * 40


def _web_dist(tmp_path: Path) -> Path:
    web_dist = tmp_path / "dist"
    web_dist.mkdir(parents=True)
    (web_dist / "index.html").write_text(
        "<!doctype html><html><body>OMNI-CIO</body></html>",
        encoding="utf-8",
    )
    return web_dist


def _disabled_auth() -> TelegramAuthRouteServicesV1:
    return TelegramAuthRouteServicesV1(
        runtimes=(),
        authentication=None,
        cookies=BrowserCookiePolicyV1(csrf_binding_key=bytes([19]) * 32),
    )


class _Result:
    def __init__(
        self,
        *,
        one: tuple[object, ...] | None = None,
        rows: list[tuple[object, ...]] | None = None,
    ) -> None:
        self._one = one
        self._rows = [] if rows is None else rows
        self.rowcount = len(self._rows) if rows is not None else int(one is not None)

    def fetchone(self) -> tuple[object, ...] | None:
        return self._one

    def fetchall(self) -> list[tuple[object, ...]]:
        return list(self._rows)


class _RuntimeProbeConnection:
    def __init__(
        self,
        role: str,
        *,
        missing_relation: str | None = None,
        extra_relation_privilege: bool = False,
        policy_drift: bool = False,
        function_drift: bool = False,
        runtime_members: list[tuple[bool, bool, bool]] | None = None,
        column_privilege_drift: bool = False,
        missing_constraint: str | None = None,
    ) -> None:
        self._role = role
        self._missing_relation = missing_relation
        self._extra_relation_privilege = extra_relation_privilege
        self._policy_drift = policy_drift
        self._function_drift = function_drift
        self._runtime_members = [] if runtime_members is None else runtime_members
        self._column_privilege_drift = column_privilege_drift
        self._missing_constraint = missing_constraint

    def _role_record(self) -> _Result:
        return _Result(
            one=(
                self._role,
                True,
                False,
                False,
                False,
                False,
                False,
            )
        )

    def _role_members(self) -> _Result:
        return _Result(rows=[tuple(row) for row in self._runtime_members])

    def _relation_grants(self) -> _Result:
        rows = [
            ("broker_accounts", "INSERT", "NO"),
            ("broker_accounts", "SELECT", "NO"),
            ("broker_connection_accounts", "INSERT", "NO"),
            ("broker_connection_accounts", "SELECT", "NO"),
            ("broker_connections", "INSERT", "NO"),
            ("broker_connections", "SELECT", "NO"),
            ("broker_connections", "UPDATE", "NO"),
            ("external_identity_bindings", "INSERT", "NO"),
            ("external_identity_bindings", "SELECT", "NO"),
            ("provider_auth_transactions", "DELETE", "NO"),
            ("provider_auth_transactions", "INSERT", "NO"),
            ("provider_auth_transactions", "SELECT", "NO"),
            ("tenants", "INSERT", "NO"),
            ("users", "INSERT", "NO"),
            ("users", "SELECT", "NO"),
            ("web_sessions", "DELETE", "NO"),
            ("web_sessions", "INSERT", "NO"),
            ("web_sessions", "SELECT", "NO"),
            ("web_sessions", "UPDATE", "NO"),
        ]
        if self._extra_relation_privilege:
            rows.append(("tenants", "SELECT", "NO"))
        return _Result(rows=rows)

    def _required_relations(self) -> _Result:
        relations: list[object | None] = [
            "omni_cio_v10.tenants",
            "omni_cio_v10.users",
            "omni_cio_v10.external_identity_bindings",
            "omni_cio_v10.web_sessions",
            "omni_cio_v10.provider_auth_transactions",
        ]
        if self._missing_relation is not None:
            relations[relations.index(self._missing_relation)] = None
        return _Result(one=tuple(relations))

    def _security_constraints(self) -> _Result:
        rows = [
            ("users", "users_user_tenant_uq", "u", True),
            ("users", "users_one_account_per_tenant", "u", True),
            ("web_sessions", "web_sessions_pkey", "p", True),
            ("web_sessions", "web_session_token_sha256", "c", True),
            ("web_sessions", "web_session_user_scope_fk", "f", True),
            ("web_sessions", "web_session_time_order", "c", True),
            (
                "external_identity_bindings",
                "external_identity_bindings_pkey",
                "p",
                True,
            ),
            (
                "external_identity_bindings",
                "external_identity_product_scope",
                "c",
                True,
            ),
            (
                "external_identity_bindings",
                "external_identity_user_scope_fk",
                "f",
                True,
            ),
            (
                "external_identity_bindings",
                "external_identity_one_provider_per_user",
                "u",
                True,
            ),
            (
                "provider_auth_transactions",
                "provider_auth_transactions_pkey",
                "p",
                True,
            ),
            (
                "provider_auth_transactions",
                "provider_auth_transactions_browser_proof_sha256_key",
                "u",
                True,
            ),
            (
                "provider_auth_transactions",
                "provider_auth_state_sha256",
                "c",
                True,
            ),
            (
                "provider_auth_transactions",
                "provider_auth_browser_proof_sha256",
                "c",
                True,
            ),
            (
                "provider_auth_transactions",
                "provider_auth_lifetime",
                "c",
                True,
            ),
        ]
        if self._missing_constraint is not None:
            rows = [row for row in rows if row[1] != self._missing_constraint]
        return _Result(rows=rows)

    def _tenant_scope_function(self) -> _Result:
        source = (
            "SELECT 'tenant:v1:owner'"
            if self._function_drift
            else "SELECT NULLIF("
            "pg_catalog.current_setting('omni_cio.tenant_id', true), '')"
        )
        return _Result(one=("sql", "s", False, False, source))

    def _tenant_policies(self) -> _Result:
        expression = (
            "tenant_id = 'tenant:v1:owner'"
            if self._policy_drift
            else "tenant_id = omni_cio_v10.current_tenant_scope()"
        )
        return _Result(
            rows=[
                (
                    "broker_accounts",
                    "broker_accounts_tenant_isolation",
                    "*",
                    True,
                    True,
                    expression,
                    expression,
                ),
                (
                    "broker_connection_accounts",
                    "broker_connection_accounts_tenant_isolation",
                    "*",
                    True,
                    True,
                    expression,
                    expression,
                ),
                (
                    "broker_connections",
                    "broker_connections_tenant_isolation",
                    "*",
                    True,
                    True,
                    expression,
                    expression,
                ),
            ]
        )

    def _query_handlers(self) -> tuple[tuple[str, Callable[[], _Result]], ...]:
        return (
            ("AS database_owned", lambda: _Result(one=(0, 0, 0, 0))),
            ("JOIN pg_catalog.pg_roles granted_role", self._role_members),
            ("FROM pg_catalog.pg_auth_members", lambda: _Result(one=(0,))),
            (
                "has_database_privilege",
                lambda: _Result(one=(True, False, False)),
            ),
            (
                "has_schema_privilege",
                lambda: _Result(one=(True, False, False)),
            ),
            (
                "FROM pg_catalog.pg_attribute attribute_record",
                lambda: _Result(one=(1 if self._column_privilege_drift else 0,)),
            ),
            ("aclexplode", lambda: _Result(one=(0,))),
            ("information_schema.role_table_grants", self._relation_grants),
            ("information_schema.table_privileges", lambda: _Result(rows=[])),
            (
                "information_schema.role_routine_grants",
                lambda: _Result(rows=[("current_tenant_scope", "EXECUTE", "NO")]),
            ),
            ("information_schema.routine_privileges", lambda: _Result(rows=[])),
            ("has_sequence_privilege", lambda: _Result(one=(0,))),
            ("SELECT to_regclass", self._required_relations),
            (
                "FROM pg_catalog.pg_constraint constraint_record",
                self._security_constraints,
            ),
            (
                "FROM pg_catalog.pg_proc function_record",
                self._tenant_scope_function,
            ),
            ("FROM pg_catalog.pg_policy p", self._tenant_policies),
            (
                "FROM pg_catalog.pg_class c",
                lambda: _Result(
                    rows=[
                        ("broker_accounts", True, True),
                        ("broker_connection_accounts", True, True),
                        ("broker_connections", True, True),
                    ]
                ),
            ),
            ("FROM pg_catalog.pg_roles", self._role_record),
        )

    def execute(self, statement: str, params: object = None) -> _Result:
        del params
        if statement == "SHOW server_version_num":
            return _Result(one=("180000",))
        for marker, handler in self._query_handlers():
            if marker in statement:
                return handler()
        raise AssertionError(statement)


class _ReconnectableRawConnection:
    def __init__(self, *, closed: bool = False, fail_once: bool = False) -> None:
        self.closed = closed
        self.autocommit = True
        self.fail_once = fail_once
        self.execute_calls = 0

    def execute(
        self,
        query: object,
        params: object = None,
        *,
        prepare: bool | None = None,
    ) -> _Result:
        del query, params, prepare
        self.execute_calls += 1
        if self.fail_once:
            self.fail_once = False
            self.closed = True
            raise RuntimeError("simulated connection loss")
        return _Result(one=("ok",))


class _PoolTransaction:
    def __init__(self, owner: "_PoolRawConnection") -> None:
        self._owner = owner

    def __enter__(self) -> "_PoolTransaction":
        self._owner.transaction_enters += 1
        return self

    def __exit__(
        self,
        exc_type: object,
        exc_value: object,
        traceback: object,
    ) -> None:
        del exc_type, exc_value, traceback


class _PoolRawConnection(_ReconnectableRawConnection):
    def __init__(
        self,
        name: str,
        *,
        closed: bool = False,
        fail_once: bool = False,
        fail_transaction_exit: bool = False,
    ) -> None:
        super().__init__(closed=closed, fail_once=fail_once)
        self.name = name
        self.fail_transaction_exit = fail_transaction_exit
        self.transaction_enters = 0

    def transaction(self) -> object:
        if not self.fail_transaction_exit:
            return _PoolTransaction(self)
        transaction = MagicMock()
        transaction.__enter__.return_value = transaction
        transaction.__exit__.side_effect = RuntimeError(
            "simulated transaction exit failure"
        )
        return transaction

    def execute(
        self,
        query: object,
        params: object = None,
        *,
        prepare: bool | None = None,
    ) -> _Result:
        del query, params, prepare
        self.execute_calls += 1
        if self.fail_once:
            self.fail_once = False
            self.closed = True
            raise RuntimeError("simulated connection loss")
        result = _Result(one=(self.name,), rows=[(self.name,)])
        result.description = (("name",),)
        return result


def _execute_pool_transaction(
    pool: _BoundedWebConnectionPool,
    query: str,
) -> object:
    with pool.transaction():
        return pool.execute(query).fetchone()


def _execute_pool_once_in_worker(pool: _BoundedWebConnectionPool) -> object:
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(pool.execute, "SELECT 1")
        return future.result(timeout=1.0).fetchone()


def _force_transaction_affinity_drift(pool: _BoundedWebConnectionPool) -> None:
    with pool.transaction():
        connection = pool._transaction_connection()
        assert connection is not None
        pool._unbind_transaction_connection(connection)


def test_serialized_web_connection_reconnects_before_next_operation() -> None:
    stale = _ReconnectableRawConnection(closed=True)
    replacement = _ReconnectableRawConnection()
    reconnect_calls: list[str] = []

    def reconnect() -> _ReconnectableRawConnection:
        reconnect_calls.append("reconnect")
        return replacement

    connection = _SerializedWebConnection(stale, reconnect=reconnect)

    assert connection.execute("SELECT 1").fetchone() == ("ok",)
    assert reconnect_calls == ["reconnect"]
    assert replacement.execute_calls == 1


def test_serialized_web_connection_never_replays_failed_operation() -> None:
    broken = _ReconnectableRawConnection(fail_once=True)
    replacement = _ReconnectableRawConnection()
    reconnect_calls: list[str] = []

    def reconnect() -> _ReconnectableRawConnection:
        reconnect_calls.append("reconnect")
        return replacement

    connection = _SerializedWebConnection(broken, reconnect=reconnect)

    with pytest.raises(RuntimeError, match="simulated connection loss"):
        connection.execute("INSERT INTO example VALUES (1)")
    assert reconnect_calls == []

    assert connection.execute("SELECT 1").fetchone() == ("ok",)
    assert reconnect_calls == ["reconnect"]
    assert replacement.execute_calls == 1


def test_bounded_pool_allows_two_concurrent_transactions() -> None:
    initial = _PoolRawConnection("initial")
    replacement = _PoolRawConnection("replacement")
    connect_calls: list[str] = []

    def connect() -> _PoolRawConnection:
        connect_calls.append("connect")
        return replacement

    pool = _BoundedWebConnectionPool(
        initial,
        connect=connect,
        max_size=2,
        acquire_timeout_seconds=1.0,
    )
    barrier = threading.Barrier(2)

    def transaction_name() -> str:
        with pool.transaction():
            row = pool.execute("SELECT 1").fetchone()
            assert row is not None
            barrier.wait(timeout=1.0)
            return str(row[0])

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(transaction_name) for _ in range(2)]
        names = {future.result(timeout=2.0) for future in futures}

    assert names == {"initial", "replacement"}
    assert connect_calls == ["connect"]


def test_bounded_pool_drops_failed_connection_without_replay() -> None:
    initial = _PoolRawConnection("initial", fail_once=True)
    replacement = _PoolRawConnection("replacement")
    connect_calls: list[str] = []

    def connect() -> _PoolRawConnection:
        connect_calls.append("connect")
        return replacement

    pool = _BoundedWebConnectionPool(
        initial,
        connect=connect,
        max_size=1,
        acquire_timeout_seconds=1.0,
    )

    with pytest.raises(RuntimeError, match="simulated connection loss"):
        _execute_pool_transaction(pool, "INSERT INTO example VALUES (1)")
    assert initial.execute_calls == 1
    assert initial.closed is True
    assert connect_calls == []

    with pool.transaction():
        assert pool.execute("SELECT 1").fetchone() == ("replacement",)
    assert connect_calls == ["connect"]
    assert replacement.execute_calls == 1


def test_bounded_pool_exhaustion_is_time_bounded() -> None:
    pool = _BoundedWebConnectionPool(
        _PoolRawConnection("initial"),
        connect=lambda: _PoolRawConnection("unexpected"),
        max_size=1,
        acquire_timeout_seconds=0.01,
    )

    def blocked_checkout() -> str:
        with pytest.raises(
            RuntimeError,
            match="WEB_RUNTIME_POSTGRES_POOL_EXHAUSTED",
        ):
            _execute_pool_transaction(pool, "SELECT 1")
        return "blocked"

    with pool.transaction():
        with ThreadPoolExecutor(max_workers=1) as executor:
            assert executor.submit(blocked_checkout).result(timeout=1.0) == "blocked"


def test_bounded_pool_discards_connection_when_transaction_exit_fails() -> None:
    initial = _PoolRawConnection("initial", fail_transaction_exit=True)
    replacement = _PoolRawConnection("replacement")
    connect_calls: list[str] = []

    def connect() -> _PoolRawConnection:
        connect_calls.append("connect")
        return replacement

    pool = _BoundedWebConnectionPool(
        initial,
        connect=connect,
        max_size=1,
        acquire_timeout_seconds=1.0,
    )

    with pytest.raises(RuntimeError, match="simulated transaction exit failure"):
        _execute_pool_transaction(pool, "SELECT 1")

    assert initial.execute_calls == 1
    assert _execute_pool_transaction(pool, "SELECT 1") == ("replacement",)
    assert connect_calls == ["connect"]


def test_bounded_pool_discards_connection_on_affinity_cleanup_drift() -> None:
    initial = _PoolRawConnection("initial")
    replacement = _PoolRawConnection("replacement")
    connect_calls: list[str] = []

    def connect() -> _PoolRawConnection:
        connect_calls.append("connect")
        return replacement

    pool = _BoundedWebConnectionPool(
        initial,
        connect=connect,
        max_size=1,
        acquire_timeout_seconds=1.0,
    )

    with pytest.raises(
        RuntimeError,
        match="WEB_RUNTIME_POSTGRES_TRANSACTION_AFFINITY_DRIFT",
    ):
        _force_transaction_affinity_drift(pool)

    assert _execute_pool_transaction(pool, "SELECT 1") == ("replacement",)
    assert connect_calls == ["connect"]


def test_bounded_pool_releases_reserved_slot_after_connect_failure() -> None:
    initial = _PoolRawConnection("initial")
    replacement = _PoolRawConnection("replacement")
    attempts = 0

    def connect() -> _PoolRawConnection:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("simulated connect failure")
        return replacement

    pool = _BoundedWebConnectionPool(
        initial,
        connect=connect,
        max_size=2,
        acquire_timeout_seconds=1.0,
    )

    with pool.transaction():
        with pytest.raises(RuntimeError, match="simulated connect failure"):
            _execute_pool_once_in_worker(pool)
        result = _execute_pool_once_in_worker(pool)

    assert result == ("replacement",)
    assert attempts == 2


def test_provider_neutral_runtime_role_probe_accepts_exact_current_user() -> None:
    role = validate_hosted_runtime_role("omni_cio_timeweb_candidate")
    probe_hosted_runtime_database(
        _RuntimeProbeConnection(role),
        expected_runtime_role=role,
    )


def test_provider_neutral_runtime_role_probe_accepts_pg18_safe_creator_edge() -> None:
    role = "omni_cio_timeweb_candidate"
    probe_hosted_runtime_database(
        _RuntimeProbeConnection(
            role,
            runtime_members=[(True, False, False)],
        ),
        expected_runtime_role=role,
    )


def test_provider_neutral_runtime_role_probe_rejects_member_authority_drift() -> None:
    role = "omni_cio_timeweb_candidate"
    connection = _RuntimeProbeConnection(
        role,
        runtime_members=[(True, True, False)],
    )
    with pytest.raises(
        RuntimeError,
        match="HOSTED_RUNTIME_DATABASE_ROLE_MEMBER_DRIFT",
    ):
        probe_hosted_runtime_database(
            connection,
            expected_runtime_role=role,
        )


def test_provider_neutral_runtime_probe_rejects_column_authority_drift() -> None:
    role = "omni_cio_timeweb_candidate"
    connection = _RuntimeProbeConnection(role, column_privilege_drift=True)
    with pytest.raises(
        RuntimeError,
        match="HOSTED_RUNTIME_COLUMN_PRIVILEGE_FORBIDDEN",
    ):
        probe_hosted_runtime_database(
            connection,
            expected_runtime_role=role,
        )


def test_provider_neutral_runtime_probe_rejects_security_constraint_drift() -> None:
    role = "omni_cio_timeweb_candidate"
    connection = _RuntimeProbeConnection(
        role,
        missing_constraint="external_identity_user_scope_fk",
    )
    with pytest.raises(
        RuntimeError,
        match="HOSTED_RUNTIME_DATABASE_CONSTRAINT_DRIFT",
    ):
        probe_hosted_runtime_database(
            connection,
            expected_runtime_role=role,
        )


def test_provider_neutral_runtime_role_probe_rejects_identity_drift() -> None:
    connection = _RuntimeProbeConnection("omni_cio_other_runtime")
    with pytest.raises(RuntimeError, match="HOSTED_RUNTIME_DATABASE_ROLE_DRIFT"):
        probe_hosted_runtime_database(
            connection,
            expected_runtime_role="omni_cio_timeweb_candidate",
        )


def test_provider_neutral_runtime_probe_rejects_incomplete_auth_schema() -> None:
    role = "omni_cio_timeweb_candidate"
    connection = _RuntimeProbeConnection(
        role,
        missing_relation="omni_cio_v10.provider_auth_transactions",
    )
    with pytest.raises(RuntimeError, match="HOSTED_RUNTIME_DATABASE_SCHEMA_INCOMPLETE"):
        probe_hosted_runtime_database(
            connection,
            expected_runtime_role=role,
        )


def test_provider_neutral_runtime_probe_rejects_extra_relation_authority() -> None:
    role = "omni_cio_timeweb_candidate"
    connection = _RuntimeProbeConnection(role, extra_relation_privilege=True)
    with pytest.raises(
        RuntimeError,
        match="HOSTED_RUNTIME_RELATION_PRIVILEGE_DRIFT",
    ):
        probe_hosted_runtime_database(
            connection,
            expected_runtime_role=role,
        )


def test_provider_neutral_runtime_probe_rejects_tenant_scope_function_drift() -> None:
    role = "omni_cio_timeweb_candidate"
    connection = _RuntimeProbeConnection(role, function_drift=True)
    with pytest.raises(
        RuntimeError,
        match="HOSTED_RUNTIME_TENANT_SCOPE_FUNCTION_DRIFT",
    ):
        probe_hosted_runtime_database(
            connection,
            expected_runtime_role=role,
        )


def test_provider_neutral_runtime_probe_rejects_rls_policy_drift() -> None:
    role = "omni_cio_timeweb_candidate"
    connection = _RuntimeProbeConnection(role, policy_drift=True)
    with pytest.raises(RuntimeError, match="HOSTED_RUNTIME_TENANT_POLICY_DRIFT"):
        probe_hosted_runtime_database(
            connection,
            expected_runtime_role=role,
        )


def test_provider_neutral_runtime_role_validation_fails_closed() -> None:
    for role in ("", "OMNI-CIO", "omni cio", "../runtime", "a" * 64):
        with pytest.raises(
            RuntimeError,
            match="HOSTED_RUNTIME_DATABASE_ROLE_INVALID",
        ):
            validate_hosted_runtime_role(role)


def test_livez_is_process_only_after_runtime_startup(tmp_path: Path) -> None:
    state = {"calls": 0, "fail": False}

    def database_probe() -> None:
        state["calls"] += 1
        if state["fail"]:
            raise RuntimeError("database unavailable")

    app = create_hosted_app(
        HostedRuntimeServicesV1(
            sessions=SessionRegistryV1(HOSTED_SESSION_POLICY),
            database_probe=database_probe,
            hostname=HOSTNAME,
            release_sha=RELEASE_SHA,
            provider_auth=_disabled_auth(),
            synthetic_preview=False,
        ),
        web_dist=_web_dist(tmp_path),
        additional_hosts=("localhost",),
        trusted_edge_tls_terminated=True,
        provider_start_paths=frozenset(),
        provider_route_installer=lambda app, *, services: None,
    )
    assert state["calls"] == 1
    state["fail"] = True

    client = TestClient(app, base_url="http://localhost")
    live = client.get("/livez")
    assert live.status_code == 200
    assert live.json() == {"status": "ok", "release_sha": RELEASE_SHA}
    assert state["calls"] == 1

    ready = client.get("/healthz")
    assert ready.status_code == 503
    assert ready.json()["status"] == "unavailable"
    assert state["calls"] == 2


def test_livez_can_use_plain_http_only_from_explicit_loopback(tmp_path: Path) -> None:
    app = create_hosted_app(
        HostedRuntimeServicesV1(
            sessions=SessionRegistryV1(HOSTED_SESSION_POLICY),
            database_probe=lambda: None,
            hostname=HOSTNAME,
            release_sha=RELEASE_SHA,
            provider_auth=_disabled_auth(),
            synthetic_preview=False,
        ),
        web_dist=_web_dist(tmp_path),
        additional_hosts=("localhost",),
        trusted_edge_tls_terminated=False,
        allow_insecure_loopback_livez=True,
        provider_start_paths=frozenset(),
        provider_route_installer=lambda app, *, services: None,
    )
    loopback = TestClient(
        app,
        base_url="http://localhost",
        client=("127.0.0.1", 50000),
    )
    assert loopback.get("/livez").status_code == 200
    assert loopback.get("/healthz").status_code == 403

    non_loopback = TestClient(
        app,
        base_url="http://localhost",
        client=("203.0.113.10", 50000),
    )
    assert non_loopback.get("/livez").status_code == 403


def test_timeweb_trusted_edge_flag_is_explicit_and_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OMNI_V10_TRUSTED_EDGE_TLS_TERMINATED", raising=False)
    assert _trusted_edge_tls_terminated() is False

    monkeypatch.setenv("OMNI_V10_TRUSTED_EDGE_TLS_TERMINATED", "true")
    assert _trusted_edge_tls_terminated() is True

    monkeypatch.setenv("OMNI_V10_TRUSTED_EDGE_TLS_TERMINATED", "unexpected")
    with pytest.raises(
        RuntimeError,
        match="HOSTED_RUNTIME_TRUSTED_EDGE_TLS_FLAG_INVALID",
    ):
        _trusted_edge_tls_terminated()


def test_private_routes_fail_closed_without_session(tmp_path: Path) -> None:
    app = create_hosted_app(
        HostedRuntimeServicesV1(
            sessions=SessionRegistryV1(HOSTED_SESSION_POLICY),
            database_probe=lambda: None,
            hostname=HOSTNAME,
            release_sha=RELEASE_SHA,
            provider_auth=_disabled_auth(),
            synthetic_preview=False,
        ),
        web_dist=_web_dist(tmp_path),
        additional_hosts=("localhost",),
        trusted_edge_tls_terminated=True,
        provider_start_paths=frozenset(),
        provider_route_installer=lambda app, *, services: None,
    )
    client = TestClient(app, base_url="http://localhost")

    response = client.get("/api/v10/web/portfolio-dashboard")

    assert response.status_code == 401
    assert response.json() == {"detail": "AUTHENTICATION_REQUIRED"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_non_synthetic_status_is_provider_neutral() -> None:
    services = HostedRuntimeServicesV1(
        sessions=SessionRegistryV1(HOSTED_SESSION_POLICY),
        database_probe=lambda: None,
        hostname=HOSTNAME,
        release_sha=RELEASE_SHA,
        provider_auth=_disabled_auth(),
        synthetic_preview=False,
    )

    payload = _system_status(services, now="2026-09-22T12:00:00+00:00")
    database = next(item for item in payload["services"] if item["id"] == "database")
    expected_series = discover_migrations()
    expected_latest = expected_series[-1]
    expected_label = f"{expected_latest.version:04d}_{expected_latest.name}"
    assert database["label"] == "PostgreSQL 18"
    assert payload["database"]["current_migration"] is None
    assert payload["database"]["expected_migration"] == expected_label
    assert payload["database"]["migration_count"] == len(expected_series)
    assert payload["database"]["exact_migration_state"] is False
    assert "Neon" not in str(payload)


def test_current_identity_and_cookie_defaults_are_telegram_only() -> None:
    assert ORDINARY_LOGIN_PROVIDERS == (IdentityProviderV1.TELEGRAM,)
    cookies = BrowserCookiePolicyV1(csrf_binding_key=bytes([23]) * 32)
    assert cookies.allowed_providers == (IdentityProviderV1.TELEGRAM,)
    services = TelegramAuthRouteServicesV1(
        runtimes=(),
        authentication=None,
        cookies=cookies,
    )
    assert [item.provider for item in services.descriptors()] == [
        IdentityProviderV1.TELEGRAM
    ]
    assert services.disabled_reason(IdentityProviderV1.TELEGRAM) == "NOT_CONFIGURED"
    with pytest.raises(ValueError, match="TELEGRAM_AUTH_PROVIDER_INVALID"):
        services.disabled_reason(IdentityProviderV1.VK_ID)


def test_telegram_builder_exposes_only_telegram_when_fail_closed() -> None:
    services = build_telegram_provider_auth(
        connection=object(),  # unused while the provider is unconfigured
        sessions=SessionRegistryV1(HOSTED_SESSION_POLICY),
        canonical_origin="https://omnicio.ru",
        env={
            "OMNI_V10_VK_ID_CLIENT_ID": "historical-value-is-ignored",
            "OMNI_V10_VK_ID_LOGIN_ENABLED": "true",
        },
    )

    descriptors = services.descriptors()
    assert [item.provider for item in descriptors] == [IdentityProviderV1.TELEGRAM]
    assert services.runtimes == ()
    assert services.registration_enabled is False
    with pytest.raises(ValueError, match="BROWSER_PROVIDER_INVALID"):
        services.cookies.proof_cookie(IdentityProviderV1.VK_ID)


def test_telegram_public_and_login_flags_must_transition_together() -> None:
    for env in (
        {"PUBLIC_MULTI_USER_ENABLED": "true"},
        {"OMNI_V10_TELEGRAM_LOGIN_ENABLED": "true"},
    ):
        connection = object()
        sessions = SessionRegistryV1(HOSTED_SESSION_POLICY)
        with pytest.raises(
            TelegramAuthConfigurationError,
            match="TELEGRAM_AUTH_ACTIVATION_FLAGS_MISMATCH",
        ):
            build_telegram_provider_auth(
                connection=connection,
                sessions=sessions,
                canonical_origin="https://omnicio.ru",
                env=env,
            )


def test_telegram_activation_pair_requires_provider_configuration() -> None:
    connection = object()
    sessions = SessionRegistryV1(HOSTED_SESSION_POLICY)
    with pytest.raises(
        TelegramAuthConfigurationError,
        match="TELEGRAM_AUTH_ACTIVATION_CONFIGURATION_REQUIRED",
    ):
        build_telegram_provider_auth(
            connection=connection,
            sessions=sessions,
            canonical_origin="https://omnicio.ru",
            env={
                "PUBLIC_MULTI_USER_ENABLED": "true",
                "OMNI_V10_TELEGRAM_LOGIN_ENABLED": "true",
            },
        )


def test_candidate_hostname_is_optional_and_validated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OMNI_V10_CANDIDATE_HOSTNAME", raising=False)
    assert _optional_candidate_hostname() is None

    monkeypatch.setenv("OMNI_V10_CANDIDATE_HOSTNAME", "Candidate.Example.Invalid.")
    assert _optional_candidate_hostname() == "candidate.example.invalid"

    monkeypatch.setenv("OMNI_V10_CANDIDATE_HOSTNAME", "https://example.invalid")
    with pytest.raises(RuntimeError, match="HOSTED_RUNTIME_HOST_INVALID"):
        _optional_candidate_hostname()


def test_hosted_runtime_reproves_transport_for_each_database_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ca_path = tmp_path / "timeweb-postgres-root.crt"
    prepared_dsns = iter(("prepared-a", "prepared-b"))
    preparation_calls: list[tuple[str, Path]] = []
    connection_calls: list[str] = []
    configured: list[object] = []
    probed_roles: list[str] = []
    connections = [object(), object()]

    def prepare_target(external_dsn: str, observed_ca_path: Path) -> str:
        preparation_calls.append((external_dsn, observed_ca_path))
        return next(prepared_dsns)

    def connect_prepared(
        prepared_dsn: str,
        **kwargs: object,
    ) -> object:
        del kwargs
        connection_calls.append(prepared_dsn)
        return connections[len(connection_calls) - 1]

    monkeypatch.setattr(
        hosted_runtime,
        "prepare_timeweb_postgres_target",
        prepare_target,
    )
    monkeypatch.setattr(
        hosted_runtime,
        "connect_prepared_timeweb_postgres",
        connect_prepared,
    )
    monkeypatch.setattr(
        hosted_runtime,
        "_configure_long_lived_web_connection",
        configured.append,
    )
    monkeypatch.setattr(
        hosted_runtime,
        "probe_hosted_runtime_database",
        lambda _connection, *, expected_runtime_role: probed_roles.append(
            expected_runtime_role
        ),
    )

    first = hosted_runtime._open_runtime_database(
        "external-dsn",
        ca_path,
        "runtime",
    )
    second = hosted_runtime._open_runtime_database(
        "external-dsn",
        ca_path,
        "runtime",
    )

    assert first is connections[0]
    assert second is connections[1]
    assert preparation_calls == [
        ("external-dsn", ca_path),
        ("external-dsn", ca_path),
    ]
    assert connection_calls == ["prepared-a", "prepared-b"]
    assert configured == connections
    assert probed_roles == ["runtime", "runtime"]


def test_timeweb_runtime_source_has_no_retired_provider_dependency() -> None:
    root = Path(__file__).resolve().parents[1]
    current_sources = (
        root / "apps" / "api" / "hosted_runtime.py",
        root / "apps" / "api" / "hosted_app.py",
        root / "apps" / "api" / "hosted_database_runtime.py",
        root / "apps" / "api" / "telegram_auth.py",
        root / "omni_cio" / "web" / "telegram_auth_routes_v1.py",
        root / "omni_cio" / "web" / "telegram_auth_services_v1.py",
    )
    forbidden = (
        "cf_d_database_bootstrap",
        "wp22a_phase5_auth",
        "vk_id_oauth",
        "RENDER_",
        "CLOUDFLARE_",
        "NEON_",
        "hosted_preview",
        "provider_auth_routes_v1",
    )
    combined = "\n".join(path.read_text(encoding="utf-8") for path in current_sources)
    for marker in forbidden:
        assert marker not in combined

    for marker in (
        "omni_cio.real_trading",
        "TINVEST_TRADING_TOKEN",
        "REAL_TRADING_ENABLED",
        "PostOrder",
    ):
        assert marker not in combined

    runtime = current_sources[0].read_text(encoding="utf-8")
    assert "probe_hosted_runtime_database" in runtime
    assert "_probe_runtime_database" not in runtime
    assert "_probe_hosted_preview_database" not in runtime
    assert "OMNI_V10_POSTGRES_RUNTIME_ROLE" in runtime
    assert "connect_prepared_timeweb_postgres" in runtime
    assert "install_timeweb_postgres_ca" in runtime
    assert "prepare_timeweb_postgres_target" in runtime
    assert "prepare_timeweb_postgres_tls" not in runtime
    assert 'failure_prefix="HOSTED_RUNTIME_DATABASE"' in runtime
    assert "connect_timeout=_DATABASE_CONNECT_TIMEOUT_SECONDS" in runtime
    assert "connect_postgres(" not in runtime
    assert "connect=lambda:" in runtime
    assert "_BoundedWebConnectionPool(" in runtime
    assert "_SerializedWebConnection(" not in runtime
    assert "_DATABASE_POOL_MAX_SIZE = 4" in runtime
    assert "_DATABASE_POOL_ACQUIRE_TIMEOUT_SECONDS = 5.0" in runtime
    assert "omni_cio_hosted_api" not in runtime
    assert "omni_cio_cloudflare_" not in runtime
    assert "HOSTED_SESSION_POLICY" in runtime
    hosted_app = current_sources[1].read_text(encoding="utf-8")
    assert "HOSTED_SESSION_POLICY" not in hosted_app
    assert "from starlette.concurrency import run_in_threadpool" in hosted_app
    assert "scope = await run_in_threadpool(" in hosted_app
    assert 'additional_hosts=("localhost", *candidate_hosts)' in runtime
    assert "OMNI_V10_CANDIDATE_HOSTNAME" in runtime
    assert "from apps.api.app import" not in runtime
    assert "trusted_edge_tls_terminated=True" not in runtime
    assert "OMNI_V10_TRUSTED_EDGE_TLS_TERMINATED" in runtime
    assert "allow_insecure_loopback_livez=True" in runtime

    postgres_connection = (
        root / "apps" / "api" / "postgres_web_connection.py"
    ).read_text(encoding="utf-8")
    assert "t_tech" not in postgres_connection
    assert "grpc" not in postgres_connection


def test_timeweb_dockerfile_uses_provider_neutral_runtime() -> None:
    root = Path(__file__).resolve().parents[1]
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")

    assert "EXPOSE 8080" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "http://localhost:8080/livez" in dockerfile
    assert "apps.api.hosted_runtime:create_app" in dockerfile
    assert "ARG OMNI_V10_RELEASE_SHA" not in dockerfile
    assert "ENV OMNI_V10_RELEASE_SHA" not in dockerfile
    assert "SSL_TBANK_VERIFY=True" in dockerfile
    assert "prepare_v10_tbank_pip_ca_bundle.py" in dockerfile
    assert 'PIP_CERT="$PIP_CERT_PATH" python -m pip install' in dockerfile
    for secret_name in (
        "OMNI_V10_POSTGRES_DSN",
        "TELEGRAM_BOT_TOKEN",
        "TINVEST_TOKEN",
        "TINVEST_TRADING_TOKEN",
    ):
        assert f"ARG {secret_name}" not in dockerfile
        assert f"ENV {secret_name}" not in dockerfile
    assert "Dockerfile.cloudflare" not in dockerfile
    assert "wrangler" not in dockerfile.lower()
    assert "render" not in dockerfile.lower()
    assert "neon" not in dockerfile.lower()
