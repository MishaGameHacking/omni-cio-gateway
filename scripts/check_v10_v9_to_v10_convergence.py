from __future__ import annotations

import ast
import json
from pathlib import Path, PurePath
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
DOCKERFILE = ROOT / "Dockerfile"
HOSTED_RECOVERY_CONTRACT = ROOT / "infrastructure/postgres/hosted-recovery-contract.json"
TIMEWEB_DELIVERY_CONTRACT = ROOT / "docs/architecture/V10_TIMEWEB_FULL_PRODUCTION_DELIVERY_CONTRACT.json"

_ACCEPTED_V9 = "".join(("b9e4fabc", "b54f8f6e", "0ba206f0", "30c35f2f", "afa2ce62"))
_ACCEPTED_MAIN = "".join(("26bdc17c", "4e5d68c2", "62f47b99", "9e975b1e", "b8651858"))
_BRANCH = "system/timeweb-platform-consolidation-tw-b"
_CURRENT_CHECKPOINT = "V9C-F"
_V9_MIGRATION_SOURCE_MARKER = "V9 migration source"
_REQUIRED_CHECKPOINTS = (
    "V9C-A_AUTHORITY_AND_INVENTORY",
    "V9C-B_DETERMINISTIC_SOURCE_RELOCATION",
    "V9C-C_RUNTIME_ENTRYPOINT_CONVERGENCE",
    "V9C-D_GPT_AND_RETIRED_PROVIDER_WORKTREE_RETIREMENT",
    "V9C-E_CI_RECOVERY_CONVERGENCE",
    "V9C-F_WHOLE_TREE_LEGACY_ABSENCE_PROOF",
)
_EXPECTED_CHECKPOINT_STATES = {
    "V9C-A": "CERTIFIED_GREEN",
    "V9C-B": "CERTIFIED_GREEN",
    "V9C-C": "CERTIFIED_GREEN",
    "V9C-D": "CERTIFIED_GREEN",
    "V9C-E": "IMPLEMENTED_VERIFICATION_PENDING",
    "V9C-F": "IMPLEMENTED_VERIFICATION_PENDING",
}
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
_LEGACY_PATH_LITERAL_ALLOWLIST = frozenset(
    {
        Path("scripts/check_v10_v9_to_v10_convergence.py"),
        Path("tests/test_v10_v9_to_v10_convergence.py"),
    }
)
_LEGACY_FILE_PATH_LITERALS = frozenset(
    source for source in _EXPECTED_ROOT_SOURCES if source.endswith(".py")
)
_LEGACY_DIRECTORY_PATH_PREFIXES = ("broker_report_reconciliation/",)
_NONCANONICAL_RECONCILIATION_PATH_PREFIXES = ("omni_cio/reconciliation/broker_report/",)

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
_CURRENT_RUNTIME_ENTRYPOINT = Path("apps/api/hosted_runtime.py")
_LEGACY_RUNTIME_MODULE_ROOTS = frozenset({"app", "app_v360", "app_v371", "main"})
_RETIRED_PROVIDER_MODULE_MARKERS = frozenset(
    {"cloudflare", "neon", "render", "cloudru", "cloud_ru", "vk_id"}
)
_RETIRED_PROVIDER_AUTHORITIES = ("RENDER", "CLOUDFLARE", "NEON", "CLOUD_RU", "VK_ID")
_CURRENT_GPT_AUTHORITY_PATHS = (
    Path("gpt/PROJECT_INSTRUCTIONS.md"),
    Path("gpt/NEW_CHAT_PROMPT.md"),
)
_PROTECTED_V9_GPT_RECOVERY_PATHS = (
    Path("gpt/README.md"),
    Path("gpt/CONFIGURATION.md"),
    Path("gpt/MY_GPT_SETUP_RUNBOOK.md"),
    Path("gpt/SETUP_INDEX.md"),
    Path("gpt/BOT_ONLY_FILE_MANIFEST.md"),
    Path("gpt/SECRETS_AND_RENDER.md"),
)
_RETIRED_PROVIDER_WORKFLOW_PATHS = (
    Path(".github/workflows/v10-cloudflare-candidate-deploy.yml"),
    Path(".github/workflows/v10-cloudflare-production-release.yml"),
    Path(".github/workflows/v10-cloudflare-provider-readiness.yml"),
    Path(".github/workflows/v10-neon-egress-boundary.yml"),
)
_PROTECTED_V9_GPT_MARKER = "PROTECTED V9 RECOVERY ONLY — NOT CURRENT V10 AUTHORITY"


