from __future__ import annotations

import ast
import json
from pathlib import Path
import sys
from typing import Any

from scripts.v10_ast_guard import call_lines


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
_PUBLIC_IPV4_GUARD_MODULE = (
    "python -m scripts.check_v10_timeweb_postgres_public_ipv4_tls"
)
_PUBLIC_IPV4_GUARD_SCRIPT = (
    "python scripts/check_v10_timeweb_postgres_public_ipv4_tls.py"
)


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

    allocation_prerequisite = _mapping(
        payload.get("allocation_prerequisite"),
        "TIMEWEB_PUBLIC_IPV4_ALLOCATION_PREREQUISITE_INVALID",
    )
    _require(
        allocation_prerequisite,
        {
            "workflow": ".github/workflows/v10-timeweb-ipv4-allocation.yml",
            "required_transport_input": "allocation_plan_id",
            "required_phase": "ALLOCATED",
            "durable_receipt_required_before_mutation_adapter": True,
            "provider_methods_during_receipt_check": ["GET"],
            "allowed_current_binding_states": [
                "MANAGED_UNBOUND",
                "MANAGED_TARGET_BOUND",
            ],
            "network_state_is_not_receipt_identity": True,
            "provider_custody_rechecked_before_network_mutation": True,
            "plan_handle_is_non_authorizing_reference": True,
        },
        "TIMEWEB_PUBLIC_IPV4_ALLOCATION_PREREQUISITE_INVALID",
    )

    verifier = _mapping(
        payload.get("verifier_egress"),
        "TIMEWEB_PUBLIC_IPV4_VERIFIER_INVALID",
    )
    expected_verifier = {
        "source": "GITHUB_WORKFLOW_DISPATCH_INPUT",
        "input_name": "verifier_cidr",
        "external_discovery_allowed": False,
        "exact_ipv4_32_required": True,
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
        "mutation_reconciliation_before_exposure_required": True,
        "post_exposure_revalidation_read_only": True,
        "ambiguous_mutation_replay_allowed": False,
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
    for key in (
        "new_ipv4_create_authorized",
        "ipv4_delete_authorized",
        "metadata_stamp_authorized",
        "blind_mutation_retry_allowed",
    ):
        _require(
            ipv4.get(key),
            False,
            "TIMEWEB_PUBLIC_IPV4_IP_AUTHORITY_INVALID",
        )
    for key in (
        "existing_allocated_ipv4_required",
        "enable_transition_requires_tls_fields_absent",
    ):
        _require(
            ipv4.get(key),
            True,
            "TIMEWEB_PUBLIC_IPV4_IP_AUTHORITY_INVALID",
        )
    for forbidden_key in (
        "create_endpoint",
        "ambiguous_create_requires_get_reconciliation",
    ):
        _require(
            forbidden_key in ipv4,
            False,
            "TIMEWEB_PUBLIC_IPV4_IP_AUTHORITY_INVALID",
        )

    tls = _mapping(payload.get("tls"), "TIMEWEB_PUBLIC_IPV4_TLS_INVALID")
    _require(
        tls,
        {
            "provider_secure_connection_required": True,
            "public_ipv4_required_before_enable": True,
            "separate_provider_transition_required": True,
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
            "public_ipv4_before_tls_required": True,
            "state_reconciliation_between_public_ipv4_and_tls_required": True,
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
        },
        "TIMEWEB_PUBLIC_IPV4_API_BOUNDARY_INVALID",
    )
    _require(
        set(provider_api.get("patch_endpoints", [])),
        {
            "/api/v1/firewall/groups/{group_id}/rules/{rule_id}",
            "/api/v2/databases/{cluster_id}",
        },
        "TIMEWEB_PUBLIC_IPV4_API_BOUNDARY_INVALID",
    )
    _require(
        "delete_endpoint_for_created_ipv4_cleanup_only" in provider_api,
        False,
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
            "latest_live_sequence_failure": {
                "workflow_ordinal": 5,
                "exact_main_sha_parts": [
                    "7a875092",
                    "58552db4",
                    "b9ee0c2e",
                    "762597e5",
                    "61a42fb6",
                ],
                "observed_terminal_code": "TIMEWEB_DATABASE_PUBLIC_NETWORK_PATCH_REJECTED",
                "http_status": 400,
                "combined_public_ipv4_tls_patch_rejected": True,
                "exact_provider_validation_message_unavailable": True,
                "repair_requires_separate_public_ipv4_and_tls_transitions": True,
                "get_reconciliation_between_transitions_required": True,
            },
            "latest_live_readiness_failure": {
                "workflow_ordinal": 6,
                "exact_main_sha_parts": [
                    "86294ebb",
                    "0e5b6eb0",
                    "a56aa8d4",
                    "b28f1692",
                    "f483a8d8",
                ],
                "observed_terminal_code": "TIMEWEB_PUBLIC_IPV4_TLS_READY_TIMEOUT",
                "prior_tls_wait_budget_seconds": 83,
                "provider_readiness_sla_seconds_documented": False,
                "provider_mutation_success_can_precede_resource_readiness": True,
                "extended_get_only_reconciliation_required": True,
                "minimum_tls_wait_budget_seconds": 300,
                "maximum_tls_wait_budget_seconds": 900,
                "stage_specific_timeout_classification_required": True,
                "stage_specific_timeout_codes": [
                    "TIMEWEB_PUBLIC_IPV4_STATE_DRIFT_DURING_TLS",
                    "TIMEWEB_TLS_ENABLE_READY_TIMEOUT",
                    "TIMEWEB_TLS_CERTIFICATE_READY_TIMEOUT",
                    "TIMEWEB_TLS_CLUSTER_STATE_READY_TIMEOUT",
                ],
                "blind_retry_allowed": False,
                "transient_control_plane_reads_retryable": True,
                "transient_http_statuses": [408, 429, 500, 502, 503, 504],
                "nullable_domains_during_tls_transition_means_pending": True,
                "ca_fetch_transient_retry_required": True,
                "postgres_tls_socket_transient_retry_required": True,
                "postgres_tls_refused_is_retryable_readiness": True,
                "postgres_tls_refused_timeout_code": "TIMEWEB_POSTGRES_TLS_REFUSED_TIMEOUT",
                "postgres_tls_transport_timeout_code": "TIMEWEB_POSTGRES_TLS_TRANSPORT_TIMEOUT",
                "certificate_verification_failure_retry_allowed": False,
                "rollback_get_reconciliation_extended": True,
                "rollback_final_observation_after_last_backoff_required": True,
                "post_exposure_scope_transient_read_retry_required": True,
                "post_exposure_scope_security_drift_retry_allowed": False,
                "public_ipv4_binding_visibility_is_reconciled": True,
                "public_ipv4_binding_timeout_code": "TIMEWEB_PUBLIC_IPV4_BINDING_READY_TIMEOUT",
            },
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
        False,
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


def _validate_provisioner_safety(provisioner: str) -> None:
    tree = ast.parse(provisioner)
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_provision_transport"
    ]
    if len(functions) != 1:
        raise RuntimeError("TIMEWEB_PUBLIC_IPV4_PROVISIONER_DRIFT")
    function = functions[0]

    credential = call_lines(
        function,
        owner="read_only",
        name="verify_credential_health",
    )
    prerequisite = call_lines(
        function,
        owner=None,
        name="_verify_allocation_prerequisite",
    )
    writer = call_lines(function, owner=None, name="TimewebMutationApi")
    if len(credential) != 1 or len(prerequisite) != 1 or len(writer) != 1:
        raise RuntimeError("TIMEWEB_PUBLIC_IPV4_CREDENTIAL_SEQUENCE_INVALID")
    if not credential[0] < prerequisite[0] < writer[0]:
        raise RuntimeError("TIMEWEB_PUBLIC_IPV4_CREDENTIAL_SEQUENCE_INVALID")
    if "TIMEWEB_API_TOKEN_INVALID_OR_INSUFFICIENT" in provisioner:
        raise RuntimeError("TIMEWEB_PUBLIC_IPV4_AUTH_CLASSIFICATION_DRIFT")
    if "exc.read(" in provisioner:
        raise RuntimeError("TIMEWEB_PUBLIC_IPV4_RESPONSE_BODY_READ_FORBIDDEN")

    forbidden_markers = (
        '"is_ddos_guard": True',
        '"is_enabled_public_ipv6": True',
        "OMNI_V10_POSTGRES_DSN",
        "NEON_API_KEY",
        "ssl.CERT_NONE",
        "check_hostname = False",
        "TIMEWEB_CLUSTER_REPLICAS_PRESENT",
    )
    if any(marker in provisioner for marker in forbidden_markers):
        raise RuntimeError("TIMEWEB_PUBLIC_IPV4_AUTHORITY_WIDENED")


def _validate_sources() -> None:
    provisioner = _read(PROVISIONER)
    read_only_probe = _read(READ_ONLY_PROBE)
    discoverer = _read(DISCOVERER)
    workflow = _read(WORKFLOW)
    runbook = _read(RUNBOOK)

    _markers(
        discoverer,
        (
            'CIDR_ENV = "OMNI_V10_RU_PG_VERIFIER_CIDR"',
            "def _required_verifier_cidr() -> str:",
            "ipaddress.ip_network(raw, strict=True)",
            "network.prefixlen != 32",
            "raw != str(network)",
            "network.network_address.is_global",
            "::add-mask::",
            "RU_PG_VERIFIER_EGRESS=READY source=/32",
        ),
        "TIMEWEB_PUBLIC_IPV4_DISCOVERER_DRIFT",
    )
    for retired_endpoint in (
        "cloudflare.com/cdn-cgi/trace",
        "TRACE_URL",
        "urllib.request",
        "_NO_REDIRECT_OPENER",
    ):
        if retired_endpoint in discoverer:
            raise RuntimeError("TIMEWEB_PUBLIC_IPV4_RETIRED_DISCOVERY_FORBIDDEN")
    if "print(cidr)" in discoverer or "print(address)" in discoverer:
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
            'operation="DATABASE_PUBLIC_IPV4_PATCH"',
            'operation="DATABASE_TLS_ENABLE_PATCH"',
            "_wait_public_ipv4_ready(api, cluster_id, address)",
            "_TLS_STATE_DELAYS_SECONDS = (",
            "_WAIT_API_TIMEOUT_SECONDS = 8.0",
            "_CA_RETRY_DELAYS_SECONDS = (",
            "_TLS_SOCKET_RETRY_DELAYS_SECONDS = (",
            "_ROLLBACK_STATE_DELAYS_SECONDS = (",
            "_RECONCILE_DELAYS_SECONDS = (",
            "_verify_exact_rule",
            "for attempt in range(len(delays) + 1):",
            "_is_transient_control_plane_failure",
            "TIMEWEB_TLS_CONTROL_PLANE_READ_TIMEOUT",
            "TIMEWEB_TLS_ENABLE_READY_TIMEOUT",
            "TIMEWEB_TLS_CERTIFICATE_READY_TIMEOUT",
            "TIMEWEB_TLS_CLUSTER_STATE_READY_TIMEOUT",
            "TIMEWEB_PUBLIC_IPV4_STATE_DRIFT_DURING_TLS",
            "http_status={exc.status}",
            "TIMEWEB_PUBLIC_NETWORK_ROLLBACK_MANUAL_RECONCILIATION_REQUIRED",
            "TIMEWEB_FIREWALL_SERVICE_GROUPS_NOT_EXCLUSIVE",
            "TIMEWEB_PREEXISTING_PUBLIC_NETWORK_UNSAFE",
            "TIMEWEB_PREEXISTING_PUBLIC_IPV6_UNSAFE",
            "read_only._require_target_cluster_disk(",
            "read_only._require_target_replica_topology(",
            "allocation.verify_transport_prerequisite(",
            "adapter.transport_snapshot",
            "read_only.raise_timeweb_auth_failure(status)",
            "_verify_allocation_prerequisite(api)",
            "TIMEWEB_CLUSTER_DISK_SIZE_DRIFT",
            'f"/api/v1/firewall/service/{FIREWALL_RESOURCE_TYPE}/{cluster_id}"',
            _READY_MARKER,
        ),
        "TIMEWEB_PUBLIC_IPV4_PROVISIONER_DRIFT",
    )
    _validate_provisioner_safety(provisioner)

    _markers(
        workflow,
        (
            "workflow_dispatch:",
            _CONFIRMATION,
            "verifier_cidr:",
            "allocation_plan_id:",
            "actions: read",
            "contents: read",
            "if: github.ref == 'refs/heads/main'",
            "environment: timeweb-synthetic",
            _PUBLIC_IPV4_GUARD_MODULE,
            "OMNI_V10_RU_PG_VERIFIER_CIDR: ${{ inputs.verifier_cidr }}",
            "python -m scripts.discover_v10_ru_pg_verifier_ipv4",
            "python -m scripts.provision_v10_timeweb_postgres_public_ipv4_tls",
            "TIMEWEB_CLOUD_API_TOKEN: ${{ secrets.TIMEWEB_CLOUD_API_TOKEN }}",
            "TIMEWEB_ALLOCATION_PLAN_ID: ${{ inputs.allocation_plan_id }}",
            "git clean -ffdx",
        ),
        "TIMEWEB_PUBLIC_IPV4_WORKFLOW_DRIFT",
    )
    _require(
        workflow.count(_PUBLIC_IPV4_GUARD_MODULE),
        2,
        "TIMEWEB_PUBLIC_IPV4_WORKFLOW_ENTRYPOINT_INVALID",
    )
    if _PUBLIC_IPV4_GUARD_SCRIPT in workflow:
        raise RuntimeError("TIMEWEB_PUBLIC_IPV4_WORKFLOW_ENTRYPOINT_INVALID")
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
            "durable `ALLOCATED` allocation receipt",
            "allocation_plan_id",
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
        "transport_existing_only_after_allocation_receipt": True,
        "transport_create_allowed": False,
        "transport_delete_allowed": False,
        "transport_stamp_allowed": False,
        "transport_missing_allocated_ipv4_terminal_code": "TIMEWEB_ALLOCATED_IPV4_MISSING",
        "transport_two_read_drift_terminal_code": "TIMEWEB_ALLOCATED_IPV4_DRIFT",
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


