from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

# V10 reserves these names for the single future platform. They are created only
# by their owning work package; WP1 does not require empty placeholder folders.
RESERVED_V10_ROOTS = {
    "apps",
    "ai",
    "infrastructure",
}

# These names would create a second application/control-plane tree instead of
# extending the approved V10 structure.
FORBIDDEN_COMPETING_ROOTS = {
    "api",
    "backend",
    "bot",
    "execution",
    "frontend",
    "gateway",
    "omni_cio_v10",
    "server",
    "site",
    "telegram_bot",
    "trading",
    "v10",
    "web",
    "website",
}

REQUIRED_V10_AUTHORITY_FILES = {
    "AGENTS.md",
    "knowledge/00_PROJECT_MASTER_CONTEXT.md",
    "knowledge/17_V10_CURRENT_PROGRAM_STATUS.md",
    "docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md",
    "docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md",
    "docs/master-plan/Omni-CIO_V10_Master_Plan_RU.pdf",
    "docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.sha256",
    "docs/architecture/REPOSITORY_STRUCTURE.md",
    "docs/architecture/V10_SYSTEM_ARCHITECTURE.md",
    "docs/architecture/V10_SECURITY_BOUNDARIES.md",
    "docs/architecture/V10_DATA_FLOW.md",
    "docs/architecture/V10_THREAT_MODEL.md",
    "docs/architecture/V10_RECOVERY_CONTRACT.md",
    "docs/architecture/V10_V9_BASELINE_FREEZE.md",
}

PROTECTED_COMPATIBILITY_PATHS = {
    "app.py",
    "app_v371.py",
    "app_v360.py",
    "main.py",
    "render.yaml",
    "omni_cio/real_trading",
    "omni_cio/sandbox",
    "omni_cio/plan_execution",
    "gpt",
}

# The existing domain packages are the V10 deterministic Core. A wholesale
# omni_cio -> omni_cio/core relocation is intentionally not required by WP1.
CRITICAL_CORE_PACKAGES = {
    "candidates",
    "credit",
    "decision",
    "decision_journal",
    "funds",
    "optimizer",
    "plans",
    "policy",
    "research",
    "risk",
    "router",
    "strategy",
    "universe",
    "watchtower",
}

# These future adapters are never allowed to import the low-level Real trading
# package directly. apps/api may eventually call a reviewed plan/execution
# facade, but direct broker-write authority remains isolated.
DIRECT_REAL_IMPORT_FORBIDDEN_ROOTS = (
    Path("apps"),
    Path("ai"),
)
DIRECT_REAL_MODULE_PREFIX = "omni_cio.real_trading"
TRADING_SECRET_MARKER = "TINVEST_TRADING_TOKEN"  # pragma: allowlist secret

# The AI and presentation adapters additionally cannot own the plan-execution
# authority. The API adapter is intentionally excluded because a later approved
# work package may expose a tightly reviewed approval facade through it.
PLAN_EXECUTION_FORBIDDEN_ROOTS = (
    Path("ai"),
    Path("apps/web"),
    Path("apps/telegram"),
)
PLAN_EXECUTION_MODULE_PREFIX = "omni_cio.plan_execution"

REQUIRED_CODEOWNER_PATTERNS = {
    "/apps/",
    "/ai/",
    "/infrastructure/",
    "/omni_cio/",
    "/docs/",
    "/knowledge/",
    "/gpt/",
    "/tests/",
    "/scripts/",
    "/.github/",
}


def _fail(message: str, failures: list[str]) -> None:
    failures.append(message)


def _iter_python_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        path
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts and ".venv" not in path.parts
    )


def _module_imports(source: str, filename: str) -> set[str]:
    tree = ast.parse(source, filename=filename)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


def validate_authority_files(failures: list[str]) -> None:
    for relative in sorted(REQUIRED_V10_AUTHORITY_FILES):
        if not (ROOT / relative).is_file():
            _fail(f"missing V10 authority file: {relative}", failures)

    for relative in sorted(PROTECTED_COMPATIBILITY_PATHS):
        if not (ROOT / relative).exists():
            _fail(f"protected V9 compatibility path is missing: {relative}", failures)


def validate_no_competing_roots(failures: list[str]) -> None:
    for name in sorted(FORBIDDEN_COMPETING_ROOTS):
        path = ROOT / name
        if path.exists():
            _fail(
                "competing top-level application/runtime root is forbidden by V10: "
                f"{name}",
                failures,
            )

    for name in RESERVED_V10_ROOTS:
        path = ROOT / name
        if path.exists() and not path.is_dir():
            _fail(f"reserved V10 root must be a directory when present: {name}", failures)


def validate_single_execution_authority(failures: list[str]) -> None:
    real_dirs = [
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("real_trading")
        if path.is_dir() and ".git" not in path.parts
    ]
    if real_dirs != ["omni_cio/real_trading"]:
        _fail(
            "Real execution authority must exist exactly once at "
            f"omni_cio/real_trading; found: {sorted(real_dirs)}",
            failures,
        )

    plan_dirs = [
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("plan_execution")
        if path.is_dir() and ".git" not in path.parts
    ]
    if plan_dirs != ["omni_cio/plan_execution"]:
        _fail(
            "plan execution authority must exist exactly once at "
            f"omni_cio/plan_execution; found: {sorted(plan_dirs)}",
            failures,
        )


