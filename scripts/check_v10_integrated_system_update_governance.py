from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AMENDMENT = (
    ROOT
    / "docs/master-plan/OMNI_CIO_V10_INTEGRATED_SYSTEM_UPDATE_EXECUTION_AMENDMENT.md"
)
INDEX = ROOT / "docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md"
CONTRACT = (
    ROOT / "docs/architecture/V10_INTEGRATED_SYSTEM_UPDATE_EXECUTION_CONTRACT.json"
)
LEDGER = ROOT / "docs/updates/INTEGRATED_SYSTEM_UPDATE_EXECUTION_LEDGER_TEMPLATE.md"
WP_TEMPLATE = ROOT / "docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md"
PR_TEMPLATE = ROOT / ".github/pull_request_template.md"
ISSUE_TEMPLATE = ROOT / ".github/ISSUE_TEMPLATE/v10_integrated_system_update.yml"
STATUS = ROOT / "knowledge/17_V10_CURRENT_PROGRAM_STATUS.md"
AGENTS = ROOT / "AGENTS.md"
CONTRIBUTING = ROOT / "CONTRIBUTING.md"
README = ROOT / "README.md"
MASTER_CONTEXT = ROOT / "knowledge/00_PROJECT_MASTER_CONTEXT.md"
COPILOT = ROOT / ".github/copilot-instructions.md"
PROJECT_INSTRUCTIONS = ROOT / "gpt/PROJECT_INSTRUCTIONS.md"
NEW_CHAT = ROOT / "gpt/NEW_CHAT_PROMPT.md"
WORKFLOW = ROOT / ".github/workflows/v10-engineering-governance.yml"

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


def _text(path: Path, failures: list[str]) -> str:
    if not path.is_file():
        failures.append(
            f"missing integrated-update governance file: {path.relative_to(ROOT)}"
        )
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        failures.append(f"cannot read {path.relative_to(ROOT)}: {exc}")
        return ""


def _json(path: Path, failures: list[str]) -> dict[str, Any] | None:
    raw = _text(path, failures)
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        failures.append(f"invalid JSON in {path.relative_to(ROOT)}: {exc}")
        return None
    if not isinstance(payload, dict):
        failures.append(f"JSON root must be object: {path.relative_to(ROOT)}")
        return None
    return payload


def _require_markers(
    path: Path,
    text: str,
    markers: tuple[str, ...],
    failures: list[str],
) -> None:
    for marker in markers:
        if marker not in text:
            failures.append(
                f"{path.relative_to(ROOT)} missing integrated-update marker: {marker}"
            )


def _expect_bool(
    section: dict[str, Any],
    key: str,
    expected: bool,
    label: str,
    failures: list[str],
) -> None:
    if section.get(key) is not expected:
        failures.append(f"{label}.{key} must be {expected!r}")


def _section(
    payload: dict[str, Any],
    name: str,
    failures: list[str],
) -> dict[str, Any]:
    section = payload.get(name)
    if not isinstance(section, dict):
        failures.append(f"integrated-update contract section must be object: {name}")
        return {}
    return section


