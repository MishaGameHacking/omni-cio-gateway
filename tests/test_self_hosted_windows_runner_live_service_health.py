from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTIC = ROOT / "scripts" / "check_self_hosted_windows_runner_service.ps1"
RECOVERY = ROOT / "scripts" / "recover_self_hosted_windows_runner_service.ps1"
EXPECTED_RUNNER_NAME = "omni-cio-ci"
RUNNER_ROOT = Path(r"C:\actions-runner")


def _run_script(powershell: str, script: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            powershell,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-RunnerRoot",
            str(RUNNER_ROOT),
            "-ExpectedRunnerName",
            EXPECTED_RUNNER_NAME,
            "-AsJson",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def _assert_private_values_absent(stdout: str) -> None:
    lowered = stdout.lower()
    assert "actions.runner" not in lowered
    assert "actions-runner" not in lowered
    assert "github.com" not in lowered


def test_configured_runner_service_is_healthy_on_authoritative_runner() -> None:
    if os.environ.get("RUNNER_NAME") != EXPECTED_RUNNER_NAME:
        return

    powershell = shutil.which("powershell.exe")
    assert powershell is not None

    result = _run_script(powershell, DIAGNOSTIC)
    payload = json.loads(result.stdout.strip())
    allowed_keys = {
        "healthy",
        "error_code",
        "runner_root_exists",
        "expected_runner_name",
        "runner_configuration_present",
        "runner_configuration_valid",
        "runner_configuration_error_detail",
        "runner_configuration_identity_matches",
        "runner_ephemeral",
        "run_command_present",
        "service_marker_present",
        "service_marker_valid",
        "service_marker_identity_matches",
        "service_query_succeeded",
        "service_identity_matches",
        "service_state",
        "service_start_mode",
    }
    assert set(payload) == allowed_keys
    _assert_private_values_absent(result.stdout)
    assert result.returncode == 0, payload
    assert payload["healthy"] is True
    assert payload["error_code"] is None
    assert payload["runner_configuration_error_detail"] is None
    assert payload["runner_configuration_valid"] is True
    assert payload["runner_configuration_identity_matches"] is True
    assert payload["runner_ephemeral"] is False
    assert payload["service_marker_valid"] is True
    assert payload["service_marker_identity_matches"] is True
    assert payload["service_query_succeeded"] is True
    assert payload["service_identity_matches"] is True
    assert payload["service_state"] == "Running"
    assert payload["service_start_mode"] == "Auto"


def test_runner_recovery_preview_is_noop_when_authoritative_runner_is_healthy() -> None:
    if os.environ.get("RUNNER_NAME") != EXPECTED_RUNNER_NAME:
        return

    powershell = shutil.which("powershell.exe")
    assert powershell is not None

    result = _run_script(powershell, RECOVERY)
    payload = json.loads(result.stdout.strip())
    allowed_keys = {
        "healthy",
        "error_code",
        "diagnostic_error_code",
        "runner_configuration_error_detail",
        "expected_runner_name",
        "apply_requested",
        "recovery_action",
        "mutations_attempted",
        "mutation_stage",
        "service_state",
        "service_start_mode",
        "ready",
    }
    assert set(payload) == allowed_keys
    _assert_private_values_absent(result.stdout)
    assert result.returncode == 0, payload
    assert payload["healthy"] is True
    assert payload["ready"] is True
    assert payload["error_code"] is None
    assert payload["diagnostic_error_code"] is None
    assert payload["apply_requested"] is False
    assert payload["recovery_action"] == "NONE"
    assert payload["mutations_attempted"] is False
    assert payload["mutation_stage"] is None
    assert payload["service_state"] == "Running"
    assert payload["service_start_mode"] == "Auto"