def _repository_contract_path(path: PurePath) -> str:
    """Serialize repository-relative paths independently of runner OS semantics."""
    return path.as_posix()


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
        "current_checkpoint": _CURRENT_CHECKPOINT,
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
    states = _mapping(contract.get("checkpoint_states"), "V9C_CHECKPOINT_STATES_INVALID")
    if states != _EXPECTED_CHECKPOINT_STATES:
        raise RuntimeError("V9C_CHECKPOINT_STATE_DRIFT")


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
        "protected_v9_compatibility_entrypoint": "app:app",
        "protected_v9_compatibility_preserved": True,
        "v10_runtime_legacy_import_allowed": False,
    }
    for key, value in expected.items():
        if runtime.get(key) != value:
            raise RuntimeError(f"V9C_RUNTIME_TARGET_DRIFT:{key}")


def _relocation_row(
    root: Path,
    row: object,
) -> tuple[str, str]:
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
    if (root / source).exists():
        raise RuntimeError(f"V9C_LEGACY_SOURCE_REINTRODUCED:{source}")
    if not (root / target).exists():
        raise RuntimeError(f"V9C_CANONICAL_TARGET_MISSING:{target}")
    return source, target


def _runtime_retirement_path(root: Path, row: object) -> str:
    if not isinstance(row, dict):
        raise RuntimeError("V9C_RUNTIME_RETIREMENT_ROW_INVALID")
    if row.get("state") != "PROTECTED_V9_COMPATIBILITY_ONLY":
        raise RuntimeError("V9C_RUNTIME_COMPATIBILITY_STATE_DRIFT")
    if row.get("v10_supported_runtime_consumer_allowed") is not False:
        raise RuntimeError("V9C_RUNTIME_COMPATIBILITY_AUTHORITY_DRIFT")

    path = row.get("path")
    if not isinstance(path, str):
        raise RuntimeError("V9C_RUNTIME_RETIREMENT_PATH_INVALID")
    if not (root / path).is_file():
        raise RuntimeError(f"V9C_PROTECTED_V9_RUNTIME_MISSING:{path}")
    return path


def _validate_inventory(root: Path, contract: dict[str, Any]) -> None:
    relocation = contract.get("root_relocation_plan")
    if not isinstance(relocation, list):
        raise RuntimeError("V9C_RELOCATION_PLAN_INVALID")

    relocated = [_relocation_row(root, row) for row in relocation]
    sources = tuple(source for source, _ in relocated)
    targets = tuple(target for _, target in relocated)
    if sources != _EXPECTED_ROOT_SOURCES:
        raise RuntimeError("V9C_RELOCATION_SOURCE_SET_DRIFT")
    if targets != _EXPECTED_TARGETS:
        raise RuntimeError("V9C_RELOCATION_TARGET_SET_DRIFT")

    retirements = contract.get("runtime_retirement_plan")
    if not isinstance(retirements, list):
        raise RuntimeError("V9C_RUNTIME_RETIREMENT_PLAN_INVALID")
    runtime_paths = tuple(_runtime_retirement_path(root, row) for row in retirements)
    if runtime_paths != _EXPECTED_RUNTIME_ROOTS:
        raise RuntimeError("V9C_RUNTIME_SOURCE_SET_DRIFT")


def _python_scan_paths(root: Path) -> list[Path]:
    paths = sorted({*root.rglob("*.py"), *root.rglob("*.pyfrag")})
    return [
        path
        for path in paths
        if not any(part in {".git", ".venv", ".venv-ci"} for part in path.parts)
    ]


