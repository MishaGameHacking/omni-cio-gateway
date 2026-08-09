from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "infrastructure" / "windows" / "wp9_rehearsal_worker.ps1"
PROVISIONER = ROOT / "infrastructure" / "windows" / "provision_wp9_supervision.ps1"


def test_restart_rehearsal_uses_bounded_child_recovery() -> None:
    text = WORKER.read_text(encoding="utf-8")

    assert "[int]$MaxAttempts = 3" in text
    assert "[int]$BackoffSeconds = 60" in text
    assert "Start-SyntheticChild" in text
    assert "Wait-Process -Id $child.Id" in text
    assert 'State "RUNNING_FIRST_ATTEMPT"' in text
    assert 'State "RECOVERED"' in text
    assert 'State "RECOVERY_ATTEMPTS_EXHAUSTED"' in text
    assert "Start-Sleep -Seconds $BackoffSeconds" in text
    assert "for ($attempt = 2; $attempt -le $MaxAttempts; $attempt += 1)" in text


def test_provisioner_kills_only_reported_synthetic_process_and_waits_for_recovery() -> None:
    text = PROVISIONER.read_text(encoding="utf-8")

    assert "Stop-Process -Id $processId -Force -ErrorAction Stop" in text
    assert 'ProcessName -notmatch \'^powershell$\'' in text
    assert "[int]$state.run_count -ge 2" in text
    assert '[string]$state.state -eq "RECOVERED"' in text
    assert '-TimeoutSeconds 120' in text
    assert "WP9_RESTART_REHEARSAL_RECOVERY_TIMEOUT" in text
