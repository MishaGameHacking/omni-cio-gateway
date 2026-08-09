from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "architecture" / "V10_WP9A_OPERATIONS_CONTRACT.json"
WP5_THRESHOLDS = ROOT / "infrastructure" / "windows" / "wp5_node_thresholds.json"


class ContractError(RuntimeError):
    pass


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_contract(contract: dict, wp5: dict) -> None:
    if contract.get("schema_version") != "1" or contract.get("work_package") != "WP9A":
        raise ContractError("WP9A_CONTRACT_IDENTITY_INVALID")

    authority = contract["authority"]
    if authority["stable_entrypoint"] != "app:app":
        raise ContractError("STABLE_ENTRYPOINT_CHANGED")
    if authority["trading_methods"] is not False:
        raise ContractError("TRADING_METHODS_ENABLED")
    if authority["real_money_authority_change"] is not False:
        raise ContractError("REAL_MONEY_AUTHORITY_CHANGED")

    time = contract["time"]
    wp5_clock = wp5["clock"]
    expected_clock = {
        "warning_absolute_offset_ms": wp5_clock["warn_absolute_offset_ms"],
        "block_sensitive_absolute_offset_ms": wp5_clock[
            "block_sensitive_absolute_offset_ms"
        ],
        "unknown_offset_blocks_sensitive_operations": wp5_clock[
            "unknown_offset_blocks_sensitive_operations"
        ],
        "windows_time_service_must_be_running": wp5_clock[
            "windows_time_service_must_be_running"
        ],
        "canonical_application_timezone": wp5_clock["canonical_application_timezone"],
    }
    for key, expected in expected_clock.items():
        if time.get(key) != expected:
            raise ContractError(f"WP5_CLOCK_THRESHOLD_DRIFT:{key}")

    resources = contract["resources"]
    if resources.get("reuse_wp5_thresholds_without_relaxation") is not True:
        raise ContractError("WP5_RESOURCE_THRESHOLDS_NOT_REUSED")

    restart = contract["restart_and_crash_loop"]
    if restart.get("max_attempts") != 3 or restart.get("backoff_seconds") != 60:
        raise ContractError("WP9_BOUNDED_RESTART_POLICY_CHANGED")
    if restart.get("infinite_restart_forbidden") is not True:
        raise ContractError("INFINITE_RESTART_NOT_FORBIDDEN")
    if restart.get("real_execution_auto_restart_without_reconciliation_forbidden") is not True:
        raise ContractError("REAL_EXECUTION_RESTART_GUARD_MISSING")

    runner = contract["github_runner"]
    if runner.get("policy") != "DEFAULT_AUTO_UPDATE_MONITORED":
        raise ContractError("RUNNER_UPDATE_POLICY_INVALID")
    if runner.get("manual_disable_update_forbidden_without_review") is not True:
        raise ContractError("RUNNER_DISABLEUPDATE_GUARD_MISSING")
    if int(runner.get("staleness_limit_days_when_auto_update_disabled", 0)) > 30:
        raise ContractError("RUNNER_STALENESS_WINDOW_TOO_WIDE")

    postgres = contract["postgresql"]
    if int(postgres.get("accepted_major", 0)) != 18:
        raise ContractError("POSTGRES_MAJOR_CHANGED")
    if postgres.get("automatic_update_by_omni_cio") is not False:
        raise ContractError("POSTGRES_AUTOUPDATE_ENABLED")
    if postgres.get("major_upgrade_out_of_scope") is not True:
        raise ContractError("POSTGRES_MAJOR_UPGRADE_SCOPE_LEAK")

    ollama = contract["ollama"]
    if ollama.get("runtime_required_now") is not False:
        raise ContractError("OLLAMA_PREMATURE_RUNTIME_REQUIREMENT")
    if ollama.get("installation_or_activation_in_wp9a_forbidden") is not True:
        raise ContractError("OLLAMA_PREMATURE_INSTALL_NOT_FORBIDDEN")
    if ollama.get("automatic_update_by_omni_cio") is not False:
        raise ContractError("OLLAMA_AUTOUPDATE_ENABLED")

    nvidia = contract["nvidia_driver"]
    if nvidia.get("automatic_driver_update_by_omni_cio") is not False:
        raise ContractError("NVIDIA_AUTOUPDATE_ENABLED")
    if nvidia.get("post_update_wp5_thermal_compatibility_required") is not True:
        raise ContractError("NVIDIA_POSTUPDATE_THERMAL_GATE_MISSING")

    maintenance = contract["maintenance"]
    if maintenance.get("pre_update_health_required") is not True:
        raise ContractError("PRE_UPDATE_HEALTH_GATE_MISSING")
    if maintenance.get("post_update_health_required") is not True:
        raise ContractError("POST_UPDATE_HEALTH_GATE_MISSING")
    if maintenance.get("post_reboot_wp9_audit_required") is not True:
        raise ContractError("POST_REBOOT_WP9_GATE_MISSING")

    logging = contract["logging"]
    allowed = set(logging.get("allowed_fields", []))
    forbidden = set(logging.get("forbidden_fields", []))
    if not allowed or allowed & forbidden:
        raise ContractError("LOG_FIELD_POLICY_INVALID")
    required_forbidden = {
        "secret",
        "token",
        "authorization",
        "ciphertext",
        "password",
        "account_id",
        "portfolio_payload",
        "process_command_line",
        "process_dump",
    }
    if not required_forbidden.issubset(forbidden):
        raise ContractError("LOG_PRIVATE_FIELD_GUARDS_INCOMPLETE")
    if logging.get("ci_private_payload_upload_forbidden") is not True:
        raise ContractError("CI_PRIVATE_PAYLOAD_UPLOAD_NOT_FORBIDDEN")

    impact = contract["update_impact_gate"]
    if "REGRESSION" not in impact.get("calculations", []):
        raise ContractError("CALCULATION_UPDATE_REGRESSION_GATE_MISSING")
    if "EVAL" not in impact.get("ai_behavior", []):
        raise ContractError("AI_UPDATE_EVAL_GATE_MISSING")
    if "ROLLBACK" not in impact.get("database_compatibility", []):
        raise ContractError("DB_UPDATE_ROLLBACK_GATE_MISSING")
    if "OWNER_REVIEW" not in impact.get("broker_execution_path", []):
        raise ContractError("EXECUTION_UPDATE_OWNER_GATE_MISSING")
    if impact.get("update_availability_is_never_real_submit_authority") is not True:
        raise ContractError("UPDATE_AUTHORITY_FIREWALL_MISSING")

    privacy = contract["privacy"]
    if any(privacy.get(key) is not False for key in privacy):
        raise ContractError("WP9A_PRIVATE_INPUT_REQUIREMENT_PRESENT")

    exit_gate = contract["exit_gate"]
    if exit_gate.get("next_wp") != "WP10":
        raise ContractError("WP9A_NEXT_WP_INVALID")
    required_exit_flags = [key for key in exit_gate if key.endswith("_pass") or key.endswith("_required")]
    if any(exit_gate[key] is not True for key in required_exit_flags):
        raise ContractError("WP9A_EXIT_GATE_WEAKENED")


def main() -> int:
    contract = _load(CONTRACT)
    wp5 = _load(WP5_THRESHOLDS)
    validate_contract(contract, wp5)
    print("V10 WP9A operations contract check passed.")
    print("WP5 time/resource thresholds: reused without relaxation")
    print("WP9 restart boundary: max 3 / 60-second backoff")
    print("Later product runtimes: not activated by WP9A")
    print("Real-money authority: unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
