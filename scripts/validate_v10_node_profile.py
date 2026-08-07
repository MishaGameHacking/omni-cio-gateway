from __future__ import annotations

import argparse
from datetime import datetime
import ipaddress
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_THRESHOLDS = ROOT / "infrastructure" / "windows" / "wp5_node_thresholds.json"

REQUIRED_TOP_LEVEL = {
    "schema_version",
    "captured_at_utc",
    "capture_mode",
    "node_role",
    "privacy",
    "hardware",
    "os",
    "security",
    "time",
    "network",
    "power",
    "thermal",
    "checks",
    "thresholds_ref",
    "exit_gate",
}
FORBIDDEN_KEYS = {
    "serial_number",
    "serial_numbers",
    "mac",
    "mac_address",
    "mac_addresses",
    "ip",
    "ip_address",
    "ip_addresses",
    "username",
    "user_name",
    "hostname",
    "host_name",
    "computer_name",
    "device_id",
    "uuid",
    "key_protector",
    "key_protectors",
    "recovery_password",
    "recovery_key",
    "recovery_key_value",
    "secret",
    "secrets",
    "token",
    "tokens",
    "broker_token",
    "account_id",
}
MAC_RE = re.compile(r"(?i)(?:\b[0-9a-f]{2}[:-]){5}[0-9a-f]{2}\b")
USER_PATH_RE = re.compile(r"(?i)(?:[a-z]:\\Users\\[^\\\s]+|/Users/[^/\s]+)")
IPV4_CANDIDATE_RE = re.compile(
    r"(?<![A-Za-z0-9_.-])\d{1,3}(?:\.\d{1,3}){3}(?![A-Za-z0-9_.-])"
)


class ProfileError(ValueError):
    pass


