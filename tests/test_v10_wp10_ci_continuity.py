from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "v10-wp10-recovery-continuity.yml"
DECISION = ROOT / "docs" / "architecture" / "V10_WP10_CI_CONTINUITY_DECISION.md"
UTILIZATION = ROOT / "docs" / "architecture" / "V10_GITHUB_PRO_UTILIZATION_CONTRACT.json"
FETCHER = ROOT / "scripts" / "fetch_v10_wp10_portable_python.py"
PS51_CHECK = ROOT / "scripts" / "check_v10_wp10_powershell51.ps1"
PYTEST_LAUNCHER = ROOT / "scripts" / "run_v10_wp10_pytest_with_target.py"


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
    assert "scripts\\bootstrap_windows_ci_python.cmd" in workflow
    assert "scripts\\fetch_v10_wp10_portable_python.py --version 3.14.6" in workflow
    assert "\\python\\python.exe" in workflow
    assert "scripts\\check_v10_wp10_powershell51.ps1" in workflow
    assert "powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File" in workflow
    assert "pytest==9.0.2" in workflow
    assert "--target" in workflow
    assert "scripts\\run_v10_wp10_pytest_with_target.py" in workflow
    assert "RUNNER_TEMP" in workflow
    assert "tests\\test_v10_wp10_recovery_contract.py" in workflow
    assert "tests\\test_v10_wp10_offdevice_audit_privilege_boundary.py" in workflow
    assert "if defined WP10_PORTABLE_ROOT" in workflow
    assert "if defined WP10_PYTEST_TARGET" in workflow
    assert workflow.count("shell: cmd") >= 7
    assert "git reset --hard HEAD" in workflow
    assert "git clean -ffdx" in workflow


def test_wp10_portable_fetcher_is_python_org_hash_checked_and_temp_scoped() -> None:
    fetcher = FETCHER.read_text(encoding="utf-8")

    assert "https://www.python.org/ftp/python/3.14.6/python-3.14.6-embed-amd64.zip" in fetcher
    assert "df901e84a896ff1ee720ad03377e0c8d8c2244fda79808aeeaff6316df1cb75c" in fetcher
    assert 'ALLOWED_HOSTS = {"www.python.org"}' in fetcher
    assert "response.geturl()" in fetcher
    assert "hashlib.sha256()" in fetcher
    assert "WP10_CONTINUITY_PYTHON_SHA256_MISMATCH" in fetcher
    assert 'if version != VERSION' in fetcher
    assert "WP10_CONTINUITY_OUTPUT_NOT_UNDER_RUNNER_TEMP" in fetcher
    assert "WP10_CONTINUITY_PYTHON_ARCHIVE_PATH_REJECTED" in fetcher
    assert 'extracted / "python.exe"' in fetcher


def test_wp10_embedded_pytest_launcher_injects_only_temp_target() -> None:
    launcher = PYTEST_LAUNCHER.read_text(encoding="utf-8")

    assert 'parser.add_argument("--target"' in launcher
    assert "target.is_dir()" in launcher
    assert "sys.path.insert(0, str(target))" in launcher
    assert "import pytest" in launcher
    assert 'pytest.main(["-q", *args.tests])' in launcher


def test_wp10_ps51_probe_is_repo_owned_and_exact() -> None:
    probe = PS51_CHECK.read_text(encoding="utf-8")

    assert "$PSVersionTable.PSVersion.Major -ne 5" in probe
    assert "System.Management.Automation.Language.Parser" in probe
    assert "run_wp10_owner_rehearsal.ps1" in probe
    assert "WP10_CONTINUITY_POWERSHELL51_PARSE=PASS" in probe


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
