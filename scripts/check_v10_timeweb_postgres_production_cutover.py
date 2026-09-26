from __future__ import annotations

import ast
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    ROOT / "docs/architecture/V10_TIMEWEB_POSTGRES_PRODUCTION_CUTOVER_CONTRACT.json"
)
RUNBOOK = ROOT / "docs/operations/V10_TIMEWEB_POSTGRES_PRODUCTION_CUTOVER_RUNBOOK.md"
CONTROLLER = ROOT / "scripts/timeweb_postgres_production_cutover.py"
HOSTED_RUNTIME = ROOT / "apps/api/hosted_runtime.py"
TIMEWEB_TLS = ROOT / "apps/api/timeweb_postgres_tls.py"
WORKFLOW = ROOT / ".github/workflows/v10-timeweb-postgres-production-cutover.yml"
RUNTIME = ROOT / "infrastructure/postgres/hosted-postgres-runtime-contract.json"
RECOVERY = ROOT / "infrastructure/postgres/hosted-recovery-contract.json"

_PREPARE_CONFIRMATION = "PREPARE_TIMEWEB_PRODUCTION_POSTGRES"
_RECOVERY_ATTESTATION = (
    "TIMEWEB_PHYSICAL_BACKUP_AND_SEPARATE_RESTORE_REHEARSAL_ACCEPTED"
)
_CONTROL_PLANE_SECRET = "${{ secrets.TIMEWEB_CLOUD_API_TOKEN }}"
_BOOTSTRAP_DSN_SECRET = "${{ secrets.OMNI_V10_TIMEWEB_PROD_BOOTSTRAP_DSN }}"
_RUNTIME_DSN_SECRET = "${{ secrets.OMNI_V10_TIMEWEB_PROD_RUNTIME_DSN }}"
_RECOVERY_ATTESTATION_SECRET = "${{ secrets.OMNI_V10_TIMEWEB_PG_RECOVERY_ATTESTATION }}"
_GITHUB_INVALID = "TIMEWEB_PG_CUTOVER_GITHUB_INVALID"


class CutoverContractError(RuntimeError):
    pass


def _text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise CutoverContractError(
            f"TIMEWEB_PG_CUTOVER_SOURCE_UNREADABLE:{path.name}"
        ) from exc


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(_text(path))
    except json.JSONDecodeError as exc:
        raise CutoverContractError("TIMEWEB_PG_CUTOVER_JSON_INVALID") from exc
    if not isinstance(value, dict):
        raise CutoverContractError("TIMEWEB_PG_CUTOVER_JSON_INVALID")
    return value


def _markers(source: str, required: tuple[str, ...], code: str) -> None:
    missing = [item for item in required if item not in source]
    if missing:
        raise CutoverContractError(f"{code}:{missing[0]}")


def _false_map(value: object, keys: tuple[str, ...], code: str) -> None:
    if not isinstance(value, dict) or any(value.get(key) is not False for key in keys):
        raise CutoverContractError(code)


def _true_map(value: object, keys: tuple[str, ...], code: str) -> None:
    if not isinstance(value, dict) or any(value.get(key) is not True for key in keys):
        raise CutoverContractError(code)