def _parsed_python(root: Path, path: Path, code: str) -> tuple[Path, ast.AST]:
    relative = path.relative_to(root)
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(relative))
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        raise RuntimeError(f"{code}:{relative}:{exc}") from exc
    return relative, tree


def _imported_modules(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom) and node.module:
        return [node.module]
    return []


def _dynamic_import_module(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Call) or not node.args:
        return None
    named_import = isinstance(node.func, ast.Name) and node.func.id == "__import__"
    module_import = (
        isinstance(node.func, ast.Attribute) and node.func.attr == "import_module"
    )
    if not (named_import or module_import):
        return None
    first = node.args[0]
    if not isinstance(first, ast.Constant) or not isinstance(first.value, str):
        return None
    return first.value


def _module_name(relative: Path) -> str:
    module_path = (
        relative.parent if relative.name == "__init__.py" else relative.with_suffix("")
    )
    return ".".join(module_path.parts)


def _local_module_path(root: Path, module: str) -> Path | None:
    if not module:
        return None
    relative = Path(*module.split("."))
    candidates = (relative.with_suffix(".py"), relative / "__init__.py")
    return next(
        (candidate for candidate in candidates if (root / candidate).is_file()),
        None,
    )


def _import_from_base(relative: Path, node: ast.ImportFrom) -> str | None:
    if node.level == 0:
        return node.module
    package_parts = _module_name(relative).split(".")
    if relative.name != "__init__.py":
        package_parts = package_parts[:-1]
    ascent = node.level - 1
    if ascent > len(package_parts):
        return None
    base_parts = package_parts[: len(package_parts) - ascent]
    if node.module:
        base_parts.extend(node.module.split("."))
    return ".".join(part for part in base_parts if part)


def _runtime_import_candidates(relative: Path, node: ast.AST) -> list[str]:
    modules: list[str] = []
    if isinstance(node, ast.Import):
        modules.extend(alias.name for alias in node.names)
    elif isinstance(node, ast.ImportFrom):
        base = _import_from_base(relative, node)
        if base:
            modules.append(base)
            modules.extend(
                f"{base}.{alias.name}" for alias in node.names if alias.name != "*"
            )
    return modules


def _reject_legacy_runtime_module(relative: Path, module: str) -> None:
    if module.split(".", 1)[0] in _LEGACY_RUNTIME_MODULE_ROOTS:
        raise RuntimeError(f"V9C_CURRENT_RUNTIME_LEGACY_IMPORT:{relative}:{module}")


def _retired_provider_marker(module: str) -> str | None:
    normalized = module.casefold().replace("-", "_")
    parts = normalized.split(".")
    for marker in _RETIRED_PROVIDER_MODULE_MARKERS:
        if marker in parts:
            return marker
        if any(part.startswith(marker + "_") for part in parts):
            return marker
    return None


def _reject_retired_provider_runtime_module(relative: Path, module: str) -> None:
    marker = _retired_provider_marker(module)
    if marker is not None:
        raise RuntimeError(
            f"V9C_CURRENT_RUNTIME_RETIRED_PROVIDER_IMPORT:{relative}:{marker}"
        )


def _runtime_dependency_modules(
    relative: Path,
    tree: ast.AST,
) -> list[str]:
    modules: list[str] = []
    for node in ast.walk(tree):
        modules.extend(_runtime_import_candidates(relative, node))
        dynamic_module = _dynamic_import_module(node)
        if dynamic_module is not None:
            modules.append(dynamic_module)
    return modules


def _append_local_runtime_dependency(
    *,
    root: Path,
    relative: Path,
    module: str,
    queue: list[Path],
    visited: set[Path],
) -> None:
    _reject_legacy_runtime_module(relative, module)
    _reject_retired_provider_runtime_module(relative, module)
    local = _local_module_path(root, module)
    if local is not None and local not in visited:
        queue.append(local)


