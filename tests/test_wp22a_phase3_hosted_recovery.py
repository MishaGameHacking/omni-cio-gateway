from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import pytest

import omni_cio.persistence.hosted_recovery_v1 as hosted_recovery
from omni_cio.persistence._hosted_recovery_integrity_v1 import (
    _archive_file_integrity,
)
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
_ARCHIVE_NAME = "wp22a-20260820T113000Z-ea232a88b3ee.dump"
_ALT_ARCHIVE_NAME = "wp22a-20260820T113001Z-ea232a88b3ee.dump"


def _contract() -> dict[str, object]:
    return load_hosted_recovery_contract(CONTRACT_PATH)


def _manifest() -> dict[str, object]:
    return {
        "schema_version": "v10.wp22a.phase3.hosted-recovery-manifest.v1",
        "backup_class": "POSTGRES_LOGICAL_PRIVATE_STATE",
        "created_at_utc": "2026-08-20T11:30:00Z",
        "archive_name": _ARCHIVE_NAME,
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
        "restore_list_preflight_passed": True,
        "restore_catalog_rechecked": True,
        "replacement_runtime_recovery_rehearsed": True,
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


def _write_archive(
    tmp_path: Path,
    archive_bytes: bytes = _ARCHIVE,
    archive_name: str = _ARCHIVE_NAME,
) -> Path:
    archive_path = (tmp_path / archive_name).resolve()
    archive_path.write_bytes(archive_bytes)
    return archive_path


def _validate_manifest(
    tmp_path: Path,
    manifest: dict[str, object],
    archive_bytes: bytes = _ARCHIVE,
    archive_name: str = _ARCHIVE_NAME,
) -> Path:
    archive_path = _write_archive(tmp_path, archive_bytes, archive_name)
    validate_recovery_manifest(
        manifest,
        archive_path=archive_path,
        expected_release_sha=_RELEASE_SHA,
        expected_migration_sha256=_MIGRATION_SHA,
        expected_tenant_boundary_sha256=_TENANT_SHA,
        expected_schema_sha256=_SCHEMA_SHA,
        required_forced_rls_relations=_FORCED_RLS,
    )
    return archive_path


def _build_restore_commands(
    archive_path: Path,
    manifest: dict[str, object],
    destination_database: str = "omni_restore_candidate",
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    return build_restore_commands(
        archive_path=archive_path,
        destination_database=destination_database,
        source_database="omni_hosted",
        manifest=manifest,
        expected_release_sha=_RELEASE_SHA,
        expected_migration_sha256=_MIGRATION_SHA,
        expected_tenant_boundary_sha256=_TENANT_SHA,
        expected_schema_sha256=_SCHEMA_SHA,
        required_forced_rls_relations=_FORCED_RLS,
    )


def _validate_evidence(evidence: dict[str, object]) -> None:
    validate_restore_evidence(
        evidence,
        expected_release_sha=_RELEASE_SHA,
        expected_migration_sha256=_MIGRATION_SHA,
        expected_tenant_boundary_sha256=_TENANT_SHA,
        expected_schema_sha256=_SCHEMA_SHA,
        required_forced_rls_relations=_FORCED_RLS,
    )


def test_hosted_recovery_contract_rejects_unknown_top_level_fields() -> None:
    payload = deepcopy(_contract())
    payload["unexpected"] = True
    with pytest.raises(HostedRecoveryContractError, match="CONTRACT_FIELDS_INVALID"):
        validate_hosted_recovery_contract(payload)


def test_hosted_recovery_contract_is_provider_neutral_and_fail_closed() -> None:
    payload = _contract()
    validate_hosted_recovery_contract(payload)

    authority = payload["authority"]
    postgres = payload["postgres"]
    integrity = payload["integrity"]
    off_runtime = payload["off_runtime"]
    assert isinstance(authority, dict)
    assert isinstance(postgres, dict)
    assert isinstance(integrity, dict)
    assert isinstance(off_runtime, dict)
    assert authority["provider"] == "PROVIDER_NEUTRAL_POSTGRESQL_18"
    assert authority["provider_apply_authorized"] is False
    assert authority["public_ingress_allowed"] is False
    assert authority["public_multi_user_enabled"] is False
    assert authority["real_trading_enabled"] is False
    assert authority["trading_methods_enabled"] is False
    assert authority["wp23_unlocked"] is False
    assert authority["authorized_recurring_rub"] == 0
    assert authority["protected_v9_entrypoint"] == "app:app"
    assert postgres["major"] == 18
    assert postgres["archive_format"] == "CUSTOM"
    assert postgres["required_dump_flags"] == [
        "--format=custom",
        "--no-privileges",
    ]
    assert postgres["required_restore_flags"] == [
        "--exit-on-error",
        "--no-owner",
        "--no-privileges",
    ]
    assert integrity["minimum_archive_bytes"] == 1
    assert off_runtime["encrypted_copy_required"] is True
    assert off_runtime["github_allowed"] is False
    assert off_runtime["ci_artifact_allowed"] is False
    assert off_runtime["plaintext_object_storage_allowed"] is False


def test_hosted_recovery_contract_path_is_provider_neutral() -> None:
    normalized = CONTRACT_PATH.as_posix().lower()
    assert "infrastructure/postgres" in normalized
    assert "cloudru" not in normalized


def test_legacy_dump_helper_is_not_exposed() -> None:
    assert not hasattr(hosted_recovery, "build_dump_command")


def test_recovery_manifest_accepts_exact_archive_and_boundary(tmp_path: Path) -> None:
    _validate_manifest(tmp_path, _manifest())


def test_recovery_manifest_accepts_allowlisted_fields_in_any_json_order(
    tmp_path: Path,
) -> None:
    manifest = _manifest()
    reordered = dict(reversed(tuple(manifest.items())))
    _validate_manifest(tmp_path, reordered)


def test_recovery_manifest_rejects_corrupt_archive(tmp_path: Path) -> None:
    with pytest.raises(HostedRecoveryContractError, match="ARCHIVE_SHA256_MISMATCH"):
        _validate_manifest(tmp_path, _manifest(), b"X" + _ARCHIVE[1:])


def test_recovery_manifest_rejects_empty_archive(tmp_path: Path) -> None:
    manifest = _manifest()
    manifest["archive_sha256"] = archive_sha256(b"")
    manifest["archive_size_bytes"] = 0
    with pytest.raises(HostedRecoveryContractError, match="ARCHIVE_SIZE_INVALID"):
        _validate_manifest(tmp_path, manifest, b"")


def test_stream_integrity_enforces_runtime_size_bound(tmp_path: Path) -> None:
    archive_path = _write_archive(tmp_path)
    with pytest.raises(HostedRecoveryContractError, match="ARCHIVE_SIZE_EXCEEDED"):
        _archive_file_integrity(
            archive_path,
            maximum_archive_bytes=len(_ARCHIVE) - 1,
        )


def test_recovery_manifest_rejects_declared_size_drift(tmp_path: Path) -> None:
    manifest = _manifest()
    manifest["archive_size_bytes"] = len(_ARCHIVE) + 1
    with pytest.raises(HostedRecoveryContractError, match="ARCHIVE_SIZE_MISMATCH"):
        _validate_manifest(tmp_path, manifest)


def test_recovery_manifest_rejects_invalid_or_mismatched_timestamp(
    tmp_path: Path,
) -> None:
    manifest = _manifest()
    manifest["created_at_utc"] = "2026-99-99T99:99:99Z"
    with pytest.raises(HostedRecoveryContractError, match="CREATED_AT_INVALID"):
        _validate_manifest(tmp_path, manifest)

    manifest = _manifest()
    manifest["created_at_utc"] = "2026-08-20T11:30:01Z"
    with pytest.raises(
        HostedRecoveryContractError,
        match="ARCHIVE_TIMESTAMP_MISMATCH",
    ):
        _validate_manifest(tmp_path, manifest)

    manifest = _manifest()
    invalid_name = "wp22a-20269999T999999Z-ea232a88b3ee.dump"
    manifest["archive_name"] = invalid_name
    with pytest.raises(
        HostedRecoveryContractError,
        match="ARCHIVE_TIMESTAMP_INVALID",
    ):
        _validate_manifest(tmp_path, manifest, archive_name=invalid_name)


def test_recovery_manifest_rejects_digest_suffix_drift(tmp_path: Path) -> None:
    manifest = _manifest()
    invalid_name = "wp22a-20260820T113000Z-000000000000.dump"
    manifest["archive_name"] = invalid_name
    with pytest.raises(
        HostedRecoveryContractError,
        match="ARCHIVE_DIGEST_SUFFIX_MISMATCH",
    ):
        _validate_manifest(
            tmp_path,
            manifest,
            archive_name=invalid_name,
        )


def test_recovery_manifest_rejects_partial_archive_name(tmp_path: Path) -> None:
    manifest = _manifest()
    manifest["archive_name"] = str(manifest["archive_name"]) + ".partial"
    with pytest.raises(HostedRecoveryContractError, match="PARTIAL_ARCHIVE_FORBIDDEN"):
        _validate_manifest(tmp_path, manifest)


def test_recovery_manifest_binds_manifest_to_exact_archive_path(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        HostedRecoveryContractError,
        match="ARCHIVE_MANIFEST_NAME_MISMATCH",
    ):
        _validate_manifest(tmp_path, _manifest(), archive_name=_ALT_ARCHIVE_NAME)


def test_recovery_manifest_rejects_release_or_boundary_drift(tmp_path: Path) -> None:
    manifest = _manifest()
    manifest["source_release_sha"] = "0" * 40
    with pytest.raises(HostedRecoveryContractError, match="SOURCE_RELEASE_MISMATCH"):
        _validate_manifest(tmp_path, manifest)

    manifest = _manifest()
    manifest["tenant_boundary_sha256"] = "0" * 64
    with pytest.raises(
        HostedRecoveryContractError,
        match="TENANT_BOUNDARY_SHA256_MISMATCH",
    ):
        _validate_manifest(tmp_path, manifest)


def test_recovery_manifest_rejects_forced_rls_drift(tmp_path: Path) -> None:
    manifest = _manifest()
    manifest["forced_rls_relations"] = list(_FORCED_RLS[:-1])
    with pytest.raises(HostedRecoveryContractError, match="FORCE_RLS_MISMATCH"):
        _validate_manifest(tmp_path, manifest)

    manifest = _manifest()
    manifest["forced_rls_relations"] = [*_FORCED_RLS[:-1], 1]
    with pytest.raises(HostedRecoveryContractError, match="FORCED_RLS_INVALID"):
        _validate_manifest(tmp_path, manifest)


def test_hosted_recovery_contract_rejects_encryption_drift() -> None:
    payload = deepcopy(_contract())
    off_runtime = payload["off_runtime"]
    assert isinstance(off_runtime, dict)
    off_runtime["encrypted_copy_required"] = False
    with pytest.raises(HostedRecoveryContractError, match="OFF_RUNTIME_DRIFT"):
        validate_hosted_recovery_contract(payload)


def test_restore_commands_validate_exact_archive_before_building_argv(
    tmp_path: Path,
) -> None:
    manifest = _manifest()
    archive_path = _write_archive(tmp_path)
    commands = _build_restore_commands(archive_path, manifest)
    assert commands == (
        ("pg_restore", "--list", str(archive_path)),
        (
            "pg_restore",
            "--exit-on-error",
            "--no-owner",
            "--no-privileges",
            "--dbname",
            "omni_restore_candidate",
            str(archive_path),
        ),
    )

    with pytest.raises(
        HostedRecoveryContractError,
        match="DESTINATION_DATABASE_INVALID",
    ):
        _build_restore_commands(
            archive_path,
            manifest,
            destination_database="invalid database",
        )
    with pytest.raises(
        HostedRecoveryContractError,
        match="RESTORE_TO_SOURCE_DATABASE_FORBIDDEN",
    ):
        _build_restore_commands(
            archive_path,
            manifest,
            destination_database="omni_hosted",
        )
    with pytest.raises(HostedRecoveryContractError, match="ARCHIVE_PATH_NOT_ABSOLUTE"):
        _build_restore_commands(Path(_ARCHIVE_NAME), manifest)


def test_restore_commands_reject_unverified_or_changed_archive(tmp_path: Path) -> None:
    manifest = _manifest()
    archive_path = _write_archive(tmp_path)
    archive_path.write_bytes(b"x" * len(_ARCHIVE))
    with pytest.raises(HostedRecoveryContractError, match="ARCHIVE_SHA256_MISMATCH"):
        _build_restore_commands(archive_path, manifest)

    partial_path = archive_path.with_name(f"{archive_path.name}.partial")
    partial_path.write_bytes(_ARCHIVE)
    with pytest.raises(HostedRecoveryContractError, match="PARTIAL_ARCHIVE_FORBIDDEN"):
        _build_restore_commands(partial_path, manifest)

    invalid_name_path = (tmp_path / "backup.dump").resolve()
    invalid_name_path.write_bytes(_ARCHIVE)
    with pytest.raises(HostedRecoveryContractError, match="ARCHIVE_NAME_INVALID"):
        _build_restore_commands(invalid_name_path, manifest)


def test_restore_evidence_requires_tenant_preserving_negatives() -> None:
    _validate_evidence(_evidence())

    for field in (
        "restored_into_separate_database",
        "restore_list_preflight_passed",
        "restore_catalog_rechecked",
        "replacement_runtime_recovery_rehearsed",
        "unscoped_access_denied",
        "cross_tenant_access_denied",
        "runtime_acl_reapplied",
        "rollback_release_available",
        "temporary_state_cleaned",
    ):
        evidence = _evidence()
        evidence[field] = False
        with pytest.raises(HostedRecoveryContractError, match=field.upper()):
            _validate_evidence(evidence)
