from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

PUBLIC_AMENDMENT = (
    ROOT
    / "docs/master-plan/OMNI_CIO_V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_AMENDMENT.md"
)
ROLE_AMENDMENT = (
    ROOT
    / "docs/master-plan/OMNI_CIO_V10_PRODUCT_USER_AND_ENGINEERING_AUTHORITY_BOUNDARY_AMENDMENT.md"
)
PROGRESSIVE_AMENDMENT = (
    ROOT / "docs/master-plan/"
    "OMNI_CIO_V10_LIVE_USER_OPERABILITY_AND_PROGRESSIVE_CAPABILITY_"
    "ACTIVATION_AMENDMENT.md"
)
CONTRACT = (
    ROOT / "docs/architecture/V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_CONTRACT.json"
)
PROGRESSIVE_CONTRACT = (
    ROOT / "docs/architecture/V10_PROGRESSIVE_CAPABILITY_ACTIVATION_CONTRACT.json"
)

LIVE_PRODUCT_AUTHORITY = (
    ROOT / "AGENTS.md",
    ROOT / "README.md",
    ROOT / "knowledge/00_PROJECT_MASTER_CONTEXT.md",
    ROOT / "knowledge/17_V10_CURRENT_PROGRAM_STATUS.md",
    ROOT / "docs/master-plan/README.md",
    ROOT / "docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md",
    ROOT / "docs/architecture/V10_WP22A_SERVICE_SELECTION.md",
    ROOT / "docs/architecture/V10_WP22A_EXECUTION_CONTRACT.md",
    ROOT / "docs/architecture/V10_WP22_SYSTEM_ADMIN_UI_CONTRACT.md",
    ROOT / ".github/copilot-instructions.md",
    ROOT / ".github/instructions/owner-handoff-and-runtime.instructions.md",
    ROOT / "gpt/PROJECT_INSTRUCTIONS.md",
    ROOT / "gpt/NEW_CHAT_PROMPT.md",
)


def read_text(path: Path, failures: list[str]) -> str:
    if not path.is_file():
        failures.append(f"missing public-plan authority file: {path.relative_to(ROOT)}")
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        failures.append(f"cannot read {path.relative_to(ROOT)}: {exc}")
        return ""


def require(text: str, marker: str, label: str, failures: list[str]) -> None:
    if marker not in text:
        failures.append(f"{label} missing marker: {marker}")


def load_json(path: Path, label: str, failures: list[str]) -> dict[str, Any]:
    raw = read_text(path, failures)
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        failures.append(f"{label} JSON invalid: {exc}")
        return {}
    if not isinstance(payload, dict):
        failures.append(f"{label} root must be an object")
        return {}
    return payload


