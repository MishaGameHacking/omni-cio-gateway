from __future__ import annotations

import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = (
    ROOT / "docs" / "architecture" / "V10_WP6_IDENTITY_PRIVILEGE_CONTRACT.json"
)
WORKFLOW_ROOT = ROOT / ".github" / "workflows"
SELF_HOSTED_WORKFLOW = WORKFLOW_ROOT / "self-hosted-windows-smoke.yml"
RELEASE_MANIFEST_SCHEMA = (
    ROOT / "docs" / "architecture" / "V10_RELEASE_MANIFEST.schema.json"
)
RELEASE_WORKFLOW = WORKFLOW_ROOT / "v10-release-provenance.yml"

SECRET_REFERENCE = re.compile(r"\$\{\{\s*secrets\.([A-Za-z0-9_]+)\s*\}\}")
RAW_IDENTITY_COMMAND = re.compile(r"(?im)^\s*(?:whoami|whoami\.exe)(?:\s+.*)?$")
RUNNER_CONFIG_TEXT = (
    "c:\\actions-runner",
    "c:/actions-runner",
    "c:\\actions-runner\\.runner",
    "c:/actions-runner/.runner",
    "c:\\actions-runner\\.service",
    "c:/actions-runner/.service",
    "actions.runner.",
)
BROKER_WRITE_TEXT = (
    "TINVEST_TRADING_TOKEN",
    "TINVEST_TRANSFER_TOKEN",
    "post_order",
    "replace_order",
    "cancel_order",
    "post_stop_order",
    "withdraw",
    "executeRealTrade",
)
GENERAL_RUNTIME_ROOTS = (
    ROOT / "omni_cio" / "ai",
    ROOT / "omni_cio" / "web",
    ROOT / "omni_cio" / "telegram",
    ROOT / "omni_cio" / "research",
)


class ContractError(ValueError):
    pass


def _expect_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError(f"{label} must be an object")
    return value


def _safe_path_label(path: Path) -> str:
    """Return a repository-relative diagnostic path without leaking host paths.

    Negative tests deliberately substitute roots outside the repository. Those
    paths must still produce a deterministic boundary failure instead of raising
    from ``Path.relative_to``. For out-of-repository paths only the file name is
    retained, which also avoids exposing runner/user/temp-directory identities.
    """

    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.name


def load_contract() -> dict[str, Any]:
    try:
        raw = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot load WP6 contract: {exc}") from exc
    contract = _expect_mapping(raw, "contract")
    if contract.get("schema_version") != "1":
        raise ContractError("schema_version must be '1'")
    if contract.get("contract") != "V10_WP6_IDENTITY_PRIVILEGE_CONTRACT":
        raise ContractError("unexpected contract identity")
    return contract


