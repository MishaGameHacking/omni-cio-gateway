from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    ROOT / "docs/architecture/V10_RU_POSTGRES_TIMEWEB_CONTROL_PLANE_CONTRACT.json"
)
PROBE = ROOT / "scripts/probe_v10_timeweb_postgres_control_plane.py"
ENVIRONMENT_VERIFIER = ROOT / "scripts/verify_v10_timeweb_github_environment.py"
RUNBOOK = ROOT / "docs/operations/V10_RU_POSTGRES_TIMEWEB_CONTROL_PLANE_RUNBOOK.md"
WORKFLOWS = ROOT / ".github/workflows"
LIVE_WORKFLOW = WORKFLOWS / "v10-timeweb-postgres-readonly-proof.yml"
SYNTHETIC_CREATE_WORKFLOW = WORKFLOWS / "v10-timeweb-postgres-synthetic-create.yml"
PUBLIC_IPV4_TLS_WORKFLOW = WORKFLOWS / "v10-timeweb-postgres-public-ipv4-tls.yml"
TIMEWEB_ALLOCATION_WORKFLOW = WORKFLOWS / "v10-timeweb-ipv4-allocation.yml"
APP_CANDIDATE_WORKFLOW = WORKFLOWS / "v10-timeweb-app-candidate.yml"
PRODUCTION_CUTOVER_WORKFLOW = (
    WORKFLOWS / "v10-timeweb-postgres-production-cutover.yml"
)
_TIMEWEB_BINDING = "TIMEWEB_CLOUD_API_" + "TOKEN"
_ENVIRONMENT_NAME = "timeweb-synthetic"
_PRODUCTION_ENVIRONMENT_NAME = "timeweb-production"
_ENVIRONMENT_GATE_MARKER = "TIMEWEB_GITHUB_ENVIRONMENT_GATE=READY"
_CLUSTER_DETAIL_ENDPOINT = "/api/v1/databases/{cluster_id}"
_REPLICA_TOPOLOGY_MARKER = "TIMEWEB_RU_PG_REPLICA_TOPOLOGY=OBSERVED"
_REGRESSION_SHIELD_WORKFLOW = "Regression Shield"


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError("TIMEWEB_CONTROL_PLANE_SOURCE_UNREADABLE") from exc


def _load_contract() -> dict[str, Any]:
    try:
        payload = json.loads(_read(CONTRACT))
    except json.JSONDecodeError as exc:
        raise RuntimeError("TIMEWEB_CONTROL_PLANE_CONTRACT_INVALID") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("TIMEWEB_CONTROL_PLANE_CONTRACT_INVALID")
    return payload


