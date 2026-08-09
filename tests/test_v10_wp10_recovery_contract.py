from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.check_v10_wp10_recovery_contract import ContractError, validate_contract

ROOT = Path(__file__).resolve().parents[1]


def _fixtures() -> tuple[dict, dict, dict]:
    contract = json.loads(
        (ROOT / "docs" / "architecture" / "V10_WP10_RECOVERY_CONTRACT.json").read_text(
            encoding="utf-8"
        )
    )
    wp8 = json.loads(
        (
            ROOT / "docs" / "architecture" / "V10_WP8_SECRET_STORE_CONTRACT.json"
        ).read_text(encoding="utf-8")
    )
    wp9a = json.loads(
        (
            ROOT / "docs" / "architecture" / "V10_WP9A_OPERATIONS_CONTRACT.json"
        ).read_text(encoding="utf-8")
    )
    return contract, wp8, wp9a


def test_wp10_contract_accepts_canonical_policy() -> None:
    contract, wp8, wp9a = _fixtures()
    validate_contract(contract, wp8, wp9a)


@pytest.mark.parametrize(
    ("section", "field", "value", "reason"),
    [
        ("authority", "trading_methods", True, "TRADING_METHODS_ENABLED"),
        ("authority", "real_trading_enabled", True, "REAL_TRADING_ENABLED"),
        (
            "authority",
            "real_money_authority_change",
            True,
            "REAL_MONEY_AUTHORITY_CHANGED",
        ),
        ("recovery_objectives", "rpo_minutes", 1440, "WP10_RPO_CHANGED"),
        ("recovery_objectives", "rto_minutes", 15, "WP10_RTO_CHANGED"),
        (
            "postgresql",
            "production_database_binding",
            "ACTIVE_NOW",
            "WP13_DATABASE_BINDING_SCOPE_LEAK",
        ),
        (
            "postgresql",
            "cluster_role_password_backup_forbidden",
            False,
            "POSTGRES_ROLE_PASSWORD_BACKUP_NOT_FORBIDDEN",
        ),
        (
            "local_staging",
            "production_runner_read_access",
            True,
            "RUNNER_PRIVATE_BACKUP_ACCESS_ENABLED",
        ),
        (
            "off_device",
            "system_volume_allowed",
            True,
            "SYSTEM_VOLUME_ACCEPTED_AS_OFFDEVICE",
        ),
        (
            "off_device",
            "runner_backup_payload_read_allowed",
            True,
            "RUNNER_OFFDEVICE_PAYLOAD_ACCESS_ENABLED",
        ),
    ],
)
def test_wp10_contract_rejects_boundary_regressions(
    section: str, field: str, value: object, reason: str
) -> None:
    contract, wp8, wp9a = _fixtures()
    mutated = copy.deepcopy(contract)
    mutated[section][field] = value
    with pytest.raises(ContractError, match=reason):
        validate_contract(mutated, wp8, wp9a)


def test_wp10_contract_rejects_secret_field_in_manifest_allowlist() -> None:
    contract, wp8, wp9a = _fixtures()
    mutated = copy.deepcopy(contract)
    mutated["bundle"]["manifest_allowed_fields"].append("token")
    with pytest.raises(ContractError, match="BACKUP_MANIFEST_FIELD_POLICY_INVALID"):
        validate_contract(mutated, wp8, wp9a)


def test_wp10_contract_rejects_unbounded_retention() -> None:
    contract, wp8, wp9a = _fixtures()
    mutated = copy.deepcopy(contract)
    mutated["retention"]["maximum_successful_bundles_per_target"] = 9999
    with pytest.raises(ContractError, match="BACKUP_RETENTION_COUNT_UNSAFE"):
        validate_contract(mutated, wp8, wp9a)


def test_wp10_contract_requires_full_bitlocker_protection() -> None:
    contract, wp8, wp9a = _fixtures()
    mutated = copy.deepcopy(contract)
    mutated["off_device"]["bitlocker_volume_status_required"] = "EncryptionInProgress"
    with pytest.raises(ContractError, match="OFFDEVICE_FULL_ENCRYPTION_NOT_REQUIRED"):
        validate_contract(mutated, wp8, wp9a)


def test_wp10_contract_keeps_wp11_locked() -> None:
    contract, wp8, wp9a = _fixtures()
    mutated = copy.deepcopy(contract)
    mutated["next_wp"]["early_start_forbidden"] = False
    with pytest.raises(ContractError, match="WP11_EARLY_START_NOT_FORBIDDEN"):
        validate_contract(mutated, wp8, wp9a)
