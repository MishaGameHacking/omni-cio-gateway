from __future__ import annotations

import re
from typing import Any


_ROLE_PATTERN = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
_EXPECTED_RELATION_PRIVILEGES = frozenset(
    {
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
    }
)
_EXPECTED_ROUTINE_PRIVILEGES = frozenset(
    {("current_tenant_scope", "EXECUTE", "NO")}
)
_EXPECTED_RLS_POLICIES = {
    "broker_accounts": "broker_accounts_tenant_isolation",
    "broker_connection_accounts": "broker_connection_accounts_tenant_isolation",
    "broker_connections": "broker_connections_tenant_isolation",
}
_TENANT_POLICY_EXPRESSION = "tenant_id=omni_cio_v10.current_tenant_scope"
_TENANT_SCOPE_FUNCTION_SOURCE = (
    "selectnullif(pg_catalog.current_setting('omni_cio.tenant_id',true),'')"
)


def validate_hosted_runtime_role(value: str) -> str:
    normalized = value.strip()
    if _ROLE_PATTERN.fullmatch(normalized) is None:
        raise RuntimeError("HOSTED_RUNTIME_DATABASE_ROLE_INVALID")
    return normalized


def _normalized_privileges(
    rows: list[tuple[Any, ...]],
) -> frozenset[tuple[str, str, str]]:
    return frozenset(
        (str(row[0]), str(row[1]).upper(), str(row[2]).upper()) for row in rows
    )


def _normalize_expression(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"[\s()]+", "", value).lower()


def _validate_runtime_role(connection: Any, expected_role: str) -> None:
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


def _validate_runtime_ownership(connection: Any) -> None:
    ownership = connection.execute(
        "SELECT "
        "(SELECT count(*) FROM pg_catalog.pg_database d "
        " WHERE d.datname = current_database() "
        " AND d.datdba = (SELECT oid FROM pg_catalog.pg_roles "
        "                  WHERE rolname = current_user)) AS database_owned, "
        "(SELECT count(*) FROM pg_catalog.pg_namespace n "
        " WHERE n.nspname = 'omni_cio_v10' "
        " AND n.nspowner = (SELECT oid FROM pg_catalog.pg_roles "
        "                   WHERE rolname = current_user)) AS schema_owned, "
        "(SELECT count(*) FROM pg_catalog.pg_class c "
        " JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
        " WHERE n.nspname = 'omni_cio_v10' "
        " AND c.relowner = (SELECT oid FROM pg_catalog.pg_roles "
        "                   WHERE rolname = current_user)) AS relation_owned, "
        "(SELECT count(*) FROM pg_catalog.pg_proc p "
        " JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace "
        " WHERE n.nspname = 'omni_cio_v10' "
        " AND p.proowner = (SELECT oid FROM pg_catalog.pg_roles "
        "                   WHERE rolname = current_user)) AS routine_owned"
    ).fetchone()
    if ownership is None or tuple(int(value) for value in ownership) != (0, 0, 0, 0):
        raise RuntimeError("HOSTED_RUNTIME_DATABASE_OWNERSHIP_FORBIDDEN")


