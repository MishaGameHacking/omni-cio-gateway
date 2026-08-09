from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.assess_v10_wp10_owner_evidence import (
    assess,
    expected_implementation_fingerprint,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "docs" / "architecture" / "V10_WP10_RECOVERY_CONTRACT.json"


def _contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _rehearsal() -> dict:
    return {
        "schema_version": "1",
        "work_package": "WP10",
        "evidence_class": "OWNER_OFFDEVICE_RECOVERY_REHEARSAL",
        "status": "PASS",
        "reason_code": "OWNER_OFFDEVICE_BACKUP_CORRUPTION_RESTORE_PASS",
        "implementation_fingerprint": expected_implementation_fingerprint(),
        "postgres_major": 18,
        "postgres_version_class": "18.4",
        "owner_target_used": True,
        "non_system_volume": True,
        "data_volume": True,
        "bitlocker_fully_encrypted": True,
        "bitlocker_protection_on": True,
        "recovery_key_custody_confirmed": True,
        "target_marker_present": True,
        "bundle_integrity_pass": True,
        "offdevice_copy_pass": True,
        "corruption_rejected": True,
        "separate_restore_database_used": True,
        "restore_probe_exact_match": True,
        "temporary_state_cleaned": True,
        "real_secret_values_used": False,
        "private_portfolio_data_used": False,
        "account_identifiers_used": False,
        "production_database_accessed": False,
        "duration_ms": 9_000,
    }


def _access() -> dict:
    return {
        "schema_version": "1",
        "work_package": "WP10",
        "evidence_class": "NONADMIN_OFFDEVICE_ACCESS_AUDIT",
        "status": "PASS",
        "reason_code": "RUNNER_PAYLOAD_ACCESS_DENIED",
        "owner_descriptor_valid": True,
        "runner_payload_read_denied": True,
        "runner_payload_write_denied": True,
        "raw_disk_identity_emitted": False,
        "secret_value_emitted": False,
    }


def test_owner_evidence_passes_only_with_physical_nonadmin_and_current_code_proofs() -> None:
    result = assess(_rehearsal(), _access(), _contract())
    assert result["status"] == "PASS"
    assert result["target"]["runner_payload_read_denied"] is True
    assert result["target"]["runner_payload_write_denied"] is True
    assert result["rehearsal"]["offdevice_copy_pass"] is True
    assert "CURRENT_IMPLEMENTATION_FINGERPRINT_MATCH" in result["reason_codes"]
    assert all(value is False for value in result["privacy"].values())
    assert set(result) == {
        "schema_version",
        "work_package",
        "evidence_class",
        "captured_at_utc",
        "target",
        "rehearsal",
        "privacy",
        "status",
        "reason_codes",
    }


def test_owner_evidence_rejects_missing_or_stale_implementation_fingerprint() -> None:
    missing = _rehearsal()
    missing.pop("implementation_fingerprint")
    result = assess(missing, _access(), _contract())
    assert result["status"] == "FAIL"
    assert "IMPLEMENTATION_FINGERPRINT_MISSING" in result["reason_codes"]

    stale = _rehearsal()
    stale["implementation_fingerprint"]["rehearsal_script_sha256"] = "0" * 64
    result = assess(stale, _access(), _contract())
    assert result["status"] == "FAIL"
    assert any(
        code.startswith("IMPLEMENTATION_FINGERPRINT_MISMATCH:")
        for code in result["reason_codes"]
    )


def test_owner_evidence_rejects_missing_encryption_proof() -> None:
    rehearsal = _rehearsal()
    rehearsal["bitlocker_protection_on"] = False
    result = assess(rehearsal, _access(), _contract())
    assert result["status"] == "FAIL"
    assert "TARGET_BITLOCKER_PROTECTION_NOT_PROVEN" in result["reason_codes"]


def test_owner_evidence_rejects_runner_read_or_write_access() -> None:
    for field, reason in (
        ("runner_payload_read_denied", "RUNNER_READ_DENIAL_NOT_PROVEN"),
        ("runner_payload_write_denied", "RUNNER_WRITE_DENIAL_NOT_PROVEN"),
    ):
        access = _access()
        access[field] = False
        result = assess(_rehearsal(), access, _contract())
        assert result["status"] == "FAIL"
        assert reason in result["reason_codes"]


def test_owner_evidence_rejects_secret_private_or_production_use() -> None:
    for field, reason in (
        ("real_secret_values_used", "REAL_SECRET_USED"),
        ("private_portfolio_data_used", "PRIVATE_PORTFOLIO_USED"),
        ("account_identifiers_used", "ACCOUNT_IDENTIFIER_USED"),
        ("production_database_accessed", "PRODUCTION_DATABASE_ACCESSED"),
    ):
        rehearsal = _rehearsal()
        rehearsal[field] = True
        result = assess(rehearsal, _access(), _contract())
        assert result["status"] == "FAIL"
        assert reason in result["reason_codes"]


def test_owner_evidence_rejects_rto_breach() -> None:
    rehearsal = _rehearsal()
    rehearsal["duration_ms"] = 14_400_001
    result = assess(rehearsal, _access(), _contract())
    assert result["status"] == "FAIL"
    assert "REHEARSAL_EXCEEDS_RTO" in result["reason_codes"]


def test_owner_evidence_cannot_be_synthesized_by_ci_contract() -> None:
    contract = copy.deepcopy(_contract())
    contract["off_device"]["ci_may_synthesize_owner_evidence"] = True
    result = assess(_rehearsal(), _access(), contract)
    assert result["status"] == "FAIL"
    assert "OWNER_EVIDENCE_SYNTHESIS_BOUNDARY_WEAKENED" in result["reason_codes"]
