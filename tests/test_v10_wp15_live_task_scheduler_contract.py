from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROVISIONER = (
    ROOT / "infrastructure" / "windows" / "provision_wp15_live_web_acceptance.ps1"
)
STARTER = ROOT / "infrastructure" / "windows" / "start_wp15_live_web_acceptance.ps1"
FINALIZER = ROOT / "infrastructure" / "windows" / "finalize_wp15_live_web_evidence.ps1"
AUDITOR = ROOT / "infrastructure" / "windows" / "audit_wp15_live_web_runner.ps1"


def _provisioner_text() -> str:
    return PROVISIONER.read_text(encoding="utf-8")


def _starter_text() -> str:
    return STARTER.read_text(encoding="utf-8")


def test_live_acceptance_task_can_start_and_continue_on_battery() -> None:
    text = _provisioner_text()
    settings_block = text.split("$settings = New-ScheduledTaskSettingsSet", 1)[1].split(
        "Register-ScheduledTask", 1
    )[0]

    assert "-AllowStartIfOnBatteries" in settings_block
    assert "-DontStopIfGoingOnBatteries" in settings_block


def test_live_acceptance_timeout_reports_sanitized_task_scheduler_state() -> None:
    text = _provisioner_text()
    failure_block = text.split("if (-not $readyHttp) {", 1)[1].split("\n    }\n}", 1)[0]

    assert "Get-ScheduledTaskInfo -TaskName $taskName" in failure_block
    assert "$failedTask.State" in failure_block
    assert "$failedTaskInfo.LastTaskResult" in failure_block
    assert (
        "WP15_LIVE_LOOPBACK_RUNTIME_NOT_READY; task_state={0}; last_task_result={1}"
    ) in failure_block
    assert "Get-WinEvent" not in failure_block
    assert "Get-Content" not in failure_block


def test_live_acceptance_starter_uses_temporary_batch_logon_right_only() -> None:
    text = _starter_text()

    assert '"SeBatchLogonRight"' in text
    assert '"SeDenyBatchLogonRight"' in text
    assert "LsaEnumerateAccountRights" in text
    assert "LsaAddAccountRights" in text
    assert "LsaRemoveAccountRights" in text
    assert "WP15_LIVE_RUNTIME_DENY_BATCH_LOGON_RIGHT_PRESENT" in text
    assert "$batchRightAdded = $false" in text
    assert "finally {" in text
    assert "RemoveRight($runtimeSid, $batchRight)" in text
    assert "WP15_LIVE_RUNTIME_BATCH_LOGON_RIGHT_RESTORE_FAILED" in text
    assert "SeServiceLogonRight" not in text
    assert "SeInteractiveLogonRight" not in text


def test_live_acceptance_starter_has_non_mutating_preflight() -> None:
    text = _starter_text()

    assert "[switch]$Inspect" in text
    assert 'evidence_type = "LIVE_RUNTIME_BATCH_LOGON_PREFLIGHT"' in text
    assert "batch_logon_right_present" in text
    assert "deny_batch_logon_right_present" in text
    assert "mutation_performed = $false" in text
    assert "real_secret_values_used = $false" in text
    assert "if (-not $inspectReady) { exit 73 }" in text


def test_live_acceptance_starter_preserves_exact_head_and_existing_provisioner() -> None:
    text = _starter_text()

    assert "WP15_LIVE_GIT_HEAD_MISMATCH" in text
    assert "WP15_LIVE_WORKTREE_NOT_CLEAN" in text
    assert '"Omni-CIO V10 WP6 runtime role anchor"' in text
    assert "WP15_LIVE_RUNTIME_IS_ADMINISTRATOR" in text
    assert '"provision_wp15_live_web_acceptance.ps1"' in text
    assert '"-Apply"' in text
    assert '"-ExpectedImplementationSha"' in text
    assert '"-AsJson"' in text


def test_live_acceptance_final_evidence_binds_privilege_starter() -> None:
    finalizer = FINALIZER.read_text(encoding="utf-8")
    auditor = AUDITOR.read_text(encoding="utf-8")

    assert '$starterPath = Join-Path $PSScriptRoot "start_wp15_live_web_acceptance.ps1"' in finalizer
    assert "acceptance_starter_sha256 = $starterHash" in finalizer
    assert '$starterPath = Join-Path $PSScriptRoot "start_wp15_live_web_acceptance.ps1"' in auditor
    assert "acceptance_starter_sha256 = if (Test-Path -LiteralPath $starterPath" in auditor
