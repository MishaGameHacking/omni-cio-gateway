from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECOVERY = (
    ROOT
    / "infrastructure"
    / "windows"
    / "recover_wp22a_local_web_diagnostic.ps1"
)


def test_recovery_diagnostic_preserves_numeric_wp15_runtime_result_only() -> None:
    source = RECOVERY.read_text(encoding="utf-8")
    assert 'evidence_class = "LOCAL_WEB_RECOVERY_DIAGNOSTIC"' in source
    assert "Invoke-BaseProvisionerCaptured" in source
    assert "WP15_LIVE_LOOPBACK_RUNTIME_NOT_READY" in source
    assert "task_state=([A-Za-z]+)" in source
    assert "last_task_result=(-?[0-9]+)" in source
    assert '71 { "WP15_SESSION_PROBE_CONNECTION_FAILED" }' in source
    assert '76 { "WP15_SESSION_PROBE_BOOTSTRAP_FAILED" }' in source
    assert '267009 { "TASK_SCHEDULER_RUNNING" }' in source
    assert "raw_child_output_emitted = $false" in source
    assert "task_scheduler_message_emitted = $false" in source
    assert "raw_identity_emitted = $false" in source
    assert "secret_value_emitted = $false" in source
    assert "Write-Output $output" not in source
    assert ".Message" not in source


def test_recovery_diagnostic_normalizes_before_apply_and_cleans_after_failure() -> None:
    source = RECOVERY.read_text(encoding="utf-8")
    assert "$preCleanup = Invoke-BaseProvisionerCaptured -Mode Cleanup" in source
    assert "$apply = Invoke-BaseProvisionerCaptured -Mode Apply" in source
    assert "$postCleanup = Invoke-BaseProvisionerCaptured -Mode Cleanup" in source
    assert 'reason_code = "WP22A_LOCAL_WEB_RECOVERY_PASS"' in source
    assert 'reason_code = "WP22A_LOCAL_RECOVERY_DIAGNOSTIC_CAPTURED"' in source
    assert 'reason_code = "WP22A_LOCAL_RECOVERY_DIAGNOSTIC_CLEANUP_FAILED"' in source
    assert "local_web_restored = $true" in source
    assert "final_safe_state = $true" in source
