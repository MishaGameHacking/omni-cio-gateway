from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import pytest

from omni_cio.persistence.hosted_recovery_v1 import (
    CONTRACT_PATH,
    HostedRecoveryContractError,
    archive_sha256,
    build_restore_commands,
    load_hosted_recovery_contract,
    validate_hosted_recovery_contract,
    validate_recovery_manifest,
    validate_restore_evidence,
)


_ARCHIVE = b"synthetic-pg18-custom-archive"
_RELEASE_SHA = "".join(("9ba45a60", "40365599", "bcfdebbb", "ec90938e", "1deaa5e5"))
_MIGRATION_SHA = sha256(b"synthetic-migration-state").hexdigest()
_TENANT_SHA = sha256(b"synthetic-tenant-boundary").hexdigest()
_SCHEMA_SHA = sha256(b"synthetic-schema-state").hexdigest()
_FORCED_RLS = [
    "broker_accounts",
    "broker_connections",
    "broker_connection_accounts",
]


def _contract() -> dict[str, object]:
    return load_hosted_recovery_contract(CONTRACT_PATH)


def _manifest() -> dict[str, object]:
    return {
        "schema_version": "v10.wp22a.phase3.hosted-recovery-manifest.v1",
        "backup_class": "POSTGRES_LOGICAL_PRIVATE_STATE",
        "created_at_utc": "2026-08-20T11:30:00Z",
        "archive_name": "wp22a-20260820T113000Z-a1b2c3d4e5f6.dump",
        "archive_sha256": archive_sha256(_ARCHIVE),
        "archive_size_bytes": len(_ARCHIVE),
        "postgres_major": 18,
        "archive_format": "CUSTOM",
        "source_release_sha": _RELEASE_SHA,
        "migration_state_sha256": _MIGRATION_SHA,
        "tenant_boundary_sha256": _TENANT_SHA,
        "schema_state_sha256": _SCHEMA_SHA,
        "forced_rls_relations": list(_FORCED_RLS),
        "encryption_state": "EXTERNAL_ENVELOPE_REQUIRED",
    }


def _evidence() -> dict[str, object]:
    return {
        "restored_into_separate_database": True,
        "accepted_release_sha": _RELEASE_SHA,
        "migration_state_sha256": _MIGRATION_SHA,
        "tenant_boundary_sha256": _TENANT_SHA,
        "schema_state_sha256": _SCHEMA_SHA,
        "forced_rls_relations": list(_FORCED_RLS),
        "unscoped_access_denied": True,
        "cross_tenant_access_denied": True,
        "runtime_acl_reapplied": True,
        "rollback_release_available": True,
        "temporary_state_cleaned": True,
    }


def test_hosted_recovery_contract_preserves_phase3_authority() -> None:
    payload = _contract()
    validate_hosted_recovery_contract(payload)

    authority = payload["authority"]
    postgres = payload["postgres"]
    off_runtime = payload["off_runtime"]
    assert isinstance(authority, dict)
    assert isinstance(postgres, dict)
    assert isinstance(off_runtime, dict)
    assert authority["provider_apply_enabled"] is False
    assert authority["public_ingress_enabled"] is False
    assert authority["public_multi_user_enabled"] is False
    assert authority["real_trading_enabled"] is False
    assert authority["trading_methods"] is False
    assert authority["wp23_unlocked"] is False
    assert authority["owner_recurring_cost_rub_month"] == 0
    assert authority["gateway_entrypoint"] == "app:app"
    assert postgres["major_version"] == 18
    assert postgres["dump_format"] == "custom"
    assert postgres["no_owner"] is True
    assert postgres["no_privileges"] is True
    assert off_runtime["encrypted_copy_required"] is True
    assert off_runtime["github_allowed"] is False
    assert off_runtime["ci_artifacts_allowed"] is False
    assert off_runtime["plaintext_object_storage_allowed"] is False


def test_recovery_manifest_accepts_exact_archive_and_boundary() -> None:
    validate_recovery_manifest(
        _manifest(),
        archive_bytes=_ARCHIVE,
        expected_release_sha=_RELEASE_SHA,
        expected_migration_sha256=_MIGRATION_SHA,
        expected_tenant_boundary_sha256=_TENANT_SHA,
        expected_schema_sha256=_SCHEMA_SHA,
        required_forced_rls_relations=_FORCED_RLS,
    )


def test_recovery_manifest_rejects_corrupt_archive() -> None:
    with pytest.raises(HostedRecoveryContractError, match="archive SHA-256 mismatch"):
        validate_recovery_manifest(
            _manifest(),
            archive_bytes=b"tampered" + _ARCHIVE,
            expected_release_sha=_RELEASE_SHA,
            expected_migration_sha256=_MIGRATION_SHA,
            expected_tenant_boundary_sha256=_TENANT_SHA,
            expected_schema_sha256=_SCHEMA_SHA,
            required_forced_rls_relations=_FORCED_RLS,
        )


