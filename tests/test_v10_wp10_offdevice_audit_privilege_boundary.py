from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "infrastructure" / "windows" / "audit_wp10_offdevice_target.ps1"
PREPARE = ROOT / "infrastructure" / "windows" / "prepare_wp10_offdevice_target.ps1"


def test_nonadmin_audit_does_not_requery_privileged_bitlocker_control_plane() -> None:
    audit = AUDIT.read_text(encoding="utf-8")
    prepare = PREPARE.read_text(encoding="utf-8")

    assert "RUNNER_MUST_BE_NON_ADMIN" in audit
    assert "$bitlocker = Get-BitLockerVolume" not in audit
    assert "$bitlocker = Get-BitLockerVolume" in prepare

    assert "$result.data_volume = [bool]$evidence.data_volume" in audit
    assert (
        "$result.bitlocker_fully_encrypted = [bool]$evidence.bitlocker_fully_encrypted"
        in audit
    )
    assert (
        "$result.bitlocker_protection_on = [bool]$evidence.bitlocker_protection_on"
        in audit
    )


def test_nonadmin_audit_still_proves_runner_payload_access_is_denied() -> None:
    audit = AUDIT.read_text(encoding="utf-8")

    assert "[IO.FileMode]::Open" in audit
    assert "[IO.FileAccess]::Read" in audit
    assert "RUNNER_SENTINEL_READ_SUCCEEDED" in audit
    assert '".wp10-runner-write-probe.tmp"' in audit
    assert "[IO.FileMode]::CreateNew" in audit
    assert "[IO.FileAccess]::Write" in audit
    assert "RUNNER_WRITE_SUCCEEDED" in audit
    assert "RUNNER_OFFDEVICE_ACCESS_NOT_DENIED" in audit


def test_privileged_owner_gate_remains_fail_closed_for_bitlocker_state() -> None:
    prepare = PREPARE.read_text(encoding="utf-8")

    assert "Get-BitLockerVolume -MountPoint $mountPoint -ErrorAction Stop" in prepare
    assert '"TARGET_NOT_DATA_VOLUME"' in prepare
    assert '"TARGET_NOT_FULLY_ENCRYPTED"' in prepare
    assert '"TARGET_BITLOCKER_PROTECTION_OFF"' in prepare
    assert '"OWNER_ADMIN_REQUIRED"' in prepare
