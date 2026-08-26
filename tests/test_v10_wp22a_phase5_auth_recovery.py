from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from omni_cio.persistence._hosted_recovery_contract_v1 import (
    HostedRecoveryContractError,
)
from omni_cio.persistence.phase5_auth_recovery_v1 import (
    build_phase5_post_restore_auth_commands,
    build_phase5_restore_commands,
    validate_phase5_post_restore_auth_evidence,
)


_ARCHIVE = b"synthetic-phase5-archive"
_RELEASE_SHA = "a" * 40
_MIGRATION_SHA = sha256(b"migration").hexdigest()
_TENANT_SHA = sha256(b"tenant").hexdigest()
_SCHEMA_SHA = sha256(b"schema").hexdigest()
_FORCED_RLS = [
    "broker_accounts",
    "broker_connections",
    "broker_connection_accounts",
]
_ARCHIVE_NAME = "wp22a-20260825T190000Z-" + sha256(_ARCHIVE).hexdigest()[:12] + ".dump"


def _manifest() -> dict[str, object]:
    return {
        "schema_version": "v10.wp22a.phase3.hosted-recovery-manifest.v1",
        "backup_class": "POSTGRES_LOGICAL_PRIVATE_STATE",
        "created_at_utc": "2026-08-25T19:00:00Z",
        "archive_name": _ARCHIVE_NAME,
        "archive_sha256": sha256(_ARCHIVE).hexdigest(),
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


def _archive(tmp_path: Path) -> Path:
    path = (tmp_path / _ARCHIVE_NAME).resolve()
    path.write_bytes(_ARCHIVE)
    return path


def test_post_restore_auth_cleanup_invalidates_only_ephemeral_authority() -> None:
    cleanup, verify = build_phase5_post_restore_auth_commands(
        "omni_restore_candidate"
    )

    cleanup_sql = cleanup[-1]
    assert cleanup[:5] == (
        "psql",
        "--dbname",
        "omni_restore_candidate",
        "--set",
        "ON_ERROR_STOP=1",
    )
    assert "DELETE FROM omni_cio_v10.provider_auth_transactions" in cleanup_sql
    assert "DELETE FROM omni_cio_v10.web_sessions" in cleanup_sql
    assert "tenants" not in cleanup_sql
    assert "users" not in cleanup_sql
    assert "broker_connections" not in cleanup_sql

    verify_sql = verify[-1]
    assert "provider_auth_transactions" in verify_sql
    assert "web_sessions" in verify_sql
    assert "--tuples-only" in verify
    assert "--no-align" in verify


def test_phase5_restore_sequence_cannot_expose_restored_sessions_before_cleanup(
    tmp_path: Path,
) -> None:
    commands = build_phase5_restore_commands(
        _archive(tmp_path),
        "omni_restore_candidate",
        source_database="omni_hosted",
        manifest=_manifest(),
        expected_release_sha=_RELEASE_SHA,
        expected_migration_sha256=_MIGRATION_SHA,
        expected_tenant_boundary_sha256=_TENANT_SHA,
        expected_schema_sha256=_SCHEMA_SHA,
        required_forced_rls_relations=_FORCED_RLS,
    )

    assert len(commands) == 4
    preflight, restore, cleanup, verify = commands
    assert preflight[:2] == ("pg_restore", "--list")
    assert restore[0] == "pg_restore"
    assert "provider_auth_transactions" in cleanup[-1]
    assert "web_sessions" in cleanup[-1]
    assert "provider_auth_transactions" in verify[-1]
    assert "web_sessions" in verify[-1]


def test_post_restore_auth_cleanup_rejects_invalid_database_name() -> None:
    for invalid in ("", "invalid database", "-prod", "prod;drop"):
        with pytest.raises(
            HostedRecoveryContractError,
            match="HOSTED_RECOVERY_DESTINATION_DATABASE_INVALID",
        ):
            build_phase5_post_restore_auth_commands(invalid)


def test_post_restore_auth_evidence_requires_zero_ephemeral_authority() -> None:
    evidence = {
        "web_sessions_remaining": 0,
        "provider_auth_transactions_remaining": 0,
        "runtime_not_exposed_before_invalidation": True,
    }
    validate_phase5_post_restore_auth_evidence(evidence)

    for field in (
        "web_sessions_remaining",
        "provider_auth_transactions_remaining",
    ):
        failed = dict(evidence)
        failed[field] = 1
        with pytest.raises(HostedRecoveryContractError, match="ZERO_REQUIRED"):
            validate_phase5_post_restore_auth_evidence(failed)

    exposed = dict(evidence)
    exposed["runtime_not_exposed_before_invalidation"] = False
    with pytest.raises(
        HostedRecoveryContractError,
        match="RUNTIME_EXPOSURE_BLOCK_REQUIRED",
    ):
        validate_phase5_post_restore_auth_evidence(exposed)


def test_phase5_auth_evidence_rejects_boolean_count_and_extra_field() -> None:
    with pytest.raises(HostedRecoveryContractError, match="ZERO_REQUIRED"):
        validate_phase5_post_restore_auth_evidence(
            {
                "web_sessions_remaining": False,
                "provider_auth_transactions_remaining": 0,
                "runtime_not_exposed_before_invalidation": True,
            }
        )

    with pytest.raises(HostedRecoveryContractError, match="FIELDS_INVALID"):
        validate_phase5_post_restore_auth_evidence(
            {
                "web_sessions_remaining": 0,
                "provider_auth_transactions_remaining": 0,
                "runtime_not_exposed_before_invalidation": True,
                "unexpected": True,
            }
        )
