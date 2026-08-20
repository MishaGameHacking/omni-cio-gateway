from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path

import pytest

import omni_cio.persistence.hosted_recovery_atomic_v1 as atomic
from omni_cio.persistence.hosted_recovery_atomic_v1 import (
    build_staging_dump_command,
    finalize_staged_archive,
)
from omni_cio.persistence.hosted_recovery_v1 import HostedRecoveryContractError


_ARCHIVE = b"synthetic-pg18-custom-archive"
_CREATED_AT = "2026-08-20T17:15:30Z"


def _staged_archive(tmp_path: Path, nonce: str = "abc123def456") -> Path:
    staging_path, _ = build_staging_dump_command(
        tmp_path.resolve(),
        nonce,
        "omni_hosted",
    )
    staging_path.write_bytes(_ARCHIVE)
    return staging_path


def _final_path(tmp_path: Path) -> Path:
    digest = sha256(_ARCHIVE).hexdigest()
    return tmp_path.resolve() / f"wp22a-20260820T171530Z-{digest[:12]}.dump"


def test_staging_dump_command_uses_isolated_partial_path(
    tmp_path: Path,
) -> None:
    staging_dir = tmp_path.resolve()
    staging_path, command = build_staging_dump_command(
        staging_dir,
        "abc123def456",
        "omni_hosted",
    )

    assert staging_path == staging_dir / (
        "wp22a-staging-abc123def456.dump.partial"
    )
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


def test_staging_dump_command_rejects_existing_or_invalid_target(
    tmp_path: Path,
) -> None:
    staging_dir = tmp_path.resolve()
    existing = staging_dir / "wp22a-staging-abc123def456.dump.partial"
    existing.write_bytes(b"existing")

    with pytest.raises(
        HostedRecoveryContractError,
        match="STAGING_PATH_EXISTS",
    ):
        build_staging_dump_command(
            staging_dir,
            "abc123def456",
            "omni_hosted",
        )

    with pytest.raises(
        HostedRecoveryContractError,
        match="STAGING_NONCE_INVALID",
    ):
        build_staging_dump_command(
            staging_dir,
            "../escape",
            "omni_hosted",
        )

    with pytest.raises(
        HostedRecoveryContractError,
        match="SOURCE_DATABASE_INVALID",
    ):
        build_staging_dump_command(
            staging_dir,
            "abc123def457",
            "invalid database",
        )


def test_finalize_staged_archive_promotes_to_content_addressed_name(
    tmp_path: Path,
) -> None:
    staging_path = _staged_archive(tmp_path)

    result = finalize_staged_archive(
        staging_path,
        created_at_utc=_CREATED_AT,
    )

    digest = sha256(_ARCHIVE).hexdigest()
    final_path = _final_path(tmp_path)
    assert result == {
        "created_at_utc": _CREATED_AT,
        "archive_name": final_path.name,
        "archive_path": str(final_path),
        "archive_sha256": digest,
        "archive_size_bytes": len(_ARCHIVE),
    }
    assert final_path.read_bytes() == _ARCHIVE
    assert not staging_path.exists()


def test_finalize_staged_archive_refuses_existing_final(
    tmp_path: Path,
) -> None:
    staging_path = _staged_archive(tmp_path)
    final_path = _final_path(tmp_path)
    final_path.write_bytes(b"do-not-overwrite")

    with pytest.raises(
        HostedRecoveryContractError,
        match="FINAL_ARCHIVE_EXISTS",
    ):
        finalize_staged_archive(
            staging_path,
            created_at_utc=_CREATED_AT,
        )

    assert final_path.read_bytes() == b"do-not-overwrite"
    assert staging_path.read_bytes() == _ARCHIVE


