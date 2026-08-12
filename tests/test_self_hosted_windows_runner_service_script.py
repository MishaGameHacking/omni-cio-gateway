from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_self_hosted_windows_runner_service.ps1"
RECOVERY = ROOT / "scripts" / "recover_self_hosted_windows_runner_service.ps1"
RUNBOOK = ROOT / "docs" / "operations" / "SELF_HOSTED_WINDOWS_RUNNER_SERVICE.md"
EXPECTED = "omni-ci-test-fixture"
SERVICE_NAME = f"actions.runner.owner-repo.{EXPECTED}"


def _powershell() -> str | None:
    return shutil.which("powershell.exe")


def _run(
    powershell: str,
    script: Path,
    runner_root: Path,
    *,
    apply: bool = False,
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    command = [
        powershell,
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
        "-RunnerRoot",
        str(runner_root),
        "-ExpectedRunnerName",
        EXPECTED,
        "-AsJson",
    ]
    if apply:
        command.append("-Apply")
    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return result, json.loads(result.stdout.strip())


def _write_config(root: Path) -> None:
    (root / "run.cmd").write_text("@echo off\n", encoding="utf-8")
    (root / ".runner").write_text(
        json.dumps({"agentName": EXPECTED, "ephemeral": False}), encoding="utf-8"
    )


def _set_hidden(powershell: str, path: Path, hidden: bool) -> None:
    escaped = str(path).replace("'", "''")
    op = "-bor" if hidden else "-band -bnot"
    result = subprocess.run(
        [
            powershell,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            (
                f"$i=Get-Item -LiteralPath '{escaped}' -Force; "
                f"$i.Attributes=$i.Attributes {op} [System.IO.FileAttributes]::Hidden"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_diagnostic_is_read_only_and_matches_upstream_windows_service_format() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    for required in (
        "Set-StrictMode -Version Latest",
        '$ErrorActionPreference = "Stop"',
        "[System.IO.File]::ReadAllText(",
        "[System.IO.FileInfo]::new(",
        "ConvertFrom-Json -ErrorAction Stop",
        "Get-JsonPropertyOrdinalIgnoreCase",
        "Test-ServiceExecutablePathMatches",
        'Join-Path $RunnerRoot "bin\\RunnerService.exe"',
        "$serviceDetails.PathName",
        '$expectedServiceSuffix = ".$ExpectedRunnerName"',
        "actions/runner WindowsServiceControlManager writes actions.runner.{repo-or-org}.{runner-name}",
        "$candidate.Length -le 80",
        "Get-Service -ErrorAction Stop",
        "Get-CimInstance -ClassName Win32_Service -ErrorAction Stop",
        '"SIZE_INVALID"',
        '"READ_FAILED"',
        '"JSON_INVALID"',
        '"AGENT_NAME_INVALID"',
        '"EPHEMERAL_INVALID"',
    ):
        assert required in text
    for forbidden in (
        "Start-Service",
        "Stop-Service",
        "Set-Service",
        "Remove-Service",
        "Restart-Service",
        "Invoke-WebRequest",
        "Invoke-RestMethod",
        ".credentials",
        'expectedServiceSuffix = ".$ExpectedRunnerName.service"',
        "runner_root =",
        "service_name =",
        "service_path =",
        "GitHubUrl",
        "ServerUrl",
    ):
        assert forbidden not in text


def test_recovery_is_preview_first_single_target_and_upstream_aligned() -> None:
    text = RECOVERY.read_text(encoding="utf-8")
    normalized = " ".join(text.split())
    for required in (
        "Test-DiagnosticContract",
        "Test-RecoverableDiagnosticState",
        "Test-ServiceExecutablePathMatches",
        'Join-Path $RunnerRoot "bin\\RunnerService.exe"',
        "$serviceDetails.PathName",
        '"RUNNER_SERVICE_NOT_AUTOMATIC"',
        '"RUNNER_SERVICE_NOT_RUNNING"',
        '"RUNNER_RECOVERY_BLOCKED_BY_DIAGNOSTIC"',
        '"RUNNER_RECOVERY_SERVICE_IDENTITY_MISMATCH"',
        '"RUNNER_SERVICE_RECOVERY_PREVIEW"',
        '"RUNNER_SERVICE_RECOVERY_ADMIN_REQUIRED"',
        '"RUNNER_SERVICE_RECOVERY_MUTATION_FAILED"',
        '"RUNNER_SERVICE_RECOVERY_POSTCONDITION_FAILED"',
        '$expectedServiceSuffix = ".$ExpectedRunnerName"',
        "$declaredServiceName.Length -le 80",
        "$matchingServices.Count -ne 1",
        "$matchingServiceDetails.Count -ne 1",
        "mutations_attempted = $MutationsAttempted",
    ):
        assert required in text
    assert (
        "Set-Service -Name $declaredServiceName -StartupType Automatic -ErrorAction Stop"
        in normalized
    )
    assert "Start-Service -Name $declaredServiceName -ErrorAction Stop" in normalized
    for forbidden in (
        "Stop-Service",
        "Remove-Service",
        "Restart-Service",
        "Set-Service -Name $service.Name",
        "Start-Service -Name $service.Name",
        'expectedServiceSuffix = ".$ExpectedRunnerName.service"',
        "Invoke-WebRequest",
        "Invoke-RestMethod",
        ".credentials",
    ):
        assert forbidden not in text


def test_runbook_keeps_recovery_source_controlled_and_secret_free() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")
    for required in (
        "check_self_hosted_windows_runner_service.ps1",
        "recover_self_hosted_windows_runner_service.ps1",
        "[self-hosted, Windows, X64, omni-cio-ci]",
        "registration token",
        "must never be stored",
        "trading_methods=false",
        "RunnerService.exe",
        "RUNNER_RECOVERY_BLOCKED_BY_DIAGNOSTIC",
        "RUNNER_RECOVERY_SERVICE_IDENTITY_MISMATCH",
        "RUNNER_SERVICE_RECOVERY_PREVIEW",
    ):
        assert required in text
    for forbidden in (
        "TINVEST_TOKEN=",
        "GATEWAY_API_KEY=",
        "github_pat_",
        "ghp_",
        "Set-Service -Name $service.Name",
        "Start-Service -Name $service.Name",
    ):
        assert forbidden not in text


def test_scripts_parse_on_windows_powershell() -> None:
    powershell = _powershell()
    if powershell is None:
        return
    for script in (SCRIPT, RECOVERY):
        escaped = str(script).replace("'", "''")
        command = (
            "$t=$null;$e=$null;"
            f"[System.Management.Automation.Language.Parser]::ParseFile('{escaped}',[ref]$t,[ref]$e)|Out-Null;"
            "if($e.Count){$e|%{Write-Error $_.Message};exit 1}"
        )
        result = subprocess.run(
            [powershell, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr


def test_configuration_failures_are_typed_on_windows(tmp_path: Path) -> None:
    powershell = _powershell()
    if powershell is None:
        return
    (tmp_path / "run.cmd").write_text("@echo off\n", encoding="utf-8")
    for raw, detail in (
        ("not-json", "JSON_INVALID"),
        (json.dumps({"ephemeral": False}), "AGENT_NAME_INVALID"),
        (json.dumps({"agentName": EXPECTED, "ephemeral": "false"}), "EPHEMERAL_INVALID"),
    ):
        (tmp_path / ".runner").write_text(raw, encoding="utf-8")
        result, payload = _run(powershell, SCRIPT, tmp_path)
        assert result.returncode == 2
        assert payload["error_code"] == "RUNNER_CONFIGURATION_INVALID"
        assert payload["runner_configuration_error_detail"] == detail

    (tmp_path / ".runner").write_text(
        json.dumps({"agentName": "other-runner", "ephemeral": False}), encoding="utf-8"
    )
    _, payload = _run(powershell, SCRIPT, tmp_path)
    assert payload["error_code"] == "RUNNER_CONFIGURATION_IDENTITY_MISMATCH"

    (tmp_path / ".runner").write_text(
        json.dumps({"agentName": EXPECTED, "ephemeral": True}), encoding="utf-8"
    )
    _, payload = _run(powershell, SCRIPT, tmp_path)
    assert payload["error_code"] == "RUNNER_EPHEMERAL_UNSUPPORTED"


def test_marker_format_is_bounded_exact_and_private_on_windows(tmp_path: Path) -> None:
    powershell = _powershell()
    if powershell is None:
        return
    _write_config(tmp_path)
    marker = tmp_path / ".service"

    marker.write_text(f"{SERVICE_NAME}.service", encoding="utf-8")
    result, payload = _run(powershell, SCRIPT, tmp_path)
    assert result.returncode == 2
    assert payload["error_code"] in {
        "RUNNER_SERVICE_MARKER_INVALID",
        "RUNNER_SERVICE_MARKER_IDENTITY_MISMATCH",
    }
    assert "actions.runner" not in result.stdout.lower()

    marker.write_text("x" * 1025, encoding="utf-8")
    _, payload = _run(powershell, SCRIPT, tmp_path)
    assert payload["error_code"] == "RUNNER_SERVICE_MARKER_INVALID"

    marker.write_text("actions.runner.owner-repo.other-runner", encoding="utf-8")
    _, payload = _run(powershell, SCRIPT, tmp_path)
    assert payload["error_code"] == "RUNNER_SERVICE_MARKER_IDENTITY_MISMATCH"

    marker.write_text(SERVICE_NAME, encoding="utf-8")
    result, payload = _run(powershell, SCRIPT, tmp_path)
    assert result.returncode == 2
    assert payload["error_code"] == "RUNNER_SERVICE_MISSING"
    assert payload["service_marker_valid"] is True
    assert payload["service_marker_identity_matches"] is True
    assert "actions.runner" not in result.stdout.lower()


def test_hidden_runner_markers_are_read_via_direct_dotnet_io_on_windows(tmp_path: Path) -> None:
    powershell = _powershell()
    if powershell is None:
        return
    _write_config(tmp_path)
    marker = tmp_path / ".service"
    marker.write_text(SERVICE_NAME, encoding="utf-8")
    config = tmp_path / ".runner"
    _set_hidden(powershell, config, True)
    _set_hidden(powershell, marker, True)
    try:
        result, payload = _run(powershell, SCRIPT, tmp_path)
        assert result.returncode == 2
        assert payload["error_code"] == "RUNNER_SERVICE_MISSING"
        assert payload["runner_configuration_valid"] is True
        assert payload["runner_configuration_error_detail"] is None
        assert payload["service_marker_valid"] is True
        assert payload["service_marker_identity_matches"] is True
    finally:
        _set_hidden(powershell, config, False)
        _set_hidden(powershell, marker, False)


def test_recovery_apply_blocks_nonrecoverable_states_without_mutation(tmp_path: Path) -> None:
    powershell = _powershell()
    if powershell is None:
        return
    (tmp_path / "run.cmd").write_text("@echo off\n", encoding="utf-8")
    (tmp_path / ".runner").write_text("not-json", encoding="utf-8")
    result, payload = _run(powershell, RECOVERY, tmp_path, apply=True)
    assert result.returncode == 2
    assert payload["error_code"] == "RUNNER_RECOVERY_BLOCKED_BY_DIAGNOSTIC"
    assert payload["diagnostic_error_code"] == "RUNNER_CONFIGURATION_INVALID"
    assert payload["mutations_attempted"] is False

    _write_config(tmp_path)
    result, payload = _run(powershell, RECOVERY, tmp_path, apply=True)
    assert result.returncode == 2
    assert payload["diagnostic_error_code"] == "RUNNER_SERVICE_MARKER_MISSING"
    assert payload["mutations_attempted"] is False

    (tmp_path / ".service").write_text(SERVICE_NAME, encoding="utf-8")
    result, payload = _run(powershell, RECOVERY, tmp_path, apply=True)
    assert result.returncode == 2
    assert payload["diagnostic_error_code"] == "RUNNER_SERVICE_MISSING"
    assert payload["mutations_attempted"] is False