from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = (
    ROOT
    / "infrastructure"
    / "cloudru"
    / "wp22a"
    / "hosted-postgres-runtime-contract.json"
)
BOOTSTRAP_PATH = (
    ROOT
    / "infrastructure"
    / "cloudru"
    / "wp22a"
    / "hosted-postgres-runtime.sql"
)

_ROLE_NAME = "omni_cio_hosted_api"
_SCHEMA_NAME = "omni_cio_v10"
_EXPECTED_RELATION_PRIVILEGES: dict[str, tuple[str, ...]] = {
    "tenants": ("INSERT",),
    "users": ("SELECT", "INSERT"),
    "external_identity_bindings": ("SELECT", "INSERT"),
    "web_sessions": ("SELECT", "INSERT", "UPDATE", "DELETE"),
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
_EXPECTED_ROLE_OPTIONS = (
    "NOSUPERUSER",
    "NOCREATEDB",
    "NOCREATEROLE",
    "NOINHERIT",
    "NOLOGIN",
    "NOREPLICATION",
    "NOBYPASSRLS",
)
_DANGEROUS_ROLE_OPTIONS = (
    "SUPERUSER",
    "CREATEDB",
    "CREATEROLE",
    "INHERIT",
    "LOGIN",
    "REPLICATION",
    "BYPASSRLS",
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
        raise HostedPostgresRuntimeContractError(
            "HOSTED_POSTGRES_CONTRACT_NOT_OBJECT"
        )
    return payload


def validate_hosted_postgres_runtime_contract(
    payload: Mapping[str, Any],
) -> None:
    if (
        payload.get("schema_version")
        != "v10.wp22a.phase3.hosted-postgres-runtime.v1"
    ):
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
            "provider": "Cloud.ru Evolution",
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

    runtime_role = _as_mapping(
        payload.get("runtime_role"),
        "HOSTED_POSTGRES_ROLE_INVALID",
    )
    _require_exact_mapping(
        runtime_role,
        {
            "name": _ROLE_NAME,
            "cluster_scoped": True,
            "login_identity_bound": False,
            "preexisting_exact_role_reuse_allowed": True,
            "membership_in_other_roles_allowed": False,
            "superuser": False,
            "create_database": False,
            "create_role": False,
            "inherit": False,
            "replication": False,
            "bypass_rls": False,
        },
        "HOSTED_POSTGRES_ROLE_DRIFT",
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

    relation_privileges = _as_mapping(
        payload.get("relation_privileges"),
        "HOSTED_POSTGRES_RELATION_PRIVILEGES_INVALID",
    )
    normalized_privileges = {
        str(relation): _as_string_sequence(
            privileges,
            "HOSTED_POSTGRES_RELATION_PRIVILEGES_INVALID",
        )
        for relation, privileges in relation_privileges.items()
    }
    if normalized_privileges != _EXPECTED_RELATION_PRIVILEGES:
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

    forbidden_role_grants = _as_string_sequence(
        payload.get("forbidden_role_grants"),
        "HOSTED_POSTGRES_FORBIDDEN_ROLE_GRANTS_INVALID",
    )
    if forbidden_role_grants != ("pg_read_all_data", "pg_write_all_data"):
        raise HostedPostgresRuntimeContractError(
            "HOSTED_POSTGRES_FORBIDDEN_ROLE_GRANTS_DRIFT"
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
    expected = {
        f"GRANT USAGE ON SCHEMA {_SCHEMA_NAME.upper()} TO {_ROLE_NAME.upper()}"
    }
    for relation, privileges in _EXPECTED_RELATION_PRIVILEGES.items():
        joined = ", ".join(privileges)
        expected.add(
            "GRANT "
            f"{joined} ON TABLE {_SCHEMA_NAME.upper()}.{relation.upper()} "
            f"TO {_ROLE_NAME.upper()}"
        )
    return expected


def validate_hosted_postgres_runtime_sql(
    sql: str,
    payload: Mapping[str, Any] | None = None,
) -> None:
    contract = payload or load_hosted_postgres_runtime_contract()
    validate_hosted_postgres_runtime_contract(contract)
    normalized = _normalize_sql(sql)

    option_pattern = (
        r"\b(?:NO)?(?:SUPERUSER|CREATEDB|CREATEROLE|INHERIT|LOGIN|"
        r"REPLICATION|BYPASSRLS)\b"
    )
    for statement in ("CREATE", "ALTER"):
        match = re.search(
            rf"{statement} ROLE {_ROLE_NAME.upper()} "
            rf"(?P<body>.*?NOBYPASSRLS)",
            normalized,
        )
        if match is None:
            raise HostedPostgresRuntimeContractError(
                "HOSTED_POSTGRES_SQL_ROLE_OPTION_DRIFT"
            )
        if set(re.findall(option_pattern, match.group("body"))) != set(
            _EXPECTED_ROLE_OPTIONS
        ):
            raise HostedPostgresRuntimeContractError(
                "HOSTED_POSTGRES_SQL_ROLE_OPTION_DRIFT"
            )

    for option in _DANGEROUS_ROLE_OPTIONS:
        if re.search(rf"(?<!NO)\b{option}\b", normalized):
            raise HostedPostgresRuntimeContractError(
                "HOSTED_POSTGRES_SQL_ROLE_OPTION_DRIFT"
            )

    required_markers = (
        "PG_CATALOG.PG_ROLES",
        "PG_CATALOG.PG_AUTH_MEMBERS",
        "HOSTED_API_ROLE_ATTRIBUTE_DRIFT",
        "HOSTED_API_ROLE_MEMBERSHIP_DRIFT",
        "REVOKE ALL ON ALL TABLES IN SCHEMA OMNI_CIO_V10 FROM OMNI_CIO_HOSTED_API",
        "REVOKE ALL ON ALL SEQUENCES IN SCHEMA OMNI_CIO_V10 FROM OMNI_CIO_HOSTED_API",
        "REVOKE CREATE ON SCHEMA OMNI_CIO_V10 FROM OMNI_CIO_HOSTED_API",
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
        raise HostedPostgresRuntimeContractError(
            "HOSTED_POSTGRES_SQL_GRANT_UNEXPECTED"
        )

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
            rf"{re.escape(relation.upper())}\s+TO\s+{_ROLE_NAME.upper()}"
        )
        if re.search(grant_pattern, normalized):
            raise HostedPostgresRuntimeContractError(
                "HOSTED_POSTGRES_SQL_FORBIDDEN_RELATION_GRANT"
            )

    for role_name in _as_string_sequence(
        contract.get("forbidden_role_grants"),
        "HOSTED_POSTGRES_FORBIDDEN_ROLE_GRANTS_INVALID",
    ):
        if re.search(
            rf"GRANT\s+{re.escape(role_name.upper())}\s+TO\s+"
            rf"{_ROLE_NAME.upper()}",
            normalized,
        ):
            raise HostedPostgresRuntimeContractError(
                "HOSTED_POSTGRES_SQL_BROAD_ROLE_GRANT"
            )
