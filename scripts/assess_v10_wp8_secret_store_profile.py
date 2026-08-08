from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

EXPECTED_CLASSES = {
    "broker_read",
    "broker_trading",
    "telegram_bot",
    "local_encryption_key",
    "external_source",
}
FORBIDDEN_KEYS = {
    "sid",
    "username",
    "hostname",
    "address",
    "addresses",
    "account_id",
    "account_ids",
    "secret",
    "secret_value",
    "token",
    "password",
    "ciphertext",
    "hash",
    "digest",
    "fingerprint",
    "private_data",
}


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load WP8 profile: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("WP8 profile must contain a JSON object")
    return value


def _walk_forbidden_keys(value: Any, path: str = "$") -> list[str]:
    blockers: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower()
            if normalized in FORBIDDEN_KEYS:
                blockers.append(f"FORBIDDEN_PROFILE_FIELD:{path}.{key}")
            blockers.extend(_walk_forbidden_keys(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            blockers.extend(_walk_forbidden_keys(child, f"{path}[{index}]"))
    return blockers


def assess(profile: dict[str, Any], *, require_runner_denial: bool = True) -> list[str]:
    blockers: list[str] = []

    if profile.get("schema_version") != "1":
        blockers.append("PROFILE_SCHEMA_INVALID")
    if profile.get("provider") != "WINDOWS_DPAPI_LOCAL_MACHINE_PLUS_PROTECTED_DACL":
        blockers.append("PROVIDER_INVALID")
    if profile.get("status") != "PASS":
        blockers.append("PROFILE_STATUS_NOT_PASS")
    if profile.get("reasons") not in ([], tuple()):
        blockers.append("PROFILE_REASON_CODES_PRESENT")
    if profile.get("real_secret_values_used") is not False:
        blockers.append("REAL_SECRET_VALUES_USED")

    privacy = profile.get("privacy")
    expected_privacy = {
        "raw_usernames_collected",
        "sids_emitted",
        "hostnames_collected",
        "addresses_collected",
        "secret_values_collected",
        "secret_hashes_collected",
        "ciphertext_collected",
        "account_ids_collected",
        "private_data_collected",
        "process_dumps_collected",
    }
    if not isinstance(privacy, dict):
        blockers.append("PRIVACY_PROFILE_MISSING")
    else:
        if set(privacy) != expected_privacy:
            blockers.append("PRIVACY_PROFILE_FIELDS_INVALID")
        for name in expected_privacy:
            if privacy.get(name) is not False:
                blockers.append(f"PRIVACY_FLAG_NOT_FALSE:{name}")

    runtime = profile.get("runtime_role")
    execution = profile.get("execution_role")
    for name, role in (("runtime", runtime), ("execution", execution)):
        if not isinstance(role, dict):
            blockers.append(f"ROLE_PROFILE_MISSING:{name}")
            continue
        if role.get("present") is not True:
            blockers.append(f"ROLE_NOT_PRESENT:{name}")
        if role.get("enabled") is not False:
            blockers.append(f"ROLE_NOT_DISABLED:{name}")
        if role.get("administrator") is not False:
            blockers.append(f"ROLE_ADMINISTRATOR:{name}")

    rotation = profile.get("rotation_rehearsal")
    if not isinstance(rotation, dict):
        blockers.append("ROTATION_PROFILE_MISSING")
    else:
        if rotation.get("broker_read") is not True:
            blockers.append("BROKER_READ_ROTATION_REHEARSAL_FAILED")
        if rotation.get("telegram_bot") is not True:
            blockers.append("TELEGRAM_ROTATION_REHEARSAL_FAILED")

    classes = profile.get("classes")
    if not isinstance(classes, list):
        blockers.append("CLASS_PROFILE_MISSING")
        classes = []

    by_id: dict[str, dict[str, Any]] = {}
    for item in classes:
        if not isinstance(item, dict):
            blockers.append("CLASS_PROFILE_ENTRY_INVALID")
            continue
        class_id = str(item.get("secret_class", ""))
        if class_id in by_id:
            blockers.append(f"DUPLICATE_CLASS_PROFILE:{class_id}")
            continue
        by_id[class_id] = item

    if set(by_id) != EXPECTED_CLASSES:
        blockers.append("CLASS_PROFILE_SET_INVALID")

    runner_process = profile.get("runner_process") is True
    if require_runner_denial and not runner_process:
        blockers.append("AUTHORITATIVE_RUNNER_PROCESS_NOT_PROVEN")

    for class_id in sorted(EXPECTED_CLASSES):
        item = by_id.get(class_id)
        if item is None:
            continue
        for field in ("directory_present", "sentinel_present", "intended_read_grant"):
            if item.get(field) is not True:
                blockers.append(f"CLASS_{field.upper()}_NOT_TRUE:{class_id}")
        for field in (
            "runner_read_data_grant",
            "runner_write_grant",
            "broad_read_exposure",
        ):
            if item.get(field) is not False:
                blockers.append(f"CLASS_{field.upper()}_NOT_FALSE:{class_id}")
        if item.get("real_secret_provisioned") is not False:
            blockers.append(f"REAL_SECRET_PROVISIONED:{class_id}")
        if item.get("lifecycle_state") != "UNPROVISIONED":
            blockers.append(f"LIFECYCLE_NOT_UNPROVISIONED:{class_id}")
        if item.get("lifecycle_version") != 0:
            blockers.append(f"LIFECYCLE_VERSION_NOT_ZERO:{class_id}")
        if require_runner_denial and item.get("runner_data_read") != "ACCESS_DENIED":
            blockers.append(f"RUNNER_DATA_READ_NOT_DENIED:{class_id}")

    broker_read = by_id.get("broker_read")
    if broker_read is not None:
        if broker_read.get("runtime_read_grant") is not True:
            blockers.append("RUNTIME_BROKER_READ_GRANT_MISSING")
        if broker_read.get("execution_read_grant") is not False:
            blockers.append("EXECUTION_BROKER_READ_GRANT_PRESENT")

    broker_trading = by_id.get("broker_trading")
    if broker_trading is not None:
        if broker_trading.get("execution_read_grant") is not True:
            blockers.append("EXECUTION_TRADING_READ_GRANT_MISSING")
        if broker_trading.get("runtime_read_grant") is not False:
            blockers.append("RUNTIME_TRADING_READ_GRANT_PRESENT")

    for class_id in ("telegram_bot", "local_encryption_key", "external_source"):
        item = by_id.get(class_id)
        if item is None:
            continue
        if item.get("runtime_read_grant") is not False:
            blockers.append(f"SEALED_RUNTIME_READ_GRANT_PRESENT:{class_id}")
        if item.get("execution_read_grant") is not False:
            blockers.append(f"SEALED_EXECUTION_READ_GRANT_PRESENT:{class_id}")

    blockers.extend(_walk_forbidden_keys(profile))
    return blockers


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Assess sanitized V10 WP8 secret-store evidence"
    )
    parser.add_argument("profile", type=Path)
    parser.add_argument(
        "--owner-preview",
        action="store_true",
        help="do not require the current process to be the CI runner",
    )
    args = parser.parse_args()

    try:
        profile = _load(args.profile)
    except ValueError as exc:
        print(json.dumps({"status": "FAIL", "blockers": [str(exc)]}, sort_keys=True))
        return 1

    blockers = assess(profile, require_runner_denial=not args.owner_preview)
    result = {"status": "PASS" if not blockers else "FAIL", "blockers": blockers}
    print(json.dumps(result, sort_keys=True))
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
