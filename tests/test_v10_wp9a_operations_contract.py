from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.check_v10_wp9a_operations_contract import ContractError, validate_contract

ROOT = Path(__file__).resolve().parents[1]


def _fixtures() -> tuple[dict, dict]:
    contract = json.loads(
        (
            ROOT
            / "docs"
            / "architecture"
            / "V10_WP9A_OPERATIONS_CONTRACT.json"
        ).read_text(encoding="utf-8")
    )
    wp5 = json.loads(
        (
            ROOT / "infrastructure" / "windows" / "wp5_node_thresholds.json"
        ).read_text(encoding="utf-8")
    )
    return contract, wp5


def test_wp9a_contract_accepts_canonical_policy() -> None:
    contract, wp5 = _fixtures()
    validate_contract(contract, wp5)


@pytest.mark.parametrize(
    ("path", "value", "reason"),
    [
        (("authority", "trading_methods"), True, "TRADING_METHODS_ENABLED"),
        (
            ("authority", "real_money_authority_change"),
            True,
            "REAL_MONEY_AUTHORITY_CHANGED",
        ),
        (
            ("restart_and_crash_loop", "max_attempts"),
            99,
            "WP9_BOUNDED_RESTART_POLICY_CHANGED",
        ),
        (
            ("restart_and_crash_loop", "backoff_seconds"),
            0,
            "WP9_BOUNDED_RESTART_POLICY_CHANGED",
        ),
        (
            ("postgresql", "automatic_update_by_omni_cio"),
            True,
            "POSTGRES_AUTOUPDATE_ENABLED",
        ),
        (
            ("ollama", "runtime_required_now"),
            True,
            "OLLAMA_PREMATURE_RUNTIME_REQUIREMENT",
        ),
        (
            ("nvidia_driver", "automatic_driver_update_by_omni_cio"),
            True,
            "NVIDIA_AUTOUPDATE_ENABLED",
        ),
        (
            ("logging", "ci_private_payload_upload_forbidden"),
            False,
            "CI_PRIVATE_PAYLOAD_UPLOAD_NOT_FORBIDDEN",
        ),
        (
            (
                "update_impact_gate",
                "update_availability_is_never_real_submit_authority",
            ),
            False,
            "UPDATE_AUTHORITY_FIREWALL_MISSING",
        ),
    ],
)
def test_wp9a_contract_rejects_boundary_regressions(
    path: tuple[str, str], value: object, reason: str
) -> None:
    contract, wp5 = _fixtures()
    mutated = copy.deepcopy(contract)
    mutated[path[0]][path[1]] = value
    with pytest.raises(ContractError, match=reason):
        validate_contract(mutated, wp5)


def test_wp9a_contract_rejects_relaxed_clock_threshold() -> None:
    contract, wp5 = _fixtures()
    mutated = copy.deepcopy(contract)
    mutated["time"]["block_sensitive_absolute_offset_ms"] = 5000
    with pytest.raises(ContractError, match="WP5_CLOCK_THRESHOLD_DRIFT"):
        validate_contract(mutated, wp5)


def test_wp9a_logging_allowlist_is_disjoint_from_forbidden_fields() -> None:
    contract, wp5 = _fixtures()
    mutated = copy.deepcopy(contract)
    mutated["logging"]["allowed_fields"].append("token")
    with pytest.raises(ContractError, match="LOG_FIELD_POLICY_INVALID"):
        validate_contract(mutated, wp5)


def test_wp9a_logging_integrity_and_retention_are_locked() -> None:
    contract, wp5 = _fixtures()
    for field, value, reason in (
        ("integrity", "NONE", "LOG_INTEGRITY_POLICY_MISSING"),
        ("retained_files", 99, "LOG_FILE_RETENTION_COUNT_CHANGED"),
        ("retention_days", 365, "LOG_RETENTION_DAYS_CHANGED"),
        ("max_file_mib", 100, "LOG_MAX_FILE_SIZE_CHANGED"),
    ):
        mutated = copy.deepcopy(contract)
        mutated["logging"][field] = value
        with pytest.raises(ContractError, match=reason):
            validate_contract(mutated, wp5)


def test_wp9a_missing_later_runtime_is_allowed_by_contract() -> None:
    contract, wp5 = _fixtures()
    assert contract["ollama"]["not_installed_is_acceptable"] is True
    assert contract["ollama"]["installation_or_activation_in_wp9a_forbidden"] is True
    validate_contract(contract, wp5)
