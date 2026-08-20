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
_RELEASE_SHA = "9ba45a6040365599bcfdebbbec90938e1deaa5e5"
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
    assert authority["provider_apply_authorized"] is False
    assert authority["public_ingress_allowed"] is False
    assert authority["authorized_recurring_rub"] == 0
    assert authority["public_multi_user_enabled"] is False
    assert authority["trading_methods_enabled"] is False
    assert authority["real_trading_enabled"] is False
    assert authority["protected_v9_entrypoint"] == "app:app"
    assert authority["wp23_unlocked"] is False
    assert postgres["major"] == 18
    assert postgres["required_dump_flags"] == [
        "--format=custom",
        "--no-owner",
        "--no-privileges",
    ]
    assert postgres["runtime_acl_reapply_required"] is True
    assert postgres["forced_rls_reverify_required"] is True
    assert off_runtime["encrypted_copy_required"] is True
    assert off_runtime["github_allowed"] is False
    assert off_runtime["ci_artifact_allowed"] is False
    assert off_runtime["plaintext_object_storage_allowed"] is False


def test_hosted_recovery_manifest_accepts_verified_synthetic_bundle() -> None:
    manifest = _manifest()
    validate_recovery_manifest(manifest, _ARCHIVE, _contract())
    assert manifest["archive_sha256"] == sha256(_ARCHIVE).hexdigest()
    assert manifest["forced_rls_relations"] == _FORCED_RLS


def test_hosted_recovery_manifest_rejects_corrupt_archive() -> None:
    with pytest.raises(
        HostedRecoveryContractError,
        match="HOSTED_RECOVERY_ARCHIVE_HASH_MISMATCH",
    ):
        validate_recovery_manifest(_manifest(), _ARCHIVE + b"corrupt", _contract())


def test_hosted_recovery_manifest_rejects_field_and_rls_drift() -> None:
    extra = _manifest()
    extra["tenant_id"] = "forbidden-raw-tenant-selector"
    with pytest.raises(
        HostedRecoveryContractError,
        match="HOSTED_RECOVERY_MANIFEST_FIELDS_INVALID",
    ):
        validate_recovery_manifest(extra, _ARCHIVE, _contract())

    weakened = _manifest()
    weakened["forced_rls_relations"] = ["broker_accounts"]
    with pytest.raises(
        HostedRecoveryContractError,
        match="HOSTED_RECOVERY_FORCED_RLS_DRIFT",
    ):
        validate_recovery_manifest(weakened, _ARCHIVE, _contract())


def test_hosted_recovery_manifest_rejects_size_or_encryption_drift() -> None:
    bad_size = _manifest()
    bad_size["archive_size_bytes"] = len(_ARCHIVE) + 1
    with pytest.raises(
        HostedRecoveryContractError,
        match="HOSTED_RECOVERY_ARCHIVE_SIZE_MISMATCH",
    ):
        validate_recovery_manifest(bad_size, _ARCHIVE, _contract())

    plaintext = _manifest()
    plaintext["encryption_state"] = "PLAINTEXT"
    with pytest.raises(
        HostedRecoveryContractError,
        match="HOSTED_RECOVERY_ENCRYPTION_STATE_INVALID",
    ):
        validate_recovery_manifest(plaintext, _ARCHIVE, _contract())


def test_hosted_recovery_builds_non_shell_restore_commands() -> None:
    archive_path = Path("C:/OmniCIO/recovery/wp22a-test.dump").resolve()
    preflight, restore = build_restore_commands(
        archive_path,
        "omni_cio_restore_probe",
    )
    assert preflight == ("pg_restore", "--list", str(archive_path))
    assert restore == (
        "pg_restore",
        "--exit-on-error",
        "--no-owner",
        "--no-privileges",
        "--dbname",
        "omni_cio_restore_probe",
        str(archive_path),
    )


def test_hosted_recovery_restore_commands_reject_unsafe_destination() -> None:
    archive_path = Path("C:/OmniCIO/recovery/wp22a-test.dump").resolve()
    with pytest.raises(
        HostedRecoveryContractError,
        match="HOSTED_RECOVERY_DESTINATION_DB_INVALID",
    ):
        build_restore_commands(archive_path, "prod;DROP DATABASE prod")


def test_hosted_recovery_evidence_requires_tenant_preserving_restore() -> None:
    manifest = _manifest()
    evidence = _evidence()
    validate_restore_evidence(evidence, manifest)

    cross_tenant = deepcopy(evidence)
    cross_tenant["cross_tenant_access_denied"] = False
    with pytest.raises(
        HostedRecoveryContractError,
        match="HOSTED_RECOVERY_CROSS_TENANT_ACCESS_DENIED_REQUIRED",
    ):
        validate_restore_evidence(cross_tenant, manifest)

    tenant_mismatch = deepcopy(evidence)
    tenant_mismatch["tenant_boundary_sha256"] = sha256(b"other-tenant-state").hexdigest()
    with pytest.raises(
        HostedRecoveryContractError,
        match="HOSTED_RECOVERY_TENANT_BOUNDARY_SHA256_MISMATCH",
    ):
        validate_restore_evidence(tenant_mismatch, manifest)


def test_hosted_recovery_evidence_requires_runtime_acl_and_cleanup() -> None:
    manifest = _manifest()
    for field in (
        "runtime_acl_reapplied",
        "rollback_release_available",
        "temporary_state_cleaned",
        "unscoped_access_denied",
    ):
        evidence = _evidence()
        evidence[field] = False
        with pytest.raises(HostedRecoveryContractError):
            validate_restore_evidence(evidence, manifest)
