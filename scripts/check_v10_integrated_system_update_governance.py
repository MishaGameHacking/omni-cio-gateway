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
    "green_checkpoint_amendment": ROOT
    / "docs/master-plan/OMNI_CIO_V10_GREEN_CHECKPOINT_AND_TARGETED_CI_REPAIR_AMENDMENT.md",
    "green_checkpoint_contract": ROOT
    / "docs/architecture/V10_GREEN_CHECKPOINT_TARGETED_CI_REPAIR_CONTRACT.json",
    "ledger": ROOT / "docs/updates/INTEGRATED_SYSTEM_UPDATE_EXECUTION_LEDGER_TEMPLATE.md",
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
GREEN_CHECKPOINT_LAW = "Green Checkpoint & Targeted CI Repair Law"
CERTIFIED_GREEN = "CERTIFIED_GREEN"
RED_REPAIR_ONLY = "RED_REPAIR_ONLY"
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
    "verification": (
        "immediate_repair_on_material_red",
        "root_cause_before_correction",
        "blast_radius_before_correction",
        "analogous_pattern_search_before_correction",
        "coupled_producer_consumer_review_before_correction",
        "adjacent_failure_mode_review_before_correction",
        "targeted_recheck_before_full_recertification_preferred",
        "full_recertification_before_next_functional_checkpoint",
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

FALSE_RULES = {
    "publication": (
        "publish_after_integration_ready",
        "one_coherent_implementation_head_default",
    ),
    "verification": (
        "head_freeze_after_external_verification",
        "observe_safe_findings_before_fix",
        "batch_correction_default",
    ),
}

TRUE_PUBLICATION = (
    "checkpoint_publication_allowed_before_integration_ready",
    "temporary_verifier_commits_forbidden",
    "green_checkpoint_required_before_next_functional_checkpoint",
)

TRUE_AMENDMENT_16_SUPERSESSION = (
    "single_remote_publication_default_superseded",
    "wait_all_head_freeze_superseded",
    "batch_only_repair_default_superseded",
    "integration_ready_remains_final_whole_update_gate",
)

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
        "HEAD FREEZE",
        "Systemic diagnosis and batch-correction law",
        PRODUCT_IMPLEMENTATION_PAUSED,
        OWNER_START_COMMAND,
    ),
    "green_checkpoint_amendment": (
        f"{GREEN_CHECKPOINT_LAW} / Amendment 16",
        RED_REPAIR_ONLY,
        CERTIFIED_GREEN,
        "Same-SHA targeted rerun",
    ),
    "index": (
        INTEGRATED_UPDATE_LAW,
        GREEN_CHECKPOINT_LAW,
        "OMNI_CIO_V10_INTEGRATED_SYSTEM_UPDATE_EXECUTION_AMENDMENT.md",
        "OMNI_CIO_V10_GREEN_CHECKPOINT_AND_TARGETED_CI_REPAIR_AMENDMENT.md",
    ),
    "ledger": (
        BRANCH_LEDGER_BANNER,
        "Mandatory split-trigger review",
    ),
    "wp_template": (
        "Execution unit",
        INTEGRATED_SYSTEM_UPDATE,
        INTEGRATION_READY,
        "mandatory split review",
    ),
    "pr_template": (
        "Execution unit",
        INTEGRATION_READY,
        "System Update dashboard",
    ),
    "issue_template": (
        "V10 Integrated System Update Dashboard",
        BRANCH_LEDGER_BANNER,
        "Mandatory split-trigger review",
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
        GREEN_CHECKPOINT_LAW,
        FOCUSED_CHANGE,
        INTEGRATED_SYSTEM_UPDATE,
        RED_REPAIR_ONLY,
        CERTIFIED_GREEN,
        OWNER_START_COMMAND,
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
    "workflow": (
        "python scripts/check_v10_integrated_system_update_governance.py",
        "python scripts/check_v10_green_checkpoint_ci_repair.py",
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


def load_json_surface(name: str, failures: list[str]) -> dict[str, Any]:
    raw = read_surface(name, failures)
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        failures.append(f"invalid JSON in {PATHS[name].relative_to(ROOT)}: {exc}")
        return {}
    fail_unless(isinstance(payload, dict), f"{name} root must be an object", failures)
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


def validate_rules(payload: dict[str, Any], failures: list[str]) -> None:
    for section_name, keys in TRUE_RULES.items():
        section = mapping_section(payload, section_name, failures)
        validate_boolean_values(section, keys, True, section_name, failures)
    for section_name, keys in FALSE_RULES.items():
        section = mapping_section(payload, section_name, failures)
        validate_boolean_values(section, keys, False, section_name, failures)
    publication = mapping_section(payload, "publication", failures)
    validate_boolean_values(publication, TRUE_PUBLICATION, True, "publication", failures)
    amendment_16 = mapping_section(payload, "amendment_16_supersession", failures)
    validate_boolean_values(
        amendment_16,
        TRUE_AMENDMENT_16_SUPERSESSION,
        True,
        "amendment_16_supersession",
        failures,
    )
    validate_expected_values(
        amendment_16,
        {
            "law": "docs/master-plan/OMNI_CIO_V10_GREEN_CHECKPOINT_AND_TARGETED_CI_REPAIR_AMENDMENT.md",
            "contract": "docs/architecture/V10_GREEN_CHECKPOINT_TARGETED_CI_REPAIR_CONTRACT.json",
            "runbook": "docs/operations/V10_GREEN_CHECKPOINT_CI_RUNBOOK.md",
        },
        "amendment_16_supersession",
        failures,
    )


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
    validate_rules(payload, failures)
    validate_ledgers(payload, failures)
    fail_unless(
        set(payload.get("split_triggers", [])) == EXPECTED_SPLIT_TRIGGERS,
        "mandatory split-trigger set mismatch",
        failures,
    )
    validate_protected_invariants(payload, failures)


def validate_green_checkpoint_contract(failures: list[str]) -> None:
    payload = load_json_surface("green_checkpoint_contract", failures)
    fail_unless(
        payload.get("schema") == "omni-cio.v10.green-checkpoint-targeted-ci-repair.v1",
        "Green Checkpoint contract schema mismatch",
        failures,
    )
    core = mapping_section(payload, "core", failures)
    fail_unless(
        core.get("next_functional_checkpoint_requires_certified_green") is True,
        "Green Checkpoint must block next functional checkpoint until certified",
        failures,
    )
    fail_unless(
        core.get("must_wait_for_all_independent_jobs_before_starting_repair") is False,
        "Green Checkpoint repair must not wait for all independent jobs",
        failures,
    )


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
    validate_contract(load_json_surface("contract", failures), failures)
    validate_green_checkpoint_contract(failures)
    validate_surfaces(failures)

    if failures:
        print("V10 integrated-system-update governance check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("V10 integrated-system-update governance check passed.")
    print(f"Execution units: {FOCUSED_CHANGE} / {INTEGRATED_SYSTEM_UPDATE}")
    print(
        "Verification: Green Checkpoint immediate repair + targeted proof + "
        "full exact-SHA recertification"
    )
    print("Accepted progress: main/post-merge only")
    print("Product implementation: PAUSED until exact OWNER START")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