def test_recovery_manifest_rejects_declared_size_drift() -> None:
    manifest = _manifest()
    manifest["archive_size_bytes"] = len(_ARCHIVE) + 1
    with pytest.raises(HostedRecoveryContractError, match="archive size mismatch"):
        validate_recovery_manifest(
            manifest,
            archive_bytes=_ARCHIVE,
            expected_release_sha=_RELEASE_SHA,
            expected_migration_sha256=_MIGRATION_SHA,
            expected_tenant_boundary_sha256=_TENANT_SHA,
            expected_schema_sha256=_SCHEMA_SHA,
            required_forced_rls_relations=_FORCED_RLS,
        )


def test_recovery_manifest_rejects_partial_archive_name() -> None:
    manifest = _manifest()
    manifest["archive_name"] = str(manifest["archive_name"]) + ".partial"
    with pytest.raises(HostedRecoveryContractError, match="archive name"):
        validate_recovery_manifest(
            manifest,
            archive_bytes=_ARCHIVE,
            expected_release_sha=_RELEASE_SHA,
            expected_migration_sha256=_MIGRATION_SHA,
            expected_tenant_boundary_sha256=_TENANT_SHA,
            expected_schema_sha256=_SCHEMA_SHA,
            required_forced_rls_relations=_FORCED_RLS,
        )


def test_recovery_manifest_rejects_release_or_boundary_drift() -> None:
    manifest = _manifest()
    manifest["source_release_sha"] = "0" * 40
    with pytest.raises(HostedRecoveryContractError, match="source release"):
        validate_recovery_manifest(
            manifest,
            archive_bytes=_ARCHIVE,
            expected_release_sha=_RELEASE_SHA,
            expected_migration_sha256=_MIGRATION_SHA,
            expected_tenant_boundary_sha256=_TENANT_SHA,
            expected_schema_sha256=_SCHEMA_SHA,
            required_forced_rls_relations=_FORCED_RLS,
        )

    manifest = _manifest()
    manifest["tenant_boundary_sha256"] = "0" * 64
    with pytest.raises(HostedRecoveryContractError, match="tenant boundary"):
        validate_recovery_manifest(
            manifest,
            archive_bytes=_ARCHIVE,
            expected_release_sha=_RELEASE_SHA,
            expected_migration_sha256=_MIGRATION_SHA,
            expected_tenant_boundary_sha256=_TENANT_SHA,
            expected_schema_sha256=_SCHEMA_SHA,
            required_forced_rls_relations=_FORCED_RLS,
        )


def test_recovery_manifest_rejects_forced_rls_drift() -> None:
    manifest = _manifest()
    manifest["forced_rls_relations"] = list(_FORCED_RLS[:-1])
    with pytest.raises(HostedRecoveryContractError, match="FORCE-RLS"):
        validate_recovery_manifest(
            manifest,
            archive_bytes=_ARCHIVE,
            expected_release_sha=_RELEASE_SHA,
            expected_migration_sha256=_MIGRATION_SHA,
            expected_tenant_boundary_sha256=_TENANT_SHA,
            expected_schema_sha256=_SCHEMA_SHA,
            required_forced_rls_relations=_FORCED_RLS,
        )


def test_hosted_recovery_contract_rejects_encryption_drift() -> None:
    payload = deepcopy(_contract())
    off_runtime = payload["off_runtime"]
    assert isinstance(off_runtime, dict)
    off_runtime["encrypted_copy_required"] = False
    with pytest.raises(HostedRecoveryContractError, match="encrypted"):
        validate_hosted_recovery_contract(payload)


def test_restore_commands_are_argv_and_validate_destination() -> None:
    commands = build_restore_commands(
        archive_path=Path("backup.dump"),
        destination_database="omni_restore_candidate",
    )
    assert commands == (
        (
            "pg_restore",
            "--list",
            "backup.dump",
        ),
        (
            "pg_restore",
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-privileges",
            "--dbname",
            "omni_restore_candidate",
            "backup.dump",
        ),
    )
    with pytest.raises(HostedRecoveryContractError, match="destination database"):
        build_restore_commands(
            archive_path=Path("backup.dump"),
            destination_database="postgres;DROP DATABASE omni",
        )


def test_restore_evidence_requires_tenant_preserving_negatives() -> None:
    validate_restore_evidence(
        _evidence(),
        expected_release_sha=_RELEASE_SHA,
        expected_migration_sha256=_MIGRATION_SHA,
        expected_tenant_boundary_sha256=_TENANT_SHA,
        expected_schema_sha256=_SCHEMA_SHA,
        required_forced_rls_relations=_FORCED_RLS,
    )

    for field in (
        "restored_into_separate_database",
        "unscoped_access_denied",
        "cross_tenant_access_denied",
        "runtime_acl_reapplied",
        "rollback_release_available",
        "temporary_state_cleaned",
    ):
        evidence = _evidence()
        evidence[field] = False
        with pytest.raises(HostedRecoveryContractError, match=field):
            validate_restore_evidence(
                evidence,
                expected_release_sha=_RELEASE_SHA,
                expected_migration_sha256=_MIGRATION_SHA,
                expected_tenant_boundary_sha256=_TENANT_SHA,
                expected_schema_sha256=_SCHEMA_SHA,
                required_forced_rls_relations=_FORCED_RLS,
            )
