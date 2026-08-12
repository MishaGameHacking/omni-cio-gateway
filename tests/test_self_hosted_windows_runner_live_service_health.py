from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_self_hosted_windows_runner_service.ps1"
EXPECTED_RUNNER_NAME = "omni-cio-ci"
RUNNER_ROOT = Path(r"C:\actions-runner")


def test_configured_runner_service_is_healthy_on_authoritative_runner() -> None:
    if os.environ.get("RUNNER_NAME") != EXPECTED_RUNNER_NAME:
        return

    powershell = shutil.which("powershell.exe")
    assert powershell is not None

    result = subprocess.run(
        [
            powershell,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SCRIPT),
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
