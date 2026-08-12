from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROVISIONER = (
    ROOT / "infrastructure" / "windows" / "provision_wp15_live_web_acceptance.ps1"
)


def _provisioner_text() -> str:
    return PROVISIONER.read_text(encoding="utf-8")


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
