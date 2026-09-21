"""Validate M2 source integration without claiming live allocation acceptance."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    ROOT / "docs/architecture/V10_RU_POSTGRES_TIMEWEB_IPV4_ALLOCATION_CONTRACT.json"
)
SOURCE = ROOT / "scripts/timeweb_ipv4_allocation.py"
PROVIDER = ROOT / "scripts/timeweb_ipv4_allocation_provider.py"
RUNNER = ROOT / "scripts/run_v10_timeweb_ipv4_allocation.py"
WORKFLOW = ROOT / ".github/workflows/v10-timeweb-ipv4-allocation.yml"
_ERROR = "TIMEWEB_ALLOCATION_PROTOCOL_CONTRACT_INVALID"
_ISSUES_READ = "issues: read"
_TRANSPORT_READY_MARKER = "TIMEWEB_RU_PG_PUBLIC_IPV4_TLS=READY"
_PARITY_PASS_MARKER = "RU_PG_TIMEWEB_SYNTHETIC_PARITY=PASS"
# Historical accepted base for this repair, not mutable current-main authority.
_SOURCE_BASE_SHA_PARTS = (
    "3083e65f",
    "9e6dbc7a",
    "6f26de66",
    "49ae7ff4",
    "0627ba5c",
)


def _require(condition: bool) -> None:
    if not condition:
        raise ValueError(_ERROR)


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(_ERROR)
    return value


def _flags(data: dict[str, object], names: tuple[str, ...], expected: bool) -> None:
    for name in names:
        _require(data.get(name) is expected)


def source_base_sha(data: dict[str, object]) -> str:
    """Reconstruct only the known base revision; reject missing or dual encodings."""
    if "source_base_sha" in data:
        raise ValueError(_ERROR)
    parts = data.get("source_base_sha_parts")
    if not isinstance(parts, list) or len(parts) != len(_SOURCE_BASE_SHA_PARTS):
        raise ValueError(_ERROR)
    for part in parts:
        if not isinstance(part, str) or re.fullmatch(r"[0-9a-f]{8}", part) is None:
            raise ValueError(_ERROR)
    _require(tuple(parts) == _SOURCE_BASE_SHA_PARTS)
    return "".join(parts)


def validate_contract(data: dict[str, object]) -> None:
    source_base_sha(data)
    _require(data.get("schema") == "omni-cio.v10.timeweb-ipv4-allocation-protocol.v1")
    _require(data.get("stage") == "RU-PG-B" and data.get("owning_issue") == 559)
    _require(data.get("status") == "M2_SOURCE_INTEGRATION_PENDING_CERTIFICATION")
    implementation = _mapping(data.get("implementation"))
    _flags(
        implementation,
        (
            "pure_protocol",
            "live_entrypoint_enabled",
            "production_closed_journal_implemented",
            "production_owner_approval_verifier_implemented",
            "production_provider_adapter_implemented",
            "ready_for_remote_certification",
        ),
        True,
    )
    adapters = _mapping(data.get("source_adapters"))
    _require(adapters.get("sqlite_synchronous") == "EXTRA")
    _flags(
        adapters,
        (
            "windows_current_user_dpapi",
            "sqlite_immediate_transaction",
            "native_acl_required",
            "github_owner_comment_verifier",
            "timeweb_snapshot_comment_only_adapter",
            "operational_workflow_source_present",
            "native_windows_evidence_required_before_live_apply",
        ),
        True,
    )
    _flags(
        adapters,
        (
            "connector_authored_approval_allowed",
            "real_provider_integration_certified",
        ),
        False,
    )
    plan = _mapping(data.get("plan"))
    _require(type(plan.get("ttl_seconds")) is int and plan["ttl_seconds"] == 3600)
    _require(
        type(plan.get("complete_inventory_count")) is int
        and plan["complete_inventory_count"] == 1
    )
    _require(plan.get("prior_comment_required") == "EMPTY")
    _flags(
        plan,
        ("requires_two_equal_observations", "source_current_main_recheck_required"),
        True,
    )
    _flags(
        plan,
        (
            "checksum_is_authentication",
            "private_identifiers_in_output_allowed",
            "foreign_comment_overwrite_allowed",
        ),
        False,
    )
    approval = _mapping(data.get("approval"))
    _require(
        approval.get("confirmation")
        == "ALLOCATE_EXISTING_TIMEWEB_IPV4_NO_CREATE_NO_DELETE"
    )
    _flags(
        approval,
        (
            "authenticated_owner_evidence_required",
            "bound_to_plan_digest_source_target_purpose_expiry",
            "revocation_recheck_before_write",
        ),
        True,
    )
    _flags(
        approval,
        (
            "generic_development_approval_sufficient",
            "cost_approval_sufficient",
            "typed_python_object_alone_is_authentication",
        ),
        False,
    )
    transition = _mapping(data.get("transition"))
    _require(
        type(transition.get("metadata_writes_per_claim_max")) is int
        and transition["metadata_writes_per_claim_max"] == 1
    )
    _require(transition.get("only_metadata_field") == "comment")
    _require(transition.get("reconcile_provider_methods") == ["GET"])
    _flags(
        transition,
        (
            "claim_before_provider_write",
            "claim_requires_atomic_durable_acknowledgement",
            "reuse_accepted_custody_marker_v1",
            "receipt_requires_two_equal_gets",
            "unknown_outcome_keeps_claim",
            "receipt_persisted_before_success",
            "external_writers_must_be_frozen",
        ),
        True,
    )
    _flags(
        transition,
        (
            "repeat_apply_allowed",
            "expiry_releases_attempted_claim",
            "provider_compare_and_set_proven",
            "historical_creation_provenance_inferred",
        ),
        False,
    )
    workflow = _mapping(data.get("operational_workflow"))
    _require(
        workflow.get("path") == ".github/workflows/v10-timeweb-ipv4-allocation.yml"
    )
    _require(
        workflow.get("dispatch_modes") == ["INITIALIZE", "PLAN", "APPLY", "RECONCILE"]
    )
    _require(workflow.get("environment") == "timeweb-synthetic")
    _require(workflow.get("apply_github_permission") == _ISSUES_READ)
    _require(workflow.get("non_apply_issue_permission") == "none")
    _require(
        workflow.get("shared_provider_mutation_concurrency_group")
        == "v10-timeweb-postgres-public-ipv4-tls"
    )
    _require(workflow.get("plan_provider_methods") == ["GET"])
    _require(workflow.get("apply_provider_methods") == ["GET", "PATCH_COMMENT_ONCE"])
    _require(workflow.get("reconcile_provider_methods") == ["GET"])
    _flags(
        workflow,
        (
            "protected_main_only",
            "provider_secret_step_scoped",
            "dispatch_inputs_passed_via_environment_only",
        ),
        True,
    )
    _flags(
        workflow,
        (
            "initialize_provider_access_allowed",
            "summary_private_identifiers_allowed",
            "allocation_success_implies_transport_ready",
            "direct_shell_interpolation_of_dispatch_inputs_allowed",
        ),
        False,
    )
    transport = _mapping(data.get("transport_prerequisite"))
    _require(
        transport
        == {
            "verification_function": "verify_transport_prerequisite",
            "required_receipt_phase": "ALLOCATED",
            "requires_two_equal_current_provider_gets": True,
            "allowed_current_binding_states": [
                "MANAGED_UNBOUND",
                "MANAGED_TARGET_BOUND",
            ],
            "expected_provider_comment": "CUSTODY_MARKER_V1",
            "network_state_is_not_receipt_identity": True,
            "provider_write_allowed": False,
            "provider_custody_recheck_still_required": True,
        }
    )
    invariants = _mapping(data.get("protected_invariants"))
    _require(invariants.get("protected_v9_entrypoint") == "app:app")
    _require(invariants.get("neon_production_authority_preserved") is True)
    _flags(
        invariants,
        (
            "new_ipv4_purchase_allowed",
            "existing_ipv4_delete_allowed",
            "network_enable_allowed",
            "firewall_change_allowed",
            "ordinary_unmarked_adoption_allowed",
            "transport_ready_claim_allowed",
            "sql_parity_claim_allowed",
            "production_dsn_change_allowed",
            "public_auth_enabled",
            "broker_write",
            "trading_methods",
            "REAL_TRADING_ENABLED",
        ),
        False,
    )


def validate_source(source: str) -> None:
    tree = ast.parse(source)
    functions = {
        node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    _require(
        {
            "prepare",
            "apply",
            "reconcile",
            "verify_transport_prerequisite",
            "safe_summary",
        }
        <= functions.keys()
    )
    _require(not any(isinstance(node, ast.If) for node in tree.body))
    forbidden_imports = {"os", "subprocess", "socket", "urllib", "requests", "httpx"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            _require(
                not any(
                    alias.name.split(".")[0] in forbidden_imports
                    for alias in node.names
                )
            )
        if isinstance(node, ast.ImportFrom):
            _require((node.module or "").split(".")[0] not in forbidden_imports)
    writers = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "write_comment_once"
    ]
    _require(len(writers) == 1)
    _require(writers[0] in list(ast.walk(functions["apply"])))
    transport = functions["verify_transport_prerequisite"]
    _require("read_snapshot" in {arg.arg for arg in transport.args.args})
    _require("journal" in {arg.arg for arg in transport.args.args})
    transport_names = {
        node.id for node in ast.walk(transport) if isinstance(node, ast.Name)
    }
    _require("write_comment_once" not in transport_names)

    reconcile_names = {
        node.id
        for node in ast.walk(functions["reconcile"])
        if isinstance(node, ast.Name)
    }
    _require("write_comment_once" not in reconcile_names)
    _require(
        "write_comment_once"
        not in {arg.arg for arg in functions["reconcile"].args.args}
    )
    for name in ("apply", "prepare"):
        _require("read_context" in {a.arg for a in functions[name].args.kwonlyargs})
    for forbidden in (
        "CERTIFIED_GREEN",
        _TRANSPORT_READY_MARKER,
        _PARITY_PASS_MARKER,
    ):
        _require(forbidden not in source)


def _adapter_source(name: str) -> str:
    return (ROOT / "scripts" / name).read_text(encoding="utf-8")


def _validate_m1_adapters() -> None:
    journal = _adapter_source("timeweb_ipv4_allocation_journal.py")
    approval = _adapter_source("timeweb_ipv4_allocation_github.py")
    windows = _adapter_source("timeweb_ipv4_allocation_windows.py")
    for marker in (
        "BEGIN IMMEDIATE",
        "PRAGMA synchronous=EXTRA",
        "PRAGMA trusted_schema=OFF",
        "CryptProtectData",
        "CryptUnprotectData",
        "TIMEWEB_JOURNAL_MISSING_RECONCILIATION_REQUIRED",
    ):
        _require(marker in journal)
    for marker in (
        "performed_via_github_app",
        "author_association",
        "approval_body(plan)",
        "current_context(plan.context.source_sha)",
        "environment._request_json(path, self._token)",
    ):
        _require(marker in approval)
    for marker in (
        "SetAccessRuleProtection($true, $false)",
        "ReparsePoint",
        "GITHUB_WORKSPACE",
        "TIMEWEB_JOURNAL_WORKSPACE_FORBIDDEN",
    ):
        _require(marker in windows)
    for source in (journal, approval, windows):
        for forbidden in (
            "JournalDouble",
            "VerifierDouble",
            "fake_codec",
            "TimewebMutationApi",
            "CRYPTPROTECT_LOCAL_MACHINE",
            _TRANSPORT_READY_MARKER,
        ):
            _require(forbidden not in source)


def _validate_provider() -> None:
    source = PROVIDER.read_text(encoding="utf-8")
    tree = ast.parse(source)
    classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
    _require("TimewebAllocationProvider" in classes)
    methods = {
        node.name: node
        for node in classes["TimewebAllocationProvider"].body
        if isinstance(node, ast.FunctionDef)
    }
    _require({"snapshot", "write_comment_once"} <= methods.keys())
    writes = [
        node
        for node in ast.walk(methods["write_comment_once"])
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "mutate_once"
    ]
    _require(len(writes) == 1)
    call = writes[0]
    _require(
        bool(call.args)
        and isinstance(call.args[0], ast.Constant)
        and call.args[0].value == "PATCH"
    )
    for forbidden in (
        '"POST"',
        '"PUT"',
        '"DELETE"',
        '"POST"',
        '"/bind"',
        '"/unbind"',
        "/firewall/",
        "/api/v2/databases/",
        _TRANSPORT_READY_MARKER,
        _PARITY_PASS_MARKER,
    ):
        _require(forbidden not in source)
    _require('body={"comment": marker}' in source)
    _require("def transport_snapshot(" in source)
    _require("allocation.TransportSnapshot(" in source)
    _require('self._read_api.get("/api/v1/floating-ips")' in source)
    _require("/api/v1/floating-ips/{parsed.identifier}" in source)


def _validate_runner() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    for marker in (
        'frozenset({"INITIALIZE", "PLAN", "APPLY", "RECONCILE"})',
        '"refs/heads/main"',
        'allocation.safe_summary(identifier, "OWNER_APPROVAL_REQUIRED")',
        '"ALLOCATION_VERIFIED_TRANSPORT_NOT_VERIFIED"',
        "allow_write=False",
        "allow_write=True",
        "allocation.reconcile(",
        "allocation.apply(",
        "open_journal(initialize=initialize)",
    ):
        _require(marker in source)
    for forbidden in (
        _TRANSPORT_READY_MARKER,
        _PARITY_PASS_MARKER,
        "plan.digest, output",
        "snapshot.ip_address, output",
    ):
        _require(forbidden not in source)


def _validate_workflow() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    for marker in (
        "workflow_dispatch:",
        "group: v10-timeweb-postgres-public-ipv4-tls",
        "environment: timeweb-synthetic",
        _ISSUES_READ,
        "inputs.mode != 'APPLY'",
        "inputs.mode == 'APPLY'",
        "--mode INITIALIZE",
        "--mode PLAN",
        "--mode RECONCILE",
        "--mode APPLY",
        "ALLOCATE_EXISTING_TIMEWEB_IPV4_NO_CREATE_NO_DELETE",
        "TIMEWEB_ALLOCATION_PLAN_ID: ${{ inputs.plan_id }}",
        "TIMEWEB_ALLOCATION_APPROVAL_REFERENCE: ${{ inputs.approval_comment_id }}",
        "TIMEWEB_ALLOCATION_CONFIRMATION: ${{ inputs.confirmation }}",
        "python scripts/check_v10_timeweb_ipv4_allocation.py",
        "python scripts/check_v10_provider_secret_custody.py",
        "python scripts/check_v10_timeweb_postgres_control_plane.py",
        "python -m scripts.verify_v10_timeweb_github_environment",
    ):
        _require(marker in source)
    for forbidden in (
        "on:\n  push:",
        "pull_request:",
        "schedule:",
        "issues: write",
        "contents: write",
        "actions: write",
        "curl ",
        "Invoke-RestMethod",
        "Invoke-WebRequest",
        '--plan-id "${{ inputs.plan_id }}"',
        '--approval-reference "${{ inputs.approval_comment_id }}"',
        '--confirmation "${{ inputs.confirmation }}"',
    ):
        _require(forbidden not in source)
    _require(
        source.count("TIMEWEB_CLOUD_API_TOKEN: ${{ secrets.TIMEWEB_CLOUD_API_TOKEN }}")
        == 3
    )
    non_apply = source[source.index("  non-apply:") : source.index("  apply:")]
    apply = source[source.index("  apply:") :]
    _require(_ISSUES_READ not in non_apply)
    _require(_ISSUES_READ in apply)


def validate_adapters() -> None:
    _validate_m1_adapters()
    _validate_provider()
    _validate_runner()
    _validate_workflow()


def validate() -> None:
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))
    _require(isinstance(data, dict))
    validate_contract(data)
    validate_source(SOURCE.read_text(encoding="utf-8"))
    validate_adapters()


def main() -> int:
    validate()
    print(
        "Allocation M2 source integration checks passed; "
        "live allocation remains unaccepted."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
