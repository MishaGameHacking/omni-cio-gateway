from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import secrets
import sys
from typing import Any, NoReturn

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

from apps.api.hosted_database_runtime import probe_hosted_runtime_database
from omni_cio.persistence.migration import (
    apply_migrations,
    current_migration_state,
    discover_migrations,
    require_postgres_18,
)
from scripts import postgres_runtime_primitives as postgres_runtime
from scripts import provider_runtime_primitives as provider_base
from scripts import timeweb_app_release as app_release


BOOTSTRAP_DSN_ENV = "OMNI_V10_TIMEWEB_PROD_BOOTSTRAP_DSN"
RUNTIME_DSN_ENV = "OMNI_V10_TIMEWEB_PROD_RUNTIME_DSN"
RECOVERY_ATTESTATION_VALUE = (
    "TIMEWEB_PHYSICAL_BACKUP_AND_SEPARATE_RESTORE_REHEARSAL_ACCEPTED"
)
PREPARE_CONFIRMATION = "PREPARE_TIMEWEB_PRODUCTION_POSTGRES"
RUNTIME_ROLE = "omni_cio_hosted_api"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$", re.ASCII)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$", re.ASCII)
_RETIRED_HOST_MARKERS = ("neon.tech", "cloudflare", "render.com", "cloud.ru")
_CLEAN_TABLES = (
    "tenants",
    "users",
    "external_identity_bindings",
    "web_sessions",
    "provider_auth_transactions",
    "broker_accounts",
    "broker_connections",
    "broker_connection_accounts",
)
_SET_TENANT_SCOPE_SQL = "SELECT set_config('omni_cio.tenant_id', %s, true)"
_PRODUCTION_CONNECT_RETRY_DELAYS = (1.0, 2.0, 5.0, 10.0, 20.0, 30.0)


class CutoverStopped(RuntimeError):
    pass


def _stop(code: str) -> NoReturn:
    raise CutoverStopped(code)


def _mask(value: str) -> None:
    if value:
        print(f"::add-mask::{value}")


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        _stop(f"{name}_REQUIRED")
    _mask(value)
    return value


def _sha(value: str, code: str) -> str:
    normalized = value.strip().lower()
    if _SHA_RE.fullmatch(normalized) is None:
        _stop(code)
    return normalized


def _recovery_evidence_sha256(value: str) -> str:
    normalized = value.strip().lower()
    if _SHA256_RE.fullmatch(normalized) is None:
        _stop("TIMEWEB_PG_PRODUCTION_RECOVERY_EVIDENCE_SHA256_INVALID")
    return normalized


def _dsn(name: str) -> tuple[str, dict[str, str]]:
    value = _required_env(name)
    try:
        raw = conninfo_to_dict(value)
    except psycopg.Error:
        _stop(f"{name}_INVALID")
    params = {str(key): str(item) for key, item in raw.items()}
    host = params.get("host", "").strip().lower().rstrip(".")
    database = params.get("dbname", "").strip()
    user = params.get("user", "").strip()
    if not host or not database or not user:
        _stop(f"{name}_IDENTITY_REQUIRED")
    if any(marker in host for marker in _RETIRED_HOST_MARKERS):
        _stop(f"{name}_RETIRED_PROVIDER_FORBIDDEN")
    if params.get("sslmode", "").strip().lower() != "verify-full":
        _stop(f"{name}_TLS_VERIFY_FULL_REQUIRED")
    if not params.get("sslrootcert", "").strip():
        _stop(f"{name}_TLS_ROOT_CERT_REQUIRED")
    return value, params


def _validate_target_pair(bootstrap: dict[str, str], runtime: dict[str, str]) -> None:
    for field in ("host", "port", "dbname"):
        left = bootstrap.get(field, "").strip().lower()
        right = runtime.get(field, "").strip().lower()
        if left != right:
            _stop(f"TIMEWEB_PG_PRODUCTION_TARGET_DRIFT:{field}")
    if runtime.get("user", "").strip() != RUNTIME_ROLE:
        _stop("TIMEWEB_PG_PRODUCTION_RUNTIME_ROLE_INVALID")
    if bootstrap.get("user", "").strip() == RUNTIME_ROLE:
        _stop("TIMEWEB_PG_PRODUCTION_BOOTSTRAP_RUNTIME_COLLISION")