def _string_literals(function: ast.FunctionDef) -> set[str]:
    return {
        node.value
        for node in ast.walk(function)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }


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


def _validate_existing_only_transport(tree: ast.Module) -> None:
    function = _function(tree, "_resolve_transport_ipv4")
    select_calls = call_lines(function, owner="custody", name="select")
    if len(select_calls) != 2:
        raise RuntimeError("TIMEWEB_IPV4_EXISTING_ONLY_RESOLVER_INVALID")
    literals = _string_literals(function)
    for required in (
        "TIMEWEB_ALLOCATED_IPV4_MISSING",
        "TIMEWEB_ALLOCATED_IPV4_DRIFT",
    ):
        _require(
            required in literals,
            True,
            "TIMEWEB_IPV4_EXISTING_ONLY_RESOLVER_INVALID",
        )
    forbidden_calls = {
        "_create_floating_ip",
        "_stamp_created_ipv4",
        "_delete_created_ipv4_if_unbound",
    }
    for node in ast.walk(function):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in forbidden_calls:
                raise RuntimeError("TIMEWEB_IPV4_EXISTING_ONLY_RESOLVER_INVALID")
            if (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "custody"
                and node.func.attr == "resolve"
            ):
                raise RuntimeError("TIMEWEB_IPV4_EXISTING_ONLY_RESOLVER_INVALID")


