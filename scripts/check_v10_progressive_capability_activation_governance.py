from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PATHS = {
    "amendment": ROOT
    / (
        "docs/master-plan/"
        "OMNI_CIO_V10_LIVE_USER_OPERABILITY_AND_PROGRESSIVE_CAPABILITY_"
        "ACTIVATION_AMENDMENT.md"
    ),
    "index": ROOT / "docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md",
    "contract": ROOT
    / "docs/architecture/V10_PROGRESSIVE_CAPABILITY_ACTIVATION_CONTRACT.json",
    "ledger": ROOT / "docs/operations/V10_CAPABILITY_ACTIVATION_LEDGER.json",
    "standard": ROOT
    / "docs/operations/V10_LIVE_USER_OPERABILITY_ACCEPTANCE_STANDARD.md",
    "issue_template": ROOT / ".github/ISSUE_TEMPLATE/v10_capability_activation.yml",
    "public_contract": ROOT
    / "docs/architecture/V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_CONTRACT.json",
    "status": ROOT / "knowledge/17_V10_CURRENT_PROGRAM_STATUS.md",
    "amendment12": ROOT
    / "docs/master-plan/OMNI_CIO_V10_INTEGRATED_SYSTEM_UPDATE_EXECUTION_AMENDMENT.md",
    "workflow": ROOT / ".github/workflows/v10-engineering-governance.yml",
}

ALLOWED_STATES = [
    "IMPLEMENTED",
    "LIVE_OPERABLE",
    "BLOCKED_EXTERNAL",
    "REAL_MONEY_AUTHORIZED",
]
BLOCKED_EXTERNAL = "BLOCKED_EXTERNAL"
REAL_MONEY_AUTHORIZED = "REAL_MONEY_AUTHORIZED"
OWNER_START_COMMAND = "START V10 WEB VISUAL SYSTEM UPDATE"
CAPABILITY_BANNER = (
    "CAPABILITY ACTIVATION WORKING STATE — NOT V10 PROGRESS AUTHORITY"
)


