from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "docs" / "architecture" / "V10_WP10_RECOVERY_CONTRACT.json"
REHEARSAL_SCRIPT = ROOT / "infrastructure" / "windows" / "rehearse_wp10_recovery.ps1"
BACKUP_RUNNER = ROOT / "infrastructure" / "windows" / "run_wp10_backup.ps1"
PREPARE_SCRIPT = (
    ROOT / "infrastructure" / "windows" / "prepare_wp10_offdevice_target.ps1"
)
OWNER_GATE_SCRIPT = ROOT / "infrastructure" / "windows" / "run_wp10_owner_gate.ps1"
BUNDLE_TOOL = ROOT / "scripts" / "v10_wp10_backup_bundle.py"


class OwnerEvidenceError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OwnerEvidenceError("EVIDENCE_READ_INVALID") from exc
    if not isinstance(payload, dict):
        raise OwnerEvidenceError("EVIDENCE_NOT_OBJECT")
    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def expected_implementation_fingerprint() -> dict[str, str]:
    return {
        "recovery_contract_sha256": _sha256(CONTRACT_PATH),
        "rehearsal_script_sha256": _sha256(REHEARSAL_SCRIPT),
        "backup_runner_sha256": _sha256(BACKUP_RUNNER),
        "bundle_tool_sha256": _sha256(BUNDLE_TOOL),
        "prepare_script_sha256": _sha256(PREPARE_SCRIPT),
        "owner_gate_script_sha256": _sha256(OWNER_GATE_SCRIPT),
    }


def _true(payload: dict[str, Any], key: str, reason: str, blockers: list[str]) -> None:
    if payload.get(key) is not True:
        blockers.append(reason)


def _false(payload: dict[str, Any], key: str, reason: str, blockers: list[str]) -> None:
    if payload.get(key) is not False:
        blockers.append(reason)


