from __future__ import annotations

import re
from typing import Any


_ROLE_PATTERN = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


def validate_hosted_runtime_role(value: str) -> str:
    normalized = value.strip()
    if _ROLE_PATTERN.fullmatch(normalized) is None:
        raise RuntimeError("HOSTED_RUNTIME_DATABASE_ROLE_INVALID")
    return normalized


def probe_hosted_runtime_database(
    connection: Any,
    *,
    expected_runtime_role: str,
) -> None:
    """Validate provider-neutral PostgreSQL 18 runtime authority."""

    expected_role = validate_hosted_runtime_role(expected_runtime_role)

    version = connection.execute("SHOW server_version_num").fetchone()
    if version is None or int(version[0]) // 10000 != 18:
        raise RuntimeError("HOSTED_RUNTIME_POSTGRES18_REQUIRED")

    role = connection.execute(
        "SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, "
        "rolreplication, rolbypassrls FROM pg_catalog.pg_roles "
        "WHERE rolname = current_user"
    ).fetchone()
    if role != (
        expected_role,
        True,
        False,
        False,
        False,
        False,
        False,
    ):
        raise RuntimeError("HOSTED_RUNTIME_DATABASE_ROLE_DRIFT")

    memberships = connection.execute(
        "SELECT count(*) FROM pg_catalog.pg_auth_members m "
        "JOIN pg_catalog.pg_roles r ON r.oid = m.member "
        "WHERE r.rolname = current_user"
    ).fetchone()
    if memberships is None or int(memberships[0]) != 0:
        raise RuntimeError("HOSTED_RUNTIME_DATABASE_MEMBERSHIP_FORBIDDEN")

    required = connection.execute(
        "SELECT to_regclass('omni_cio_v10.tenants'), "
        "to_regclass('omni_cio_v10.users'), "
        "to_regclass('omni_cio_v10.web_sessions')"
    ).fetchone()
    if required is None or any(value is None for value in required):
        raise RuntimeError("HOSTED_RUNTIME_DATABASE_SCHEMA_INCOMPLETE")

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
    if len(rows) != 3 or any(
        not bool(row[1]) or not bool(row[2]) for row in rows
    ):
        raise RuntimeError("HOSTED_RUNTIME_DATABASE_FORCE_RLS_REQUIRED")
