from __future__ import annotations

import ast
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PATHS = (
    "README.md",
    "AGENTS.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "app.py",
    "render.yaml",
    "requirements.in",
    "requirements.txt",
    "requirements-dev.in",
    "requirements-dev.txt",
    "pyproject.toml",
    ".env.example",
    "scripts/check_ci_security_baseline.py",
    "tests/test_ci_security_baseline.py",
    "tests/test_no_telegram_runtime.py",
    "knowledge/00_PROJECT_MASTER_CONTEXT.md",
    "knowledge/09_MARKET_DATA_AND_BUYING_POWER.txt",
    "knowledge/10_OPERATIONS_ANALYTICS_AND_RECONCILIATION.txt",
    "knowledge/11_BROKER_REPORT_ASYNC_INTEGRITY.txt",
    "knowledge/12_TELEGRAM_RETIREMENT.txt",
    "knowledge/14_CI_SECURITY_BASELINE.txt",
    "docs/README.md",
    "docs/architecture/SYSTEM_OVERVIEW.md",
    "docs/architecture/REPOSITORY_STRUCTURE.md",
    "docs/architecture/DECISIONS.md",
    "docs/inventory/PROJECT_ASSETS.md",
    "docs/inventory/FILE_INDEX.md",
    "docs/operations/DEPLOYMENT_RUNBOOK.md",
    "docs/operations/TELEGRAM_REMOVAL_RUNBOOK.md",
    "docs/operations/RELEASE_CHECKLIST.md",
    "gpt/README.md",
    "gpt/CONFIGURATION.md",
    "gpt/INSTRUCTIONS.md",
    "gpt/ACTIONS_CATALOG.md",
    "gpt/NEW_CHAT_PROMPT.md",
    ".github/CODEOWNERS",
    ".github/dependabot.yml",
    ".github/copilot-instructions.md",
    ".github/pull_request_template.md",
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/workflows/regression-shield.yml",
)

FORBIDDEN_TRACKED_NAMES = {
    ".env",
    "pytest-results.xml",
}

FORBIDDEN_WORKFLOWS = {
    "apply-v390.yml",
    "pr03-bootstrap.yml",
    "upgrade-v390.yml",
}

RETIRED_TELEGRAM_PATHS = (
    "telegram_bot",
    "render.telegram.yaml",
    "tests/test_telegram_companion.py",
    "knowledge/12_TELEGRAM_COMPANION.txt",
    "docs/operations/TELEGRAM_COMPANION_RUNBOOK.md",
)

RETIRED_TELEGRAM_ENV_VARS = (
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_WEBHOOK_SECRET",
    "TELEGRAM_ALLOWED_USER_IDS",
    "OMNI_GATEWAY_URL",
    "OMNI_GATEWAY_API_KEY",
    "TELEGRAM_AUTO_CONFIGURE",
    "TELEGRAM_PUBLIC_BASE_URL",
    "TELEGRAM_REQUEST_TIMEOUT_SECONDS",
    "TELEGRAM_GATEWAY_RETRY_ATTEMPTS",
    "TELEGRAM_GATEWAY_RETRY_DELAY_SECONDS",
    "TELEGRAM_MAX_RESPONSE_CHARS",
    "TELEGRAM_MIN_REQUEST_INTERVAL_SECONDS",
)

RETIRED_TELEGRAM_DEPENDENCIES = (
    "aiogram",
    "pytelegrambotapi",
    "python-telegram-bot",
    "telethon",
)

FORBIDDEN_BROKER_METHOD_PREFIXES = (
    "post_order",
    "replace_order",
    "cancel_order",
    "create_order",
    "execute_order",
    "post_stop_order",
    "cancel_stop_order",
    "withdraw",
    "transfer",
)

FORBIDDEN_BROKER_METHODS = {
    "pay_in",
    "sandbox_pay_in",
    "open_sandbox_account",
    "close_sandbox_account",
}

FORBIDDEN_BROKER_SERVICES = {
    "stop_orders",
    "sandbox",
}


def fail(message: str, failures: list[str]) -> None:
    failures.append(message)


def is_forbidden_broker_attribute(name: str) -> bool:
    return (
        name in FORBIDDEN_BROKER_METHODS
        or name in FORBIDDEN_BROKER_SERVICES
        or any(name.startswith(prefix) for prefix in FORBIDDEN_BROKER_METHOD_PREFIXES)
    )


