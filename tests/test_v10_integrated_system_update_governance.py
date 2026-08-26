from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/check_v10_integrated_system_update_governance.py"
CONTRACT = (
    ROOT / "docs/architecture/V10_INTEGRATED_SYSTEM_UPDATE_EXECUTION_CONTRACT.json"
)
LEDGER = ROOT / "docs/updates/INTEGRATED_SYSTEM_UPDATE_EXECUTION_LEDGER_TEMPLATE.md"
ISSUE_TEMPLATE = ROOT / ".github/ISSUE_TEMPLATE/v10_integrated_system_update.yml"
STATUS = ROOT / "knowledge/17_V10_CURRENT_PROGRAM_STATUS.md"


def _contract() -> dict[str, object]:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_current_repository_satisfies_integrated_update_governance() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert (
        "Execution units: FOCUSED_CHANGE / INTEGRATED_SYSTEM_UPDATE"
        in completed.stdout
    )
    assert "Verification: HEAD FREEZE" in completed.stdout
    assert (
        "Product implementation: PAUSED until exact OWNER START"
        in completed.stdout
    )


def test_contract_preserves_execution_order_and_single_acceptance_boundary() -> None:
    payload = _contract()
    assert payload["execution_units"] == [
        "FOCUSED_CHANGE",
        "INTEGRATED_SYSTEM_UPDATE",
    ]

    integrated = payload["integrated_update"]
    assert isinstance(integrated, dict)
    assert integrated["one_branch_default"] is True
    assert integrated["one_final_pr_default"] is True
    assert integrated["internal_milestones_required"] is True
    assert integrated["member_milestones_must_follow_dependency_order"] is True
    assert integrated["internal_milestone_pass_is_branch_local_only"] is True
    assert (
        integrated["main_progress_changes_only_after_merge_and_post_merge_acceptance"]
        is True
    )
    assert integrated["next_major_update_locked_until_acceptance"] is True


def test_publication_and_verification_are_batch_oriented_not_fake_green() -> None:
    payload = _contract()
    publication = payload["publication"]
    verification = payload["verification"]
    assert isinstance(publication, dict)
    assert isinstance(verification, dict)

    assert publication["publish_after_integration_ready"] is True
    assert publication["temporary_verifier_commits_forbidden"] is True
    assert publication["one_coherent_implementation_head_default"] is True

    assert verification["head_freeze_after_external_verification"] is True
    assert verification["observe_safe_findings_before_fix"] is True
    assert verification["root_cause_before_correction"] is True
    assert verification["batch_correction_default"] is True
    assert verification["continue_on_error_to_fake_green_forbidden"] is True
    assert verification["exact_head_success_only"] is True
    assert verification["new_commit_invalidates_prior_final_green"] is True
    assert verification["safety_abort_overrides_diagnostic_completeness"] is True


def test_split_triggers_cover_real_acceptance_boundaries() -> None:
    payload = _contract()
    assert set(payload["split_triggers"]) == {
        "migration_ordering",
        "security_authority_transition",
        "dependency_toolchain_boundary",
        "owner_provider_action",
        "live_temporal_evidence",
        "production_cutover",
        "real_money_authority",
        "reviewability_limit",
    }


def test_working_ledgers_cannot_become_competing_current_status() -> None:
    payload = _contract()
    ledgers = payload["ledgers"]
    assert isinstance(ledgers, dict)
    assert ledgers["branch_execution_ledger_required"] is True
    assert ledgers["github_dashboard_required"] is True
    assert ledgers["current_status_authority_remains"] == (
        "knowledge/17_V10_CURRENT_PROGRAM_STATUS.md"
    )
    banner = "BRANCH-LOCAL EXECUTION STATE — NOT ACCEPTED MAIN AUTHORITY"
    assert ledgers["working_state_banner"] == banner
    assert banner in LEDGER.read_text(encoding="utf-8")
    assert banner in ISSUE_TEMPLATE.read_text(encoding="utf-8")


def test_governance_acceptance_pauses_product_until_exact_owner_start() -> None:
    payload = _contract()
    authority = payload["authority"]
    assert isinstance(authority, dict)
    assert authority["product_progress_effect"] == "NONE"
    assert authority["runtime_authority_effect"] == "NONE"
    assert authority["product_implementation_paused_after_acceptance"] is True
    assert authority["next_prepared_system_update"] == "WEB-VISUAL-INTEGRATED"
    assert authority["next_prepared_member_milestones"] == [
        "WEB-VISUAL-A",
        "WEB-VISUAL-B",
        "WEB-VISUAL-C",
        "WEB-VISUAL-D",
        "WEB-VISUAL-E",
        "WEB-VISUAL-F",
        "WEB-VISUAL-G",
    ]
    assert authority["owner_start_required"] is True
    assert authority["owner_start_command"] == "START V10 WEB VISUAL SYSTEM UPDATE"

    status = STATUS.read_text(encoding="utf-8")
    assert "PRODUCT IMPLEMENTATION PAUSED" in status
    assert "WEB-VISUAL-INTEGRATED" in status
    assert "OWNER START REQUIRED" in status
    assert "Accepted implementation progress is **54%**" in status


def test_protected_money_public_and_tenant_invariants_remain_fail_closed() -> None:
    protected = _contract()["protected_invariants"]
    assert isinstance(protected, dict)
    assert protected["app_entrypoint"] == "app:app"
    assert protected["trading_methods"] is False
    assert protected["REAL_TRADING_ENABLED"] is False
    assert protected["broker_write"] is False
    assert protected["PUBLIC_MULTI_USER_ENABLED"] is False
    assert protected["transfer_withdrawal_authority"] is False
    assert protected["margin_leverage_uncovered_short_authority"] is False
    assert protected["cross_tenant_isolation_required"] is True
    assert protected["secrets_private_data_in_github_ci_artifacts_allowed"] is False
    assert protected["squash_merge_required"] is True
    assert protected["zero_unresolved_blocking_threads_required"] is True
    assert protected["post_merge_regression_shield_required"] is True
    assert protected["owner_only_evidence_may_be_synthesized"] is False
