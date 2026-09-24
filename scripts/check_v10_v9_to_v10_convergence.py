from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/architecture/V10_V9_TO_V10_CONVERGENCE_CONTRACT.json"
AMENDMENT = ROOT / "docs/master-plan/OMNI_CIO_V10_V9_TO_V10_CONVERGENCE_AND_LEGACY_RETIREMENT_AMENDMENT.md"
INDEX = ROOT / "docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md"
STATUS = ROOT / "knowledge/17_V10_CURRENT_PROGRAM_STATUS.md"
LEDGER = ROOT / "docs/updates/TIMEWEB_PLATFORM_CONSOLIDATION_EXECUTION_LEDGER.md"
AGENTS = ROOT / "AGENTS.md"
README = ROOT / "README.md"
CONTRIBUTING = ROOT / "CONTRIBUTING.md"
WORKFLOW = ROOT / ".github/workflows/v10-engineering-governance.yml"

_ACCEPTED_V9 = "b9e4fabcb54f8f6e0ba206f030c35f2fafa2ce62"
_ACCEPTED_MAIN = "26bdc17c4e5d68c262f47b999e975b1eb8651858"
_BRANCH = "system/timeweb-platform-consolidation-tw-b"
_REQUIRED_CHECKPOINTS = (
    "V9C-A_AUTHORITY_AND_INVENTORY",
    "V9C-B_DETERMINISTIC_SOURCE_RELOCATION",
    "V9C-C_RUNTIME_ENTRYPOINT_CONVERGENCE",
    "V9C-D_GPT_AND_RETIRED_PROVIDER_WORKTREE_RETIREMENT",
    "V9C-E_CI_RECOVERY_CONVERGENCE",
    "V9C-F_WHOLE_TREE_LEGACY_ABSENCE_PROOF",
)
_EXPECTED_ROOT_SOURCES = (
    "portfolio_market.py",
    "portfolio_analytics.py",
    "cash_liquidity.py",
    "operations_analytics.py",
    "purchase_capacity.py",
    "purchase_capacity_integrity.py",
    "sale_capacity.py",
    "sale_capacity_normalization.py",
    "sdk_order_compat.py",
    "broker_report_reconciliation",
)
_EXPECTED_RUNTIME_ROOTS = ("app.py", "app_v360.py", "app_v371.py", "main.py")


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(_text(path))
    if not isinstance(payload, dict):
        raise RuntimeError("V9C_CONTRACT_ROOT_INVALID")
    return payload


