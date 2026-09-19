from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
from typing import Any

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from scripts import provision_v10_cloudflare_neon_runtime as neon_runtime
from scripts import provision_v10_render_neon_preview as postgres_base

from omni_cio.persistence.hosted_postgres_runtime_v1 import (
    load_hosted_postgres_runtime_contract,
    validate_hosted_postgres_runtime_sql,
)
from omni_cio.persistence.migration import (
    apply_migrations,
    current_migration_state,
    discover_migrations,
    require_postgres_18,
)


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SQL = ROOT / "infrastructure/cloudru/wp22a/hosted-postgres-runtime.sql"
DSN_ENV = "OMNI_V10_RU_PG_BOOTSTRAP_DSN"
ACK_ENV = "OMNI_V10_RU_PG_SYNTHETIC_ACK"
ACK_VALUE = "TIMEWEB_SYNTHETIC_ONLY"
LOCATION_ENV = "OMNI_V10_RU_PG_PROVIDER_LOCATION"
LOCATION_VALUE = "ru-3"
RUNTIME_ROLE = neon_runtime._runtime_role("staging")
_BROKER_CONNECTION_PREFIX = "broker-connection:v1:"
_READ_CONNECTION_PREFIX = "read-connection:v1:"
_SET_TENANT_SCOPE_SQL = "SELECT set_config('omni_cio.tenant_id', %s, true)"
NOW = datetime(2026, 9, 19, 9, 0, tzinfo=timezone.utc)
TENANT_A = "tenant:v1:ru_pg_a"
TENANT_B = "tenant:v1:ru_pg_b"
CONNECTION_A = _BROKER_CONNECTION_PREFIX + "1" * 64
CONNECTION_B = _BROKER_CONNECTION_PREFIX + "2" * 64
CROSS_CONNECTION = _BROKER_CONNECTION_PREFIX + "3" * 64
SECRET_A = _READ_CONNECTION_PREFIX + "4" * 64
SECRET_B = _READ_CONNECTION_PREFIX + "5" * 64
CROSS_SECRET = _READ_CONNECTION_PREFIX + "6" * 64


class ParityStopped(RuntimeError):
    """Fail-closed sanitized RU-PG-B proof failure."""


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ParityStopped(f"{name}_REQUIRED")
    return value


def _required_dsn() -> str:
    if _required_env(ACK_ENV) != ACK_VALUE:
        raise ParityStopped("RU_PG_SYNTHETIC_ACK_INVALID")
    if _required_env(LOCATION_ENV) != LOCATION_VALUE:
        raise ParityStopped("RU_PG_PROVIDER_LOCATION_INVALID")
    value = _required_env(DSN_ENV)
    params = conninfo_to_dict(value)
    host = str(params.get("host", "")).lower().rstrip(".")
    if not host:
        raise ParityStopped("RU_PG_BOOTSTRAP_HOST_REQUIRED")
    if host.endswith(".neon.tech"):
        raise ParityStopped("RU_PG_NEON_TARGET_FORBIDDEN")
    if str(params.get("sslmode", "")).lower() != "verify-full":
        raise ParityStopped("RU_PG_TLS_VERIFY_FULL_REQUIRED")
    if not str(params.get("sslrootcert", "")).strip():
        raise ParityStopped("RU_PG_TLS_ROOT_CERT_REQUIRED")
    return value


def _dsn_for_role(dsn: str, role: str, password: str) -> str:
    params = conninfo_to_dict(dsn)
    params["user"] = role
    params["password"] = password
    return make_conninfo(**params)


