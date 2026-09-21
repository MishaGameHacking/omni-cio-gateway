from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AMENDMENT = (
    ROOT
    / "docs/master-plan/OMNI_CIO_V10_CLOUDFLARE_PUBLIC_PRODUCT_INTEGRATED_DELIVERY_AMENDMENT.md"
)
CONTRACT = (
    ROOT / "docs/architecture/V10_CLOUDFLARE_PUBLIC_PRODUCT_INTEGRATED_CONTRACT.json"
)
INDEX = ROOT / "docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md"
STATUS = ROOT / "knowledge/17_V10_CURRENT_PROGRAM_STATUS.md"
README = ROOT / "README.md"
AGENTS = ROOT / "AGENTS.md"
CONTRIBUTING = ROOT / "CONTRIBUTING.md"
MASTER_CONTEXT = ROOT / "knowledge/00_PROJECT_MASTER_CONTEXT.md"
GOVERNANCE_WORKFLOW = ROOT / ".github/workflows/v10-engineering-governance.yml"

UPDATE_ID = "CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED"
BRANCH = "system/cloudflare-public-product"
OWNER_START_COMMAND = "START V10 WEB VISUAL SYSTEM UPDATE"
EXPECTED_MILESTONES = [
    ("CF-A", "CLOUDFLARE-BUILDS-VERIFIER-INTEGRATION", False, False),
    ("CF-B", "CLOUDFLARE-RUNTIME-COMPATIBILITY", False, False),
    ("CF-C", "CLOUDFLARE-CANDIDATE-DEPLOYMENT", True, False),
    ("CF-D", "CLOUDFLARE-PUBLIC-CUTOVER", True, True),
]


def _read(path: Path, failures: list[str]) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        failures.append(f"cannot read {path.relative_to(ROOT)}: {exc}")
        return ""


def _load_contract(failures: list[str]) -> dict[str, Any]:
    raw = _read(CONTRACT, failures)
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        failures.append(f"invalid integrated Cloudflare contract JSON: {exc}")
        return {}
    if not isinstance(payload, dict):
        failures.append("integrated Cloudflare contract root must be an object")
        return {}
    return payload


def _expect_bool(
    section: dict[str, Any],
    key: str,
    expected: bool,
    label: str,
    failures: list[str],
) -> None:
    if section.get(key) is not expected:
        failures.append(f"{label}.{key} must be {expected}")


def _section(payload: dict[str, Any], key: str, failures: list[str]) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        failures.append(f"{key} must be an object")
        return {}
    return value


def _validate_identity(payload: dict[str, Any], failures: list[str]) -> None:
    if payload.get("schema") != "omni-cio.v10.cloudflare-public-product-integrated.v1":
        failures.append("integrated Cloudflare contract schema mismatch")
    if (
        payload.get("status")
        != "OWNER_APPROVED_EFFECTIVE_WHEN_PRESENT_ON_ACCEPTED_MAIN"
    ):
        failures.append("integrated Cloudflare contract status mismatch")
    if payload.get("update_id") != UPDATE_ID:
        failures.append("integrated Cloudflare update_id mismatch")
    if payload.get("execution_unit") != "INTEGRATED_SYSTEM_UPDATE":
        failures.append("Cloudflare public product must be an INTEGRATED_SYSTEM_UPDATE")
    if payload.get("default_branch") != BRANCH:
        failures.append("integrated Cloudflare branch mismatch")


def _validate_delivery(payload: dict[str, Any], failures: list[str]) -> None:
    delivery = _section(payload, "delivery", failures)
    for key in (
        "one_integrated_branch_default",
        "one_final_pr_default",
        "internal_milestone_order_required",
        "internal_exit_gate_before_dependent_milestone_required",
        "mandatory_split_trigger_may_still_force_split",
        "integration_ready_before_external_final_verification",
    ):
        _expect_bool(delivery, key, True, "delivery", failures)
    _expect_bool(
        delivery,
        "separate_main_acceptance_between_internal_milestones_required",
        False,
        "delivery",
        failures,
    )


