from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PATHS = {
    "amendment": ROOT
    / "docs/master-plan/OMNI_CIO_V10_INTEGRATED_SYSTEM_UPDATE_EXECUTION_AMENDMENT.md",
    "index": ROOT / "docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md",
    "contract": ROOT
    / "docs/architecture/V10_INTEGRATED_SYSTEM_UPDATE_EXECUTION_CONTRACT.json",
    "ledger": ROOT
    / "docs/updates/INTEGRATED_SYSTEM_UPDATE_EXECUTION_LEDGER_TEMPLATE.md",
    "wp_template": ROOT / "docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md",
    "pr_template": ROOT / ".github/pull_request_template.md",
    "issue_template": ROOT / ".github/ISSUE_TEMPLATE/v10_integrated_system_update.yml",
    "status": ROOT / "knowledge/17_V10_CURRENT_PROGRAM_STATUS.md",
    "agents": ROOT / "AGENTS.md",
    "contributing": ROOT / "CONTRIBUTING.md",
    "readme": ROOT / "README.md",
    "master_context": ROOT / "knowledge/00_PROJECT_MASTER_CONTEXT.md",
    "copilot": ROOT / ".github/copilot-instructions.md",
    "project_instructions": ROOT / "gpt/PROJECT_INSTRUCTIONS.md",
    "new_chat": ROOT / "gpt/NEW_CHAT_PROMPT.md",
    "workflow": ROOT / ".github/workflows/v10-engineering-governance.yml",
}

FOCUSED_CHANGE = "FOCUSED_CHANGE"
INTEGRATED_SYSTEM_UPDATE = "INTEGRATED_SYSTEM_UPDATE"
INTEGRATED_UPDATE_LAW = "Integrated System Update Execution Law"
INTEGRATION_READY = "INTEGRATION_READY"
HEAD_FREEZE = "HEAD FREEZE"
PRODUCT_IMPLEMENTATION_PAUSED = "PRODUCT IMPLEMENTATION PAUSED"
WEB_VISUAL_INTEGRATED = "WEB-VISUAL-INTEGRATED"
OWNER_START_REQUIRED = "OWNER START REQUIRED"
OWNER_START_COMMAND = "START V10 WEB VISUAL SYSTEM UPDATE"
BRANCH_LEDGER_BANNER = "BRANCH-LOCAL EXECUTION STATE — NOT ACCEPTED MAIN AUTHORITY"
ACCEPTED_PROGRESS_MARKER = "Accepted implementation progress is **54%**"
PROTECTED_INVARIANTS = "protected_invariants"

TRUE_RULES = {
    "integrated_update": (
        "one_branch_default",
        "one_final_pr_default",
        "internal_milestones_required",
        "member_milestones_must_follow_dependency_order",
        "internal_milestone_pass_is_branch_local_only",
        "main_progress_changes_only_after_merge_and_post_merge_acceptance",
        "next_major_update_locked_until_acceptance",
        "only_one_product_integrated_update_active_by_default",
    ),
    "publication": (
        "publish_after_integration_ready",
        "temporary_verifier_commits_forbidden",
        "one_coherent_implementation_head_default",
        "second_published_head_requires_correction_batch_base_sync_or_split_reason",
    ),
    "verification": (
        "head_freeze_after_external_verification",
        "observe_safe_findings_before_fix",
        "root_cause_before_correction",
        "blast_radius_before_correction",
        "analogous_pattern_search_before_correction",
        "coupled_producer_consumer_review_before_correction",
        "adjacent_failure_mode_review_before_correction",
        "batch_correction_default",
        "continue_on_error_to_fake_green_forbidden",
        "exact_head_success_only",
        "new_commit_invalidates_prior_final_green",
        "safety_abort_overrides_diagnostic_completeness",
    ),
    "supersession": (
        "delivery_granularity_only",
        "program_block_wp_order_preserved",
        "program_weights_preserved",
        "product_scope_preserved",
    ),
}

FALSE_PROTECTED = (
    "trading_methods",
    "REAL_TRADING_ENABLED",
    "broker_write",
    "PUBLIC_MULTI_USER_ENABLED",
    "transfer_withdrawal_authority",
    "margin_leverage_uncovered_short_authority",
    "secrets_private_data_in_github_ci_artifacts_allowed",
    "owner_only_evidence_may_be_synthesized",
)
TRUE_PROTECTED = (
    "cross_tenant_isolation_required",
    "squash_merge_required",
    "zero_unresolved_blocking_threads_required",
    "post_merge_regression_shield_required",
)
EXPECTED_SPLIT_TRIGGERS = {
    "migration_ordering",
    "security_authority_transition",
    "dependency_toolchain_boundary",
    "owner_provider_action",
    "live_temporal_evidence",
    "production_cutover",
    "real_money_authority",
    "reviewability_limit",
}

