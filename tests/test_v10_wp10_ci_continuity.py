from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "v10-wp10-recovery-continuity.yml"
DECISION = ROOT / "docs" / "architecture" / "V10_WP10_CI_CONTINUITY_DECISION.md"
UTILIZATION = ROOT / "docs" / "architecture" / "V10_GITHUB_PRO_UTILIZATION_CONTRACT.json"


def test_wp10_continuity_matches_no_paid_overage_program_authority() -> None:
    policy = json.loads(UTILIZATION.read_text(encoding="utf-8"))

    assert policy["billing_guard"]["paid_overage_required_for_definition_of_done"] is False
    assert policy["actions_budget"]["paid_overage_required_for_definition_of_done"] is False
    assert (
        policy["actions_budget"]["quota_exhaustion_behavior"]
        == "degrade_hosted_acceleration_without_disabling_authoritative_safety_gates"
    )


def test_wp10_continuity_workflow_is_self_hosted_and_fail_closed() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "runs-on: [self-hosted, Windows, X64, omni-cio-ci]" in workflow
    assert "github.event.pull_request.head.repo.full_name == github.repository" in workflow
    assert "permissions:\n  contents: read" in workflow
    assert "${{ secrets." not in workflow
    assert "C:\\Program Files\\Python314\\python.exe" in workflow
    assert 'Get-Command "py.exe"' in workflow
    assert "sys.executable" in workflow
    assert "USERPROFILE" in workflow
    assert "LOCALAPPDATA" in workflow
    assert "APPDATA" in workflow
    assert '"3.14.6"' in workflow
    assert "-m venv" in workflow
    assert "RUNNER_TEMP" in workflow
    assert "$PSVersionTable.PSVersion.Major -ne 5" in workflow
    assert "System.Management.Automation.Language.Parser" in workflow
    assert "tests/test_v10_wp10_recovery_contract.py" in workflow
    assert "tests/test_v10_wp10_offdevice_audit_privilege_boundary.py" in workflow
    assert "git reset --hard HEAD" in workflow
    assert "git clean -ffdx" in workflow


def test_wp10_continuity_decision_keeps_hosted_lane_and_safety_gates() -> None:
    decision = DECISION.read_text(encoding="utf-8")

    assert "DEGRADED_HOSTED_ACCELERATION" in decision
    assert "does **not** claim to turn the persistent Lenovo host into a disposable" in decision
    assert "V10 authoritative merge gate` PASS remains mandatory" in decision
    assert "WP10 Recovery Audit PASS remains mandatory" in decision
    assert "WP10 Off-Device Audit PASS remains mandatory" in decision
    assert "trading_methods=false" in decision
    assert "REAL_TRADING_ENABLED=false" in decision
    assert "no direct-main push" in decision
    assert "Post-merge Regression Shield remains required" in decision
