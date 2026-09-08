from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "scripts/check_v10_green_checkpoint_ci_repair.py"
CONTRACT = ROOT / "docs/architecture/V10_GREEN_CHECKPOINT_TARGETED_CI_REPAIR_CONTRACT.json"
AMENDMENT = ROOT / "docs/master-plan/OMNI_CIO_V10_GREEN_CHECKPOINT_AND_TARGETED_CI_REPAIR_AMENDMENT.md"
RUNBOOK = ROOT / "docs/operations/V10_GREEN_CHECKPOINT_CI_RUNBOOK.md"
TARGETED_WORKFLOW = ROOT / ".github/workflows/v10-targeted-repair.yml"


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

    def test_sonar_new_code_is_clean_before_next_checkpoint(self) -> None:
        sonar = self._contract()["sonar_review"]
        assert isinstance(sonar, dict)
        assert sonar["quality_gate_pass_required_when_applicable"] is True
        assert sonar["new_issues_default"] == 0
        assert sonar["unresolved_new_security_hotspots"] == 0
        assert sonar["material_new_reliability_security_maintainability_findings"] == 0

    def test_targeted_workflow_pins_exact_requested_sha(self) -> None:
        workflow = TARGETED_WORKFLOW.read_text(encoding="utf-8")
        assert "^[0-9a-fA-F]{40}$" in workflow
        assert 'git fetch --no-tags --depth=1 origin "$EXPECTED_HEAD"' in workflow
        assert 'test "$(git rev-parse HEAD)" = "$EXPECTED_HEAD"' in workflow

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
        ):
            assert marker in runbook


if __name__ == "__main__":
    unittest.main()