def scan_runtime_broker_egress(failures: list[str]) -> None:
    for path in ROOT.rglob("*.py"):
        relative = path.relative_to(ROOT)
        if any(
            part in {".git", ".venv", "tests", "scripts", "__pycache__"}
            for part in relative.parts
        ):
            continue

        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(relative))
        except (OSError, SyntaxError) as exc:
            fail(f"cannot inspect runtime Python source {relative}: {exc}", failures)
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and is_forbidden_broker_attribute(
                node.attr
            ):
                fail(
                    (
                        "forbidden broker write surface referenced: "
                        f"{relative}:{node.lineno} ({node.attr})"
                    ),
                    failures,
                )
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "getattr"
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and isinstance(node.args[1].value, str)
                and is_forbidden_broker_attribute(node.args[1].value)
            ):
                fail(
                    (
                        "dynamic forbidden broker write surface referenced: "
                        f"{relative}:{node.lineno} ({node.args[1].value})"
                    ),
                    failures,
                )


def scan_retired_telegram_surface(failures: list[str]) -> None:
    for relative_path in RETIRED_TELEGRAM_PATHS:
        if (ROOT / relative_path).exists():
            fail(f"retired Telegram path is still present: {relative_path}", failures)

    for relative_path in (
        ".env.example",
        "render.yaml",
        "requirements.in",
        "requirements.txt",
        "requirements-dev.in",
        "requirements-dev.txt",
    ):
        path = ROOT / relative_path
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for variable in RETIRED_TELEGRAM_ENV_VARS:
            if variable in text:
                fail(
                    f"retired Telegram configuration remains in {relative_path}: "
                    f"{variable}",
                    failures,
                )

    for relative_path in (
        "requirements.in",
        "requirements.txt",
        "requirements-dev.in",
        "requirements-dev.txt",
    ):
        path = ROOT / relative_path
        if not path.is_file():
            continue
        dependencies = path.read_text(encoding="utf-8").lower()
        for dependency in RETIRED_TELEGRAM_DEPENDENCIES:
            if dependency in dependencies:
                fail(
                    f"retired Telegram dependency remains in {relative_path}: "
                    f"{dependency}",
                    failures,
                )

    for path in ROOT.rglob("*.py"):
        relative = path.relative_to(ROOT)
        if any(
            part in {".git", ".venv", "tests", "scripts", "__pycache__"}
            for part in relative.parts
        ):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(relative))
        except (OSError, SyntaxError) as exc:
            fail(f"cannot inspect runtime Python source {relative}: {exc}", failures)
            continue
        for node in ast.walk(tree):
            modules: tuple[str, ...] = ()
            if isinstance(node, ast.Import):
                modules = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = (node.module,)
            if any(
                module == "telegram_bot" or module.startswith("telegram_bot.")
                for module in modules
            ):
                fail(
                    f"retired Telegram runtime import remains: {relative}",
                    failures,
                )


def main() -> int:
    failures: list[str] = []

    for relative_path in REQUIRED_PATHS:
        if not (ROOT / relative_path).is_file():
            fail(f"missing required file: {relative_path}", failures)

    render_path = ROOT / "render.yaml"
    if render_path.is_file():
        render_text = render_path.read_text(encoding="utf-8")
        expected = "uvicorn app:app --host 0.0.0.0 --port $PORT"
        if expected not in render_text:
            fail("render.yaml does not preserve the app:app entrypoint", failures)

    app_path = ROOT / "app.py"
    if app_path.is_file():
        app_text = app_path.read_text(encoding="utf-8")
        if 'ENTRYPOINT = "app:app"' not in app_text:
            fail("app.py does not declare ENTRYPOINT = app:app", failures)
        if "trading_methods" not in app_text:
            fail("app.py does not expose the read-only contract marker", failures)

    for path in ROOT.rglob("*"):
        if ".git" in path.parts or not path.is_file():
            continue
        if path.name in FORBIDDEN_TRACKED_NAMES:
            fail(
                f"forbidden generated or secret file present: {path.relative_to(ROOT)}",
                failures,
            )
        if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
            fail(
                f"generated Python artifact present: {path.relative_to(ROOT)}", failures
            )

    workflow_dir = ROOT / ".github" / "workflows"
    for name in FORBIDDEN_WORKFLOWS:
        if (workflow_dir / name).exists():
            fail(f"obsolete one-time workflow still present: {name}", failures)

    scan_runtime_broker_egress(failures)
    scan_retired_telegram_surface(failures)

    if failures:
        print("Repository layout check failed:", file=sys.stderr)
        for item in failures:
            print(f"- {item}", file=sys.stderr)
        return 1

    print("Repository layout check passed.")
    print(f"Required files checked: {len(REQUIRED_PATHS)}")
    print("Gateway entrypoint: app:app")
    print("Telegram runtime: retired")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
