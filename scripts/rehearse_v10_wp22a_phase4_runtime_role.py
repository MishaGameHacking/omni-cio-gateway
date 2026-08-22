from __future__ import annotations

import os
from pathlib import Path

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
UNSAFE_MEMBER = "omni_phase4_unsafe_member"
SYNTHETIC_PASSWORD = "phase4-ci-only-runtime-password"  # pragma: allowlist secret
BOOTSTRAP_PASSWORD = "phase4-ci-only-bootstrap-password"  # pragma: allowlist secret


def _required_dsn() -> str:
    value = os.environ.get(DSN_ENV, "").strip()
    if not value:
        raise RuntimeError(f"{DSN_ENV} is required")
    return value


def _dsn_for_role(dsn: str, role: str, password: str) -> str:
    params = conninfo_to_dict(dsn)
    params["user"] = role
    params["password"] = password
    return make_conninfo(**params)


def _membership_rows(connection: psycopg.Connection[object]) -> list[tuple[object, ...]]:
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
    return [tuple(row) for row in rows]


def main() -> int:
    admin_dsn = _required_dsn()
    runtime_sql = RUNTIME_SQL.read_text(encoding="utf-8")
    validate_hosted_postgres_runtime_sql(
        runtime_sql,
        load_hosted_postgres_runtime_contract(),
    )

    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        database_name = str(admin.execute("SELECT current_database()").fetchone()[0])
        for role in (UNSAFE_MEMBER, RUNTIME_ROLE, BOOTSTRAP_ROLE):
            admin.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role)))
        admin.execute(
            sql.SQL(
                "CREATE ROLE {} WITH LOGIN NOSUPERUSER NOCREATEDB CREATEROLE "
                "NOREPLICATION NOBYPASSRLS PASSWORD {}"
            ).format(sql.Identifier(BOOTSTRAP_ROLE), sql.Literal(BOOTSTRAP_PASSWORD))
        )
        admin.execute(
            sql.SQL("ALTER DATABASE {} OWNER TO {}").format(
                sql.Identifier(database_name),
                sql.Identifier(BOOTSTRAP_ROLE),
            )
        )

    bootstrap_dsn = _dsn_for_role(admin_dsn, BOOTSTRAP_ROLE, BOOTSTRAP_PASSWORD)
    with psycopg.connect(bootstrap_dsn, autocommit=True) as bootstrap:
        apply_migrations(bootstrap)
        bootstrap.execute(
            sql.SQL(
                "CREATE ROLE {} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                "NOREPLICATION NOBYPASSRLS PASSWORD {}"
            ).format(sql.Identifier(RUNTIME_ROLE), sql.Literal(SYNTHETIC_PASSWORD))
        )

        memberships = _membership_rows(bootstrap)
        expected = [(BOOTSTRAP_ROLE, True, False, False)]
        if memberships != expected:
            raise AssertionError(
                "PostgreSQL 18 creator-admin membership shape drifted: "
                f"count={len(memberships)} values={memberships!r}"
            )
        print("PG18_RUNTIME_CREATOR_ADMIN_EDGE=PASS")

        bootstrap.execute(runtime_sql, prepare=False)
        print("PG18_HOSTED_RUNTIME_BOOTSTRAP=PASS")

        bootstrap.execute(
            sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(UNSAFE_MEMBER))
        )
        bootstrap.execute(
            sql.SQL(
                "GRANT {} TO {} WITH INHERIT TRUE, SET TRUE"
            ).format(sql.Identifier(RUNTIME_ROLE), sql.Identifier(UNSAFE_MEMBER))
        )
        memberships = _membership_rows(bootstrap)
        if len(memberships) != 2:
            raise AssertionError("unsafe membership fixture was not created")

        try:
            bootstrap.execute(runtime_sql, prepare=False)
        except psycopg.Error as exc:
            if exc.sqlstate != "42501":
                raise AssertionError(
                    f"unexpected unsafe-membership SQLSTATE: {exc.sqlstate}"
                ) from None
        else:
            raise AssertionError("unsafe runtime-role member was not rejected")
        print("PG18_UNSAFE_RUNTIME_MEMBER_REJECTED=PASS")

    print("V10_WP22A_PHASE4_PG18_RUNTIME_ROLE_REHEARSAL=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
