from __future__ import annotations

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
            "TIMEWEB_PUBLIC_NETWORK_ROLLBACK_MANUAL_RECONCILIATION_REQUIRED",
            "TIMEWEB_FIREWALL_SERVICE_GROUPS_NOT_EXCLUSIVE",
            "TIMEWEB_PREEXISTING_PUBLIC_NETWORK_UNSAFE",
            "TIMEWEB_PREEXISTING_PUBLIC_IPV6_UNSAFE",
            'f"/api/v1/firewall/service/{FIREWALL_RESOURCE_TYPE}/{cluster_id}"',
            _READY_MARKER,
        ),
        "TIMEWEB_PUBLIC_IPV4_PROVISIONER_DRIFT",
    )
    for forbidden in (
        '"is_ddos_guard": True',
        '"is_enabled_public_ipv6": True',
        "OMNI_V10_POSTGRES_DSN",
        "NEON_API_KEY",
        "ssl.CERT_NONE",
        "check_hostname = False",
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
            _READY_MARKER,
            "RU_PG_TIMEWEB_SYNTHETIC_PARITY=PASS",
            "RU-PG-C remains locked",
        ),
        "TIMEWEB_PUBLIC_IPV4_RUNBOOK_DRIFT",
    )


def validate() -> None:
    _validate_contract(_load(CONTRACT))
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