def _validate_runtime_privileges(connection: Any) -> None:
    database = connection.execute(
        "SELECT "
        "pg_catalog.has_database_privilege(current_user, current_database(), 'CONNECT'), "
        "pg_catalog.has_database_privilege(current_user, current_database(), 'CREATE'), "
        "pg_catalog.has_database_privilege(current_user, current_database(), 'TEMP')"
    ).fetchone()
    if database != (True, False, False):
        raise RuntimeError("HOSTED_RUNTIME_DATABASE_PRIVILEGE_DRIFT")

    schema = connection.execute(
        "SELECT "
        "pg_catalog.has_schema_privilege(current_user, 'omni_cio_v10', 'USAGE'), "
        "pg_catalog.has_schema_privilege(current_user, 'omni_cio_v10', 'CREATE'), "
        "pg_catalog.has_schema_privilege(current_user, 'public', 'CREATE')"
    ).fetchone()
    if schema != (True, False, False):
        raise RuntimeError("HOSTED_RUNTIME_SCHEMA_PRIVILEGE_DRIFT")

    public_schema = connection.execute(
        "SELECT count(*) FROM pg_catalog.pg_namespace n "
        "CROSS JOIN LATERAL pg_catalog.aclexplode("
        "COALESCE(n.nspacl, pg_catalog.acldefault('n', n.nspowner))) acl "
        "WHERE n.nspname = 'omni_cio_v10' AND acl.grantee = 0"
    ).fetchone()
    if public_schema is None or int(public_schema[0]) != 0:
        raise RuntimeError("HOSTED_RUNTIME_PUBLIC_SCHEMA_PRIVILEGE_FORBIDDEN")

    relation_rows = connection.execute(
        "SELECT table_name, privilege_type, is_grantable "
        "FROM information_schema.role_table_grants "
        "WHERE grantee = current_user AND table_schema = 'omni_cio_v10' "
        "ORDER BY table_name, privilege_type"
    ).fetchall()
    if _normalized_privileges(relation_rows) != _EXPECTED_RELATION_PRIVILEGES:
        raise RuntimeError("HOSTED_RUNTIME_RELATION_PRIVILEGE_DRIFT")

    public_relations = connection.execute(
        "SELECT table_name, privilege_type, is_grantable "
        "FROM information_schema.table_privileges "
        "WHERE grantee = 'PUBLIC' AND table_schema = 'omni_cio_v10' "
        "ORDER BY table_name, privilege_type"
    ).fetchall()
    if public_relations:
        raise RuntimeError("HOSTED_RUNTIME_PUBLIC_RELATION_PRIVILEGE_FORBIDDEN")

    routine_rows = connection.execute(
        "SELECT routine_name, privilege_type, is_grantable "
        "FROM information_schema.role_routine_grants "
        "WHERE grantee = current_user AND routine_schema = 'omni_cio_v10' "
        "ORDER BY routine_name, privilege_type"
    ).fetchall()
    if _normalized_privileges(routine_rows) != _EXPECTED_ROUTINE_PRIVILEGES:
        raise RuntimeError("HOSTED_RUNTIME_ROUTINE_PRIVILEGE_DRIFT")

    public_routines = connection.execute(
        "SELECT routine_name, privilege_type, is_grantable "
        "FROM information_schema.routine_privileges "
        "WHERE grantee = 'PUBLIC' AND routine_schema = 'omni_cio_v10' "
        "ORDER BY routine_name, privilege_type"
    ).fetchall()
    if public_routines:
        raise RuntimeError("HOSTED_RUNTIME_PUBLIC_ROUTINE_PRIVILEGE_FORBIDDEN")

    sequences = connection.execute(
        "SELECT count(*) FROM pg_catalog.pg_class c "
        "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'omni_cio_v10' AND c.relkind = 'S'"
    ).fetchone()
    if sequences is None or int(sequences[0]) != 0:
        raise RuntimeError("HOSTED_RUNTIME_SEQUENCE_SURFACE_UNEXPECTED")


def _validate_runtime_schema(connection: Any) -> None:
    required = connection.execute(
        "SELECT to_regclass('omni_cio_v10.tenants'), "
        "to_regclass('omni_cio_v10.users'), "
        "to_regclass('omni_cio_v10.external_identity_bindings'), "
        "to_regclass('omni_cio_v10.web_sessions'), "
        "to_regclass('omni_cio_v10.provider_auth_transactions')"
    ).fetchone()
    if required is None or any(value is None for value in required):
        raise RuntimeError("HOSTED_RUNTIME_DATABASE_SCHEMA_INCOMPLETE")


