from __future__ import annotations

import ast
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/architecture/V10_V9_TO_V10_CONVERGENCE_CONTRACT.json"
PARITY_LEDGER = ROOT / "docs/architecture/V10_V9_TO_V10_PARITY_LEDGER.json"
AMENDMENT = (
    ROOT
    / "docs/master-plan/OMNI_CIO_V10_V9_TO_V10_CONVERGENCE_AND_LEGACY_RETIREMENT_AMENDMENT.md"
)
INDEX = ROOT / "docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md"
STATUS = ROOT / "knowledge/17_V10_CURRENT_PROGRAM_STATUS.md"
LEDGER = ROOT / "docs/updates/TIMEWEB_PLATFORM_CONSOLIDATION_EXECUTION_LEDGER.md"
AGENTS = ROOT / "AGENTS.md"
README = ROOT / "README.md"
CONTRIBUTING = ROOT / "CONTRIBUTING.md"
WORKFLOW = ROOT / ".github/workflows/v10-engineering-governance.yml"
PYPROJECT = ROOT / "pyproject.toml"

_ACCEPTED_V9 = "".join(("b9e4fabc", "b54f8f6e", "0ba206f0", "30c35f2f", "afa2ce62"))
_ACCEPTED_MAIN = "".join(("26bdc17c", "4e5d68c2", "62f47b99", "9e975b1e", "b8651858"))
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
_EXPECTED_TARGETS = (
    "omni_cio/portfolio/market_source_v1.py",
    "omni_cio/analytics/portfolio_source_v1.py",
    "omni_cio/analytics/cash_liquidity_v1.py",
    "omni_cio/analytics/operations_source_v1.py",
    "omni_cio/pretrade/purchase_capacity_v1.py",
    "omni_cio/pretrade/purchase_capacity_integrity_v1.py",
    "omni_cio/pretrade/sale_capacity_v1.py",
    "omni_cio/pretrade/sale_capacity_normalization_v1.py",
    "omni_cio/adapters/tinvest_order_compat_v1.py",
    "omni_cio/reconciliation",
)
_LEGACY_IMPORT_ROOTS = {
    "portfolio_market",
    "portfolio_analytics",
    "cash_liquidity",
    "operations_analytics",
    "purchase_capacity",
    "purchase_capacity_integrity",
    "sale_capacity",
    "sale_capacity_normalization",
    "sdk_order_compat",
    "broker_report_reconciliation",
}
_EXPECTED_RUNTIME_ROOTS = ("app.py", "app_v360.py", "app_v371.py", "main.py")
_VERIFIER_WORKFLOW_RELATIVE_PATHS = (
    Path(".github/workflows/v10-pr-fast-checks.yml"),
    Path(".github/workflows/regression-shield.yml"),
    Path(".github/workflows/self-hosted-windows-smoke.yml"),
)


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


def _joined_sha(value: object, code: str) -> str:
    if (
        not isinstance(value, list)
        or len(value) != 5
        or any(
            not isinstance(segment, str)
            or len(segment) != 8
            or any(character not in "0123456789abcdef" for character in segment)
            for segment in value
        )
    ):
        raise RuntimeError(code)
    return "".join(value)


def _validate_identity(contract: dict[str, Any]) -> None:
    expected = {
        "schema": "omni-cio.v10.v9-to-v10-convergence.v1",
        "status": "OWNER_APPROVED_BRANCH_LOCAL_ACTIVE",
        "decision_date": "2026-09-24",
        "system_update": "TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED",
        "branch": _BRANCH,
        "pull_request": 584,
        "current_checkpoint": "V9C-B",
    }
    for key, value in expected.items():
        if contract.get(key) != value:
            raise RuntimeError(f"V9C_IDENTITY_DRIFT:{key}")
    if (
        _joined_sha(
            contract.get("accepted_v9_repository_target_segments"),
            "V9C_ACCEPTED_V9_SHA_SEGMENTS_INVALID",
        )
        != _ACCEPTED_V9
    ):
        raise RuntimeError("V9C_IDENTITY_DRIFT:accepted_v9_repository_target")
    if (
        _joined_sha(
            contract.get("accepted_main_at_authority_restore_segments"),
            "V9C_ACCEPTED_MAIN_SHA_SEGMENTS_INVALID",
        )
        != _ACCEPTED_MAIN
    ):
        raise RuntimeError("V9C_IDENTITY_DRIFT:accepted_main_at_authority_restore")
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
    targets: list[str] = []
    for row in relocation:
        if not isinstance(row, dict):
            raise RuntimeError("V9C_RELOCATION_ROW_INVALID")
        if row.get("state") != "RELOCATED":
            raise RuntimeError("V9C_RELOCATION_STATE_DRIFT")
        source = row.get("source")
        target = row.get("target")
        if not isinstance(source, str) or not source:
            raise RuntimeError("V9C_RELOCATION_SOURCE_INVALID")
        if not isinstance(target, str) or not target.startswith("omni_cio/"):
            raise RuntimeError("V9C_RELOCATION_TARGET_INVALID")
        sources.append(source)
        targets.append(target)
        if (root / source).exists():
            raise RuntimeError(f"V9C_LEGACY_SOURCE_REINTRODUCED:{source}")
        if not (root / target).exists():
            raise RuntimeError(f"V9C_CANONICAL_TARGET_MISSING:{target}")

    if tuple(sources) != _EXPECTED_ROOT_SOURCES:
        raise RuntimeError("V9C_RELOCATION_SOURCE_SET_DRIFT")
    if tuple(targets) != _EXPECTED_TARGETS:
        raise RuntimeError("V9C_RELOCATION_TARGET_SET_DRIFT")

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