def _mapping(value: object, code: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CutoverContractError(code)
    return value


def _validate_target(payload: dict[str, Any]) -> None:
    code = "TIMEWEB_PG_CUTOVER_TARGET_INVALID"
    target = _mapping(payload.get("target"), code)
    if (
        target.get("postgres_major") != 18
        or target.get("synthetic_fixture_promotion_allowed") is not False
    ):
        raise CutoverContractError(code)


def _validate_transport(payload: dict[str, Any]) -> None:
    transport = _mapping(
        payload.get("transport"),
        "TIMEWEB_PG_CUTOVER_TRANSPORT_INVALID",
    )
    expected = {
        "sslmode": "verify-full",
        "sslrootcert_required": True,
        "encrypted_session_required": True,
        "plaintext_dsn_in_repository_allowed": False,
        "technical_domain_required": True,
        "provider_technical_domain_suffix_required": True,
        "provider_technical_domain_suffixes": [
            ".tw1.ru",
            ".tw1.su",
            ".twc1.net",
            ".webtm.ru",
        ],
        "allowed_external_dsn_parameters": [
            "dbname",
            "host",
            "password",
            "port",
            "sslmode",
            "sslrootcert",
            "user",
        ],
        "explicit_password_required": True,
        "ambient_libpq_target_or_credential_override_allowed": False,
        "ambient_libpq_connection_environment_allowed": False,
        "verified_hostaddr_binding_required": True,
        "second_dns_lookup_for_authenticated_connection_allowed": False,
        "port": 5432,
        "canonical_sslrootcert": ".omni-cio/timeweb-postgres-root.crt",
        "ca_source_url": "https://st.timeweb.com/cloud-static/ca.crt",
        "ca_fetch_bounded_retry_required": True,
        "ca_redirect_allowed": False,
        "ca_materialization_before_connect_required": True,
        "credential_free_transport_preflight_required": True,
        "dns_public_resolution_required": True,
        "private_or_reserved_resolution_allowed": False,
        "postgres_sslrequest_required": True,
        "tls_minimum_version": "TLSv1.2",
        "transport_preflight_before_database_auth_required": True,
        "raw_endpoint_or_exception_logging_allowed": False,
        "external_dsn_format": "POSTGRESQL_LIBPQ",
        "php_pdo_dsn_allowed": False,
        "resolved_sslrootcert_may_be_absolute_in_process_only": True,
    }
    if transport != expected:
        raise CutoverContractError("TIMEWEB_PG_CUTOVER_TRANSPORT_INVALID")


def _validate_connection_retry(payload: dict[str, Any]) -> None:
    retry = _mapping(
        payload.get("connection_retry"),
        "TIMEWEB_PG_CUTOVER_CONNECTION_RETRY_INVALID",
    )
    expected = {
        "bounded": True,
        "classified_failure_code_required": True,
        "raw_exception_text_logging_allowed": False,
        "unclassified_client_failure_retry_allowed": False,
        "classified_client_timeout_retry_allowed": True,
        "transient_sqlstates": [
            "08000",
            "08001",
            "08003",
            "08006",
            "08007",
            "53300",
            "57P01",
            "57P02",
            "57P03",
        ],
        "invalid_authorization_sqlstate_retry_allowed": False,
        "unknown_server_sqlstate_retry_allowed": False,
    }
    if retry != expected:
        raise CutoverContractError("TIMEWEB_PG_CUTOVER_CONNECTION_RETRY_INVALID")


def _validate_runtime_role(payload: dict[str, Any]) -> None:
    role = _mapping(
        payload.get("runtime_role"),
        "TIMEWEB_PG_CUTOVER_RUNTIME_ROLE_INVALID",
    )
    if role.get("name") != "omni_cio_hosted_api":
        raise CutoverContractError("TIMEWEB_PG_CUTOVER_RUNTIME_ROLE_INVALID")
    _false_map(
        role,
        (
            "controller_creates_login",
            "controller_alters_login_password",
            "superuser_allowed",
            "createdb_allowed",
            "createrole_allowed",
            "replication_allowed",
            "bypassrls_allowed",
            "membership_widening_allowed",
            "database_owner_allowed",
            "schema_owner_allowed",
            "object_owner_allowed",
        ),
        "TIMEWEB_PG_CUTOVER_RUNTIME_ROLE_WIDENED",
    )


def _validate_prepare(payload: dict[str, Any]) -> None:
    prepare = _mapping(payload.get("prepare"), "TIMEWEB_PG_CUTOVER_PREPARE_INVALID")
    if prepare.get("confirmation") != _PREPARE_CONFIRMATION:
        raise CutoverContractError("TIMEWEB_PG_CUTOVER_PREPARE_INVALID")
    _true_map(
        prepare,
        (
            "migrations_apply_required",
            "migration_retry_idempotence_required",
            "provider_neutral_runtime_acl_required",
            "force_rls_required",
            "cross_tenant_negative_required",
        ),
        "TIMEWEB_PG_CUTOVER_PREPARE_INVALID",
    )
    _false_map(
        prepare,
        ("data_deletion_allowed", "drop_schema_allowed", "truncate_allowed"),
        "TIMEWEB_PG_CUTOVER_DESTRUCTIVE_AUTHORITY",
    )


def _validate_recovery(payload: dict[str, Any]) -> None:
    recovery = _mapping(
        payload.get("recovery"),
        "TIMEWEB_PG_CUTOVER_RECOVERY_INVALID",
    )
    expected = {
        "recovery_attestation_source": "WORKFLOW_DISPATCH_INPUT",
        "recovery_attestation_input": "recovery_attestation",
        "recovery_attestation_value": _RECOVERY_ATTESTATION,
        "recovery_evidence_sha256_input": "recovery_evidence_sha256",
        "recovery_evidence_sha256_required": True,
        "recovery_evidence_digest_is_not_secret": True,
        "actions_secret_for_recovery_attestation_allowed": False,
    }
    for key, value in expected.items():
        if recovery.get(key) != value:
            raise CutoverContractError(f"TIMEWEB_PG_CUTOVER_RECOVERY_DRIFT:{key}")
    _true_map(
        recovery,
        (
            "timeweb_physical_backup_required",
            "physical_backup_is_additive_to_logical_recovery",
            "separate_restore_rehearsal_required",
            "provider_panel_action_allowed_when_no_documented_safe_api_exists",
        ),
        "TIMEWEB_PG_CUTOVER_RECOVERY_INVALID",
    )


def _validate_app_binding(payload: dict[str, Any]) -> None:
    binding = _mapping(
        payload.get("app_binding"),
        "TIMEWEB_PG_CUTOVER_APP_BINDING_INVALID",
    )
    _false_map(
        binding,
        (
            "runtime_dsn_promotion_by_controller_allowed",
            "undocumented_timeweb_app_settings_api_allowed",
        ),
        "TIMEWEB_PG_CUTOVER_APP_BINDING_INVALID",
    )


def _validate_github(payload: dict[str, Any]) -> None:
    github = _mapping(payload.get("github"), _GITHUB_INVALID)
    expected = {
        "environment": "timeweb-production",
        "environment_preexisting_required": True,
        "environment_branch_policy_pattern": "main",
        "environment_branch_policy_type": "branch",
    }
    if any(github.get(key) != value for key, value in expected.items()):
        raise CutoverContractError(_GITHUB_INVALID)
    _true_map(
        github,
        (
            "manual_dispatch_only",
            "provider_token_step_scope_only",
            "database_bindings_step_scope_only",
            "operation_specific_secret_injection_required",
            "provider_token_accept_only",
            "production_dsns_step_scoped",
            "environment_policy_reverified_before_secret_access",
        ),
        _GITHUB_INVALID,
    )
    _false_map(
        github,
        (
            "recovery_attestation_as_actions_secret_allowed",
            "environment_administration_by_workflow_allowed",
        ),
        _GITHUB_INVALID,
    )


def _validate_observe(payload: dict[str, Any]) -> None:
    observe = _mapping(payload.get("observe"), "TIMEWEB_PG_CUTOVER_OBSERVE_INVALID")
    expected = {
        "sql_mutation_allowed": False,
        "migrations_required_before_observe": False,
        "prepared_schema_required_before_observe": False,
        "cross_tenant_write_probe_allowed": False,
        "postgres18_required": True,
        "tls_verify_full_required": True,
        "bootstrap_authority_identity_required": True,
        "runtime_role_identity_required": True,
        "existing_product_residue_must_be_clean": True,
        "local_ca_materialization_allowed": True,
    }
    if observe != expected:
        raise CutoverContractError("TIMEWEB_PG_CUTOVER_OBSERVE_INVALID")
    operations = _mapping(
        payload.get("operations"),
        "TIMEWEB_PG_CUTOVER_OPERATIONS_INVALID",
    )
    if operations.get("observe") != "READ_ONLY_PREPARE_PREREQUISITE_VERIFICATION":
        raise CutoverContractError("TIMEWEB_PG_CUTOVER_OPERATIONS_INVALID")


def _validate_protected_invariants(payload: dict[str, Any]) -> None:
    _false_map(
        payload.get("protected_invariants"),
        (
            "PUBLIC_MULTI_USER_ENABLED",
            "OMNI_V10_TELEGRAM_LOGIN_ENABLED",
            "OMNI_V10_VK_ID_LOGIN_ENABLED",
            "broker_write",
            "trading_methods",
            "REAL_TRADING_ENABLED",
            "canonical_domain_mutation",
            "web_visual_started",
            "wp23_unlocked",
        ),
        "TIMEWEB_PG_CUTOVER_AUTHORITY_WIDENED",
    )


def _validate_contract(payload: dict[str, Any]) -> None:
    expected_root = {
        "schema": "omni-cio.v10.timeweb-postgres-production-cutover.v1",
        "status": "OWNER_APPROVED_BRANCH_LOCAL_IMPLEMENTATION_VERIFICATION_PENDING",
        "owning_system_update": "TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED",
        "owning_pr": 584,
        "milestone": "P3_POSTGRES18_PRODUCTION_CUTOVER",
    }
    if any(payload.get(key) != value for key, value in expected_root.items()):
        raise CutoverContractError("TIMEWEB_PG_CUTOVER_IDENTITY_DRIFT")
    _validate_target(payload)
    _validate_transport(payload)
    _validate_connection_retry(payload)
    _validate_runtime_role(payload)
    _validate_prepare(payload)
    _validate_recovery(payload)
    _validate_app_binding(payload)
    _validate_github(payload)
    _validate_observe(payload)
    _validate_protected_invariants(payload)


def _validate_workflow_secret_scope(workflow: str) -> None:
    expected_counts = {
        _CONTROL_PLANE_SECRET: 1,
        _BOOTSTRAP_DSN_SECRET: 3,
        _RUNTIME_DSN_SECRET: 3,
    }
    for reference, expected_count in expected_counts.items():
        if workflow.count(reference) != expected_count:
            raise CutoverContractError("TIMEWEB_PG_CUTOVER_WORKFLOW_SECRET_SCOPE_DRIFT")
    if _RECOVERY_ATTESTATION_SECRET in workflow:
        raise CutoverContractError(
            "TIMEWEB_PG_CUTOVER_RECOVERY_ATTESTATION_SECRET_FORBIDDEN"
        )


def _direct_call_names(source: str, function_name: str) -> set[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise CutoverContractError(
            "TIMEWEB_PG_CUTOVER_CONTROLLER_SYNTAX_INVALID"
        ) from exc
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == function_name
    ]
    if len(functions) != 1:
        raise CutoverContractError("TIMEWEB_PG_CUTOVER_CONTROLLER_FUNCTION_INVALID")
    calls: set[str] = set()
    for node in ast.walk(functions[0]):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            calls.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            calls.add(node.func.attr)
    return calls


def _validate_sources() -> None:
    controller = _text(CONTROLLER)
    _markers(
        controller,
        (
            f'PREPARE_CONFIRMATION = "{_PREPARE_CONFIRMATION}"',
            'RUNTIME_ROLE = "omni_cio_hosted_api"',
            '"verify-full"',
            "_SHA256_RE",
            "_recovery_evidence_sha256",
            "require_postgres_18",
            "apply_migrations(bootstrap)",
            "postgres_runtime.render_runtime_sql(RUNTIME_ROLE)",
            "probe_hosted_runtime_database",
            "_verify_runtime_role_identity",
            "_require_observed_clean_product_state",
            "_observe_database",
            "_verify_cross_tenant_negative(runtime)",
            "_PRODUCTION_CONNECT_RETRY_DELAYS = (",
            "retry_delays=_PRODUCTION_CONNECT_RETRY_DELAYS",
            "timeweb_postgres_tls.install_timeweb_postgres_ca()",
            "timeweb_postgres_tls.probe_timeweb_postgres_transport(",
            "timeweb_postgres_tls.resolve_timeweb_postgres_dsn(",
            "timeweb_postgres_tls.connect_prepared_timeweb_postgres(",
            "TIMEWEB_PG_PRODUCTION_TARGET_NOT_CLEAN",
            "TIMEWEB_PG_PRODUCTION_APP_SHAPE_DRIFT",
            "TIMEWEB_PG_PRODUCTION_APP_DSN_NOT_PROMOTED",
            "--recovery-attestation",
            "--recovery-evidence-sha256",
            "TIMEWEB_POSTGRES_PRODUCTION_CUTOVER=ACCEPTED",
        ),
        "TIMEWEB_PG_CUTOVER_CONTROLLER_DRIFT",
    )
    observe_calls = _direct_call_names(controller, "_observe_database")
    forbidden_observe_calls = {
        "apply_migrations",
        "_prepare_database",
        "_verify_runtime_database",
        "_verify_cross_tenant_negative",
        "render_runtime_sql",
    }
    if observe_calls & forbidden_observe_calls:
        raise CutoverContractError("TIMEWEB_PG_CUTOVER_OBSERVE_MUTATION_PATH")

    if any(
        item in controller
        for item in (
            "DROP DATABASE",
            "DROP SCHEMA",
            "TRUNCATE ",
            "sslmode=disable",
            "CREATE ROLE",
            "ALTER ROLE",
        )
    ):
        raise CutoverContractError("TIMEWEB_PG_CUTOVER_CONTROLLER_AUTHORITY_WIDENED")

    tls_source = _text(TIMEWEB_TLS)
    _markers(
        tls_source,
        (
            'TIMEWEB_POSTGRES_CA_URL = "https://st.timeweb.com/cloud-static/ca.crt"',
            'TIMEWEB_POSTGRES_SSLROOTCERT = ".omni-cio/timeweb-postgres-root.crt"',
            "_NoRedirectHandler",
            "TIMEWEB_PG_TLS_TECHNICAL_DOMAIN_REQUIRED",
            "TIMEWEB_PG_TLS_PROVIDER_TECHNICAL_DOMAIN_REQUIRED",
            "_TIMEWEB_TECHNICAL_DOMAIN_SUFFIXES",
            "_ALLOWED_EXTERNAL_DSN_PARAMETERS",
            "_FORBIDDEN_LIBPQ_ENVIRONMENT",
            "TIMEWEB_PG_TLS_AMBIENT_LIBPQ_ENV_FORBIDDEN",
            "TIMEWEB_PG_TLS_DSN_PARAMETER_FORBIDDEN",
            "TIMEWEB_PG_TLS_VERIFIED_HOSTADDR_INVALID",
            "TIMEWEB_PG_TLS_PASSWORD_REQUIRED",
            "TIMEWEB_PG_TLS_RESOLUTION_NOT_PUBLIC",
            "TIMEWEB_PG_TLS_TCP_TIMEOUT",
            "TIMEWEB_PG_TLS_SSLREQUEST_REFUSED",
            "TIMEWEB_PG_TLS_CERT_VERIFY_FAILED",
            "UNCLASSIFIED_CLIENT_FAILURE",
            "TIMEWEB_PG_TLS_VERIFY_FULL_REQUIRED",
            "TIMEWEB_PG_TLS_ROOT_CERT_PATH_INVALID",
            "probe_timeweb_postgres_transport(",
            "connect_prepared_timeweb_postgres(",
            "os.replace(temporary, target)",
            "make_conninfo(dsn, sslrootcert=str(absolute_ca))",
        ),
        "TIMEWEB_PG_CUTOVER_TLS_RUNTIME_DRIFT",
    )

    _markers(
        _text(HOSTED_RUNTIME),
        (
            "connect_prepared_timeweb_postgres",
            "prepare_timeweb_postgres_tls",
            "database_dsn = prepare_timeweb_postgres_tls(_required_env(_DSN_ENV))",
            'failure_prefix="HOSTED_RUNTIME_DATABASE"',
        ),
        "TIMEWEB_PG_CUTOVER_HOSTED_RUNTIME_TLS_DRIFT",
    )

    workflow = _text(WORKFLOW)
    _markers(
        workflow,
        (
            "workflow_dispatch:",
            "expected_main_sha:",
            "recovery_attestation:",
            "recovery_evidence_sha256:",
            "timeweb-production",
            _PREPARE_CONFIRMATION,
            "Observe verified production database",
            "Prepare verified production database",
            "Accept verified production database",
            "OMNI_V10_TIMEWEB_PROD_BOOTSTRAP_DSN",
            "OMNI_V10_TIMEWEB_PROD_RUNTIME_DSN",
            "TIMEWEB_CLOUD_API_TOKEN",
            "scripts.timeweb_postgres_production_cutover",
        ),
        "TIMEWEB_PG_CUTOVER_WORKFLOW_DRIFT",
    )
    _validate_workflow_secret_scope(workflow)
    if workflow.count("python -m scripts.verify_v10_timeweb_github_environment") != 2:
        raise CutoverContractError("TIMEWEB_PG_CUTOVER_ENVIRONMENT_REVERIFY_MISSING")
    if any(
        item in workflow for item in ("\n  push:", "\n  pull_request:", "schedule:")
    ):
        raise CutoverContractError("TIMEWEB_PG_CUTOVER_WORKFLOW_AUTO_TRIGGER_FORBIDDEN")

    _markers(
        _text(RUNBOOK),
        (
            "distinct from the historical synthetic parity target",
            "physical backup recovery point",
            "separate restore rehearsal",
            "recovery_evidence_sha256",
            "not credentials",
            "Do not invent an undocumented endpoint",
            "timeweb-production",
            "Selected branches and tags",
            "Branch `main`",
            "Portable CA / DSN rule",
            "Credential-free connection-readiness ladder",
            "sslrootcert=.omni-cio/timeweb-postgres-root.crt",
            "TIMEWEB_PG_TLS_TRANSPORT=READY",
            "pgsql:host=...",
            "The observe phase is SQL read-only",
            "36276384123",
            "Only after P3 acceptance may P4",
        ),
        "TIMEWEB_PG_CUTOVER_RUNBOOK_DRIFT",
    )
    if _json(RUNTIME).get("schema_version") != "v10.hosted-postgres-runtime.v5":
        raise CutoverContractError("TIMEWEB_PG_CUTOVER_RUNTIME_CONTRACT_INVALID")
    if _json(RECOVERY).get("schema_version") != "v10.hosted-recovery.v2":
        raise CutoverContractError("TIMEWEB_PG_CUTOVER_RECOVERY_CONTRACT_INVALID")


def validate(root: Path = ROOT) -> None:
    global ROOT, CONTRACT, RUNBOOK, CONTROLLER, HOSTED_RUNTIME, TIMEWEB_TLS
    global WORKFLOW, RUNTIME, RECOVERY
    old = (
        ROOT,
        CONTRACT,
        RUNBOOK,
        CONTROLLER,
        HOSTED_RUNTIME,
        TIMEWEB_TLS,
        WORKFLOW,
        RUNTIME,
        RECOVERY,
    )
    if root != ROOT:
        ROOT = root
        CONTRACT = (
            root
            / "docs/architecture/V10_TIMEWEB_POSTGRES_PRODUCTION_CUTOVER_CONTRACT.json"
        )
        RUNBOOK = (
            root / "docs/operations/V10_TIMEWEB_POSTGRES_PRODUCTION_CUTOVER_RUNBOOK.md"
        )
        CONTROLLER = root / "scripts/timeweb_postgres_production_cutover.py"
        HOSTED_RUNTIME = root / "apps/api/hosted_runtime.py"
        TIMEWEB_TLS = root / "apps/api/timeweb_postgres_tls.py"
        WORKFLOW = (
            root / ".github/workflows/v10-timeweb-postgres-production-cutover.yml"
        )
        RUNTIME = root / "infrastructure/postgres/hosted-postgres-runtime-contract.json"
        RECOVERY = root / "infrastructure/postgres/hosted-recovery-contract.json"
    try:
        _validate_contract(_json(CONTRACT))
        _validate_sources()
    finally:
        (
            ROOT,
            CONTRACT,
            RUNBOOK,
            CONTROLLER,
            HOSTED_RUNTIME,
            TIMEWEB_TLS,
            WORKFLOW,
            RUNTIME,
            RECOVERY,
        ) = old


def main() -> int:
    try:
        validate()
    except CutoverContractError as exc:
        print(
            f"V10_TIMEWEB_POSTGRES_PRODUCTION_CUTOVER=FAIL code={exc}",
            file=sys.stderr,
        )
        return 1
    print(
        "V10_TIMEWEB_POSTGRES_PRODUCTION_CUTOVER=PASS "
        "repository_implementation=bounded external_cutover=fail_closed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