def _verify_tls(connection: Any) -> None:
    row = connection.execute(
        "SELECT ssl FROM pg_catalog.pg_stat_ssl WHERE pid = pg_catalog.pg_backend_pid()"
    ).fetchone()
    if row != (True,):
        _stop("TIMEWEB_PG_PRODUCTION_TLS_SESSION_REQUIRED")


def _verify_bootstrap_role(connection: Any) -> None:
    row = connection.execute(
        "SELECT rolcanlogin, rolsuper, rolcreaterole, rolreplication, "
        "rolbypassrls FROM pg_catalog.pg_roles WHERE rolname = current_user"
    ).fetchone()
    if row != (True, False, True, False, False):
        _stop("TIMEWEB_PG_PRODUCTION_BOOTSTRAP_AUTHORITY_INVALID")


def _expected_migration_state() -> tuple[tuple[int, str], ...]:
    return tuple((item.version, item.sha256) for item in discover_migrations())


def _clean_counts(connection: Any) -> tuple[int, ...]:
    expressions = ", ".join(
        f"(SELECT count(*) FROM omni_cio_v10.{table})" for table in _CLEAN_TABLES
    )
    row = connection.execute(f"SELECT {expressions}").fetchone()
    if row is None or len(row) != len(_CLEAN_TABLES):
        _stop("TIMEWEB_PG_PRODUCTION_CLEAN_STATE_UNREADABLE")
    return tuple(int(value) for value in row)


def _require_clean_product_state(connection: Any) -> None:
    if any(_clean_counts(connection)):
        _stop("TIMEWEB_PG_PRODUCTION_TARGET_NOT_CLEAN")


def _probe_identity_payload(tenant_id: str) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "identity_version": 1,
        "tenant_id": tenant_id,
        "mode": "product_user",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _record_sha256(payload: dict[str, object]) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _verify_runtime_role_identity(connection: Any) -> None:
    row = connection.execute(
        "SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, "
        "rolreplication, rolbypassrls FROM pg_catalog.pg_roles "
        "WHERE rolname = current_user"
    ).fetchone()
    if row != (
        RUNTIME_ROLE,
        True,
        False,
        False,
        False,
        False,
        False,
    ):
        _stop("TIMEWEB_PG_PRODUCTION_RUNTIME_ROLE_DRIFT")
    memberships = connection.execute(
        "SELECT count(*) FROM pg_catalog.pg_auth_members memberships "
        "JOIN pg_catalog.pg_roles member_role "
        "ON member_role.oid = memberships.member "
        "WHERE member_role.rolname = current_user"
    ).fetchone()
    if memberships is None or int(memberships[0]) != 0:
        _stop("TIMEWEB_PG_PRODUCTION_RUNTIME_ROLE_MEMBERSHIP_PRESENT")


def _observed_product_tables(connection: Any) -> tuple[str, ...]:
    rows = connection.execute(
        "SELECT tablename FROM pg_catalog.pg_tables "
        "WHERE schemaname = 'omni_cio_v10' AND tablename = ANY(%s) "
        "ORDER BY tablename",
        (list(_CLEAN_TABLES),),
    ).fetchall()
    return tuple(str(row[0]) for row in rows)


def _require_observed_clean_product_state(connection: Any) -> None:
    tables = _observed_product_tables(connection)
    for table in tables:
        query = sql.SQL("SELECT count(*) FROM {}.{}").format(
            sql.Identifier("omni_cio_v10"),
            sql.Identifier(table),
        )
        row = connection.execute(query).fetchone()
        if row is None or len(row) != 1:
            _stop("TIMEWEB_PG_PRODUCTION_CLEAN_STATE_UNREADABLE")
        if int(row[0]) != 0:
            _stop("TIMEWEB_PG_PRODUCTION_TARGET_NOT_CLEAN")


