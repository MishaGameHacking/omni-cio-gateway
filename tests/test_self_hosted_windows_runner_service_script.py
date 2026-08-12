from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_self_hosted_windows_runner_service.ps1"
RECOVERY = ROOT / "scripts" / "recover_self_hosted_windows_runner_service.ps1"
RUNBOOK = ROOT / "docs" / "operations" / "SELF_HOSTED_WINDOWS_RUNNER_SERVICE.md"


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


def _run_recovery(
    powershell: str,
    runner_root: Path,
    *,
    expected_runner_name: str = "omni-ci-test-fixture",
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
        str(RECOVERY),
        "-RunnerRoot",
        str(runner_root),
        "-ExpectedRunnerName",
        expected_runner_name,
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
    payload = json.loads(result.stdout.strip())
    return result, payload


def _write_persistent_runner_config(runner_root: Path) -> None:
    (runner_root / "run.cmd").write_text("@echo off\n", encoding="utf-8")
    (runner_root / ".runner").write_text(
        json.dumps({"agentName": "omni-ci-test-fixture", "ephemeral": False}),
        encoding="utf-8",
    )


def _set_hidden(powershell: str, path: Path, hidden: bool) -> None:
    escaped = str(path).replace("'", "''")
    operation = "-bor" if hidden else "-band -bnot"
    command = (
        f"$p='{escaped}'; $i=Get-Item -LiteralPath $p -Force; "
        f"$i.Attributes = $i.Attributes {operation} "
        "[System.IO.FileAttributes]::Hidden"
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


def test_runner_service_diagnostic_is_read_only_and_fail_closed() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    for required in (
        "Set-StrictMode -Version Latest",
        '$ErrorActionPreference = "Stop"',
        "ValidatePattern('^[A-Za-z0-9._-]{1,64}$')",
        '$expectedServiceSuffix = ".$ExpectedRunnerName.service"',
        "$serviceNamePattern",
        "[System.IO.FileInfo]::new($runnerConfigPath)",
        "[System.IO.File]::ReadAllText(",
        "[System.Text.Encoding]::UTF8",
        "ConvertFrom-Json -ErrorAction Stop",
        "Get-JsonPropertyOrdinalIgnoreCase",
        '-Name "AgentName"',
        '-Name "Ephemeral"',
        '"SIZE_INVALID"',
        '"READ_FAILED"',
        '"JSON_INVALID"',
        '"AGENT_NAME_INVALID"',
        '"EPHEMERAL_INVALID"',
        "Get-Service -ErrorAction Stop",
        "Get-CimInstance -ClassName Win32_Service -ErrorAction Stop",
        "[string]::Equals(",
        "runner_configuration_error_detail = $runnerConfigurationErrorDetail",
        "service_query_succeeded = $serviceQuerySucceeded",
        '"RUNNER_SERVICE_NOT_AUTOMATIC"',
        '"RUNNER_SERVICE_NOT_RUNNING"',
        "ConvertTo-Json -Depth 4 -Compress",
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
        "Get-Content -LiteralPath $runnerConfigPath",
        "Get-Content -LiteralPath $serviceFilePath",
        "runner_root =",
        "service_name =",
        "PathName",
        "GitHubUrl",
        "ServerUrl",
        "WorkFolder",
        "AgentId",
        "PoolName",
    ):
        assert forbidden not in text


def test_runner_service_recovery_is_single_target_and_fail_closed() -> None:
    text = RECOVERY.read_text(encoding="utf-8")
    normalized = " ".join(text.split())
    for required in (
        "Set-StrictMode -Version Latest",
        '$ErrorActionPreference = "Stop"',
        "[switch]$Apply",
        'Join-Path -Path $PSScriptRoot -ChildPath "check_self_hosted_windows_runner_service.ps1"',
        "Test-DiagnosticContract",
        "Test-RecoverableDiagnosticState",
        '"RUNNER_SERVICE_NOT_AUTOMATIC"',
        '"RUNNER_SERVICE_NOT_RUNNING"',
        '"RUNNER_RECOVERY_BLOCKED_BY_DIAGNOSTIC"',
        '"RUNNER_SERVICE_RECOVERY_PREVIEW"',
        '"RUNNER_SERVICE_RECOVERY_ADMIN_REQUIRED"',
        '"RUNNER_SERVICE_RECOVERY_MUTATION_FAILED"',
        '"RUNNER_SERVICE_RECOVERY_POSTCONDITION_FAILED"',
        "[System.IO.FileInfo]::new($serviceFilePath)",
        "[System.IO.File]::ReadAllText(",
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
        "config.cmd",
        "--token",
        "Invoke-WebRequest",
        "Invoke-RestMethod",
        ".credentials",
        "Set-Service -Name $service.Name",
        "Start-Service -Name $service.Name",
        'Get-Content -LiteralPath ".\\.service"',
        'Get-Content -LiteralPath ".service"',
        '-like "actions.runner.*"',
        "service_name =",
        "runner_root =",
        "PathName",
        "GitHubUrl",
        "ServerUrl",
    ):
        assert forbidden not in text


def test_runner_service_runbook_keeps_recovery_source_controlled_and_secret_free() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")
    for required in (
        "check_self_hosted_windows_runner_service.ps1",
        "recover_self_hosted_windows_runner_service.ps1",
        "[self-hosted, Windows, X64, omni-cio-ci]",
        "registration token",
        "must never be stored",
        "trading_methods=false",
        "RUNNER_RECOVERY_BLOCKED_BY_DIAGNOSTIC",
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


def test_runner_service_scripts_parse_when_windows_powershell_is_available() -> None:
    powershell = _powershell()
    if powershell is None:
        return
    for script in (SCRIPT, RECOVERY):
        script_path = str(script).replace("'", "''")
        command = (
            "$tokens=$null; $errors=$null; "
            f"[System.Management.Automation.Language.Parser]::ParseFile('{script_path}',"
            "[ref]$tokens,[ref]$errors)|Out-Null; "
            "if($errors.Count -gt 0){$errors|%{Write-Error $_.Message};exit 1}"
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


def test_runner_configuration_failures_are_typed_on_windows(tmp_path: Path) -> None:
    powershell = _powershell()
    if powershell is None:
        return
    (tmp_path / "run.cmd").write_text("@echo off\n", encoding="utf-8")

    cases: tuple[tuple[object, str], ...] = (
        ("not-json", "JSON_INVALID"),
        (json.dumps({"ephemeral": False}), "AGENT_NAME_INVALID"),
        (
            json.dumps({"agentName": "omni-ci-test-fixture", "ephemeral": "false"}),
            "EPHEMERAL_INVALID",
        ),
    )
    for raw, detail in cases:
        (tmp_path / ".runner").write_text(str(raw), encoding="utf-8")
        result, payload = _run_diagnostic(powershell, tmp_path)
        assert result.returncode == 2
        assert payload["error_code"] == "RUNNER_CONFIGURATION_INVALID"
        assert payload["runner_configuration_error_detail"] == detail

    (tmp_path / ".runner").write_text(
        json.dumps({"agentName": "other-runner", "ephemeral": False}), encoding="utf-8"
    )
    result, payload = _run_diagnostic(powershell, tmp_path)
    assert result.returncode == 2
    assert payload["error_code"] == "RUNNER_CONFIGURATION_IDENTITY_MISMATCH"
    assert payload["runner_configuration_valid"] is True

    (tmp_path / ".runner").write_text(
        json.dumps({"agentName": "omni-ci-test-fixture", "ephemeral": True}),
        encoding="utf-8",
    )
    result, payload = _run_diagnostic(powershell, tmp_path)
    assert result.returncode == 2
    assert payload["error_code"] == "RUNNER_EPHEMERAL_UNSUPPORTED"
    assert payload["runner_ephemeral"] is True


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


def test_service_marker_is_bounded_exact_and_never_emitted_on_windows(
    tmp_path: Path,
) -> None:
    powershell = _powershell()
    if powershell is None:
        return
    _write_persistent_runner_config(tmp_path)
    marker = tmp_path / ".service"

    marker.write_text("actions.runner.*.omni-ci-test-fixture.service", encoding="utf-8")
    result, payload = _run_diagnostic(powershell, tmp_path)
    assert result.returncode == 2
    assert payload["error_code"] == "RUNNER_SERVICE_MARKER_INVALID"
    assert "actions.runner" not in result.stdout

    marker.write_text("x" * 1025, encoding="utf-8")
    result, payload = _run_diagnostic(powershell, tmp_path)
    assert result.returncode == 2
    assert payload["error_code"] == "RUNNER_SERVICE_MARKER_INVALID"

    marker.write_text("actions.runner.owner-repo.other-runner.service", encoding="utf-8")
    result, payload = _run_diagnostic(powershell, tmp_path)
    assert result.returncode == 2
    assert payload["error_code"] == "RUNNER_SERVICE_MARKER_IDENTITY_MISMATCH"

    marker.write_text(
        "actions.runner.owner-repo.omni-ci-test-fixture.service", encoding="utf-8"
    )
    result, payload = _run_diagnostic(powershell, tmp_path)
    assert result.returncode == 2
    assert payload["error_code"] == "RUNNER_SERVICE_MISSING"
    assert payload["service_marker_valid"] is True
    assert payload["service_marker_identity_matches"] is True
    assert "actions.runner" not in result.stdout


def test_hidden_runner_markers_are_read_via_direct_dotnet_io_on_windows(
    tmp_path: Path,
) -> None:
    powershell = _powershell()
    if powershell is None:
        return
    _write_persistent_runner_config(tmp_path)
    marker = tmp_path / ".service"
    marker.write_text(
        "actions.runner.owner-repo.omni-ci-test-fixture.service", encoding="utf-8"
    )
    runner_config = tmp_path / ".runner"
    _set_hidden(powershell, runner_config, True)
    _set_hidden(powershell, marker, True)
    try:
        result, payload = _run_diagnostic(powershell, tmp_path)
        assert result.returncode == 2
        assert payload["error_code"] == "RUNNER_SERVICE_MISSING"
        assert payload["runner_configuration_valid"] is True
        assert payload["runner_configuration_error_detail"] is None
        assert payload["runner_configuration_identity_matches"] is True
        assert payload["service_marker_valid"] is True
        assert payload["service_marker_identity_matches"] is True
    finally:
        _set_hidden(powershell, runner_config, False)
        _set_hidden(powershell, marker, False)


def test_recovery_apply_blocks_invalid_configuration_without_mutation_on_windows(
    tmp_path: Path,
) -> None:
    powershell = _powershell()
    if powershell is None:
        return
    (tmp_path / "run.cmd").write_text("@echo off\n", encoding="utf-8")
    (tmp_path / ".runner").write_text("not-json", encoding="utf-8")
    result, payload = _run_recovery(powershell, tmp_path, apply=True)
    assert result.returncode == 2
    assert payload["error_code"] == "RUNNER_RECOVERY_BLOCKED_BY_DIAGNOSTIC"
    assert payload["diagnostic_error_code"] == "RUNNER_CONFIGURATION_INVALID"
    assert payload["runner_configuration_error_detail"] == "JSON_INVALID"
    assert payload["mutations_attempted"] is False
    assert payload["recovery_action"] is None


def test_recovery_apply_blocks_missing_or_unknown_service_without_mutation_on_windows(
    tmp_path: Path,
) -> None:
    powershell = _powershell()
    if powershell is None:
        return
    _write_persistent_runner_config(tmp_path)

    result, payload = _run_recovery(powershell, tmp_path, apply=True)
    assert result.returncode == 2
    assert payload["error_code"] == "RUNNER_RECOVERY_BLOCKED_BY_DIAGNOSTIC"
    assert payload["diagnostic_error_code"] == "RUNNER_SERVICE_MARKER_MISSING"
    assert payload["mutations_attempted"] is False

    (tmp_path / ".service").write_text(
        "actions.runner.owner-repo.omni-ci-test-fixture.service", encoding="utf-8"
    )
    result, payload = _run_recovery(powershell, tmp_path, apply=True)
    assert result.returncode == 2
    assert payload["error_code"] == "RUNNER_RECOVERY_BLOCKED_BY_DIAGNOSTIC"
    assert payload["diagnostic_error_code"] == "RUNNER_SERVICE_MISSING"
    assert payload["mutations_attempted"] is False
