from __future__ import annotations

import ast
import json
from pathlib import Path
import sys
from typing import Any

from scripts.v10_ast_guard import call_lines


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    ROOT / "docs/architecture/V10_RU_POSTGRES_TIMEWEB_SYNTHETIC_CREATE_CONTRACT.json"
)
PROVISIONER = ROOT / "scripts/provision_v10_timeweb_postgres_synthetic.py"
READ_ONLY_PROBE = ROOT / "scripts/probe_v10_timeweb_postgres_control_plane.py"
ENVIRONMENT_VERIFIER = ROOT / "scripts/verify_v10_timeweb_github_environment.py"
RUNBOOK = ROOT / "docs/operations/V10_RU_POSTGRES_TIMEWEB_SYNTHETIC_CREATE_RUNBOOK.md"
WORKFLOW = ROOT / ".github/workflows/v10-timeweb-postgres-synthetic-create.yml"
PUBLIC_IPV4_CONTRACT = (
    ROOT / "docs/architecture/V10_RU_POSTGRES_TIMEWEB_PUBLIC_IPV4_TLS_CONTRACT.json"
)
PUBLIC_IPV4_WORKFLOW = (
    ROOT / ".github/workflows/v10-timeweb-postgres-public-ipv4-tls.yml"
)

_SCHEMA = "omni-cio.v10.ru-postgres-timeweb-synthetic-create.v1"
_STAGE = "RU-PG-B_TIMEWEB_SYNTHETIC_CLUSTER_CREATE"
_STATUS = "SOURCE_READY_PAID_MUTATION_GATED_ON_PARITY_TRANSPORT"
_TIMEWEB_BINDING = "TIMEWEB_CLOUD_API_" + "TOKEN"
_CONFIRMATION = "CREATE_TIMEWEB_RU_PG_SYNTHETIC_790_RUB_MONTH"
_PUBLIC_IPV4_GUARD_MODULE = (
    "python -m scripts.check_v10_timeweb_postgres_public_ipv4_tls"
)
_PUBLIC_IPV4_GUARD_SCRIPT = (
    "python scripts/check_v10_timeweb_postgres_public_ipv4_tls.py"
)
_SYNTHETIC_GUARD_MODULE = (
    "python -m scripts.check_v10_timeweb_postgres_synthetic_create"
)
_SYNTHETIC_GUARD_SCRIPT = (
    "python scripts/check_v10_timeweb_postgres_synthetic_create.py"
)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError("TIMEWEB_SYNTHETIC_CREATE_SOURCE_UNREADABLE") from exc


def _load_contract() -> dict[str, Any]:
    try:
        payload = json.loads(_read(CONTRACT))
    except json.JSONDecodeError as exc:
        raise RuntimeError("TIMEWEB_SYNTHETIC_CREATE_CONTRACT_INVALID") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("TIMEWEB_SYNTHETIC_CREATE_CONTRACT_INVALID")
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


_PROVISIONER_DRIFT = "TIMEWEB_SYNTHETIC_CREATE_PROVISIONER_DRIFT"


def _parse_python_source(source: str) -> ast.Module:
    try:
        return ast.parse(source)
    except SyntaxError as exc:
        raise RuntimeError(_PROVISIONER_DRIFT) from exc


def _find_function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise RuntimeError(_PROVISIONER_DRIFT)


def _find_assignment(function: ast.FunctionDef, name: str) -> ast.Assign:
    for node in function.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(
            isinstance(target, ast.Name) and target.id == name
            for target in node.targets
        ):
            return node
    raise RuntimeError(_PROVISIONER_DRIFT)


def _assignment_sequence(assignment: ast.Assign) -> ast.Tuple | ast.List:
    if isinstance(assignment.value, (ast.Tuple, ast.List)):
        return assignment.value
    raise RuntimeError(_PROVISIONER_DRIFT)