def _observe_database(bootstrap_dsn: str, runtime_dsn: str) -> None:
    bootstrap = _connect(
        bootstrap_dsn,
        code="TIMEWEB_PG_PRODUCTION_BOOTSTRAP_CONNECTION_FAILED",
    )
    with bootstrap:
        _verify_tls(bootstrap)
        require_postgres_18(bootstrap)
        _verify_bootstrap_role(bootstrap)
        _require_observed_clean_product_state(bootstrap)

    runtime = _connect(
        runtime_dsn,
        code="TIMEWEB_PG_PRODUCTION_RUNTIME_CONNECTION_FAILED",
    )
    with runtime:
        _verify_tls(runtime)
        require_postgres_18(runtime)
        _verify_runtime_role_identity(runtime)


def _verify_cross_tenant_negative(connection: Any) -> None:
    nonce = secrets.token_hex(8)
    tenant_a = f"tenant:v1:p3a_{nonce}"
    tenant_b = f"tenant:v1:p3b_{nonce}"
    connection_id = "broker-connection:v1:" + secrets.token_hex(32)
    credential_handle = "read-connection:v1:" + secrets.token_hex(32)
    payload = _probe_identity_payload(tenant_a)

    try:
        with connection.transaction():
            connection.execute(
                "INSERT INTO omni_cio_v10.tenants "
                "(tenant_id, schema_version, identity_version, mode, created_at, "
                "record_sha256) VALUES (%s, %s, %s, %s, %s, %s)",
                (
                    tenant_a,
                    "1.0",
                    1,
                    "product_user",
                    payload["created_at"],
                    _record_sha256(payload),
                ),
            )
            connection.execute(_SET_TENANT_SCOPE_SQL, (tenant_a,))
            connection.execute(
                "INSERT INTO omni_cio_v10.broker_connections "
                "(connection_id, tenant_id, provider, credential_role, state, "
                "secret_ref, created_at, last_verified_at) "
                "VALUES (%s, %s, 't_invest', 'read', 'ACTIVE', %s, now(), now())",
                (connection_id, tenant_a, credential_handle),
            )
            visible = connection.execute(
                "SELECT connection_id FROM omni_cio_v10.broker_connections"
            ).fetchall()
            if visible != [(connection_id,)]:
                _stop("TIMEWEB_PG_PRODUCTION_SAME_TENANT_READ_FAILED")

            connection.execute(_SET_TENANT_SCOPE_SQL, (tenant_b,))
            if connection.execute(
                "SELECT connection_id FROM omni_cio_v10.broker_connections"
            ).fetchall():
                _stop("TIMEWEB_PG_PRODUCTION_CROSS_TENANT_READ_LEAK")

            connection.execute(
                "INSERT INTO omni_cio_v10.broker_connections "
                "(connection_id, tenant_id, provider, credential_role, state, "
                "secret_ref, created_at, last_verified_at) "
                "VALUES (%s, %s, 't_invest', 'read', 'ACTIVE', %s, now(), now())",
                (
                    "broker-connection:v1:" + secrets.token_hex(32),
                    tenant_a,
                    "read-connection:v1:" + secrets.token_hex(32),
                ),
            )
    except CutoverStopped:
        raise
    except psycopg.Error as exc:
        if exc.sqlstate != "42501":
            _stop("TIMEWEB_PG_PRODUCTION_CROSS_TENANT_WRITE_WRONG_FAILURE")
    else:
        _stop("TIMEWEB_PG_PRODUCTION_CROSS_TENANT_WRITE_ALLOWED")


def _connect(dsn: str, *, code: str) -> Any:
    return provider_base._connect_postgres_with_retry(
        psycopg,
        dsn,
        retry_marker="TIMEWEB_PG_PRODUCTION_NETWORK_RETRY",
        failure_code=code,
        retry_delays=_PRODUCTION_CONNECT_RETRY_DELAYS,
    )


def _prepare_database(bootstrap_dsn: str, runtime_dsn: str) -> None:
    bootstrap = _connect(
        bootstrap_dsn,
        code="TIMEWEB_PG_PRODUCTION_BOOTSTRAP_CONNECTION_FAILED",
    )
    with bootstrap:
        _verify_tls(bootstrap)
        require_postgres_18(bootstrap)
        _verify_bootstrap_role(bootstrap)
        apply_migrations(bootstrap)
        first_state = current_migration_state(bootstrap)
        if first_state != _expected_migration_state():
            _stop("TIMEWEB_PG_PRODUCTION_MIGRATION_STATE_INVALID")
        apply_migrations(bootstrap)
        if current_migration_state(bootstrap) != first_state:
            _stop("TIMEWEB_PG_PRODUCTION_MIGRATION_RETRY_DRIFT")
        _require_clean_product_state(bootstrap)
        runtime_sql = postgres_runtime.render_runtime_sql(RUNTIME_ROLE)
        bootstrap.execute(runtime_sql, prepare=False)

    _verify_runtime_database(runtime_dsn)