def _validate_current_runtime_dependency_graph(root: Path) -> int:
    entrypoint = root / _CURRENT_RUNTIME_ENTRYPOINT
    if not entrypoint.is_file():
        raise RuntimeError("V9C_CURRENT_RUNTIME_ENTRYPOINT_MISSING")

    queue = [_CURRENT_RUNTIME_ENTRYPOINT]
    visited: set[Path] = set()
    while queue:
        relative = queue.pop()
        if relative in visited:
            continue
        visited.add(relative)
        _, tree = _parsed_python(
            root,
            root / relative,
            "V9C_CURRENT_RUNTIME_SCAN_FAILED",
        )
        for module in _runtime_dependency_modules(relative, tree):
            _append_local_runtime_dependency(
                root=root,
                relative=relative,
                module=module,
                queue=queue,
                visited=visited,
            )
    return len(visited)


def _validate_runtime_entrypoint_convergence(root: Path) -> None:
    dockerfile = _text(root / DOCKERFILE.relative_to(ROOT))
    if "apps.api.hosted_runtime:create_app" not in dockerfile:
        raise RuntimeError("V9C_TIMEWEB_ENTRYPOINT_MISSING")
    for forbidden in ("app:app", "main:app", "app_v360", "app_v371"):
        if forbidden in dockerfile:
            raise RuntimeError(f"V9C_TIMEWEB_LEGACY_ENTRYPOINT_CONSUMER:{forbidden}")
    if _validate_current_runtime_dependency_graph(root) < 2:
        raise RuntimeError("V9C_CURRENT_RUNTIME_GRAPH_TOO_SHALLOW")


def _workflow_events(source: str) -> tuple[str, ...]:
    lines = source.splitlines()
    try:
        start = lines.index("on:")
    except ValueError as exc:
        raise RuntimeError("V9C_RETIRED_WORKFLOW_TRIGGER_BLOCK_MISSING") from exc

    events: list[str] = []
    for line in lines[start + 1 :]:
        if line and not line.startswith(" "):
            break
        if line.startswith("  ") and not line.startswith("    "):
            value = line.strip()
            if value.endswith(":"):
                events.append(value[:-1])
    return tuple(events)


