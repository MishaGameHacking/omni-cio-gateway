from __future__ import annotations

import copy

import pytest

from scripts.assess_v10_wp10_recovery_profile import assess


def _contract() -> dict:
    return {
        "recovery_objectives": {"rto_minutes": 240},
        "postgresql": {"production_database_binding": "NOT_READY_UNTIL_WP13"},
        "off_device": {
            "production_backup_writer_identity": (
                "NOT_READY_UNTIL_PRODUCT_DB_AND_BACKUP_JOB_BINDING"
            )
        },
    }


def _passing_profile() -> dict:
    return {
        "schema_version": "1",
        "work_package": "WP10",
        "mode": "SYNTHETIC_RECOVERY_REHEARSAL",
        "status": "PASS",
        "reason_code": "RECOVERY_REHEARSAL_PASS",
        "postgres_version_class": "18.4",
        "bundle_integrity_pass": True,
        "corruption_rejected": True,
        "offdevice_copy_pass": True,
        "restore_probe_pass": True,
        "offdevice_cleanup_pass": True,
        "source_restore_separate": True,
        "temporary_state_cleaned": True,
        "owner_target_used": False,
        "real_secret_values_used": False,
        "private_portfolio_data_used": False,
        "account_identifiers_used": False,
        "production_database_accessed": False,
        "offdevice_mode": "SYNTHETIC_TEMP_ONLY",
        "duration_ms": 10_000,
    }


def test_recovery_profile_accepts_complete_synthetic_proof() -> None:
    result = assess(_passing_profile(), _contract())
    assert result["status"] == "PASS"
    assert result["synthetic_recovery_ready"] is True
    assert result["production_database_binding"] == "NOT_READY_UNTIL_WP13"
    assert (
        result["production_backup_writer_identity"]
        == "NOT_READY_UNTIL_PRODUCT_DB_AND_BACKUP_JOB_BINDING"
    )


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("bundle_integrity_pass", False, "BUNDLE_INTEGRITY_NOT_PROVEN"),
        ("corruption_rejected", False, "CORRUPTION_REJECTION_NOT_PROVEN"),
        ("offdevice_copy_pass", False, "SYNTHETIC_COPY_NOT_PROVEN"),
        ("restore_probe_pass", False, "RESTORE_PROBE_NOT_PROVEN"),
        (
            "offdevice_cleanup_pass",
            False,
            "SYNTHETIC_OFFDEVICE_CLEANUP_NOT_PROVEN",
        ),
        ("source_restore_separate", False, "SOURCE_RESTORE_NOT_SEPARATE"),
        ("temporary_state_cleaned", False, "TEMPORARY_STATE_NOT_CLEANED"),
        ("owner_target_used", True, "OWNER_TARGET_USED_IN_CI_REHEARSAL"),
        ("real_secret_values_used", True, "REAL_SECRET_USED"),
        ("private_portfolio_data_used", True, "PRIVATE_PORTFOLIO_USED"),
        ("account_identifiers_used", True, "ACCOUNT_IDENTIFIER_USED"),
        ("production_database_accessed", True, "PRODUCTION_DATABASE_ACCESSED"),
    ],
)
def test_recovery_profile_rejects_incomplete_or_private_evidence(
    field: str, value: object, reason: str
) -> None:
    profile = copy.deepcopy(_passing_profile())
    profile[field] = value
    result = assess(profile, _contract())
    assert result["status"] == "FAIL"
    assert reason in result["blockers"]


def test_recovery_profile_rejects_rto_breach() -> None:
    profile = _passing_profile()
    profile["duration_ms"] = 241 * 60 * 1000
    result = assess(profile, _contract())
    assert result["status"] == "FAIL"
    assert "REHEARSAL_EXCEEDS_RTO" in result["blockers"]
