from __future__ import annotations

import argparse
import os
from pathlib import Path
import secrets
from typing import Any

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from omni_cio.persistence.hosted_postgres_runtime_v1 import (
    load_hosted_postgres_runtime_contract,
    validate_hosted_postgres_runtime_sql,
)
from omni_cio.persistence.migration import apply_migrations


DSN_ENV = "OMNI_CIO_WP13_DSN"
ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SQL = (
    ROOT / "infrastructure" / "cloudru" / "wp22a" / "hosted-postgres-runtime.sql"
)
BOOTSTRAP_ROLE = "omni_phase4_bootstrap"
RUNTIME_ROLE = "omni_cio_hosted_api"


def _required_dsn() -> str:
    value = os.environ.get(DSN_ENV, "").strip()
    if not value:
        raise RuntimeError(f"{DSN_ENV} is required")
    return value


def _ephemeral_password() -> str:
    return secrets.token_urlsafe(32)


def _dsn_for_role(dsn: str, role: str, password: str) -> str:
    params = conninfo_to_dict(dsn)
    params["user"] = role
    params["password"] = password
    return make_conninfo(**params)


def _membership_rows(
    connection: psycopg.Connection[Any],
) -> list[tuple[str, bool, bool, bool]]:
    rows = connection.execute(
        "SELECT member_role.rolname, membership.admin_option, "
        "membership.inherit_option, membership.set_option "
        "FROM pg_catalog.pg_auth_members membership "
        "JOIN pg_catalog.pg_roles granted_role "
        "ON granted_role.oid = membership.roleid "
        "JOIN pg_catalog.pg_roles member_role "
        "ON member_role.oid = membership.member "
        "WHERE granted_role.rolname = %s "
        "ORDER BY member_role.rolname",
        (RUNTIME_ROLE,),
    ).fetchall()
    return [(str(row[0]), bool(row[1]), bool(row[2]), bool(row[3])) for row in rows]


def _create_bootstrap_role(admin_dsn: str, *, own_database: bool) -> str:
    bootstrap_password = _ephemeral_password()
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        database_row = admin.execute("SELECT current_database()").fetchone()
        if database_row is None:
            raise AssertionError("PostgreSQL returned no current database")
        database_name = str(database_row[0])
        for role in (RUNTIME_ROLE, BOOTSTRAP_ROLE):
            admin.execute(
                sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role))
            )
        admin.execute(
            sql.SQL(
                "CREATE ROLE {} WITH LOGIN NOSUPERUSER NOCREATEDB CREATEROLE "
                "NOREPLICATION NOBYPASSRLS PASSWORD {}"
            ).format(sql.Identifier(BOOTSTRAP_ROLE), sql.Literal(bootstrap_password))
        )
        if own_database:
            admin.execute(
                sql.SQL("ALTER DATABASE {} OWNER TO {}").format(
                    sql.Identifier(database_name),
                    sql.Identifier(BOOTSTRAP_ROLE),
                )
            )
    return _dsn_for_role(admin_dsn, BOOTSTRAP_ROLE, bootstrap_password)


def _create_runtime_role(bootstrap: psycopg.Connection[Any]) -> None:
    runtime_password = _ephemeral_password()
    bootstrap.execute(
        sql.SQL(
            "CREATE ROLE {} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
            "NOREPLICATION NOBYPASSRLS PASSWORD {}"
        ).format(sql.Identifier(RUNTIME_ROLE), sql.Literal(runtime_password))
    )


def _assert_creator_edge(bootstrap: psycopg.Connection[Any]) -> None:
    memberships = _membership_rows(bootstrap)
    expected = [(BOOTSTRAP_ROLE, True, False, False)]
    if memberships != expected:
        raise AssertionError(
            "PostgreSQL 18 creator-admin membership shape drifted: "
            f"count={len(memberships)}"
        )
    print("PG18_RUNTIME_CREATOR_ADMIN_EDGE=PASS")


def rehearse_creator_edge() -> int:
    admin_dsn = _required_dsn()
    bootstrap_dsn = _create_bootstrap_role(admin_dsn, own_database=False)
    with psycopg.connect(bootstrap_dsn, autocommit=True) as bootstrap:
        _create_runtime_role(bootstrap)
        _assert_creator_edge(bootstrap)
    print("V10_WP22A_PHASE4_PG18_CREATOR_EDGE_REHEARSAL=PASS")
    return 0


def rehearse_bootstrap() -> int:
    admin_dsn = _required_dsn()
    runtime_sql = RUNTIME_SQL.read_text(encoding="utf-8")
    validate_hosted_postgres_runtime_sql(
        runtime_sql,
        load_hosted_postgres_runtime_contract(),
    )
    bootstrap_dsn = _create_bootstrap_role(admin_dsn, own_database=True)
    with psycopg.connect(bootstrap_dsn, autocommit=True) as bootstrap:
        apply_migrations(bootstrap)
        _create_runtime_role(bootstrap)
        _assert_creator_edge(bootstrap)
        bootstrap.execute(runtime_sql, prepare=False)
        print("PG18_HOSTED_RUNTIME_BOOTSTRAP=PASS")
    print("V10_WP22A_PHASE4_PG18_RUNTIME_ROLE_REHEARSAL=PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("creator-edge", "bootstrap"))
    args = parser.parse_args()
    if args.mode == "creator-edge":
        return rehearse_creator_edge()
    return rehearse_bootstrap()


if __name__ == "__main__":
    raise SystemExit(main())