def assess(
    rehearsal: dict[str, Any],
    access: dict[str, Any],
    contract: dict[str, Any],
) -> dict[str, Any]:
    blockers: list[str] = []

    if (
        rehearsal.get("schema_version") != "1"
        or rehearsal.get("work_package") != "WP10"
    ):
        blockers.append("OWNER_REHEARSAL_IDENTITY_INVALID")
    if rehearsal.get("evidence_class") != "OWNER_OFFDEVICE_RECOVERY_REHEARSAL":
        blockers.append("OWNER_REHEARSAL_CLASS_INVALID")
    if rehearsal.get("status") != "PASS":
        blockers.append("OWNER_REHEARSAL_NOT_PASS")
    if rehearsal.get("reason_code") != "OWNER_OFFDEVICE_BACKUP_CORRUPTION_RESTORE_PASS":
        blockers.append("OWNER_REHEARSAL_REASON_INVALID")

    fingerprint = rehearsal.get("implementation_fingerprint")
    expected_fingerprint = expected_implementation_fingerprint()
    if not isinstance(fingerprint, dict):
        blockers.append("IMPLEMENTATION_FINGERPRINT_MISSING")
    elif set(fingerprint) != set(expected_fingerprint):
        blockers.append("IMPLEMENTATION_FINGERPRINT_FIELDS_INVALID")
    else:
        for key, expected in expected_fingerprint.items():
            actual = fingerprint.get(key)
            if not isinstance(actual, str) or actual.lower() != expected:
                blockers.append(f"IMPLEMENTATION_FINGERPRINT_MISMATCH:{key.upper()}")

    if rehearsal.get("postgres_major") != 18:
        blockers.append("POSTGRES_MAJOR_MISMATCH")
    version = str(rehearsal.get("postgres_version_class", ""))
    if not version.startswith("18."):
        blockers.append("POSTGRES_VERSION_CLASS_INVALID")

    for key, reason in (
        ("owner_target_used", "OWNER_TARGET_NOT_USED"),
        ("non_system_volume", "TARGET_NOT_PROVEN_NON_SYSTEM"),
        ("data_volume", "TARGET_NOT_PROVEN_DATA_VOLUME"),
        ("bitlocker_fully_encrypted", "TARGET_NOT_PROVEN_FULLY_ENCRYPTED"),
        ("bitlocker_protection_on", "TARGET_BITLOCKER_PROTECTION_NOT_PROVEN"),
        ("recovery_key_custody_confirmed", "RECOVERY_KEY_CUSTODY_NOT_CONFIRMED"),
        ("target_marker_present", "TARGET_MARKER_NOT_PROVEN"),
        ("bundle_integrity_pass", "BUNDLE_INTEGRITY_NOT_PROVEN"),
        ("offdevice_copy_pass", "OFFDEVICE_COPY_NOT_PROVEN"),
        ("corruption_rejected", "CORRUPTION_REJECTION_NOT_PROVEN"),
        ("separate_restore_database_used", "SEPARATE_RESTORE_DATABASE_NOT_PROVEN"),
        ("restore_probe_exact_match", "RESTORE_PROBE_NOT_PROVEN"),
        ("temporary_state_cleaned", "TEMPORARY_STATE_NOT_CLEANED"),
    ):
        _true(rehearsal, key, reason, blockers)

    for key, reason in (
        ("real_secret_values_used", "REAL_SECRET_USED"),
        ("private_portfolio_data_used", "PRIVATE_PORTFOLIO_USED"),
        ("account_identifiers_used", "ACCOUNT_IDENTIFIER_USED"),
        ("production_database_accessed", "PRODUCTION_DATABASE_ACCESSED"),
    ):
        _false(rehearsal, key, reason, blockers)

    duration = rehearsal.get("duration_ms")
    rto_ms = int(contract["recovery_objectives"]["rto_minutes"]) * 60 * 1000
    if (
        isinstance(duration, bool)
        or not isinstance(duration, (int, float))
        or duration < 0
    ):
        blockers.append("REHEARSAL_DURATION_INVALID")
        duration_ms = 0
    else:
        duration_ms = int(duration)
        if duration_ms > rto_ms:
            blockers.append("REHEARSAL_EXCEEDS_RTO")

    if access.get("schema_version") != "1" or access.get("work_package") != "WP10":
        blockers.append("ACCESS_AUDIT_IDENTITY_INVALID")
    if access.get("evidence_class") != "NONADMIN_OFFDEVICE_ACCESS_AUDIT":
        blockers.append("ACCESS_AUDIT_CLASS_INVALID")
    if access.get("status") != "PASS":
        blockers.append("ACCESS_AUDIT_NOT_PASS")
    if access.get("reason_code") != "RUNNER_PAYLOAD_ACCESS_DENIED":
        blockers.append("ACCESS_AUDIT_REASON_INVALID")
    for key, reason in (
        ("owner_descriptor_valid", "OWNER_DESCRIPTOR_NOT_PROVEN"),
        ("runner_payload_read_denied", "RUNNER_READ_DENIAL_NOT_PROVEN"),
        ("runner_payload_write_denied", "RUNNER_WRITE_DENIAL_NOT_PROVEN"),
    ):
        _true(access, key, reason, blockers)
    for key, reason in (
        ("raw_disk_identity_emitted", "RAW_DISK_IDENTITY_EMITTED"),
        ("secret_value_emitted", "SECRET_VALUE_EMITTED"),
    ):
        _false(access, key, reason, blockers)

    if contract["off_device"].get("ci_may_synthesize_owner_evidence") is not False:
        blockers.append("OWNER_EVIDENCE_SYNTHESIS_BOUNDARY_WEAKENED")
    if contract["acceptance"].get("owner_physical_recovery_required") is not True:
        blockers.append("OWNER_PHYSICAL_GATE_WEAKENED")

    blockers = sorted(set(blockers))
    status = "PASS" if not blockers else "FAIL"
    reason_codes = (
        [
            "CURRENT_IMPLEMENTATION_FINGERPRINT_MATCH",
            "OWNER_OFFDEVICE_RECOVERY_PASS",
            "RUNNER_PAYLOAD_ACCESS_DENIED",
        ]
        if not blockers
        else blockers
    )

    return {
        "schema_version": "1",
        "work_package": "WP10",
        "evidence_class": "OWNER_OFFDEVICE_RECOVERY",
        "captured_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "target": {
            "non_system_volume": bool(rehearsal.get("non_system_volume")),
            "bitlocker_fully_encrypted": bool(
                rehearsal.get("bitlocker_fully_encrypted")
            ),
            "bitlocker_protection_on": bool(rehearsal.get("bitlocker_protection_on")),
            "recovery_key_custody_confirmed": bool(
                rehearsal.get("recovery_key_custody_confirmed")
            ),
            "target_marker_present": bool(rehearsal.get("target_marker_present")),
            "runner_payload_read_denied": bool(
                access.get("runner_payload_read_denied")
            ),
            "runner_payload_write_denied": bool(
                access.get("runner_payload_write_denied")
            ),
        },
        "rehearsal": {
            "postgres_major": 18,
            "bundle_integrity_pass": bool(rehearsal.get("bundle_integrity_pass")),
            "corruption_rejected": bool(rehearsal.get("corruption_rejected")),
            "offdevice_copy_pass": bool(rehearsal.get("offdevice_copy_pass")),
            "separate_restore_database_used": bool(
                rehearsal.get("separate_restore_database_used")
            ),
            "restore_probe_exact_match": bool(
                rehearsal.get("restore_probe_exact_match")
            ),
            "temporary_state_cleaned": bool(rehearsal.get("temporary_state_cleaned")),
            "duration_ms": duration_ms,
        },
        "privacy": {
            "raw_disk_identity_collected": False,
            "recovery_key_value_collected": False,
            "secret_value_collected": False,
            "account_identifier_collected": False,
            "private_portfolio_payload_collected": False,
            "private_database_archive_uploaded_to_ci": False,
        },
        "status": status,
        "reason_codes": reason_codes,
    }