def validate_historical_public_contract(failures: list[str]) -> None:
    payload = load_json(CONTRACT, "public hosted runtime contract", failures)
    if not payload:
        return

    expected_false = {
        ("product_target", "project_owner_is_special_product_role"),
        ("product_target", "offline_registration_allowed"),
        ("product_target", "offline_login_allowed"),
        ("product_target", "offline_authenticated_product_mode_allowed"),
        ("production_hosting", "home_public_ip_dependency_allowed"),
        ("production_hosting", "home_wifi_dependency_allowed"),
        ("production_hosting", "home_router_dependency_allowed"),
        ("production_hosting", "owner_lan_dependency_allowed"),
        ("production_hosting", "lenovo_as_public_production_origin_allowed"),
        (
            "production_hosting",
            "owner_home_power_or_internet_may_be_public_sla_dependency",
        ),
        ("initial_access_model", "billing_enabled"),
        ("initial_access_model", "trial_enabled"),
        ("initial_access_model", "subscription_enforcement"),
        ("initial_access_model", "premium_feature_gating"),
        ("initial_access_model", "payment_method_required_for_registration"),
        ("broker_credentials", "global_shared_read_token_allowed"),
        ("broker_credentials", "global_shared_trade_token_allowed"),
        ("broker_credentials", "return_raw_secret_to_browser"),
        ("broker_credentials", "browser_web_storage_allowed"),
        ("broker_credentials", "github_ci_artifact_storage_allowed"),
        ("broker_credentials", "cross_tenant_secret_access_allowed"),
        ("broker_credentials", "cortex_raw_secret_access_allowed"),
        ("activation", "implementation_default_public_multi_user_enabled"),
        ("activation", "payment_kkt_gate_required_while_billing_disabled"),
        ("t_invest", "user_supplied_token_waives_broker_terms"),
        ("safety", "trading_methods"),
        ("safety", "real_trading_enabled"),
        ("safety", "margin_allowed"),
        ("safety", "leverage_allowed"),
        ("safety", "uncovered_short_allowed"),
        ("safety", "transfer_withdrawal_allowed"),
    }
    expected_true = {
        ("product_target", "public_multi_user_target"),
        ("product_target", "ordinary_browser_global_internet_access"),
        (
            "product_target",
            "internet_connection_required_for_registration_login_product_use",
        ),
        ("product_target", "one_account_one_tenant_baseline"),
        ("production_hosting", "managed_cloud_origin_required"),
        ("identity", "tenant_scope_from_server_session_only"),
        ("identity", "database_enforced_tenant_isolation_required"),
        ("broker_credentials", "encrypted_at_rest_required"),
        ("activation", "target_after_exit_gates_public_multi_user_enabled"),
        ("safety", "protected_v9_rollback"),
        ("safety", "wp23_locked_until_corrected_wp22a_exit_gate"),
    }

    for section, key in expected_false:
        if payload.get(section, {}).get(key) is not False:
            failures.append(f"historical contract must keep {section}.{key}=false")
    for section, key in expected_true:
        if payload.get(section, {}).get(key) is not True:
            failures.append(f"historical contract must keep {section}.{key}=true")

    if payload.get("initial_access_model", {}).get("future_monetization_state") != (
        "DEFERRED_OPTIONAL"
    ):
        failures.append("future monetization must remain DEFERRED_OPTIONAL")
    if payload.get("broker_credentials", {}).get("ownership") != (
        "TENANT_SCOPED_BROKER_CONNECTION"
    ):
        failures.append(
            "broker credential ownership must remain TENANT_SCOPED_BROKER_CONNECTION"
        )
    if payload.get("t_invest", {}).get("public_connector_default") != (
        "FAIL_CLOSED_PENDING_BROKER_TERMS_PERMISSION"
    ):
        failures.append(
            "T-Invest public connector must remain fail-closed pending broker terms"
        )
    if payload.get("safety", {}).get("app_entrypoint") != "app:app":
        failures.append("protected app entrypoint must remain app:app")


def validate_progressive_contract(failures: list[str]) -> None:
    payload = load_json(
        PROGRESSIVE_CONTRACT,
        "progressive capability activation contract",
        failures,
    )
    if not payload:
        return

    if payload.get("activation_states") != [
        "IMPLEMENTED",
        "LIVE_OPERABLE",
        "BLOCKED_EXTERNAL",
        "REAL_MONEY_AUTHORIZED",
    ]:
        failures.append("progressive activation state enum changed")

    runtime = payload.get("current_runtime_defaults", {})
    for key in (
        "PUBLIC_MULTI_USER_ENABLED",
        "trading_methods",
        "broker_write",
        "REAL_TRADING_ENABLED",
    ):
        if runtime.get(key) is not False:
            failures.append(f"governance PR must keep current {key}=false")
    if runtime.get("public_tinvest_state") != (
        "FAIL_CLOSED_PENDING_BROKER_TERMS_PERMISSION"
    ):
        failures.append("progressive contract widened current public T-Invest state")

    broker = payload.get("broker", {})
    if broker.get("read_independent_from_real_execution") is not True:
        failures.append("READ must remain independent from unfinished Real execution")
    if broker.get("trade_credential_connected_does_not_authorize_submit") is not True:
        failures.append("TRADE credential connection must not authorize submit")
    if broker.get("real_submit_requires_state") != "REAL_MONEY_AUTHORIZED":
        failures.append("real submit must require REAL_MONEY_AUTHORIZED")
    for key in (
        "transfer_withdrawal_authority",
        "margin_leverage_authority",
        "uncovered_short_authority",
    ):
        if broker.get(key) is not False:
            failures.append(f"progressive contract must keep broker.{key}=false")


