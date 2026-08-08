from __future__ import annotations

import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = (
    ROOT / "docs" / "architecture" / "V10_WP7_BOOTSTRAP_CONTRACT.json"
)
TOOLCHAIN_PATH = ROOT / "docs" / "architecture" / "V10_TOOLCHAIN_BASELINE.json"
BOOTSTRAP_PATH = ROOT / "infrastructure" / "windows" / "bootstrap-v10.ps1"
ROLLBACK_PATH = ROOT / "infrastructure" / "windows" / "rollback_wp7_bootstrap.ps1"


class ContractError(ValueError):
    pass


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot load {path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"{path.relative_to(ROOT)} must contain an object")
    return value


def _mapping(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        raise ContractError(f"{label} must be an object")
    return value


def validate() -> list[str]:
    failures: list[str] = []
    try:
        contract = load_json(CONTRACT_PATH)
        toolchain = load_json(TOOLCHAIN_PATH)
    except ContractError as exc:
        return [str(exc)]

    if contract.get("schema_version") != "1":
        failures.append("WP7 bootstrap contract schema_version must be '1'")

    try:
        bootstrap = _mapping(contract.get("bootstrap"), "bootstrap")
        selected = _mapping(contract.get("toolchain"), "toolchain")
        selected_python = _mapping(selected.get("python"), "toolchain.python")
        selected_node = _mapping(selected.get("node"), "toolchain.node")
        selected_npm = _mapping(selected.get("npm"), "toolchain.npm")
        selected_pg = _mapping(selected.get("postgresql"), "toolchain.postgresql")
        base_backend = _mapping(toolchain.get("backend"), "V10 toolchain backend")
        base_frontend = _mapping(toolchain.get("frontend"), "V10 toolchain frontend")
        base_database = _mapping(toolchain.get("database"), "V10 toolchain database")
    except ContractError as exc:
        return [str(exc)]

    expected_versions = {
        "python": str(base_backend.get("python")),
        "node": str(base_frontend.get("node")),
        "npm": str(base_frontend.get("npm")),
        "postgresql": str(base_database.get("tested_patch")),
    }
    actual_versions = {
        "python": str(selected_python.get("runtime_version")),
        "node": str(selected_node.get("runtime_version")),
        "npm": str(selected_npm.get("runtime_version")),
        "postgresql": str(selected_pg.get("runtime_version")),
    }
    for name, expected in expected_versions.items():
        if actual_versions[name] != expected:
            failures.append(
                f"WP7 {name} target must match V10 toolchain: "
                f"{actual_versions[name]} != {expected}"
            )

    if selected_pg.get("major") != base_database.get("postgresql_major"):
        failures.append("WP7 PostgreSQL major must match V10 toolchain")

    package_expectations = {
        "python": ("Python.Python.3.14", expected_versions["python"]),
        "node": ("OpenJS.NodeJS.LTS", expected_versions["node"]),
        "postgresql": ("PostgreSQL.PostgreSQL.18", "18.4-2"),
    }
    for name, (package_id, package_version) in package_expectations.items():
        spec = _mapping(selected.get(name), f"toolchain.{name}")
        if spec.get("winget_id") != package_id:
            failures.append(f"unexpected WP7 winget package id for {name}")
        if spec.get("winget_version") != package_version:
            failures.append(f"unexpected WP7 pinned winget version for {name}")

    expected_services = [
        ("core-runtime", "OmniCIO.Core", "omni-cio-runtime"),
        ("web-api", "OmniCIO.WebApi", "omni-cio-runtime"),
        ("research-ai", "OmniCIO.ResearchAI", "omni-cio-runtime"),
        ("execution", "OmniCIO.Execution", "omni-cio-execution"),
    ]
    service_definitions = contract.get("service_definitions")
    if not isinstance(service_definitions, list):
        failures.append("WP7 service_definitions must be a list")
    else:
        actual_services: list[tuple[str, str, str, str]] = []
        for index, item in enumerate(service_definitions):
            try:
                spec = _mapping(item, f"service_definitions[{index}]")
            except ContractError as exc:
                failures.append(str(exc))
                continue
            actual_services.append(
                (
                    str(spec.get("id")),
                    str(spec.get("windows_service_name")),
                    str(spec.get("identity_role")),
                    str(spec.get("activation")),
                )
            )
        expected_with_activation = [
            (*item, "FUTURE_WP_ONLY") for item in expected_services
        ]
        if actual_services != expected_with_activation:
            failures.append(
                "WP7 future service definitions do not match reviewed identities"
            )

    if bootstrap.get("default_mode") != "PREVIEW":
        failures.append("WP7 bootstrap must be preview/dry-run by default")
    if bootstrap.get("requires_owner_administrator_for_apply") is not True:
        failures.append("WP7 Apply must require OWNER administrator")
    if bootstrap.get("accepts_secret_values") is not False:
        failures.append("WP7 bootstrap must not accept secret values")
    if bootstrap.get("runner_registration_allowed") is not False:
        failures.append("WP7 bootstrap must not re-register the runner")
    if bootstrap.get("future_application_service_activation_allowed") is not False:
        failures.append("WP7 bootstrap must not activate future application services")

    profile_contract = _mapping(contract.get("profile"), "profile")
    states = profile_contract.get("allowed_prerequisite_states")
    if not isinstance(states, list) or "NOT_MACHINE_VISIBLE" not in states:
        failures.append("WP7 prerequisite states must include NOT_MACHINE_VISIBLE")

    exit_gate = _mapping(contract.get("exit_gate"), "exit_gate")
    if exit_gate.get("prerequisites_machine_visible") is not True:
        failures.append("WP7 Exit Gate must require machine-visible prerequisites")

    try:
        bootstrap_text = BOOTSTRAP_PATH.read_text(encoding="utf-8")
        rollback_text = ROLLBACK_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"cannot load WP7 PowerShell asset: {exc}"]

    param_match = re.search(
        r"param\((.*?)\)\s*\n\s*Set-StrictMode", bootstrap_text, re.S
    )
    if not param_match:
        failures.append("WP7 bootstrap param block not found")
    else:
        param_block = param_match.group(1).lower()
        for forbidden in (
            "token",
            "secret",
            "password",
            "api_key",
            "apikey",
            "authorization",
            "connectionstring",
            "connection_string",
        ):
            if forbidden in param_block:
                failures.append(
                    f"WP7 bootstrap exposes forbidden parameter marker: {forbidden}"
                )

    required_bootstrap_fragments = (
        "[switch]$Apply",
        "[switch]$Verify",
        "[switch]$InstallPrerequisites",
        'if ($Apply -and $Verify)',
        "Test-Administrator",
        "Get-RunnerHealth",
        "Get-LocalRoleState",
        "Test-MachineVisiblePath",
        'return "NOT_MACHINE_VISIBLE"',
        "Install-ExactWingetPackage",
        '"--exact"',
        '"--version"',
        '"--source", "winget"',
        "Ensure-Wp7State",
        "Get-ExistingInstalledPackages",
        "$existingInstalled + $installedThisRun",
        "secondPassChanges",
        "WP7 bootstrap second pass was not idempotent",
        "future_services_inactive",
        "Real secret values used: NO",
    )
    for fragment in required_bootstrap_fragments:
        if fragment not in bootstrap_text:
            failures.append(f"WP7 bootstrap missing required guard: {fragment}")

    forbidden_bootstrap_fragments = (
        "config.cmd remove",
        "config.cmd --url",
        "svc.cmd install",
        "svc.cmd uninstall",
        "TINVEST_TRADING_TOKEN",
        "TINVEST_TOKEN",
        "TELEGRAM_BOT_TOKEN",
        "REAL_TRADING_ENABLED=true",
        "New-Service",
        "sc.exe create",
        "Set-Service -Name OmniCIO",
    )
    for fragment in forbidden_bootstrap_fragments:
        if fragment.lower() in bootstrap_text.lower():
            failures.append(
                f"WP7 bootstrap contains forbidden authority/scope marker: {fragment}"
            )

    if "$secretRoot" not in bootstrap_text:
        failures.append("WP7 bootstrap must explicitly bind the WP8 secret-root boundary")
    secret_mutation_patterns = (
        r"New-Item[^\n]*\$secretRoot",
        r"Set-Content[^\n]*\$secretRoot",
        r"Remove-Item[^\n]*\$secretRoot",
        r"Set-Acl[^\n]*\$secretRoot",
    )
    for pattern in secret_mutation_patterns:
        if re.search(pattern, bootstrap_text, re.I):
            failures.append("WP7 bootstrap must not mutate the WP8 secret root")

    required_rollback_fragments = (
        "Test-OwnedDirectory",
        "safe_to_cleanup",
        "future_services_present",
        "Prerequisites will be uninstalled: NO",
        "WP6 identities/runner/secret boundary will be changed: NO",
    )
    for fragment in required_rollback_fragments:
        if fragment not in rollback_text:
            failures.append(f"WP7 rollback missing required guard: {fragment}")

    for fragment in (
        "C:\\actions-runner\\.credentials",
        "TINVEST_TRADING_TOKEN",
        "Remove-LocalUser",
        "Uninstall-Package",
        "winget uninstall",
    ):
        if fragment.lower() in rollback_text.lower():
            failures.append(
                f"WP7 rollback contains forbidden destructive marker: {fragment}"
            )

    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("V10 WP7 bootstrap contract check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("V10 WP7 bootstrap contract check passed.")
    print("Default mode: PREVIEW")
    print("Apply authority: OWNER administrator only")
    print("Package resolution: exact IDs + pinned versions")
    print("Prerequisite visibility: machine-wide required")
    print("Runner registration: untouched")
    print("Secret-value inputs: forbidden")
    print("Future application services: definitions only / inactive")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