def _decode_expected_entry(
    item: ast.expr,
) -> tuple[str, tuple[object, str]] | None:
    if not isinstance(item, (ast.Tuple, ast.List)) or len(item.elts) != 3:
        return None
    key_node, value_node, code_node = item.elts
    if not isinstance(key_node, ast.Constant) or not isinstance(key_node.value, str):
        return None
    if not isinstance(value_node, ast.Constant):
        return None
    if not isinstance(code_node, ast.Constant) or not isinstance(code_node.value, str):
        return None
    return key_node.value, (value_node.value, code_node.value)


def _terminal_expected_entries(source: str) -> dict[str, tuple[object, str]]:
    tree = _parse_python_source(source)
    function = _find_function(tree, "_verify_terminal_shape")
    assignment = _find_assignment(function, "expected")
    sequence = _assignment_sequence(assignment)

    entries: dict[str, tuple[object, str]] = {}
    for item in sequence.elts:
        decoded = _decode_expected_entry(item)
        if decoded is None:
            continue
        key, value = decoded
        entries[key] = value
    return entries


def _validate_terminal_false_invariants(source: str) -> None:
    entries = _terminal_expected_entries(source)
    required = {
        "is_enabled_public_network": (
            False,
            "TIMEWEB_CLUSTER_PUBLIC_NETWORK_DRIFT",
        ),
        "is_autobackups_enabled": (
            False,
            "TIMEWEB_CLUSTER_AUTOBACKUPS_DRIFT",
        ),
        "is_backup_schedule_enabled": (
            False,
            "TIMEWEB_CLUSTER_BACKUP_SCHEDULE_DRIFT",
        ),
    }
    for key, expected in required.items():
        if entries.get(key) != expected:
            raise RuntimeError(_PROVISIONER_DRIFT)


def _validate_transport_state(
    transport: dict[str, Any],
    target: dict[str, Any],
    *,
    require_ready: bool,
) -> None:
    modes = {
        "TIMEWEB_PRIVATE_VPC_RUNNER": "private_vpc_runner_evidence_accepted",
        "PUBLIC_IPV6_PROVEN": "public_ipv6_reachability_accepted",
        "PUBLIC_IPV4_OWNER_APPROVED": "public_ipv4_owner_approval_recorded",
    }
    evidence = {key: transport.get(key) is True for key in modes.values()}
    status = transport.get("status")
    selected = transport.get("selected_mode")

    if status == "BLOCKED_PENDING_PROOF":
        if selected is not None or any(evidence.values()):
            raise RuntimeError("TIMEWEB_SYNTHETIC_CREATE_TRANSPORT_GATE_INVALID")
        if require_ready:
            raise RuntimeError("TIMEWEB_SYNTHETIC_CREATE_PARITY_TRANSPORT_BLOCKED")
        return

    if status != "READY":
        raise RuntimeError("TIMEWEB_SYNTHETIC_CREATE_TRANSPORT_GATE_INVALID")
    evidence_key = modes.get(selected)
    if evidence_key is None:
        raise RuntimeError("TIMEWEB_SYNTHETIC_CREATE_PARITY_TRANSPORT_INVALID")
    if sum(evidence.values()) != 1 or not evidence[evidence_key]:
        raise RuntimeError("TIMEWEB_SYNTHETIC_CREATE_PARITY_TRANSPORT_INVALID")
    if (
        selected == "PUBLIC_IPV6_PROVEN"
        and target.get("public_ipv6_authorized") is not True
    ):
        raise RuntimeError("TIMEWEB_SYNTHETIC_CREATE_PARITY_TRANSPORT_INVALID")
    if (
        selected == "PUBLIC_IPV4_OWNER_APPROVED"
        and target.get("public_ipv4_authorized") is not True
    ):
        raise RuntimeError("TIMEWEB_SYNTHETIC_CREATE_PARITY_TRANSPORT_INVALID")