def validate_live_authority(failures: list[str]) -> None:
    forbidden_current_markers = (
        "WP22A — External Web Access / OWNER Authentication Security Gate",
        "Do **not** begin functional WP22A implementation until that planning PR is squash-merged",
        "The current public/free/hosted planning correction must complete its own merge/post-merge lifecycle",
        "Before functional WP22A coding resumes, the OWNER-approved planning correction",
        "Current planning freeze:",
    )
    for path in LIVE_PRODUCT_AUTHORITY:
        text = read_text(path, failures)
        if not text:
            continue
        for marker in forbidden_current_markers:
            if marker in text:
                failures.append(
                    "live authority restored obsolete product/planning wording: "
                    f"{path.relative_to(ROOT)}: {marker}"
                )

    canonical_package_name = (
        "WP22A — External Web Access / Product Authentication Security Gate"
    )
    for path in (
        ROOT / "knowledge/17_V10_CURRENT_PROGRAM_STATUS.md",
        ROOT / "docs/architecture/V10_WP22A_EXECUTION_CONTRACT.md",
    ):
        text = read_text(path, failures)
        require(
            text,
            canonical_package_name,
            str(path.relative_to(ROOT)),
            failures,
        )

    live_completion_markers = (
        (ROOT / "AGENTS.md", "The WP22A technical gate is complete only through"),
        (ROOT / "README.md", "WP22A technical closeout is accepted only through"),
    )
    for path, marker in live_completion_markers:
        text = read_text(path, failures)
        require(text, marker, str(path.relative_to(ROOT)), failures)

    amendment = read_text(PUBLIC_AMENDMENT, failures)
    for marker in (
        "home public IP address",
        "Lenovo laptop as the public production origin",
        "approved managed cloud production runtime",
        "The normal requirement for product use is an Internet connection",
        "`BILLING_ENABLED=false`",
        "`TRIAL_ENABLED=false`",
        "`SUBSCRIPTION_ENFORCEMENT=false`",
        "`PREMIUM_FEATURE_GATING=false`",
        "There is no application-global READ token and no application-global TRADE token",
        "credentials are never returned to the browser after submission",
        "public Omni-CIO account/Web activation and public T-Invest connector activation are separate gates",
        "`PUBLIC_MULTI_USER_ENABLED=false` remains the safe implementation default",
    ):
        require(amendment, marker, str(PUBLIC_AMENDMENT.relative_to(ROOT)), failures)

    role = read_text(ROLE_AMENDMENT, failures)
    for marker in (
        "PROJECT OWNER is not a special Omni-CIO product user",
        "PROJECT OWNER using Omni-CIO == ordinary USER using Omni-CIO",
        "engineering authority to operate the service != product authority to read/use a tenant",
    ):
        require(role, marker, str(ROLE_AMENDMENT.relative_to(ROOT)), failures)

    progressive = read_text(PROGRESSIVE_AMENDMENT, failures)
    for marker in (
        "one canonical Omni-CIO Web",
        "`LIVE_OPERABLE` does not imply Real-money broker-submit authority",
        "READ credential is a normal read capability, not Real-money execution authority",
        "`TRADE credential connected/verified`",
        "current runtime state**, not a permanent V10-wide release lock",
    ):
        require(
            progressive, marker, str(PROGRESSIVE_AMENDMENT.relative_to(ROOT)), failures
        )

    status = read_text(ROOT / "knowledge/17_V10_CURRENT_PROGRAM_STATUS.md", failures)
    for marker in (
        "Accepted implementation progress is **54%**",
        "Amendment 13 — progressive capability activation",
        "telegram_login | `BLOCKED_EXTERNAL`",
        "tinvest_read | `BLOCKED_EXTERNAL`",
        "current runtime state, not a V10-wide release lock",
        "WP22A — External Web Access / Product Authentication Security Gate",
        "Public T-Invest-backed production functionality remains **FAIL_CLOSED_PENDING_BROKER_TERMS_PERMISSION**",
    ):
        require(status, marker, "current status", failures)


def main() -> int:
    failures: list[str] = []
    validate_historical_public_contract(failures)
    validate_progressive_contract(failures)
    validate_live_authority(failures)

    if failures:
        for failure in failures:
            print(f"PUBLIC_PRODUCT_PLAN_FAIL: {failure}", file=sys.stderr)
        return 1

    print(
        "V10 public product plan guard passed: public hosted target, progressive "
        "capability activation, free initial access, tenant-scoped broker credentials "
        "and Real-money separation are locked."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
