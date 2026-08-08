from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts import validate_v10_node_profile as node_profile


ROOT = Path(__file__).resolve().parents[1]
THRESHOLDS = json.loads(
    (ROOT / "infrastructure" / "windows" / "wp5_node_thresholds.json").read_text(
        encoding="utf-8"
    )
)


def pass_profile() -> dict[str, object]:
    return {
        "schema_version": "1",
        "captured_at_utc": "2026-08-07T13:00:00+00:00",
        "capture_mode": "PASSIVE_READ_ONLY",
        "node_role": "OWNER_PERSONAL_NODE",
        "privacy": {
            "serial_numbers_collected": False,
            "mac_or_ip_collected": False,
            "usernames_or_hostnames_collected": False,
            "secret_values_collected": False,
            "recovery_key_material_collected": False,
        },
        "hardware": {
            "cpu": {
                "model": "Example CPU",
                "physical_cores": 8,
                "logical_processors": 16,
            },
            "memory": {"total_gib": 32.0},
            "gpu": {
                "present": True,
                "vendor": "NVIDIA",
                "model": "Example GPU",
                "vram_mib": 6144,
                "driver_version": "example-driver",
                "idle_temperature_c": 42.0,
                "telemetry_source": "NVIDIA_SMI",
            },
            "storage": {
                "system_volume": {
                    "capacity_gib": 953.0,
                    "free_gib": 400.0,
                    "free_percent": 41.97,
                    "health_status": "Healthy",
                },
                "physical_disks": [
                    {
                        "size_gib": 953.0,
                        "media_type": "SSD",
                        "health_status": "Healthy",
                        "operational_status": "OK",
                    }
                ],
            },
        },
        "os": {
            "product_name": "Microsoft Windows 11 Pro",
            "version": "example-version",
            "build": "example-build",
            "architecture": "64-bit",
            "last_boot_utc": "2026-08-07T08:00:00+00:00",
        },
        "security": {
            "full_disk_encryption": {
                "provider": "BITLOCKER",
                "volume_status": "FullyEncrypted",
                "protection_status": "ON",
                "encryption_percentage": 100,
                "encryption_method": "XtsAes256",
                "recovery_key_custody_status": "OWNER_CONFIRMED_SEPARATE",
            },
            "firewall": {
                "profiles": [
                    {
                        "name": "Domain",
                        "enabled": True,
                        "default_inbound_action": "Block",
                        "default_outbound_action": "Allow",
                    },
                    {
                        "name": "Private",
                        "enabled": True,
                        "default_inbound_action": "Block",
                        "default_outbound_action": "Allow",
                    },
                    {
                        "name": "Public",
                        "enabled": True,
                        "default_inbound_action": "Block",
                        "default_outbound_action": "Allow",
                    },
                ],
                "wildcard_tcp_listener_count": 0,
            },
            "private_at_rest": {
                "classification": "BROKER_SECRETS_PRIVATE_DB_CORTEX_HISTORY_PRIVATE",
                "acl_state": "WP6_NOT_YET_CONFIGURED",
            },
        },
        "time": {
            "service_status": "RUNNING",
            "source_class": "WINDOWS_NTP",
            "measured_against": "time.windows.com",
            "offset_ms": 40.0,
            "utc_policy": "CANONICAL_EVENT_TIMESTAMPS_UTC",
            "sensitive_operation_gate": "PASS",
        },
        "network": {
            "wired_connected": True,
            "wired_link_speed_mbps": 1000,
            "public_exposure_assessment": "BASELINE_FIREWALL_ONLY_NO_V10_RUNTIME",
        },
        "power": {
            "battery_present": True,
            "ac_online": True,
            "active_power_scheme": "Balanced",
            "battery_conservation": "ENABLED",
            "restart_after_power_loss": "ENABLED",
        },
        "thermal": {
            "acpi_zone_max_idle_c": 45.0,
            "gpu_idle_c": 42.0,
            "observation": "PASSIVE_BASELINE",
        },
        "checks": {
            "disk_health": "PASS",
            "reboot": "PASS",
            "network_reconnect": "PASS",
            "sustained_cpu_gpu_load": "PASS",
        },
        "thresholds_ref": "infrastructure/windows/wp5_node_thresholds.json",
        "exit_gate": {"status": "PASS", "blocking_reasons": []},
    }