def _repo_path(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def validate_contract(failures: list[str]) -> None:
    payload = _json(CONTRACT, failures)
    if payload is None:
        return

    if payload.get("schema") != "omni-cio.v10.integrated-system-update-execution.v1":
        failures.append("integrated-update contract schema mismatch")
    if (
        payload.get("status")
        != "OWNER_APPROVED_EFFECTIVE_WHEN_PRESENT_ON_ACCEPTED_MAIN"
    ):
        failures.append("integrated-update contract status mismatch")
    if payload.get("execution_units") != [
        "FOCUSED_CHANGE",
        "INTEGRATED_SYSTEM_UPDATE",
    ]:
        failures.append("integrated-update execution units mismatch")

    authority = _section(payload, "authority", failures)
    integrated = _section(payload, "integrated_update", failures)
    publication = _section(payload, "publication", failures)
    verification = _section(payload, "verification", failures)
    ledgers = _section(payload, "ledgers", failures)
    supersession = _section(payload, "supersession", failures)
    protected = _section(payload, "protected_invariants", failures)

    if authority.get("product_progress_effect") != "NONE":
        failures.append("governance amendment must not advance product progress")
    if authority.get("runtime_authority_effect") != "NONE":
        failures.append("governance amendment must not add runtime authority")
    _expect_bool(
        authority,
        "product_implementation_paused_after_acceptance",
        True,
        "authority",
        failures,
    )
    _expect_bool(authority, "owner_start_required", True, "authority", failures)
    if authority.get("next_prepared_system_update") != "WEB-VISUAL-INTEGRATED":
        failures.append("next prepared system update mismatch")
    if authority.get("owner_start_command") != "START V10 WEB VISUAL SYSTEM UPDATE":
        failures.append("OWNER start command mismatch")
    members = authority.get("next_prepared_member_milestones")
    expected_members = [f"WEB-VISUAL-{letter}" for letter in "ABCDEFG"]
    if members != expected_members:
        failures.append("WEB VISUAL member milestone order mismatch")

    for key in (
        "one_branch_default",
        "one_final_pr_default",
        "internal_milestones_required",
        "member_milestones_must_follow_dependency_order",
        "internal_milestone_pass_is_branch_local_only",
        "main_progress_changes_only_after_merge_and_post_merge_acceptance",
        "next_major_update_locked_until_acceptance",
        "only_one_product_integrated_update_active_by_default",
    ):
        _expect_bool(integrated, key, True, "integrated_update", failures)

    for key in (
        "publish_after_integration_ready",
        "temporary_verifier_commits_forbidden",
        "one_coherent_implementation_head_default",
        "second_published_head_requires_correction_batch_base_sync_or_split_reason",
    ):
        _expect_bool(publication, key, True, "publication", failures)

    for key in (
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
    ):
        _expect_bool(verification, key, True, "verification", failures)

    _expect_bool(
        ledgers,
        "branch_execution_ledger_required",
        True,
        "ledgers",
        failures,
    )
    _expect_bool(
        ledgers,
        "github_dashboard_required",
        True,
        "ledgers",
        failures,
    )
    if ledgers.get("branch_execution_ledger_template") != _repo_path(LEDGER):
        failures.append("branch Execution Ledger template path mismatch")
    if ledgers.get("github_dashboard_issue_template") != _repo_path(ISSUE_TEMPLATE):
        failures.append("GitHub System Update dashboard template path mismatch")
    if (
        ledgers.get("working_state_banner")
        != "BRANCH-LOCAL EXECUTION STATE — NOT ACCEPTED MAIN AUTHORITY"
    ):
        failures.append("working-state non-authority banner mismatch")
    if ledgers.get("current_status_authority_remains") != _repo_path(STATUS):
        failures.append("canonical current-status authority path mismatch")

    triggers = payload.get("split_triggers")
    if not isinstance(triggers, list) or set(triggers) != EXPECTED_SPLIT_TRIGGERS:
        failures.append("mandatory split-trigger set mismatch")

    for key in (
        "delivery_granularity_only",
        "program_block_wp_order_preserved",
        "program_weights_preserved",
        "product_scope_preserved",
    ):
        _expect_bool(supersession, key, True, "supersession", failures)

    if protected.get("app_entrypoint") != "app:app":
        failures.append("protected app entrypoint must remain app:app")
    for key in (
        "trading_methods",
        "REAL_TRADING_ENABLED",
        "broker_write",
        "PUBLIC_MULTI_USER_ENABLED",
        "transfer_withdrawal_authority",
        "margin_leverage_uncovered_short_authority",
        "secrets_private_data_in_github_ci_artifacts_allowed",
        "owner_only_evidence_may_be_synthesized",
    ):
        _expect_bool(protected, key, False, "protected_invariants", failures)
    for key in (
        "cross_tenant_isolation_required",
        "squash_merge_required",
        "zero_unresolved_blocking_threads_required",
        "post_merge_regression_shield_required",
    ):
        _expect_bool(protected, key, True, "protected_invariants", failures)


def validate_synchronized_surfaces(failures: list[str]) -> None:
    requirements: tuple[tuple[Path, tuple[str, ...]], ...] = (
        (
            AMENDMENT,
            (
                "Integrated System Update Execution Law / Amendment 12",
                "Single Remote Publication Default",
                "HEAD FREEZE",
                "Systemic diagnosis and batch-correction law",
                "PRODUCT IMPLEMENTATION PAUSED",
                "START V10 WEB VISUAL SYSTEM UPDATE",
            ),
        ),
        (
            INDEX,
            (
                "Integrated System Update Execution Law",
                AMENDMENT.name,
                CONTRACT.name,
            ),
        ),
        (
            LEDGER,
            (
                "BRANCH-LOCAL EXECUTION STATE — NOT ACCEPTED MAIN AUTHORITY",
                "Mandatory split-trigger review",
                "Verification batches / HEAD FREEZE",
                "Root-cause inventory and correction batch",
            ),
        ),
        (
            WP_TEMPLATE,
            (
                "Execution unit",
                "INTEGRATED_SYSTEM_UPDATE",
                "INTEGRATION_READY",
                "HEAD FREEZE",
                "mandatory split review",
            ),
        ),
        (
            PR_TEMPLATE,
            (
                "Execution unit",
                "INTEGRATION_READY",
                "HEAD FREEZE",
                "consolidated finding inventory",
                "System Update dashboard",
            ),
        ),
        (
            ISSUE_TEMPLATE,
            (
                "V10 Integrated System Update Dashboard",
                "BRANCH-LOCAL EXECUTION STATE — NOT ACCEPTED MAIN AUTHORITY",
                "Mandatory split-trigger review",
                "Verification batches / exact SHAs / consolidated findings",
            ),
        ),
        (
            STATUS,
            (
                "PRODUCT IMPLEMENTATION PAUSED",
                "WEB-VISUAL-INTEGRATED",
                "OWNER START REQUIRED",
                "START V10 WEB VISUAL SYSTEM UPDATE",
                "Accepted implementation progress is **54%**",
            ),
        ),
        (
            AGENTS,
            (
                "Integrated System Update Execution Law",
                "FOCUSED_CHANGE",
                "INTEGRATED_SYSTEM_UPDATE",
                "HEAD FREEZE",
                "START V10 WEB VISUAL SYSTEM UPDATE",
            ),
        ),
        (
            CONTRIBUTING,
            (
                "Integrated System Update Execution Law",
                "INTEGRATION_READY",
                "HEAD FREEZE",
                "correction batch",
            ),
        ),
        (
            README,
            (
                "WEB-VISUAL-INTEGRATED",
                "PRODUCT IMPLEMENTATION PAUSED",
                "OWNER START REQUIRED",
            ),
        ),
        (
            MASTER_CONTEXT,
            (
                "WEB-VISUAL-INTEGRATED",
                "PRODUCT IMPLEMENTATION PAUSED",
                "OWNER START REQUIRED",
            ),
        ),
        (
            COPILOT,
            (
                "Integrated System Update Execution Law",
                "INTEGRATED_SYSTEM_UPDATE",
                "HEAD FREEZE",
            ),
        ),
        (
            PROJECT_INSTRUCTIONS,
            (
                "Integrated System Update Execution Law",
                "INTEGRATED_SYSTEM_UPDATE",
                "HEAD FREEZE",
            ),
        ),
        (
            NEW_CHAT,
            (
                "Integrated System Update Execution Law",
                "INTEGRATED_SYSTEM_UPDATE",
                "HEAD FREEZE",
            ),
        ),
        (
            WORKFLOW,
            (
                "python scripts/check_v10_integrated_system_update_governance.py",
                "scripts/check_v10_integrated_system_update_governance.py",
            ),
        ),
    )
    for path, markers in requirements:
        text = _text(path, failures)
        if text:
            _require_markers(path, text, markers, failures)


def main() -> int:
    failures: list[str] = []
    validate_contract(failures)
    validate_synchronized_surfaces(failures)

    if failures:
        print("V10 integrated-system-update governance check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("V10 integrated-system-update governance check passed.")
    print("Execution units: FOCUSED_CHANGE / INTEGRATED_SYSTEM_UPDATE")
    print("Publication: INTEGRATION_READY before external verification")
    print("Verification: HEAD FREEZE + consolidated root-cause correction batches")
    print("Accepted progress: main/post-merge only")
    print("Product implementation: PAUSED until exact OWNER START")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
