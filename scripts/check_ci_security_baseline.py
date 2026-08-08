from __future__ import annotations

import argparse
import hashlib
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
APPROVED_KEYWORD_LINE_SHA256 = {
    "docs/architecture/V10_WP6_IDENTITY_PRIVILEGE_CONTRACT.json": frozenset(
        {
            "3ba3737580cee6fdb914ed343b7718f65c523a275fece9c6a286615bddc78f00",
            "5738a62997f73e408c2f614f015e6ade6bda39e79f6518d4966cb1126d3204e6",
            "ea759685dd2df4b2b3a43399b84bdc2981939e48f719cd32410838b0564e6810",
            "3602f714fb7ecf0fd9806db764b2da5d61f3184ee6e0805646656bf65e5b430c",
        }
    ),
    "infrastructure/windows/collect_wp6_identity_profile.ps1": frozenset(
        {"e29d48683d83857e73b19ac28fa8e401cebb11c9186b1c7c55b480ac85abcf1f"}
    ),
    "scripts/assess_v10_wp6_identity_profile.py": frozenset(
        {"2999954df8614b4d412ee5e3ef1bb897cec3949aff2dfe1f30a904cb58e5c8e5"}
    ),
    "tests/test_v10_wp6_identity_profile.py": frozenset(
        {
            "672fcad70bffec336a621c37769bc44c1c151c3ed5fc55fb045af17cd879167e",
            "755a553020e112fe20a6133af7d094ae4ef65632f4552aad72d9c3f26ffe88c9",
        }
    ),
}
EXTERNAL_VENV_ROOT_COMMAND = 'VENV_ROOT="$(cygpath -u "$RUNNER_TEMP")"'
EXTERNAL_VENV_EXPORT_COMMAND = 'echo "VENV_PATH=$VENV_PATH" >> "$GITHUB_ENV"'
DIAGNOSTICS_SOFT_FAIL = re.compile(
    r"(?ms)^\s*- name: Upload test diagnostics\s*$"
    r".*?^\s+id: diagnostics_upload\s*$"
    r".*?^\s+continue-on-error: true\s*$"
    r".*?^\s+uses: actions/upload-artifact@[0-9a-f]{40}.*?$"
)

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


def validate_soft_fail_policy(workflow_text: str, failures: list[str]) -> None:
    count = workflow_text.count("continue-on-error: true")
    if count == 0:
        return
    if count != 1 or DIAGNOSTICS_SOFT_FAIL.search(workflow_text) is None:
        failures.append(
            "security and quality gates may not use continue-on-error; only the "
            "post-merge diagnostics artifact transport may be best-effort"
        )


def validate_workflow(failures: list[str]) -> None:
    if not WORKFLOW_PATH.is_file():
        failures.append("missing .github/workflows/regression-shield.yml")
        return

    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    validate_action_pins(text, failures)
    validate_soft_fail_policy(text, failures)
    for label, command in REQUIRED_WORKFLOW_COMMANDS.items():
        if command not in text:
            failures.append(f"Regression Shield is missing {label}: {command}")
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


def _normalize_repo_filename(filename: str) -> str:
    normalized = filename.replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _approved_keyword_metadata_finding(filename: str, finding: dict[str, Any]) -> bool:
    if finding.get("type") != "Secret Keyword":
        return False
    line_number = finding.get("line_number")
    if isinstance(line_number, bool) or not isinstance(line_number, int):
        return False

    normalized = _normalize_repo_filename(filename)
    approved_hashes = APPROVED_KEYWORD_LINE_SHA256.get(normalized)
    if not approved_hashes:
        return False

    root = ROOT.resolve()
    candidate = (ROOT / Path(normalized)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return False

    try:
        lines = candidate.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return False
    if line_number < 1 or line_number > len(lines):
        return False

    digest = hashlib.sha256(lines[line_number - 1].strip().encode("utf-8")).hexdigest()
    return digest in approved_hashes


def validate_detect_secrets_report(
    report: dict[str, Any],
    failures: list[str],
) -> None:
    results = report.get("results")
    if not isinstance(results, dict):
        failures.append("detect-secrets output does not contain a results object")
        return

    for filename, findings in results.items():
        if not isinstance(filename, str):
            failures.append("invalid detect-secrets filename")
            continue
        if GENERATED_SECRET_SCAN_PATH.search(filename):
            continue
        if not isinstance(findings, list):
            failures.append(f"invalid detect-secrets findings for {filename}")
            continue
        for finding in findings:
            if not isinstance(finding, dict):
                failures.append(f"invalid detect-secrets finding for {filename}")
                continue
            if _approved_keyword_metadata_finding(filename, finding):
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
        print("Regression Shield: post-merge only on dedicated self-hosted Windows runner")
        print("V10 repository boundary guard: required")
        print("V10 toolchain baseline guard: required")
        print("V10 Regression Shield guard: required")
        print("Diagnostics artifact transport: best-effort and non-authoritative")
        print("Render entrypoint: app:app")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