def assess(profile: dict[str, object]) -> list[str]:
    return node_profile.assess_exit_gate(profile, THRESHOLDS)


def normalize_exit_gate(profile: dict[str, object]) -> None:
    blockers = assess(profile)
    profile["exit_gate"] = {
        "status": "PASS" if not blockers else "BLOCKED",
        "blocking_reasons": blockers,
    }


def test_complete_safe_profile_passes_exit_gate() -> None:
    profile = pass_profile()
    assert assess(profile) == []
    assert node_profile.validate_profile(profile, THRESHOLDS) == []


def test_initial_passive_profile_can_be_valid_but_exit_gate_blocked() -> None:
    profile = pass_profile()
    profile["checks"] = {
        "disk_health": "PASS",
        "reboot": "NOT_RUN",
        "network_reconnect": "NOT_RUN",
        "sustained_cpu_gpu_load": "NOT_RUN",
    }
    normalize_exit_gate(profile)

    assert profile["exit_gate"]["status"] == "BLOCKED"  # type: ignore[index]
    assert node_profile.validate_profile(profile, THRESHOLDS) == []


def test_clock_drift_over_two_seconds_is_fail_closed() -> None:
    profile = pass_profile()
    profile["time"]["offset_ms"] = 2500.0  # type: ignore[index]
    profile["time"]["sensitive_operation_gate"] = "BLOCK_DRIFT"  # type: ignore[index]
    normalize_exit_gate(profile)

    blockers = assess(profile)
    assert "CLOCK_DRIFT_EXCEEDS_SENSITIVE_OPERATION_LIMIT" in blockers
    assert "CLOCK_GATE_STATE_INCONSISTENT" not in blockers


def test_stopped_time_service_requires_unknown_time_gate() -> None:
    profile = pass_profile()
    profile["time"]["service_status"] = "STOPPED"  # type: ignore[index]
    profile["time"]["offset_ms"] = 50.0  # type: ignore[index]
    profile["time"]["sensitive_operation_gate"] = "BLOCK_UNKNOWN_TIME"  # type: ignore[index]
    normalize_exit_gate(profile)

    blockers = assess(profile)
    assert "WINDOWS_TIME_SERVICE_NOT_RUNNING" in blockers
    assert "CLOCK_GATE_STATE_INCONSISTENT" not in blockers


def test_bitlocker_low_disk_and_unrun_checks_block_exit() -> None:
    profile = pass_profile()
    profile["security"]["full_disk_encryption"]["protection_status"] = "OFF"  # type: ignore[index]
    profile["hardware"]["storage"]["system_volume"]["free_gib"] = 10.0  # type: ignore[index]
    profile["hardware"]["storage"]["system_volume"]["free_percent"] = 5.0  # type: ignore[index]
    profile["checks"]["reboot"] = "NOT_RUN"  # type: ignore[index]
    normalize_exit_gate(profile)

    blockers = assess(profile)
    assert "BITLOCKER_PROTECTION_NOT_ON" in blockers
    assert "SYSTEM_VOLUME_FREE_GIB_BELOW_BLOCK_LIMIT" in blockers
    assert "SYSTEM_VOLUME_FREE_PERCENT_BELOW_BLOCK_LIMIT" in blockers
    assert "REBOOT_TEST_NOT_PASS" in blockers


def test_privacy_guard_rejects_identifiers_and_recovery_material() -> None:
    for injected in (
        {"serial_number": "example"},
        {"network_note": "adapter 00:11:22:33:44:55"},
        {"network_note": "address 192.168.1.20"},
        {"path_note": r"C:\Users\owner\private"},
        {"recovery_key": "never-collect-this"},
    ):
        profile = copy.deepcopy(pass_profile())
        profile.update(injected)
        failures = node_profile.validate_shape(profile)
        assert any("forbidden" in failure.lower() for failure in failures), failures


def test_exit_gate_record_must_exactly_match_computed_blockers() -> None:
    profile = pass_profile()
    profile["checks"]["reboot"] = "NOT_RUN"  # type: ignore[index]
    profile["exit_gate"] = {"status": "PASS", "blocking_reasons": []}

    failures = node_profile.validate_profile(profile, THRESHOLDS)
    assert any("exit_gate.status" in failure for failure in failures)
    assert any("blocking_reasons" in failure for failure in failures)
