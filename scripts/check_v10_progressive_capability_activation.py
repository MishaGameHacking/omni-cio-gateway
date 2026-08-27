from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AMENDMENT = (
    ROOT / "docs/master-plan/"
    "OMNI_CIO_V10_LIVE_USER_OPERABILITY_AND_PROGRESSIVE_CAPABILITY_"
    "ACTIVATION_AMENDMENT.md"
)
CONTRACT = (
    ROOT / "docs/architecture/V10_PROGRESSIVE_CAPABILITY_ACTIVATION_CONTRACT.json"
)
LEDGER = ROOT / "docs/updates/V10_CAPABILITY_ACTIVATION_LEDGER_TEMPLATE.md"
ISSUE_TEMPLATE = ROOT / ".github/ISSUE_TEMPLATE/v10_capability_activation.yml"
STATUS = ROOT / "knowledge/17_V10_CURRENT_PROGRAM_STATUS.md"
INDEX = ROOT / "docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md"
AGENTS = ROOT / "AGENTS.md"
CONTRIBUTING = ROOT / "CONTRIBUTING.md"
WP_TEMPLATE = ROOT / "docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md"
PR_TEMPLATE = ROOT / ".github/pull_request_template.md"
WORKFLOW = ROOT / ".github/workflows/v10-engineering-governance.yml"
PUBLIC_PLAN_GUARD = ROOT / "scripts/check_v10_public_product_plan.py"

EXPECTED_STATES = [
    "IMPLEMENTED",
    "LIVE_OPERABLE",
    "BLOCKED_EXTERNAL",
    "REAL_MONEY_AUTHORIZED",
]
CURRENT_CAPABILITY_STATES = {
    "telegram_login": "BLOCKED_EXTERNAL",
    "vk_id": "BLOCKED_EXTERNAL",
    "public_multi_user_tenant_access": "BLOCKED_EXTERNAL",
    "tinvest_read": "BLOCKED_EXTERNAL",
}
WORKING_BANNER = "WORKING CAPABILITY ACTIVATION STATE — NOT ACCEPTED MAIN AUTHORITY"


def _read(path: Path, failures: list[str]) -> str:
    if not path.is_file():
        failures.append(
            f"missing progressive-activation authority: {path.relative_to(ROOT)}"
        )
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        failures.append(f"cannot read {path.relative_to(ROOT)}: {exc}")
        return ""


def _require(text: str, marker: str, label: str, failures: list[str]) -> None:
    if marker not in text:
        failures.append(f"{label} missing marker: {marker}")


def _require_boolean_values(
    section: dict[str, Any],
    label: str,
    keys: tuple[str, ...],
    expected: bool,
    failures: list[str],
) -> None:
    expected_label = "true" if expected else "false"
    for key in keys:
        if section.get(key) is not expected:
            failures.append(f"{label}.{key} must be {expected_label}")


def _load_contract(failures: list[str]) -> dict[str, Any]:
    raw = _read(CONTRACT, failures)
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        failures.append(f"progressive activation contract JSON invalid: {exc}")
        return {}
    if not isinstance(payload, dict):
        failures.append("progressive activation contract root must be an object")
        return {}
    return payload


def _validate_state_model(payload: dict[str, Any], failures: list[str]) -> None:
    if payload.get("activation_states") != EXPECTED_STATES:
        failures.append("activation state enum must be exact and ordered")

    model = payload.get("product_model", {})
    _require_boolean_values(
        model,
        "product_model",
        (
            "one_canonical_web",
            "synthetic_ci_provider_double_contours_allowed",
            "sandbox_shadow_contours_allowed",
            "completed_capability_must_not_wait_unrelated_v10_blocks",
            "real_user_operability_required_for_user_facing_dod_when_provable",
            "multi_user_isolation_required_where_applicable",
            "owner_uses_ordinary_user_product_path",
        ),
        True,
        failures,
    )
    _require_boolean_values(
        model,
        "product_model",
        (
            "separate_user_facing_staging_required",
            "second_product_or_auth_bypass_allowed",
        ),
        False,
        failures,
    )

    rules = payload.get("state_rules", {})
    _require_boolean_values(
        rules,
        "state_rules",
        (
            "implemented_to_live_operable_requires_all_owning_gates",
            "implemented_to_blocked_external_requires_specific_external_blocker",
            "blocked_external_to_live_operable_requires_accepted_real_evidence",
            "v10_not_finished_is_not_valid_external_blocker",
            "live_operable_does_not_imply_real_money_authorized",
            "governance_merge_does_not_mutate_runtime_state",
            "capability_not_implemented_must_not_be_falsely_state_labeled",
            "accepted_state_separate_from_temporary_runtime_availability",
        ),
        True,
        failures,
    )


