from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "scripts/check_v10_green_checkpoint_ci_repair.py"
CONTRACT = ROOT / "docs/architecture/V10_GREEN_CHECKPOINT_TARGETED_CI_REPAIR_CONTRACT.json"
AMENDMENT = (
    ROOT
    / "docs/master-plan/OMNI_CIO_V10_GREEN_CHECKPOINT_AND_TARGETED_CI_REPAIR_AMENDMENT.md"
)
RUNBOOK = ROOT / "docs/operations/V10_GREEN_CHECKPOINT_CI_RUNBOOK.md"
TARGETED_WORKFLOW = ROOT / ".github/workflows/v10-targeted-repair.yml"

LIVE_GUIDANCE = (
    ROOT / "AGENTS.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / "README.md",
    ROOT / ".github/copilot-instructions.md",
    ROOT / "gpt/PROJECT_INSTRUCTIONS.md",
    ROOT / "gpt/NEW_CHAT_PROMPT.md",
    ROOT / "docs/master-plan/README.md",
    ROOT / "docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md",
    ROOT / "docs/updates/INTEGRATED_SYSTEM_UPDATE_EXECUTION_LEDGER_TEMPLATE.md",
    ROOT / "docs/updates/CLOUDFLARE_PUBLIC_PRODUCT_INTEGRATED_EXECUTION_LEDGER.md",
    ROOT / ".github/pull_request_template.md",
    ROOT / ".github/ISSUE_TEMPLATE/v10_integrated_system_update.yml",
)


