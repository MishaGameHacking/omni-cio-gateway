from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WINDOWS = ROOT / "infrastructure" / "windows"


def _text(name: str) -> str:
    return (WINDOWS / name).read_text(encoding="utf-8")


def test_wp10_offdevice_scripts_never_contain_destructive_disk_commands() -> None:
    combined = "\n".join(
        _text(name)
        for name in (
            "prepare_wp10_offdevice_target.ps1",
            "audit_wp10_offdevice_target.ps1",
            "rehearse_wp10_recovery.ps1",
            "run_wp10_backup.ps1",
            "run_wp10_owner_gate.ps1",
        )
    ).lower()
    forbidden = (
        "format-volume",
        "format.com",
        "clear-disk",
        "initialize-disk",
        "new-partition",
        "remove-partition",
        "resize-partition",
        "diskpart",
    )
    for token in forbidden:
        assert token not in combined


def test_wp10_backup_runner_has_no_password_or_token_parameter() -> None:
    runner = _text("run_wp10_backup.ps1").lower()
    parameter_region = runner.split("set-strictmode", 1)[0]
    assert "$password" not in parameter_region
    assert "$token" not in parameter_region
    assert "$secret" not in parameter_region
    assert "--no-password" in runner
    assert "pgpassfile" in runner


def test_wp10_private_state_backup_cannot_succeed_local_only() -> None:
    runner = _text("run_wp10_backup.ps1")
    assert "[switch]$UsePreparedOffdeviceTarget" in runner
    assert "PRIVATE_STATE_BACKUP_REQUIRES_OFFDEVICE_TARGET" in runner
    assert "OFFDEVICE_COPY_REQUIRED_BUT_NOT_PROVEN" in runner
    assert '"copy"' in runner
    assert '"prune"' in runner
    assert "OFFDEVICE_POST_RETENTION_VERIFY_FAILED" in runner


def test_wp10_owner_preparation_requires_existing_encrypted_data_volume() -> None:
    script = _text("prepare_wp10_offdevice_target.ps1")
    assert "Get-BitLockerVolume" in script
    assert 'VolumeStatus -ne "FullyEncrypted"' in script
    assert 'ProtectionStatus -ne "On"' in script
    assert 'VolumeType -ne "Data"' in script
    assert "SYSTEM_VOLUME_FORBIDDEN" in script
    assert "RecoveryKeyCustodyConfirmed" in script


def test_wp10_owner_rehearsal_revalidates_target_and_restores_from_offdevice() -> None:
    script = _text("rehearse_wp10_recovery.ps1")
    assert "UsePreparedOffdeviceTarget" in script
    assert "Get-PreparedOffdeviceTarget" in script
    assert "Get-BitLockerVolume" in script
    assert 'VolumeStatus -ne "FullyEncrypted"' in script
    assert 'ProtectionStatus -ne "On"' in script
    assert "BACKUP_RUNNER_OFFDEVICE_CYCLE_NOT_PASS" in script
    assert '"VERIFY_OWNER_OFFDEVICE"' in script
    assert "$restoreArchive = Join-Path" in script
    assert '"OWNER_OFFDEVICE_BACKUP_CORRUPTION_RESTORE_PASS"' in script
    assert "Remove-Item -LiteralPath $restoreArchive" not in script


def test_wp10_owner_gate_writes_only_current_sanitized_local_rehearsal() -> None:
    script = _text("run_wp10_owner_gate.ps1")
    assert "owner-rehearsal.sanitized.local.json" in script
    assert "Remove-Item -LiteralPath $OwnerRehearsalPath" in script
    assert "implementation_fingerprint" in script
    assert "owner_gate_script_sha256" in script
    assert "target_identity_emitted = $false" in script
    assert "recovery_key_value_collected = $false" in script
    assert "TargetMountPoint $TargetMountPoint" in script
    assert "Write-Output $TargetMountPoint" not in script


def test_wp10_nonadmin_audit_does_not_require_live_bitlocker_privilege() -> None:
    script = _text("audit_wp10_offdevice_target.ps1")
    assert "Get-BitLockerVolume" not in script
    assert "NONADMIN_AUDIT_REQUIRED" in script
    assert "RUNNER_READ_ACCESS_NOT_DENIED" in script
    assert "RUNNER_WRITE_ACCESS_NOT_DENIED" in script


def test_wp10_schedule_is_sealed_and_within_rpo() -> None:
    schedule = json.loads((WINDOWS / "wp10_backup_schedule.json").read_text(encoding="utf-8"))
    contract = json.loads(
        (ROOT / "docs" / "architecture" / "V10_WP10_RECOVERY_CONTRACT.json").read_text(
            encoding="utf-8"
        )
    )
    assert schedule["cadence_minutes"] <= contract["recovery_objectives"]["rpo_minutes"]
    assert schedule["enabled_before_product_binding"] is False
    assert schedule["production_database_binding"] == "NOT_READY_UNTIL_WP13"
    assert schedule["production_task_identity_binding"] == "NOT_READY_UNTIL_WP13_WP14"
    assert schedule["production_backup_class"] == "POSTGRES_LOGICAL_PRIVATE_STATE"
    assert schedule["use_prepared_offdevice_target"] is True
    assert schedule["successful_cycle_requires_offdevice_copy"] is True
    assert schedule["successful_cycle_requires_retention"] is True
    assert contract["automation"]["production_cycle_requires_offdevice_copy"] is True
    assert contract["automation"]["production_cycle_requires_retention"] is True
    assert schedule["credentials_in_task_definition"] is False
    assert schedule["private_payload_in_task_definition"] is False


def test_wp10_rehearsal_uses_separate_source_and_restore_databases() -> None:
    script = _text("rehearse_wp10_recovery.ps1")
    assert '"wp10_source"' in script
    assert '"wp10_restore"' in script
    assert "CORRUPT_ARCHIVE_ACCEPTED" in script
    assert "RESTORE_PROBE_MISMATCH" in script
    assert "14400000" in script