def _validate_contract(payload: dict[str, Any]) -> None:
    _require(payload.get("schema"), _SCHEMA, "TIMEWEB_SYNTHETIC_CREATE_SCHEMA_INVALID")
    _require(payload.get("stage"), _STAGE, "TIMEWEB_SYNTHETIC_CREATE_STAGE_INVALID")
    _require(payload.get("status"), _STATUS, "TIMEWEB_SYNTHETIC_CREATE_STATUS_INVALID")
    _require(payload.get("owning_issue"), 559, "TIMEWEB_SYNTHETIC_CREATE_ISSUE_INVALID")
    _require(
        payload.get("accepted_base_sha_parts"),
        ["4987d5ad", "ced8f449", "b482ec1a", "d4165a01", "30c995d3"],
        "TIMEWEB_SYNTHETIC_CREATE_BASE_INVALID",
    )

    prerequisite = _mapping(
        payload.get("prerequisite_evidence"),
        "TIMEWEB_SYNTHETIC_CREATE_PREREQUISITE_INVALID",
    )
    expected_prerequisite = {
        "read_only_workflow_run": 35507498165,
        "environment_gate_marker": "TIMEWEB_GITHUB_ENVIRONMENT_GATE=READY",
        "read_only_marker": "TIMEWEB_RU_PG_CONTROL_PLANE=READ_ONLY_READY",
        "postgres_major": 18,
        "terraform_location": "ru-3",
        "cpu": 1,
        "ram_mb": 2048,
        "disk_mb": 20480,
        "base_monthly_price_rub": 790,
        "target_cluster_name_available": False,
        "existing_target": True,
        "replica_list_count": 1,
        "replica_topology_relation": "matches_contract_count",
    }
    _require(
        prerequisite,
        expected_prerequisite,
        "TIMEWEB_SYNTHETIC_CREATE_PREREQUISITE_INVALID",
    )

    authority = _mapping(
        payload.get("authority"),
        "TIMEWEB_SYNTHETIC_CREATE_AUTHORITY_INVALID",
    )
    expected_authority = {
        "owner_base_cost_approval_recorded": True,
        "authorized_base_monthly_price_rub": 790,
        "fresh_cost_revalidation_before_post_required": True,
        "paid_mutation_allowed_only_after_source_checkpoint_accepted_on_main": True,
        "manual_workflow_dispatch_required": True,
        "exact_main_ref_required": True,
        "environment": "timeweb-synthetic",
        "environment_machine_gate_required": True,
        "provider_secret_step_scope_required": True,
        "parity_transport_ready_required_before_provider_secret_access": True,
    }
    _require(
        authority,
        expected_authority,
        "TIMEWEB_SYNTHETIC_CREATE_AUTHORITY_INVALID",
    )

    transport = _mapping(
        payload.get("parity_transport_gate"),
        "TIMEWEB_SYNTHETIC_CREATE_TRANSPORT_GATE_INVALID",
    )
    expected_modes = [
        "TIMEWEB_PRIVATE_VPC_RUNNER",
        "PUBLIC_IPV6_PROVEN",
        "PUBLIC_IPV4_OWNER_APPROVED",
    ]
    _require(
        transport.get("required_before_provider_secret_access"),
        True,
        "TIMEWEB_SYNTHETIC_CREATE_TRANSPORT_GATE_INVALID",
    )
    _require(
        transport.get("accepted_modes"),
        expected_modes,
        "TIMEWEB_SYNTHETIC_CREATE_TRANSPORT_GATE_INVALID",
    )
    _require(
        transport.get("public_ipv4_recurring_price_rub"),
        200,
        "TIMEWEB_SYNTHETIC_CREATE_TRANSPORT_GATE_INVALID",
    )
    _require(
        transport.get("public_ipv4_price_is_separate_from_base_790"),
        True,
        "TIMEWEB_SYNTHETIC_CREATE_TRANSPORT_GATE_INVALID",
    )
    for key in (
        "public_ipv4_security_source_required",
        "public_ipv4_firewall_drop_required",
        "public_ipv4_tls_verify_full_required",
    ):
        _require(
            transport.get(key),
            True,
            "TIMEWEB_SYNTHETIC_CREATE_TRANSPORT_GATE_INVALID",
        )
    target = _mapping(payload.get("target"), "TIMEWEB_SYNTHETIC_CREATE_TARGET_INVALID")
    expected_target = {
        "provider": "Timeweb Cloud",
        "service": "Managed PostgreSQL",
        "cluster_name": "omni-cio-v10-ru-pg-synthetic",
        "postgres_major": 18,
        "location": "ru-3",
        "availability_zone": "msk-1",
        "cpu": 1,
        "ram_mb": 2048,
        "disk_mb": 20480,
        "public_ipv4_authorized": True,
        "public_ipv6_authorized": False,
        "backup_addon_authorized": False,
        "additional_paid_replication_authorized": False,
        "disk_autoscaling_authorized": False,
        "production_data_allowed": False,
    }
    _require(target, expected_target, "TIMEWEB_SYNTHETIC_CREATE_TARGET_INVALID")
    _validate_transport_state(transport, target, require_ready=False)

    topology = _mapping(
        payload.get("provider_replica_topology"),
        "TIMEWEB_SYNTHETIC_CREATE_REPLICA_TOPOLOGY_INVALID",
    )
    _require(
        topology,
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
        "TIMEWEB_SYNTHETIC_CREATE_REPLICA_TOPOLOGY_INVALID",
    )

    disk_units = _mapping(
        payload.get("provider_disk_units"),
        "TIMEWEB_SYNTHETIC_CREATE_DISK_UNITS_INVALID",
    )
    _require(
        disk_units,
        {
            "preset_disk_unit": "MB",
            "cluster_disk_size_unit": "KB",
            "cluster_kb_per_preset_mb": 1024,
            "exact_integer_cluster_size_required": True,
            "target_cluster_disk_kb": 20971520,
        },
        "TIMEWEB_SYNTHETIC_CREATE_DISK_UNITS_INVALID",
    )

    api = _mapping(
        payload.get("api_boundary"),
        "TIMEWEB_SYNTHETIC_CREATE_API_BOUNDARY_INVALID",
    )
    _require(
        api.get("create_endpoint"),
        "POST /api/v1/databases",
        "TIMEWEB_SYNTHETIC_CREATE_ENDPOINT_INVALID",
    )
    for key in (
        "post_retry_allowed",
        "put_allowed",
        "patch_allowed",
        "delete_allowed",
        "redirects_allowed",
        "response_body_logging_allowed",
        "provider_identifiers_in_output_allowed",
    ):
        _require(api.get(key), False, "TIMEWEB_SYNTHETIC_CREATE_API_BOUNDARY_INVALID")
    _require(
        api.get("ambiguous_post_requires_get_reconciliation"),
        True,
        "TIMEWEB_SYNTHETIC_CREATE_RECONCILIATION_INVALID",
    )
    _require(
        api.get("existing_exact_target_recovery_get_only"),
        True,
        "TIMEWEB_SYNTHETIC_CREATE_RECONCILIATION_INVALID",
    )
    _require(
        api.get("second_post_for_existing_target_allowed"),
        False,
        "TIMEWEB_SYNTHETIC_CREATE_RECONCILIATION_INVALID",
    )
    _require(
        api.get("max_response_bytes"),
        1048576,
        "TIMEWEB_SYNTHETIC_CREATE_API_BOUNDARY_INVALID",
    )

    request = _mapping(
        payload.get("request_shape"),
        "TIMEWEB_SYNTHETIC_CREATE_REQUEST_INVALID",
    )
    _require(
        set(request.get("forbidden_fields", [])),
        {
            "admin",
            "instance",
            "network",
            "replication",
            "auto_backups",
            "backup_schedule",
            "maintenance_slot",
            "configuration",
            "config_parameters",
        },
        "TIMEWEB_SYNTHETIC_CREATE_REQUEST_INVALID",
    )
    _require(
        request.get("exact_availability_zone"),
        "msk-1",
        "TIMEWEB_SYNTHETIC_CREATE_REQUEST_INVALID",
    )
    _require(
        request.get("is_public_ipv6"),
        False,
        "TIMEWEB_SYNTHETIC_CREATE_REQUEST_INVALID",
    )
    _require(
        request.get("disk_autoscaling_enabled"),
        False,
        "TIMEWEB_SYNTHETIC_CREATE_REQUEST_INVALID",
    )

    verification = _mapping(
        payload.get("post_create_verification"),
        "TIMEWEB_SYNTHETIC_CREATE_VERIFICATION_INVALID",
    )
    _require(
        verification.get("sanitized_marker"),
        "TIMEWEB_RU_PG_SYNTHETIC_CREATE=READY",
        "TIMEWEB_SYNTHETIC_CREATE_VERIFICATION_INVALID",
    )
    for key in (
        "exact_cluster_get_required",
        "exact_project_membership_recheck_required",
        "started_status_required",
        "starting_state_uses_bounded_state_aware_verification",
        "starting_explicit_unsafe_values_fail_closed",
        "terminal_started_exact_shape_required",
        "field_specific_sanitized_drift_codes_required",
        "public_network_must_be_disabled",
        "public_ipv6_must_be_disabled",
        "autobackups_must_be_disabled",
        "backup_schedule_must_be_disabled",
        "canonical_replica_topology_verification_required",
        "disk_autoscaling_must_be_disabled",
    ):
        _require(
            verification.get(key),
            True,
            "TIMEWEB_SYNTHETIC_CREATE_VERIFICATION_INVALID",
        )

    _require(
        verification.get("provider_replica_list_count_must_equal"),
        1,
        "TIMEWEB_SYNTHETIC_CREATE_VERIFICATION_INVALID",
    )

    invariants = _mapping(
        payload.get("protected_invariants"),
        "TIMEWEB_SYNTHETIC_CREATE_INVARIANTS_INVALID",
    )
    _require(
        invariants.get("current_neon_production_authority_preserved"),
        True,
        "TIMEWEB_SYNTHETIC_CREATE_INVARIANTS_INVALID",
    )
    _require(
        invariants.get("protected_v9_entrypoint"),
        "app:app",
        "TIMEWEB_SYNTHETIC_CREATE_INVARIANTS_INVALID",
    )
    for key in (
        "production_postgres_dsn_mutation_allowed",
        "PUBLIC_MULTI_USER_ENABLED",
        "OMNI_V10_TELEGRAM_LOGIN_ENABLED",
        "OMNI_V10_VK_ID_LOGIN_ENABLED",
        "broker_write",
        "trading_methods",
        "REAL_TRADING_ENABLED",
        "ru_pg_c_allowed",
    ):
        _require(
            invariants.get(key),
            False,
            "TIMEWEB_SYNTHETIC_CREATE_INVARIANTS_INVALID",
        )


