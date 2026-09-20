from __future__ import annotations

import ast
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    ROOT / "docs/architecture/V10_RU_POSTGRES_TIMEWEB_PUBLIC_IPV4_TLS_CONTRACT.json"
)
PROVISIONER = ROOT / "scripts/provision_v10_timeweb_postgres_public_ipv4_tls.py"
DISCOVERER = ROOT / "scripts/discover_v10_ru_pg_verifier_ipv4.py"
WORKFLOW = ROOT / ".github/workflows/v10-timeweb-postgres-public-ipv4-tls.yml"
RUNBOOK = ROOT / "docs/operations/V10_RU_POSTGRES_TIMEWEB_PUBLIC_IPV4_TLS_RUNBOOK.md"
CREATE_CONTRACT = (
    ROOT / "docs/architecture/V10_RU_POSTGRES_TIMEWEB_SYNTHETIC_CREATE_CONTRACT.json"
)
READ_ONLY_PROBE = ROOT / "scripts/probe_v10_timeweb_postgres_control_plane.py"

_SCHEMA = "omni-cio.v10.ru-postgres-timeweb-public-ipv4-tls.v1"
_STAGE = "RU-PG-B_TIMEWEB_PUBLIC_IPV4_TLS_TRANSPORT"
_STATUS = "SOURCE_READY_PROVIDER_MUTATION_PENDING_MAIN_ACCEPTANCE"
_CONFIRMATION = "ENABLE_TIMEWEB_RU_PG_PUBLIC_IPV4_200_RUB_MONTH"
_TIMEWEB_BINDING = "TIMEWEB_CLOUD_API_" + "TOKEN"
_READY_MARKER = "TIMEWEB_RU_PG_PUBLIC_IPV4_TLS=READY"


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError("TIMEWEB_PUBLIC_IPV4_SOURCE_UNREADABLE") from exc


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(_read(path))
    except json.JSONDecodeError as exc:
        raise RuntimeError("TIMEWEB_PUBLIC_IPV4_CONTRACT_INVALID") from exc
    if not isinstance(value, dict):
        raise RuntimeError("TIMEWEB_PUBLIC_IPV4_CONTRACT_INVALID")
    return value


