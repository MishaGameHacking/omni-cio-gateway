from __future__ import annotations

import copy

import pytest

from scripts.assess_v10_wp10_offdevice_profile import assess


def _passing_profile() -> dict:
    return {
        "schema_version": "1",
        "work_package": "WP10",
        "mode": "NONADMIN_OFFDEVICE_AUDIT",
        "status": "PASS",
        "reason_code": "OFFDEVICE_AUDIT_PASS",
        "owner_evidence_present": True,
        "target_present": True,
        "non_system_volume": True,
        "data_volume": True,
        "bitlocker_state_known": True,
        "bitlocker_fully_encrypted": True,
        "bitlocker_protection_on": True,
        "recovery_key_custody_confirmed": True,
        "target_marker_expected": True,
        "sentinel_expected": True,
        "runner_read_denied": True,
        "runner_write_denied": True,
        "runner_payload_access_granted": False,
        "private_payload_collected": False,
        "secret_value_collected": False,
        "recovery_key_value_collected": False,
    }


def test_offdevice_profile_accepts_canonical_pass() -> None:
    result = assess(_passing_profile())
    assert result["status"] == "PASS"
    assert result["offdevice_ready"] is True
    assert result["runner_private_backup_access"] is False


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("non_system_volume", False, "TARGET_IS_SYSTEM_VOLUME"),
        ("bitlocker_fully_encrypted", False, "TARGET_NOT_FULLY_ENCRYPTED"),
        ("bitlocker_protection_on", False, "BITLOCKER_PROTECTION_OFF"),
        ("recovery_key_custody_confirmed", False, "RECOVERY_KEY_CUSTODY_UNKNOWN"),
        ("runner_read_denied", False, "RUNNER_READ_NOT_DENIED"),
        ("runner_write_denied", False, "RUNNER_WRITE_NOT_DENIED"),
        ("runner_payload_access_granted", True, "RUNNER_PAYLOAD_ACCESS_ENABLED"),
        ("private_payload_collected", True, "PRIVATE_PAYLOAD_COLLECTED"),
        ("secret_value_collected", True, "SECRET_VALUE_COLLECTED"),
        ("recovery_key_value_collected", True, "RECOVERY_KEY_VALUE_COLLECTED"),
    ],
)
def test_offdevice_profile_rejects_security_regression(
    field: str, value: object, reason: str
) -> None:
    profile = copy.deepcopy(_passing_profile())
    profile[field] = value
    result = assess(profile)
    assert result["status"] == "FAIL"
    assert reason in result["blockers"]


def test_offdevice_profile_rejects_non_pass_reason() -> None:
    profile = _passing_profile()
    profile["reason_code"] = "TARGET_PREVIEW_PASS"
    result = assess(profile)
    assert result["status"] == "FAIL"
    assert "OFFDEVICE_REASON_INVALID" in result["blockers"]
