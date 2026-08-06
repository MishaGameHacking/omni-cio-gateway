from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "regression-shield.yml"
LOCK_PATHS = (
    ROOT / "requirements.txt",
    ROOT / "requirements-dev.txt",
)

FULL_SHA = re.compile(r"[0-9a-f]{40}")
SECRET_SCAN_EXCLUDE_PATTERN = (
    r"(^|[\\/])(\.git|\.venv|\.venv-ci|\.mypy_cache|\.ruff_cache|"
    r"__pycache__|requirements(-dev)?\.txt|windows-.*requirements.*\.txt|"
    r"coverage\.xml|pytest-results\.xml)([\\/]|$)"
)
GENERATED_SECRET_SCAN_PATH = re.compile(r"(^|[\\/])\.pytest_cache([\\/]|$)")
EXTERNAL_VENV_ROOT_COMMAND = 'VENV_ROOT="$(cygpath -u "$RUNNER_TEMP")"'
EXTERNAL_VENV_EXPORT_COMMAND = 'echo "VENV_PATH=$VENV_PATH" >> "$GITHUB_ENV"'

REQUIRED_WORKFLOW_COMMANDS = {
    "external Windows CI environment": EXTERNAL_VENV_ROOT_COMMAND,
    "external CI environment export": EXTERNAL_VENV_EXPORT_COMMAND,
    "Windows lock projection": "python scripts/windows_ci_lock.py project",
    "hash-locked install": "--require-hashes -r windows-requirements-dev.txt",
    "lock consistency": "python -m piptools compile",
    "Windows lock verification": "python scripts/windows_ci_lock.py verify",
    "CI policy self-check": "python scripts/check_ci_security_baseline.py",
    "V10 repository boundaries": "python scripts/check_v10_repository_boundaries.py",
    "V10 toolchain baseline": "python scripts/check_v10_toolchain_baseline.py",
    "V10 Regression Shield": "python scripts/check_v10_regression_shield.py",
    "lint": "python -m ruff check .",
    "formatting": "python -m ruff format --check",
    "type checking": "python -m mypy",
    "coverage": "--cov-fail-under=",
    "dependency audit": "python -m pip_audit",
    "SAST": "python -m bandit",
    "secret scan": "python -m detect_secrets",
    "cross-platform secret-scan exclusions": SECRET_SCAN_EXCLUDE_PATTERN,
}

SELF_HOSTED_RUNNER_LABELS = "[self-hosted, Windows, X64, omni-cio-ci]"


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return path.name


def requirement_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if raw_line[:1].isspace():
            if current:
                current.append(stripped)
            continue
        if stripped.startswith(("--", "-r ", "-c ")):
            continue
        if current:
            blocks.append(" ".join(current))
        current = [stripped]

    if current:
        blocks.append(" ".join(current))
    return blocks


def validate_lock_file(path: Path, failures: list[str]) -> None:
    if not path.is_file():
        failures.append(f"missing lock file: {display_path(path)}")
        return

    blocks = requirement_blocks(path.read_text(encoding="utf-8"))
    if not blocks:
        failures.append(f"lock file has no pinned packages: {display_path(path)}")
        return

    for block in blocks:
        requirement = block.split("\\", maxsplit=1)[0].strip()
        if "==" not in requirement:
            failures.append(
                f"unpinned requirement in {display_path(path)}: {requirement}"
            )
        if "--hash=sha256:" not in block:
            failures.append(
                f"requirement without SHA-256 hash in {display_path(path)}: "
                f"{requirement}"
            )


def validate_action_pins(workflow_text: str, failures: list[str]) -> None:
    for line_number, raw_line in enumerate(workflow_text.splitlines(), start=1):
        if "uses:" not in raw_line:
            continue
        value = raw_line.split("uses:", maxsplit=1)[1].split("#", maxsplit=1)[0]
        value = value.strip().strip("\"'")
        if value.startswith("./"):
            continue
        if "@" not in value:
            failures.append(
                f"Action without ref at {WORKFLOW_PATH.name}:{line_number}: {value}"
            )
            continue
        ref = value.rsplit("@", maxsplit=1)[1]
        if not FULL_SHA.fullmatch(ref):
            failures.append(
                f"Action is not pinned to a full commit SHA at "
                f"{WORKFLOW_PATH.name}:{line_number}: {value}"
            )