def _mapping(value: object, code: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(code)
    return value


def _validate_identity(contract: dict[str, Any]) -> None:
    expected = {
        "schema": "omni-cio.v10.v9-to-v10-convergence.v1",
        "status": "OWNER_APPROVED_BRANCH_LOCAL_ACTIVE",
        "decision_date": "2026-09-24",
        "system_update": "TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED",
        "branch": _BRANCH,
        "pull_request": 584,
        "accepted_v9_repository_target": _ACCEPTED_V9,
        "accepted_main_at_authority_restore": _ACCEPTED_MAIN,
        "current_checkpoint": "V9C-A",
    }
    for key, value in expected.items():
        if contract.get(key) != value:
            raise RuntimeError(f"V9C_IDENTITY_DRIFT:{key}")
    if tuple(contract.get("checkpoints", ())) != _REQUIRED_CHECKPOINTS:
        raise RuntimeError("V9C_CHECKPOINT_ORDER_DRIFT")


def _validate_history_policy(contract: dict[str, Any]) -> None:
    policy = _mapping(contract.get("history_policy"), "V9C_HISTORY_POLICY_INVALID")
    expected = {
        "stale_v9_branch_direct_merge_allowed": False,
        "accepted_v9_target_already_in_main_lineage": True,
        "git_history_rewrite_allowed": False,
        "git_history_is_historical_archive": True,
        "working_tree_legacy_retirement_allowed_after_gate": True,
    }
    for key, value in expected.items():
        if policy.get(key) != value:
            raise RuntimeError(f"V9C_HISTORY_POLICY_DRIFT:{key}")


def _validate_runtime_target(contract: dict[str, Any]) -> None:
    runtime = _mapping(contract.get("final_runtime"), "V9C_RUNTIME_TARGET_INVALID")
    expected = {
        "product_line": "V10_ONLY_AFTER_CONVERGENCE_AND_OWNER_ACCEPTED_LANDING",
        "provider": "TIMEWEB_APP_PLATFORM",
        "application_entrypoint": "apps.api.hosted_runtime:create_app",
        "database": "TIMEWEB_POSTGRESQL_18_AFTER_TW_D",
        "human_login_provider": "TELEGRAM_LOGIN_ONLY",
    }
    for key, value in expected.items():
        if runtime.get(key) != value:
            raise RuntimeError(f"V9C_RUNTIME_TARGET_DRIFT:{key}")


def _validate_inventory(root: Path, contract: dict[str, Any]) -> None:
    relocation = contract.get("root_relocation_plan")
    if not isinstance(relocation, list):
        raise RuntimeError("V9C_RELOCATION_PLAN_INVALID")
    sources: list[str] = []
    for row in relocation:
        if not isinstance(row, dict):
            raise RuntimeError("V9C_RELOCATION_ROW_INVALID")
        if row.get("state") != "PLANNED":
            raise RuntimeError("V9C_RELOCATION_PREMATURE_STATE")
        source = row.get("source")
        target = row.get("target")
        if not isinstance(source, str) or not source:
            raise RuntimeError("V9C_RELOCATION_SOURCE_INVALID")
        if not isinstance(target, str) or not target.startswith("omni_cio/"):
            raise RuntimeError("V9C_RELOCATION_TARGET_INVALID")
        sources.append(source)
        if not (root / source).exists():
            raise RuntimeError(f"V9C_SOURCE_MISSING:{source}")
    if tuple(sources) != _EXPECTED_ROOT_SOURCES:
        raise RuntimeError("V9C_RELOCATION_SOURCE_SET_DRIFT")

    retirements = contract.get("runtime_retirement_plan")
    if not isinstance(retirements, list):
        raise RuntimeError("V9C_RUNTIME_RETIREMENT_PLAN_INVALID")
    runtime_paths: list[str] = []
    for row in retirements:
        if not isinstance(row, dict):
            raise RuntimeError("V9C_RUNTIME_RETIREMENT_ROW_INVALID")
        if row.get("state") != "BLOCKED_UNTIL_V9C_C":
            raise RuntimeError("V9C_RUNTIME_RETIREMENT_PREMATURE")
        path = row.get("path")
        if not isinstance(path, str):
            raise RuntimeError("V9C_RUNTIME_RETIREMENT_PATH_INVALID")
        runtime_paths.append(path)
        if not (root / path).is_file():
            raise RuntimeError(f"V9C_RUNTIME_SOURCE_MISSING:{path}")
    if tuple(runtime_paths) != _EXPECTED_RUNTIME_ROOTS:
        raise RuntimeError("V9C_RUNTIME_SOURCE_SET_DRIFT")


def _validate_deletion_and_authority(contract: dict[str, Any]) -> None:
    gate = _mapping(contract.get("deletion_gate"), "V9C_DELETION_GATE_INVALID")
    required = {
        "replacement_exists",
        "current_consumers_migrated",
        "parity_or_contract_tests_green",
        "required_runtime_ci_consumer_count_zero",
        "current_recovery_proven",
        "security_and_tenant_boundaries_preserved",
        "no_guard_weakening",
    }
    if set(gate) != required or any(gate[key] is not True for key in required):
        raise RuntimeError("V9C_DELETION_GATE_DRIFT")

    merge = _mapping(contract.get("merge_authority"), "V9C_MERGE_AUTHORITY_INVALID")
    if merge.get("pr_584_merge_without_new_explicit_owner_instruction_allowed") is not False:
        raise RuntimeError("V9C_UNAUTHORIZED_MAIN_MERGE")
    if merge.get("internal_checkpoint_merge_to_main_required") is not False:
        raise RuntimeError("V9C_INTERNAL_MAIN_MERGE_DRIFT")
    if merge.get("exact_new_main_postmerge_required_after_owner_authorized_landing") is not True:
        raise RuntimeError("V9C_POSTMERGE_EVIDENCE_DRIFT")

    protected = _mapping(
        contract.get("protected_invariants"),
        "V9C_PROTECTED_INVARIANTS_INVALID",
    )
    if any(value is not False for value in protected.values()):
        raise RuntimeError("V9C_PROTECTED_AUTHORITY_WIDENED")


def _validate_documentation(root: Path) -> None:
    required = {
        AMENDMENT.relative_to(ROOT): (
            "accepted V9 repository target",
            "stale",
            "V9C-A / AUTHORITY_AND_INVENTORY",
            "must not be merged",
        ),
        INDEX.relative_to(ROOT): (
            "### 20. V9-to-V10 Convergence and Legacy Working-Tree Retirement",
            "OMNI_CIO_V10_V9_TO_V10_CONVERGENCE_AND_LEGACY_RETIREMENT_AMENDMENT.md",
        ),
        STATUS.relative_to(ROOT): (
            "V9C-A / AUTHORITY_AND_INVENTORY",
            _ACCEPTED_V9,
            "PR #584",
        ),
        LEDGER.relative_to(ROOT): (
            "V9C-A / AUTHORITY_AND_INVENTORY",
            "V9C-F / WHOLE_TREE_LEGACY_ABSENCE_PROOF",
        ),
        AGENTS.relative_to(ROOT): ("V9 migration source", "V9C-A", "PR #584"),
        README.relative_to(ROOT): ("V9 migration source", "V9C-A"),
        CONTRIBUTING.relative_to(ROOT): ("V9 migration source", "V9C-A"),
    }
    for relative, markers in required.items():
        source = _text(root / relative)
        for marker in markers:
            if marker not in source:
                raise RuntimeError(f"V9C_DOCUMENTATION_DRIFT:{relative}:{marker}")


def _validate_workflow(root: Path) -> None:
    workflow = _text(root / WORKFLOW.relative_to(ROOT))
    for marker in (
        "Verify V9-to-V10 convergence authority",
        "python scripts/check_v10_v9_to_v10_convergence.py",
        "scripts/check_v10_v9_to_v10_convergence.py",
        "tests.test_v10_v9_to_v10_convergence",
    ):
        if marker not in workflow:
            raise RuntimeError(f"V9C_WORKFLOW_DRIFT:{marker}")


def validate(root: Path = ROOT) -> None:
    contract = _json(root / CONTRACT.relative_to(ROOT))
    _validate_identity(contract)
    _validate_history_policy(contract)
    _validate_runtime_target(contract)
    _validate_inventory(root, contract)
    _validate_deletion_and_authority(contract)
    _validate_documentation(root)
    _validate_workflow(root)


def main() -> int:
    try:
        validate()
    except (OSError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"V10_V9_TO_V10_CONVERGENCE=FAIL reason={exc}", file=sys.stderr)
        return 1
    print("V10_V9_TO_V10_CONVERGENCE=PASS checkpoint=V9C-A")
    print(f"Accepted V9 migration source: {_ACCEPTED_V9}")
    print("Stale v9 branch merge: forbidden")
    print("PR #584 main merge: requires a new explicit OWNER instruction")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