def _validate_no_legacy_imports(root: Path) -> None:
    source_paths = sorted({*root.rglob("*.py"), *root.rglob("*.pyfrag")})
    for path in source_paths:
        if any(part in {".git", ".venv", ".venv-ci"} for part in path.parts):
            continue
        relative = path.relative_to(root)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(relative))
        except (OSError, UnicodeDecodeError, SyntaxError) as exc:
            raise RuntimeError(f"V9C_PYTHON_SCAN_FAILED:{relative}:{exc}") from exc
        for node in ast.walk(tree):
            imported: list[str] = []
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
            for module in imported:
                root_name = module.split(".", 1)[0]
                if root_name in _LEGACY_IMPORT_ROOTS:
                    raise RuntimeError(
                        f"V9C_LEGACY_IMPORT_REINTRODUCED:{relative}:{module}"
                    )

            if isinstance(node, ast.Call) and node.args:
                dynamic_import = False
                if isinstance(node.func, ast.Name) and node.func.id == "__import__":
                    dynamic_import = True
                elif (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "import_module"
                ):
                    dynamic_import = True
                if dynamic_import and isinstance(node.args[0], ast.Constant):
                    module = node.args[0].value
                    if isinstance(module, str):
                        root_name = module.split(".", 1)[0]
                        if root_name in _LEGACY_IMPORT_ROOTS:
                            raise RuntimeError(
                                "V9C_LEGACY_DYNAMIC_IMPORT_REINTRODUCED:"
                                f"{relative}:{module}"
                            )


def _validate_verifier_ownership(root: Path) -> None:
    pyproject = _text(root / PYPROJECT.relative_to(ROOT))
    forbidden_pyproject = (
        '"portfolio_market"',
        '"portfolio_analytics"',
        '"cash_liquidity"',
        '"purchase_capacity"',
        '"purchase_capacity_integrity"',
        '"operations_analytics"',
        '"sdk_order_compat"',
        '"broker_report_reconciliation"',
    )
    for marker in forbidden_pyproject:
        if marker in pyproject:
            raise RuntimeError(f"V9C_PYPROJECT_LEGACY_TARGET:{marker}")

    required_pyproject = (
        '"omni_cio/portfolio"',
        '"omni_cio/reconciliation"',
        '"omni_cio.portfolio.market_source_v1"',
        '"omni_cio.analytics.portfolio_source_v1"',
        '"omni_cio.analytics.cash_liquidity_v1"',
        '"omni_cio.analytics.operations_source_v1"',
        '"omni_cio.pretrade.purchase_capacity_v1"',
        '"omni_cio.pretrade.purchase_capacity_integrity_v1"',
        '"omni_cio.pretrade.sale_capacity_v1"',
        '"omni_cio.pretrade.sale_capacity_normalization_v1"',
        '"omni_cio.adapters.tinvest_order_compat_v1"',
        '"omni_cio.reconciliation"',
    )
    for marker in required_pyproject:
        if marker not in pyproject:
            raise RuntimeError(f"V9C_PYPROJECT_CANONICAL_TARGET_MISSING:{marker}")

    workflow_paths = tuple(
        root / relative for relative in _VERIFIER_WORKFLOW_RELATIVE_PATHS
    )
    legacy_file_tokens = tuple(
        source for source in _EXPECTED_ROOT_SOURCES if source.endswith(".py")
    ) + ("broker_report_reconciliation ",)
    for workflow_path in workflow_paths:
        workflow = _text(workflow_path)
        for marker in legacy_file_tokens:
            if marker in workflow:
                raise RuntimeError(
                    f"V9C_WORKFLOW_LEGACY_TARGET:{workflow_path.name}:{marker}"
                )