def validate_contract_shape(contract: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    roles = _expect_mapping(contract.get("roles"), "roles")
    for required in ("owner_admin", "ci_runner", "runtime", "execution"):
        if required not in roles:
            failures.append(f"missing role: {required}")

    runner = _expect_mapping(roles.get("ci_runner", {}), "roles.ci_runner")
    if runner.get("administrator") is not False:
        failures.append("CI runner must be non-admin")
    if runner.get("execution_secret_access") != "DENY":
        failures.append("CI runner must be denied execution-secret access")
    if not runner.get("allowed_service_account_classes"):
        failures.append("CI runner allowed account classes must be explicit")

    runtime = _expect_mapping(roles.get("runtime", {}), "roles.runtime")
    if runtime.get("administrator") is not False:
        failures.append("ordinary runtime must be non-admin")
    if runtime.get("execution_secret_access") != "DENY":
        failures.append("ordinary runtime must not read execution secret")
    if runtime.get("runner_configuration_write_access") != "DENY":
        failures.append("ordinary runtime must not modify runner configuration")
    if runtime.get("runner_root_access") != "DENY":
        failures.append("ordinary runtime must be denied runner-root access")
    if runtime.get("broker_write_authority") != "DENY":
        failures.append("ordinary runtime must not receive broker-write authority")

    execution = _expect_mapping(roles.get("execution", {}), "roles.execution")
    if execution.get("administrator") is not False:
        failures.append("execution identity must be non-admin")
    if execution.get("runner_root_access") != "DENY":
        failures.append("execution identity must be denied runner-root access")
    if execution.get("transfer_withdraw_margin_short_authority") != "DENY":
        failures.append("execution identity must retain forbidden money authorities")

    deployment = _expect_mapping(contract.get("deployment"), "deployment")
    if deployment.get("authority") != "REVIEWED_RELEASE_IDENTITY":
        failures.append("deployment authority must be reviewed release identity")
    if deployment.get("required_identity_source") != "V10_RELEASE_MANIFEST":
        failures.append("deployment must bind to the V10 release manifest")
    if deployment.get("arbitrary_pr_worktree_in_secret_context") is not False:
        failures.append("arbitrary PR worktrees must be forbidden in secret context")

    privacy = _expect_mapping(contract.get("privacy"), "privacy")
    for key, value in privacy.items():
        if value is not False:
            failures.append(f"privacy flag must remain false: {key}")
    return failures


def workflow_files() -> list[Path]:
    return sorted(
        path
        for pattern in ("*.yml", "*.yaml")
        for path in WORKFLOW_ROOT.glob(pattern)
        if path.is_file()
    )


def validate_workflow_secret_boundary(
    contract: dict[str, Any], failures: list[str]
) -> None:
    forbidden = contract.get("forbidden_ci_secret_names")
    if not isinstance(forbidden, list) or not all(
        isinstance(item, str) and item for item in forbidden
    ):
        failures.append("forbidden_ci_secret_names must be a non-empty string list")
        return
    forbidden_set = set(forbidden)
    for path in workflow_files():
        text = path.read_text(encoding="utf-8")
        for secret_name in SECRET_REFERENCE.findall(text):
            if secret_name in forbidden_set:
                failures.append(
                    f"workflow references forbidden production secret: {path.name}:{secret_name}"
                )
        for secret_name in forbidden_set:
            if secret_name in text:
                failures.append(
                    f"workflow contains forbidden secret identifier: {path.name}:{secret_name}"
                )


def validate_self_hosted_workflow(failures: list[str]) -> None:
    if not SELF_HOSTED_WORKFLOW.is_file():
        failures.append("missing self-hosted Windows workflow")
        return
    text = SELF_HOSTED_WORKFLOW.read_text(encoding="utf-8")
    required_markers = {
        "contents: read": "self-hosted workflow must retain contents: read",
        "[self-hosted, Windows, X64, omni-cio-ci]": (
            "self-hosted workflow must target omni-cio-ci"
        ),
        "GITHUB_TOKEN: ${{ github.token }}": (
            "self-hosted bootstrap must use only the job-scoped GitHub token"
        ),
        'GIT_TERMINAL_PROMPT: "0"': (
            "self-hosted bootstrap must disable interactive Git prompts"
        ),
        'GCM_INTERACTIVE: "0"': (
            "self-hosted bootstrap must disable interactive Git Credential Manager"
        ),
        'git config --local credential.helper ""': (
            "self-hosted bootstrap must reset inherited credential helpers"
        ),
        "git config --local --add credential.helper": (
            "self-hosted bootstrap must install a temporary job-token helper"
        ),
        "git config --local --unset-all credential.helper": (
            "self-hosted bootstrap must remove temporary credentials after fetch"
        ),
        'git checkout --detach "$EXPECTED_HEAD"': (
            "self-hosted bootstrap must detach at the reviewed exact head"
        ),
        'test "$(git rev-parse HEAD)" = "$EXPECTED_HEAD"': (
            "self-hosted bootstrap must verify the reviewed exact head"
        ),
        'test -z "$(git config --local --get-all credential.helper || true)"': (
            "self-hosted bootstrap must verify no local credential helper remains"
        ),
    }
    for marker, message in required_markers.items():
        if marker not in text:
            failures.append(message)
    if "uses: actions/checkout@" in text:
        failures.append(
            "self-hosted authority workflow must not depend on actions/checkout"
        )
    if RAW_IDENTITY_COMMAND.search(text):
        failures.append("self-hosted workflow must not print raw Windows identity")


def validate_release_identity_boundary(failures: list[str]) -> None:
    if not RELEASE_MANIFEST_SCHEMA.is_file():
        failures.append("missing V10 release manifest schema")
    if not RELEASE_WORKFLOW.is_file():
        failures.append("missing V10 release provenance workflow")


def _python_sources(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(path for path in root.rglob("*.py") if path.is_file())


def validate_general_runtime_broker_boundary(failures: list[str]) -> None:
    for root in GENERAL_RUNTIME_ROOTS:
        for path in _python_sources(root):
            text = path.read_text(encoding="utf-8")
            for forbidden in BROKER_WRITE_TEXT:
                if forbidden in text:
                    failures.append(
                        "general runtime/AI crosses broker-write boundary: "
                        f"{_safe_path_label(path)} ({forbidden})"
                    )


def validate_runtime_runner_config_boundary(failures: list[str]) -> None:
    candidates = [ROOT / "app.py"]
    candidates.extend(
        path for path in (ROOT / "omni_cio").rglob("*.py") if path.is_file()
    )
    for path in candidates:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8").lower()
        for forbidden in RUNNER_CONFIG_TEXT:
            if forbidden in text:
                failures.append(
                    "application runtime references runner configuration surface: "
                    f"{_safe_path_label(path)} ({forbidden})"
                )


def validate_repository() -> list[str]:
    try:
        contract = load_contract()
    except ContractError as exc:
        return [str(exc)]

    failures = validate_contract_shape(contract)
    validate_workflow_secret_boundary(contract, failures)
    validate_self_hosted_workflow(failures)
    validate_release_identity_boundary(failures)
    validate_general_runtime_broker_boundary(failures)
    validate_runtime_runner_config_boundary(failures)
    return failures


def main() -> int:
    failures = validate_repository()
    if failures:
        print("WP6 privilege boundary check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("WP6 privilege boundary check passed.")
    print("CI production-secret references: absent")
    print("Self-hosted raw identity logging: absent")
    print("General runtime broker-write boundary: preserved")
    print("Deployment identity: V10 release manifest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
