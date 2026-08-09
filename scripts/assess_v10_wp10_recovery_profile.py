from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "docs" / "architecture" / "V10_WP10_RECOVERY_CONTRACT.json"


class RecoveryProfileError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise RecoveryProfileError("PROFILE_NOT_OBJECT")
    return payload


def assess(profile: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    if profile.get("schema_version") != "1" or profile.get("work_package") != "WP10":
        blockers.append("PROFILE_IDENTITY_INVALID")
    if profile.get("evidence_class") != "LENOVO_SYNTHETIC_RECOVERY_REHEARSAL":
        blockers.append("PROFILE_CLASS_INVALID")
    if profile.get("status") != "PASS":
        blockers.append("REHEARSAL_NOT_PASS")
    if profile.get("reason_code") != "SYNTHETIC_BACKUP_CORRUPTION_RESTORE_PASS":
        blockers.append("REHEARSAL_REASON_INVALID")

    if profile.get("postgres_major") != 18:
        blockers.append("POSTGRES_MAJOR_MISMATCH")
    version = str(profile.get("postgres_version_class", ""))
    if not version.startswith("18."):
        blockers.append("POSTGRES_VERSION_CLASS_INVALID")

    for key, reason in (
        ("bundle_integrity_pass", "BUNDLE_INTEGRITY_NOT_PROVEN"),
        ("corruption_rejected", "CORRUPTION_REJECTION_NOT_PROVEN"),
        ("separate_restore_database_used", "RESTORE_DATABASE_NOT_SEPARATE"),
        ("restore_probe_exact_match", "RESTORE_PROBE_NOT_PROVEN"),
        ("temporary_state_cleaned", "TEMPORARY_STATE_NOT_CLEANED"),
    ):
        if profile.get(key) is not True:
            blockers.append(reason)

    for key, reason in (
        ("real_secret_values_used", "REAL_SECRET_USED"),
        ("private_portfolio_data_used", "PRIVATE_PORTFOLIO_USED"),
        ("production_database_accessed", "PRODUCTION_DATABASE_ACCESSED"),
    ):
        if profile.get(key) is not False:
            blockers.append(reason)

    duration = profile.get("duration_ms")
    if (
        isinstance(duration, bool)
        or not isinstance(duration, (int, float))
        or duration < 0
    ):
        blockers.append("REHEARSAL_DURATION_INVALID")
    else:
        rto_ms = int(contract["recovery_objectives"]["rto_minutes"]) * 60 * 1000
        if float(duration) > rto_ms:
            blockers.append("REHEARSAL_EXCEEDS_RTO")

    blockers = sorted(set(blockers))
    return {
        "schema_version": "1",
        "work_package": "WP10",
        "status": "PASS" if not blockers else "FAIL",
        "blockers": blockers,
        "synthetic_recovery_ready": not blockers,
        "owner_offdevice_final_acceptance": "OWNER_ACTION_REQUIRED",
        "production_database_binding": contract["postgresql"][
            "production_database_binding"
        ],
        "production_job_binding": contract["postgresql"]["production_job_binding"],
        "wp11_locked": True,
        "trading_methods": False,
        "real_trading_enabled": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Assess sanitized WP10 synthetic recovery evidence"
    )
    parser.add_argument("profile", type=Path)
    args = parser.parse_args()
    result = assess(_load(args.profile), _load(CONTRACT_PATH))
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