def _index_current_capabilities(
    raw_capabilities: Any, failures: list[str]
) -> dict[str, dict[str, Any]]:
    if not isinstance(raw_capabilities, list):
        failures.append("current_capabilities must be a list")
        return {}

    observed: dict[str, dict[str, Any]] = {}
    for item in raw_capabilities:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            failures.append("each current capability must have a string id")
            continue
        observed[item["id"]] = item
    return observed


def _validate_current_capability(
    capability_id: str,
    expected_state: str,
    item: dict[str, Any],
    failures: list[str],
) -> None:
    if item.get("implementation_complete") is not True:
        failures.append(f"{capability_id} must record accepted implementation")
    if item.get("state") != expected_state:
        failures.append(f"{capability_id} must remain {expected_state}")
    blockers = item.get("blockers")
    if not isinstance(blockers, list) or not blockers:
        failures.append(f"{capability_id} must record real external blockers")


def _validate_current_capabilities(
    payload: dict[str, Any], failures: list[str]
) -> None:
    observed = _index_current_capabilities(payload.get("current_capabilities"), failures)
    if set(observed) != set(CURRENT_CAPABILITY_STATES):
        failures.append(
            "current capability set does not match accepted technical baseline"
        )
        return

    for capability_id, expected_state in CURRENT_CAPABILITY_STATES.items():
        _validate_current_capability(
            capability_id,
            expected_state,
            observed[capability_id],
            failures,
        )

    multi_user = observed["public_multi_user_tenant_access"]
    if multi_user.get("runtime_flag") != "PUBLIC_MULTI_USER_ENABLED=false":
        failures.append(
            "public multi-user runtime flag must remain false in governance PR"
        )

    tinvest = observed["tinvest_read"]
    if tinvest.get("external_gate") != "FAIL_CLOSED_PENDING_BROKER_TERMS_PERMISSION":
        failures.append("T-Invest READ must retain the broker-terms external gate")


def _validate_broker_contract(payload: dict[str, Any], failures: list[str]) -> None:
    broker = payload.get("broker", {})
    _require_boolean_values(
        broker,
        "broker",
        (
            "read_independent_from_real_execution",
            "read_live_operability_must_not_wait_real_execution",
            "trade_credential_connection_may_be_live_after_own_provisioning_security_gate",
            "trade_credential_connected_does_not_authorize_submit",
            "trade_credential_never_fallback_for_reads",
            "mismatched_account_identity_fails_closed",
            "sandbox_shadow_before_real",
            "real_submit_requires_immutable_plan",
            "real_submit_requires_user_approval",
            "real_submit_requires_drift_preflight",
            "real_submit_requires_ambiguous_submit_reconciliation",
            "real_submit_requires_kill_switches",
            "real_submit_requires_broker_terms_permission",
            "submitted_is_not_filled_without_broker_evidence",
        ),
        True,
        failures,
    )
    if broker.get("executable_accounts_formula") != (
        "VERIFIED_READ_ACCOUNTS ∩ VERIFIED_TRADE_ACCOUNTS"
    ):
        failures.append("READ/TRADE executable-account intersection changed")
    if broker.get("real_submit_requires_state") != "REAL_MONEY_AUTHORIZED":
        failures.append("real submit must require REAL_MONEY_AUTHORIZED")
    _require_boolean_values(
        broker,
        "broker",
        (
            "transfer_withdrawal_authority",
            "margin_leverage_authority",
            "uncovered_short_authority",
        ),
        False,
        failures,
    )


def _validate_secret_tenant_contract(
    payload: dict[str, Any], failures: list[str]
) -> None:
    secrets = payload.get("secrets_and_tenants", {})
    _require_boolean_values(
        secrets,
        "secrets_and_tenants",
        (
            "raw_provider_secrets_in_github_ci_chat_allowed",
            "raw_broker_credentials_in_github_ci_chat_allowed",
            "raw_credentials_returned_to_browser_allowed",
            "browser_web_storage_for_broker_credentials_allowed",
            "cross_tenant_secret_or_data_access_allowed",
        ),
        False,
        failures,
    )
    _require_boolean_values(
        secrets,
        "secrets_and_tenants",
        (
            "tenant_scope_from_authenticated_server_state_required",
            "database_enforced_tenant_isolation_required",
        ),
        True,
        failures,
    )


