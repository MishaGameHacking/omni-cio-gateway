from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "docs" / "architecture" / "V10_WP10_RECOVERY_CONTRACT.json"
WP8_PATH = ROOT / "docs" / "architecture" / "V10_WP8_SECRET_STORE_CONTRACT.json"
WP9A_PATH = ROOT / "docs" / "architecture" / "V10_WP9A_OPERATIONS_CONTRACT.json"


class ContractError(RuntimeError):
    pass


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_contract(contract: dict, wp8: dict, wp9a: dict) -> None:
    if contract.get("schema_version") != "1" or contract.get("work_package") != "WP10":
        raise ContractError("WP10_CONTRACT_IDENTITY_INVALID")

    authority = contract["authority"]
    if authority.get("stable_entrypoint") != "app:app":
        raise ContractError("STABLE_ENTRYPOINT_CHANGED")
    if authority.get("trading_methods") is not False:
        raise ContractError("TRADING_METHODS_ENABLED")
    if authority.get("real_trading_enabled") is not False:
        raise ContractError("REAL_TRADING_ENABLED")
    if authority.get("real_money_authority_change") is not False:
        raise ContractError("REAL_MONEY_AUTHORITY_CHANGED")
    if wp8["acceptance"].get("trading_methods") is not False:
        raise ContractError("INHERITED_WP8_TRADING_BOUNDARY_INVALID")
    if wp9a["authority"].get("trading_methods") is not False:
        raise ContractError("INHERITED_WP9A_TRADING_BOUNDARY_INVALID")

    objectives = contract["recovery_objectives"]
    if int(objectives.get("rpo_minutes", 0)) != 60:
        raise ContractError("WP10_RPO_CHANGED")
    if int(objectives.get("rto_minutes", 0)) != 240:
        raise ContractError("WP10_RTO_CHANGED")
    for key in (
        "rpo_applies_after_product_db_binding",
        "off_device_freshness_required_for_rpo",
        "rto_never_bypasses_integrity_or_reconciliation",
    ):
        if objectives.get(key) is not True:
            raise ContractError(f"RECOVERY_OBJECTIVE_GUARD_MISSING:{key}")

    separation = contract["source_separation"]
    for key in (
        "github_is_private_state_backup",
        "github_is_secret_backup",
        "ci_artifact_is_private_state_backup",
    ):
        if separation.get(key) is not False:
            raise ContractError(f"RECOVERY_SOURCE_SEPARATION_INVALID:{key}")

    postgres = contract["postgresql"]
    if int(postgres.get("accepted_major", 0)) != 18:
        raise ContractError("POSTGRES_MAJOR_CHANGED")
    if postgres.get("archive_format") != "CUSTOM":
        raise ContractError("POSTGRES_ARCHIVE_FORMAT_INVALID")
    required_flags = set(postgres.get("required_dump_flags", []))
    if required_flags != {"--format=custom", "--no-owner", "--no-privileges"}:
        raise ContractError("POSTGRES_DUMP_FLAGS_INVALID")
    if postgres.get("cluster_role_password_backup_forbidden") is not True:
        raise ContractError("POSTGRES_ROLE_PASSWORD_BACKUP_NOT_FORBIDDEN")
    if postgres.get("production_database_binding") != "NOT_READY_UNTIL_WP13":
        raise ContractError("WP13_DATABASE_BINDING_SCOPE_LEAK")
    if postgres.get("synthetic_rehearsal_required_now") is not True:
        raise ContractError("SYNTHETIC_REHEARSAL_NOT_REQUIRED")
    if postgres.get("real_private_database_required_for_wp10_acceptance") is not False:
        raise ContractError("PRIVATE_DATABASE_PREMATURELY_REQUIRED")

    integrity = contract["integrity"]
    if integrity.get("algorithm") != "SHA256":
        raise ContractError("BACKUP_INTEGRITY_ALGORITHM_INVALID")
    for key, value in integrity.items():
        if key == "algorithm":
            continue
        if value is not True:
            raise ContractError(f"BACKUP_INTEGRITY_GUARD_MISSING:{key}")

    bundle = contract["bundle"]
    allowed = set(bundle.get("manifest_allowed_fields", []))
    forbidden = set(bundle.get("manifest_forbidden_fields", []))
    if not allowed or allowed & forbidden:
        raise ContractError("BACKUP_MANIFEST_FIELD_POLICY_INVALID")
    required_forbidden = {
        "secret",
        "token",
        "password",
        "authorization",
        "ciphertext",
        "recovery_key",
        "account_id",
        "portfolio_payload",
        "database_password",
        "connection_string",
    }
    if not required_forbidden.issubset(forbidden):
        raise ContractError("BACKUP_MANIFEST_PRIVATE_FIELD_GUARDS_INCOMPLETE")
    required_allowed = {
        "schema_version",
        "backup_class",
        "created_at_utc",
        "archive_name",
        "archive_sha256",
        "archive_size_bytes",
        "postgres_major",
        "postgres_version_class",
        "archive_format",
        "retention_class",
    }
    if allowed != required_allowed:
        raise ContractError("BACKUP_MANIFEST_ALLOWLIST_DRIFT")

    retention = contract["retention"]
    if int(retention.get("cadence_minutes_after_product_binding", 0)) != 60:
        raise ContractError("BACKUP_CADENCE_CHANGED")
    count = int(retention.get("maximum_successful_bundles_per_target", 0))
    if count < 2 or count > 168:
        raise ContractError("BACKUP_RETENTION_COUNT_UNSAFE")
    days = int(retention.get("maximum_age_days", 0))
    if days < 1 or days > 90:
        raise ContractError("BACKUP_RETENTION_AGE_UNSAFE")
    for key in (
        "never_delete_only_verified_bundle",
        "unknown_or_unowned_file_deletion_forbidden",
        "manifest_validity_required_before_prune",
    ):
        if retention.get(key) is not True:
            raise ContractError(f"BACKUP_RETENTION_GUARD_MISSING:{key}")

    staging = contract["local_staging"]
    if staging.get("encrypted_system_volume_required") is not True:
        raise ContractError("LOCAL_STAGING_ENCRYPTION_GUARD_MISSING")
    if staging.get("plaintext_secret_material_forbidden") is not True:
        raise ContractError("LOCAL_STAGING_SECRET_GUARD_MISSING")
    if staging.get("production_runner_read_access") is not False:
        raise ContractError("RUNNER_PRIVATE_BACKUP_ACCESS_ENABLED")
    if staging.get("synthetic_ci_contains_private_data") is not False:
        raise ContractError("SYNTHETIC_CI_PRIVATE_DATA_ENABLED")

    off_device = contract["off_device"]
    if (
        off_device.get("initial_target_class")
        != "BITLOCKER_OWNER_CONTROLLED_NON_SYSTEM_VOLUME"
    ):
        raise ContractError("OFFDEVICE_TARGET_CLASS_INVALID")
    if off_device.get("system_volume_allowed") is not False:
        raise ContractError("SYSTEM_VOLUME_ACCEPTED_AS_OFFDEVICE")
    if off_device.get("bitlocker_volume_status_required") != "FullyEncrypted":
        raise ContractError("OFFDEVICE_FULL_ENCRYPTION_NOT_REQUIRED")
    if off_device.get("bitlocker_protection_status_required") != "On":
        raise ContractError("OFFDEVICE_BITLOCKER_PROTECTION_NOT_REQUIRED")
    for key in (
        "recovery_key_custody_separate_required",
        "target_marker_required",
        "owner_physical_action_required_for_final_acceptance",
        "owner_synthetic_copy_restore_rehearsal_required",
        "owner_rehearsal_evidence_required",
        "nonadmin_runner_read_write_denial_required",
    ):
        if off_device.get(key) is not True:
            raise ContractError(f"OFFDEVICE_GUARD_MISSING:{key}")
    if off_device.get("runner_backup_payload_read_allowed") is not False:
        raise ContractError("RUNNER_OFFDEVICE_PAYLOAD_ACCESS_ENABLED")
    if off_device.get("runtime_backup_payload_read_allowed_now") is not False:
        raise ContractError("RUNTIME_OFFDEVICE_READ_PREMATURELY_ENABLED")
    if off_device.get("runtime_backup_payload_write_allowed_now") is not False:
        raise ContractError("RUNTIME_OFFDEVICE_WRITE_PREMATURELY_ENABLED")
    if (
        off_device.get("production_backup_writer_identity")
        != "NOT_READY_UNTIL_PRODUCT_DB_AND_BACKUP_JOB_BINDING"
    ):
        raise ContractError("PRODUCTION_BACKUP_WRITER_SCOPE_LEAK")

    metadata = contract["private_metadata"]
    if metadata.get("mode") != "ALLOWLIST_ONLY":
        raise ContractError("PRIVATE_METADATA_MODE_INVALID")
    if Path(metadata.get("secret_root", "")) != Path(wp8["paths"]["secret_root"]):
        raise ContractError("WP8_SECRET_ROOT_MISMATCH")
    for key in (
        "secret_root_backup_forbidden",
        "wp8_ciphertext_backup_forbidden",
        "recovery_key_backup_forbidden",
        "runner_private_config_backup_forbidden",
        "process_dump_backup_forbidden",
    ):
        if metadata.get(key) is not True:
            raise ContractError(f"PRIVATE_METADATA_GUARD_MISSING:{key}")

    rehearsal = contract["rehearsal"]
    if rehearsal.get("real_secret_values_used") is not False:
        raise ContractError("REAL_SECRET_REQUIRED_FOR_REHEARSAL")
    if rehearsal.get("private_portfolio_data_used") is not False:
        raise ContractError("PRIVATE_PORTFOLIO_REQUIRED_FOR_REHEARSAL")
    for key in (
        "postgres_synthetic_cluster",
        "source_and_restore_database_separate",
        "corrupted_archive_must_be_rejected",
        "restored_probe_must_match_exactly",
        "temporary_state_cleanup_required",
    ):
        if rehearsal.get(key) is not True:
            raise ContractError(f"RECOVERY_REHEARSAL_GUARD_MISSING:{key}")

    observability = contract["observability"]
    if set(observability.get("allowed_states", [])) != {
        "READY",
        "NOT_READY_ALLOWED",
        "DEGRADED",
        "BLOCKED",
        "ERROR",
    }:
        raise ContractError("WP10_STATE_VOCABULARY_INVALID")
    for key in (
        "private_archive_upload_to_ci_forbidden",
        "secret_or_recovery_key_log_forbidden",
        "off_device_file_listing_upload_forbidden",
        "sanitized_boolean_and_reason_evidence_only",
    ):
        if observability.get(key) is not True:
            raise ContractError(f"WP10_OBSERVABILITY_GUARD_MISSING:{key}")

    next_wp = contract["next_wp"]
    if next_wp.get("wp") != "WP11":
        raise ContractError("WP10_NEXT_WP_INVALID")
    if next_wp.get("requires_wp10_exit_gate") is not True:
        raise ContractError("WP10_NEXT_WP_EXIT_GATE_MISSING")
    if next_wp.get("requires_block_c_acceptance") is not True:
        raise ContractError("BLOCK_C_ACCEPTANCE_GATE_MISSING")
    if next_wp.get("early_start_forbidden") is not True:
        raise ContractError("WP11_EARLY_START_NOT_FORBIDDEN")


def main() -> int:
    contract = _load(CONTRACT_PATH)
    validate_contract(contract, _load(WP8_PATH), _load(WP9A_PATH))
    print("V10 WP10 recovery contract check passed.")
    print("RPO: 60 minutes; RTO: 240 minutes")
    print("PostgreSQL: major 18 / custom logical archive / synthetic rehearsal")
    print("Off-device: encrypted target + OWNER copy/restore + runner denial")
    print("Production backup writer: sealed until owning DB/job binding")
    print("GitHub/CI/private-state/secret recovery paths: separated")
    print("WP11: locked until WP10 Exit Gate and Block C acceptance")
    print("Real-money authority: unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
