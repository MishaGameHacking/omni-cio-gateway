"""Validate the source checkpoint without claiming live allocation readiness."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    ROOT / "docs/architecture/V10_RU_POSTGRES_TIMEWEB_IPV4_ALLOCATION_CONTRACT.json"
)
SOURCE = ROOT / "scripts/timeweb_ipv4_allocation.py"
_ERROR = "TIMEWEB_ALLOCATION_PROTOCOL_CONTRACT_INVALID"


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


def validate_contract(data: dict[str, object]) -> None:
    _require(data.get("schema") == "omni-cio.v10.timeweb-ipv4-allocation-protocol.v1")
    _require(data.get("stage") == "RU-PG-B" and data.get("owning_issue") == 559)
    _require(data.get("status") == "SOURCE_CHECKPOINT_NATIVE_CERTIFICATION_PENDING")
    implementation = _mapping(data.get("implementation"))
    _flags(implementation, ("pure_protocol", "ready_for_remote_certification"), True)
    _flags(
        implementation,
        (
            "live_entrypoint_enabled",
            "production_closed_journal_implemented",
            "production_owner_approval_verifier_implemented",
            "production_provider_adapter_implemented",
        ),
        False,
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
            "native_windows_evidence_required_before_live_wiring",
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
    _require({"prepare", "apply", "reconcile", "safe_summary"} <= functions.keys())
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
        "TIMEWEB_RU_PG_PUBLIC_IPV4_TLS=READY",
        "RU_PG_TIMEWEB_SYNTHETIC_PARITY=PASS",
    ):
        _require(forbidden not in source)


def _adapter_source(name: str) -> str:
    return (ROOT / "scripts" / name).read_text(encoding="utf-8")


def validate_adapters() -> None:
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
            "TIMEWEB_RU_PG_PUBLIC_IPV4_TLS=READY",
        ):
            _require(forbidden not in source)


def validate() -> None:
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))
    _require(isinstance(data, dict))
    validate_contract(data)
    validate_source(SOURCE.read_text(encoding="utf-8"))
    validate_adapters()


if __name__ == "__main__":
    validate()
    print("Allocation source checks passed; live integration remains disabled.")
