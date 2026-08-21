from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
from typing import Any

from omni_cio.persistence.hosted_postgres_runtime_v1 import (
    validate_hosted_postgres_runtime_sql,
)
from omni_cio.persistence.migration import (
    apply_migrations,
    connect_postgres,
    current_migration_state,
    discover_migrations,
    require_postgres_18,
)


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SQL_PATH = (
    ROOT / "infrastructure" / "cloudru" / "wp22a" / "hosted-postgres-runtime.sql"
)
_ROLE_RE = re.compile(r"^[a-z][a-z0-9_]{2,62}$")
_EXPECTED_RUNTIME_ROLE = "omni_cio_hosted_api"


class PreviewDatabaseError(RuntimeError):
    pass


def _close(connection: Any) -> None:
    close = getattr(connection, "close", None)
    if callable(close):
        close()


def _autocommit(connection: Any) -> None:
    try:
        connection.autocommit = True
    except Exception as exc:
        raise PreviewDatabaseError("PREVIEW_DATABASE_AUTOCOMMIT_REQUIRED") from exc
    if getattr(connection, "autocommit", None) is not True:
        raise PreviewDatabaseError("PREVIEW_DATABASE_AUTOCOMMIT_REQUIRED")


def _runtime_sql() -> str:
    try:
        value = RUNTIME_SQL_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise PreviewDatabaseError("PREVIEW_RUNTIME_SQL_UNAVAILABLE") from exc
    validate_hosted_postgres_runtime_sql(value)
    return value


def _apply_runtime_grants(connection: Any, sql: str) -> None:
    try:
        with connection.transaction():
            connection.execute(sql, prepare=False)
    except Exception as exc:
        raise PreviewDatabaseError("PREVIEW_RUNTIME_GRANTS_FAILED") from exc


def _verify_migrations(connection: Any) -> None:
    expected = tuple((item.version, item.sha256) for item in discover_migrations())
    actual = current_migration_state(connection)
    if actual != expected:
        raise PreviewDatabaseError("PREVIEW_MIGRATION_STATE_INVALID")


def _verify_runtime_role(connection: Any, runtime_role: str) -> None:
    row = connection.execute(
        "SELECT current_user, rolsuper, rolcreatedb, rolcreaterole, "
        "rolreplication, rolbypassrls "
        "FROM pg_catalog.pg_roles WHERE rolname = current_user"
    ).fetchone()
    if row is None or str(row[0]) != runtime_role:
        raise PreviewDatabaseError("PREVIEW_RUNTIME_ROLE_IDENTITY_INVALID")
    if any(bool(value) for value in row[1:]):
        raise PreviewDatabaseError("PREVIEW_RUNTIME_ROLE_AUTHORITY_WIDENED")

    membership = connection.execute(
        "SELECT EXISTS ("
        "SELECT 1 FROM pg_catalog.pg_auth_members membership "
        "JOIN pg_catalog.pg_roles role_record "
        "ON role_record.oid = membership.member "
        "WHERE role_record.rolname = current_user"
        ")"
    ).fetchone()
    if membership is None or bool(membership[0]):
        raise PreviewDatabaseError("PREVIEW_RUNTIME_ROLE_MEMBERSHIP_PRESENT")

    database_privileges = connection.execute(
        "SELECT "
        "has_database_privilege(current_user, current_database(), 'CONNECT'), "
        "has_database_privilege(current_user, current_database(), 'CREATE'), "
        "has_database_privilege(current_user, current_database(), 'TEMPORARY')"
    ).fetchone()
    if database_privileges is None:
        raise PreviewDatabaseError("PREVIEW_RUNTIME_DATABASE_PRIVILEGES_MISSING")
    if tuple(bool(value) for value in database_privileges) != (True, False, False):
        raise PreviewDatabaseError("PREVIEW_RUNTIME_DATABASE_PRIVILEGES_INVALID")

    schema_privileges = connection.execute(
        "SELECT "
        "has_schema_privilege(current_user, 'omni_cio_v10', 'USAGE'), "
        "has_schema_privilege(current_user, 'omni_cio_v10', 'CREATE')"
    ).fetchone()
    if schema_privileges is None:
        raise PreviewDatabaseError("PREVIEW_RUNTIME_SCHEMA_PRIVILEGES_MISSING")
    if tuple(bool(value) for value in schema_privileges) != (True, False):
        raise PreviewDatabaseError("PREVIEW_RUNTIME_SCHEMA_PRIVILEGES_INVALID")

    forced_rls = connection.execute(
        "SELECT relname, relrowsecurity, relforcerowsecurity "
        "FROM pg_catalog.pg_class relation_record "
        "JOIN pg_catalog.pg_namespace schema_record "
        "ON schema_record.oid = relation_record.relnamespace "
        "WHERE schema_record.nspname = 'omni_cio_v10' "
        "AND relation_record.relname IN ("
        "'broker_accounts', "
        "'broker_connections', "
        "'broker_connection_accounts'"
        ") ORDER BY relname"
    ).fetchall()
    expected_relations = {
        "broker_accounts",
        "broker_connection_accounts",
        "broker_connections",
    }
    if {str(row[0]) for row in forced_rls} != expected_relations:
        raise PreviewDatabaseError("PREVIEW_RUNTIME_RLS_RELATIONS_MISSING")
    if any(not bool(row[1]) or not bool(row[2]) for row in forced_rls):
        raise PreviewDatabaseError("PREVIEW_RUNTIME_FORCE_RLS_MISSING")

    unscoped = connection.execute(
        "SELECT count(*) FROM omni_cio_v10.broker_connections"
    ).fetchone()
    if unscoped is None or int(unscoped[0]) != 0:
        raise PreviewDatabaseError("PREVIEW_RUNTIME_UNSCOPED_RLS_FAILED")