def _workflow_job_blocks(source: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
    lines = source.splitlines()
    try:
        start = lines.index("jobs:")
    except ValueError as exc:
        raise RuntimeError("V9C_RETIRED_WORKFLOW_JOBS_BLOCK_MISSING") from exc

    blocks: list[tuple[str, tuple[str, ...]]] = []
    current_name: str | None = None
    current_lines: list[str] = []
    for line in lines[start + 1 :]:
        if line and not line.startswith(" "):
            break
        is_job = (
            line.startswith("  ")
            and not line.startswith("    ")
            and line.strip().endswith(":")
        )
        if is_job:
            if current_name is not None:
                blocks.append((current_name, tuple(current_lines)))
            current_name = line.strip()[:-1]
            current_lines = []
            continue
        if current_name is not None:
            current_lines.append(line)
    if current_name is not None:
        blocks.append((current_name, tuple(current_lines)))
    return tuple(blocks)


def _validate_retired_provider_workflow(root: Path, relative: Path) -> None:
    source = _text(root / relative)
    if "ARCHIVE-IN-PLACE" not in source:
        raise RuntimeError(f"V9C_RETIRED_WORKFLOW_ARCHIVE_MARKER_MISSING:{relative}")
    if _workflow_events(source) != ("workflow_dispatch",):
        raise RuntimeError(f"V9C_RETIRED_WORKFLOW_TRIGGER_DRIFT:{relative}")
    blocks = _workflow_job_blocks(source)
    if not blocks:
        raise RuntimeError(f"V9C_RETIRED_WORKFLOW_JOB_SET_EMPTY:{relative}")
    for job, lines in blocks:
        if "    if: ${{ false }}" not in lines:
            raise RuntimeError(
                f"V9C_RETIRED_WORKFLOW_NOT_HARD_DISABLED:{relative}:{job}"
            )


def _validate_gpt_authority(root: Path) -> None:
    for relative in _CURRENT_GPT_AUTHORITY_PATHS:
        source = _text(root / relative)
        for marker in (
            "CURRENT AMENDMENT-21",
            "Timeweb Cloud",
            "Telegram Login",
            _CURRENT_CHECKPOINT,
        ):
            if marker not in source:
                raise RuntimeError(
                    f"V9C_CURRENT_GPT_AUTHORITY_DRIFT:{relative}:{marker}"
                )

    for relative in _PROTECTED_V9_GPT_RECOVERY_PATHS:
        source = _text(root / relative)
        if _PROTECTED_V9_GPT_MARKER not in source:
            raise RuntimeError(f"V9C_V9_GPT_RECOVERY_MARKER_MISSING:{relative}")


def _require_retirement_value(
    retirement: dict[str, Any],
    key: str,
    expected: object,
    code: str,
) -> None:
    if retirement.get(key) != expected:
        raise RuntimeError(code)


def _repository_contract_paths(paths: tuple[Path, ...]) -> tuple[str, ...]:
    return tuple(_repository_contract_path(path) for path in paths)


def _validate_provider_retirement_policy(retirement: dict[str, Any]) -> None:
    history_key = (
        "history_only_worktree_artifacts_allowed_when_required_for_"
        "provenance_or_protected_v9_recovery"
    )
    expected = (
        ("checkpoint", "V9C-D", "V9C_PROVIDER_RETIREMENT_CHECKPOINT_DRIFT"),
        (
            "providers",
            list(_RETIRED_PROVIDER_AUTHORITIES),
            "V9C_PROVIDER_RETIREMENT_SET_DRIFT",
        ),
        (
            "current_feature_authority",
            False,
            "V9C_PROVIDER_RETIREMENT_AUTHORITY_WIDENED",
        ),
        (
            "current_runtime_provider_module_import_allowed",
            False,
            "V9C_PROVIDER_RUNTIME_IMPORT_AUTHORITY_WIDENED",
        ),
        (
            "zero_current_consumer_proof_required",
            True,
            "V9C_PROVIDER_ZERO_CONSUMER_PROOF_DISABLED",
        ),
        (
            "history_preserved_in_git",
            True,
            "V9C_PROVIDER_HISTORY_POLICY_DRIFT",
        ),
        (
            history_key,
            True,
            "V9C_PROVIDER_HISTORY_WORKTREE_POLICY_DRIFT",
        ),
        (
            "current_gpt_authority",
            list(_repository_contract_paths(_CURRENT_GPT_AUTHORITY_PATHS)),
            "V9C_CURRENT_GPT_AUTHORITY_SET_DRIFT",
        ),
        (
            "protected_v9_gpt_recovery",
            list(_repository_contract_paths(_PROTECTED_V9_GPT_RECOVERY_PATHS)),
            "V9C_V9_GPT_RECOVERY_SET_DRIFT",
        ),
        (
            "retired_provider_workflows",
            list(_repository_contract_paths(_RETIRED_PROVIDER_WORKFLOW_PATHS)),
            "V9C_RETIRED_WORKFLOW_SET_DRIFT",
        ),
        (
            "retired_provider_workflow_state",
            "MANUAL_ONLY_HARD_DISABLED_HISTORY",
            "V9C_RETIRED_WORKFLOW_STATE_DRIFT",
        ),
    )
    for key, expected_value, code in expected:
        _require_retirement_value(retirement, key, expected_value, code)


def _validate_provider_worktree_retirement(
    root: Path,
    contract: dict[str, Any],
) -> None:
    retirement = _mapping(
        contract.get("provider_worktree_retirement"),
        "V9C_PROVIDER_RETIREMENT_INVALID",
    )
    _validate_provider_retirement_policy(retirement)
    _validate_gpt_authority(root)
    for relative in _RETIRED_PROVIDER_WORKFLOW_PATHS:
        _validate_retired_provider_workflow(root, relative)


def _reject_legacy_import(relative: Path, module: str, *, dynamic: bool) -> None:
    if module.split(".", 1)[0] not in _LEGACY_IMPORT_ROOTS:
        return
    code = (
        "V9C_LEGACY_DYNAMIC_IMPORT_REINTRODUCED"
        if dynamic
        else "V9C_LEGACY_IMPORT_REINTRODUCED"
    )
    raise RuntimeError(f"{code}:{relative}:{module}")


def _validate_no_legacy_imports(root: Path) -> None:
    for path in _python_scan_paths(root):
        relative, tree = _parsed_python(root, path, "V9C_PYTHON_SCAN_FAILED")
        for node in ast.walk(tree):
            for module in _imported_modules(node):
                _reject_legacy_import(relative, module, dynamic=False)
            dynamic_module = _dynamic_import_module(node)
            if dynamic_module is not None:
                _reject_legacy_import(relative, dynamic_module, dynamic=True)


def _validate_legacy_path_literal(relative: Path, literal: str) -> None:
    normalized = literal.replace("\\", "/")
    is_legacy_file = normalized in _LEGACY_FILE_PATH_LITERALS
    is_legacy_directory = normalized.startswith(_LEGACY_DIRECTORY_PATH_PREFIXES)
    if is_legacy_file or is_legacy_directory:
        raise RuntimeError(
            f"V9C_LEGACY_PATH_CONSUMER_REINTRODUCED:{relative}:{normalized}"
        )
    if normalized.startswith(_NONCANONICAL_RECONCILIATION_PATH_PREFIXES):
        raise RuntimeError(
            f"V9C_NONCANONICAL_RECONCILIATION_PATH_CONSUMER:{relative}:{normalized}"
        )


def _validate_no_stale_relocation_path_consumers(root: Path) -> None:
    for path in _python_scan_paths(root):
        relative = path.relative_to(root)
        if relative in _LEGACY_PATH_LITERAL_ALLOWLIST:
            continue
        relative, tree = _parsed_python(
            root,
            path,
            "V9C_PATH_CONSUMER_SCAN_FAILED",
        )
        literals = (
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        )
        for literal in literals:
            _validate_legacy_path_literal(relative, literal)


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


def _validate_ci_recovery_convergence(root: Path) -> None:
    recovery = _json(root / HOSTED_RECOVERY_CONTRACT.relative_to(ROOT))
    authority = _mapping(recovery.get("authority"), "V9C_CURRENT_RECOVERY_AUTHORITY_INVALID")
    expected_authority = {
        "provider": "PROVIDER_NEUTRAL_POSTGRESQL_18",
        "source_only": True,
        "provider_apply_authorized": False,
        "public_ingress_allowed": False,
        "public_multi_user_enabled": False,
        "trading_methods_enabled": False,
        "real_trading_enabled": False,
        "protected_v9_entrypoint": "app:app",
        "wp23_unlocked": False,
    }
    for key, value in expected_authority.items():
        if authority.get(key) != value:
            raise RuntimeError(f"V9C_CURRENT_RECOVERY_PROVIDER_DRIFT:{key}")
    restore = _mapping(recovery.get("restore"), "V9C_CURRENT_RECOVERY_RESTORE_INVALID")
    for key in (
        "replacement_runtime_required",
        "accepted_release_sha_match_required",
        "migration_state_match_required",
        "schema_state_match_required",
        "tenant_boundary_match_required",
        "restore_catalog_recheck_required",
        "rollback_to_last_accepted_release_required",
        "temporary_state_cleanup_required",
    ):
        if restore.get(key) is not True:
            raise RuntimeError(f"V9C_CURRENT_RECOVERY_RESTORE_DRIFT:{key}")
    if restore.get("restore_to_original_database_in_rehearsal_allowed") is not False:
        raise RuntimeError("V9C_CURRENT_RECOVERY_REHEARSAL_AUTHORITY_WIDENED")
    delivery = _json(root / TIMEWEB_DELIVERY_CONTRACT.relative_to(ROOT))
    release = _mapping(delivery.get("release"), "V9C_TIMEWEB_RELEASE_AUTHORITY_INVALID")
    expected_release = {
        "source_authority": "GITHUB_PROTECTED_MAIN",
        "deployment_platform": "TIMEWEB_APP_PLATFORM",
        "exact_commit_sha_required": True,
        "production_autodeploy_allowed": False,
        "deployed_sha_must_equal_accepted_main_sha": True,
        "last_known_good_rollback_required": True,
        "mismatch_state": "OUT_OF_SYNC/DEPLOYMENT_BLOCKED",
    }
    for key, value in expected_release.items():
        if release.get(key) != value:
            raise RuntimeError(f"V9C_TIMEWEB_RELEASE_AUTHORITY_DRIFT:{key}")


def _validate_whole_tree_legacy_absence(root: Path) -> None:
    _validate_no_legacy_imports(root)
    _validate_no_stale_relocation_path_consumers(root)
    if _validate_current_runtime_dependency_graph(root) < 2:
        raise RuntimeError("V9C_CURRENT_RUNTIME_GRAPH_TOO_SHALLOW")


def _validate_documentation(root: Path) -> None:
    required = {
        AMENDMENT.relative_to(ROOT): (
            "accepted V9 repository target",
            "stale",
            "V9C-D / GPT_AND_RETIRED_PROVIDER_WORKTREE_RETIREMENT",
            "V9C-E / CI_RECOVERY_CONVERGENCE",
            f"{_CURRENT_CHECKPOINT} / WHOLE_TREE_LEGACY_ABSENCE_PROOF",
            "verification pending",
            "must not be merged",
            "protected V9 compatibility",
        ),
        INDEX.relative_to(ROOT): (
            "### 20. V9-to-V10 Convergence and Legacy Working-Tree Retirement",
            "OMNI_CIO_V10_V9_TO_V10_CONVERGENCE_AND_LEGACY_RETIREMENT_AMENDMENT.md",
        ),
        STATUS.relative_to(ROOT): (
            f"{_CURRENT_CHECKPOINT} / WHOLE_TREE_LEGACY_ABSENCE_PROOF",
            _ACCEPTED_V9,
            "PR #584",
        ),
        LEDGER.relative_to(ROOT): (
            "| V9C-D | GPT_AND_RETIRED_PROVIDER_WORKTREE_RETIREMENT | CERTIFIED_GREEN |",
            "| V9C-E | CI_RECOVERY_CONVERGENCE | IMPLEMENTED_VERIFICATION_PENDING |",
            f"| {_CURRENT_CHECKPOINT} | WHOLE_TREE_LEGACY_ABSENCE_PROOF | IMPLEMENTED_VERIFICATION_PENDING |",
        ),
        AGENTS.relative_to(ROOT): (
            _V9_MIGRATION_SOURCE_MARKER,
            _CURRENT_CHECKPOINT,
            "PR #584",
        ),
        README.relative_to(ROOT): (_V9_MIGRATION_SOURCE_MARKER, _CURRENT_CHECKPOINT),
        CONTRIBUTING.relative_to(ROOT): (
            _V9_MIGRATION_SOURCE_MARKER,
            _CURRENT_CHECKPOINT,
        ),
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
    _validate_runtime_entrypoint_convergence(root)
    _validate_provider_worktree_retirement(root, contract)
    _validate_verifier_ownership(root)
    _validate_parity_ledger(root)
    _validate_deletion_and_authority(contract)
    _validate_ci_recovery_convergence(root)
    _validate_whole_tree_legacy_absence(root)
    _validate_documentation(root)
    _validate_workflow(root)


def main() -> int:
    try:
        validate()
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"V10_V9_TO_V10_CONVERGENCE=FAIL reason={exc}", file=sys.stderr)
        return 1
    print(f"V10_V9_TO_V10_CONVERGENCE=PASS checkpoint={_CURRENT_CHECKPOINT}")
    print(f"Accepted V9 migration source: {_ACCEPTED_V9}")
    print("Legacy deterministic root imports: absent")
    print("Canonical V10 package relocation: complete")
    print("Timeweb V10 runtime dependency on protected V9 roots: absent")
    print("Timeweb V10 runtime dependency on retired provider modules: absent")
    print("Retired provider workflows: manual-only and hard-disabled history")
    print("Protected V9 GPT recovery surfaces: explicitly non-current")
    print("Protected V9 compatibility entrypoint: preserved as app:app")
    print("Stale v9 branch merge: forbidden")
    print("PR #584 main merge: requires a new explicit OWNER instruction")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
