from __future__ import annotations

import argparse
import json
from pathlib import Path


class OffdeviceProfileError(RuntimeError):
    pass


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def assess(profile: dict) -> dict:
    blockers: list[str] = []

    if profile.get("schema_version") != "1" or profile.get("work_package") != "WP10":
        blockers.append("PROFILE_IDENTITY_INVALID")
    if profile.get("mode") != "NONADMIN_OFFDEVICE_AUDIT":
        blockers.append("PROFILE_MODE_INVALID")
    if profile.get("status") != "PASS":
        blockers.append("OFFDEVICE_AUDIT_NOT_PASS")
    if profile.get("reason_code") != "OFFDEVICE_AUDIT_PASS":
        blockers.append("OFFDEVICE_REASON_INVALID")

    for key, reason in (
        ("owner_evidence_present", "OWNER_EVIDENCE_MISSING"),
        ("target_present", "TARGET_NOT_PRESENT"),
        ("non_system_volume", "TARGET_IS_SYSTEM_VOLUME"),
        ("data_volume", "TARGET_NOT_DATA_VOLUME"),
        ("bitlocker_state_known", "BITLOCKER_STATE_UNKNOWN"),
        ("bitlocker_fully_encrypted", "TARGET_NOT_FULLY_ENCRYPTED"),
        ("bitlocker_protection_on", "BITLOCKER_PROTECTION_OFF"),
        ("recovery_key_custody_confirmed", "RECOVERY_KEY_CUSTODY_UNKNOWN"),
        ("target_marker_expected", "TARGET_MARKER_NOT_BOUND"),
        ("sentinel_expected", "TARGET_SENTINEL_NOT_BOUND"),
        ("runner_read_denied", "RUNNER_READ_NOT_DENIED"),
        ("runner_write_denied", "RUNNER_WRITE_NOT_DENIED"),
    ):
        if profile.get(key) is not True:
            blockers.append(reason)

    for key, reason in (
        ("runner_payload_access_granted", "RUNNER_PAYLOAD_ACCESS_ENABLED"),
        ("private_payload_collected", "PRIVATE_PAYLOAD_COLLECTED"),
        ("secret_value_collected", "SECRET_VALUE_COLLECTED"),
        ("recovery_key_value_collected", "RECOVERY_KEY_VALUE_COLLECTED"),
    ):
        if profile.get(key) is not False:
            blockers.append(reason)

    blockers = sorted(set(blockers))
    return {
        "schema_version": "1",
        "work_package": "WP10",
        "status": "PASS" if not blockers else "FAIL",
        "blockers": blockers,
        "offdevice_ready": not blockers,
        "runner_private_backup_access": False,
        "real_money_authority_changed": False,
        "trading_methods": False,
        "real_trading_enabled": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", type=Path)
    args = parser.parse_args()
    result = assess(_load(args.profile))
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
