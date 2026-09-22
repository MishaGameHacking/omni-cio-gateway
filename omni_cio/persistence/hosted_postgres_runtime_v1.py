from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = (
    ROOT / "infrastructure" / "postgres" / "hosted-postgres-runtime-contract.json"
)
BOOTSTRAP_PATH = ROOT / "infrastructure" / "postgres" / "hosted-postgres-runtime.sql"

_USER_NAME = "omni_cio_hosted_api"
_SCHEMA_NAME = "omni_cio_v10"
_EXPECTED_DATABASE_PRIVILEGES = ("CONNECT",)
_EXPECTED_FUNCTION_PRIVILEGES: dict[str, tuple[str, ...]] = {
    "current_tenant_scope()": ("EXECUTE",),
}
_EXPECTED_RELATION_PRIVILEGES: dict[str, tuple[str, ...]] = {
    "tenants": ("INSERT",),
    "users": ("SELECT", "INSERT"),
    "external_identity_bindings": ("SELECT", "INSERT"),
    "web_sessions": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    "provider_auth_transactions": ("SELECT", "INSERT", "DELETE"),
    "broker_accounts": ("SELECT", "INSERT"),
    "broker_connections": ("SELECT", "INSERT", "UPDATE"),
    "broker_connection_accounts": ("SELECT", "INSERT"),
}
_EXPECTED_FORCED_RLS = (
    "broker_accounts",
    "broker_connections",
    "broker_connection_accounts",
)
_EXPECTED_FORBIDDEN_RELATIONS = (
    "schema_migrations",
    "portfolios",
    "instruments",
    "policies",
    "portfolio_snapshots",
    "positions",
    "evidence",
    "incidents",
    "incident_revisions",
    "incident_evidence",
    "decisions",
    "decision_evidence",
    "plans",
    "executions",
    "journal",
    "research_cache",
    "jobs",
    "job_events",
    "system_health",
    "content_blobs",
    "state_revisions",
)
_EXPECTED_FORBIDDEN_PREDEFINED_ROLES = (
    "pg_read_all_data",
    "pg_write_all_data",
)


class HostedPostgresRuntimeContractError(RuntimeError):
    """Fail-closed hosted PostgreSQL runtime contract violation."""


