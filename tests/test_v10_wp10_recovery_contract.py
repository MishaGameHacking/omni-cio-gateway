from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.check_v10_wp10_recovery_contract import ContractError, validate_contract

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "architecture" / "V10_WP10_RECOVERY_CONTRACT.json"


def _contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_wp10_contract_accepts_canonical_policy() -> None:
    validate_contract(_contract())


@pytest.mark.parametrize(
    ("section", "field", "value", "reason"),
    [
        ("authority", "trading_methods", True, "TRADING_METHODS_ENABLED"),
        ("authority", "real_trading_enabled", True, "REAL_TRADING_ENABLED"),
        ("authority", "broker_authority_change", True, "BROKER_AUTHORITY_CHANGED"),
        ("recovery_objectives", "rpo_minutes", 120, "RECOVERY_OBJECTIVE_DRIFT"),
        ("recovery_objectives", "rto_minutes", 480, "RECOVERY_OBJECTIVE_DRIFT"),
        ("postgresql", "production_database_binding", "READY", "PRODUCTION_DB_BOUND_EARLY"),
        ("postgresql", "production_job_binding", "READY", "PRODUCTION_JOB_BOUND_EARLY"),
        ("automation", "target_cadence_minutes", 61, "BACKUP_CADENCE_EXCEEDS_RPO"),
        ("automation", "production_schedule_activation_before_product_binding", True, "PRODUCTION_SCHEDULE_ACTIVATED_EARLY"),
        ("off_device", "system_volume_allowed", True, "OFFDEVICE_BOUNDARY_VIOLATION"),
        ("off_device", "format_disk_forbidden", False, "OFFDEVICE_GUARD_MISSING"),
        ("off_device", "repartition_disk_forbidden", False, "OFFDEVICE_GUARD_MISSING"),
        ("off_device", "ci_may_synthesize_owner_evidence", True, "OFFDEVICE_BOUNDARY_VIOLATION"),
        ("acceptance", "owner_physical_recovery_required", False, "EXIT_GATE_WEAKENED"),
        ("acceptance", "wp11_locked_until_complete", False, "EXIT_GATE_WEAKENED"),
    ],
)
def test_wp10_contract_rejects_boundary_regressions(
    section: str, field: str, value: object, reason: str
) -> None:
    mutated = copy.deepcopy(_contract())
    mutated[section][field] = value
    with pytest.raises(ContractError, match=reason):
        validate_contract(mutated)


def test_wp10_contract_cannot_claim_completion_before_owner_gate() -> None:
    mutated = _contract()
    mutated["status"] = "COMPLETE"
    with pytest.raises(ContractError, match="WP10_PREMATURE_ACCEPTANCE_STATUS"):
        validate_contract(mutated)


def test_wp10_separates_github_private_state_and_secrets() -> None:
    contract = _contract()
    separation = contract["source_separation"]
    assert separation["github_is_private_state_backup"] is False
    assert separation["github_is_secret_backup"] is False
    assert separation["ci_artifact_is_private_state_backup"] is False
    validate_contract(contract)


def test_wp10_owner_evidence_is_non_synthetic_and_sanitized() -> None:
    contract = _contract()
    assert contract["off_device"]["ci_may_synthesize_owner_evidence"] is False
    assert contract["owner_evidence"]["missing_evidence_state"] == "OWNER_ACTION_REQUIRED"
    assert contract["owner_evidence"]["recovery_key_value_forbidden"] is True
    validate_contract(contract)