def _validate_runtime_defaults(payload: dict[str, Any], failures: list[str]) -> None:
    runtime = payload.get("current_runtime_defaults", {})
    if runtime.get("app_entrypoint") != "app:app":
        failures.append("protected app entrypoint must remain app:app")
    _require_boolean_values(
        runtime,
        "current_runtime_defaults",
        (
            "PUBLIC_MULTI_USER_ENABLED",
            "trading_methods",
            "broker_write",
            "REAL_TRADING_ENABLED",
        ),
        False,
        failures,
    )
    if (
        runtime.get("public_tinvest_state")
        != "FAIL_CLOSED_PENDING_BROKER_TERMS_PERMISSION"
    ):
        failures.append("current public T-Invest state must remain fail-closed")


def _validate_broker_and_security(payload: dict[str, Any], failures: list[str]) -> None:
    _validate_broker_contract(payload, failures)
    _validate_secret_tenant_contract(payload, failures)
    _validate_runtime_defaults(payload, failures)


def _validate_documents(failures: list[str]) -> None:
    amendment = _read(AMENDMENT, failures)
    for marker in (
        "Live User Operability & Progressive Capability Activation Law",
        "one canonical Omni-CIO Web",
        "IMPLEMENTED",
        "LIVE_OPERABLE",
        "BLOCKED_EXTERNAL",
        "REAL_MONEY_AUTHORIZED",
        "EXECUTABLE_ACCOUNTS = VERIFIED_READ_ACCOUNTS ∩ VERIFIED_TRADE_ACCOUNTS",
        "`PRODUCT IMPLEMENTATION PAUSED` remains true",
    ):
        _require(amendment, marker, "Amendment 13", failures)

    index = _read(INDEX, failures)
    _require(index, "### 13. Live User Operability", "amendments index", failures)

    status = _read(STATUS, failures)
    for marker in (
        "Amendment 13 — progressive capability activation",
        "telegram_login | `BLOCKED_EXTERNAL`",
        "tinvest_read | `BLOCKED_EXTERNAL`",
        "current runtime state, not a V10-wide release lock",
        "PRODUCT IMPLEMENTATION PAUSED",
        "START V10 WEB VISUAL SYSTEM UPDATE",
    ):
        _require(status, marker, "current status", failures)

    agents = _read(AGENTS, failures)
    contributing = _read(CONTRIBUTING, failures)
    wp_template = _read(WP_TEMPLATE, failures)
    pr_template = _read(PR_TEMPLATE, failures)
    for text, label in (
        (agents, "AGENTS.md"),
        (contributing, "CONTRIBUTING.md"),
        (wp_template, "WP execution template"),
        (pr_template, "PR template"),
    ):
        for marker in (
            "Progressive Capability Activation",
            "LIVE_OPERABLE",
            "BLOCKED_EXTERNAL",
            "REAL_MONEY_AUTHORIZED",
            "VERIFIED_READ_ACCOUNTS ∩ VERIFIED_TRADE_ACCOUNTS",
        ):
            _require(text, marker, label, failures)

    ledger = _read(LEDGER, failures)
    issue = _read(ISSUE_TEMPLATE, failures)
    _require(ledger, WORKING_BANNER, "activation ledger", failures)
    _require(issue, WORKING_BANNER, "activation issue template", failures)

    workflow = _read(WORKFLOW, failures)
    _require(
        workflow,
        "python scripts/check_v10_progressive_capability_activation.py",
        "engineering governance workflow",
        failures,
    )
    _require(
        workflow,
        "tests.test_v10_progressive_capability_activation",
        "engineering governance workflow",
        failures,
    )

    public_guard = _read(PUBLIC_PLAN_GUARD, failures)
    _require(
        public_guard,
        "V10_PROGRESSIVE_CAPABILITY_ACTIVATION_CONTRACT.json",
        "public product plan guard",
        failures,
    )


def main() -> int:
    failures: list[str] = []
    payload = _load_contract(failures)
    if payload:
        _validate_state_model(payload, failures)
        _validate_current_capabilities(payload, failures)
        _validate_broker_and_security(payload, failures)
    _validate_documents(failures)

    if failures:
        for failure in failures:
            print(f"PROGRESSIVE_ACTIVATION_FAIL: {failure}", file=sys.stderr)
        return 1

    print(
        "V10 progressive capability activation guard passed: one canonical Web, "
        "real-user operability, tenant isolation, READ/TRADE separation and "
        "REAL_MONEY_AUTHORIZED boundaries are locked."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
