from __future__ import annotations

import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "docs" / "architecture" / "V10_WP8_SECRET_STORE_CONTRACT.json"
WP6_PATH = ROOT / "docs" / "architecture" / "V10_WP6_IDENTITY_PRIVILEGE_CONTRACT.json"
EXECUTION_CONTRACT = ROOT / "docs" / "architecture" / "V10_WP8_EXECUTION_CONTRACT.md"
RUNBOOK = ROOT / "docs" / "operations" / "V10_WP8_SECRET_STORE_RUNBOOK.md"
PROVISIONER = ROOT / "infrastructure" / "windows" / "provision_wp8_secret_store.ps1"
MANAGER = ROOT / "infrastructure" / "windows" / "manage_wp8_secret.ps1"
ROLLBACK = ROOT / "infrastructure" / "windows" / "rollback_wp8_secret_store.ps1"
DECISIONS = ROOT / "docs" / "architecture" / "DECISIONS.md"


class ContractError(ValueError):
    pass


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot load {path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"{path.relative_to(ROOT)} must contain an object")
    return value


def _mapping(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        raise ContractError(f"{label} must be an object")
    return value


def _text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ContractError(f"cannot load {path.relative_to(ROOT)}: {exc}") from exc


def validate() -> list[str]:
    failures: list[str] = []
    try:
        contract = load_json(CONTRACT_PATH)
        wp6 = load_json(WP6_PATH)
        provider = _mapping(contract.get("provider"), "provider")
        paths = _mapping(contract.get("paths"), "paths")
        identities = _mapping(contract.get("identities"), "identities")
        acl = _mapping(contract.get("acl"), "acl")
        lifecycle = _mapping(contract.get("lifecycle"), "lifecycle")
        acceptance = _mapping(contract.get("acceptance"), "acceptance")
        wp6_paths = _mapping(wp6.get("local_paths"), "WP6 local_paths")
        wp6_roles = _mapping(wp6.get("roles"), "WP6 roles")
        wp6_runtime = _mapping(wp6_roles.get("runtime"), "WP6 runtime role")
        wp6_execution = _mapping(wp6_roles.get("execution"), "WP6 execution role")
        provisioner = _text(PROVISIONER)
        manager = _text(MANAGER)
        rollback = _text(ROLLBACK)
        execution_contract = _text(EXECUTION_CONTRACT)
        runbook = _text(RUNBOOK)
        decisions = _text(DECISIONS)
    except ContractError as exc:
        return [str(exc)]

    if contract.get("schema_version") != "1":
        failures.append("WP8 secret-store contract schema_version must be '1'")
    if contract.get("work_package") != "WP8":
        failures.append("WP8 work_package marker must be WP8")

    expected_provider = {
        "type": "WINDOWS_DPAPI",
        "api": "System.Security.Cryptography.ProtectedData",
        "scope": "LOCAL_MACHINE",
        "authorization_boundary": "PROTECTED_NTFS_DACL",
    }
    for key, expected in expected_provider.items():
        if provider.get(key) != expected:
            failures.append(f"WP8 provider.{key} must be {expected}")
    if provider.get("local_machine_scope_is_not_principal_authorization") is not True:
        failures.append("WP8 must acknowledge LocalMachine DPAPI is not principal authorization")
    for key in (
        "plaintext_cli_allowed",
        "plaintext_environment_allowed",
        "plaintext_log_allowed",
        "secret_hash_metadata_allowed",
        "ciphertext_in_github_allowed",
    ):
        if provider.get(key) is not False:
            failures.append(f"WP8 provider.{key} must be false")

    if paths.get("secret_root") != wp6_paths.get("secret_root"):
        failures.append("WP8 must reuse the accepted WP6 secret root")
    if paths.get("wp6_execution_sentinel") != wp6_paths.get("execution_acl_sentinel"):
        failures.append("WP8 must preserve the accepted WP6 execution sentinel")
    if identities.get("runtime_role") != wp6_runtime.get("role_name"):
        failures.append("WP8 runtime role must match WP6")
    if identities.get("execution_role") != wp6_execution.get("role_name"):
        failures.append("WP8 execution role must match WP6")

    expected_classes = [
        ("broker_read", "omni-cio-runtime", "READ", True),
        ("broker_trading", "omni-cio-execution", "READ", False),
        ("telegram_bot", "SEALED_UNTIL_BLOCK_F", "NONE", True),
        ("local_encryption_key", "SEALED_UNTIL_OWNING_WP", "NONE", False),
        ("external_source", "SEALED_UNTIL_OWNING_WP", "NONE", False),
    ]
    classes = contract.get("secret_classes")
    if not isinstance(classes, list):
        failures.append("WP8 secret_classes must be a list")
    else:
        actual: list[tuple[str, str, str, bool]] = []
        for index, item in enumerate(classes):
            try:
                spec = _mapping(item, f"secret_classes[{index}]")
            except ContractError as exc:
                failures.append(str(exc))
                continue
            actual.append(
                (
                    str(spec.get("id")),
                    str(spec.get("consumer_role")),
                    str(spec.get("consumer_data_access")),
                    bool(spec.get("rotation_rehearsal_required")),
                )
            )
            if spec.get("real_value_required_for_wp8") is not False:
                failures.append(f"WP8 class {spec.get('id')} must not require a real value")
            directory = str(spec.get("directory", ""))
            if not directory.startswith("C:\\ProgramData\\OmniCIO\\secrets\\"):
                failures.append(f"WP8 class {spec.get('id')} must live below local secret root")
        if actual != expected_classes:
            failures.append("WP8 secret class/consumer matrix differs from reviewed contract")

    for key, expected in {
        "inheritance_protected": True,
        "ci_runner_read_data_allowed": False,
        "ci_runner_write_allowed": False,
        "broad_read_principals_allowed": False,
    }.items():
        if acl.get(key) is not expected:
            failures.append(f"WP8 acl.{key} must be {expected}")

    if lifecycle.get("states") != ["UNPROVISIONED", "ACTIVE", "REVOKED", "COMPROMISED"]:
        failures.append("WP8 lifecycle states are not exact")
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
        if field not in forbidden_metadata:
            failures.append(f"WP8 metadata must forbid {field}")
    if lifecycle.get("real_value_change_forbidden_in_github_actions") is not True:
        failures.append("WP8 real-value changes must be forbidden in GitHub Actions")
    if lifecycle.get("secret_input_mode") != "READ_HOST_AS_SECURE_STRING":
        failures.append("WP8 real-value input must use local SecureString prompt")

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
        if acceptance.get(key) != expected:
            failures.append(f"WP8 acceptance.{key} must equal {expected!r}")

    required_provisioner = (
        "[switch]$Apply",
        "[switch]$Verify",
        "Test-Administrator",
        "Get-RunnerServiceSid",
        "$wp6Contract.local_paths.secret_root",
        "$wp6Contract.local_paths.execution_acl_sentinel",
        "$wp6Contract.roles.runtime.role_name",
        "$wp6Contract.roles.execution.role_name",
        "SetAccessRuleProtection($true, $false)",
        "FileSystemRights]::ReadPermissions",
        "FileSystemRights]::ReadAttributes",
        "FileSystemRights]::ReadData",
        "DataProtectionScope]::LocalMachine",
        "ProtectedData]::Protect",
        "ProtectedData]::Unprotect",
        "RandomNumberGenerator]::Create",
        "Invoke-RotationRehearsal",
        "ACCESS_DENIED",
        "CI_RUNNER_SECRET_DATA_READ_NOT_DENIED",
        "RUNTIME_ROLE_TRADING_SECRET_EXPOSURE",
        "EXECUTION_ROLE_READ_BROKER_SECRET_EXPOSURE",
        "real_secret_values_used_for_wp8_acceptance = $false",
        "secret_hashes_collected = $false",
        "ciphertext_collected = $false",
        "process_dumps_collected = $false",
        "Real secret values used: NO",
    )
    for fragment in required_provisioner:
        if fragment not in provisioner:
            failures.append(f"WP8 provisioner missing required guard: {fragment}")
    for fragment in (
        "TINVEST_TOKEN",
        "TINVEST_TRADING_TOKEN",
        "TELEGRAM_BOT_TOKEN",
        "REAL_TRADING_ENABLED=true",
        "New-Service",
        "Start-Service",
        "config.cmd --token",
        "Remove-LocalUser",
    ):
        if fragment.lower() in provisioner.lower():
            failures.append(f"WP8 provisioner contains forbidden marker: {fragment}")

    manager_param_match = re.search(r"param\((.*?)\)\s*\n\s*Set-StrictMode", manager, re.S)
    if not manager_param_match:
        failures.append("WP8 manager param block not found")
    else:
        param_block = manager_param_match.group(1).lower()
        for forbidden in (
            "secretvalue",
            "secret_value",
            "tokenvalue",
            "token_value",
            "password",
            "api_key",
            "apikey",
            "connectionstring",
            "connection_string",
        ):
            if forbidden in param_block:
                failures.append(f"WP8 manager exposes forbidden plaintext parameter: {forbidden}")

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
        'ValidateSet("Set", "Rotate", "Revoke", "MarkCompromised", "Status")',
    ):
        if fragment not in manager:
            failures.append(f"WP8 manager missing required guard: {fragment}")
    for forbidden in (
        "Write-Output $plain",
        "Write-Host $plain",
        "ConvertFrom-SecureString -AsPlainText",
        "TINVEST_TOKEN",
        "TINVEST_TRADING_TOKEN",
        "TELEGRAM_BOT_TOKEN",
    ):
        if forbidden.lower() in manager.lower():
            failures.append(f"WP8 manager contains forbidden secret-output marker: {forbidden}")

    for fragment in (
        "Test-OwnedDirectory",
        "REAL_SECRET_PROVISIONED:",
        "ACTIVE_SECRET_BLOB_PRESENT:",
        "safe_to_cleanup",
        "WP6 secret root will be removed: NO",
        "WP6 identities/runner boundary will be changed: NO",
        "WP7 prerequisites/directories will be changed: NO",
    ):
        if fragment not in rollback:
            failures.append(f"WP8 rollback missing required guard: {fragment}")
    for forbidden in (
        "Remove-LocalUser",
        "winget uninstall",
        "Remove-Item -LiteralPath $secretRoot",
        "Remove-Item -LiteralPath $wp6Sentinel",
    ):
        if forbidden.lower() in rollback.lower():
            failures.append(f"WP8 rollback contains forbidden destructive marker: {forbidden}")

    for required_text, source, label in (
        ("LocalMachine", execution_contract, "execution contract"),
        ("protected NTFS DACL", execution_contract, "execution contract"),
        ("not treated as per-user authorization", execution_contract, "execution contract"),
        ("Do not enter real broker/Telegram/encryption credentials", runbook, "runbook"),
        ("Secret value/ciphertext output", manager, "manager"),
        ("ADR-020", decisions, "decision registry"),
    ):
        if required_text not in source:
            failures.append(f"WP8 {label} missing required text: {required_text}")

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
    print("Rotation rehearsal: generated non-secret broker-read + Telegram sentinels")
    print("Secret plaintext/hash/ciphertext in GitHub evidence: forbidden")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