def _as_dict(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProfileError(f"{path} must be an object")
    return value


def _parse_datetime(value: Any, path: str) -> None:
    if not isinstance(value, str):
        raise ProfileError(f"{path} must be a date-time string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProfileError(f"{path} is not RFC3339 date-time") from exc
    if parsed.tzinfo is None:
        raise ProfileError(f"{path} must include timezone information")


def _walk_privacy(value: Any, path: str = "$") -> list[str]:
    failures: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in FORBIDDEN_KEYS:
                failures.append(f"{path}.{key}: forbidden privacy-sensitive key")
            failures.extend(_walk_privacy(child, f"{path}.{key}"))
        return failures
    if isinstance(value, list):
        for index, child in enumerate(value):
            failures.extend(_walk_privacy(child, f"{path}[{index}]"))
        return failures
    if isinstance(value, str):
        if MAC_RE.search(value):
            failures.append(f"{path}: MAC-like value is forbidden")
        if USER_PATH_RE.search(value):
            failures.append(f"{path}: user profile path is forbidden")
        for token in IPV4_CANDIDATE_RE.findall(value):
            try:
                ipaddress.ip_address(token)
            except ValueError:
                continue
            failures.append(f"{path}: IP address value is forbidden")
    return failures


def _require_keys(obj: dict[str, Any], keys: set[str], path: str) -> list[str]:
    return [
        f"{path}: missing required property {key!r}"
        for key in sorted(keys - obj.keys())
    ]


def validate_shape(profile: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    failures.extend(_require_keys(profile, REQUIRED_TOP_LEVEL, "$"))
    unexpected = set(profile) - REQUIRED_TOP_LEVEL
    if unexpected:
        failures.append(f"$: unexpected top-level properties {sorted(unexpected)!r}")

    if profile.get("schema_version") != "1":
        failures.append("$.schema_version must equal '1'")
    if profile.get("capture_mode") != "PASSIVE_READ_ONLY":
        failures.append("$.capture_mode must be PASSIVE_READ_ONLY")
    if profile.get("node_role") != "OWNER_PERSONAL_NODE":
        failures.append("$.node_role must be OWNER_PERSONAL_NODE")
    if (
        profile.get("thresholds_ref")
        != "infrastructure/windows/wp5_node_thresholds.json"
    ):
        failures.append("$.thresholds_ref must point to the canonical WP5 thresholds")

    try:
        _parse_datetime(profile.get("captured_at_utc"), "$.captured_at_utc")
        os_data = _as_dict(profile.get("os"), "$.os")
        _parse_datetime(os_data.get("last_boot_utc"), "$.os.last_boot_utc")
    except ProfileError as exc:
        failures.append(str(exc))

    privacy = profile.get("privacy")
    if isinstance(privacy, dict):
        required_privacy = {
            "serial_numbers_collected",
            "mac_or_ip_collected",
            "usernames_or_hostnames_collected",
            "secret_values_collected",
            "recovery_key_material_collected",
        }
        failures.extend(_require_keys(privacy, required_privacy, "$.privacy"))
        for key in required_privacy:
            if privacy.get(key) is not False:
                failures.append(f"$.privacy.{key} must be false")
    else:
        failures.append("$.privacy must be an object")

    hardware = profile.get("hardware")
    if isinstance(hardware, dict):
        failures.extend(
            _require_keys(
                hardware,
                {"cpu", "memory", "gpu", "storage"},
                "$.hardware",
            )
        )
        cpu = hardware.get("cpu")
        if isinstance(cpu, dict):
            failures.extend(
                _require_keys(
                    cpu,
                    {"model", "physical_cores", "logical_processors"},
                    "$.hardware.cpu",
                )
            )
            if not isinstance(cpu.get("model"), str) or not cpu.get("model"):
                failures.append("$.hardware.cpu.model must be a non-empty string")
            for key in ("physical_cores", "logical_processors"):
                if not isinstance(cpu.get(key), int) or cpu.get(key, 0) < 1:
                    failures.append(
                        f"$.hardware.cpu.{key} must be a positive integer"
                    )
        else:
            failures.append("$.hardware.cpu must be an object")
        memory = hardware.get("memory")
        if (
            not isinstance(memory, dict)
            or not isinstance(memory.get("total_gib"), (int, float))
            or memory.get("total_gib", 0) <= 0
        ):
            failures.append("$.hardware.memory.total_gib must be positive")
        if not isinstance(hardware.get("gpu"), dict):
            failures.append("$.hardware.gpu must be an object")
        if not isinstance(hardware.get("storage"), dict):
            failures.append("$.hardware.storage must be an object")
    else:
        failures.append("$.hardware must be an object")

    for path, keyset in (
        ("security", {"full_disk_encryption", "firewall", "private_at_rest"}),
        (
            "time",
            {
                "service_status",
                "source_class",
                "measured_against",
                "offset_ms",
                "utc_policy",
                "sensitive_operation_gate",
            },
        ),
        (
            "network",
            {
                "wired_connected",
                "wired_link_speed_mbps",
                "public_exposure_assessment",
            },
        ),
        (
            "power",
            {
                "battery_present",
                "ac_online",
                "active_power_scheme",
                "battery_conservation",
                "restart_after_power_loss",
            },
        ),
        ("thermal", {"acpi_zone_max_idle_c", "gpu_idle_c", "observation"}),
        (
            "checks",
            {
                "disk_health",
                "reboot",
                "network_reconnect",
                "sustained_cpu_gpu_load",
            },
        ),
        ("exit_gate", {"status", "blocking_reasons"}),
    ):
        obj = profile.get(path)
        if not isinstance(obj, dict):
            failures.append(f"$.{path} must be an object")
        else:
            failures.extend(_require_keys(obj, keyset, f"$.{path}"))

    failures.extend(_walk_privacy(profile))
    return failures


def assess_exit_gate(
    profile: dict[str, Any], thresholds: dict[str, Any]
) -> list[str]:
    blockers: list[str] = []
    security = _as_dict(profile["security"], "$.security")
    encryption = _as_dict(
        security["full_disk_encryption"], "$.security.full_disk_encryption"
    )
    if encryption.get("provider") != "BITLOCKER":
        blockers.append("SYSTEM_VOLUME_ENCRYPTION_UNVERIFIED")
    if str(encryption.get("protection_status", "")).upper() != "ON":
        blockers.append("BITLOCKER_PROTECTION_NOT_ON")
    percentage = encryption.get("encryption_percentage")
    if not isinstance(percentage, (int, float)) or percentage < 100:
        blockers.append("SYSTEM_VOLUME_NOT_FULLY_ENCRYPTED")
    if encryption.get("recovery_key_custody_status") != "OWNER_CONFIRMED_SEPARATE":
        blockers.append("RECOVERY_KEY_CUSTODY_CONFIRMATION_REQUIRED")

    time_data = _as_dict(profile["time"], "$.time")
    clock_policy = _as_dict(thresholds["clock"], "$.thresholds.clock")
    offset = time_data.get("offset_ms")
    time_service_running = (
        str(time_data.get("service_status", "")).upper() == "RUNNING"
    )
    if not time_service_running:
        blockers.append("WINDOWS_TIME_SERVICE_NOT_RUNNING")
    if not isinstance(offset, (int, float)):
        blockers.append("CLOCK_OFFSET_UNKNOWN")
    elif abs(offset) > float(clock_policy["block_sensitive_absolute_offset_ms"]):
        blockers.append("CLOCK_DRIFT_EXCEEDS_SENSITIVE_OPERATION_LIMIT")

    expected_clock_gate = (
        "BLOCK_UNKNOWN_TIME"
        if not time_service_running or not isinstance(offset, (int, float))
        else "BLOCK_DRIFT"
        if abs(offset) > float(clock_policy["block_sensitive_absolute_offset_ms"])
        else "PASS"
    )
    if time_data.get("sensitive_operation_gate") != expected_clock_gate:
        blockers.append("CLOCK_GATE_STATE_INCONSISTENT")

    hardware = _as_dict(profile["hardware"], "$.hardware")
    storage = _as_dict(hardware["storage"], "$.hardware.storage")
    system_volume = _as_dict(
        storage["system_volume"], "$.hardware.storage.system_volume"
    )
    storage_policy = _as_dict(thresholds["storage"], "$.thresholds.storage")
    free_gib = system_volume.get("free_gib")
    free_percent = system_volume.get("free_percent")
    if not isinstance(free_gib, (int, float)) or free_gib < float(
        storage_policy["block_free_gib"]
    ):
        blockers.append("SYSTEM_VOLUME_FREE_GIB_BELOW_BLOCK_LIMIT")
    if not isinstance(free_percent, (int, float)) or free_percent < float(
        storage_policy["block_free_percent"]
    ):
        blockers.append("SYSTEM_VOLUME_FREE_PERCENT_BELOW_BLOCK_LIMIT")
    disks = storage.get("physical_disks", [])
    if not isinstance(disks, list) or not disks:
        blockers.append("PHYSICAL_DISK_HEALTH_UNKNOWN")
    else:
        for disk in disks:
            if not isinstance(disk, dict) or str(
                disk.get("health_status", "")
            ).lower() != "healthy":
                blockers.append("PHYSICAL_DISK_NOT_HEALTHY")
                break

    firewall = _as_dict(security["firewall"], "$.security.firewall")
    profiles = firewall.get("profiles", [])
    required_profiles = set(
        thresholds["network"]["windows_firewall_profiles_required_enabled"]
    )
    observed: set[str] = set()
    for item in profiles if isinstance(profiles, list) else []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", ""))
        observed.add(name)
        if name in required_profiles and item.get("enabled") is not True:
            blockers.append(f"WINDOWS_FIREWALL_{name.upper()}_DISABLED")
        inbound = str(item.get("default_inbound_action", "")).lower()
        if name in required_profiles and inbound not in {"block", "notconfigured"}:
            blockers.append(f"WINDOWS_FIREWALL_{name.upper()}_INBOUND_NOT_BLOCK")
    if not required_profiles.issubset(observed):
        blockers.append("WINDOWS_FIREWALL_PROFILE_DATA_INCOMPLETE")

    network = _as_dict(profile["network"], "$.network")
    if network.get("wired_connected") is not True:
        blockers.append("WIRED_NETWORK_NOT_CONNECTED")

    power = _as_dict(profile["power"], "$.power")
    if power.get("restart_after_power_loss") != "ENABLED":
        blockers.append("RESTART_AFTER_POWER_LOSS_NOT_VERIFIED_ENABLED")
    if (
        power.get("battery_present") is True
        and power.get("battery_conservation") != "ENABLED"
    ):
        blockers.append("BATTERY_CONSERVATION_NOT_VERIFIED_ENABLED")

    checks = _as_dict(profile["checks"], "$.checks")
    for key, blocker in (
        ("disk_health", "DISK_HEALTH_TEST_NOT_PASS"),
        ("reboot", "REBOOT_TEST_NOT_PASS"),
        ("network_reconnect", "NETWORK_RECONNECT_TEST_NOT_PASS"),
        ("sustained_cpu_gpu_load", "SUSTAINED_CPU_GPU_LOAD_TEST_NOT_PASS"),
    ):
        if checks.get(key) != "PASS":
            blockers.append(blocker)

    return sorted(set(blockers))


def validate_profile(
    profile: dict[str, Any], thresholds: dict[str, Any]
) -> list[str]:
    failures = validate_shape(profile)
    if failures:
        return failures
    try:
        blockers = assess_exit_gate(profile, thresholds)
    except (KeyError, ProfileError, TypeError, ValueError) as exc:
        return [f"cannot assess WP5 Exit Gate: {exc}"]
    exit_gate = _as_dict(profile["exit_gate"], "$.exit_gate")
    expected_status = "PASS" if not blockers else "BLOCKED"
    if exit_gate.get("status") != expected_status:
        failures.append(f"$.exit_gate.status must be {expected_status}")
    recorded = exit_gate.get("blocking_reasons")
    if not isinstance(recorded, list) or sorted(
        set(str(item) for item in recorded)
    ) != blockers:
        failures.append(
            "$.exit_gate.blocking_reasons must exactly match computed blockers"
        )
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate the privacy-safe WP5 OWNER_NODE_PROFILE"
    )
    parser.add_argument("profile")
    parser.add_argument("--thresholds", default=str(DEFAULT_THRESHOLDS))
    parser.add_argument("--require-exit-gate", action="store_true")
    args = parser.parse_args(argv)

    try:
        profile = json.loads(Path(args.profile).read_text(encoding="utf-8"))
        thresholds = json.loads(Path(args.thresholds).read_text(encoding="utf-8"))
        if not isinstance(profile, dict) or not isinstance(thresholds, dict):
            raise ProfileError("profile and thresholds must be JSON objects")
        failures = validate_profile(profile, thresholds)
    except (OSError, json.JSONDecodeError, ProfileError) as exc:
        print(f"WP5 node profile validation failed: {exc}", file=sys.stderr)
        return 1

    if failures:
        print("WP5 node profile validation failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    blockers = assess_exit_gate(profile, thresholds)
    print("WP5 node profile validation passed.")
    if blockers:
        print("WP5 Exit Gate remains BLOCKED:")
        for blocker in blockers:
            print(f"- {blocker}")
        return 2 if args.require_exit_gate else 0
    print("WP5 Exit Gate: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
