from __future__ import annotations

from datetime import datetime
import hashlib
import os
from pathlib import Path
import re
from typing import Final

from omni_cio.persistence.hosted_recovery_v1 import HostedRecoveryContractError


_STAGING_NAME_RE: Final = re.compile(r"^wp22a-staging-([a-z0-9]{12,64})\.dump\.partial$")
_DATABASE_RE: Final = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
_CREATED_AT_RE: Final = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
_MIN_ARCHIVE_BYTES: Final = 1
_MAX_ARCHIVE_BYTES: Final = 4_294_967_296
_CHUNK_BYTES: Final = 1024 * 1024


def _require_regular_directory(path: Path) -> Path:
    if not path.is_absolute():
        raise HostedRecoveryContractError("HOSTED_RECOVERY_STAGING_DIR_NOT_ABSOLUTE")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise HostedRecoveryContractError("HOSTED_RECOVERY_STAGING_DIR_INVALID") from exc
    if resolved != path or path.is_symlink() or not path.is_dir():
        raise HostedRecoveryContractError("HOSTED_RECOVERY_STAGING_DIR_INVALID")
    return path


def _require_staging_path(path: Path) -> Path:
    if not path.is_absolute():
        raise HostedRecoveryContractError("HOSTED_RECOVERY_STAGING_PATH_NOT_ABSOLUTE")
    if not _STAGING_NAME_RE.fullmatch(path.name):
        raise HostedRecoveryContractError("HOSTED_RECOVERY_STAGING_NAME_INVALID")
    _require_regular_directory(path.parent)
    if path.is_symlink():
        raise HostedRecoveryContractError("HOSTED_RECOVERY_STAGING_PATH_INVALID")
    return path


def build_staging_dump_command(
    staging_dir: Path,
    nonce: str,
    source_database: str,
) -> tuple[Path, tuple[str, ...]]:
    """Build an argv-only pg_dump command targeting a fresh isolated staging path."""
    staging_dir = _require_regular_directory(staging_dir)
    if not re.fullmatch(r"[a-z0-9]{12,64}", nonce):
        raise HostedRecoveryContractError("HOSTED_RECOVERY_STAGING_NONCE_INVALID")
    if not _DATABASE_RE.fullmatch(source_database):
        raise HostedRecoveryContractError("HOSTED_RECOVERY_SOURCE_DATABASE_INVALID")

    staging_path = staging_dir / f"wp22a-staging-{nonce}.dump.partial"
    _require_staging_path(staging_path)
    if staging_path.exists():
        raise HostedRecoveryContractError("HOSTED_RECOVERY_STAGING_PATH_EXISTS")

    return staging_path, (
        "pg_dump",
        "--format=custom",
        "--no-privileges",
        "--file",
        str(staging_path),
        "--dbname",
        source_database,
    )


def _parse_created_at(created_at_utc: str) -> datetime:
    if not isinstance(created_at_utc, str) or not _CREATED_AT_RE.fullmatch(created_at_utc):
        raise HostedRecoveryContractError("HOSTED_RECOVERY_CREATED_AT_INVALID")
    try:
        return datetime.strptime(created_at_utc, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise HostedRecoveryContractError("HOSTED_RECOVERY_CREATED_AT_INVALID") from exc


def _stream_integrity(path: Path) -> tuple[int, str]:
    try:
        before = path.stat()
        if path.is_symlink() or not path.is_file():
            raise HostedRecoveryContractError("HOSTED_RECOVERY_STAGING_NOT_REGULAR_FILE")
        digest = hashlib.sha256()
        observed = 0
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(_CHUNK_BYTES), b""):
                observed += len(chunk)
                if observed > _MAX_ARCHIVE_BYTES:
                    raise HostedRecoveryContractError("HOSTED_RECOVERY_ARCHIVE_SIZE_EXCEEDED")
                digest.update(chunk)
        after = path.stat()
    except HostedRecoveryContractError:
        raise
    except OSError as exc:
        raise HostedRecoveryContractError("HOSTED_RECOVERY_ARCHIVE_READ_INVALID") from exc

    if observed < _MIN_ARCHIVE_BYTES:
        raise HostedRecoveryContractError("HOSTED_RECOVERY_ARCHIVE_SIZE_INVALID")
    if before.st_size != observed or after.st_size != observed or before.st_mtime_ns != after.st_mtime_ns:
        raise HostedRecoveryContractError("HOSTED_RECOVERY_ARCHIVE_CHANGED_DURING_VALIDATION")
    return observed, digest.hexdigest()


def _sync_directory(directory: Path) -> None:
    """Best-effort directory fsync; unsupported platforms preserve file-fsync semantics."""
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    try:
        fd = os.open(directory, flags)
    except OSError:
        return
    try:
        try:
            os.fsync(fd)
        except OSError:
            return
    finally:
        os.close(fd)


def finalize_staged_archive(
    staging_path: Path,
    *,
    created_at_utc: str,
) -> dict[str, object]:
    """Atomically promote one completed staging archive to a content-addressed final name."""
    staging_path = _require_staging_path(staging_path)
    if not staging_path.exists():
        raise HostedRecoveryContractError("HOSTED_RECOVERY_STAGING_PATH_MISSING")

    created_at = _parse_created_at(created_at_utc)
    archive_size, archive_sha256 = _stream_integrity(staging_path)
    final_name = f"wp22a-{created_at.strftime('%Y%m%dT%H%M%SZ')}-{archive_sha256[:12]}.dump"
    final_path = staging_path.with_name(final_name)
    if final_path.exists() or final_path.is_symlink():
        raise HostedRecoveryContractError("HOSTED_RECOVERY_FINAL_ARCHIVE_EXISTS")

    try:
        with staging_path.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(staging_path, final_path)
        _sync_directory(final_path.parent)
        promoted_size, promoted_sha256 = _stream_integrity(final_path)
        if promoted_size != archive_size or promoted_sha256 != archive_sha256:
            raise HostedRecoveryContractError("HOSTED_RECOVERY_POST_PROMOTION_VALIDATION_FAILED")
        if not final_path.name.endswith(f"-{archive_sha256[:12]}.dump"):
            raise HostedRecoveryContractError("HOSTED_RECOVERY_FINAL_ARCHIVE_DIGEST_SUFFIX_INVALID")
    except HostedRecoveryContractError:
        if final_path.exists() and not staging_path.exists():
            try:
                final_path.unlink()
            finally:
                _sync_directory(final_path.parent)
        raise
    except OSError as exc:
        if final_path.exists() and not staging_path.exists():
            try:
                final_path.unlink()
            finally:
                _sync_directory(final_path.parent)
        raise HostedRecoveryContractError("HOSTED_RECOVERY_ATOMIC_PROMOTION_FAILED") from exc

    return {
        "created_at_utc": created_at_utc,
        "archive_name": final_path.name,
        "archive_path": str(final_path),
        "archive_sha256": archive_sha256,
        "archive_size_bytes": archive_size,
    }