def validate_adapter_authority(failures: list[str]) -> None:
    for relative_root in DIRECT_REAL_IMPORT_FORBIDDEN_ROOTS:
        root = ROOT / relative_root
        for path in _iter_python_files(root):
            relative = path.relative_to(ROOT).as_posix()
            try:
                source = path.read_text(encoding="utf-8")
                imported = _module_imports(source, relative)
            except (OSError, SyntaxError) as exc:
                _fail(f"cannot inspect V10 adapter {relative}: {exc}", failures)
                continue
            if any(
                module == DIRECT_REAL_MODULE_PREFIX
                or module.startswith(f"{DIRECT_REAL_MODULE_PREFIX}.")
                for module in imported
            ):
                _fail(
                    f"V10 adapter imports direct Real authority: {relative}",
                    failures,
                )
            if TRADING_SECRET_MARKER in source:
                _fail(
                    f"V10 adapter references Real trading secret marker: {relative}",
                    failures,
                )

    for relative_root in PLAN_EXECUTION_FORBIDDEN_ROOTS:
        root = ROOT / relative_root
        for path in _iter_python_files(root):
            relative = path.relative_to(ROOT).as_posix()
            try:
                source = path.read_text(encoding="utf-8")
                imported = _module_imports(source, relative)
            except (OSError, SyntaxError) as exc:
                _fail(f"cannot inspect presentation/AI adapter {relative}: {exc}", failures)
                continue
            if any(
                module == PLAN_EXECUTION_MODULE_PREFIX
                or module.startswith(f"{PLAN_EXECUTION_MODULE_PREFIX}.")
                for module in imported
            ):
                _fail(
                    f"presentation/AI adapter imports plan execution authority: {relative}",
                    failures,
                )


def _package_edges(failures: list[str]) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = defaultdict(set)
    for package in sorted(CRITICAL_CORE_PACKAGES):
        package_root = ROOT / "omni_cio" / package
        if not package_root.is_dir():
            _fail(f"critical Core package is missing: omni_cio/{package}", failures)
            continue
        graph.setdefault(package, set())
        for path in _iter_python_files(package_root):
            relative = path.relative_to(ROOT).as_posix()
            try:
                imports = _module_imports(path.read_text(encoding="utf-8"), relative)
            except (OSError, SyntaxError) as exc:
                _fail(f"cannot inspect Core import graph {relative}: {exc}", failures)
                continue
            for module in imports:
                if not module.startswith("omni_cio."):
                    continue
                parts = module.split(".")
                if len(parts) < 2:
                    continue
                target = parts[1]
                if target in CRITICAL_CORE_PACKAGES and target != package:
                    graph[package].add(target)
    return graph


def _find_cycle(graph: dict[str, set[str]]) -> list[str] | None:
    visited: set[str] = set()
    active: list[str] = []
    active_set: set[str] = set()

    def visit(node: str) -> list[str] | None:
        if node in active_set:
            start = active.index(node)
            return [*active[start:], node]
        if node in visited:
            return None
        visited.add(node)
        active.append(node)
        active_set.add(node)
        for target in sorted(graph.get(node, set())):
            cycle = visit(target)
            if cycle:
                return cycle
        active.pop()
        active_set.remove(node)
        return None

    for node in sorted(graph):
        cycle = visit(node)
        if cycle:
            return cycle
    return None


def validate_core_import_graph(failures: list[str]) -> None:
    graph = _package_edges(failures)
    cycle = _find_cycle(graph)
    if cycle:
        _fail(
            "critical V10 Core package cycle detected: " + " -> ".join(cycle),
            failures,
        )


def validate_codeowners(failures: list[str]) -> None:
    path = ROOT / ".github" / "CODEOWNERS"
    if not path.is_file():
        _fail("missing .github/CODEOWNERS", failures)
        return
    patterns = {
        line.split()[0]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#") and line.split()
    }
    missing = sorted(REQUIRED_CODEOWNER_PATTERNS - patterns)
    if missing:
        _fail(
            "CODEOWNERS is missing explicit V10 ownership patterns: "
            + ", ".join(missing),
            failures,
        )


def main() -> int:
    failures: list[str] = []
    validate_authority_files(failures)
    validate_no_competing_roots(failures)
    validate_single_execution_authority(failures)
    validate_adapter_authority(failures)
    validate_core_import_graph(failures)
    validate_codeowners(failures)

    if failures:
        print("V10 repository boundary check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("V10 repository boundary check passed.")
    print("Engineering Control Plane: private GitHub repository")
    print("Deterministic Core root: omni_cio/")
    print("Reserved adapters: apps/api, apps/web, apps/telegram")
    print("Reserved AI root: ai/")
    print("Reserved infrastructure root: infrastructure/")
    print("Direct Real authority: omni_cio/real_trading only")
    print("Protected V9 compatibility layer: present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