def _validate_read_only_probe_reuse() -> None:
    source = _read(READ_ONLY_PROBE)
    _require_markers(
        source,
        (
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
            "TIMEWEB_CLUSTER_REPLICA_TOPOLOGY_DRIFT",
            "TIMEWEB_CLUSTER_REPLICA_MEMBER_DUPLICATE",
            "TIMEWEB_CLUSTER_REPLICA_CUSTODY_DRIFT",
            "def _select_target_preset(payload: object, provider_type: str) -> int:",
            "TIMEWEB_BETA_PRESET_NOT_UNIQUE_OR_PRICE_DRIFT",
        ),
        "TIMEWEB_SYNTHETIC_CREATE_READ_ONLY_REUSE_DRIFT",
    )


def _validate_provisioner() -> None:
    source = _read(PROVISIONER)
    _require_markers(
        source,
        (
            'CREATE_PATH = "/api/v1/databases"',
            'TARGET_AVAILABILITY_ZONE = "msk-1"',
            f'CREATE_CONFIRMATION = "{_CONFIRMATION}"',
            'method="POST"',
            "def post_once(",
            "class AmbiguousCreate",
            "TIMEWEB_CLUSTER_CREATE_AMBIGUOUS_RECONCILIATION_REQUIRED",
            "def _reconcile_cluster_id(",
            "def _create_or_reconcile(",
            "read_only.verify_credential_health(read_api)",
            "existing_cluster_id = _target_cluster_id(read_api.get(project_path))",
            "mutation_api = TimewebCreateApi(token)",
            "read_only.raise_timeweb_auth_failure(status)",
            '"existing-recovery"',
            "TIMEWEB_CLUSTER_PUBLIC_NETWORK_DRIFT",
            "TIMEWEB_CLUSTER_DISK_SIZE_DRIFT",
            "read_only._require_target_cluster_disk(",
            "read_only._require_target_replica_topology(",
            '"disk_autoscaling": {"is_enabled": False}',
            '"is_public_ipv6": False',
            '"TIMEWEB_RU_PG_SYNTHETIC_CREATE=READY "',
            "create_mode={create_mode}",
        ),
        "TIMEWEB_SYNTHETIC_CREATE_PROVISIONER_DRIFT",
    )
    _validate_terminal_false_invariants(source)
    forbidden = (
        'method="PUT"',
        'method="PATCH"',
        'method="DELETE"',
        ".put(",
        ".patch(",
        ".delete(",
        "OMNI_V10_POSTGRES_DSN",
        "NEON_API_KEY",
        '"auto_backups":',
        '"backup_schedule":',
        '"replication":',
        '"network":',
        "TIMEWEB_CLUSTER_REPLICAS_PRESENT",
        '"admin":',
        '"instance":',
    )
    if any(marker in source for marker in forbidden):
        raise RuntimeError("TIMEWEB_SYNTHETIC_CREATE_AUTHORITY_WIDENED")
    if source.count('method="POST"') != 1:
        raise RuntimeError("TIMEWEB_SYNTHETIC_CREATE_POST_SURFACE_INVALID")
    tree = _parse_python_source(source)
    provision = _find_function(tree, "provision")

    credential = call_lines(
        provision,
        owner="read_only",
        name="verify_credential_health",
    )
    target_lookup = call_lines(provision, owner=None, name="_target_cluster_id")
    writer = call_lines(provision, owner=None, name="TimewebCreateApi")
    if len(credential) != 1 or not target_lookup or len(writer) != 1:
        raise RuntimeError("TIMEWEB_SYNTHETIC_CREATE_CREDENTIAL_SEQUENCE_INVALID")
    if not credential[0] < min(target_lookup) < writer[0]:
        raise RuntimeError("TIMEWEB_SYNTHETIC_CREATE_CREDENTIAL_SEQUENCE_INVALID")
    if "TIMEWEB_API_TOKEN_INVALID_OR_INSUFFICIENT" in source:
        raise RuntimeError("TIMEWEB_SYNTHETIC_CREATE_AUTH_CLASSIFICATION_DRIFT")


