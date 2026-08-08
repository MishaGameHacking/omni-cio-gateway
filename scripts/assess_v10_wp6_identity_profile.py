from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = (
    ROOT / "docs" / "architecture" / "V10_WP6_IDENTITY_PRIVILEGE_CONTRACT.json"
)


class ProfileError(ValueError):
    pass


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProfileError(f"{label} must be an object")
    return value


def _bool_or_none(value: Any, label: str) -> bool | None:
    if value is None or isinstance(value, bool):
        return value
    raise ProfileError(f"{label} must be boolean or null")


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProfileError(f"cannot load {label}: {exc}") from exc
    return _mapping(data, label)


def validate_shape(profile: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if profile.get("schema_version") != "1":
        failures.append("schema_version must be '1'")
    if profile.get("capture_mode") != "PASSIVE":
        failures.append("capture_mode must be PASSIVE")

    required_sections = ("runner", "runtime", "execution", "boundaries", "privacy")
    for section in required_sections:
        if not isinstance(profile.get(section), dict):
            failures.append(f"missing/invalid section: {section}")
    if failures:
        return failures

    runner = _mapping(profile["runner"], "runner")
    runtime = _mapping(profile["runtime"], "runtime")
    execution = _mapping(profile["execution"], "execution")
    boundaries = _mapping(profile["boundaries"], "boundaries")
    privacy = _mapping(profile["privacy"], "privacy")

    runner_keys = {
        "service_running",
        "service_start_mode",
        "account_class",
        "administrator",
        "service_identity_matches_current_process",
        "current_process_administrator",
        "distinct_from_interactive_owner",
    }
    runtime_keys = {
        "identity_present",
        "identity_enabled",
        "administrator",
        "execution_secret_direct_read_grant",
        "runner_config_direct_write_grant",
        "runner_root_deny_present",
    }
    execution_keys = {
        "identity_present",
        "identity_enabled",
        "administrator",
        "execution_secret_direct_read_grant",
        "runner_root_deny_present",
    }
    boundary_keys = {
        "execution_secret_sentinel_present",
        "runner_execution_secret_read",
        "execution_secret_broad_read_exposure",
        "runner_config_present",
        "runner_config_broad_write_exposure",
    }
    privacy_keys = {
        "raw_usernames_collected",
        "sids_emitted",
        "hostnames_collected",
        "addresses_collected",
        "secret_values_collected",
        "process_lists_collected",
    }

    for section_name, section_value, keys in (
        ("runner", runner, runner_keys),
        ("runtime", runtime, runtime_keys),
        ("execution", execution, execution_keys),
        ("boundaries", boundaries, boundary_keys),
        ("privacy", privacy, privacy_keys),
    ):
        extra = sorted(set(section_value) - keys)
        missing = sorted(keys - set(section_value))
        if extra:
            failures.append(f"unexpected {section_name} fields: {', '.join(extra)}")
        if missing:
            failures.append(f"missing {section_name} fields: {', '.join(missing)}")

    if failures:
        return failures

    for label, value in (
        ("runner.service_running", runner["service_running"]),
        ("runner.administrator", runner["administrator"]),
        (
            "runner.service_identity_matches_current_process",
            runner["service_identity_matches_current_process"],
        ),
        (
            "runner.current_process_administrator",
            runner["current_process_administrator"],
        ),
        (
            "runner.distinct_from_interactive_owner",
            runner["distinct_from_interactive_owner"],
        ),
        ("runtime.identity_present", runtime["identity_present"]),
        ("runtime.identity_enabled", runtime["identity_enabled"]),
        ("runtime.administrator", runtime["administrator"]),
        (
            "runtime.execution_secret_direct_read_grant",
            runtime["execution_secret_direct_read_grant"],
        ),
        (
            "runtime.runner_config_direct_write_grant",
            runtime["runner_config_direct_write_grant"],
        ),
        ("runtime.runner_root_deny_present", runtime["runner_root_deny_present"]),
        ("execution.identity_present", execution["identity_present"]),
        ("execution.identity_enabled", execution["identity_enabled"]),
        ("execution.administrator", execution["administrator"]),
        (
            "execution.execution_secret_direct_read_grant",
            execution["execution_secret_direct_read_grant"],
        ),
        (
            "execution.runner_root_deny_present",
            execution["runner_root_deny_present"],
        ),
        (
            "boundaries.execution_secret_sentinel_present",
            boundaries["execution_secret_sentinel_present"],
        ),
        (
            "boundaries.execution_secret_broad_read_exposure",
            boundaries["execution_secret_broad_read_exposure"],
        ),
        ("boundaries.runner_config_present", boundaries["runner_config_present"]),
        (
            "boundaries.runner_config_broad_write_exposure",
            boundaries["runner_config_broad_write_exposure"],
        ),
    ):
        try:
            _bool_or_none(value, label)
        except ProfileError as exc:
            failures.append(str(exc))

    if not isinstance(runner["service_start_mode"], str):
        failures.append("runner.service_start_mode must be a string")
    if not isinstance(runner["account_class"], str):
        failures.append("runner.account_class must be a string")
    if boundaries["runner_execution_secret_read"] not in {
        "ACCESS_GRANTED",
        "ACCESS_DENIED",
        "NOT_CONFIGURED",
        "ERROR",
    }:
        failures.append("invalid boundaries.runner_execution_secret_read")
    for key, value in privacy.items():
        if not isinstance(value, bool):
            failures.append(f"privacy.{key} must be boolean")
    return failures


def assess(profile: dict[str, Any], contract: dict[str, Any]) -> tuple[str, list[str]]:
    blockers = validate_shape(profile)
    if blockers:
        return "FAIL", blockers

    runner = _mapping(profile["runner"], "runner")
    runtime = _mapping(profile["runtime"], "runtime")
    execution = _mapping(profile["execution"], "execution")
    boundaries = _mapping(profile["boundaries"], "boundaries")
    privacy = _mapping(profile["privacy"], "privacy")
    contract_roles = _mapping(contract.get("roles"), "contract.roles")
    runner_contract = _mapping(contract_roles.get("ci_runner"), "roles.ci_runner")
    allowed_classes = runner_contract.get("allowed_service_account_classes")
    if not isinstance(allowed_classes, list):
        return "FAIL", ["contract runner allowed account classes are invalid"]

    if runner["service_running"] is not True:
        blockers.append("RUNNER_SERVICE_NOT_RUNNING")
    if runner["service_start_mode"] != "Auto":
        blockers.append("RUNNER_SERVICE_NOT_AUTOMATIC")
    if runner["account_class"] not in allowed_classes:
        blockers.append("RUNNER_ACCOUNT_CLASS_NOT_ALLOWED")
    if runner["account_class"] == "LOCAL_SYSTEM":
        blockers.append("RUNNER_USES_LOCAL_SYSTEM")
    if runner["administrator"] is not False:
        blockers.append("RUNNER_ADMINISTRATOR_NOT_FALSE")
    if runner["current_process_administrator"] is not False:
        blockers.append("RUNNER_PROCESS_IS_ADMINISTRATOR")
    if runner["service_identity_matches_current_process"] is not True:
        blockers.append("RUNNER_SERVICE_PROCESS_IDENTITY_MISMATCH")
    if runner["distinct_from_interactive_owner"] is not True:
        blockers.append("RUNNER_IDENTITY_NOT_PROVEN_DISTINCT_FROM_OWNER")

    if runtime["identity_present"] is not True:
        blockers.append("RUNTIME_IDENTITY_NOT_PRESENT")
    if runtime["administrator"] is not False:
        blockers.append("RUNTIME_ADMINISTRATOR_NOT_FALSE")
    if runtime["execution_secret_direct_read_grant"] is not False:
        blockers.append("RUNTIME_EXECUTION_SECRET_READ_NOT_DENIED")
    if runtime["runner_config_direct_write_grant"] is not False:
        blockers.append("RUNTIME_RUNNER_CONFIG_WRITE_NOT_DENIED")
    if runtime["runner_root_deny_present"] is not True:
        blockers.append("RUNTIME_RUNNER_ROOT_DENY_NOT_PRESENT")

    if execution["identity_present"] is not True:
        blockers.append("EXECUTION_IDENTITY_NOT_PRESENT")
    if execution["administrator"] is not False:
        blockers.append("EXECUTION_ADMINISTRATOR_NOT_FALSE")
    if execution["execution_secret_direct_read_grant"] is not True:
        blockers.append("EXECUTION_SECRET_READ_GRANT_NOT_PRESENT")
    if execution["runner_root_deny_present"] is not True:
        blockers.append("EXECUTION_RUNNER_ROOT_DENY_NOT_PRESENT")

    if boundaries["execution_secret_sentinel_present"] is not True:
        blockers.append("EXECUTION_SECRET_SENTINEL_NOT_PRESENT")
    if boundaries["runner_execution_secret_read"] != "ACCESS_DENIED":
        blockers.append("RUNNER_EXECUTION_SECRET_READ_NOT_DENIED")
    if boundaries["execution_secret_broad_read_exposure"] is not False:
        blockers.append("EXECUTION_SECRET_BROAD_READ_EXPOSURE")
    if boundaries["runner_config_present"] is not True:
        blockers.append("RUNNER_CONFIGURATION_NOT_PRESENT")
    if boundaries["runner_config_broad_write_exposure"] is not False:
        blockers.append("RUNNER_CONFIG_BROAD_WRITE_EXPOSURE")

    for key, value in privacy.items():
        if value is not False:
            blockers.append(f"PRIVACY_FLAG_NOT_FALSE:{key}")

    return ("PASS" if not blockers else "FAIL"), blockers


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", type=Path)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        profile = load_json(args.profile, "WP6 identity profile")
        contract = load_json(args.contract, "WP6 privilege contract")
        status, blockers = assess(profile, contract)
    except ProfileError as exc:
        print(f"WP6 identity profile assessment failed: {exc}", file=sys.stderr)
        return 1

    result = {"status": status, "blockers": blockers}
    if args.json:
        print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    else:
        print(f"WP6 identity/privilege assessment: {status}")
        for blocker in blockers:
            print(f"- {blocker}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