def test_finalize_staged_archive_rejects_racing_final_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    staging_path = _staged_archive(tmp_path)
    final_path = _final_path(tmp_path)
    real_link = os.link

    def competing_link(
        source: os.PathLike[str] | str,
        destination: os.PathLike[str] | str,
        *,
        follow_symlinks: bool = True,
    ) -> None:
        Path(destination).write_bytes(b"competing-final")
        real_link(
            source,
            destination,
            follow_symlinks=follow_symlinks,
        )

    monkeypatch.setattr(os, "link", competing_link)

    with pytest.raises(
        HostedRecoveryContractError,
        match="FINAL_ARCHIVE_EXISTS",
    ):
        finalize_staged_archive(
            staging_path,
            created_at_utc=_CREATED_AT,
        )

    assert final_path.read_bytes() == b"competing-final"
    assert staging_path.read_bytes() == _ARCHIVE


def test_publish_postcheck_failure_removes_only_owned_final(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    staging_path = _staged_archive(tmp_path)
    final_path = _final_path(tmp_path)
    real_identity = atomic._regular_identity
    calls = 0

    def failing_identity(
        path: Path,
        code: str,
    ) -> atomic._FileIdentity:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise HostedRecoveryContractError(
                "HOSTED_RECOVERY_POST_PROMOTION_VALIDATION_FAILED"
            )
        return real_identity(path, code)

    monkeypatch.setattr(atomic, "_regular_identity", failing_identity)

    with pytest.raises(
        HostedRecoveryContractError,
        match="POST_PROMOTION_VALIDATION_FAILED",
    ):
        finalize_staged_archive(
            staging_path,
            created_at_utc=_CREATED_AT,
        )

    assert not final_path.exists()
    assert staging_path.read_bytes() == _ARCHIVE


def test_finalize_staged_archive_preserves_staging_on_postcheck_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    staging_path = _staged_archive(tmp_path)
    final_path = _final_path(tmp_path)
    real_stream = atomic._stream_integrity
    calls = 0

    def failing_postcheck(
        path: Path,
    ) -> tuple[int, str, atomic._FileIdentity]:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise HostedRecoveryContractError(
                "HOSTED_RECOVERY_POST_PROMOTION_VALIDATION_FAILED"
            )
        return real_stream(path)

    monkeypatch.setattr(atomic, "_stream_integrity", failing_postcheck)

    with pytest.raises(
        HostedRecoveryContractError,
        match="POST_PROMOTION_VALIDATION_FAILED",
    ):
        finalize_staged_archive(
            staging_path,
            created_at_utc=_CREATED_AT,
        )

    assert not final_path.exists()
    assert staging_path.read_bytes() == _ARCHIVE


def test_finalize_staged_archive_keeps_verified_final_on_cleanup_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    staging_path = _staged_archive(tmp_path)
    final_path = _final_path(tmp_path)

    def fail_cleanup(
        path: Path,
        expected_identity: atomic._FileIdentity,
    ) -> None:
        del path, expected_identity
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_STAGING_CLEANUP_FAILED"
        )

    monkeypatch.setattr(atomic, "_remove_staging_link", fail_cleanup)

    with pytest.raises(
        HostedRecoveryContractError,
        match="STAGING_CLEANUP_FAILED",
    ):
        finalize_staged_archive(
            staging_path,
            created_at_utc=_CREATED_AT,
        )

    assert final_path.read_bytes() == _ARCHIVE
    assert staging_path.read_bytes() == _ARCHIVE


def test_finalize_staged_archive_rejects_empty_or_invalid_timestamp(
    tmp_path: Path,
) -> None:
    staging_dir = tmp_path.resolve()
    empty_path, _ = build_staging_dump_command(
        staging_dir,
        "abc123def456",
        "omni_hosted",
    )
    empty_path.write_bytes(b"")
    with pytest.raises(
        HostedRecoveryContractError,
        match="ARCHIVE_SIZE_INVALID",
    ):
        finalize_staged_archive(
            empty_path,
            created_at_utc=_CREATED_AT,
        )

    empty_path.unlink()
    archive_path = _staged_archive(tmp_path, nonce="abc123def457")
    with pytest.raises(
        HostedRecoveryContractError,
        match="CREATED_AT_INVALID",
    ):
        finalize_staged_archive(
            archive_path,
            created_at_utc="2026-99-99T99:99:99Z",
        )
