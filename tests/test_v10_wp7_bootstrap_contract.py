from __future__ import annotations

import json
from pathlib import Path

from scripts import check_v10_wp7_bootstrap_contract as wp7


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "infrastructure" / "windows" / "bootstrap-v10.ps1"
ROLLBACK = ROOT / "infrastructure" / "windows" / "rollback_wp7_bootstrap.ps1"
RUNNER_HEALTH = ROOT / "scripts" / "check_v10_wp7_runner_health.ps1"
CONTRACT = ROOT / "docs" / "architecture" / "V10_WP7_BOOTSTRAP_CONTRACT.json"
EXECUTION_CONTRACT = (
    ROOT / "docs" / "architecture" / "V10_WP7_EXECUTION_CONTRACT.md"
)
PYTHON_INSTALLER_SHA256 = (
    "14B3E9A710A3FCF0BD9B55AB6B60412BD91227563F813FC49040CABC0209E0BD"
)


def test_wp7_contract_guard_passes() -> None:
    assert wp7.validate() == []


def test_wp7_assets_exist() -> None:
    for path in (BOOTSTRAP, ROLLBACK, RUNNER_HEALTH, CONTRACT, EXECUTION_CONTRACT):
        assert path.is_file(), path


def test_bootstrap_is_preview_by_default_and_requires_explicit_apply() -> None:
    text = BOOTSTRAP.read_text(encoding="utf-8")
    assert "[switch]$Apply" in text
    assert "[switch]$Verify" in text
    assert "if (-not $Apply -and -not $Verify)" in text
    assert 'Get-Profile -Mode "PREVIEW"' in text
    assert "WP7 bootstrap -Apply requires an elevated OWNER-admin PowerShell" in text


def test_bootstrap_has_no_secret_value_parameters_or_real_authority() -> None:
    text = BOOTSTRAP.read_text(encoding="utf-8")
    param_block = text.split("param(", 1)[1].split("Set-StrictMode", 1)[0].lower()
    for marker in (
        "token",
        "secret",
        "password",
        "api_key",
        "apikey",
        "authorization",
        "connectionstring",
        "connection_string",
    ):
        assert marker not in param_block
    for marker in (
        "TINVEST_TRADING_TOKEN",
        "TINVEST_TOKEN",
        "TELEGRAM_BOT_TOKEN",
        "REAL_TRADING_ENABLED=true",
        "New-Service",
        "sc.exe create",
    ):
        assert marker.lower() not in text.lower()


def test_bootstrap_never_reconfigures_runner() -> None:
    text = BOOTSTRAP.read_text(encoding="utf-8").lower()
    assert "check_v10_wp7_runner_health.ps1" in text
    assert "check_self_hosted_windows_runner_service.ps1" not in text
    assert "config.cmd remove" not in text
    assert "config.cmd --url" not in text
    assert "svc.cmd install" not in text
    assert "svc.cmd uninstall" not in text


def test_runner_health_probe_is_privacy_safe_and_service_authoritative() -> None:
    text = RUNNER_HEALTH.read_text(encoding="utf-8")
    for required in (
        'Test-Path -LiteralPath $runCommand -PathType Leaf',
        "$env:RUNNER_NAME",
        "runner_name_matches = $runnerNameMatches",
        "$serviceNamePattern = '^actions\\.runner\\.'",
        "Get-CimInstance Win32_Service",
        "service_query_succeeded = $serviceQuerySucceeded",
        "service_identity_matches = $serviceIdentityMatches",
        "service_root_bound = $serviceRootBound",
        '$service.State -eq "Running"',
        '$service.StartMode -eq "Auto"',
        "Get-LocalGroupMember",
        "[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value",
        "process_identity_match = $processIdentityMatch",
        "runner_private_config_read = $runnerPrivateConfigRead",
        "$runnerPrivateConfigRead = $false",
        "service_non_admin = $serviceNonAdmin",
        "privacy_safe = $true",
    ):
        assert required in text
    for forbidden in (
        'Join-Path $RunnerRoot ".runner"',
        'Join-Path $RunnerRoot ".credentials"',
        'Join-Path $RunnerRoot ".credentials_rsaparams"',
        'Join-Path $RunnerRoot ".service"',
        "Get-Content -LiteralPath $runnerConfig",
        "Get-Item -LiteralPath $runnerConfig",
        "Get-Content -LiteralPath $serviceMarker",
        "Get-Item -LiteralPath $serviceMarker",
        "StartName =",
        "service_name =",
        "sid =",
        "username =",
        "hostname =",
        "Start-Service",
        "Set-Service",
        "config.cmd",
        "--token",
    ):
        assert forbidden not in text


def test_bootstrap_uses_exact_pinned_winget_resolution_for_node_and_postgres() -> None:
    text = BOOTSTRAP.read_text(encoding="utf-8")
    assert '"--id", $Id' in text
    assert '"--exact"' in text
    assert '"--version", $Version' in text
    assert '"--source", "winget"' in text
    assert '"--scope", "machine"' in text
    assert "contract.toolchain.node.winget_id" in text
    assert "contract.toolchain.postgresql.winget_id" in text
    assert "contract.toolchain.python.winget_id" not in text
    assert "latest" not in text.lower()


