from __future__ import annotations

import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
FAST_WORKFLOW = WORKFLOWS / "v10-pr-fast-checks.yml"
FULL_WORKFLOW = WORKFLOWS / "regression-shield.yml"
TOOLCHAIN_WORKFLOW = WORKFLOWS / "v10-toolchain-compat.yml"
AUTHORITATIVE_WORKFLOW = WORKFLOWS / "self-hosted-windows-smoke.yml"
FRONTEND_FIXTURE = ROOT / "tests" / "toolchain" / "frontend"
FULL_SHA = re.compile(r"[0-9a-f]{40}")
PATH_FILTER = re.compile(r"(?m)^\s+paths(?:-ignore)?:\s*$")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return path.name


def require_tokens(
    text: str,
    tokens: tuple[str, ...],
    label: str,
    failures: list[str],
) -> None:
    for token in tokens:
        if token not in text:
            failures.append(f"{label} is missing required contract: {token}")


def validate_action_pins(path: Path, text: str, failures: list[str]) -> None:
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        if "uses:" not in raw_line:
            continue
        value = raw_line.split("uses:", maxsplit=1)[1].split("#", maxsplit=1)[0]
        value = value.strip().strip("\"'")
        if value.startswith("./"):
            continue
        if "@" not in value:
            failures.append(
                f"{display(path)}:{line_number}: external Action has no ref: {value}"
            )
            continue
        ref = value.rsplit("@", maxsplit=1)[1]
        if not FULL_SHA.fullmatch(ref):
            failures.append(
                f"{display(path)}:{line_number}: external Action is not full-SHA pinned: {value}"
            )


def validate_common_workflow(path: Path, failures: list[str]) -> str:
    if not path.is_file():
        failures.append(f"missing mandatory workflow: {display(path)}")
        return ""
    text = path.read_text(encoding="utf-8")
    validate_action_pins(path, text, failures)
    if "continue-on-error: true" in text:
        failures.append(f"{display(path)} may not soften mandatory jobs")
    if "contents: read" not in text:
        failures.append(f"{display(path)} must retain least-privilege contents: read")
    if "persist-credentials: false" not in text:
        failures.append(f"{display(path)} checkout must not persist credentials")
    return text


def validate_fast_workflow(failures: list[str]) -> None:
    text = validate_common_workflow(FAST_WORKFLOW, failures)
    if not text:
        return
    if "pull_request:" not in text:
        failures.append("Fast PR Checks must run for pull_request events")
    if PATH_FILTER.search(text):
        failures.append("Fast PR Checks may not use path filters")
    if "self-hosted" in text:
        failures.append("Fast PR Checks must not use a self-hosted runner")
    if "secrets." in text or "${{ secrets" in text:
        failures.append("Fast PR Checks must not consume repository/environment secrets")
    require_tokens(
        text,
        (
            "name: V10 Fast PR Checks",
            "runs-on: ubuntu-latest",
            "cancel-in-progress: true",
            "python scripts/check_ci_security_baseline.py",
            "python scripts/check_repository_layout.py",
            "python scripts/check_v10_repository_boundaries.py",
            "python scripts/check_v10_toolchain_baseline.py",
            "python scripts/check_v10_regression_shield.py",
            'cache: "npm"',
            "npm ci --ignore-scripts --no-audit --no-fund",
            "npm run typecheck",
            "npm run lint",
            "npm test",
            "npm run build",
        ),
        "Fast PR Checks",
        failures,
    )


def validate_full_workflow(failures: list[str]) -> None:
    text = validate_common_workflow(FULL_WORKFLOW, failures)
    if not text:
        return
    if PATH_FILTER.search(text):
        failures.append("Regression Shield may not use path filters")
    if "\n  pull_request:" in text:
        failures.append(
            "Regression Shield is post-merge only; PR authority belongs to Lenovo gate"
        )
    require_tokens(
        text,
        (
            "name: Regression Shield",
            "push:",
            "branches:",
            "- main",
            "runs-on: [self-hosted, Windows, X64, omni-cio-ci]",
            "python scripts/check_ci_security_baseline.py",
            "python scripts/check_v10_repository_boundaries.py",
            "python scripts/check_v10_toolchain_baseline.py",
            "python scripts/check_v10_regression_shield.py",
            "python -m ruff check .",
            "python -m ruff format --check",
            "python -m mypy",
            "python -m pytest",
            "--cov-fail-under=",
            "python -m pip_audit",
            "python -m bandit",
            "python -m detect_secrets",
        ),
        "Regression Shield",
        failures,
    )


