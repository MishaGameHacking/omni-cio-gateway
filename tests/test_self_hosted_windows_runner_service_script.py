from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_self_hosted_windows_runner_service.ps1"
RUNBOOK = (
    ROOT / "docs" / "operations" / "SELF_HOSTED_WINDOWS_RUNNER_SERVICE.md"
)


def _powershell() -> str | None:
    return shutil.which("powershell.exe")


def _run_diagnostic(
    powershell: str,
    runner_root: Path,
    *,
    expected_runner_name: str = "omni-ci-test-fixture",
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
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
            str(runner_root),
            "-ExpectedRunnerName",
            expected_runner_name,
            "-AsJson",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    payload = json.loads(result.stdout.strip())
    return result, payload


def _write_persistent_runner_config(runner_root: Path) -> None:
    (runner_root / "run.cmd").write_text("@echo off\n", encoding="utf-8")
    (runner_root / ".runner").write_text(
        json.dumps({"AgentName": "omni-ci-test-fixture"}),
        encoding="utf-8",
    )


def test_runner_service_diagnostic_is_read_only_and_fail_closed() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    for required in (
        "Set-StrictMode -Version Latest",
        '$ErrorActionPreference = "Stop"',
        "ValidatePattern('^[A-Za-z0-9._-]{1,64}$')",
        '$expectedServiceSuffix = ".$ExpectedRunnerName.service"',
        "$runnerConfigInfo.Length -le 65536",
        "$serviceMarkerInfo.Length -le 1024",
        "$serviceNamePattern",
        'Properties["AgentName"]',
        'Properties["Ephemeral"]',
        "ConvertFrom-Json -ErrorAction Stop",
        "[System.StringComparison]::OrdinalIgnoreCase",
        "Get-Service -ErrorAction Stop",
        "Get-CimInstance -ClassName Win32_Service -ErrorAction Stop",
        "[string]::Equals(",
        "runner_root_exists = $runnerRootExists",
        "runner_configuration_valid = $runnerConfigurationValid",
        "runner_configuration_identity_matches = $runnerConfigurationIdentityMatches",
        "runner_ephemeral = $runnerEphemeral",
        "service_marker_present = $serviceMarkerPresent",
        "service_marker_valid = $serviceMarkerValid",
        "service_marker_identity_matches = $serviceMarkerIdentityMatches",
        "service_query_succeeded = $serviceQuerySucceeded",
        "service_identity_matches = $serviceIdentityMatches",
        "service_start_mode = $serviceStartMode",
        'error_code = "RUNNER_SERVICE_WINDOWS_REQUIRED"',
        '"RUNNER_CONFIGURATION_INVALID"',
        '"RUNNER_CONFIGURATION_IDENTITY_MISMATCH"',
        '"RUNNER_EPHEMERAL_UNSUPPORTED"',
        '"RUNNER_SERVICE_MARKER_MISSING"',
        '"RUNNER_SERVICE_MARKER_INVALID"',
        '"RUNNER_SERVICE_MARKER_IDENTITY_MISMATCH"',
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
        'Get-Service -Name "actions.runner.*"',
        '-like "*.$ExpectedRunnerName.service"',
        "runner_root = $RunnerRoot",
        "service_name =",
        "service_path =",
        "PathName",
        "GitHubUrl",
        "ServerUrl",
        "WorkFolder",
        "AgentId",
        "PoolName",
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
    assert "RUNNER_EPHEMERAL_UNSUPPORTED" in text
    assert "RUNNER_SERVICE_MARKER_INVALID" in text
    assert "TINVEST_TOKEN=" not in text
    assert "GATEWAY_API_KEY=" not in text
    assert "github_pat_" not in text
    assert "ghp_" not in text


def test_runner_service_script_parses_when_windows_powershell_is_available() -> None:
    powershell = _powershell()
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


def test_runner_configuration_failures_are_typed_on_windows(
    tmp_path: Path,
) -> None:
    powershell = _powershell()
    if powershell is None:
        return

    (tmp_path / "run.cmd").write_text("@echo off\n", encoding="utf-8")

    (tmp_path / ".runner").write_text("not-json", encoding="utf-8")
    malformed, malformed_payload = _run_diagnostic(powershell, tmp_path)
    assert malformed.returncode == 2
    assert malformed_payload["error_code"] == "RUNNER_CONFIGURATION_INVALID"
    assert malformed_payload["runner_ephemeral"] is None

    (tmp_path / ".runner").write_text(
        json.dumps({"AgentName": "other-runner", "Ephemeral": False}),
        encoding="utf-8",
    )
    mismatch, mismatch_payload = _run_diagnostic(powershell, tmp_path)
    assert mismatch.returncode == 2
    assert mismatch_payload["error_code"] == (
        "RUNNER_CONFIGURATION_IDENTITY_MISMATCH"
    )
    assert mismatch_payload["runner_configuration_valid"] is True

    (tmp_path / ".runner").write_text(
        json.dumps({"AgentName": "omni-ci-test-fixture", "Ephemeral": True}),
        encoding="utf-8",
    )
    ephemeral, ephemeral_payload = _run_diagnostic(powershell, tmp_path)
    assert ephemeral.returncode == 2
    assert ephemeral_payload["error_code"] == "RUNNER_EPHEMERAL_UNSUPPORTED"
    assert ephemeral_payload["runner_ephemeral"] is True


def test_persistent_runner_configuration_requires_service_marker_on_windows(
    tmp_path: Path,
) -> None:
    powershell = _powershell()
    if powershell is None:
        return

    _write_persistent_runner_config(tmp_path)
    result, payload = _run_diagnostic(powershell, tmp_path)

    assert result.returncode == 2
    assert payload["error_code"] == "RUNNER_SERVICE_MARKER_MISSING"
    assert payload["runner_configuration_valid"] is True
    assert payload["runner_configuration_identity_matches"] is True
    assert payload["runner_ephemeral"] is False
    assert payload["service_marker_present"] is False


def test_service_marker_is_bounded_exact_and_never_emitted_on_windows(
    tmp_path: Path,
) -> None:
    powershell = _powershell()
    if powershell is None:
        return

    _write_persistent_runner_config(tmp_path)
    service_marker = tmp_path / ".service"

    service_marker.write_text(
        "actions.runner.*.omni-ci-test-fixture.service",
        encoding="utf-8",
    )
    wildcard, wildcard_payload = _run_diagnostic(powershell, tmp_path)
    assert wildcard.returncode == 2
    assert wildcard_payload["error_code"] == "RUNNER_SERVICE_MARKER_INVALID"
    assert wildcard_payload["service_marker_valid"] is False
    assert "actions.runner" not in wildcard.stdout

    service_marker.write_text("x" * 1025, encoding="utf-8")
    oversized, oversized_payload = _run_diagnostic(powershell, tmp_path)
    assert oversized.returncode == 2
    assert oversized_payload["error_code"] == "RUNNER_SERVICE_MARKER_INVALID"
    assert oversized_payload["service_marker_valid"] is False

    service_marker.write_text(
        "actions.runner.owner-repo.other-runner.service",
        encoding="utf-8",
    )
    mismatch, mismatch_payload = _run_diagnostic(powershell, tmp_path)
    assert mismatch.returncode == 2
    assert mismatch_payload["error_code"] == (
        "RUNNER_SERVICE_MARKER_IDENTITY_MISMATCH"
    )
    assert mismatch_payload["service_marker_valid"] is True
    assert mismatch_payload["service_marker_identity_matches"] is False

    service_marker.write_text(
        "actions.runner.owner-repo.omni-ci-test-fixture.service",
        encoding="utf-8",
    )
    missing, missing_payload = _run_diagnostic(powershell, tmp_path)
    assert missing.returncode == 2
    assert missing_payload["error_code"] == "RUNNER_SERVICE_MISSING"
    assert missing_payload["service_marker_valid"] is True
    assert missing_payload["service_marker_identity_matches"] is True
    assert missing_payload["service_query_succeeded"] is True
    assert "actions.runner" not in missing.stdout