def _validate_tenant_scope_function(connection: Any) -> None:
    row = connection.execute(
        "SELECT language_record.lanname, function_record.provolatile, "
        "function_record.prosecdef, function_record.proleakproof, "
        "function_record.prosrc "
        "FROM pg_catalog.pg_proc function_record "
        "JOIN pg_catalog.pg_namespace schema_record "
        "ON schema_record.oid = function_record.pronamespace "
        "JOIN pg_catalog.pg_language language_record "
        "ON language_record.oid = function_record.prolang "
        "WHERE schema_record.nspname = 'omni_cio_v10' "
        "AND function_record.proname = 'current_tenant_scope' "
        "AND pg_catalog.pg_get_function_identity_arguments(function_record.oid) = ''"
    ).fetchone()
    if row is None or tuple(row[:4]) != ("sql", "s", False, False):
        raise RuntimeError("HOSTED_RUNTIME_TENANT_SCOPE_FUNCTION_DRIFT")
    if _normalize_expression(row[4]) != _TENANT_SCOPE_FUNCTION_SOURCE:
        raise RuntimeError("HOSTED_RUNTIME_TENANT_SCOPE_FUNCTION_DRIFT")


def _validate_force_rls_policies(connection: Any) -> None:
    relation_names = sorted(_EXPECTED_RLS_POLICIES)
    rows = connection.execute(
        "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity "
        "FROM pg_catalog.pg_class c "
        "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'omni_cio_v10' "
        "AND c.relname = ANY(%s) ORDER BY c.relname",
        (relation_names,),
    ).fetchall()
    if len(rows) != len(relation_names):
        raise RuntimeError("HOSTED_RUNTIME_DATABASE_FORCE_RLS_REQUIRED")
    if any(not bool(row[1]) or not bool(row[2]) for row in rows):
        raise RuntimeError("HOSTED_RUNTIME_DATABASE_FORCE_RLS_REQUIRED")

    policies = connection.execute(
        "SELECT c.relname, p.polname, p.polcmd, p.polpermissive, "
        "p.polroles = ARRAY[0::oid], "
        "pg_catalog.pg_get_expr(p.polqual, p.polrelid), "
        "pg_catalog.pg_get_expr(p.polwithcheck, p.polrelid) "
        "FROM pg_catalog.pg_policy p "
        "JOIN pg_catalog.pg_class c ON c.oid = p.polrelid "
        "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'omni_cio_v10' "
        "AND c.relname = ANY(%s) ORDER BY c.relname, p.polname",
        (relation_names,),
    ).fetchall()
    if len(policies) != len(relation_names):
        raise RuntimeError("HOSTED_RUNTIME_TENANT_POLICY_DRIFT")
    for relation, policy_name, command, permissive, public_only, using, check in policies:
        expected_name = _EXPECTED_RLS_POLICIES.get(str(relation))
        if (
            policy_name != expected_name
            or command != "*"
            or permissive is not True
            or public_only is not True
            or _normalize_expression(using) != _TENANT_POLICY_EXPRESSION
            or _normalize_expression(check) != _TENANT_POLICY_EXPRESSION
        ):
            raise RuntimeError("HOSTED_RUNTIME_TENANT_POLICY_DRIFT")


def probe_hosted_runtime_database(
    connection: Any,
    *,
    expected_runtime_role: str,
) -> None:
    """Validate provider-neutral PostgreSQL 18 runtime authority and tenant boundary."""

    expected_role = validate_hosted_runtime_role(expected_runtime_role)

    version = connection.execute("SHOW server_version_num").fetchone()
    if version is None or int(version[0]) // 10000 != 18:
        raise RuntimeError("HOSTED_RUNTIME_POSTGRES18_REQUIRED")

    _validate_runtime_role(connection, expected_role)
    _validate_runtime_ownership(connection)
    _validate_runtime_privileges(connection)
    _validate_runtime_schema(connection)
    _validate_tenant_scope_function(connection)
    _validate_force_rls_policies(connection)
