from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.assess_v10_wp9a_operations_profile import assess

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads(
    (ROOT / "docs" / "architecture" / "V10_WP9A_OPERATIONS_CONTRACT.json").read_text(
        encoding="utf-8"
    )
)
WP5 = json.loads(
    (ROOT / "infrastructure" / "windows" / "wp5_node_thresholds.json").read_text(
        encoding="utf-8"
    )
)


def safe_profile() -> dict:
    return {
        "schema_version": "1",
        "work_package": "WP9A",
        "windows_update": {
            "service_present": True,
            "service_disabled": False,
            "reboot_state_known": True,
            "reboot_required": False,
            "reboot_source": "WINDOWS_UPDATE_AGENT",
            "legacy_pending_file_rename_present": False,
        },
        "time": {"service_running": True, "offset_ms": 10.0},
        "runner": {
            "service_present": True,
            "service_running": True,
            "disable_update": False,
            "version_known": True,
            "version": "2.336.0",
            "update_diagnostics_present": False,
        },
        "postgresql": {
            "present": True,
            "version_known": True,
            "version": "18.4",
            "major": 18,
            "ready": True,
        },
        "nvidia": {
            "present": True,
            "driver_version_known": True,
            "driver_version": "999.1",
            "temperature_c": 50.0,
            "vram_used_percent": 5.0,
        },
        "ollama": {"present": False, "not_ready_allowed": True},
        "resources": {
            "system_disk_free_gib": 100.0,
            "system_disk_free_percent": 30.0,
            "memory_used_percent": 40.0,
        },
        "wp9": {"present": True, "status": "DEGRADED", "fresh": True},
        "privacy": {
            "raw_usernames_collected": False,
            "hostnames_collected": False,
            "addresses_collected": False,
            "credential_values_collected": False,
            "ciphertext_collected": False,
            "account_ids_collected": False,
            "private_portfolio_data_collected": False,
            "process_command_lines_collected": False,
            "process_dumps_collected": False,
        },
    }


def test_safe_profile_passes_with_nonblocking_runner_log_warning() -> None:
    result = assess(safe_profile(), POLICY, WP5)
    assert result["status"] == "PASS"
    assert result["blockers"] == []
    assert "RUNNER_SELFUPDATE_LOG_NOT_PRESENT" in result["warnings"]
    assert result["sensitive_operations_ready"] is True


def test_time_drift_blocks_sensitive_readiness() -> None:
    profile = safe_profile()
    profile["time"]["offset_ms"] = 2500.0
    result = assess(profile, POLICY, WP5)
    assert "TIME_DRIFT_BLOCK" in result["blockers"]
    assert result["sensitive_operations_ready"] is False


def test_authoritative_update_reboot_blocks_sensitive_readiness() -> None:
    profile = safe_profile()
    profile["windows_update"]["reboot_required"] = True
    result = assess(profile, POLICY, WP5)
    assert "WINDOWS_UPDATE_REBOOT_REQUIRED" in result["blockers"]
    assert result["sensitive_operations_ready"] is False


def test_unknown_update_reboot_state_fails_closed() -> None:
    profile = safe_profile()
    profile["windows_update"]["reboot_state_known"] = False
    profile["windows_update"]["reboot_required"] = None
    result = assess(profile, POLICY, WP5)
    assert "WINDOWS_UPDATE_REBOOT_STATE_UNKNOWN" in result["blockers"]


def test_legacy_pending_file_rename_is_diagnostic_only() -> None:
    profile = safe_profile()
    profile["windows_update"]["legacy_pending_file_rename_present"] = True
    result = assess(profile, POLICY, WP5)
    assert result["status"] == "PASS"
    assert "LEGACY_PENDING_FILE_RENAME_PRESENT" in result["warnings"]


def test_premature_ollama_install_fails_closed() -> None:
    profile = safe_profile()
    profile["ollama"]["present"] = True
    result = assess(profile, POLICY, WP5)
    assert "OLLAMA_PREMATURELY_INSTALLED" in result["blockers"]


def test_private_evidence_flag_fails_closed() -> None:
    profile = safe_profile()
    profile["privacy"]["account_ids_collected"] = True
    result = assess(profile, POLICY, WP5)
    assert "PRIVACY_BOUNDARY_VIOLATION" in result["blockers"]


def test_memory_and_disk_use_wp5_block_thresholds() -> None:
    profile = safe_profile()
    profile["resources"]["system_disk_free_gib"] = (
        float(WP5["storage"]["block_free_gib"]) - 1
    )
    profile["resources"]["memory_used_percent"] = float(
        WP5["memory"]["block_new_heavy_work_percent"]
    )
    result = assess(profile, POLICY, WP5)
    assert "DISK_FREE_BLOCK" in result["blockers"]
    assert "MEMORY_HEAVY_WORK_BLOCK" in result["blockers"]


def test_wp9_supervision_must_remain_fresh_and_truthful() -> None:
    profile = copy.deepcopy(safe_profile())
    profile["wp9"] = {"present": True, "status": "UNKNOWN", "fresh": False}
    result = assess(profile, POLICY, WP5)
    assert "WP9_HEALTH_STATUS_INVALID" in result["blockers"]
    assert "WP9_HEALTH_EVIDENCE_STALE" in result["blockers"]