def _validate_milestones(payload: dict[str, Any], failures: list[str]) -> None:
    milestones = payload.get("milestones")
    if not isinstance(milestones, list):
        failures.append("milestones must be a list")
        return

    observed: list[tuple[object, object, object, object]] = []
    for item in milestones:
        if not isinstance(item, dict):
            failures.append("each milestone must be an object")
            continue
        observed.append(
            (
                item.get("id"),
                item.get("legacy_stage_id"),
                item.get("provider_mutation_allowed"),
                item.get("production_promotion_allowed"),
            )
        )
    if observed != EXPECTED_MILESTONES:
        failures.append("Cloudflare internal milestone order/authority mismatch")


def _validate_cloudflare_first(payload: dict[str, Any], failures: list[str]) -> None:
    cloudflare = _section(payload, "cloudflare_first", failures)
    for key in (
        "prefer_cloudflare_when_semantically_equivalent",
        "workers_static_assets_preferred_for_existing_react_vite_web",
        "python_workers_require_dependency_compatibility_proof",
        "containers_allowed_for_proven_full_linux_native_runtime_need",
        "neon_postgresql18_may_remain_until_equivalent_migration_is_proved",
        "github_engineering_authority_retained",
        "protected_v9_render_recovery_preserved",
    ):
        _expect_bool(cloudflare, key, True, "cloudflare_first", failures)
    for key in (
        "adopt_feature_merely_because_available",
        "d1_replaces_financial_postgresql_by_default",
        "hyperdrive_postgresql18_assumed_compatible",
        "new_v10_render_use_allowed",
    ):
        _expect_bool(cloudflare, key, False, "cloudflare_first", failures)


def _validate_cost_security(payload: dict[str, Any], failures: list[str]) -> None:
    cost = _section(payload, "cost_security", failures)
    _expect_bool(
        cost,
        "workers_paid_included_capacity_may_be_used",
        True,
        "cost_security",
        failures,
    )
    for key in (
        "automatic_paid_overage_allowed",
        "higher_plan_without_fresh_owner_approval_allowed",
        "real_secrets_in_repository_chat_ci_artifacts_allowed",
        "quota_or_provider_outage_may_be_reported_as_success",
    ):
        _expect_bool(cost, key, False, "cost_security", failures)


def _validate_product_activation(payload: dict[str, Any], failures: list[str]) -> None:
    activation = _section(payload, "product_activation", failures)
    for key in (
        "goal_public_current_safe_product",
        "capability_specific_live_gate_required",
    ):
        _expect_bool(activation, key, True, "product_activation", failures)
    for key in (
        "public_multi_user_enabled_by_governance_alone",
        "telegram_vk_live_without_real_provider_evidence_allowed",
        "tinvest_read_live_without_broker_terms_and_secret_custody_allowed",
    ):
        _expect_bool(activation, key, False, "product_activation", failures)


def _validate_web_visual(payload: dict[str, Any], failures: list[str]) -> None:
    visual = _section(payload, "web_visual", failures)
    _expect_bool(visual, "included_in_this_update", False, "web_visual", failures)
    _expect_bool(visual, "owner_start_required", True, "web_visual", failures)
    if visual.get("owner_start_command") != OWNER_START_COMMAND:
        failures.append("WEB VISUAL OWNER start command changed")


def _validate_protected_invariants(
    payload: dict[str, Any], failures: list[str]
) -> None:
    protected = _section(payload, "protected_invariants", failures)
    if protected.get("app_entrypoint") != "app:app":
        failures.append("protected app entrypoint must remain app:app")
    for key in (
        "broker_write",
        "trading_methods",
        "REAL_TRADING_ENABLED",
        "transfer_withdrawal_authority",
        "margin_leverage_uncovered_short_authority",
        "wp23_unlocked",
    ):
        _expect_bool(protected, key, False, "protected_invariants", failures)
    for key in (
        "cross_tenant_isolation_required",
        "exact_head_success_only",
        "squash_merge_required",
        "post_merge_regression_shield_required",
    ):
        _expect_bool(protected, key, True, "protected_invariants", failures)