def _validate_public_ipv4_source() -> None:
    contract = _read(PUBLIC_IPV4_CONTRACT)
    workflow = _read(PUBLIC_IPV4_WORKFLOW)
    _require_markers(
        contract,
        (
            '"status": "SOURCE_READY_PROVIDER_MUTATION_PENDING_MAIN_ACCEPTANCE"',
            '"selected_transport": "PUBLIC_IPV4_OWNER_APPROVED"',
            '"policy": "DROP"',
            '"port": "5432"',
            '"source_prefix_length": 32',
            '"public_ipv6_authorized": false',
            '"ddos_addon_authorized": false',
            '"sslmode": "verify-full"',
        ),
        "TIMEWEB_SYNTHETIC_CREATE_PUBLIC_IPV4_SOURCE_DRIFT",
    )
    _require_markers(
        workflow,
        (
            "workflow_dispatch:",
            "environment: timeweb-synthetic",
            _PUBLIC_IPV4_GUARD_MODULE,
        ),
        "TIMEWEB_SYNTHETIC_CREATE_PUBLIC_IPV4_SOURCE_DRIFT",
    )
    if _PUBLIC_IPV4_GUARD_SCRIPT in workflow:
        raise RuntimeError("TIMEWEB_SYNTHETIC_CREATE_PUBLIC_IPV4_SOURCE_DRIFT")


