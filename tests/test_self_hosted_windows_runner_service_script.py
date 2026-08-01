from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_self_hosted_windows_runner_service.ps1"
RUNBOOK = (
    ROOT / "docs" / "operations" / "SELF_HOSTED_WINDOWS_RUNNER_SERVICE.md"
)


def test_runner_service_diagnostic_is_read_only_and_fail_closed() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    for required in (
        "Set-StrictMode -Version Latest",
        '$ErrorActionPreference = "Stop"',
        'Get-Service -Name "actions.runner.*"',
        "Get-CimInstance",
        "Win32_Service",
        "service_identity_matches = $serviceIdentityMatches",
        "service_start_mode = $serviceStartMode",
        'error_code = "RUNNER_SERVICE_WINDOWS_REQUIRED"',
        '"RUNNER_SERVICE_MISSING"',
        '"RUNNER_SERVICE_IDENTITY_MISMATCH"',
        '"RUNNER_SERVICE_QUERY_FAILED"',
        '"RUNNER_SERVICE_NOT_AUTOMATIC"',
        '"RUNNER_SERVICE_NOT_RUNNING"',
        "ConvertTo-Json -Depth 4 -Compress",
        "exit 2",
    ):
        assert required in text

    for forbidden in (
        "Start-Service",
        "Stop-Service",
        "Set-Service",
        "Remove-Service",
        "Restart-Service",
        "config.cmd",
        "--token",
        "Invoke-WebRequest",
        "Invoke-RestMethod",
        ".credentials",
    ):
        assert forbidden not in text

    assert "\nelif " not in text
    assert "\nelseif " in text


def test_runner_service_runbook_keeps_secrets_out_of_repository() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")

    assert "check_self_hosted_windows_runner_service.ps1" in text
    assert "[self-hosted, Windows, X64, omni-cio-ci]" in text
    assert "registration token" in text.lower()
    assert "must never be stored" in text
    assert "trading_methods=false" in text
    assert "TINVEST_TOKEN=" not in text
    assert "GATEWAY_API_KEY=" not in text
    assert "github_pat_" not in text
    assert "ghp_" not in text


def test_runner_service_script_parses_when_windows_powershell_is_available() -> None:
    powershell = shutil.which("powershell.exe")
    if powershell is None:
        return

    script_path = str(SCRIPT).replace("'", "''")
    command = (
        "$tokens = $null; $errors = $null; "
        f"[System.Management.Automation.Language.Parser]::ParseFile('{script_path}', "
        "[ref]$tokens, [ref]$errors) | Out-Null; "
        "if ($errors.Count -gt 0) { "
        "$errors | ForEach-Object { Write-Error $_.Message }; exit 1 }"
    )
    result = subprocess.run(
        [
            powershell,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            command,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