def _mapping(value: object, code: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(code)
    return value


def _require(actual: object, expected: object, code: str) -> None:
    if actual != expected:
        raise RuntimeError(code)


def _require_markers(source: str, markers: tuple[str, ...], code: str) -> None:
    for marker in markers:
        if marker not in source:
            raise RuntimeError(code)


def _require_fields(
    source: dict[str, Any],
    expectations: tuple[tuple[str, object, str], ...],
) -> None:
    for key, expected, code in expectations:
        _require(source.get(key), expected, code)


def _validate_contract(payload: dict[str, Any]) -> None:
    _require_fields(
        payload,
        (
            (
                "schema",
                "omni-cio.v10.ru-postgres-timeweb-control-plane-readonly.v1",
                "TIMEWEB_CONTROL_PLANE_SCHEMA_INVALID",
            ),
            (
                "stage",
                "RU-PG-B_TIMEWEB_CONTROL_PLANE_READ_ONLY_PROOF",
                "TIMEWEB_CONTROL_PLANE_STAGE_INVALID",
            ),
            (
                "status",
                "SOURCE_READY_MACHINE_ENVIRONMENT_GATE_PENDING_LIVE_EVIDENCE",
                "TIMEWEB_CONTROL_PLANE_STATUS_INVALID",
            ),
            (
                "accepted_base_sha_parts",
                [
                    "3a1bd050",
                    "d596b2e0",
                    "5f73a72f",
                    "93199f4e",
                    "2944f94b",
                ],
                "TIMEWEB_CONTROL_PLANE_BASE_INVALID",
            ),
        ),
    )
    _validate_environment_contract(payload)
    _validate_api_contract(payload)
    _validate_credential_health_contract(payload)
    _validate_replica_topology_contract(payload)
    _validate_beta_contract(payload)
    _validate_mutation_contract(payload)
    _validate_iac_contract(payload)


def _validate_environment_contract(payload: dict[str, Any]) -> None:
    environment = _mapping(
        payload.get("environment_gate"),
        "TIMEWEB_CONTROL_PLANE_ENVIRONMENT_INVALID",
    )
    _require_fields(
        environment,
        (
            ("name", _ENVIRONMENT_NAME, "TIMEWEB_CONTROL_PLANE_ENVIRONMENT_INVALID"),
            (
                "environment_variable_parts",
                ["TIMEWEB_CLOUD_API_", "TOKEN"],
                "TIMEWEB_CONTROL_PLANE_ENVIRONMENT_INVALID",
            ),
            (
                "selected_branch_required",
                "main",
                "TIMEWEB_CONTROL_PLANE_ENVIRONMENT_INVALID",
            ),
            (
                "unrestricted_deployment_refs_allowed",
                False,
                "TIMEWEB_CONTROL_PLANE_ENVIRONMENT_INVALID",
            ),
            (
                "environment_hardening_accepted",
                False,
                "TIMEWEB_CONTROL_PLANE_ENVIRONMENT_EVIDENCE_INVALID",
            ),
            (
                "owner_ui_hardening_evidence_required",
                False,
                "TIMEWEB_CONTROL_PLANE_ENVIRONMENT_EVIDENCE_INVALID",
            ),
            (
                "machine_api_hardening_evidence_required",
                True,
                "TIMEWEB_CONTROL_PLANE_ENVIRONMENT_EVIDENCE_INVALID",
            ),
            (
                "machine_gate_marker",
                _ENVIRONMENT_GATE_MARKER,
                "TIMEWEB_CONTROL_PLANE_ENVIRONMENT_EVIDENCE_INVALID",
            ),
            (
                "github_actions_read_permission_required",
                True,
                "TIMEWEB_CONTROL_PLANE_WORKFLOW_AUTHORITY_INVALID",
            ),
            (
                "pre_secret_environment_policy_job_required",
                True,
                "TIMEWEB_CONTROL_PLANE_WORKFLOW_AUTHORITY_INVALID",
            ),
            (
                "pre_provider_revalidation_required",
                True,
                "TIMEWEB_CONTROL_PLANE_WORKFLOW_AUTHORITY_INVALID",
            ),
            (
                "exact_custom_branch_patterns",
                ["main"],
                "TIMEWEB_CONTROL_PLANE_ENVIRONMENT_EVIDENCE_INVALID",
            ),
            (
                "api_branch_type_must_be_branch_if_exposed",
                True,
                "TIMEWEB_CONTROL_PLANE_ENVIRONMENT_EVIDENCE_INVALID",
            ),
            (
                "runtime_ref_kind_enforcement_required",
                True,
                "TIMEWEB_CONTROL_PLANE_WORKFLOW_AUTHORITY_INVALID",
            ),
            (
                "secret_consumption_allowed_before_environment_gate",
                False,
                "TIMEWEB_CONTROL_PLANE_SECRET_AUTHORITY_INVALID",
            ),
            (
                "secret_consumption_allowed_after_environment_gate",
                True,
                "TIMEWEB_CONTROL_PLANE_SECRET_AUTHORITY_INVALID",
            ),
            (
                "workflow_dispatch_main_only",
                True,
                "TIMEWEB_CONTROL_PLANE_WORKFLOW_AUTHORITY_INVALID",
            ),
            (
                "workflow_path",
                ".github/workflows/v10-timeweb-postgres-readonly-proof.yml",
                "TIMEWEB_CONTROL_PLANE_WORKFLOW_AUTHORITY_INVALID",
            ),
            (
                "api_endpoints",
                [
                    "/repos/{owner}/{repo}/environments/timeweb-synthetic",
                    "/repos/{owner}/{repo}/environments/timeweb-synthetic/"
                    "deployment-branch-policies?per_page=100&page=1",
                ],
                "TIMEWEB_CONTROL_PLANE_ENVIRONMENT_EVIDENCE_INVALID",
            ),
        ),
    )
    automatic = _mapping(
        environment.get("automatic_read_only_proof"),
        "TIMEWEB_CONTROL_PLANE_AUTO_PROOF_INVALID",
    )
    _require(
        automatic,
        {
            "enabled": True,
            "trigger_event": "workflow_run",
            "upstream_workflow": _REGRESSION_SHIELD_WORKFLOW,
            "upstream_conclusion_required": "success",
            "upstream_event_required": "push",
            "upstream_head_branch_required": "main",
            "expected_head_source": "github.event.workflow_run.head_sha",
            "current_main_equality_required": True,
            "manual_workflow_dispatch_fallback_preserved": True,
            "provider_mutation_authority_inherited": False,
            "paid_transition_authority_inherited": False,
            "retired_provider_dependency_allowed": False,
        },
        "TIMEWEB_CONTROL_PLANE_AUTO_PROOF_INVALID",
    )


def _validate_api_contract(payload: dict[str, Any]) -> None:
    api = _mapping(payload.get("api_boundary"), "TIMEWEB_CONTROL_PLANE_API_INVALID")
    _require_fields(
        api,
        (
            ("allowed_methods", ["GET"], "TIMEWEB_CONTROL_PLANE_METHOD_INVALID"),
            (
                "mutation_methods_allowed",
                False,
                "TIMEWEB_CONTROL_PLANE_METHOD_INVALID",
            ),
            ("redirects_allowed", False, "TIMEWEB_CONTROL_PLANE_REDIRECT_INVALID"),
            (
                "response_body_logging_allowed",
                False,
                "TIMEWEB_CONTROL_PLANE_OUTPUT_INVALID",
            ),
            (
                "provider_identifiers_in_output_allowed",
                False,
                "TIMEWEB_CONTROL_PLANE_OUTPUT_INVALID",
            ),
            (
                "endpoints",
                [
                    "/api/v1/projects",
                    "/api/v1/database-types",
                    "/api/v2/presets/dbs",
                    "/api/v1/projects/{project_id}/resources/databases",
                    _CLUSTER_DETAIL_ENDPOINT,
                ],
                "TIMEWEB_CONTROL_PLANE_API_INVALID",
            ),
        ),
    )


def _validate_credential_health_contract(payload: dict[str, Any]) -> None:
    health = _mapping(
        payload.get("credential_health"),
        "TIMEWEB_CONTROL_PLANE_CREDENTIAL_HEALTH_INVALID",
    )
    _require(
        health,
        {
            "preflight_endpoint": "/api/v1/projects",
            "exact_project_selection_required": True,
            "authentication_status": 401,
            "authentication_code": "TIMEWEB_API_AUTHENTICATION_REJECTED",
            "authorization_status": 403,
            "authorization_code": "TIMEWEB_API_AUTHORIZATION_REJECTED",
            "auth_failures_retryable": False,
            "response_body_logging_allowed": False,
            "token_value_logging_allowed": False,
            "mutation_adapter_requires_successful_read_preflight": True,
            "credential_rotation_is_external_owner_action": True,
        },
        "TIMEWEB_CONTROL_PLANE_CREDENTIAL_HEALTH_INVALID",
    )


def _validate_replica_topology_contract(payload: dict[str, Any]) -> None:
    topology = _mapping(
        payload.get("replica_topology_diagnostic"),
        "TIMEWEB_REPLICA_TOPOLOGY_CONTRACT_INVALID",
    )
    _require(
        topology,
        {
            "enabled": True,
            "existing_target_only": True,
            "cluster_detail_endpoint": _CLUSTER_DETAIL_ENDPOINT,
            "accepted_marker": _REPLICA_TOPOLOGY_MARKER,
            "sanitized_output_fields": [
                "replica_list_count",
                "contract_replica_list_count",
                "relation",
                "semantics",
            ],
            "provider_identifiers_in_output_allowed": False,
            "response_body_logging_allowed": False,
            "mutation_allowed": False,
            "provider_semantics_resolved": False,
            "paid_replica_authority_inferred_from_observation": False,
            "accepted_provider_baseline_count": 1,
            "accepted_live_evidence_workflow_run": 35507498165,
            "accepted_live_evidence_exact_main_sha_parts": [
                "3a96dfe8",
                "8e99aac7",
                "54d89497",
                "25122295",
                "dd957429",
            ],
            "additional_paid_replication_authorized": False,
        },
        "TIMEWEB_REPLICA_TOPOLOGY_CONTRACT_INVALID",
    )


def _validate_beta_contract(payload: dict[str, Any]) -> None:
    beta = _mapping(payload.get("beta_target"), "TIMEWEB_CONTROL_PLANE_BETA_INVALID")
    expected_beta = {
        "cpu": 1,
        "ram_mb": 2048,
        "disk_mb": 20480,
        "base_monthly_price_rub": 790,
        "public_ipv4_authorized": False,
        "backup_storage_addon_authorized": False,
        "provider_replica_list_count": 1,
        "additional_paid_replication_authorized": False,
        "auto_scaling_authorized": False,
    }
    _require(beta, expected_beta, "TIMEWEB_CONTROL_PLANE_BETA_INVALID")

    canonical = _mapping(
        payload.get("canonical_replica_topology"),
        "TIMEWEB_REPLICA_TOPOLOGY_CONTRACT_INVALID",
    )
    _require(
        canonical,
        {
            "provider_field": "replica_list",
            "expected_provider_replica_list_count": 1,
            "accepted_live_evidence_workflow_run": 35507498165,
            "accepted_live_evidence_exact_main_sha_parts": [
                "3a96dfe8",
                "8e99aac7",
                "54d89497",
                "25122295",
                "dd957429",
            ],
            "terminal_exact_count_required": True,
            "starting_missing_or_empty_allowed": True,
            "cluster_custody_field": "db_id",
            "cross_cluster_members_forbidden": True,
            "duplicate_member_ids_forbidden": True,
            "additional_paid_replication_authorized": False,
            "provider_semantics_resolved": False,
        },
        "TIMEWEB_REPLICA_TOPOLOGY_CONTRACT_INVALID",
    )


def _validate_mutation_contract(payload: dict[str, Any]) -> None:
    mutation = _mapping(
        payload.get("provider_mutation"),
        "TIMEWEB_CONTROL_PLANE_MUTATION_INVALID",
    )
    for key in (
        "cluster_create_allowed",
        "cluster_update_allowed",
        "cluster_delete_allowed",
        "public_ip_create_allowed",
        "network_mutation_allowed",
        "production_dsn_mutation_allowed",
    ):
        _require(mutation.get(key), False, "TIMEWEB_CONTROL_PLANE_MUTATION_INVALID")
    _require(
        mutation.get("neon_production_authority_preserved"),
        False,
        "TIMEWEB_CONTROL_PLANE_NEON_AUTHORITY_INVALID",
    )
    _require(
        mutation.get("neon_rollback_available"),
        False,
        "TIMEWEB_CONTROL_PLANE_NEON_AUTHORITY_INVALID",
    )
    _require(
        mutation.get("neon_state_source"),
        "OWNER_REPORTED_EXTERNAL_DECOMMISSION",
        "TIMEWEB_CONTROL_PLANE_NEON_AUTHORITY_INVALID",
    )


def _validate_iac_contract(payload: dict[str, Any]) -> None:
    iac = _mapping(
        payload.get("infrastructure_as_code"),
        "TIMEWEB_CONTROL_PLANE_IAC_INVALID",
    )
    _require_fields(
        iac,
        (
            (
                "timeweb_terraform_mutation_allowed",
                False,
                "TIMEWEB_CONTROL_PLANE_IAC_INVALID",
            ),
            (
                "direct_public_api_adapter_selected",
                True,
                "TIMEWEB_CONTROL_PLANE_IAC_INVALID",
            ),
        ),
    )


def _validate_probe_source() -> None:
    source = _read(PROBE)
    _require_markers(
        source,
        (
            'API_BASE = "https://api.timeweb.cloud"',
            'TOKEN_ENV = "TIMEWEB_CLOUD_API_TOKEN"',
            'TARGET_PROJECT_NAME = "Общий проект"',
            'TARGET_CLUSTER_NAME = "omni-cio-v10-ru-pg-synthetic"',
            'TARGET_LOCATION = "ru-3"',
            "PROVIDER_CLUSTER_DISK_KB_PER_PRESET_MB = 1024",
            "TARGET_DISK_KB = TARGET_DISK_MB * PROVIDER_CLUSTER_DISK_KB_PER_PRESET_MB",
            "def _cluster_disk_size_kb(",
            "def _require_target_cluster_disk(",
            'TARGET_PRICE_RUB = Decimal("790")',
            "TARGET_PROVIDER_REPLICA_LIST_COUNT = 1",
            "ADDITIONAL_PAID_REPLICATION_AUTHORIZED = False",
            "def _provider_replica_list_count(",
            "def _require_target_replica_topology(",
            "TIMEWEB_CLUSTER_REPLICA_MEMBER_DUPLICATE",
            "TIMEWEB_CLUSTER_REPLICA_TOPOLOGY_DRIFT",
            'method="GET"',
            "_NO_REDIRECT_OPENER",
            "MAX_RESPONSE_BYTES + 1",
            'AUTHENTICATION_REJECTED_CODE = "TIMEWEB_API_AUTHENTICATION_REJECTED"',
            'AUTHORIZATION_REJECTED_CODE = "TIMEWEB_API_AUTHORIZATION_REJECTED"',
            "def raise_timeweb_auth_failure(",
            "def verify_credential_health(",
            "project_id = verify_credential_health(api)",
            'api.get("/api/v1/database-types")',
            'api.get("/api/v2/presets/dbs")',
            "TIMEWEB_BETA_PRESET_NOT_UNIQUE_OR_PRICE_DRIFT",
            "def _target_cluster_id(",
            "def _replica_topology_observation(",
            'api.get(f"' + _CLUSTER_DETAIL_ENDPOINT + '")',
            _REPLICA_TOPOLOGY_MARKER,
            "contract_replica_list_count=",
            "semantics=COUNT_ONLY_BASELINE",
            "TIMEWEB_RU_PG_CONTROL_PLANE=READ_ONLY_READY",
        ),
        "TIMEWEB_CONTROL_PLANE_PROBE_DRIFT",
    )
    forbidden = (
        'method="POST"',
        'method="PUT"',
        'method="PATCH"',
        'method="DELETE"',
        ".post(",
        ".put(",
        ".patch(",
        ".delete(",
        "OMNI_V10_POSTGRES_DSN",
        "NEON_API_KEY",
    )
    if any(marker in source for marker in forbidden):
        raise RuntimeError("TIMEWEB_CONTROL_PLANE_MUTATION_SOURCE_PRESENT")
    if "TIMEWEB_API_TOKEN_INVALID_OR_INSUFFICIENT" in source:
        raise RuntimeError("TIMEWEB_CONTROL_PLANE_AUTH_CLASSIFICATION_DRIFT")


def _validate_environment_verifier_source() -> None:
    source = _read(ENVIRONMENT_VERIFIER)
    _require_markers(
        source,
        (
            'API_BASE = "https://api.github.com"',
            'API_VERSION = "2026-03-10"',
            'ENVIRONMENT_NAME = "timeweb-synthetic"',
            'PRODUCTION_ENVIRONMENT_NAME = "timeweb-production"',
            "--environment-name",
            'EXPECTED_BRANCH_PATTERN = "main"',
            'method="GET"',
            "_NO_REDIRECT_OPENER",
            "MAX_RESPONSE_BYTES + 1",
            "deployment_branch_policy",
            "custom_branch_policies",
            "protected_branches",
            "branch_policies",
            _ENVIRONMENT_GATE_MARKER,
        ),
        "TIMEWEB_CONTROL_PLANE_ENVIRONMENT_VERIFIER_DRIFT",
    )
    forbidden = (
        'method="POST"',
        'method="PUT"',
        'method="PATCH"',
        'method="DELETE"',
        ".post(",
        ".put(",
        ".patch(",
        ".delete(",
        "TIMEWEB_CLOUD_API_TOKEN",
        "OMNI_V10_POSTGRES_DSN",
    )
    if any(marker in source for marker in forbidden):
        raise RuntimeError(
            "TIMEWEB_CONTROL_PLANE_ENVIRONMENT_VERIFIER_MUTATION_SURFACE"
        )


def _validate_live_workflow() -> None:
    source = _read(LIVE_WORKFLOW)
    _require_markers(
        source,
        (
            "workflow_dispatch:",
            "workflow_run:",
            _REGRESSION_SHIELD_WORKFLOW,
            "github.event.workflow_run.conclusion == 'success'",
            "github.event.workflow_run.event == 'push'",
            "github.event.workflow_run.head_branch == 'main'",
            "github.event.workflow_run.head_sha",
            'test "$EXPECTED_BRANCH" = "main"',
            "refs/heads/main:refs/remotes/origin/main",
            'test "$(git rev-parse refs/remotes/origin/main)" = "$EXPECTED_HEAD"',
            "actions: read",
            "contents: read",
            "environment-policy-proof:",
            "needs: environment-policy-proof",
            f"environment: {_ENVIRONMENT_NAME}",
            f"{_TIMEWEB_BINDING}: ${{{{ secrets.{_TIMEWEB_BINDING} }}}}",
            "python scripts/check_v10_timeweb_postgres_control_plane.py",
            "python -m scripts.verify_v10_timeweb_github_environment",
            "python -m scripts.probe_v10_timeweb_postgres_control_plane",
            "git clean -ffdx",
        ),
        "TIMEWEB_CONTROL_PLANE_WORKFLOW_DRIFT",
    )
    verifier_marker = "python -m scripts.verify_v10_timeweb_github_environment"
    if source.count(verifier_marker) != 2:
        raise RuntimeError("TIMEWEB_CONTROL_PLANE_ENVIRONMENT_VERIFIER_ORDER_INVALID")
    environment_job = source.find("environment-policy-proof:")
    proof_job = source.find("read-only-proof:")
    secret_binding = source.find(
        f"{_TIMEWEB_BINDING}: ${{{{ secrets.{_TIMEWEB_BINDING} }}}}"
    )
    second_verifier = source.rfind(verifier_marker, 0, secret_binding)
    if not (
        0 <= environment_job < proof_job
        and proof_job < source.find(f"environment: {_ENVIRONMENT_NAME}", proof_job)
        and proof_job < second_verifier < secret_binding
    ):
        raise RuntimeError("TIMEWEB_CONTROL_PLANE_ENVIRONMENT_VERIFIER_ORDER_INVALID")

    forbidden = (
        "on:\n  push:",
        "pull_request:",
        "schedule:",
        "curl ",
        "Invoke-RestMethod",
        "Invoke-WebRequest",
        "method=POST",
        "method=PUT",
        "method=PATCH",
        "method=DELETE",
        "provision_v10_ru_postgres",
        "OMNI_V10_POSTGRES_DSN",
    )
    if any(marker in source for marker in forbidden):
        raise RuntimeError("TIMEWEB_CONTROL_PLANE_WORKFLOW_MUTATION_SURFACE")


def _validate_timeweb_secret_scope() -> None:
    secret_bearing = {
        LIVE_WORKFLOW.resolve(),
        SYNTHETIC_CREATE_WORKFLOW.resolve(),
        PUBLIC_IPV4_TLS_WORKFLOW.resolve(),
        TIMEWEB_ALLOCATION_WORKFLOW.resolve(),
        APP_CANDIDATE_WORKFLOW.resolve(),
        PRODUCTION_CUTOVER_WORKFLOW.resolve(),
    }
    synthetic_environment = {
        LIVE_WORKFLOW.resolve(),
        SYNTHETIC_CREATE_WORKFLOW.resolve(),
        PUBLIC_IPV4_TLS_WORKFLOW.resolve(),
        TIMEWEB_ALLOCATION_WORKFLOW.resolve(),
    }
    production_environment = {
        APP_CANDIDATE_WORKFLOW.resolve(),
        PRODUCTION_CUTOVER_WORKFLOW.resolve(),
    }
    for pattern in ("*.yml", "*.yaml"):
        for path in WORKFLOWS.glob(pattern):
            source = _read(path)
            resolved = path.resolve()
            if _TIMEWEB_BINDING in source and resolved not in secret_bearing:
                raise RuntimeError("TIMEWEB_CONTROL_PLANE_SECRET_SCOPE_TOO_BROAD")
            if (
                f"environment: {_ENVIRONMENT_NAME}" in source
                and resolved not in synthetic_environment
            ):
                raise RuntimeError("TIMEWEB_CONTROL_PLANE_ENVIRONMENT_SCOPE_TOO_BROAD")
            if (
                f"environment: {_PRODUCTION_ENVIRONMENT_NAME}" in source
                and resolved not in production_environment
            ):
                raise RuntimeError(
                    "TIMEWEB_CONTROL_PLANE_PRODUCTION_ENVIRONMENT_SCOPE_TOO_BROAD"
                )


def _validate_runbook() -> None:
    source = _read(RUNBOOK)
    _require_markers(
        source,
        (
            "RU-PG-B",
            "read-only",
            _ENVIRONMENT_NAME,
            _TIMEWEB_BINDING,
            "Selected branches and tags",
            "`main`",
            "workflow_dispatch",
            "workflow_run",
            _REGRESSION_SHIELD_WORKFLOW,
            "Terraform",
            "Public API",
            "Neon external authority is unavailable",
            _ENVIRONMENT_GATE_MARKER,
            "TIMEWEB_RU_PG_CONTROL_PLANE=READ_ONLY_READY",
            _REPLICA_TOPOLOGY_MARKER,
            _CLUSTER_DETAIL_ENDPOINT,
            "COUNT_ONLY_BASELINE",
            "additional paid replication remains unauthorized",
            "TIMEWEB_API_AUTHENTICATION_REJECTED",
            "TIMEWEB_API_AUTHORIZATION_REJECTED",
        ),
        "TIMEWEB_CONTROL_PLANE_RUNBOOK_DRIFT",
    )


def validate() -> None:
    _validate_contract(_load_contract())
    _validate_probe_source()
    _validate_environment_verifier_source()
    _validate_live_workflow()
    _validate_timeweb_secret_scope()
    _validate_runbook()


def main() -> int:
    try:
        validate()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(
        "V10 Timeweb RU-PG-B source workflow check passed; "
        "live provider access remains blocked until the machine environment "
        "gate passes."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