def _verify_runtime_database(runtime_dsn: str) -> None:
    runtime = _connect(
        runtime_dsn,
        code="TIMEWEB_PG_PRODUCTION_RUNTIME_CONNECTION_FAILED",
    )
    with runtime:
        _verify_tls(runtime)
        probe_hosted_runtime_database(
            runtime,
            expected_runtime_role=RUNTIME_ROLE,
        )
        _verify_cross_tenant_negative(runtime)

    bootstrap_dsn, _bootstrap_params = _dsn(BOOTSTRAP_DSN_ENV)
    bootstrap = _connect(
        bootstrap_dsn,
        code="TIMEWEB_PG_PRODUCTION_BOOTSTRAP_CONNECTION_FAILED",
    )
    with bootstrap:
        _require_clean_product_state(bootstrap)


def _is_canonical_app_row(value: object) -> bool:
    if (
        not isinstance(value, dict)
        or value.get("name") != app_release.CANONICAL_APP_NAME
    ):
        return False
    repository = value.get("repository")
    return (
        isinstance(repository, dict)
        and repository.get("full_name") == app_release.CANONICAL_REPOSITORY
    )


def _require_canonical_app_shape(payload: dict[str, Any]) -> None:
    expected = {
        "type": "backend",
        "framework": app_release.CANONICAL_FRAMEWORK,
        "branch_name": app_release.CANONICAL_BRANCH,
    }
    if any(payload.get(key) != value for key, value in expected.items()):
        _stop("TIMEWEB_PG_PRODUCTION_APP_SHAPE_DRIFT")
    if payload.get("is_auto_deploy") is not False:
        _stop("TIMEWEB_PG_PRODUCTION_APP_AUTODEPLOY_FORBIDDEN")


def _app_envs(api: app_release.TimewebAppApi) -> dict[str, str]:
    rows = api.list_apps().get("apps")
    if not isinstance(rows, list):
        _stop("TIMEWEB_PG_PRODUCTION_APP_LIST_INVALID")
    matches = [value for value in rows if _is_canonical_app_row(value)]
    if len(matches) != 1:
        _stop("TIMEWEB_PG_PRODUCTION_APP_NOT_UNIQUE")
    app_id = str(matches[0].get("id", "")).strip()
    if not app_id:
        _stop("TIMEWEB_PG_PRODUCTION_APP_ID_INVALID")
    payload = api.get_app(app_id).get("app")
    if not isinstance(payload, dict):
        _stop("TIMEWEB_PG_PRODUCTION_APP_INVALID")
    _require_canonical_app_shape(payload)
    envs = payload.get("envs")
    if not isinstance(envs, dict):
        _stop("TIMEWEB_PG_PRODUCTION_APP_ENV_INVALID")
    return {str(key): str(value) for key, value in envs.items()}


def _verify_app_binding(expected_sha: str, runtime_dsn: str) -> None:
    token = _required_env(app_release.TOKEN_ENV)
    api = app_release.TimewebAppApi(token)
    envs = _app_envs(api)
    observed_dsn = envs.get(app_release.POSTGRES_DSN_ENV, "")
    _mask(observed_dsn)
    if not observed_dsn or observed_dsn != runtime_dsn:
        _stop("TIMEWEB_PG_PRODUCTION_APP_DSN_NOT_PROMOTED")
    if envs.get(app_release.RELEASE_SHA_ENV, "").lower() != expected_sha:
        _stop("TIMEWEB_PG_PRODUCTION_APP_RELEASE_SHA_DRIFT")
    for name in (
        app_release.PUBLIC_MULTI_USER_ENV,
        app_release.TELEGRAM_LOGIN_ENV,
    ):
        if envs.get(name, "").strip().lower() != "false":
            _stop(f"TIMEWEB_PG_PRODUCTION_PREMATURE_ACTIVATION:{name}")