def validate_workflow(failures: list[str]) -> None:
    if not WORKFLOW_PATH.is_file():
        failures.append("missing .github/workflows/regression-shield.yml")
        return

    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    validate_action_pins(text, failures)
    for label, command in REQUIRED_WORKFLOW_COMMANDS.items():
        if command not in text:
            failures.append(f"Regression Shield is missing {label}: {command}")
    if "continue-on-error: true" in text:
        failures.append("security and quality gates may not use continue-on-error")
    if "contents: read" not in text:
        failures.append("workflow permissions must retain contents: read")
    if "\n  pull_request:" in text:
        failures.append(
            "Regression Shield must remain post-merge only; PR authority belongs to the authoritative gate"
        )
    if SELF_HOSTED_RUNNER_LABELS not in text:
        failures.append(
            "Regression Shield must target the dedicated self-hosted Windows runner"
        )
    if text.count("persist-credentials: false") < 2:
        failures.append("every checkout must disable persisted credentials")
    if "scripts\\bootstrap_windows_ci_python.cmd" not in text:
        failures.append("Regression Shield must bootstrap the verified Python runtime")
    if "python -m venv .venv-ci" in text:
        failures.append(
            "CI virtual environments must be created outside the repository checkout"
        )
    if text.count(EXTERNAL_VENV_ROOT_COMMAND) < 2:
        failures.append(
            "every self-hosted job must create its virtual environment in RUNNER_TEMP"
        )
    if text.count(EXTERNAL_VENV_EXPORT_COMMAND) < 2:
        failures.append(
            "every self-hosted job must export its external virtual environment"
        )
    if text.count('rm -rf "$VENV_PATH"') < 4:
        failures.append(
            "every self-hosted job must reset and clean its external virtual environment"
        )


def validate_render_contract(failures: list[str]) -> None:
    path = ROOT / "render.yaml"
    if not path.is_file():
        failures.append("missing render.yaml")
        return

    text = path.read_text(encoding="utf-8")
    if "pip install --require-hashes -r requirements.txt" not in text:
        failures.append("Render must install the hash-locked runtime dependencies")
    if "uvicorn app:app --host 0.0.0.0 --port $PORT" not in text:
        failures.append("Render must preserve the app:app entrypoint")


def validate_detect_secrets_report(
    report: dict[str, Any],
    failures: list[str],
) -> None:
    results = report.get("results")
    if not isinstance(results, dict):
        failures.append("detect-secrets output does not contain a results object")
        return

    for filename, findings in results.items():
        if GENERATED_SECRET_SCAN_PATH.search(filename):
            continue
        if not isinstance(findings, list):
            failures.append(f"invalid detect-secrets findings for {filename}")
            continue
        for finding in findings:
            if not isinstance(finding, dict):
                failures.append(f"invalid detect-secrets finding for {filename}")
                continue
            line_number = finding.get("line_number", "unknown")
            finding_type = finding.get("type", "unknown")
            failures.append(
                f"potential secret: {filename}:{line_number} ({finding_type})"
            )


def validate_repository_baseline() -> list[str]:
    failures: list[str] = []

    for path in LOCK_PATHS:
        validate_lock_file(path, failures)
    validate_workflow(failures)
    validate_render_contract(failures)

    bootstrap = ROOT / ".github" / "workflows" / "pr03-bootstrap.yml"
    if bootstrap.exists():
        failures.append("temporary PR-03 bootstrap workflow must not be committed")
    return failures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--detect-secrets-report",
        action="store_true",
        help="Validate detect-secrets JSON read from standard input.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.detect_secrets_report:
        try:
            report = json.load(sys.stdin)
        except (json.JSONDecodeError, OSError) as exc:
            print(f"Invalid detect-secrets JSON: {exc}", file=sys.stderr)
            return 1
        failures: list[str] = []
        validate_detect_secrets_report(report, failures)
    else:
        failures = validate_repository_baseline()

    if failures:
        print("CI/security baseline check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    if args.detect_secrets_report:
        print("Secret scan passed: no potential secrets detected.")
    else:
        print("CI/security baseline check passed.")
        print("Dependency locks: pinned and SHA-256 hashed")
        print("Windows projection: exact except allowlisted uvloop exclusion")
        print("CI virtual environments: isolated in RUNNER_TEMP")
        print("GitHub Actions: pinned to full commit SHAs")
        print("Regression Shield: post-merge only on dedicated self-hosted runner")
        print("V10 repository boundary guard: required")
        print("V10 toolchain baseline guard: required")
        print("V10 Regression Shield guard: required")
        print("Render entrypoint: app:app")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
