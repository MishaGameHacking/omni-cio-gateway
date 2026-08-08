from __future__ import annotations

import json
from pathlib import Path

from scripts import assess_v10_wp8_secret_store_profile as assessor
from scripts import check_v10_wp8_secret_store_contract as wp8


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "architecture" / "V10_WP8_SECRET_STORE_CONTRACT.json"
EXECUTION_CONTRACT = ROOT / "docs" / "architecture" / "V10_WP8_EXECUTION_CONTRACT.md"
RUNBOOK = ROOT / "docs" / "operations" / "V10_WP8_SECRET_STORE_RUNBOOK.md"
PROVISIONER = ROOT / "infrastructure" / "windows" / "provision_wp8_secret_store.ps1"
MANAGER = ROOT / "infrastructure" / "windows" / "manage_wp8_secret.ps1"
ROLLBACK = ROOT / "infrastructure" / "windows" / "rollback_wp8_secret_store.ps1"
ASSESSOR = ROOT / "scripts" / "assess_v10_wp8_secret_store_profile.py"


def test_wp8_contract_guard_passes() -> None:
    assert wp8.validate() == []


def test_wp8_assets_exist() -> None:
    for path in (
        CONTRACT,
        EXECUTION_CONTRACT,
        RUNBOOK,
        PROVISIONER,
        MANAGER,
        ROLLBACK,
        ASSESSOR,
    ):
        assert path.is_file(), path


def test_wp8_provider_and_role_matrix_are_exact() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert contract["provider"] == {
        "type": "WINDOWS_DPAPI",
        "api": "System.Security.Cryptography.ProtectedData",
        "scope": "LOCAL_MACHINE",
        "authorization_boundary": "PROTECTED_NTFS_DACL",
        "local_machine_scope_is_not_principal_authorization": True,
        "additional_entropy": "NONE",
        "plaintext_cli_allowed": False,
        "plaintext_environment_allowed": False,
        "plaintext_log_allowed": False,
        "secret_hash_metadata_allowed": False,
        "ciphertext_in_github_allowed": False,
    }
    classes = {item["id"]: item for item in contract["secret_classes"]}
    assert classes["broker_read"]["consumer_role"] == "omni-cio-runtime"
    assert classes["broker_trading"]["consumer_role"] == "omni-cio-execution"
    for class_id in ("telegram_bot", "local_encryption_key", "external_source"):
        assert classes[class_id]["consumer_data_access"] == "NONE"
    assert all(item["real_value_required_for_wp8"] is False for item in classes.values())


def test_wp8_acceptance_preserves_protected_money_authority() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    acceptance = contract["acceptance"]
    assert acceptance["real_secret_values_used"] is False
    assert acceptance["future_service_activation_allowed"] is False
    assert acceptance["broker_write_activation_allowed"] is False
    assert acceptance["trading_methods"] is False
    assert acceptance["gateway_entrypoint"] == "app:app"


def test_provisioner_uses_local_machine_dpapi_plus_fail_closed_acl() -> None:
    text = PROVISIONER.read_text(encoding="utf-8")
    for required in (
        "ProtectedData]::Protect",
        "ProtectedData]::Unprotect",
        "DataProtectionScope]::LocalMachine",
        "SetAccessRuleProtection($true, $false)",
        "FileSystemRights]::ReadPermissions",
        "FileSystemRights]::ReadAttributes",
        "FileSystemRights]::ReadData",
        "CI_RUNNER_SECRET_DATA_READ_NOT_DENIED",
        "RUNTIME_ROLE_TRADING_SECRET_EXPOSURE",
        "EXECUTION_ROLE_READ_BROKER_SECRET_EXPOSURE",
        "BROAD_SECRET_READ_EXPOSURE",
        'return "ACCESS_DENIED"',
    ):
        assert required in text
    for forbidden in (
        "New-Service",
        "Start-Service",
        "REAL_TRADING_ENABLED=true",
        "TINVEST_TOKEN",
        "TINVEST_TRADING_TOKEN",
        "TELEGRAM_BOT_TOKEN",
    ):
        assert forbidden.lower() not in text.lower()


