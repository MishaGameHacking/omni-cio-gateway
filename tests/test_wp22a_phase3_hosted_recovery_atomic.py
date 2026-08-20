from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from omni_cio.persistence.hosted_recovery_atomic_v1 import (
    build_staging_dump_command,
    finalize_staged_archive,
)
from omni_cio.persistence.hosted_recovery_v1 import HostedRecoveryContractError


_ARCHIVE = b"synthetic-pg18-custom-archive"


def test_staging_dump_command_uses_isolated_partial_path(tmp_path: Path) -> None:
    staging_dir = tmp_path.resolve()
    staging_path, command = build_staging_dump_command(
        staging_dir,
        "abc123def456",
        "omni_hosted",
    )

    assert staging_path == staging_dir / "wp22a-staging-abc123def456.dump.partial"
    assert command == (
        "pg_dump",
        "--format=custom",
        "--no-privileges",
        "--file",
        str(staging_path),
        "--dbname",
        "omni_hosted",
    )
    assert not staging_path.exists()


def test_staging_dump_command_rejects_existing_or_invalid_target(tmp_path: Path) -> None:
    staging_dir = tmp_path.resolve()
    existing = staging_dir / "wp22a-staging-abc123def456.dump.partial"
    existing.write_bytes(b"existing")

    with pytest.raises(HostedRecoveryContractError, match="STAGING_PATH_EXISTS"):
        build_staging_dump_command(staging_dir, "abc123def456", "omni_hosted")

    with pytest.raises(HostedRecoveryContractError, match="STAGING_NONCE_INVALID"):
        build_staging_dump_command(staging_dir, "../escape", "omni_hosted")

    with pytest.raises(HostedRecoveryContractError, match="SOURCE_DATABASE_INVALID"):
        build_staging_dump_command(staging_dir, "abc123def457", "postgres;drop")


def test_finalize_staged_archive_promotes_to_content_addressed_name(tmp_path: Path) -> None:
    staging_dir = tmp_path.resolve()
    staging_path, _ = build_staging_dump_command(staging_dir, "abc123def456", "omni_hosted")
    staging_path.write_bytes(_ARCHIVE)

    result = finalize_staged_archive(
        staging_path,
        created_at_utc="2026-08-20T17:15:30Z",
    )

    digest = sha256(_ARCHIVE).hexdigest()
    expected_name = f"wp22a-20260820T171530Z-{digest[:12]}.dump"
    final_path = staging_dir / expected_name
    assert result == {
        "created_at_utc": "2026-08-20T17:15:30Z",
        "archive_name": expected_name,
        "archive_path": str(final_path),
        "archive_sha256": digest,
        "archive_size_bytes": len(_ARCHIVE),
    }
    assert final_path.read_bytes() == _ARCHIVE
    assert not staging_path.exists()


def test_finalize_staged_archive_refuses_existing_final(tmp_path: Path) -> None:
    staging_dir = tmp_path.resolve()
    staging_path, _ = build_staging_dump_command(staging_dir, "abc123def456", "omni_hosted")
    staging_path.write_bytes(_ARCHIVE)
    digest = sha256(_ARCHIVE).hexdigest()
    final_path = staging_dir / f"wp22a-20260820T171530Z-{digest[:12]}.dump"
    final_path.write_bytes(b"do-not-overwrite")

    with pytest.raises(HostedRecoveryContractError, match="FINAL_ARCHIVE_EXISTS"):
        finalize_staged_archive(staging_path, created_at_utc="2026-08-20T17:15:30Z")

    assert final_path.read_bytes() == b"do-not-overwrite"
    assert staging_path.read_bytes() == _ARCHIVE


def test_finalize_staged_archive_rejects_empty_or_invalid_timestamp(tmp_path: Path) -> None:
    staging_dir = tmp_path.resolve()
    empty_path, _ = build_staging_dump_command(staging_dir, "abc123def456", "omni_hosted")
    empty_path.write_bytes(b"")
    with pytest.raises(HostedRecoveryContractError, match="ARCHIVE_SIZE_INVALID"):
        finalize_staged_archive(empty_path, created_at_utc="2026-08-20T17:15:30Z")

    empty_path.unlink()
    archive_path, _ = build_staging_dump_command(staging_dir, "abc123def457", "omni_hosted")
    archive_path.write_bytes(_ARCHIVE)
    with pytest.raises(HostedRecoveryContractError, match="CREATED_AT_INVALID"):
        finalize_staged_archive(archive_path, created_at_utc="2026-99-99T99:99:99Z")
