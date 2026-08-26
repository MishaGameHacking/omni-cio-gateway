from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest


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


class IntegratedSystemUpdateGovernanceTests(unittest.TestCase):
    def test_current_repository_satisfies_integrated_update_governance(self) -> None:
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

    def test_contract_preserves_execution_order_and_acceptance_boundary(self) -> None:
        payload = _contract()
        assert payload["execution_units"] == [
            "FOCUSED_CHANGE",
            "INTEGRATED_SYSTEM_UPDATE",
        ]

        integrated = payload["integrated_update"]
        assert isinstance(integrated, dict)
        required_true = {
            "one_branch_default",
            "one_final_pr_default",
            "internal_milestones_required",
            "member_milestones_must_follow_dependency_order",
            "internal_milestone_pass_is_branch_local_only",
            "main_progress_changes_only_after_merge_and_post_merge_acceptance",
            "next_major_update_locked_until_acceptance",
        }
        assert all(integrated[key] is True for key in required_true)

    def test_publication_and_verification_are_batch_oriented(self) -> None:
        payload = _contract()
        publication = payload["publication"]
        verification = payload["verification"]
        assert isinstance(publication, dict)
        assert isinstance(verification, dict)

        assert all(
            publication[key] is True
            for key in (
                "publish_after_integration_ready",
                "temporary_verifier_commits_forbidden",
                "one_coherent_implementation_head_default",
            )
        )
        assert all(
            verification[key] is True
            for key in (
                "head_freeze_after_external_verification",
                "observe_safe_findings_before_fix",
                "root_cause_before_correction",
                "batch_correction_default",
                "continue_on_error_to_fake_green_forbidden",
                "exact_head_success_only",
                "new_commit_invalidates_prior_final_green",
                "safety_abort_overrides_diagnostic_completeness",
            )
        )

    def test_split_triggers_cover_real_acceptance_boundaries(self) -> None:
        assert set(_contract()["split_triggers"]) == {
            "migration_ordering",
            "security_authority_transition",
            "dependency_toolchain_boundary",
            "owner_provider_action",
            "live_temporal_evidence",
            "production_cutover",
            "real_money_authority",
            "reviewability_limit",
        }

    def test_working_ledgers_cannot_compete_with_current_status(self) -> None:
        ledgers = _contract()["ledgers"]
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

    def test_governance_acceptance_pauses_product_until_owner_start(self) -> None:
        authority = _contract()["authority"]
        assert isinstance(authority, dict)
        assert authority["product_progress_effect"] == "NONE"
        assert authority["runtime_authority_effect"] == "NONE"
        assert authority["product_implementation_paused_after_acceptance"] is True
        assert authority["next_prepared_system_update"] == "WEB-VISUAL-INTEGRATED"
        assert authority["next_prepared_member_milestones"] == [
            f"WEB-VISUAL-{letter}" for letter in "ABCDEFG"
        ]
        assert authority["owner_start_required"] is True
        assert authority["owner_start_command"] == "START V10 WEB VISUAL SYSTEM UPDATE"

        status = STATUS.read_text(encoding="utf-8")
        for marker in (
            "PRODUCT IMPLEMENTATION PAUSED",
            "WEB-VISUAL-INTEGRATED",
            "OWNER START REQUIRED",
            "Accepted implementation progress is **54%**",
        ):
            assert marker in status

    def test_protected_authority_invariants_remain_fail_closed(self) -> None:
        protected = _contract()["protected_invariants"]
        assert isinstance(protected, dict)
        assert protected["app_entrypoint"] == "app:app"
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
            assert protected[key] is False
        for key in (
            "cross_tenant_isolation_required",
            "squash_merge_required",
            "zero_unresolved_blocking_threads_required",
            "post_merge_regression_shield_required",
        ):
            assert protected[key] is True


if __name__ == "__main__":
    unittest.main()
