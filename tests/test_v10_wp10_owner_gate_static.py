from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WINDOWS = ROOT / "infrastructure" / "windows"


def _read(name: str) -> str:
    return (WINDOWS / name).read_text(encoding="utf-8")


def test_owner_target_preparation_never_manages_recovery_key_material() -> None:
    script = _read("prepare_wp10_offdevice_target.ps1")
    assert "[switch]$RecoveryKeyCustodyConfirmed" in script
    for forbidden in (
        "Enable-BitLocker",
        "Add-BitLockerKeyProtector",
        "Remove-BitLockerKeyProtector",
        "manage-bde",
        "Read-Host",
        "RecoveryPassword",
        "KeyProtector",
    ):
        assert forbidden not in script
    assert "Get-BitLockerVolume" in script
    assert "TARGET_NOT_FULLY_ENCRYPTED" in script
    assert "TARGET_BITLOCKER_PROTECTION_OFF" in script


def test_owner_target_acl_stays_system_admin_only_before_product_binding() -> None:
    script = _read("prepare_wp10_offdevice_target.ps1")
    assert "Resolve-LocalAccountSid" not in script
    assert "${runtimeSid}" not in script
    assert '"*S-1-5-18:(OI)(CI)F"' in script
    assert '"*S-1-5-32-544:(OI)(CI)F"' in script
    assert "(OI)(CI)M" not in script
    assert "NOT_READY_UNTIL_PRODUCT_DB_AND_BACKUP_JOB_BINDING" in script
    assert "runtime_payload_access_granted = $false" in script
    assert "runner_payload_access_granted = $false" in script
    assert "EXISTING_UNOWNED_BACKUP_ROOT_REFUSED" in script


def test_synthetic_rehearsal_is_bounded_and_phase_observable() -> None:
    script = _read("rehearse_wp10_recovery.ps1")
    assert '$PostgresWaitSeconds = 30' in script
    assert '$env:PGCONNECT_TIMEOUT = "5"' in script
    assert '$serverLog = Join-Path $root "postgres-server.log"' in script
    assert '$serverErrorLog = Join-Path $root "postgres-server-error.log"' in script
    assert '$postgres = Resolve-PostgresTool -Name "postgres"' in script
    assert '$pgCtl = Resolve-PostgresTool -Name "pg_ctl"' in script
    assert '$pgIsReady = Resolve-PostgresTool -Name "pg_isready"' in script
    assert '"--no-sync"' in script
    assert '"--no-instructions"' in script
    assert '$postgresProcess = Start-Process -FilePath $postgres' in script
    assert '-RedirectStandardOutput $serverLog' in script
    assert '-RedirectStandardError $serverErrorLog' in script
    assert '-WindowStyle Hidden -PassThru' in script
    assert '$null -ne $postgresProcess -and $postgresProcess.HasExited' in script
    assert '$postgresProcess.WaitForExit($PostgresWaitSeconds * 1000)' in script
    assert '--timeout=1 --quiet' in script
    assert 'throw "POSTGRES_START_READINESS_TIMEOUT"' in script
    assert '"--no-password"' in script
    assert "WP10_RECOVERY_PHASE=" in script
    for phase in (
        "INITIALIZE_TEMP_CLUSTER",
        "START_TEMP_CLUSTER",
        "WAIT_TEMP_CLUSTER_READY",
        "DUMP_SOURCE_DATABASE",
        "RESTORE_OFFDEVICE_BUNDLE",
        "VERIFY_RESTORE_PROBE",
        "STOP_TEMP_CLUSTER",
        "CLEAN_TEMP_STATE",
        "COMPLETE",
    ):
        assert phase in script


def test_owner_admin_rehearsal_uses_pg_ctl_windows_launcher() -> None:
    script = _read("rehearse_wp10_recovery.ps1")
    assert "postgres.exe refuses to run directly from an elevated Windows token" in script
    assert "pg_ctl is the PostgreSQL-supported Windows launcher" in script
    assert "Invoke-NativeChecked -FilePath $pgCtl -Arguments @(" in script
    assert '"start"' in script
    assert '"-D", $dataDir' in script
    assert '"-l", $serverLog' in script
    assert '"-w"' in script
    assert '"-t", "$PostgresWaitSeconds"' in script
    assert '"-o", "-h 127.0.0.1 -p $port"' in script
    assert 'throw "POSTGRES_PG_CTL_START_FAILED"' in script


def test_owner_rehearsal_stays_synthetic_and_restores_from_offdevice_copy() -> None:
    script = _read("rehearse_wp10_recovery.ps1")
    assert "OWNER_OFFDEVICE_RECOVERY_REHEARSAL" in script
    assert '"--target-dir", $offdeviceDirectory' in script
    assert '"--dbname=wp10_restore"' in script
    assert "$destinationArchive" in script
    assert "production_database_accessed = $false" in script
    assert "real_secret_values_used = $false" in script
    assert "private_portfolio_data_used = $false" in script
    assert "recovery_key_value_used = $false" in script
    assert "OFFDEVICE_SYNTHETIC_CLEANUP_FAILED" in script


def test_one_command_owner_gate_passes_only_boolean_custody_assertion() -> None:
    script = _read("complete_wp10_owner_offdevice_gate.ps1")
    assert "[switch]$RecoveryKeyCustodyConfirmed" in script
    assert '"-RecoveryKeyCustodyConfirmed"' in script
    assert '"-UsePreparedOffdeviceTarget"' in script
    assert "recovery_key_value_collected = $false" in script
    assert "secret_value_collected = $false" in script
    assert "private_portfolio_data_collected = $false" in script


def test_nonadmin_final_audit_requires_owner_restore_proof_and_denies_runner() -> None:
    script = _read("audit_wp10_offdevice_target.ps1")
    assert "OWNER_OFFDEVICE_RECOVERY_REHEARSAL" in script
    assert "OWNER_REHEARSAL_PREDATES_TARGET_APPLY" in script
    assert "catch [UnauthorizedAccessException]" in script
    assert "runner_read_denied = $true" in script
    assert "runner_write_denied = $true" in script
    assert "private_payload_collected = $false" in script
    assert "secret_value_collected = $false" in script
    assert "recovery_key_value_collected = $false"
