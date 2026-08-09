from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


EXPECTED_SLOTS = {"core_api", "web", "telegram", "watchtower", "ai_worker"}
PRIVACY_FLAGS = {
    "raw_usernames_collected",
    "sids_emitted",
    "hostnames_collected",
    "addresses_collected",
    "credential_values_collected",
    "ciphertext_collected",
    "credential_hashes_collected",
    "account_ids_collected",
    "private_data_collected",
    "process_command_lines_collected",
    "process_dumps_collected",
}


def _is_true(value: Any) -> bool:
    return value is True


def assess(profile: dict[str, Any]) -> list[str]:
    blockers: list[str] = []

    if profile.get("schema_version") != "1":
        blockers.append("SCHEMA_VERSION_INVALID")
    if profile.get("work_package") != "WP9":
        blockers.append("WORK_PACKAGE_INVALID")
    if profile.get("mode") != "AUDIT":
        blockers.append("PROFILE_MODE_INVALID")
    if profile.get("status") != "PASS":
        blockers.append("PROFILE_STATUS_NOT_PASS")

    reasons = profile.get("reasons")
    if not isinstance(reasons, list) or reasons:
        blockers.append("PROFILE_REASON_CODES_PRESENT")

    if not _is_true(profile.get("runner_process")):
        blockers.append("RUNNER_PROCESS_NOT_PROVEN")

    health_task = profile.get("health_task")
    if not isinstance(health_task, dict) or not _is_true(health_task.get("valid")):
        blockers.append("HEALTH_TASK_INVALID")
    else:
        if not _is_true(health_task.get("present")):
            blockers.append("HEALTH_TASK_MISSING")
        if not _is_true(health_task.get("enabled")):
            blockers.append("HEALTH_TASK_NOT_ENABLED")
        if not _is_true(health_task.get("principal_is_local_service")):
            blockers.append("HEALTH_TASK_PRINCIPAL_INVALID")
        if not _is_true(health_task.get("bounded_restart")):
            blockers.append("HEALTH_TASK_RESTART_UNBOUNDED")

    slots = profile.get("sealed_slots")
    if not isinstance(slots, list):
        blockers.append("SEALED_SLOTS_INVALID")
    else:
        seen: set[str] = set()
        for row in slots:
            if not isinstance(row, dict):
                blockers.append("SEALED_SLOT_ROW_INVALID")
                continue
            slot_id = row.get("id")
            if not isinstance(slot_id, str):
                blockers.append("SEALED_SLOT_ID_INVALID")
                continue
            seen.add(slot_id)
            task = row.get("task")
            if not isinstance(task, dict) or not _is_true(task.get("valid")):
                blockers.append(f"SEALED_TASK_INVALID:{slot_id}")
                continue
            if not _is_true(task.get("present")):
                blockers.append(f"SEALED_TASK_MISSING:{slot_id}")
            if task.get("enabled") is not False:
                blockers.append(f"SEALED_TASK_ENABLED:{slot_id}")
            if not _is_true(task.get("principal_is_local_service")):
                blockers.append(f"SEALED_TASK_PRINCIPAL_INVALID:{slot_id}")
            if not _is_true(task.get("bounded_restart")):
                blockers.append(f"SEALED_TASK_RESTART_UNBOUNDED:{slot_id}")
        if seen != EXPECTED_SLOTS:
            blockers.append("SEALED_SLOT_SET_INVALID")

    if profile.get("execution_task_present") is not False:
        blockers.append("EXECUTION_TASK_PRESENT")

    for role_name in ("runtime_role", "execution_role"):
        role = profile.get(role_name)
        if not isinstance(role, dict):
            blockers.append(f"{role_name.upper()}_INVALID")
            continue
        if not _is_true(role.get("present")):
            blockers.append(f"{role_name.upper()}_MISSING")
        if role.get("enabled") is not False:
            blockers.append(f"{role_name.upper()}_ENABLED")
        if role.get("administrator") is not False:
            blockers.append(f"{role_name.upper()}_ADMINISTRATOR")

    if profile.get("local_service_wp8_payload_read_grant") is not False:
        blockers.append("LOCAL_SERVICE_WP8_PAYLOAD_GRANT_PRESENT")

    provision = profile.get("provision")
    if not isinstance(provision, dict):
        blockers.append("PROVISION_STATE_INVALID")
    else:
        if not _is_true(provision.get("present")):
            blockers.append("PROVISION_STATE_MISSING")
        if not _is_true(provision.get("idempotence_verified")):
            blockers.append("IDEMPOTENCE_NOT_PROVEN")
        if not _is_true(provision.get("future_product_slots_sealed")):
            blockers.append("FUTURE_PRODUCT_SLOTS_NOT_SEALED")
        if provision.get("real_secret_values_used") is not False:
            blockers.append("REAL_SECRET_VALUE_USED")
        if provision.get("real_money_authority_changed") is not False:
            blockers.append("REAL_MONEY_AUTHORITY_CHANGED")

    if not _is_true(profile.get("restart_rehearsal_pass")):
        blockers.append("RESTART_REHEARSAL_FAILED")
    if not _is_true(profile.get("dependency_rehearsal_pass")):
        blockers.append("DEPENDENCY_REHEARSAL_FAILED")
    if not _is_true(profile.get("post_reboot_fresh_status")):
        blockers.append("POST_REBOOT_FRESH_STATUS_NOT_PROVEN")
    if profile.get("health_status") not in {"HEALTHY", "DEGRADED"}:
        blockers.append("HEALTH_STATUS_NOT_SAFE")

    privacy = profile.get("privacy")
    if not isinstance(privacy, dict):
        blockers.append("PRIVACY_PROFILE_INVALID")
    else:
        for flag in PRIVACY_FLAGS:
            if privacy.get(flag) is not False:
                blockers.append(f"PRIVACY_FLAG_NOT_FALSE:{flag}")

    return sorted(set(blockers))


def main() -> int:
    if len(sys.argv) != 2:
        print(
            "usage: assess_v10_wp9_supervision_profile.py PROFILE.json",
            file=sys.stderr,
        )
        return 2

    path = Path(sys.argv[1])
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "blockers": [f"PROFILE_READ_FAILED:{type(exc).__name__}"],
                }
            )
        )
        return 1
    if not isinstance(payload, dict):
        print(json.dumps({"status": "FAIL", "blockers": ["PROFILE_ROOT_INVALID"]}))
        return 1

    blockers = assess(payload)
    result = {"status": "PASS" if not blockers else "FAIL", "blockers": blockers}
    print(json.dumps(result, sort_keys=True))
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
