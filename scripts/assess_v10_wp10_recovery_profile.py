from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "docs" / "architecture" / "V10_WP10_RECOVERY_CONTRACT.json"


class RecoveryProfileError(RuntimeError):
    pass


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def assess(profile: dict, contract: dict) -> dict:
    blockers: list[str] = []

    if profile.get("schema_version") != "1" or profile.get("work_package") != "WP10":
        blockers.append("PROFILE_IDENTITY_INVALID")
    if profile.get("mode") != "SYNTHETIC_RECOVERY_REHEARSAL":
        blockers.append("PROFILE_MODE_INVALID")
    if profile.get("status") != "PASS":
        blockers.append("REHEARSAL_NOT_PASS")
    if profile.get("reason_code") != "RECOVERY_REHEARSAL_PASS":
        blockers.append("REHEARSAL_REASON_INVALID")

    version = str(profile.get("postgres_version_class", ""))
    if not version.startswith("18."):
        blockers.append("POSTGRES_MAJOR_MISMATCH")

    for key, reason in (
        ("bundle_integrity_pass", "BUNDLE_INTEGRITY_NOT_PROVEN"),
        ("corruption_rejected", "CORRUPTION_REJECTION_NOT_PROVEN"),
        ("offdevice_copy_pass", "SYNTHETIC_COPY_NOT_PROVEN"),
        ("restore_probe_pass", "RESTORE_PROBE_NOT_PROVEN"),
        ("offdevice_cleanup_pass", "SYNTHETIC_OFFDEVICE_CLEANUP_NOT_PROVEN"),
        ("source_restore_separate", "SOURCE_RESTORE_NOT_SEPARATE"),
        ("temporary_state_cleaned", "TEMPORARY_STATE_NOT_CLEANED"),
    ):
        if profile.get(key) is not True:
            blockers.append(reason)

    for key, reason in (
        ("owner_target_used", "OWNER_TARGET_USED_IN_CI_REHEARSAL"),
        ("real_secret_values_used", "REAL_SECRET_USED"),
        ("private_portfolio_data_used", "PRIVATE_PORTFOLIO_USED"),
        ("account_identifiers_used", "ACCOUNT_IDENTIFIER_USED"),
        ("production_database_accessed", "PRODUCTION_DATABASE_ACCESSED"),
    ):
        if profile.get(key) is not False:
            blockers.append(reason)

    if profile.get("offdevice_mode") != "SYNTHETIC_TEMP_ONLY":
        blockers.append("SYNTHETIC_OFFDEVICE_MODE_INVALID")

    duration = profile.get("duration_ms")
    if isinstance(duration, bool) or not isinstance(duration, (int, float)) or duration < 0:
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
        "production_database_binding": contract["postgresql"][
            "production_database_binding"
        ],
        "production_backup_writer_identity": contract["off_device"][
            "production_backup_writer_identity"
        ],
        "offdevice_final_acceptance": "OWNER_ACTION_REQUIRED",
        "real_money_authority_changed": False,
        "trading_methods": False,
        "real_trading_enabled": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", type=Path)
    args = parser.parse_args()
    result = assess(_load(args.profile), _load(CONTRACT_PATH))
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