def _as_mapping(value: object, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise HostedPostgresRuntimeContractError(code)
    return value


def _as_string_sequence(value: object, code: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise HostedPostgresRuntimeContractError(code)
    result = tuple(str(item) for item in value)
    if len(result) != len(set(result)):
        raise HostedPostgresRuntimeContractError(code)
    return result


def _require_exact_mapping(
    actual: Mapping[str, Any],
    expected: Mapping[str, object],
    code: str,
) -> None:
    if set(actual) != set(expected):
        raise HostedPostgresRuntimeContractError(code)
    for key, expected_value in expected.items():
        actual_value = actual[key]
        if type(actual_value) is not type(expected_value):
            raise HostedPostgresRuntimeContractError(code)
        if actual_value != expected_value:
            raise HostedPostgresRuntimeContractError(code)


def load_hosted_postgres_runtime_contract(
    path: Path = CONTRACT_PATH,
) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise HostedPostgresRuntimeContractError("HOSTED_POSTGRES_CONTRACT_NOT_OBJECT")
    return payload


def validate_hosted_postgres_runtime_contract(
    payload: Mapping[str, Any],
) -> None:
    if payload.get("schema_version") != "v10.hosted-postgres-runtime.v5":
        raise HostedPostgresRuntimeContractError(
            "HOSTED_POSTGRES_CONTRACT_VERSION_INVALID"
        )

    authority = _as_mapping(
        payload.get("authority"),
        "HOSTED_POSTGRES_AUTHORITY_INVALID",
    )
    _require_exact_mapping(
        authority,
        {
            "provider": "PROVIDER_NEUTRAL_POSTGRESQL_18",
            "source_only": True,
            "provider_apply_authorized": False,
            "public_database_ingress_allowed": False,
            "authorized_recurring_rub": 0,
            "public_multi_user_enabled": False,
            "trading_methods_enabled": False,
            "real_trading_enabled": False,
            "protected_v9_entrypoint": "app:app",
            "wp23_unlocked": False,
        },
        "HOSTED_POSTGRES_AUTHORITY_DRIFT",
    )

    provider_user = _as_mapping(
        payload.get("provider_user"),
        "HOSTED_POSTGRES_PROVIDER_USER_INVALID",
    )
    _require_exact_mapping(
        provider_user,
        {
            "name": _USER_NAME,
            "resource_type": "postgresql_runtime_login",
            "provisioning_phase": "PROVIDER_ADAPTER",
            "source_bootstrap_creates_user": False,
            "login_required": True,
            "credential_delivery": "external_non_source",
            "credential_value_in_source_allowed": False,
            "predefined_roles": [],
            "database_owner": False,
            "schema_owner": False,
            "object_owner": False,
            "superuser": False,
            "create_database": False,
            "create_role": False,
            "replication": False,
            "bypass_rls": False,
        },
        "HOSTED_POSTGRES_PROVIDER_USER_DRIFT",
    )

    bootstrap = _as_mapping(
        payload.get("bootstrap"),
        "HOSTED_POSTGRES_BOOTSTRAP_INVALID",
    )
    _require_exact_mapping(
        bootstrap,
        {
            "provider_user_must_preexist": True,
            "run_after_migrations": True,
            "reapply_after_every_migration": True,
            "public_schema_create_revoked": True,
            "public_app_schema_privileges_revoked": True,
            "public_function_execute_revoked": True,
            "public_database_temporary_revoked": True,
        },
        "HOSTED_POSTGRES_BOOTSTRAP_DRIFT",
    )

    schema = _as_mapping(
        payload.get("schema"),
        "HOSTED_POSTGRES_SCHEMA_INVALID",
    )
    _require_exact_mapping(
        schema,
        {"name": _SCHEMA_NAME, "usage": True, "create": False},
        "HOSTED_POSTGRES_SCHEMA_DRIFT",
    )

    database_privileges = _as_string_sequence(
        payload.get("database_privileges"),
        "HOSTED_POSTGRES_DATABASE_PRIVILEGES_INVALID",
    )
    if database_privileges != _EXPECTED_DATABASE_PRIVILEGES:
        raise HostedPostgresRuntimeContractError(
            "HOSTED_POSTGRES_DATABASE_PRIVILEGES_DRIFT"
        )

    function_privileges = _as_mapping(
        payload.get("function_privileges"),
        "HOSTED_POSTGRES_FUNCTION_PRIVILEGES_INVALID",
    )
    normalized_function_privileges = {
        str(function): _as_string_sequence(
            privileges,
            "HOSTED_POSTGRES_FUNCTION_PRIVILEGES_INVALID",
        )
        for function, privileges in function_privileges.items()
    }
    if normalized_function_privileges != _EXPECTED_FUNCTION_PRIVILEGES:
        raise HostedPostgresRuntimeContractError(
            "HOSTED_POSTGRES_FUNCTION_PRIVILEGES_DRIFT"
        )

    relation_privileges = _as_mapping(
        payload.get("relation_privileges"),
        "HOSTED_POSTGRES_RELATION_PRIVILEGES_INVALID",
    )
    normalized_relation_privileges = {
        str(relation): _as_string_sequence(
            privileges,
            "HOSTED_POSTGRES_RELATION_PRIVILEGES_INVALID",
        )
        for relation, privileges in relation_privileges.items()
    }
    if normalized_relation_privileges != _EXPECTED_RELATION_PRIVILEGES:
        raise HostedPostgresRuntimeContractError(
            "HOSTED_POSTGRES_RELATION_PRIVILEGES_DRIFT"
        )

    rls = _as_mapping(payload.get("rls"), "HOSTED_POSTGRES_RLS_INVALID")
    _require_exact_mapping(
        rls,
        {
            "tenant_setting": "omni_cio.tenant_id",
            "transaction_local_required": True,
            "unscoped_default_deny": True,
            "forced_relations": list(_EXPECTED_FORCED_RLS),
        },
        "HOSTED_POSTGRES_RLS_DRIFT",
    )

    forbidden_relations = _as_string_sequence(
        payload.get("forbidden_relations"),
        "HOSTED_POSTGRES_FORBIDDEN_RELATIONS_INVALID",
    )
    if forbidden_relations != _EXPECTED_FORBIDDEN_RELATIONS:
        raise HostedPostgresRuntimeContractError(
            "HOSTED_POSTGRES_FORBIDDEN_RELATIONS_DRIFT"
        )
    if set(forbidden_relations) & set(_EXPECTED_RELATION_PRIVILEGES):
        raise HostedPostgresRuntimeContractError(
            "HOSTED_POSTGRES_RELATION_ALLOW_DENY_OVERLAP"
        )

    forbidden_predefined_roles = _as_string_sequence(
        payload.get("forbidden_predefined_roles"),
        "HOSTED_POSTGRES_FORBIDDEN_PREDEFINED_ROLES_INVALID",
    )
    if forbidden_predefined_roles != _EXPECTED_FORBIDDEN_PREDEFINED_ROLES:
        raise HostedPostgresRuntimeContractError(
            "HOSTED_POSTGRES_FORBIDDEN_PREDEFINED_ROLES_DRIFT"
        )


def _normalize_sql(value: str) -> str:
    without_comments = re.sub(r"--.*?$", "", value, flags=re.MULTILINE)
    return re.sub(r"\s+", " ", without_comments).strip().upper()


def _grant_statements(normalized_sql: str) -> set[str]:
    return {
        statement.strip()
        for statement in normalized_sql.split(";")
        if statement.strip().startswith("GRANT ")
    }


def _expected_grant_statements() -> set[str]:
    expected = {f"GRANT USAGE ON SCHEMA {_SCHEMA_NAME.upper()} TO {_USER_NAME.upper()}"}
    for function, privileges in _EXPECTED_FUNCTION_PRIVILEGES.items():
        joined = ", ".join(privileges)
        expected.add(
            "GRANT "
            f"{joined} ON FUNCTION {_SCHEMA_NAME.upper()}.{function.upper()} "
            f"TO {_USER_NAME.upper()}"
        )
    for relation, privileges in _EXPECTED_RELATION_PRIVILEGES.items():
        joined = ", ".join(privileges)
        expected.add(
            "GRANT "
            f"{joined} ON TABLE {_SCHEMA_NAME.upper()}.{relation.upper()} "
            f"TO {_USER_NAME.upper()}"
        )
    return expected


def validate_hosted_postgres_runtime_sql(
    sql: str,
    payload: Mapping[str, Any] | None = None,
) -> None:
    contract = (
        payload if payload is not None else load_hosted_postgres_runtime_contract()
    )
    validate_hosted_postgres_runtime_contract(contract)
    normalized = _normalize_sql(sql)

    forbidden_user_management = (
        r"\bCREATE\s+(?:ROLE|USER)\b",
        r"\bALTER\s+(?:ROLE|USER)\b",
        r"\bDROP\s+(?:ROLE|USER)\b",
    )
    for pattern in forbidden_user_management:
        if re.search(pattern, normalized):
            raise HostedPostgresRuntimeContractError(
                "HOSTED_POSTGRES_SQL_PROVIDER_USER_MANAGEMENT_FORBIDDEN"
            )

    for role_name in _EXPECTED_FORBIDDEN_PREDEFINED_ROLES:
        if re.search(
            rf"\bGRANT\s+{re.escape(role_name.upper())}\s+TO\s+"
            rf"{_USER_NAME.upper()}\b",
            normalized,
        ):
            raise HostedPostgresRuntimeContractError(
                "HOSTED_POSTGRES_SQL_BROAD_ROLE_GRANT"
            )

    required_markers = (
        "PG_CATALOG.PG_ROLES",
        "PG_CATALOG.PG_AUTH_MEMBERS",
        "PG_CATALOG.PG_DATABASE",
        "PG_CATALOG.PG_NAMESPACE",
        "PG_CATALOG.PG_CLASS",
        "PG_CATALOG.PG_PROC",
        "HOSTED_API_USER_NOT_PROVISIONED",
        "HOSTED_API_USER_ATTRIBUTE_DRIFT",
        "HOSTED_API_USER_ROLE_MEMBERSHIP_PRESENT",
        "HOSTED_API_USER_MEMBERS_PRESENT",
        "HOSTED_API_DATABASE_OWNERSHIP_FORBIDDEN",
        "HOSTED_API_SCHEMA_OWNERSHIP_FORBIDDEN",
        "HOSTED_API_OBJECT_OWNERSHIP_FORBIDDEN",
        "NOT RUNTIME_USER.ROLCANLOGIN",
        "MEMBERSHIP.MEMBER = RUNTIME_USER.OID",
        "MEMBERSHIP.ROLEID = RUNTIME_USER.OID",
        "DATABASE_RECORD.DATDBA = RUNTIME_USER.OID",
        "SCHEMA_RECORD.NSPOWNER = RUNTIME_USER.OID",
        "RELATION_RECORD.RELOWNER = RUNTIME_USER.OID",
        "FUNCTION_RECORD.PROOWNER = RUNTIME_USER.OID",
        "REVOKE CREATE, TEMPORARY ON DATABASE %I FROM PUBLIC",
        "REVOKE ALL PRIVILEGES ON DATABASE %I FROM %I",
        "GRANT CONNECT ON DATABASE %I TO %I",
        "REVOKE CREATE ON SCHEMA PUBLIC FROM PUBLIC",
        "REVOKE ALL ON SCHEMA OMNI_CIO_V10 FROM PUBLIC",
        "REVOKE ALL ON ALL TABLES IN SCHEMA OMNI_CIO_V10 FROM PUBLIC",
        "REVOKE ALL ON ALL SEQUENCES IN SCHEMA OMNI_CIO_V10 FROM PUBLIC",
        "REVOKE ALL ON ALL FUNCTIONS IN SCHEMA OMNI_CIO_V10 FROM PUBLIC",
        "REVOKE ALL ON SCHEMA OMNI_CIO_V10 FROM OMNI_CIO_HOSTED_API",
        "REVOKE ALL ON ALL TABLES IN SCHEMA OMNI_CIO_V10 FROM OMNI_CIO_HOSTED_API",
        "REVOKE ALL ON ALL SEQUENCES IN SCHEMA OMNI_CIO_V10 FROM OMNI_CIO_HOSTED_API",
        "REVOKE ALL ON ALL FUNCTIONS IN SCHEMA OMNI_CIO_V10 FROM OMNI_CIO_HOSTED_API",
    )
    for marker in required_markers:
        if marker not in normalized:
            raise HostedPostgresRuntimeContractError(
                "HOSTED_POSTGRES_SQL_SAFETY_MARKER_MISSING"
            )

    for forbidden in ("ALTER DEFAULT PRIVILEGES", "SET ROLE"):
        if forbidden in normalized:
            raise HostedPostgresRuntimeContractError(
                "HOSTED_POSTGRES_SQL_AUTHORITY_WIDENED"
            )

    if _grant_statements(normalized) != _expected_grant_statements():
        raise HostedPostgresRuntimeContractError("HOSTED_POSTGRES_SQL_GRANT_UNEXPECTED")

    for relation in _EXPECTED_FORCED_RLS:
        qualified = f"{_SCHEMA_NAME.upper()}.{relation.upper()}"
        for mode in ("ENABLE", "FORCE"):
            marker = f"ALTER TABLE {qualified} {mode} ROW LEVEL SECURITY"
            if marker not in normalized:
                raise HostedPostgresRuntimeContractError(
                    "HOSTED_POSTGRES_SQL_RLS_MARKER_MISSING"
                )

    forbidden_relations = _as_string_sequence(
        contract.get("forbidden_relations"),
        "HOSTED_POSTGRES_FORBIDDEN_RELATIONS_INVALID",
    )
    for relation in forbidden_relations:
        grant_pattern = (
            rf"GRANT\s+.+?\s+ON\s+TABLE\s+{_SCHEMA_NAME.upper()}\."
            rf"{re.escape(relation.upper())}\s+TO\s+{_USER_NAME.upper()}"
        )
        if re.search(grant_pattern, normalized):
            raise HostedPostgresRuntimeContractError(
                "HOSTED_POSTGRES_SQL_FORBIDDEN_RELATION_GRANT"
            )