def _record_sha256(payload: dict[str, object]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _verify_tls(connection: psycopg.Connection[Any]) -> None:
    row = connection.execute(
        "SELECT ssl FROM pg_catalog.pg_stat_ssl WHERE pid = pg_catalog.pg_backend_pid()"
    ).fetchone()
    if row != (True,):
        raise ParityStopped("RU_PG_TLS_SESSION_REQUIRED")


def _bootstrap_role(connection: psycopg.Connection[Any]) -> str:
    row = connection.execute(
        "SELECT rolname, rolcanlogin, rolsuper, rolcreaterole, "
        "rolreplication, rolbypassrls FROM pg_catalog.pg_roles "
        "WHERE rolname = current_user"
    ).fetchone()
    if row is None or len(row) != 6:
        raise ParityStopped("RU_PG_BOOTSTRAP_ROLE_INVALID")
    role = str(row[0])
    attrs = tuple(bool(value) for value in row[1:])
    if attrs != (True, False, True, False, False):
        raise ParityStopped("RU_PG_BOOTSTRAP_ROLE_AUTHORITY_INVALID")
    if role == RUNTIME_ROLE:
        raise ParityStopped("RU_PG_BOOTSTRAP_RUNTIME_IDENTITY_COLLISION")
    return role


def _seed_tenant(
    connection: psycopg.Connection[Any],
    tenant_id: str,
) -> None:
    payload: dict[str, object] = {
        "schema_version": "1.0",
        "identity_version": 1,
        "tenant_id": tenant_id,
        "mode": "product_user",
        "created_at": NOW.isoformat(),
    }
    connection.execute(
        "INSERT INTO omni_cio_v10.tenants "
        "(tenant_id, schema_version, identity_version, mode, created_at, "
        "record_sha256) VALUES (%s, %s, %s, %s, %s, %s) "
        "ON CONFLICT (tenant_id) DO NOTHING",
        (
            tenant_id,
            "1.0",
            1,
            "product_user",
            NOW,
            _record_sha256(payload),
        ),
    )


def _seed_connection(
    connection: psycopg.Connection[Any],
    tenant_id: str,
    connection_id: str,
    secret_ref: str,
) -> None:
    with connection.transaction():
        connection.execute(
            _SET_TENANT_SCOPE_SQL,
            (tenant_id,),
        )
        connection.execute(
            "INSERT INTO omni_cio_v10.broker_connections "
            "(connection_id, tenant_id, provider, credential_role, state, "
            "secret_ref, created_at, last_verified_at) "
            "VALUES (%s, %s, 't_invest', 'read', 'ACTIVE', %s, %s, %s) "
            "ON CONFLICT (connection_id) DO NOTHING",
            (connection_id, tenant_id, secret_ref, NOW, NOW),
        )


def _seed_synthetic_scope(
    connection: psycopg.Connection[Any],
) -> None:
    _seed_tenant(connection, TENANT_A)
    _seed_tenant(connection, TENANT_B)
    _seed_connection(connection, TENANT_A, CONNECTION_A, SECRET_A)
    _seed_connection(connection, TENANT_B, CONNECTION_B, SECRET_B)


def _verify_runtime_privilege_floor(
    connection: psycopg.Connection[Any],
) -> None:
    forbidden = connection.execute(
        "SELECT has_table_privilege("
        "current_user, 'omni_cio_v10.schema_migrations', 'SELECT')"
    ).fetchone()
    if forbidden != (False,):
        raise ParityStopped("RU_PG_RUNTIME_PRIVILEGE_WIDENED")


def _verify_rls_negatives(
    connection: psycopg.Connection[Any],
) -> None:
    with connection.transaction():
        unscoped = connection.execute(
            "SELECT connection_id FROM omni_cio_v10.broker_connections"
        ).fetchall()
        if unscoped:
            raise ParityStopped("RU_PG_RLS_UNSCOPED_READ_LEAK")

    with connection.transaction():
        connection.execute(
            _SET_TENANT_SCOPE_SQL,
            (TENANT_A,),
        )
        visible = connection.execute(
            "SELECT connection_id FROM omni_cio_v10.broker_connections "
            "ORDER BY connection_id"
        ).fetchall()
        if visible != [(CONNECTION_A,)]:
            raise ParityStopped("RU_PG_RLS_CROSS_TENANT_READ_LEAK")

    try:
        with connection.transaction():
            connection.execute(
                _SET_TENANT_SCOPE_SQL,
                (TENANT_A,),
            )
            connection.execute(
                "INSERT INTO omni_cio_v10.broker_connections "
                "(connection_id, tenant_id, provider, credential_role, "
                "state, secret_ref, created_at, last_verified_at) "
                "VALUES (%s, %s, 't_invest', 'read', 'ACTIVE', %s, %s, %s)",
                (CROSS_CONNECTION, TENANT_B, CROSS_SECRET, NOW, NOW),
            )
    except psycopg.Error as exc:
        if exc.sqlstate != "42501":
            raise ParityStopped(
                "RU_PG_RLS_CROSS_TENANT_WRITE_WRONG_FAILURE"
            ) from None
    else:
        raise ParityStopped("RU_PG_RLS_CROSS_TENANT_WRITE_ALLOWED")


def _expected_migration_state() -> tuple[tuple[int, str], ...]:
    return tuple((item.version, item.sha256) for item in discover_migrations())


def prove() -> None:
    bootstrap_dsn = _required_dsn()
    runtime_sql = neon_runtime._runtime_sql(RUNTIME_ROLE)
    validate_hosted_postgres_runtime_sql(
        RUNTIME_SQL.read_text(encoding="utf-8"),
        load_hosted_postgres_runtime_contract(),
    )
    runtime_password = secrets.token_urlsafe(32)

    bootstrap = postgres_base._connect_postgres_with_retry(
        psycopg,
        bootstrap_dsn,
        retry_marker="RU_PG_BOOTSTRAP_NETWORK_RETRY",
        failure_code="RU_PG_BOOTSTRAP_NETWORK_ERROR",
    )
    with bootstrap:
        _verify_tls(bootstrap)
        require_postgres_18(bootstrap)
        _bootstrap_role(bootstrap)
        apply_migrations(bootstrap)
        if current_migration_state(bootstrap) != _expected_migration_state():
            raise ParityStopped("RU_PG_MIGRATION_STATE_INVALID")
        neon_runtime._converge_runtime_role(
            bootstrap,
            RUNTIME_ROLE,
            runtime_password,
        )
        _seed_synthetic_scope(bootstrap)
        bootstrap.execute(runtime_sql, prepare=False)

    runtime_dsn = _dsn_for_role(
        bootstrap_dsn,
        RUNTIME_ROLE,
        runtime_password,
    )
    runtime = postgres_base._connect_postgres_with_retry(
        psycopg,
        runtime_dsn,
        retry_marker="RU_PG_RUNTIME_NETWORK_RETRY",
        failure_code="RU_PG_RUNTIME_CONNECTION_FAILED",
    )
    with runtime:
        _verify_tls(runtime)
        neon_runtime._verify_runtime(runtime, RUNTIME_ROLE)
        _verify_runtime_privilege_floor(runtime)
        _verify_rls_negatives(runtime)

    print(
        "RU_PG_TIMEWEB_SYNTHETIC_PARITY=PASS "
        "postgres=18 tls=verify-full runtime_role=verified "
        "migrations=verified rls=verified"
    )


def main() -> int:
    try:
        prove()
    except ParityStopped as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except postgres_base.ProvisioningStopped as exc:
        print(f"RU_PG_REUSED_PROVISIONER_STOPPED code={exc.code}", file=sys.stderr)
        return 1
    except psycopg.Error as exc:
        code = exc.sqlstate or "UNKNOWN"
        print(f"RU_PG_POSTGRES_ERROR sqlstate={code}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