def run(
    *,
    operation: str,
    expected_sha: str,
    observed_main_sha: str,
    confirmation: str = "",
    recovery_attestation: str = "",
    recovery_evidence_sha256: str = "",
) -> None:
    expected = _sha(expected_sha, "TIMEWEB_PG_PRODUCTION_SHA_INVALID")
    observed = _sha(observed_main_sha, "TIMEWEB_PG_PRODUCTION_MAIN_SHA_INVALID")
    if expected != observed:
        _stop("TIMEWEB_PG_PRODUCTION_MAIN_SHA_DRIFT")

    bootstrap_dsn, bootstrap_params = _dsn(BOOTSTRAP_DSN_ENV)
    runtime_dsn, runtime_params = _dsn(RUNTIME_DSN_ENV)
    _validate_target_pair(bootstrap_params, runtime_params)

    if operation != "accept" and (recovery_attestation or recovery_evidence_sha256):
        _stop("TIMEWEB_PG_PRODUCTION_UNEXPECTED_RECOVERY_EVIDENCE")

    if operation == "observe":
        if confirmation:
            _stop("TIMEWEB_PG_PRODUCTION_UNEXPECTED_CONFIRMATION")
        _observe_database(bootstrap_dsn, runtime_dsn)
        print(
            "TIMEWEB_POSTGRES_PRODUCTION_CUTOVER=OBSERVED "
            f"sha={expected} postgres=18 tls=verify-full public_users=false"
        )
        return

    if operation == "prepare":
        if confirmation != PREPARE_CONFIRMATION:
            _stop("TIMEWEB_PG_PRODUCTION_PREPARE_CONFIRMATION_REQUIRED")
        _prepare_database(bootstrap_dsn, runtime_dsn)
        print(
            "TIMEWEB_POSTGRES_PRODUCTION_CUTOVER=PREPARED "
            f"sha={expected} postgres=18 tls=verify-full public_users=false"
        )
        return

    if confirmation:
        _stop("TIMEWEB_PG_PRODUCTION_UNEXPECTED_CONFIRMATION")
    if operation != "accept":
        _stop("TIMEWEB_PG_PRODUCTION_OPERATION_INVALID")

    _verify_runtime_database(runtime_dsn)
    if recovery_attestation != RECOVERY_ATTESTATION_VALUE:
        _stop("TIMEWEB_PG_PRODUCTION_RECOVERY_NOT_ACCEPTED")
    evidence_digest = _recovery_evidence_sha256(recovery_evidence_sha256)
    _verify_app_binding(expected, runtime_dsn)
    print(
        "TIMEWEB_POSTGRES_PRODUCTION_CUTOVER=ACCEPTED "
        f"sha={expected} recovery=accepted evidence_sha256={evidence_digest} "
        "app_dsn=verified public_users=false"
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--operation",
        choices=("observe", "prepare", "accept"),
        required=True,
    )
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--observed-main-sha", required=True)
    parser.add_argument("--confirmation", default="")
    parser.add_argument("--recovery-attestation", default="")
    parser.add_argument("--recovery-evidence-sha256", default="")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        run(
            operation=args.operation,
            expected_sha=args.expected_sha,
            observed_main_sha=args.observed_main_sha,
            confirmation=args.confirmation,
            recovery_attestation=args.recovery_attestation,
            recovery_evidence_sha256=args.recovery_evidence_sha256,
        )
    except CutoverStopped as exc:
        print(
            f"TIMEWEB_POSTGRES_PRODUCTION_CUTOVER=STOPPED code={exc}",
            file=sys.stderr,
        )
        return 1
    except provider_base.ProvisioningStopped as exc:
        print(
            f"TIMEWEB_POSTGRES_PRODUCTION_CUTOVER=STOPPED code={exc.code}",
            file=sys.stderr,
        )
        return 1
    except psycopg.Error as exc:
        sqlstate = exc.sqlstate or "UNKNOWN"
        print(
            "TIMEWEB_POSTGRES_PRODUCTION_CUTOVER=STOPPED "
            f"code=POSTGRES_ERROR sqlstate={sqlstate}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
