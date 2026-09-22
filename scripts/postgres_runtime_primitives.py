from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from psycopg import sql

from omni_cio.persistence.hosted_postgres_runtime_v1 import (
    BOOTSTRAP_PATH,
    load_hosted_postgres_runtime_contract,
    validate_hosted_postgres_runtime_sql,
)
from scripts.provider_runtime_primitives import ProvisioningStopped


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SQL = BOOTSTRAP_PATH
_TEMPLATE_RUNTIME_ROLE = "omni_cio_hosted_api"
_ROLE_PATTERN = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


def validate_runtime_role(value: str) -> str:
    normalized = value.strip()
    if _ROLE_PATTERN.fullmatch(normalized) is None:
        raise ProvisioningStopped("POSTGRES_RUNTIME_ROLE_INVALID")
    return normalized


def render_runtime_sql(runtime_role: str) -> str:
    role = validate_runtime_role(runtime_role)
    source = RUNTIME_SQL.read_text(encoding="utf-8")
    validate_hosted_postgres_runtime_sql(
        source,
        load_hosted_postgres_runtime_contract(),
    )
    occurrences = source.count(_TEMPLATE_RUNTIME_ROLE)
    if occurrences < 2:
        raise ProvisioningStopped("POSTGRES_RUNTIME_ROLE_TEMPLATE_INVALID")
    rendered = source.replace(_TEMPLATE_RUNTIME_ROLE, role)
    if _TEMPLATE_RUNTIME_ROLE in rendered or role not in rendered:
        raise ProvisioningStopped("POSTGRES_RUNTIME_ROLE_RENDER_FAILED")
    return rendered


def converge_runtime_role(
    connection: Any,
    runtime_role: str,
    runtime_password: str,
) -> None:
    role = validate_runtime_role(runtime_role)
    existing = connection.execute(
        "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, "
        "rolbypassrls FROM pg_catalog.pg_roles WHERE rolname = %s",
        (role,),
    ).fetchone()
    memberships = connection.execute(
        "SELECT count(*) FROM pg_catalog.pg_auth_members memberships "
        "JOIN pg_catalog.pg_roles member_role "
        "ON member_role.oid = memberships.member "
        "WHERE member_role.rolname = %s",
        (role,),
    ).fetchone()
    if memberships is not None and int(memberships[0]) != 0:
        raise ProvisioningStopped("POSTGRES_RUNTIME_ROLE_MEMBERSHIP_PRESENT")

    if existing is None:
        connection.execute(
            sql.SQL(
                "CREATE ROLE {} WITH LOGIN NOSUPERUSER NOCREATEDB "
                "NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}"
            ).format(
                sql.Identifier(role),
                sql.Literal(runtime_password),
            )
        )
        return
    if tuple(existing) != (False, False, False, False, False):
        raise ProvisioningStopped("POSTGRES_RUNTIME_ROLE_ATTRIBUTE_DRIFT")
    connection.execute(
        sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD {}").format(
            sql.Identifier(role),
            sql.Literal(runtime_password),
        )
    )


def verify_runtime(connection: Any, runtime_role: str) -> None:
    role_name = validate_runtime_role(runtime_role)
    role = connection.execute(
        "SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, "
        "rolreplication, rolbypassrls FROM pg_catalog.pg_roles "
        "WHERE rolname = current_user"
    ).fetchone()
    if role != (
        role_name,
        True,
        False,
        False,
        False,
        False,
        False,
    ):
        raise ProvisioningStopped("POSTGRES_RUNTIME_ROLE_DRIFT")
    memberships = connection.execute(
        "SELECT count(*) FROM pg_catalog.pg_auth_members memberships "
        "JOIN pg_catalog.pg_roles member_role "
        "ON member_role.oid = memberships.member "
        "WHERE member_role.rolname = current_user"
    ).fetchone()
    if memberships is None or int(memberships[0]) != 0:
        raise ProvisioningStopped("POSTGRES_RUNTIME_ROLE_MEMBERSHIP_PRESENT")
    rows = connection.execute(
        "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity "
        "FROM pg_catalog.pg_class c "
        "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'omni_cio_v10' "
        "AND c.relname = ANY(%s) ORDER BY c.relname",
        (
            [
                "broker_accounts",
                "broker_connection_accounts",
                "broker_connections",
            ],
        ),
    ).fetchall()
    if len(rows) != 3 or any(not bool(row[1]) or not bool(row[2]) for row in rows):
        raise ProvisioningStopped("POSTGRES_RUNTIME_FORCE_RLS_DRIFT")
