from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ._hosted_recovery_contract_v1 import (
    _DATABASE_RE,
    _EXPECTED_FORCED_RLS,
    _EXPECTED_RESTORE_FLAGS,
    HostedRecoveryContractError,
    _as_string_sequence,
    _require_release_sha,
    _require_sha256,
)
from ._hosted_recovery_integrity_v1 import validate_recovery_manifest


def build_restore_commands(
    archive_path: Path,
    destination_database: str,
    *,
    source_database: str,
    manifest: Mapping[str, Any],
    expected_release_sha: str,
    expected_migration_sha256: str,
    expected_tenant_boundary_sha256: str,
    expected_schema_sha256: str,
    required_forced_rls_relations: Sequence[str],
    contract: Mapping[str, Any] | None = None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if not _DATABASE_RE.fullmatch(source_database):
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_SOURCE_DATABASE_INVALID"
        )
    if not _DATABASE_RE.fullmatch(destination_database):
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_DESTINATION_DATABASE_INVALID"
        )
    if destination_database == source_database:
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_RESTORE_TO_SOURCE_DATABASE_FORBIDDEN"
        )
    validate_recovery_manifest(
        manifest,
        archive_path,
        expected_release_sha=expected_release_sha,
        expected_migration_sha256=expected_migration_sha256,
        expected_tenant_boundary_sha256=expected_tenant_boundary_sha256,
        expected_schema_sha256=expected_schema_sha256,
        required_forced_rls_relations=required_forced_rls_relations,
        contract=contract,
    )
    preflight = ("pg_restore", "--list", str(archive_path))
    restore = (
        "pg_restore",
        *_EXPECTED_RESTORE_FLAGS,
        "--dbname",
        destination_database,
        str(archive_path),
    )
    return preflight, restore


def validate_restore_evidence(
    evidence: Mapping[str, Any],
    *,
    expected_release_sha: str,
    expected_migration_sha256: str,
    expected_tenant_boundary_sha256: str,
    expected_schema_sha256: str,
    required_forced_rls_relations: Sequence[str],
) -> None:
    expected_release = _require_release_sha(
        expected_release_sha,
        "HOSTED_RECOVERY_EXPECTED_RELEASE_SHA_INVALID",
    )
    expected_migration = _require_sha256(
        expected_migration_sha256,
        "HOSTED_RECOVERY_EXPECTED_MIGRATION_SHA256_INVALID",
    )
    expected_tenant = _require_sha256(
        expected_tenant_boundary_sha256,
        "HOSTED_RECOVERY_EXPECTED_TENANT_BOUNDARY_SHA256_INVALID",
    )
    expected_schema = _require_sha256(
        expected_schema_sha256,
        "HOSTED_RECOVERY_EXPECTED_SCHEMA_SHA256_INVALID",
    )
    required_forced_rls = _as_string_sequence(
        required_forced_rls_relations,
        "HOSTED_RECOVERY_REQUIRED_FORCED_RLS_INVALID",
    )
    if required_forced_rls != _EXPECTED_FORCED_RLS:
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_REQUIRED_FORCED_RLS_DRIFT"
        )

    required_fields = {
        "restored_into_separate_database",
        "restore_list_preflight_passed",
        "restore_catalog_rechecked",
        "replacement_runtime_recovery_rehearsed",
        "accepted_release_sha",
        "migration_state_sha256",
        "tenant_boundary_sha256",
        "schema_state_sha256",
        "forced_rls_relations",
        "unscoped_access_denied",
        "cross_tenant_access_denied",
        "runtime_acl_reapplied",
        "rollback_release_available",
        "temporary_state_cleaned",
    }
    if set(evidence) != required_fields:
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_EVIDENCE_FIELDS_INVALID"
        )

    expected_values = {
        "accepted_release_sha": expected_release,
        "migration_state_sha256": expected_migration,
        "tenant_boundary_sha256": expected_tenant,
        "schema_state_sha256": expected_schema,
    }
    for field, expected_value in expected_values.items():
        if evidence[field] != expected_value:
            raise HostedRecoveryContractError(
                f"HOSTED_RECOVERY_{field.upper()}_MISMATCH"
            )

    forced_rls = _as_string_sequence(
        evidence["forced_rls_relations"],
        "HOSTED_RECOVERY_EVIDENCE_FORCED_RLS_INVALID",
    )
    if forced_rls != required_forced_rls:
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_EVIDENCE_FORCE_RLS_MISMATCH"
        )

    required_true_fields = (
        "restored_into_separate_database",
        "restore_list_preflight_passed",
        "restore_catalog_rechecked",
        "replacement_runtime_recovery_rehearsed",
        "unscoped_access_denied",
        "cross_tenant_access_denied",
        "runtime_acl_reapplied",
        "rollback_release_available",
        "temporary_state_cleaned",
    )
    for field in required_true_fields:
        if evidence[field] is not True:
            raise HostedRecoveryContractError(
                f"HOSTED_RECOVERY_{field.upper()}_REQUIRED"
            )