def _schema_shape_check(payload: dict[str, Any]) -> None:
    expected_top = {
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
    if set(payload) != expected_top:
        raise OwnerEvidenceError("SANITIZED_EVIDENCE_TOP_LEVEL_INVALID")
    if payload["schema_version"] != "1" or payload["work_package"] != "WP10":
        raise OwnerEvidenceError("SANITIZED_EVIDENCE_IDENTITY_INVALID")
    if payload["evidence_class"] != "OWNER_OFFDEVICE_RECOVERY":
        raise OwnerEvidenceError("SANITIZED_EVIDENCE_CLASS_INVALID")
    if payload["status"] not in {"PASS", "FAIL", "OWNER_ACTION_REQUIRED"}:
        raise OwnerEvidenceError("SANITIZED_EVIDENCE_STATUS_INVALID")

    target_keys = {
        "non_system_volume",
        "bitlocker_fully_encrypted",
        "bitlocker_protection_on",
        "recovery_key_custody_confirmed",
        "target_marker_present",
        "runner_payload_read_denied",
        "runner_payload_write_denied",
    }
    rehearsal_keys = {
        "postgres_major",
        "bundle_integrity_pass",
        "corruption_rejected",
        "offdevice_copy_pass",
        "separate_restore_database_used",
        "restore_probe_exact_match",
        "temporary_state_cleaned",
        "duration_ms",
    }
    privacy_keys = {
        "raw_disk_identity_collected",
        "recovery_key_value_collected",
        "secret_value_collected",
        "account_identifier_collected",
        "private_portfolio_payload_collected",
        "private_database_archive_uploaded_to_ci",
    }
    if set(payload["target"]) != target_keys:
        raise OwnerEvidenceError("SANITIZED_TARGET_FIELDS_INVALID")
    if set(payload["rehearsal"]) != rehearsal_keys:
        raise OwnerEvidenceError("SANITIZED_REHEARSAL_FIELDS_INVALID")
    if set(payload["privacy"]) != privacy_keys:
        raise OwnerEvidenceError("SANITIZED_PRIVACY_FIELDS_INVALID")
    if any(value is not False for value in payload["privacy"].values()):
        raise OwnerEvidenceError("SANITIZED_PRIVACY_GUARD_FAILED")
    if payload["rehearsal"]["postgres_major"] != 18:
        raise OwnerEvidenceError("SANITIZED_POSTGRES_MAJOR_INVALID")
    if payload["rehearsal"]["duration_ms"] > 14_400_000:
        raise OwnerEvidenceError("SANITIZED_RTO_EXCEEDED")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Combine current OWNER rehearsal and non-admin ACL audit into sanitized WP10 evidence"
    )
    parser.add_argument("rehearsal", type=Path)
    parser.add_argument("access_audit", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    contract = _load(CONTRACT_PATH)
    result = assess(_load(args.rehearsal), _load(args.access_audit), contract)
    _schema_shape_check(result)
    encoded = json.dumps(result, sort_keys=True, separators=(",", ":"))
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