def prepare_preview_database(
    *,
    owner_dsn: str,
    runtime_dsn: str,
    runtime_role: str = _EXPECTED_RUNTIME_ROLE,
) -> None:
    normalized_role = runtime_role.strip().lower()
    if normalized_role != _EXPECTED_RUNTIME_ROLE:
        raise PreviewDatabaseError("PREVIEW_RUNTIME_ROLE_NAME_INVALID")
    if _ROLE_RE.fullmatch(normalized_role) is None:
        raise PreviewDatabaseError("PREVIEW_RUNTIME_ROLE_NAME_INVALID")
    if not owner_dsn.strip() or not runtime_dsn.strip():
        raise PreviewDatabaseError("PREVIEW_DATABASE_DSN_REQUIRED")
    if owner_dsn == runtime_dsn:
        raise PreviewDatabaseError("PREVIEW_DATABASE_ROLE_SEPARATION_REQUIRED")

    owner = connect_postgres(owner_dsn)
    try:
        _autocommit(owner)
        require_postgres_18(owner)
        apply_migrations(owner)
        _apply_runtime_grants(owner, _runtime_sql())
        _verify_migrations(owner)
    finally:
        _close(owner)

    runtime = connect_postgres(runtime_dsn)
    try:
        _autocommit(runtime)
        require_postgres_18(runtime)
        _verify_migrations(runtime)
        _verify_runtime_role(runtime, normalized_role)
    finally:
        _close(runtime)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner-dsn", required=True)
    parser.add_argument("--runtime-dsn", required=True)
    parser.add_argument(
        "--runtime-role",
        default=_EXPECTED_RUNTIME_ROLE,
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    prepare_preview_database(
        owner_dsn=str(args.owner_dsn),
        runtime_dsn=str(args.runtime_dsn),
        runtime_role=str(args.runtime_role),
    )
    print("PREVIEW_DATABASE_PREPARATION=PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PreviewDatabaseError as exc:
        print(f"PREVIEW_DATABASE_PREPARATION=FAIL reason={exc}", file=sys.stderr)
        raise SystemExit(1) from exc