def _validate_environment_verifier() -> None:
    source = _read(ENVIRONMENT_VERIFIER)
    _require_markers(
        source,
        (
            'ENVIRONMENT_NAME = "timeweb-synthetic"',
            'EXPECTED_BRANCH_PATTERN = "main"',
            "TIMEWEB_GITHUB_ENVIRONMENT_GATE=READY",
        ),
        "TIMEWEB_SYNTHETIC_CREATE_ENVIRONMENT_GATE_DRIFT",
    )


def _validate_workflow() -> None:
    source = _read(WORKFLOW)
    _require_markers(
        source,
        (
            "workflow_dispatch:",
            "confirmation:",
            _CONFIRMATION,
            "actions: read",
            "contents: read",
            "if: github.ref == 'refs/heads/main'",
            "environment-policy-proof:",
            "needs: environment-policy-proof",
            "environment: timeweb-synthetic",
            _SYNTHETIC_GUARD_MODULE,
            _SYNTHETIC_GUARD_MODULE + " --require-parity-transport-ready",
            "python -m scripts.verify_v10_timeweb_github_environment",
            "python -m scripts.provision_v10_timeweb_postgres_synthetic",
            f"{_TIMEWEB_BINDING}: ${{{{ secrets.{_TIMEWEB_BINDING} }}}}",
            "git clean -ffdx",
        ),
        "TIMEWEB_SYNTHETIC_CREATE_WORKFLOW_DRIFT",
    )
    if source.count(_SYNTHETIC_GUARD_MODULE) != 3:
        raise RuntimeError("TIMEWEB_SYNTHETIC_CREATE_WORKFLOW_ENTRYPOINT_INVALID")
    if _SYNTHETIC_GUARD_SCRIPT in source:
        raise RuntimeError("TIMEWEB_SYNTHETIC_CREATE_WORKFLOW_ENTRYPOINT_INVALID")
    if source.count(f"secrets.{_TIMEWEB_BINDING}") != 1:
        raise RuntimeError("TIMEWEB_SYNTHETIC_CREATE_SECRET_SCOPE_INVALID")
    forbidden = (
        "on:\n  push:",
        "pull_request:",
        "schedule:",
        "curl ",
        "Invoke-RestMethod",
        "Invoke-WebRequest",
        "OMNI_V10_POSTGRES_DSN",
        "method=PUT",
        "method=PATCH",
        "method=DELETE",
    )
    if any(marker in source for marker in forbidden):
        raise RuntimeError("TIMEWEB_SYNTHETIC_CREATE_WORKFLOW_AUTHORITY_WIDENED")