def _mapping(value: object, code: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(code)
    return value


def _require(actual: object, expected: object, code: str) -> None:
    if actual != expected:
        raise RuntimeError(code)


def _markers(source: str, required: tuple[str, ...], code: str) -> None:
    for marker in required:
        if marker not in source:
            raise RuntimeError(code)


def _validate_contract(payload: dict[str, Any]) -> None:
    _require(payload.get("schema"), _SCHEMA, "TIMEWEB_PUBLIC_IPV4_SCHEMA_INVALID")
    _require(payload.get("stage"), _STAGE, "TIMEWEB_PUBLIC_IPV4_STAGE_INVALID")
    _require(payload.get("status"), _STATUS, "TIMEWEB_PUBLIC_IPV4_STATUS_INVALID")
    _require(payload.get("owning_issue"), 559, "TIMEWEB_PUBLIC_IPV4_ISSUE_INVALID")
    _require(
        payload.get("accepted_base_sha_parts"),
        ["b45d110d", "92d6642b", "9f29a686", "6c4c2e06", "eab76dd4"],
        "TIMEWEB_PUBLIC_IPV4_BASE_INVALID",
    )
    _require(
        payload.get("selected_transport"),
        "PUBLIC_IPV4_OWNER_APPROVED",
        "TIMEWEB_PUBLIC_IPV4_TRANSPORT_INVALID",
    )

    authority = _mapping(
        payload.get("authority"),
        "TIMEWEB_PUBLIC_IPV4_AUTHORITY_INVALID",
    )
    _require(
        authority,
        {
            "owner_ipv4_cost_approval_recorded": True,
            "authorized_ipv4_monthly_price_rub": 200,
            "funding_evidence_recorded": True,
            "manual_workflow_dispatch_required": True,
            "exact_main_ref_required": True,
            "environment": "timeweb-synthetic",
            "environment_machine_gate_required": True,
            "provider_secret_step_scope_required": True,
            "synthetic_cluster_must_preexist": True,
            "production_data_allowed": False,
        },
        "TIMEWEB_PUBLIC_IPV4_AUTHORITY_INVALID",
    )

    verifier = _mapping(
        payload.get("verifier_egress"),
        "TIMEWEB_PUBLIC_IPV4_VERIFIER_INVALID",
    )
    expected_verifier = {
        "discovery_url": "https://cloudflare.com/cdn-cgi/trace",
        "two_sample_consensus_required": True,
        "ipv4_global_unicast_required": True,
        "source_prefix_length": 32,
        "value_may_be_logged": False,
        "value_may_be_persisted": False,
        "purpose": "RU_PG_B_SYNTHETIC_VERIFIER_ONLY",
    }
    _require(
        verifier,
        expected_verifier,
        "TIMEWEB_PUBLIC_IPV4_VERIFIER_INVALID",
    )

    firewall = _mapping(
        payload.get("firewall"),
        "TIMEWEB_PUBLIC_IPV4_FIREWALL_INVALID",
    )
    expected_firewall = {
        "group_name": "omni-cio-v10-ru-pg-synthetic-verifier",
        "policy": "DROP",
        "api_resource_type": "dbaas",
        "direction": "ingress",
        "protocol": "tcp",
        "port": "5432",
        "exact_rule_count": 1,
        "wildcard_ipv4_allowed": False,
        "other_resource_links_allowed": False,
        "must_be_verified_before_public_network_enable": True,
        "must_be_reverified_after_public_network_enable": True,
        "exclusive_service_group_required": True,
        "preexisting_public_network_requires_safe_narrow_firewall": True,
    }
    _require(
        firewall,
        expected_firewall,
        "TIMEWEB_PUBLIC_IPV4_FIREWALL_INVALID",
    )

    ipv4 = _mapping(
        payload.get("public_ipv4"),
        "TIMEWEB_PUBLIC_IPV4_IP_AUTHORITY_INVALID",
    )
    _require(ipv4.get("authorized"), True, "TIMEWEB_PUBLIC_IPV4_IP_AUTHORITY_INVALID")
    _require(
        ipv4.get("monthly_price_rub"),
        200,
        "TIMEWEB_PUBLIC_IPV4_IP_AUTHORITY_INVALID",
    )
    _require(
        ipv4.get("availability_zone"),
        "msk-1",
        "TIMEWEB_PUBLIC_IPV4_IP_AUTHORITY_INVALID",
    )
    _require(
        ipv4.get("ddos_addon_authorized"),
        False,
        "TIMEWEB_PUBLIC_IPV4_IP_AUTHORITY_INVALID",
    )
    _require(
        ipv4.get("reuse_unmanaged_free_ip_allowed"),
        False,
        "TIMEWEB_PUBLIC_IPV4_IP_AUTHORITY_INVALID",
    )
    _require(
        ipv4.get("ambiguous_create_requires_get_reconciliation"),
        True,
        "TIMEWEB_PUBLIC_IPV4_IP_AUTHORITY_INVALID",
    )
    _require(
        ipv4.get("blind_mutation_retry_allowed"),
        False,
        "TIMEWEB_PUBLIC_IPV4_IP_AUTHORITY_INVALID",
    )

    tls = _mapping(payload.get("tls"), "TIMEWEB_PUBLIC_IPV4_TLS_INVALID")
    _require(
        tls,
        {
            "provider_secure_connection_required": True,
            "technical_domain_required": True,
            "certificate_status_required": "issued",
            "ca_url": "https://st.timeweb.com/cloud-static/ca.crt",
            "sslmode": "verify-full",
            "minimum_tls_version": "TLSv1.2",
            "hostname_verification_required": True,
            "postgres_sslrequest_probe_required": True,
        },
        "TIMEWEB_PUBLIC_IPV4_TLS_INVALID",
    )

    shape = _mapping(
        payload.get("network_shape"),
        "TIMEWEB_PUBLIC_IPV4_NETWORK_SHAPE_INVALID",
    )
    _require(
        shape,
        {
            "public_ipv4_authorized": True,
            "public_ipv6_authorized": False,
            "ddos_addon_authorized": False,
            "firewall_first_required": True,
            "public_network_rollback_on_tls_or_verification_failure": True,
        },
        "TIMEWEB_PUBLIC_IPV4_NETWORK_SHAPE_INVALID",
    )

    topology = _mapping(
        payload.get("provider_replica_topology"),
        "TIMEWEB_PUBLIC_IPV4_REPLICA_TOPOLOGY_INVALID",
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
        "TIMEWEB_PUBLIC_IPV4_REPLICA_TOPOLOGY_INVALID",
    )

    disk_units = _mapping(
        payload.get("provider_disk_units"),
        "TIMEWEB_PUBLIC_IPV4_DISK_UNITS_INVALID",
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
        "TIMEWEB_PUBLIC_IPV4_DISK_UNITS_INVALID",
    )

    provider_api = _mapping(
        payload.get("provider_api"),
        "TIMEWEB_PUBLIC_IPV4_API_BOUNDARY_INVALID",
    )
    _require(
        set(provider_api.get("get_endpoints", [])),
        {
            "/api/v1/projects",
            "/api/v1/projects/{project_id}/resources/databases",
            "/api/v1/databases/{cluster_id}",
            "/api/v1/firewall/groups",
            "/api/v1/firewall/groups/{group_id}",
            "/api/v1/firewall/groups/{group_id}/rules",
            "/api/v1/firewall/groups/{group_id}/resources",
            "/api/v1/firewall/service/dbaas/{cluster_id}",
            "/api/v1/floating-ips",
        },
        "TIMEWEB_PUBLIC_IPV4_API_BOUNDARY_INVALID",
    )
    _require(
        set(provider_api.get("post_endpoints", [])),
        {
            "/api/v1/firewall/groups?policy=DROP",
            "/api/v1/firewall/groups/{group_id}/rules",
            "/api/v1/firewall/groups/{group_id}/resources/{cluster_id}?resource_type=dbaas",
            "/api/v1/floating-ips",
        },
        "TIMEWEB_PUBLIC_IPV4_API_BOUNDARY_INVALID",
    )
    _require(
        set(provider_api.get("patch_endpoints", [])),
        {
            "/api/v1/firewall/groups/{group_id}/rules/{rule_id}",
            "/api/v2/databases/{cluster_id}",
            "/api/v1/floating-ips/{floating_ip_id}",
        },
        "TIMEWEB_PUBLIC_IPV4_API_BOUNDARY_INVALID",
    )
    _require(
        provider_api.get("delete_endpoint_for_created_ipv4_cleanup_only"),
        "/api/v1/floating-ips/{floating_ip_id}",
        "TIMEWEB_PUBLIC_IPV4_API_BOUNDARY_INVALID",
    )
    for key in (
        "redirects_allowed",
        "response_body_logging_allowed",
        "provider_identifiers_in_output_allowed",
    ):
        _require(
            provider_api.get(key),
            False,
            "TIMEWEB_PUBLIC_IPV4_API_BOUNDARY_INVALID",
        )

    recovery = _mapping(
        payload.get("mutation_recovery"),
        "TIMEWEB_PUBLIC_IPV4_MUTATION_RECOVERY_INVALID",
    )
    _require(
        recovery,
        {
            "accepted_failed_run": 35515788859,
            "accepted_failed_main_sha_parts": [
                "51b4e374",
                "92987bf0",
                "34dbf442",
                "47b03e23",
                "a0dd5aff",
            ],
            "observed_terminal_code": "TIMEWEB_MUTATION_REJECTED",
            "exact_provider_rejection_unresolved_from_original_log": True,
            "operation_specific_rejection_code_required": True,
            "sanitized_http_status_allowed": True,
            "provider_response_body_logging_allowed": False,
            "bodyless_mutation_content_type": "application/json",
            "reconcilable_http_statuses": [409, 423],
            "blind_mutation_retry_allowed": False,
        },
        "TIMEWEB_PUBLIC_IPV4_MUTATION_RECOVERY_INVALID",
    )

    success = _mapping(
        payload.get("success"),
        "TIMEWEB_PUBLIC_IPV4_SUCCESS_INVALID",
    )
    _require(
        success,
        {
            "sanitized_marker": _READY_MARKER,
            "does_not_certify_ru_pg_b_parity": True,
            "ru_pg_c_unlocked": False,
        },
        "TIMEWEB_PUBLIC_IPV4_SUCCESS_INVALID",
    )

    invariants = _mapping(
        payload.get("protected_invariants"),
        "TIMEWEB_PUBLIC_IPV4_INVARIANTS_INVALID",
    )
    _require(
        invariants.get("current_neon_production_authority_preserved"),
        True,
        "TIMEWEB_PUBLIC_IPV4_INVARIANTS_INVALID",
    )
    _require(
        invariants.get("protected_v9_entrypoint"),
        "app:app",
        "TIMEWEB_PUBLIC_IPV4_INVARIANTS_INVALID",
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
            "TIMEWEB_PUBLIC_IPV4_INVARIANTS_INVALID",
        )


def _validate_create_transport() -> None:
    payload = _load(CREATE_CONTRACT)
    transport = _mapping(
        payload.get("parity_transport_gate"),
        "TIMEWEB_PUBLIC_IPV4_CREATE_GATE_INVALID",
    )
    target = _mapping(
        payload.get("target"),
        "TIMEWEB_PUBLIC_IPV4_CREATE_GATE_INVALID",
    )
    _require(
        transport.get("status"),
        "READY",
        "TIMEWEB_PUBLIC_IPV4_CREATE_GATE_INVALID",
    )
    _require(
        transport.get("selected_mode"),
        "PUBLIC_IPV4_OWNER_APPROVED",
        "TIMEWEB_PUBLIC_IPV4_CREATE_GATE_INVALID",
    )
    for key in (
        "public_ipv4_owner_approval_recorded",
        "public_ipv4_security_source_required",
        "public_ipv4_firewall_drop_required",
        "public_ipv4_tls_verify_full_required",
    ):
        _require(
            transport.get(key),
            True,
            "TIMEWEB_PUBLIC_IPV4_CREATE_GATE_INVALID",
        )
    _require(
        target.get("public_ipv4_authorized"),
        True,
        "TIMEWEB_PUBLIC_IPV4_CREATE_GATE_INVALID",
    )
    _require(
        target.get("public_ipv6_authorized"),
        False,
        "TIMEWEB_PUBLIC_IPV4_CREATE_GATE_INVALID",
    )


def _validate_sources() -> None:
    provisioner = _read(PROVISIONER)
    read_only_probe = _read(READ_ONLY_PROBE)
    discoverer = _read(DISCOVERER)
    workflow = _read(WORKFLOW)
    runbook = _read(RUNBOOK)

    _markers(
        discoverer,
        (
            'TRACE_URL = "https://cloudflare.com/cdn-cgi/trace"',
            'CIDR_ENV = "OMNI_V10_RU_PG_VERIFIER_CIDR"',
            "address.is_global",
            'cidr = f"{first}/32"',
            "::add-mask::",
            "RU_PG_VERIFIER_EGRESS=READY source=/32",
        ),
        "TIMEWEB_PUBLIC_IPV4_DISCOVERER_DRIFT",
    )
    if "print(cidr)" in discoverer or "print(first)" in discoverer:
        raise RuntimeError("TIMEWEB_PUBLIC_IPV4_VERIFIER_LOGGING_FORBIDDEN")

    _markers(
        read_only_probe,
        (
            "TARGET_PROVIDER_REPLICA_LIST_COUNT = 1",
            "ADDITIONAL_PAID_REPLICATION_AUTHORIZED = False",
            "def _provider_replica_list_count(",
            "def _require_target_replica_topology(",
            "TIMEWEB_CLUSTER_REPLICA_TOPOLOGY_DRIFT",
            "TIMEWEB_CLUSTER_REPLICA_MEMBER_DUPLICATE",
            "TIMEWEB_CLUSTER_REPLICA_CUSTODY_DRIFT",
        ),
        "TIMEWEB_PUBLIC_IPV4_REPLICA_ADAPTER_DRIFT",
    )

    _markers(
        provisioner,
        (
            f'CONFIRMATION = "{_CONFIRMATION}"',
            'FIREWALL_RESOURCE_TYPE = "dbaas"',
            'POSTGRES_PORT = "5432"',
            'CA_URL = "https://st.timeweb.com/cloud-static/ca.crt"',
            '"/api/v1/firewall/groups?policy=DROP"',
            '"direction": "ingress"',
            '"protocol": "tcp"',
            '"is_ddos_guard": False',
            '"is_enabled_public_network": True',
            '"is_enabled_public_ipv6": False',
            '"is_secure_connection_enable": True',
            "ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)",
            "context.minimum_version = ssl.TLSVersion.TLSv1_2",
            "context.check_hostname = True",
            "context.verify_mode = ssl.CERT_REQUIRED",
            'struct.pack("!II", 8, 80877103)',
            "_RECONCILABLE_MUTATION_HTTP_STATUSES = frozenset({409, 423})",
            'if body is not None or method in {"POST", "PUT", "PATCH"}:',
            'f"TIMEWEB_{operation}_REJECTED"',
            'operation="FIREWALL_GROUP_CREATE"',
            'operation="FIREWALL_RULE_CREATE"',
            'operation="FIREWALL_RESOURCE_LINK"',
            'operation="FLOATING_IP_CREATE"',
            'operation="DATABASE_PUBLIC_NETWORK_PATCH"',
            "http_status={exc.status}",
            "TIMEWEB_PUBLIC_NETWORK_ROLLBACK_MANUAL_RECONCILIATION_REQUIRED",
            "TIMEWEB_FIREWALL_SERVICE_GROUPS_NOT_EXCLUSIVE",
            "TIMEWEB_PREEXISTING_PUBLIC_NETWORK_UNSAFE",
            "TIMEWEB_PREEXISTING_PUBLIC_IPV6_UNSAFE",
            "read_only._require_target_cluster_disk(",
            "read_only._require_target_replica_topology(",
            "TIMEWEB_CLUSTER_DISK_SIZE_DRIFT",
            'f"/api/v1/firewall/service/{FIREWALL_RESOURCE_TYPE}/{cluster_id}"',
            _READY_MARKER,
        ),
        "TIMEWEB_PUBLIC_IPV4_PROVISIONER_DRIFT",
    )
    if "exc.read(" in provisioner:
        raise RuntimeError("TIMEWEB_PUBLIC_IPV4_RESPONSE_BODY_READ_FORBIDDEN")

    for forbidden in (
        '"is_ddos_guard": True',
        '"is_enabled_public_ipv6": True',
        "OMNI_V10_POSTGRES_DSN",
        "NEON_API_KEY",
        "ssl.CERT_NONE",
        "check_hostname = False",
        "TIMEWEB_CLUSTER_REPLICAS_PRESENT",
    ):
        if forbidden in provisioner:
            raise RuntimeError("TIMEWEB_PUBLIC_IPV4_AUTHORITY_WIDENED")

    _markers(
        workflow,
        (
            "workflow_dispatch:",
            _CONFIRMATION,
            "actions: read",
            "contents: read",
            "if: github.ref == 'refs/heads/main'",
            "environment: timeweb-synthetic",
            "python scripts/check_v10_timeweb_postgres_public_ipv4_tls.py",
            "python -m scripts.discover_v10_ru_pg_verifier_ipv4",
            "python -m scripts.provision_v10_timeweb_postgres_public_ipv4_tls",
            "TIMEWEB_CLOUD_API_TOKEN: ${{ secrets.TIMEWEB_CLOUD_API_TOKEN }}",
            "git clean -ffdx",
        ),
        "TIMEWEB_PUBLIC_IPV4_WORKFLOW_DRIFT",
    )
    if workflow.count("secrets.TIMEWEB_CLOUD_API_TOKEN") != 1:
        raise RuntimeError("TIMEWEB_PUBLIC_IPV4_SECRET_SCOPE_INVALID")
    for forbidden_workflow in ("on:\n  push:", "pull_request:", "schedule:"):
        if forbidden_workflow in workflow:
            raise RuntimeError("TIMEWEB_PUBLIC_IPV4_WORKFLOW_AUTHORITY_WIDENED")

    _markers(
        runbook,
        (
            "RU-PG-B",
            "PUBLIC_IPV4_OWNER_APPROVED",
            "DROP",
            "TCP/5432",
            "/32",
            "verify-full",
            "20971520 KB",
            "provider replica-list baseline count is exactly `1`",
            "additional paid replication remains unauthorized",
            _READY_MARKER,
            "RU_PG_TIMEWEB_SYNTHETIC_PARITY=PASS",
            "RU-PG-C remains locked",
        ),
        "TIMEWEB_PUBLIC_IPV4_RUNBOOK_DRIFT",
    )


def _validate_ipv4_custody_contract(payload: dict[str, Any]) -> None:
    expected = {
        "observed_failed_run": 35519666168,
        "observed_terminal_code": "TIMEWEB_UNMANAGED_FREE_IPV4_PRESENT",
        "unmarked_existing_adoption_allowed": False,
        "managed_orphan_recovery_requires_exact_association": True,
        "marker_prefix": "omni-cio:ru-pg-b:ipv4:v1:",
        "marker_is_cryptographic_authentication": False,
        "stamp_requires_current_create_receipt_and_exact_get_delta": True,
        "stamp_operation": "FLOATING_IP_CUSTODY_STAMP",
        "stamp_body_fields": ["comment"],
        "stamp_http_status": 200,
        "pre_firewall_inventory_required": True,
        "recovery_requires_two_equal_get_observations": True,
        "recovered_resource_cleanup_allowed": False,
        "created_resource_cleanup_requires_get_absence_proof": True,
        "create_and_stamp_are_atomic": False,
        "crash_before_stamp_requires_external_reconciliation": True,
        "diagnostic_methods": ["GET"],
        "diagnostic_output": "COUNTS_AND_STATIC_DISPOSITION_ONLY",
        "diagnostic_proves_network_readiness": False,
        "diagnostic_proves_sql_parity": False,
        "ambiguous_create_delta_is_ownership_proof": False,
    }
    _require(
        payload.get("ipv4_custody"),
        expected,
        "TIMEWEB_IPV4_CUSTODY_CONTRACT_INVALID",
    )


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    matches = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    if len(matches) != 1:
        raise RuntimeError("TIMEWEB_IPV4_CUSTODY_SOURCE_INVALID")
    return matches[0]


def _validate_custody_stamp(tree: ast.Module) -> None:
    function = _function(tree, "_stamp_created_ipv4")
    calls = [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "mutate_once"
    ]
    if len(calls) != 1:
        raise RuntimeError("TIMEWEB_IPV4_CUSTODY_STAMP_INVALID")
    expected = ast.parse(
        'mutation.mutate_once("PATCH", '
        'f"/api/v1/floating-ips/{floating_id}", '
        'operation="FLOATING_IP_CUSTODY_STAMP", '
        'body={"comment": management_marker}, '
        "expected_statuses=frozenset({200}), "
        "reconcile_statuses=_RECONCILABLE_MUTATION_HTTP_STATUSES)",
        mode="eval",
    ).body
    _require(
        ast.dump(calls[0]),
        ast.dump(expected),
        "TIMEWEB_IPV4_CUSTODY_STAMP_INVALID",
    )


def _validate_custody_order(tree: ast.Module) -> None:
    function = _function(tree, "_configure_transport")
    blocks = [node for node in function.body if isinstance(node, ast.Try)]
    if len(blocks) != 1 or len(blocks[0].body) < 2:
        raise RuntimeError("TIMEWEB_IPV4_CUSTODY_ORDER_INVALID")
    first, second = blocks[0].body[:2]
    _require(
        ast.dump(first),
        ast.dump(
            ast.parse("_preflight_ipv4_custody(api, cluster_id, initial)").body[0]
        ),
        "TIMEWEB_IPV4_CUSTODY_ORDER_INVALID",
    )
    _require(
        ast.dump(second),
        ast.dump(
            ast.parse(
                "group_id = _converge_firewall(mutation, api, cluster_id, cidr)"
            ).body[0]
        ),
        "TIMEWEB_IPV4_CUSTODY_ORDER_INVALID",
    )


def _validate_custody_probe(source: str) -> None:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "api":
                _require(node.func.attr, "get", "TIMEWEB_IPV4_DIAGNOSTIC_WRITE")
    for forbidden in (
        "TimewebMutationApi",
        "mutate_once",
        "provision_v10_timeweb_postgres_public_ipv4_tls",
        "::add-mask::",
        "getattr(",
        "__import__(",
        "eval(",
        "exec(",
        "TIMEWEB_RU_PG_PUBLIC_IPV4_TLS=READY",
        "RU_PG_TIMEWEB_SYNTHETIC_PARITY=PASS",
    ):
        if forbidden in source:
            raise RuntimeError("TIMEWEB_IPV4_DIAGNOSTIC_WRITE_OR_OVERCLAIM")
    _markers(
        source,
        (
            'api.get("/api/v1/floating-ips")',
            "custody.raw_inventory(",
            "custody.observation(",
            "custody.disposition(",
            "TIMEWEB_RU_PG_IPV4_INVENTORY=STOPPED",
        ),
        "TIMEWEB_IPV4_DIAGNOSTIC_SOURCE_INVALID",
    )


def _validate_ipv4_custody_sources() -> None:
    source = _read(PROVISIONER)
    tree = ast.parse(source)
    _validate_custody_stamp(tree)
    _validate_custody_order(tree)
    _markers(
        source,
        (
            "custody.resolve(",
            "custody.raw_inventory(",
            "custody.is_unbound(",
            "except custody.CustodyStopped as exc:",
            "TIMEWEB_FLOATING_IP_CREATE_RECEIPT_UNPROVEN",
            "TIMEWEB_IPV4_CLEANUP_ABSENCE_UNPROVEN",
        ),
        "TIMEWEB_IPV4_CUSTODY_SOURCE_INVALID",
    )
    helper = _read(ROOT / "scripts/timeweb_ipv4_custody.py")
    _markers(
        helper,
        (
            "TIMEWEB_IPV4_ORPHAN_PROVENANCE_REQUIRED",
            "TIMEWEB_IPV4_CUSTODY_RECOVERY_DRIFT",
            "TIMEWEB_IPV4_CREATE_RECEIPT_NOT_UNIQUE",
            "TIMEWEB_IPV4_CUSTODY_CLEANUP_UNPROVEN",
            "TIMEWEB_IPV4_INVENTORY_INCOMPLETE",
            "TIMEWEB_RU_PG_IPV4_INVENTORY=OBSERVED",
            "TIMEWEB_RU_PG_IPV4_RECOVERY=BLOCKED",
        ),
        "TIMEWEB_IPV4_CUSTODY_HELPER_INVALID",
    )
    _validate_custody_probe(_read(ROOT / "scripts/probe_v10_timeweb_ipv4_custody.py"))
    workflow = _read(ROOT / ".github/workflows/v10-timeweb-postgres-readonly-proof.yml")
    command = "python -m scripts.probe_v10_timeweb_ipv4_custody"
    _require(workflow.count(command), 1, "TIMEWEB_IPV4_DIAGNOSTIC_WORKFLOW_INVALID")
    _require(
        workflow.count("python scripts/check_v10_timeweb_postgres_public_ipv4_tls.py"),
        2,
        "TIMEWEB_IPV4_DIAGNOSTIC_WORKFLOW_INVALID",
    )
    _require(
        workflow.count("secrets.TIMEWEB_CLOUD_API_TOKEN"),
        1,
        "TIMEWEB_IPV4_DIAGNOSTIC_SECRET_SCOPE_INVALID",
    )
    _markers(
        workflow,
        (command + "\n          if errorlevel 1 exit /b 1",),
        "TIMEWEB_IPV4_DIAGNOSTIC_FAILURE_PROPAGATION_INVALID",
    )


def validate() -> None:
    payload = _load(CONTRACT)
    _validate_contract(payload)
    _validate_ipv4_custody_contract(payload)
    _validate_ipv4_custody_sources()
    _validate_create_transport()
    _validate_sources()


def main() -> int:
    try:
        validate()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("V10 Timeweb RU-PG-B public IPv4/firewall/TLS source contract passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