SURFACE_MARKERS = {
    "amendment": (
        f"{INTEGRATED_UPDATE_LAW} / Amendment 12",
        "Single Remote Publication Default",
        HEAD_FREEZE,
        "Systemic diagnosis and batch-correction law",
        PRODUCT_IMPLEMENTATION_PAUSED,
        OWNER_START_COMMAND,
    ),
    "index": (
        INTEGRATED_UPDATE_LAW,
        "OMNI_CIO_V10_INTEGRATED_SYSTEM_UPDATE_EXECUTION_AMENDMENT.md",
        "V10_INTEGRATED_SYSTEM_UPDATE_EXECUTION_CONTRACT.json",
    ),
    "ledger": (
        BRANCH_LEDGER_BANNER,
        "Mandatory split-trigger review",
        f"Verification batches / {HEAD_FREEZE}",
        "Root-cause inventory and correction batch",
    ),
    "wp_template": (
        "Execution unit",
        INTEGRATED_SYSTEM_UPDATE,
        INTEGRATION_READY,
        HEAD_FREEZE,
        "mandatory split review",
    ),
    "pr_template": (
        "Execution unit",
        INTEGRATION_READY,
        HEAD_FREEZE,
        "consolidated finding inventory",
        "System Update dashboard",
    ),
    "issue_template": (
        "V10 Integrated System Update Dashboard",
        BRANCH_LEDGER_BANNER,
        "Mandatory split-trigger review",
        "Verification batches / exact SHAs / consolidated findings",
    ),
    "status": (
        PRODUCT_IMPLEMENTATION_PAUSED,
        WEB_VISUAL_INTEGRATED,
        OWNER_START_REQUIRED,
        OWNER_START_COMMAND,
        ACCEPTED_PROGRESS_MARKER,
    ),
    "agents": (
        INTEGRATED_UPDATE_LAW,
        FOCUSED_CHANGE,
        INTEGRATED_SYSTEM_UPDATE,
        HEAD_FREEZE,
        OWNER_START_COMMAND,
    ),
    "contributing": (
        INTEGRATED_UPDATE_LAW,
        INTEGRATION_READY,
        HEAD_FREEZE,
        "correction batch",
    ),
    "readme": (
        WEB_VISUAL_INTEGRATED,
        PRODUCT_IMPLEMENTATION_PAUSED,
        OWNER_START_REQUIRED,
    ),
    "master_context": (
        WEB_VISUAL_INTEGRATED,
        PRODUCT_IMPLEMENTATION_PAUSED,
        OWNER_START_REQUIRED,
    ),
    "copilot": (
        INTEGRATED_UPDATE_LAW,
        INTEGRATED_SYSTEM_UPDATE,
        HEAD_FREEZE,
    ),
    "project_instructions": (
        INTEGRATED_UPDATE_LAW,
        INTEGRATED_SYSTEM_UPDATE,
        HEAD_FREEZE,
    ),
    "new_chat": (
        INTEGRATED_UPDATE_LAW,
        INTEGRATED_SYSTEM_UPDATE,
        HEAD_FREEZE,
    ),
    "workflow": (
        "python scripts/check_v10_integrated_system_update_governance.py",
        "scripts/check_v10_integrated_system_update_governance.py",
    ),
}