def test_manager_has_no_plaintext_value_parameter_and_zeroes_transient_plaintext() -> None:
    text = MANAGER.read_text(encoding="utf-8")
    param_block = text.split("param(", 1)[1].split("Set-StrictMode", 1)[0].lower()
    for forbidden in (
        "secretvalue",
        "secret_value",
        "tokenvalue",
        "token_value",
        "password",
        "api_key",
        "apikey",
        "connectionstring",
    ):
        assert forbidden not in param_block
    for required in (
        'if ($env:GITHUB_ACTIONS -eq "true")',
        "Read-Host -AsSecureString",
        "SecureStringToBSTR",
        "ZeroFreeBSTR",
        "[Array]::Clear($plainBytes",
        "DataProtectionScope]::LocalMachine",
        "File]::Replace",
        "Secret value/ciphertext output: NEVER",
    ):
        assert required in text


def test_rollback_refuses_real_secret_or_active_blob_cleanup() -> None:
    text = ROLLBACK.read_text(encoding="utf-8")
    for required in (
        "REAL_SECRET_PROVISIONED:",
        "ACTIVE_SECRET_BLOB_PRESENT:",
        "safe_to_cleanup",
        "WP6 secret root will be removed: NO",
        "WP6 identities/runner boundary will be changed: NO",
        "WP7 prerequisites/directories will be changed: NO",
    ):
        assert required in text
    assert "Remove-Item -LiteralPath $secretRoot" not in text
    assert "Remove-Item -LiteralPath $wp6Sentinel" not in text


def _passing_profile() -> dict:
    classes = []
    for class_id in sorted(assessor.EXPECTED_CLASSES):
        runtime_read = class_id == "broker_read"
        execution_read = class_id == "broker_trading"
        classes.append(
            {
                "secret_class": class_id,
                "directory_present": True,
                "sentinel_present": True,
                "intended_read_grant": True,
                "runtime_read_grant": runtime_read,
                "execution_read_grant": execution_read,
                "runner_read_data_grant": False,
                "runner_write_grant": False,
                "broad_read_exposure": False,
                "runner_data_read": "ACCESS_DENIED",
                "lifecycle_state": "UNPROVISIONED",
                "lifecycle_version": 0,
                "real_secret_provisioned": False,
            }
        )
    return {
        "schema_version": "1",
        "mode": "VERIFY",
        "status": "PASS",
        "reasons": [],
        "provider": "WINDOWS_DPAPI_LOCAL_MACHINE_PLUS_PROTECTED_DACL",
        "runner_process": True,
        "runtime_role": {"present": True, "enabled": False, "administrator": False},
        "execution_role": {"present": True, "enabled": False, "administrator": False},
        "rotation_rehearsal": {"broker_read": True, "telegram_bot": True},
        "classes": classes,
        "real_secret_values_used": False,
        "privacy": {
            "raw_usernames_collected": False,
            "sids_emitted": False,
            "hostnames_collected": False,
            "addresses_collected": False,
            "secret_values_collected": False,
            "secret_hashes_collected": False,
            "ciphertext_collected": False,
            "account_ids_collected": False,
            "private_data_collected": False,
            "process_dumps_collected": False,
        },
    }


def test_assessor_accepts_only_complete_sanitized_runner_evidence() -> None:
    assert assessor.assess(_passing_profile()) == []


def test_assessor_rejects_secret_authority_and_privacy_regressions() -> None:
    profile = _passing_profile()
    profile["classes"][0]["runner_read_data_grant"] = True
    profile["privacy"]["ciphertext_collected"] = True
    profile["real_secret_values_used"] = True
    blockers = assessor.assess(profile)
    assert any("RUNNER_READ_DATA_GRANT" in item for item in blockers)
    assert "PRIVACY_FLAG_NOT_FALSE:ciphertext_collected" in blockers
    assert "REAL_SECRET_VALUES_USED" in blockers


def test_assessor_rejects_forbidden_identity_or_secret_fields() -> None:
    profile = _passing_profile()
    profile["username"] = "must-never-appear"
    profile["classes"][0]["ciphertext"] = "must-never-appear"
    blockers = assessor.assess(profile)
    assert any(item.startswith("FORBIDDEN_PROFILE_FIELD:") for item in blockers)