def fail_unless(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def read_text(name: str, failures: list[str]) -> str:
    path = PATHS[name]
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        failures.append(f"cannot read {path.relative_to(ROOT)}: {exc}")
        return ""


def load_json(name: str, failures: list[str]) -> dict[str, Any]:
    raw = read_text(name, failures)
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        failures.append(
            f"invalid JSON in {PATHS[name].relative_to(ROOT)}: {exc}"
        )
        return {}
    fail_unless(
        isinstance(payload, dict),
        f"{name} JSON root must be an object",
        failures,
    )
    return payload if isinstance(payload, dict) else {}


def section(
    payload: dict[str, Any], key: str, failures: list[str]
) -> dict[str, Any]:
    value = payload.get(key)
    fail_unless(
        isinstance(value, dict),
        f"contract section must be object: {key}",
        failures,
    )
    return value if isinstance(value, dict) else {}


def require_true(
    payload: dict[str, Any],
    keys: tuple[str, ...],
    prefix: str,
    failures: list[str],
) -> None:
    for key in keys:
        fail_unless(
            payload.get(key) is True,
            f"{prefix}.{key} must be true",
            failures,
        )


def require_false(
    payload: dict[str, Any],
    keys: tuple[str, ...],
    prefix: str,
    failures: list[str],
) -> None:
    for key in keys:
        fail_unless(
            payload.get(key) is False,
            f"{prefix}.{key} must be false",
            failures,
        )


def validate_authority(payload: dict[str, Any], failures: list[str]) -> None:
    authority = section(payload, "authority", failures)
    expected = {
        "product_progress_effect": "NONE",
        "runtime_mutation_effect": "NONE",
        "product_implementation_paused_after_acceptance": True,
        "next_prepared_system_update": "WEB-VISUAL-INTEGRATED",
        "owner_start_required": True,
        "owner_start_command": OWNER_START_COMMAND,
        "canonical_user_product": "ONE_CANONICAL_OMNI_CIO_WEB",
        "separate_staging_site_required": False,
    }
    for key, expected_value in expected.items():
        fail_unless(
            authority.get(key) == expected_value,
            f"authority.{key} mismatch",
            failures,
        )


def validate_progressive_activation(
    payload: dict[str, Any], failures: list[str]
) -> None:
    progressive = section(payload, "progressive_activation", failures)
    require_true(
        progressive,
        (
            "completed_capability_must_not_wait_for_unrelated_future_scope",
            "direct_gate_evidence_required",
            "external_gate_evidence_required_when_applicable",
            "canonical_web_is_live_product",
            "real_user_operability_required_for_user_facing_dod",
            "multi_user_isolation_required_when_multi_user",
            "kill_switch_may_temporarily_disable_accepted_capability",
        ),
        "progressive_activation",
        failures,
    )
    require_false(
        progressive,
        (
            "unrelated_unfinished_v10_scope_may_block_live_operability",
            "separate_staging_site_required",
            "synthetic_evidence_may_replace_required_external_evidence",
            "emergency_kill_switch_is_lifecycle_state",
        ),
        "progressive_activation",
        failures,
    )


def validate_identity(payload: dict[str, Any], failures: list[str]) -> None:
    identity = section(payload, "identity_and_multi_user", failures)
    fail_unless(
        identity.get("ordinary_login_providers") == ["TELEGRAM", "VK_ID"],
        "ordinary login providers mismatch",
        failures,
    )
    require_true(
        identity,
        (
            "tenant_scope_from_server_session_only",
            "database_enforced_tenant_isolation_required",
            "PUBLIC_MULTI_USER_ENABLED_is_capability_activation_control",
        ),
        "identity_and_multi_user",
        failures,
    )
    require_false(
        identity,
        (
            "owner_admin_developer_demo_login_allowed",
            "cross_tenant_access_allowed",
            "PUBLIC_MULTI_USER_ENABLED_current_value_changed_by_this_amendment",
        ),
        "identity_and_multi_user",
        failures,
    )


def validate_broker(payload: dict[str, Any], failures: list[str]) -> None:
    broker = section(payload, "broker_credentials", failures)
    require_true(
        broker,
        (
            "read_can_be_live_operable_before_real_execution",
            "read_requires_broker_terms_security_secret_custody_acceptance",
            "real_portfolio_positions_operations_may_follow_read_live_operability",
            "trade_credential_provisioning_can_be_live_operable_before_submit",
        ),
        "broker_credentials",
        failures,
    )
    require_false(
        broker,
        (
            "trade_credential_connected_is_real_money_authorized",
            "full_access_trade_credential_may_fallback_for_read",
            "global_shared_read_token_allowed",
            "global_shared_trade_token_allowed",
            "cross_tenant_secret_access_allowed",
            "cortex_raw_secret_access_allowed",
            "raw_secret_in_browser_web_storage_allowed",
            "raw_secret_in_github_ci_artifacts_chat_allowed",
            "user_supplied_token_waives_broker_terms",
        ),
        "broker_credentials",
        failures,
    )
    fail_unless(
        broker.get("execution_account_rule")
        == "VERIFIED_READ_ACCOUNTS_INTERSECTION_VERIFIED_TRADE_ACCOUNTS",
        "READ/TRADE account identity intersection rule mismatch",
        failures,
    )
    fail_unless(
        broker.get("current_public_t_invest_connector_state")
        == BLOCKED_EXTERNAL,
        "current public T-Invest connector must remain BLOCKED_EXTERNAL",
        failures,
    )


def validate_real_money(payload: dict[str, Any], failures: list[str]) -> None:
    real_money = section(payload, "real_money", failures)
    fail_unless(
        real_money.get("real_money_state") == REAL_MONEY_AUTHORIZED,
        "real-money lifecycle state mismatch",
        failures,
    )
    require_false(
        real_money,
        (
            "credential_connection_is_authorization",
            "REAL_TRADING_ENABLED_current_default",
            "trading_methods_current_default",
            "transfer_withdrawal_authority_expanded",
            "margin_leverage_authority_expanded",
            "uncovered_short_authority_expanded",
            "ai_direct_broker_write_authority",
        ),
        "real_money",
        failures,
    )
    required_real_money = set(real_money.get("required_before_authorization", []))
    for required in {
        "SANDBOX_OR_SHADOW_EVIDENCE",
        "IMMUTABLE_PLAN_APPROVAL",
        "DRIFT_STOP_AND_REPLAN",
        "AMBIGUOUS_SUBMIT_RECONCILIATION",
        "BROKER_RECONCILIATION",
        "EMERGENCY_KILL_SWITCHES",
    }:
        fail_unless(
            required in required_real_money,
            f"missing Real-money prerequisite: {required}",
            failures,
        )


def validate_definition_of_done(
    payload: dict[str, Any], failures: list[str]
) -> None:
    dod = section(payload, "user_facing_definition_of_done", failures)
    require_true(
        dod,
        (
            "accepted_implementation_required",
            "exact_head_success_only_required",
            "canonical_web_deployment_required_for_live_operable",
            "ordinary_user_path_required",
            "real_user_operability_evidence_required",
            "multi_user_isolation_evidence_required_when_applicable",
            "deterministic_cross_tenant_negative_tests_required_when_applicable",
            "secret_private_data_exclusion_required",
            "rollback_recovery_required",
            "external_evidence_required_when_applicable",
            "capability_ledger_transition_required",
        ),
        "user_facing_definition_of_done",
        failures,
    )


def validate_ledgers(payload: dict[str, Any], failures: list[str]) -> None:
    ledgers = section(payload, "ledgers", failures)
    expected = {
        "capability_activation_ledger": (
            "docs/operations/V10_CAPABILITY_ACTIVATION_LEDGER.json"
        ),
        "github_dashboard_issue_template": (
            ".github/ISSUE_TEMPLATE/v10_capability_activation.yml"
        ),
        "working_state_banner": CAPABILITY_BANNER,
        "capability_ledger_is_program_progress_authority": False,
        "dashboard_is_program_progress_authority": False,
    }
    for key, expected_value in expected.items():
        fail_unless(
            ledgers.get(key) == expected_value,
            f"ledgers.{key} mismatch",
            failures,
        )


def validate_protected_invariants(
    payload: dict[str, Any], failures: list[str]
) -> None:
    protected = section(payload, "protected_invariants", failures)
    fail_unless(
        protected.get("app_entrypoint") == "app:app",
        "protected app entrypoint must remain app:app",
        failures,
    )
    require_true(
        protected,
        (
            "protected_v9_rollback",
            "tenant_isolation_required",
            "secret_exclusion_required",
            "exact_head_success_only",
            "squash_merge_required",
            "post_merge_regression_shield_required",
            "temporary_verifier_commits_prs_branches_forbidden",
        ),
        "protected_invariants",
        failures,
    )
    require_false(
        protected,
        (
            "trading_methods",
            "REAL_TRADING_ENABLED",
            "broker_write",
            "PUBLIC_MULTI_USER_ENABLED_changed_by_this_amendment",
            "transfer_withdrawal_authority",
            "margin_leverage_uncovered_short_authority",
        ),
        "protected_invariants",
        failures,
    )


def validate_contract(payload: dict[str, Any], failures: list[str]) -> None:
    fail_unless(
        payload.get("schema")
        == "omni-cio.v10.progressive-capability-activation.v1",
        "progressive capability contract schema mismatch",
        failures,
    )
    fail_unless(
        payload.get("status")
        == "OWNER_APPROVED_EFFECTIVE_WHEN_PRESENT_ON_ACCEPTED_MAIN",
        "progressive capability contract status mismatch",
        failures,
    )
    fail_unless(
        payload.get("capability_states") == ALLOWED_STATES,
        "capability state set/order mismatch",
        failures,
    )
    validate_authority(payload, failures)
    validate_progressive_activation(payload, failures)
    validate_identity(payload, failures)
    validate_broker(payload, failures)
    validate_real_money(payload, failures)
    validate_definition_of_done(payload, failures)
    validate_ledgers(payload, failures)
    validate_protected_invariants(payload, failures)


def validate_ledger(payload: dict[str, Any], failures: list[str]) -> None:
    fail_unless(
        payload.get("schema") == "omni-cio.v10.capability-activation-ledger.v1",
        "capability ledger schema mismatch",
        failures,
    )
    fail_unless(
        payload.get("progress_authority") is False,
        "capability ledger must not become V10 progress authority",
        failures,
    )
    fail_unless(
        payload.get("allowed_states") == ALLOWED_STATES,
        "capability ledger allowed-state set mismatch",
        failures,
    )
    capabilities = payload.get("capabilities")
    fail_unless(
        isinstance(capabilities, list),
        "capabilities must be an array",
        failures,
    )
    if not isinstance(capabilities, list):
        return

    seen: set[str] = set()
    for item in capabilities:
        fail_unless(
            isinstance(item, dict),
            "capability ledger item must be an object",
            failures,
        )
        if not isinstance(item, dict):
            continue
        capability_id = item.get("capability_id")
        fail_unless(
            isinstance(capability_id, str) and capability_id != "",
            "capability_id must be non-empty string",
            failures,
        )
        if isinstance(capability_id, str):
            fail_unless(
                capability_id not in seen,
                f"duplicate capability_id: {capability_id}",
                failures,
            )
            seen.add(capability_id)
        state = item.get("state")
        fail_unless(
            state in ALLOWED_STATES,
            f"invalid capability state for {capability_id}: {state}",
            failures,
        )
        if state == BLOCKED_EXTERNAL:
            blockers = item.get("external_blockers")
            fail_unless(
                isinstance(blockers, list) and len(blockers) > 0,
                f"BLOCKED_EXTERNAL capability lacks blockers: {capability_id}",
                failures,
            )
        fail_unless(
            state != REAL_MONEY_AUTHORIZED,
            "Amendment 13 must not claim any current REAL_MONEY_AUTHORIZED capability",
            failures,
        )

    for required in {
        "product_authentication_telegram_vk",
        "public_multi_user_tenant_access",
        "t_invest_read_public_connector",
    }:
        fail_unless(
            required in seen,
            f"current capability ledger missing required entry: {required}",
            failures,
        )


def validate_public_runtime_contract(failures: list[str]) -> None:
    payload = load_json("public_contract", failures)
    broker = payload.get("broker_credentials", {})
    safety = payload.get("safety", {})
    fail_unless(
        isinstance(broker, dict),
        "public runtime broker_credentials must be object",
        failures,
    )
    fail_unless(
        isinstance(safety, dict),
        "public runtime safety must be object",
        failures,
    )
    if isinstance(broker, dict):
        expected_broker = {
            "ownership": "TENANT_SCOPED_BROKER_CONNECTION",
            "execution_account_rule": (
                "VERIFIED_READ_ACCOUNTS_INTERSECTION_VERIFIED_TRADE_ACCOUNTS"
            ),
            "cross_tenant_secret_access_allowed": False,
            "transfer_withdrawal_authority": False,
        }
        for key, expected_value in expected_broker.items():
            fail_unless(
                broker.get(key) == expected_value,
                f"public runtime broker_credentials.{key} mismatch",
                failures,
            )
    if isinstance(safety, dict):
        expected_safety = {
            "app_entrypoint": "app:app",
            "trading_methods": False,
            "real_trading_enabled": False,
            "margin_allowed": False,
            "uncovered_short_allowed": False,
        }
        for key, expected_value in expected_safety.items():
            fail_unless(
                safety.get(key) == expected_value,
                f"public runtime safety.{key} mismatch",
                failures,
            )


def validate_surface_markers(failures: list[str]) -> None:
    markers = {
        "amendment": (
            (
                "Live User Operability & Progressive Capability Activation Law / "
                "Amendment 13"
            ),
            "IMPLEMENTED",
            "LIVE_OPERABLE",
            "BLOCKED_EXTERNAL",
            "REAL_MONEY_AUTHORIZED",
            "TRADE credential connected != real broker submit authorized",
            OWNER_START_COMMAND,
        ),
        "index": (
            "Live User Operability & Progressive Capability Activation Law",
            (
                "OMNI_CIO_V10_LIVE_USER_OPERABILITY_AND_PROGRESSIVE_CAPABILITY_"
                "ACTIVATION_AMENDMENT.md"
            ),
            "V10_PROGRESSIVE_CAPABILITY_ACTIVATION_CONTRACT.json",
        ),
        "standard": (
            "Live User Operability Acceptance Standard",
            "real-user operability",
            "Multi-user isolation acceptance",
            "REAL_MONEY_AUTHORIZED",
        ),
        "issue_template": (
            "V10 Capability Activation Dashboard",
            CAPABILITY_BANNER,
            (
                "TRADE credential connected is not represented as Real broker-submit "
                "authorization"
            ),
        ),
        "status": (
            "PRODUCT IMPLEMENTATION PAUSED",
            "WEB-VISUAL-INTEGRATED",
            "OWNER START REQUIRED",
            "FAIL_CLOSED_PENDING_BROKER_TERMS_PERMISSION",
            "REAL_TRADING_ENABLED=false",
        ),
        "amendment12": (
            "production cutover",
            "Real-money authority",
            OWNER_START_COMMAND,
        ),
        "workflow": (
            "python scripts/check_v10_progressive_capability_activation_governance.py",
            "scripts/check_v10_progressive_capability_activation_governance.py",
            "tests.test_v10_progressive_capability_activation_governance",
        ),
    }
    for name, required_markers in markers.items():
        content = read_text(name, failures)
        for marker in required_markers:
            fail_unless(
                marker in content,
                f"{PATHS[name].relative_to(ROOT)} missing marker: {marker}",
                failures,
            )


def main() -> int:
    failures: list[str] = []
    validate_contract(load_json("contract", failures), failures)
    validate_ledger(load_json("ledger", failures), failures)
    validate_public_runtime_contract(failures)
    validate_surface_markers(failures)

    if failures:
        print(
            "V10 progressive capability activation governance check failed:",
            file=sys.stderr,
        )
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("V10 progressive capability activation governance check passed.")
    print(
        "Capability states: IMPLEMENTED / LIVE_OPERABLE / "
        "BLOCKED_EXTERNAL / REAL_MONEY_AUTHORIZED"
    )
    print(
        "Canonical Web: completed independent capabilities become live after "
        "direct gates"
    )
    print(
        "Broker: READ independent; TRADE credential connection is not submit authority"
    )
    print("Real money: remains fail-closed pending its owning execution gate")
    print("Product implementation: PAUSED until exact OWNER START")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
