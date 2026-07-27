from __future__ import annotations

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
    "requirements.txt",
    "requirements-dev.txt",
    "knowledge/00_PROJECT_MASTER_CONTEXT.md",
    "docs/README.md",
    "docs/architecture/SYSTEM_OVERVIEW.md",
    "docs/architecture/REPOSITORY_STRUCTURE.md",
    "docs/inventory/PROJECT_ASSETS.md",
    "docs/operations/DEPLOYMENT_RUNBOOK.md",
    "docs/operations/RELEASE_CHECKLIST.md",
    "gpt/README.md",
    "gpt/INSTRUCTIONS.md",
    "gpt/ACTIONS_CATALOG.md",
    "gpt/NEW_CHAT_PROMPT.md",
    ".github/CODEOWNERS",
    ".github/pull_request_template.md",
    ".github/workflows/regression-shield.yml",
)

FORBIDDEN_TRACKED_NAMES = {
    ".env",
    "pytest-results.xml",
}

FORBIDDEN_WORKFLOWS = {
    "apply-v390.yml",
    "upgrade-v390.yml",
}


def fail(message: str, failures: list[str]) -> None:
    failures.append(message)


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
            fail(f"forbidden generated or secret file present: {path.relative_to(ROOT)}", failures)
        if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
            fail(f"generated Python artifact present: {path.relative_to(ROOT)}", failures)

    workflow_dir = ROOT / ".github" / "workflows"
    for name in FORBIDDEN_WORKFLOWS:
        if (workflow_dir / name).exists():
            fail(f"obsolete one-time workflow still present: {name}", failures)

    if failures:
        print("Repository layout check failed:", file=sys.stderr)
        for item in failures:
            print(f"- {item}", file=sys.stderr)
        return 1

    print("Repository layout check passed.")
    print(f"Required files checked: {len(REQUIRED_PATHS)}")
    print("Stable entrypoint: app:app")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
