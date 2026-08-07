from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_v10_node_profile as node_profile


ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "docs" / "architecture" / "V10_OWNER_NODE_PROFILE.baseline.json"
THRESHOLDS_PATH = ROOT / "infrastructure" / "windows" / "wp5_node_thresholds.json"


def test_persisted_owner_node_baseline_is_valid_and_fail_closed() -> None:
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    thresholds = json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8"))

    assert node_profile.validate_profile(profile, thresholds) == []
    assert profile["capture_mode"] == "PASSIVE_READ_ONLY"
    assert profile["exit_gate"]["status"] == "BLOCKED"
    assert profile["privacy"] == {
        "mac_or_ip_collected": False,
        "recovery_key_material_collected": False,
        "secret_values_collected": False,
        "serial_numbers_collected": False,
        "usernames_or_hostnames_collected": False,
    }

    blockers = set(profile["exit_gate"]["blocking_reasons"])
    assert "BITLOCKER_PROTECTION_NOT_ON" in blockers
    assert "SYSTEM_VOLUME_NOT_FULLY_ENCRYPTED" in blockers
    assert "REBOOT_TEST_NOT_PASS" in blockers
    assert "NETWORK_RECONNECT_TEST_NOT_PASS" in blockers
    assert "SUSTAINED_CPU_GPU_LOAD_TEST_NOT_PASS" in blockers
