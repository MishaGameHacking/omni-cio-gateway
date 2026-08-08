from __future__ import annotations

import json
from pathlib import Path
import re
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "docs" / "architecture" / "V10_WP8_SECRET_STORE_CONTRACT.json"
WP6_PATH = ROOT / "docs" / "architecture" / "V10_WP6_IDENTITY_PRIVILEGE_CONTRACT.json"
EXECUTION_CONTRACT = ROOT / "docs" / "architecture" / "V10_WP8_EXECUTION_CONTRACT.md"
RUNBOOK = ROOT / "docs" / "operations" / "V10_WP8_SECRET_STORE_RUNBOOK.md"
PROVISIONER = ROOT / "infrastructure" / "windows" / "provision_wp8_secret_store.ps1"
MANAGER = ROOT / "infrastructure" / "windows" / "manage_wp8_secret.ps1"
ROLLBACK = ROOT / "infrastructure" / "windows" / "rollback_wp8_secret_store.ps1"
DECISIONS = ROOT / "docs" / "architecture" / "DECISIONS.md"


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _require(failures: list[str], condition: bool, message: str) -> None:
    if not condition:
        failures.append(message)


def validate() -> list[str]:
    failures: list[str] = []
    try:
        contract = _json(CONTRACT_PATH)
        wp6 = _json(WP6_PATH)
        provisioner = _text(PROVISIONER)
        manager = _text(MANAGER)
        rollback = _text(ROLLBACK)
        execution_contract = _text(EXECUTION_CONTRACT)
        runbook = _text(RUNBOOK)
        decisions = _text(DECISIONS)
    except (OSError, json.JSONDecodeError, AssertionError) as exc:
        return [f"WP8 contract asset load failed: {exc}"]

    provider = contract.get("provider", {})
    paths = contract.get("paths", {})
    identities = contract.get("identities", {})
    acl = contract.get("acl", {})
    lifecycle = contract.get("lifecycle", {})
    acceptance = contract.get("acceptance", {})
    wp6_paths = wp6.get("local_paths", {})
    wp6_roles = wp6.get("roles", {})

    _require(failures, contract.get("schema_version") == "1", "schema_version must be '1'")
    _require(failures, contract.get("work_package") == "WP8", "work_package must be WP8")
    _require(failures, provider.get("type") == "WINDOWS_DPAPI", "provider must be WINDOWS_DPAPI")
    _require(
        failures,
        provider.get("api") == "System.Security.Cryptography.ProtectedData",
        "provider API must be ProtectedData",
    )
    _require(failures, provider.get("scope") == "LOCAL_MACHINE", "DPAPI scope must be LOCAL_MACHINE")
    _require(
        failures,
        provider.get("authorization_boundary") == "PROTECTED_NTFS_DACL",
        "authorization boundary must be protected NTFS DACL",
    )
    _require(
        failures,
        provider.get("local_machine_scope_is_not_principal_authorization") is True,
        "LocalMachine DPAPI caveat must be explicit",
    )
    for key in (
        "plaintext_cli_allowed",
        "plaintext_environment_allowed",
        "plaintext_log_allowed",
        "secret_hash_metadata_allowed",
        "ciphertext_in_github_allowed",
    ):
        _require(failures, provider.get(key) is False, f"provider.{key} must be false")

    _require(
        failures,
        paths.get("secret_root") == wp6_paths.get("secret_root"),
        "WP8 must reuse WP6 secret root",
    )
    _require(
        failures,
        paths.get("wp6_execution_sentinel") == wp6_paths.get("execution_acl_sentinel"),
        "WP8 must preserve WP6 execution sentinel",
    )
    _require(
        failures,
        identities.get("runtime_role") == wp6_roles.get("runtime", {}).get("role_name"),
        "WP8 runtime role must match WP6",
    )
    _require(
        failures,
        identities.get("execution_role") == wp6_roles.get("execution", {}).get("role_name"),
        "WP8 execution role must match WP6",
    )

    expected_classes = [
        ("broker_read", "omni-cio-runtime", "READ", True),
        ("broker_trading", "omni-cio-execution", "READ", False),
        ("telegram_bot", "SEALED_UNTIL_BLOCK_F", "NONE", True),
        ("local_encryption_key", "SEALED_UNTIL_OWNING_WP", "NONE", False),
        ("external_source", "SEALED_UNTIL_OWNING_WP", "NONE", False),
    ]
    classes = contract.get("secret_classes", [])
    actual_classes = []
    for item in classes if isinstance(classes, list) else []:
        actual_classes.append(
            (
                item.get("id"),
                item.get("consumer_role"),
                item.get("consumer_data_access"),
                item.get("rotation_rehearsal_required"),
            )
        )
        _require(
            failures,
            item.get("real_value_required_for_wp8") is False,
            f"real value unexpectedly required for {item.get('id')}",
        )
    _require(failures, actual_classes == expected_classes, "secret class/consumer matrix is not exact")

    for key, expected in {
        "inheritance_protected": True,
        "ci_runner_read_data_allowed": False,
        "ci_runner_write_allowed": False,
        "broad_read_principals_allowed": False,
    }.items():
        _require(failures, acl.get(key) is expected, f"acl.{key} must be {expected}")

    _require(
        failures,
        lifecycle.get("states") == ["UNPROVISIONED", "ACTIVE", "REVOKED", "COMPROMISED"],
        "lifecycle states are not exact",
    )
    forbidden_metadata = set(lifecycle.get("forbidden_metadata_fields", []))
    for field in (
        "value",
        "secret_value",
        "ciphertext",
        "hash",
        "digest",
        "fingerprint",
        "sid",
        "username",
        "hostname",
        "account_id",
    ):
        _require(failures, field in forbidden_metadata, f"metadata must forbid {field}")
    _require(
        failures,
        lifecycle.get("real_value_change_forbidden_in_github_actions") is True,
        "GitHub Actions real-value mutation must be forbidden",
    )
    _require(
        failures,
        lifecycle.get("secret_input_mode") == "READ_HOST_AS_SECURE_STRING",
        "real-value input must use SecureString prompt",
    )

    for key, expected in {
        "real_secret_values_used": False,
        "persistent_sentinels_are_non_secret": True,
        "unauthorized_runner_data_read_expected": "ACCESS_DENIED",
        "rollback_must_refuse_if_real_secret_provisioned": True,
        "secret_root_artifact_upload_allowed": False,
        "process_dump_collection_during_secret_change_allowed": False,
        "future_service_activation_allowed": False,
        "broker_write_activation_allowed": False,
        "trading_methods": False,
        "gateway_entrypoint": "app:app",
    }.items():
        _require(failures, acceptance.get(key) == expected, f"acceptance.{key} must equal {expected!r}")

    for fragment in (
        "[switch]$Apply",
        "[switch]$Verify",
        "$wp6Contract.local_paths.secret_root",
        "$wp6Contract.local_paths.execution_acl_sentinel",
        "$wp6Contract.roles.runtime.role_name",
        "$wp6Contract.roles.execution.role_name",
        "SetAccessRuleProtection($true, $false)",
        "FileSystemRights]::ReadPermissions",
        "FileSystemRights]::ReadData",
        "DataProtectionScope]::LocalMachine",
        "ProtectedData]::Protect",
        "ProtectedData]::Unprotect",
        "Invoke-RotationRehearsal",
        "CI_RUNNER_SECRET_DATA_READ_NOT_DENIED",
        "RUNTIME_ROLE_TRADING_SECRET_EXPOSURE",
        "EXECUTION_ROLE_READ_BROKER_SECRET_EXPOSURE",
        "real_secret_values_used_for_wp8_acceptance = $false",
        "secret_hashes_collected = $false",
        "ciphertext_collected = $false",
        "process_dumps_collected = $false",
        "Real secret values used: NO",
    ):
        _require(failures, fragment in provisioner, f"provisioner missing guard: {fragment}")

    for fragment in (
        "TINVEST_TOKEN",
        "TINVEST_TRADING_TOKEN",
        "TELEGRAM_BOT_TOKEN",
        "REAL_TRADING_ENABLED=true",
        "New-Service",
        "Start-Service",
        "Remove-LocalUser",
    ):
        _require(failures, fragment.lower() not in provisioner.lower(), f"provisioner contains forbidden marker: {fragment}")

    param_match = re.search(r"param\((.*?)\)\s*\n\s*Set-StrictMode", manager, re.S)
    _require(failures, param_match is not None, "manager param block not found")
    if param_match is not None:
        param_block = param_match.group(1).lower()
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
            _require(failures, forbidden not in param_block, f"manager exposes plaintext parameter: {forbidden}")

    for fragment in (
        'if ($env:GITHUB_ACTIONS -eq "true")',
        "Read-Host -AsSecureString",
        "SecureStringToBSTR",
        "ZeroFreeBSTR",
        "[Array]::Clear($plainBytes",
        "DataProtectionScope]::LocalMachine",
        "File]::Replace",
        "Secret value/ciphertext output: NEVER",
        "AcknowledgeContourReady",
    ):
        _require(failures, fragment in manager, f"manager missing guard: {fragment}")

    for fragment in (
        "Test-OwnedDirectory",
        "REAL_SECRET_PROVISIONED:",
        "ACTIVE_SECRET_BLOB_PRESENT:",
        "safe_to_cleanup",
        "WP6 secret root will be removed: NO",
        "WP6 identities/runner boundary will be changed: NO",
        "WP7 prerequisites/directories will be changed: NO",
    ):
        _require(failures, fragment in rollback, f"rollback missing guard: {fragment}")

    for text, source, label in (
        ("LocalMachine", execution_contract, "execution contract"),
        ("protected NTFS DACL", execution_contract, "execution contract"),
        ("per-user authorization", execution_contract, "execution contract"),
        ("real broker, Telegram or encryption value", runbook, "runbook"),
        ("ADR-020", decisions, "decision registry"),
    ):
        _require(failures, text in source, f"{label} missing required text: {text}")

    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("V10 WP8 secret-store contract check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("V10 WP8 secret-store contract check passed.")
    print("Protector: Windows DPAPI LocalMachine + protected NTFS DACL")
    print("CI secret payload access: denied")
    print("Runtime broker-read / execution broker-trading roles: separated")
    print("Real secret values for WP8 acceptance: forbidden/not required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
