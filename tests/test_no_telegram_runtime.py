from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

RETIRED_PATHS = (
    "telegram_bot",
    "render.telegram.yaml",
    "tests/test_telegram_companion.py",
    "knowledge/12_TELEGRAM_COMPANION.txt",
    "docs/operations/TELEGRAM_COMPANION_RUNBOOK.md",
)

RETIRED_ENV_VARS = (
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

RETIRED_DEPENDENCIES = (
    "aiogram",
    "pytelegrambotapi",
    "python-telegram-bot",
    "telethon",
)


def _runtime_python_files() -> list[Path]:
    result: list[Path] = []
    for path in ROOT.rglob("*.py"):
        relative = path.relative_to(ROOT)
        if any(
            part in {".git", ".venv", "tests", "scripts", "__pycache__"}
            for part in relative.parts
        ):
            continue
        result.append(path)
    return result


def test_retired_telegram_paths_are_absent() -> None:
    for relative_path in RETIRED_PATHS:
        assert not (ROOT / relative_path).exists(), relative_path


def test_active_configuration_has_no_telegram_secrets_or_dependencies() -> None:
    for relative_path in (
        ".env.example",
        "render.yaml",
        "requirements.txt",
        "requirements-dev.txt",
    ):
        text = (ROOT / relative_path).read_text(encoding="utf-8")
        for variable in RETIRED_ENV_VARS:
            assert variable not in text, (relative_path, variable)

    for relative_path in ("requirements.txt", "requirements-dev.txt"):
        dependencies = (ROOT / relative_path).read_text(encoding="utf-8").lower()
        for dependency in RETIRED_DEPENDENCIES:
            assert dependency not in dependencies, (relative_path, dependency)


def test_gateway_runtime_has_no_telegram_imports() -> None:
    for path in _runtime_python_files():
        relative = path.relative_to(ROOT)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(relative))
        for node in ast.walk(tree):
            modules: tuple[str, ...] = ()
            if isinstance(node, ast.Import):
                modules = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = (node.module,)
            assert not any(
                module == "telegram_bot"
                or module.startswith("telegram_bot.")
                for module in modules
            ), relative


def test_gateway_openapi_has_no_telegram_routes() -> None:
    from fastapi.testclient import TestClient

    import app as gateway_module

    schema = TestClient(gateway_module.app).get("/openapi.json").json()
    assert all(not path.startswith("/telegram") for path in schema["paths"])