def _validate_provider_transition_order(tree: ast.Module) -> None:
    public_patch = _function(tree, "_patch_public_ipv4")
    tls_patch = _function(tree, "_enable_secure_connection")
    public_literals = _string_literals(public_patch)
    tls_literals = _string_literals(tls_patch)
    for required in (
        "floating_ip",
        "is_enabled_public_network",
        "is_enabled_public_ipv6",
        "DATABASE_PUBLIC_IPV4_PATCH",
    ):
        _require(
            required in public_literals,
            True,
            "TIMEWEB_PUBLIC_IPV4_TRANSITION_INVALID",
        )
    _require(
        "is_secure_connection_enable" in public_literals,
        False,
        "TIMEWEB_PUBLIC_IPV4_TRANSITION_INVALID",
    )
    for required in (
        "is_secure_connection_enable",
        "DATABASE_TLS_ENABLE_PATCH",
    ):
        _require(
            required in tls_literals,
            True,
            "TIMEWEB_TLS_TRANSITION_INVALID",
        )
    for forbidden in (
        "floating_ip",
        "is_enabled_public_network",
        "is_enabled_public_ipv6",
    ):
        _require(
            forbidden in tls_literals,
            False,
            "TIMEWEB_TLS_TRANSITION_INVALID",
        )

    configure = _function(tree, "_configure_transport")
    public_calls = call_lines(configure, owner=None, name="_patch_public_ipv4")
    tls_calls = call_lines(configure, owner=None, name="_enable_secure_connection")
    scope_wait_calls = call_lines(configure, owner=None, name="_wait_transport_scope")
    if len(public_calls) != 1 or len(tls_calls) != 1 or len(scope_wait_calls) != 2:
        raise RuntimeError("TIMEWEB_PROVIDER_TRANSITION_ORDER_INVALID")
    if not (public_calls[0] < scope_wait_calls[0] < tls_calls[0] < scope_wait_calls[1]):
        raise RuntimeError("TIMEWEB_PROVIDER_TRANSITION_ORDER_INVALID")

    scope_wait = _function(tree, "_wait_transport_scope")
    if len(call_lines(scope_wait, owner=None, name="_verify_transport_scope")) != 1:
        raise RuntimeError("TIMEWEB_PROVIDER_TRANSITION_ORDER_INVALID")

    forbidden_scope_calls = {
        "_ensure_group",
        "_ensure_rule",
        "_ensure_resource_link",
        "_patch_public_ipv4",
        "_enable_secure_connection",
    }
    for function_name in ("_wait_transport_scope", "_verify_transport_scope"):
        function = _function(tree, function_name)
        for node in ast.walk(function):
            if not isinstance(node, ast.Call):
                continue
            if (
                isinstance(node.func, ast.Name)
                and node.func.id in forbidden_scope_calls
            ):
                raise RuntimeError("TIMEWEB_POST_EXPOSURE_FIREWALL_MUTATION_FORBIDDEN")
            if isinstance(node.func, ast.Attribute) and node.func.attr == "mutate_once":
                raise RuntimeError("TIMEWEB_POST_EXPOSURE_FIREWALL_MUTATION_FORBIDDEN")


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
    _validate_custody_order(tree)
    _validate_existing_only_transport(tree)
    _validate_provider_transition_order(tree)
    _markers(
        source,
        (
            "custody.select(",
            "custody.raw_inventory(",
            "except custody.CustodyStopped as exc:",
            "TIMEWEB_ALLOCATED_IPV4_MISSING",
            "TIMEWEB_ALLOCATED_IPV4_DRIFT",
        ),
        "TIMEWEB_IPV4_CUSTODY_SOURCE_INVALID",
    )
    for forbidden in (
        "custody.resolve(",
        'operation="FLOATING_IP_CREATE"',
        'operation="FLOATING_IP_CUSTODY_STAMP"',
        'operation="FLOATING_IP_CLEANUP_DELETE"',
    ):
        if forbidden in source:
            raise RuntimeError("TIMEWEB_IPV4_CURRENT_TRANSPORT_WRITE_AUTHORITY_WIDENED")
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
        workflow.count(_PUBLIC_IPV4_GUARD_MODULE),
        2,
        "TIMEWEB_IPV4_DIAGNOSTIC_WORKFLOW_INVALID",
    )
    if _PUBLIC_IPV4_GUARD_SCRIPT in workflow:
        raise RuntimeError("TIMEWEB_IPV4_DIAGNOSTIC_WORKFLOW_INVALID")
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