def fail_unless(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def read_surface(name: str, failures: list[str]) -> str:
    path = PATHS[name]
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        failures.append(f"cannot read {path.relative_to(ROOT)}: {exc}")
        return ""


def load_contract(failures: list[str]) -> dict[str, Any]:
    raw = read_surface("contract", failures)
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        failures.append(f"invalid integrated-update contract JSON: {exc}")
        return {}
    fail_unless(isinstance(payload, dict), "contract root must be an object", failures)
    return payload if isinstance(payload, dict) else {}


def mapping_section(
    payload: dict[str, Any], section_name: str, failures: list[str]
) -> dict[str, Any]:
    section = payload.get(section_name)
    fail_unless(
        isinstance(section, dict),
        f"{section_name} must be an object",
        failures,
    )
    return section if isinstance(section, dict) else {}


def validate_expected_values(
    section: dict[str, Any],
    expected_values: dict[str, Any],
    prefix: str,
    failures: list[str],
) -> None:
    for key, expected in expected_values.items():
        fail_unless(
            section.get(key) == expected,
            f"{prefix}.{key} mismatch",
            failures,
        )


def validate_boolean_values(
    section: dict[str, Any],
    keys: tuple[str, ...],
    expected: bool,
    prefix: str,
    failures: list[str],
) -> None:
    for key in keys:
        fail_unless(
            section.get(key) is expected,
            f"{prefix}.{key} must be {expected}",
            failures,
        )


def validate_authority(payload: dict[str, Any], failures: list[str]) -> None:
    authority = mapping_section(payload, "authority", failures)
    validate_expected_values(
        authority,
        {
            "product_progress_effect": "NONE",
            "runtime_authority_effect": "NONE",
            "product_implementation_paused_after_acceptance": True,
            "next_prepared_system_update": WEB_VISUAL_INTEGRATED,
            "owner_start_required": True,
            "owner_start_command": OWNER_START_COMMAND,
        },
        "authority",
        failures,
    )
    fail_unless(
        authority.get("next_prepared_member_milestones")
        == [f"WEB-VISUAL-{letter}" for letter in "ABCDEFG"],
        "WEB VISUAL member milestone order mismatch",
        failures,
    )


def validate_true_rules(payload: dict[str, Any], failures: list[str]) -> None:
    for section_name, keys in TRUE_RULES.items():
        section = mapping_section(payload, section_name, failures)
        validate_boolean_values(section, keys, True, section_name, failures)


def validate_ledgers(payload: dict[str, Any], failures: list[str]) -> None:
    ledgers = mapping_section(payload, "ledgers", failures)
    validate_expected_values(
        ledgers,
        {
            "branch_execution_ledger_required": True,
            "github_dashboard_required": True,
            "branch_execution_ledger_template": (
                "docs/updates/INTEGRATED_SYSTEM_UPDATE_EXECUTION_LEDGER_TEMPLATE.md"
            ),
            "github_dashboard_issue_template": (
                ".github/ISSUE_TEMPLATE/v10_integrated_system_update.yml"
            ),
            "working_state_banner": BRANCH_LEDGER_BANNER,
            "current_status_authority_remains": (
                "knowledge/17_V10_CURRENT_PROGRAM_STATUS.md"
            ),
        },
        "ledgers",
        failures,
    )


def validate_protected_invariants(payload: dict[str, Any], failures: list[str]) -> None:
    protected = mapping_section(payload, PROTECTED_INVARIANTS, failures)
    fail_unless(
        protected.get("app_entrypoint") == "app:app",
        "protected app entrypoint must remain app:app",
        failures,
    )
    validate_boolean_values(
        protected,
        FALSE_PROTECTED,
        False,
        PROTECTED_INVARIANTS,
        failures,
    )
    validate_boolean_values(
        protected,
        TRUE_PROTECTED,
        True,
        PROTECTED_INVARIANTS,
        failures,
    )


def validate_contract(payload: dict[str, Any], failures: list[str]) -> None:
    fail_unless(
        payload.get("schema") == "omni-cio.v10.integrated-system-update-execution.v1",
        "integrated-update contract schema mismatch",
        failures,
    )
    fail_unless(
        payload.get("status")
        == "OWNER_APPROVED_EFFECTIVE_WHEN_PRESENT_ON_ACCEPTED_MAIN",
        "integrated-update contract status mismatch",
        failures,
    )
    fail_unless(
        payload.get("execution_units") == [FOCUSED_CHANGE, INTEGRATED_SYSTEM_UPDATE],
        "integrated-update execution units mismatch",
        failures,
    )
    validate_authority(payload, failures)
    validate_true_rules(payload, failures)
    validate_ledgers(payload, failures)
    fail_unless(
        set(payload.get("split_triggers", [])) == EXPECTED_SPLIT_TRIGGERS,
        "mandatory split-trigger set mismatch",
        failures,
    )
    validate_protected_invariants(payload, failures)


def validate_surfaces(failures: list[str]) -> None:
    for name, markers in SURFACE_MARKERS.items():
        content = read_surface(name, failures)
        for marker in markers:
            fail_unless(
                marker in content,
                f"{PATHS[name].relative_to(ROOT)} missing marker: {marker}",
                failures,
            )


def main() -> int:
    failures: list[str] = []
    validate_contract(load_contract(failures), failures)
    validate_surfaces(failures)

    if failures:
        print("V10 integrated-system-update governance check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("V10 integrated-system-update governance check passed.")
    print(f"Execution units: {FOCUSED_CHANGE} / {INTEGRATED_SYSTEM_UPDATE}")
    print(f"Publication: {INTEGRATION_READY} before external verification")
    print(f"Verification: {HEAD_FREEZE} + consolidated root-cause correction batches")
    print("Accepted progress: main/post-merge only")
    print("Product implementation: PAUSED until exact OWNER START")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