class GreenCheckpointTargetedCiRepairTests(unittest.TestCase):
    def _contract(self) -> dict[str, object]:
        return json.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_repository_satisfies_green_checkpoint_governance(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(CHECK)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert completed.returncode == 0, completed.stderr or completed.stdout
        assert "Live guidance: synchronized with Amendment 16" in completed.stdout
        assert (
            "Targeted verifier: exact dispatch head + accepted frontend toolchain enforced"
            in completed.stdout
        )
        assert (
            "Post-merge release gate: exact-main Sonar success enforcement enabled"
            in completed.stdout
        )
        assert (
            "Post-merge cancelled Sonar: equivalent-tree PR provenance is fail-closed"
            in completed.stdout
        )
        assert "Next functional checkpoint requires CERTIFIED_GREEN." in completed.stdout

    def test_red_checkpoint_blocks_next_functional_checkpoint(self) -> None:
        payload = self._contract()
        core = payload["core"]
        assert isinstance(core, dict)
        assert core["next_functional_checkpoint_requires_certified_green"] is True
        assert core["known_red_may_be_carried_forward"] is False
        assert core["repair_starts_immediately_on_material_red"] is True
        assert core["must_wait_for_all_independent_jobs_before_starting_repair"] is False

    def test_same_sha_rerun_is_only_for_unchanged_source(self) -> None:
        policy = self._contract()["same_sha_rerun"]
        assert isinstance(policy, dict)
        assert policy["allowed_only_when_source_unchanged"] is True
        assert policy["specific_failed_job_preferred"] is True
        assert policy["blind_repeat_until_green_forbidden"] is True

    def test_code_change_requires_replacement_sha_and_full_certification(self) -> None:
        repair = self._contract()["code_repair"]
        assert isinstance(repair, dict)
        assert repair["changed_content_requires_replacement_sha"] is True
        assert repair["old_final_evidence_stale_after_content_change"] is True
        assert repair["targeted_proof_before_full_certification_preferred"] is True
        assert repair["full_certification_required_before_next_checkpoint"] is True
        assert repair["protected_main_force_rewrite_allowed"] is False

    def test_targeted_verifier_contract_is_fail_closed(self) -> None:
        targeted = self._contract()["targeted_verifier"]
        assert isinstance(targeted, dict)
        assert targeted["workflow"] == ".github/workflows/v10-targeted-repair.yml"
        assert targeted["expected_sha_format"] == "LOWERCASE_FULL_40_HEX"
        assert targeted["expected_sha_must_equal_dispatch_ref_head"] is True
        assert targeted["exact_checkout_verified_before_and_after_lane"] is True
        assert targeted["frontend_toolchain_authority"] == (
            "docs/architecture/V10_TOOLCHAIN_BASELINE.json"
        )
        assert targeted["frontend_dependency_lifecycle_scripts_disabled"] is True
        assert targeted["workspace_cleanup_required"] is True

    def test_sonar_new_code_is_clean_before_next_checkpoint(self) -> None:
        sonar = self._contract()["sonar_review"]
        assert isinstance(sonar, dict)
        assert sonar["quality_gate_pass_required_when_applicable"] is True
        assert sonar["new_issues_default"] == 0
        assert sonar["unresolved_new_security_hotspots"] == 0
        assert sonar["material_new_reliability_security_maintainability_findings"] == 0
        assert sonar["post_merge_exact_main_check_required"] is True
        assert sonar["post_merge_check_name"] == "SonarCloud Code Analysis"
        assert sonar["post_merge_check_app_slug"] == "sonarqubecloud"
        assert sonar["post_merge_check_success_only"] is True
        assert sonar["post_merge_cancelled_equivalent_tree_fallback_allowed"] is True
        assert (
            sonar["post_merge_cancelled_fallback_main_annotations_must_be_zero"] is True
        )
        assert sonar["post_merge_cancelled_fallback_unique_merged_pr_required"] is True
        assert sonar["post_merge_cancelled_fallback_base_must_be_main"] is True
        assert (
            sonar["post_merge_cancelled_fallback_merge_sha_must_equal_exact_main"]
            is True
        )
        assert sonar["post_merge_cancelled_fallback_tree_identity_required"] is True
        assert (
            sonar["post_merge_cancelled_fallback_pr_head_sonar_success_required"] is True
        )
        assert (
            sonar["post_merge_cancelled_fallback_pr_head_zero_findings_required"] is True
        )
        assert (
            sonar["post_merge_cancelled_fallback_current_main_recheck_required"] is True
        )
        assert sonar["post_merge_failure_or_findings_fallback_forbidden"] is True

    def test_targeted_workflow_pins_exact_requested_sha_and_toolchain(self) -> None:
        workflow = TARGETED_WORKFLOW.read_text(encoding="utf-8")
        assert "^[0-9a-f]{40}$" in workflow
        assert "DISPATCH_HEAD: ${{ github.sha }}" in workflow
        assert 'if [ "$EXPECTED_HEAD" != "$DISPATCH_HEAD" ]; then' in workflow
        assert 'git fetch --no-tags --depth=1 origin "$EXPECTED_HEAD"' in workflow
        assert 'test "$(git rev-parse HEAD)" = "$EXPECTED_HEAD"' in workflow
        assert "V10_TOOLCHAIN_BASELINE.json" in workflow
        assert "Verify exact Node and npm baseline" in workflow
        assert "$baseline.frontend.node" in workflow
        assert "$baseline.frontend.npm" in workflow
        assert "--ignore-scripts --no-audit --no-fund" in workflow

    def test_live_guidance_uses_green_checkpoint_states(self) -> None:
        for path in LIVE_GUIDANCE:
            content = path.read_text(encoding="utf-8")
            assert "RED_REPAIR_ONLY" in content, path
            assert "CERTIFIED_GREEN" in content, path

    def test_superseded_wait_all_operational_sections_are_removed(self) -> None:
        forbidden_by_path = {
            ROOT / "CONTRIBUTING.md": "## Pre-CI / HEAD FREEZE",
            ROOT / ".github/pull_request_template.md": (
                "## HEAD FREEZE / verification batch"
            ),
            ROOT / "gpt/PROJECT_INSTRUCTIONS.md": "\nHEAD FREEZE:\n",
            ROOT / "gpt/NEW_CHAT_PROMPT.md": "\nHEAD FREEZE:\n",
            ROOT / "docs/updates/INTEGRATED_SYSTEM_UPDATE_EXECUTION_LEDGER_TEMPLATE.md": (
                "## 7. Verification batches / HEAD FREEZE"
            ),
            ROOT / "docs/updates/CLOUDFLARE_PUBLIC_PRODUCT_INTEGRATED_EXECUTION_LEDGER.md": (
                "## 7. Verification batches / HEAD FREEZE"
            ),
        }
        for path, marker in forbidden_by_path.items():
            assert marker not in path.read_text(encoding="utf-8"), path

    def test_amendment_and_runbook_express_operational_flow(self) -> None:
        amendment = AMENDMENT.read_text(encoding="utf-8")
        runbook = RUNBOOK.read_text(encoding="utf-8")
        for marker in (
            "RED_REPAIR_ONLY",
            "TARGET_REPAIRED",
            "CERTIFIED_GREEN",
            "MAIN_RED_STOP",
        ):
            assert marker in amendment
        for marker in (
            "ONE CHECKPOINT",
            "RED = REPAIR ONLY",
            "TARGETED RECHECK",
            "FULL CERTIFICATION",
            "dispatch-ref head",
            "V10_TOOLCHAIN_BASELINE.json",
        ):
            assert marker in runbook


if __name__ == "__main__":
    unittest.main()
