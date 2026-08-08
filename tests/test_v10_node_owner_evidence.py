from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts import apply_v10_node_owner_evidence as owner_evidence
from scripts import validate_v10_node_profile as node_profile


ROOT = Path(__file__).resolve().parents[1]
BASELINE = json.loads(
    (ROOT / "docs" / "architecture" / "V10_OWNER_NODE_PROFILE.baseline.json").read_text(
        encoding="utf-8"
    )
)
EVIDENCE = json.loads(
    (
        ROOT
        / "docs"
        / "architecture"
        / "V10_WP5_OWNER_PHYSICAL_EVIDENCE.json"
    ).read_text(encoding="utf-8")
)
THRESHOLDS = json.loads(
    (ROOT / "infrastructure" / "windows" / "wp5_node_thresholds.json").read_text(
        encoding="utf-8"
    )
)


def test_current_owner_evidence_is_applied_and_passes_thermal_gate() -> None:
    profile = copy.deepcopy(BASELINE)
    load_result = owner_evidence.apply_owner_evidence(profile, EVIDENCE, THRESHOLDS)

    assert profile["capture_mode"] == "PASSIVE_PLUS_OWNER_EVIDENCE"
    encryption = profile["security"]["full_disk_encryption"]
    assert encryption["provider"] == "BITLOCKER"
    assert encryption["volume_status"] == "FullyEncrypted"
    assert encryption["protection_status"] == "ON"
    assert encryption["encryption_percentage"] == 100.0
    assert encryption["encryption_method"] == "XtsAes128"
    assert encryption["recovery_key_custody_status"] == "OWNER_CONFIRMED_SEPARATE"
    assert profile["power"]["battery_conservation"] == "ENABLED"
    assert profile["power"]["restart_after_power_loss"] == "NOT_SUPPORTED_BY_FIRMWARE"
    assert profile["checks"]["reboot"] == "PASS"
    assert profile["checks"]["network_reconnect"] == "PASS"
    assert load_result == "PASS"
    assert profile["checks"]["sustained_cpu_gpu_load"] == "PASS"


def test_safe_complete_load_evidence_can_pass_deterministically() -> None:
    evidence = copy.deepcopy(EVIDENCE)
    load = evidence["checks"]["sustained_cpu_gpu_load"]
    load["duration_seconds"] = 1800
    load["cpu_peak_c"] = 90.0
    load["cpu_throttling_max_percent"] = 1.0
    load["cpu_throttling_average_percent"] = 0.5
    load["gpu_peak_c"] = 78.0

    assert owner_evidence.assess_load_evidence(evidence, THRESHOLDS) == "PASS"


def test_gpu_peak_is_required_for_combined_load_acceptance() -> None:
    evidence = copy.deepcopy(EVIDENCE)
    load = evidence["checks"]["sustained_cpu_gpu_load"]
    load["cpu_peak_c"] = 90.0
    load["cpu_throttling_average_percent"] = 0.0
    load["gpu_peak_c"] = None

    assert owner_evidence.assess_load_evidence(evidence, THRESHOLDS) == "FAIL"


def test_owner_evidence_is_strict_and_rejects_extra_secret_shaped_fields() -> None:
    evidence = copy.deepcopy(EVIDENCE)
    evidence["recovery_key"] = "must-never-be-recorded"

    with pytest.raises(owner_evidence.EvidenceError):
        owner_evidence.validate_owner_evidence(evidence)


def test_owner_evidence_rejects_unprotected_bitlocker_state() -> None:
    evidence = copy.deepcopy(EVIDENCE)
    evidence["full_disk_encryption"]["protection_status"] = "OFF"

    with pytest.raises(owner_evidence.EvidenceError):
        owner_evidence.validate_owner_evidence(evidence)


def test_firmware_not_supported_state_is_explicitly_acceptable() -> None:
    profile = copy.deepcopy(BASELINE)
    profile["capture_mode"] = "PASSIVE_PLUS_OWNER_EVIDENCE"
    profile["power"]["restart_after_power_loss"] = "NOT_SUPPORTED_BY_FIRMWARE"
    blockers = node_profile.assess_exit_gate(profile, THRESHOLDS)

    assert "RESTART_AFTER_POWER_LOSS_NOT_VERIFIED_ENABLED" not in blockers
    assert node_profile.validate_shape(profile) == []
