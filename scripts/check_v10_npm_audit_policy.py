from __future__ import annotations

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
AUDIT_WRAPPER = ROOT / "scripts" / "run_v10_npm_audit.py"
REQUIRED_AUDIT_WORKFLOWS = (
    WORKFLOWS / "v10-pr-fast-checks.yml",
    WORKFLOWS / "v10-wp15-live-web-support-audit.yml",
    WORKFLOWS / "v10-wp16-web-design-system-audit.yml",
    WORKFLOWS / "v10-wp17-application-shell-audit.yml",
    WORKFLOWS / "v10-wp18-portfolio-dashboard-audit.yml",
    WORKFLOWS / "v10-wp19-watchtower-incidents-audit.yml",
    WORKFLOWS / "v10-wp20-research-dossier-audit.yml",
    WORKFLOWS / "v10-wp21-decision-risk-plan-audit.yml",
    WORKFLOWS / "v10-wp22-system-admin-audit.yml",
)
_WRAPPER_TOKEN = "run_v10_npm_audit.py"
_RAW_NPM_AUDIT = re.compile(
    r"(?:npm(?:\.cmd)?|[\"'](?:[^\"'\r\n]*[\\/])?npm(?:\.cmd)?[\"'])\s+audit\b",
    re.IGNORECASE,
)
_WRAPPER_CONTRACT_TOKENS = (
    "client network socket disconnected before secure tls connection was established",
    "security gate remains failed closed",
    "retry is forbidden",
)


def _display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return path.name


def _contains_direct_one_shot_audit(text: str) -> bool:
    return _RAW_NPM_AUDIT.search(text) is not None


def validate_npm_audit_workflow(path: Path, failures: list[str]) -> None:
    if not path.is_file():
        failures.append(f"missing mandatory npm-audit workflow: {_display(path)}")
        return
    text = path.read_text(encoding="utf-8")
    if _WRAPPER_TOKEN not in text:
        failures.append(
            f"{_display(path)} must use the bounded audit wrapper {_WRAPPER_TOKEN}"
        )
    if _contains_direct_one_shot_audit(text):
        failures.append(
            f"{_display(path)} contains a raw one-shot npm audit transport call"
        )
    if "--audit-level high" not in text and "--audit-level=high" not in text:
        failures.append(
            f"{_display(path)} must retain the high-severity audit threshold"
        )


def _validate_audit_wrapper(failures: list[str]) -> None:
    if not AUDIT_WRAPPER.is_file():
        failures.append(
            f"missing mandatory npm audit wrapper: {_display(AUDIT_WRAPPER)}"
        )
        return

    source = AUDIT_WRAPPER.read_text(encoding="utf-8")
    try:
        compile(source, str(AUDIT_WRAPPER), "exec")
    except SyntaxError as exc:
        failures.append(f"npm audit wrapper is not valid Python: {exc}")

    lowered_source = source.lower()
    for token in _WRAPPER_CONTRACT_TOKENS:
        if token not in lowered_source:
            failures.append(
                f"npm audit wrapper is missing fail-closed transport contract: {token}"
            )


def _validate_required_audit_workflows(failures: list[str]) -> None:
    for workflow in REQUIRED_AUDIT_WORKFLOWS:
        validate_npm_audit_workflow(workflow, failures)


def _workflow_paths() -> tuple[Path, ...]:
    if not WORKFLOWS.is_dir():
        return ()
    return tuple(sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml")))


def _validate_no_raw_audit_bypass(failures: list[str]) -> None:
    for workflow in _workflow_paths():
        text = workflow.read_text(encoding="utf-8")
        if _contains_direct_one_shot_audit(text):
            failures.append(
                f"{_display(workflow)} bypasses the bounded npm audit transport policy"
            )


def validate_repository() -> list[str]:
    failures: list[str] = []
    _validate_audit_wrapper(failures)
    _validate_required_audit_workflows(failures)
    _validate_no_raw_audit_bypass(failures)
    return failures


def main() -> int:
    failures = validate_repository()
    if failures:
        print("V10 npm audit transport policy failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("V10 npm audit transport policy passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