def _validate_contract(payload: dict[str, Any], failures: list[str]) -> None:
    _validate_identity(payload, failures)
    _validate_delivery(payload, failures)
    _validate_milestones(payload, failures)
    _validate_cloudflare_first(payload, failures)
    _validate_cost_security(payload, failures)
    _validate_product_activation(payload, failures)
    _validate_web_visual(payload, failures)
    _validate_protected_invariants(payload, failures)


def _require_markers(
    label: str,
    text: str,
    markers: tuple[str, ...],
    failures: list[str],
) -> None:
    for marker in markers:
        if marker not in text:
            failures.append(f"{label} missing marker: {marker}")


def _validate_surfaces(failures: list[str]) -> None:
    amendment = _read(AMENDMENT, failures)
    index = _read(INDEX, failures)
    status = _read(STATUS, failures)
    readme = _read(README, failures)
    agents = _read(AGENTS, failures)
    contributing = _read(CONTRIBUTING, failures)
    master_context = _read(MASTER_CONTEXT, failures)
    governance_workflow = _read(GOVERNANCE_WORKFLOW, failures)

    _require_markers(
        "Amendment 15",
        amendment,
        (
            "**Status:** OWNER-APPROVED / EFFECTIVE ONLY WHEN ACCEPTED ON PROTECTED `main`",
            "**Product progress effect:** NONE by itself",
            UPDATE_ID,
            BRANCH,
            "CLOUDFLARE-BUILDS-VERIFIER-INTEGRATION",
            "CLOUDFLARE-RUNTIME-COMPATIBILITY",
            "CLOUDFLARE-CANDIDATE-DEPLOYMENT",
            "CLOUDFLARE-PUBLIC-CUTOVER",
            OWNER_START_COMMAND,
            "protected V9 `app:app`",
        ),
        failures,
    )
    _require_markers(
        "Amendments Index",
        index,
        (
            "Cloudflare Public Product Integrated Delivery",
            AMENDMENT.name,
            CONTRACT.name,
        ),
        failures,
    )
    _require_markers(
        "current V10 status",
        status,
        (
            "Cloudflare Public Product System Update — "
            "**HISTORICAL ACCEPTED COMPLETE / ARCHIVE-IN-PLACE**",
            "V10 Cloudflare Production Release #78",
            "TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED",
            "Amendment 18 — Timeweb-only platform consolidation",
            "CF-A",
            "CF-B",
            "CF-C",
            "CF-D",
            OWNER_START_COMMAND,
        ),
        failures,
    )
    _require_markers(
        "V10 Engineering Governance workflow",
        governance_workflow,
        (
            "Verify Cloudflare public-product integrated delivery law",
            "python scripts/check_v10_cloudflare_public_product_integrated.py",
            "if git rev-parse --verify HEAD >/dev/null 2>&1; then",
            "else\n            rm -rf .git\n          fi",
        ),
        failures,
    )
    for label, text in (
        ("README", readme),
        ("AGENTS", agents),
        ("CONTRIBUTING", contributing),
        ("Master Context", master_context),
    ):
        _require_markers(
            label,
            text,
            (UPDATE_ID, "TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED"),
            failures,
        )


def main() -> int:
    failures: list[str] = []
    _validate_contract(_load_contract(failures), failures)
    _validate_surfaces(failures)
    if failures:
        print(
            "V10 integrated Cloudflare public-product governance check failed:",
            file=sys.stderr,
        )
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("V10 integrated Cloudflare public-product governance check passed.")
    print(f"Accepted execution unit: {UPDATE_ID}")
    print(f"Historical implementation branch: {BRANCH}")
    print("Internal milestones: CF-A -> CF-B -> CF-C -> CF-D ACCEPTED COMPLETE")
    print(
        "Historical Cloudflare update remains accepted evidence; "
        "current next package: TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED"
    )
    print("Broker/Real-money authority: unchanged and fail-closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