def _validate_parity_ledger(root: Path) -> None:
    payload = _json(root / PARITY_LEDGER.relative_to(ROOT))
    rows = payload.get("capabilities")
    if not isinstance(rows, list):
        raise RuntimeError("V9C_PARITY_LEDGER_INVALID")
    indexed = {
        row.get("id"): row
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("id"), str)
    }
    required = {
        "PARITY-PORTFOLIO-CORE": "omni_cio/portfolio + omni_cio/analytics",
        "PARITY-PRETRADE-CAPACITY": "omni_cio/pretrade + omni_cio/adapters",
        "PARITY-OPERATIONS-ANALYTICS": "omni_cio/analytics/operations_source_v1.py",
        "PARITY-BROKER-REPORT-RECON": "omni_cio/reconciliation",
    }
    for row_id, owner in required.items():
        row = indexed.get(row_id)
        if not isinstance(row, dict):
            raise RuntimeError(f"V9C_PARITY_ROW_MISSING:{row_id}")
        if row.get("status") != "IMPLEMENTED":
            raise RuntimeError(f"V9C_PARITY_STATE_DRIFT:{row_id}")
        if row.get("v10_owner") != owner:
            raise RuntimeError(f"V9C_PARITY_OWNER_DRIFT:{row_id}")
        if not row.get("v9_tests_refs") or not row.get("evidence"):
            raise RuntimeError(f"V9C_PARITY_EVIDENCE_MISSING:{row_id}")


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
    if (
        merge.get("pr_584_merge_without_new_explicit_owner_instruction_allowed")
        is not False
    ):
        raise RuntimeError("V9C_UNAUTHORIZED_MAIN_MERGE")
    if merge.get("internal_checkpoint_merge_to_main_required") is not False:
        raise RuntimeError("V9C_INTERNAL_MAIN_MERGE_DRIFT")
    if (
        merge.get("exact_new_main_postmerge_required_after_owner_authorized_landing")
        is not True
    ):
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
            "V9C-B / DETERMINISTIC_SOURCE_RELOCATION",
            "must not be merged",
        ),
        INDEX.relative_to(ROOT): (
            "### 20. V9-to-V10 Convergence and Legacy Working-Tree Retirement",
            "OMNI_CIO_V10_V9_TO_V10_CONVERGENCE_AND_LEGACY_RETIREMENT_AMENDMENT.md",
        ),
        STATUS.relative_to(ROOT): (
            "V9C-B / DETERMINISTIC_SOURCE_RELOCATION",
            _ACCEPTED_V9,
            "PR #584",
        ),
        LEDGER.relative_to(ROOT): (
            "| V9C-A | AUTHORITY_AND_INVENTORY | CERTIFIED_GREEN |",
            "| V9C-B | DETERMINISTIC_SOURCE_RELOCATION | IN_PROGRESS |",
            "| V9C-F | WHOLE_TREE_LEGACY_ABSENCE_PROOF |",
        ),
        AGENTS.relative_to(ROOT): ("V9 migration source", "V9C-B", "PR #584"),
        README.relative_to(ROOT): ("V9 migration source", "V9C-B"),
        CONTRIBUTING.relative_to(ROOT): ("V9 migration source", "V9C-B"),
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
    _validate_no_legacy_imports(root)
    _validate_verifier_ownership(root)
    _validate_parity_ledger(root)
    _validate_deletion_and_authority(contract)
    _validate_documentation(root)
    _validate_workflow(root)


def main() -> int:
    try:
        validate()
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"V10_V9_TO_V10_CONVERGENCE=FAIL reason={exc}", file=sys.stderr)
        return 1
    print("V10_V9_TO_V10_CONVERGENCE=PASS checkpoint=V9C-B")
    print(f"Accepted V9 migration source: {_ACCEPTED_V9}")
    print("Legacy deterministic root imports: absent")
    print("Canonical V10 package relocation: complete")
    print("Stale v9 branch merge: forbidden")
    print("PR #584 main merge: requires a new explicit OWNER instruction")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