def test_python_machine_install_is_exact_hash_verified_and_official() -> None:
    text = BOOTSTRAP.read_text(encoding="utf-8")
    policy = json.loads(CONTRACT.read_text(encoding="utf-8"))
    python = policy["toolchain"]["python"]
    version = python["runtime_version"]
    assert python["installer_url"] == (
        f"https://www.python.org/ftp/python/{version}/python-{version}-amd64.exe"
    )
    assert python["installer_sha256"] == PYTHON_INSTALLER_SHA256
    assert python["installer_publisher"] == "Python Software Foundation"
    assert python["install_policy"] == "EXACT_VERSION_OFFICIAL_INSTALLER_SHA256_MACHINE"
    assert "winget_id" not in python
    assert "winget_version" not in python
    assert policy["bootstrap"]["public_download_hash_verification_required"] is True
    for required in (
        "Install-ExactPythonPackage",
        "Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath",
        "Get-FileHash -LiteralPath $installerPath -Algorithm SHA256",
        "Get-AuthenticodeSignature -LiteralPath $installerPath",
        '"InstallAllUsers=1"',
        '"PrependPath=0"',
        '"Include_test=0"',
    ):
        assert required in text


def test_prerequisite_discovery_prefers_machine_paths() -> None:
    text = BOOTSTRAP.read_text(encoding="utf-8")
    machine_python = '$machineCandidate = "C:\\Program Files\\Python314\\python.exe"'
    assert machine_python in text
    assert text.index(machine_python) < text.index("& py.exe -3.14")
    assert text.index("Test-Path -LiteralPath $FallbackPath") < text.index(
        "Invoke-VersionCommand -FilePath $CommandName"
    )


def test_toolchain_contract_matches_selected_baseline() -> None:
    policy = json.loads(CONTRACT.read_text(encoding="utf-8"))
    baseline = json.loads(
        (ROOT / "docs" / "architecture" / "V10_TOOLCHAIN_BASELINE.json").read_text(
            encoding="utf-8"
        )
    )
    assert (
        policy["toolchain"]["python"]["runtime_version"]
        == baseline["backend"]["python"]
    )
    assert (
        policy["toolchain"]["node"]["runtime_version"]
        == baseline["frontend"]["node"]
    )
    assert (
        policy["toolchain"]["npm"]["runtime_version"]
        == baseline["frontend"]["npm"]
    )
    assert (
        policy["toolchain"]["postgresql"]["runtime_version"]
        == baseline["database"]["tested_patch"]
    )
    assert (
        policy["toolchain"]["postgresql"]["major"]
        == baseline["database"]["postgresql_major"]
    )


def test_machine_visibility_is_part_of_the_exit_gate() -> None:
    text = BOOTSTRAP.read_text(encoding="utf-8")
    policy = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert "Test-MachineVisiblePath" in text
    assert 'return "NOT_MACHINE_VISIBLE"' in text
    assert "machine_visible" in text
    assert (
        "NOT_MACHINE_VISIBLE" in policy["profile"]["allowed_prerequisite_states"]
    )
    assert policy["exit_gate"]["prerequisites_machine_visible"] is True


def test_bootstrap_idempotence_is_a_required_runtime_postcondition() -> None:
    text = BOOTSTRAP.read_text(encoding="utf-8")
    assert "firstPassChanges" in text
    assert "secondPassChanges" in text
    assert "$secondPassChanges -eq 0" in text
    assert "WP7 bootstrap second pass was not idempotent" in text
    assert "idempotence_verified" in text


def test_repeat_apply_preserves_package_ownership_metadata() -> None:
    text = BOOTSTRAP.read_text(encoding="utf-8")
    assert "Get-ExistingInstalledPackages" in text
    assert "$existingInstalled + $installedThisRun" in text
    assert "installed_by_wp7" in text
    assert "Existing WP7 bootstrap state ownership/schema mismatch" in text


def test_bootstrap_only_defines_future_services_and_does_not_activate_them() -> None:
    text = BOOTSTRAP.read_text(encoding="utf-8")
    policy = json.loads(CONTRACT.read_text(encoding="utf-8"))
    expected_names = {
        "OmniCIO.Core",
        "OmniCIO.WebApi",
        "OmniCIO.ResearchAI",
        "OmniCIO.Execution",
    }
    assert {
        item["windows_service_name"] for item in policy["service_definitions"]
    } == expected_names
    assert all(
        item["activation"] == "FUTURE_WP_ONLY"
        for item in policy["service_definitions"]
    )
    assert "DEFINITIONS_ONLY_FUTURE_ACTIVATION" in text
    assert "Test-FutureServicesInactive" in text
    assert "New-Service" not in text
    assert "Start-Service" not in text


def test_wp8_secret_root_is_bound_but_never_mutated() -> None:
    text = BOOTSTRAP.read_text(encoding="utf-8")
    assert '$secretRoot = Join-Path $expectedRoot "secrets"' in text
    for command in ("New-Item", "Set-Content", "Remove-Item", "Set-Acl"):
        assert f"{command} -LiteralPath $secretRoot" not in text
        assert f"{command} -Path $secretRoot" not in text


def test_rollback_is_marker_guarded_and_never_uninstalls_prerequisites() -> None:
    text = ROLLBACK.read_text(encoding="utf-8")
    assert "Test-OwnedDirectory" in text
    assert "safe_to_cleanup" in text
    assert "unexpected_entries" in text
    assert "future_services_present" in text
    assert "Prerequisites will be uninstalled: NO" in text
    assert "WP6 identities/runner/secret boundary will be changed: NO" in text
    assert "winget uninstall" not in text.lower()
    assert "Remove-LocalUser" not in text


def test_privacy_profile_is_explicitly_fail_closed_against_secret_collection() -> None:
    text = BOOTSTRAP.read_text(encoding="utf-8")
    for flag in (
        "raw_usernames_collected = $false",
        "sids_emitted = $false",
        "hostnames_collected = $false",
        "addresses_collected = $false",
        "secret_values_collected = $false",
        "runner_credentials_collected = $false",
        "private_data_collected = $false",
    ):
        assert flag in text