def validate_toolchain_workflow(failures: list[str]) -> None:
    text = validate_common_workflow(TOOLCHAIN_WORKFLOW, failures)
    if not text:
        return
    if PATH_FILTER.search(text):
        failures.append("V10 Toolchain Compatibility may not use PR path filters")
    if "self-hosted" in text:
        failures.append("V10 Toolchain Compatibility must remain GitHub-hosted")
    require_tokens(
        text,
        (
            "name: V10 Toolchain Compatibility",
            "runs-on: windows-latest",
            'python-version: "3.14.6"',
            'node-version: "24.18.0"',
            "cache: pip",
            'cache: "npm"',
            "python -m ruff check .",
            "python -m ruff format --check",
            "python -m mypy",
            "python -m pytest -q",
            "python -m pip_audit",
            "npm run typecheck",
            "npm run lint",
            "npm test",
            "npm run build",
            "npm audit --audit-level=high",
            "python-sbom.cdx.json",
            "frontend-sbom.cdx.json",
        ),
        "V10 Toolchain Compatibility",
        failures,
    )


def validate_authoritative_workflow(failures: list[str]) -> None:
    text = validate_common_workflow(AUTHORITATIVE_WORKFLOW, failures)
    if not text:
        return
    if "pull_request:" not in text:
        failures.append("Authoritative Merge Gate must run for pull_request events")
    if PATH_FILTER.search(text):
        failures.append("Authoritative Merge Gate may not use PR path filters")
    if "github.event.pull_request.head.repo.full_name == github.repository" not in text:
        failures.append("Authoritative Merge Gate must reject fork PRs")
    if "secrets." in text or "${{ secrets" in text:
        failures.append("Authoritative Merge Gate must not consume repository secrets")
    if "actions/setup-python@" in text or "actions/setup-node@" in text:
        failures.append(
            "Authoritative Lenovo gate must not install toolchains at job runtime; "
            "clean V10 toolchain compatibility belongs to GitHub-hosted runners"
        )
    require_tokens(
        text,
        (
            "name: Self-Hosted Windows CI",
            "name: Windows runner smoke test",
            "name: V10 authoritative merge gate",
            "runs-on: [self-hosted, Windows, X64, omni-cio-ci]",
            "cancel-in-progress: true",
            "scripts\\bootstrap_windows_ci_python.cmd",
            "python scripts/check_ci_security_baseline.py",
            "python scripts/check_repository_layout.py",
            "python scripts/check_v10_repository_boundaries.py",
            "python scripts/check_v10_toolchain_baseline.py",
            "python scripts/check_v10_regression_shield.py",
            "python -m ruff check .",
            "python -m ruff format --check",
            "python -m mypy",
            "python -m pytest",
            "--cov-fail-under=",
            "python -m pip_audit",
            "python -m bandit",
            "python -m detect_secrets",
            "git clean -ffdx",
        ),
        "V10 Authoritative Merge Gate",
        failures,
    )