def _validate_runbook() -> None:
    source = _read(RUNBOOK)
    _require_markers(
        source,
        (
            "RU-PG-B",
            "790 RUB/month",
            "POST /api/v1/databases",
            "never automatically retried",
            "Reconciliation",
            _CONFIRMATION,
            "TIMEWEB_RU_PG_SYNTHETIC_CREATE=READY",
            "20971520 KB",
            "provider replica-list baseline count is exactly `1`",
            "additional paid replication remains unauthorized",
            "RU_PG_TIMEWEB_SYNTHETIC_PARITY=PASS",
            "Neon production authority",
            "RU-PG-C remains",
        ),
        "TIMEWEB_SYNTHETIC_CREATE_RUNBOOK_DRIFT",
    )


def _require_parity_transport_ready() -> None:
    payload = _load_contract()
    transport = _mapping(
        payload.get("parity_transport_gate"),
        "TIMEWEB_SYNTHETIC_CREATE_TRANSPORT_GATE_INVALID",
    )
    target = _mapping(
        payload.get("target"),
        "TIMEWEB_SYNTHETIC_CREATE_TARGET_INVALID",
    )
    _validate_transport_state(transport, target, require_ready=True)


def validate() -> None:
    _validate_contract(_load_contract())
    _validate_read_only_probe_reuse()
    _validate_provisioner()
    _validate_public_ipv4_source()
    _validate_environment_verifier()
    _validate_workflow()
    _validate_runbook()


def main() -> int:
    try:
        validate()
        if "--require-parity-transport-ready" in sys.argv[1:]:
            _require_parity_transport_ready()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("V10 Timeweb RU-PG-B synthetic create source contract passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
