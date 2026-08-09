from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "architecture" / "V10_WP10_RECOVERY_CONTRACT.json"


class ContractError(RuntimeError):
    pass


def _load(path: Path = CONTRACT) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ContractError("WP10_CONTRACT_NOT_OBJECT")
    return payload


def _require_true(mapping: dict[str, Any], key: str, code: str) -> None:
    if mapping.get(key) is not True:
        raise ContractError(code)


def _require_false(mapping: dict[str, Any], key: str, code: str) -> None:
    if mapping.get(key) is not False:
        raise ContractError(code)


def validate_contract(contract: dict[str, Any]) -> None:
    if contract.get("schema_version") != "2" or contract.get("work_package") != "WP10":
        raise ContractError("WP10_CONTRACT_IDENTITY_INVALID")
    if contract.get("status") != "IN_PROGRESS_OWNER_GATE_REQUIRED":
        raise ContractError("WP10_PREMATURE_ACCEPTANCE_STATUS")

    authority = contract["authority"]
    if authority.get("stable_entrypoint") != "app:app":
        raise ContractError("STABLE_ENTRYPOINT_CHANGED")
    _require_false(authority, "trading_methods", "TRADING_METHODS_ENABLED")
    _require_false(authority, "real_trading_enabled", "REAL_TRADING_ENABLED")
    _require_false(authority, "broker_authority_change", "BROKER_AUTHORITY_CHANGED")

    objectives = contract["recovery_objectives"]
    rpo = int(objectives.get("rpo_minutes", 0))
    rto = int(objectives.get("rto_minutes", 0))
    if rpo != 60 or rto != 240:
        raise ContractError("RECOVERY_OBJECTIVE_DRIFT")
    if objectives.get("rpo_status_before_product_db_binding") != "NOT_APPLICABLE_YET":
        raise ContractError("PREMATURE_RPO_CLAIM")
    _require_true(
        objectives,
        "rpo_requires_offdevice_copy",
        "RPO_OFFDEVICE_GUARD_MISSING",
    )
    _require_true(
        objectives,
        "rto_requires_integrity_checks",
        "RTO_INTEGRITY_GUARD_MISSING",
    )
    _require_true(
        objectives,
        "measured_owner_rehearsal_required",
        "RTO_MEASUREMENT_GATE_MISSING",
    )

    separation = contract["source_separation"]
    if separation.get("engineering_source") != "GITHUB_ACCEPTED_MAIN_RELEASE":
        raise ContractError("ENGINEERING_SOURCE_INVALID")
    if (
        separation.get("private_durable_state")
        != "ENCRYPTED_OWNER_CONTROLLED_OFFDEVICE_BACKUP"
    ):
        raise ContractError("PRIVATE_STATE_SOURCE_INVALID")
    if (
        separation.get("runtime_credential_recovery")
        != "SEPARATELY_RESTORED_OWNER_CONTROLLED_STORE"
    ):
        raise ContractError("CREDENTIAL_RECOVERY_PATH_INVALID")
    for key in (
        "github_is_private_state_backup",
        "github_is_secret_backup",
        "ci_artifact_is_private_state_backup",
    ):
        _require_false(separation, key, f"SOURCE_SEPARATION_VIOLATION:{key}")

    postgres = contract["postgresql"]
    if int(postgres.get("accepted_major", 0)) != 18:
        raise ContractError("POSTGRES_MAJOR_CHANGED")
    if (
        postgres.get("backup_tool") != "pg_dump"
        or postgres.get("restore_tool") != "pg_restore"
    ):
        raise ContractError("POSTGRES_TOOLCHAIN_INVALID")
    if postgres.get("archive_format") != "CUSTOM":
        raise ContractError("POSTGRES_ARCHIVE_FORMAT_INVALID")
    if set(postgres.get("required_dump_flags", [])) != {
        "--format=custom",
        "--no-owner",
        "--no-privileges",
    }:
        raise ContractError("POSTGRES_DUMP_FLAGS_INVALID")
    for key in (
        "restore_list_preflight_required",
        "restore_into_separate_database_required",
        "synthetic_rehearsal_required_now",
        "automation_mechanism_required_now",
    ):
        _require_true(postgres, key, f"POSTGRES_GUARD_MISSING:{key}")
    if postgres.get("production_database_binding") != "NOT_READY_UNTIL_WP13":
        raise ContractError("PRODUCTION_DB_BOUND_EARLY")
    if postgres.get("production_job_binding") != "NOT_READY_UNTIL_WP13_WP14":
        raise ContractError("PRODUCTION_JOB_BOUND_EARLY")

    automation = contract["automation"]
    cadence = int(automation.get("target_cadence_minutes", 0))
    if cadence <= 0 or cadence > rpo:
        raise ContractError("BACKUP_CADENCE_EXCEEDS_RPO")
    for key in (
        "cadence_must_not_exceed_rpo",
        "noninteractive_runner_required",
        "schedule_definition_required_now",
        "synthetic_schedule_rehearsal_required_now",
        "secret_values_in_task_definition_forbidden",
    ):
        _require_true(automation, key, f"AUTOMATION_GUARD_MISSING:{key}")
    _require_false(
        automation,
        "production_schedule_activation_before_product_binding",
        "PRODUCTION_SCHEDULE_ACTIVATED_EARLY",
    )

    integrity = contract["integrity"]
    if integrity.get("algorithm") != "SHA256":
        raise ContractError("INTEGRITY_ALGORITHM_INVALID")
    for key in (
        "archive_size_bound",
        "manifest_schema_bound",
        "hash_before_restore_required",
        "destination_rehash_required",
        "atomic_promotion_required",
        "corrupt_backup_rejection_required",
    ):
        _require_true(integrity, key, f"INTEGRITY_GUARD_MISSING:{key}")

    bundle = contract["bundle"]
    required_fields = {
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
    if set(bundle.get("allowed_manifest_fields", [])) != required_fields:
        raise ContractError("MANIFEST_FIELD_SET_INVALID")
    required_forbidden = {
        "secret",
        "token",
        "password",
        "authorization",
        "ciphertext",
        "recovery_key",
        "account_id",
        "portfolio_payload",
        "connection_string",
        "hostname",
        "ip_address",
    }
    if not required_forbidden.issubset(
        set(bundle.get("forbidden_manifest_tokens", []))
    ):
        raise ContractError("MANIFEST_PRIVATE_FIELD_GUARDS_INCOMPLETE")

    retention = contract["retention"]
    if int(retention.get("maximum_successful_bundles_per_target", 0)) != 72:
        raise ContractError("RETENTION_COUNT_DRIFT")
    if int(retention.get("maximum_age_days", 0)) != 30:
        raise ContractError("RETENTION_AGE_DRIFT")
    for key in (
        "never_delete_only_verified_bundle",
        "unknown_or_invalid_content_deletion_forbidden",
        "verify_immediately_before_delete",
    ):
        _require_true(retention, key, f"RETENTION_GUARD_MISSING:{key}")

    metadata = contract["private_metadata"]
    if metadata.get("mode") != "EXPLICIT_ALLOWLIST_ONLY":
        raise ContractError("METADATA_ALLOWLIST_NOT_STRICT")
    _require_true(
        metadata,
        "empty_payload_allowed_before_owning_wps",
        "EMPTY_METADATA_NOT_ALLOWED",
    )
    _require_true(
        metadata,
        "synthetic_allowlist_test_required_now",
        "METADATA_TEST_GATE_MISSING",
    )
    forbidden_paths = {
        str(item).lower() for item in metadata.get("forbidden_path_tokens", [])
    }
    if not {"secrets", "token", "password", "private_key", "runner"}.issubset(
        forbidden_paths
    ):
        raise ContractError("METADATA_FORBIDDEN_PATHS_INCOMPLETE")

    off_device = contract["off_device"]
    if (
        off_device.get("initial_target_class")
        != "OWNER_CONTROLLED_NON_SYSTEM_BITLOCKER_VOLUME"
    ):
        raise ContractError("OFFDEVICE_TARGET_CLASS_INVALID")
    for key in (
        "owner_target_required_for_final_acceptance",
        "fully_encrypted_required",
        "protection_on_required",
        "separate_recovery_key_custody_required",
        "destructive_provisioning_by_wp10_forbidden",
        "format_disk_forbidden",
        "repartition_disk_forbidden",
        "shrink_volume_forbidden",
        "owner_copy_restore_rehearsal_required",
    ):
        _require_true(off_device, key, f"OFFDEVICE_GUARD_MISSING:{key}")
    for key in (
        "system_volume_allowed",
        "runner_payload_read_allowed",
        "runner_payload_write_allowed",
        "ci_may_synthesize_owner_evidence",
    ):
        _require_false(off_device, key, f"OFFDEVICE_BOUNDARY_VIOLATION:{key}")

    owner = contract["owner_evidence"]
    if owner.get("required_state_before_final_acceptance") != "PASS":
        raise ContractError("OWNER_GATE_STATE_INVALID")
    if owner.get("missing_evidence_state") != "OWNER_ACTION_REQUIRED":
        raise ContractError("MISSING_OWNER_EVIDENCE_NOT_BLOCKING")
    for key in (
        "sanitized_only",
        "raw_disk_identity_forbidden",
        "recovery_key_value_forbidden",
        "secret_value_forbidden",
        "private_payload_forbidden",
        "measured_duration_required",
    ):
        _require_true(owner, key, f"OWNER_EVIDENCE_GUARD_MISSING:{key}")

    rehearsal = contract["rehearsal"]
    for key in (
        "synthetic_database_required",
        "corrupt_copy_must_be_rejected",
        "separate_restore_database_required",
        "restored_probe_exact_match_required",
        "temporary_state_cleanup_required",
    ):
        _require_true(rehearsal, key, f"REHEARSAL_GUARD_MISSING:{key}")
    _require_false(
        rehearsal,
        "private_portfolio_data_used",
        "PRIVATE_PORTFOLIO_USED_IN_REHEARSAL",
    )
    _require_false(
        rehearsal,
        "real_secret_values_used",
        "REAL_SECRET_USED_IN_REHEARSAL",
    )

    acceptance = contract["acceptance"]
    for key in (
        "software_tests_required",
        "lenovo_synthetic_recovery_required",
        "owner_physical_recovery_required",
        "repository_required_checks_green",
        "zero_unresolved_review_threads",
        "squash_merge_only",
        "post_merge_regression_shield_required",
        "wp11_locked_until_complete",
    ):
        _require_true(acceptance, key, f"EXIT_GATE_WEAKENED:{key}")


def main() -> int:
    validate_contract(_load())
    print("V10 WP10 recovery contract check passed.")
    print("RPO/RTO objectives: 60/240 minutes, measured proof required")
    print("Automated backup mechanism: required now; production binding sealed")
    print("Off-device target: OWNER-controlled, encrypted, non-destructive audit only")
    print("Secrets/GitHub/CI artifacts: not private-state backup sources")
    print("WP11: locked until the full WP10 Exit Gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