def validate_frontend_fixture(failures: list[str]) -> None:
    package_path = FRONTEND_FIXTURE / "package.json"
    if not package_path.is_file():
        failures.append("missing frontend toolchain package.json")
        return
    try:
        package = json.loads(package_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        failures.append(f"invalid frontend package.json: {exc}")
        return
    scripts = package.get("scripts")
    if not isinstance(scripts, dict):
        failures.append("frontend package.json has no scripts object")
        return
    for name in ("typecheck", "lint", "test", "build"):
        value = scripts.get(name)
        if not isinstance(value, str) or not value.strip():
            failures.append(f"frontend baseline is missing deterministic `{name}` script")
    for path in (
        FRONTEND_FIXTURE / "scripts" / "lint.mjs",
        FRONTEND_FIXTURE / "tests" / "smoke_contract.test.ts",
        FRONTEND_FIXTURE / "src" / "smoke_contract.ts",
    ):
        if not path.is_file():
            failures.append(f"frontend baseline is missing {display(path)}")


def has_python_contract(directory: Path) -> bool:
    return directory.is_dir() and any(directory.rglob("test_*.py"))


def validate_future_web_contract(failures: list[str]) -> None:
    web = ROOT / "apps" / "web"
    if not web.exists():
        return
    package_path = web / "package.json"
    if not package_path.is_file():
        failures.append("apps/web exists without package.json")
        return
    try:
        package = json.loads(package_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        failures.append(f"invalid apps/web/package.json: {exc}")
        return
    scripts = package.get("scripts")
    if not isinstance(scripts, dict):
        scripts = {}
    for name in ("typecheck", "lint", "test", "build", "e2e"):
        if not isinstance(scripts.get(name), str) or not scripts[name].strip():
            failures.append(f"apps/web requires `{name}` script when Web is introduced")
    if not any(
        (web / name).is_file()
        for name in (
            "playwright.config.ts",
            "playwright.config.js",
            "playwright.config.mjs",
        )
    ):
        failures.append("apps/web requires Playwright configuration when Web is introduced")
    if not list(web.rglob("*.spec.ts")) and not list(web.rglob("*.spec.tsx")):
        failures.append("apps/web requires at least one Playwright *.spec.ts[x] test")


def validate_capability_contracts(failures: list[str]) -> None:
    contracts = ROOT / "tests" / "contracts"
    capabilities = (
        (ROOT / "apps" / "api", contracts / "api", "API schema/contract"),
        (ROOT / "apps" / "telegram", contracts / "telegram", "Telegram signature/freshness"),
        (ROOT / "ai", contracts / "ai", "AI schema/authority"),
        (ROOT / "infrastructure" / "backup", contracts / "backup_restore", "backup/restore"),
    )
    for capability, tests, label in capabilities:
        if capability.exists() and not has_python_contract(tests):
            failures.append(
                f"{display(capability)} exists without mandatory {label} tests in {display(tests)}"
            )

    migration_dirs = [
        path
        for path in ROOT.rglob("migrations")
        if path.is_dir()
        and ".git" not in path.parts
        and "node_modules" not in path.parts
        and ".venv" not in path.parts
    ]
    if migration_dirs and not has_python_contract(contracts / "db_migrations"):
        failures.append(
            "database migrations exist without tests/contracts/db_migrations/test_*.py"
        )

    authority_roots = (ROOT / "apps" / "api", ROOT / "apps" / "telegram", ROOT / "ai")
    if any(path.exists() for path in authority_roots) and not has_python_contract(
        contracts / "authority"
    ):
        failures.append(
            "new transport/AI capability exists without tests/contracts/authority/test_*.py"
        )

    validate_future_web_contract(failures)


def validate_money_path_protection(failures: list[str]) -> None:
    for runtime in (
        ROOT / "omni_cio" / "real_trading",
        ROOT / "omni_cio" / "plan_execution",
        ROOT / "omni_cio" / "sandbox",
    ):
        if not runtime.is_dir():
            failures.append(f"protected money-path package missing: {display(runtime)}")

    test_names = [path.name for path in (ROOT / "tests").glob("test_*.py")]
    for fragment in ("real_trading", "plan_execution", "sandbox"):
        if not any(fragment in name for name in test_names):
            failures.append(
                f"protected money-path test family `{fragment}` is missing from tests/"
            )


def validate_repository() -> list[str]:
    failures: list[str] = []
    validate_fast_workflow(failures)
    validate_full_workflow(failures)
    validate_toolchain_workflow(failures)
    validate_authoritative_workflow(failures)
    validate_frontend_fixture(failures)
    validate_capability_contracts(failures)
    validate_money_path_protection(failures)
    return failures


def main() -> int:
    failures = validate_repository()
    if failures:
        print("V10 Regression Shield contract failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("V10 Regression Shield contract passed.")
    print("Fast PR lane: GitHub-hosted Linux acceleration, cached, no secrets")
    print("Hosted toolchain lane: clean GitHub-hosted Windows Python/Node compatibility")
    print("Authoritative PR lane: self-hosted Windows full protected-runtime regression/security")
    print("Post-merge lane: self-hosted Regression Shield sentinel on main")
    print("Toolchain installation is intentionally excluded from the Lenovo merge gate")
    print("Frontend baseline: typecheck + lint + unit + build")
    print("Future capability test contracts: fail-closed when roots appear")
    print("Money-path test families: protected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
