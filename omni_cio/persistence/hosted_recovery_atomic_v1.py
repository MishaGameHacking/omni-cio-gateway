from __future__ import annotations

from datetime import datetime
import hashlib
import os
from pathlib import Path
import re
import stat
from typing import Final

from omni_cio.persistence.hosted_recovery_v1 import HostedRecoveryContractError


_STAGING_NAME_RE: Final = re.compile(
    r"^wp22a-staging-([a-z0-9]{12,64})\.dump\.partial$"
)
_DATABASE_RE: Final = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
_CREATED_AT_RE: Final = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"
)
_MIN_ARCHIVE_BYTES: Final = 1
_MAX_ARCHIVE_BYTES: Final = 4_294_967_296
_CHUNK_BYTES: Final = 1024 * 1024

_FileIdentity = tuple[int, int]
_FileSnapshot = tuple[int, int, int, int, int]


def _identity(value: os.stat_result) -> _FileIdentity:
    return value.st_dev, value.st_ino


def _snapshot(value: os.stat_result) -> _FileSnapshot:
    return (
        value.st_dev,
        value.st_ino,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _is_reparse(value: os.stat_result) -> bool:
    if os.name != "nt":
        return False
    attributes = getattr(value, "st_file_attributes", 0)
    return bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _lstat(path: Path, code: str) -> os.stat_result:
    try:
        return path.stat(follow_symlinks=False)
    except OSError as exc:
        raise HostedRecoveryContractError(code) from exc


def _require_regular_directory(path: Path) -> Path:
    if not path.is_absolute():
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_STAGING_DIR_NOT_ABSOLUTE"
        )
    try:
        resolved = path.resolve(strict=True)
        metadata = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_STAGING_DIR_INVALID"
        ) from exc
    if (
        resolved != path
        or _is_reparse(metadata)
        or not stat.S_ISDIR(metadata.st_mode)
    ):
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_STAGING_DIR_INVALID"
        )
    return path


def _require_staging_path(path: Path) -> Path:
    if not path.is_absolute():
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_STAGING_PATH_NOT_ABSOLUTE"
        )
    if not _STAGING_NAME_RE.fullmatch(path.name):
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_STAGING_NAME_INVALID"
        )
    _require_regular_directory(path.parent)
    return path


def _entry_exists(path: Path) -> bool:
    try:
        path.stat(follow_symlinks=False)
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_STAGING_PATH_INVALID"
        ) from exc
    return True


def build_staging_dump_command(
    staging_dir: Path,
    nonce: str,
    source_database: str,
) -> tuple[Path, tuple[str, ...]]:
    """Build pg_dump argv targeting a fresh isolated staging path."""
    staging_dir = _require_regular_directory(staging_dir)
    if not re.fullmatch(r"[a-z0-9]{12,64}", nonce):
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_STAGING_NONCE_INVALID"
        )
    if not _DATABASE_RE.fullmatch(source_database):
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_SOURCE_DATABASE_INVALID"
        )

    staging_path = staging_dir / f"wp22a-staging-{nonce}.dump.partial"
    _require_staging_path(staging_path)
    if _entry_exists(staging_path):
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_STAGING_PATH_EXISTS"
        )

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
    if (
        not isinstance(created_at_utc, str)
        or not _CREATED_AT_RE.fullmatch(created_at_utc)
    ):
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_CREATED_AT_INVALID"
        )
    try:
        return datetime.strptime(created_at_utc, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_CREATED_AT_INVALID"
        ) from exc


def _stream_integrity(path: Path) -> tuple[int, str, _FileIdentity]:
    try:
        before = path.stat(follow_symlinks=False)
        if _is_reparse(before) or not stat.S_ISREG(before.st_mode):
            raise HostedRecoveryContractError(
                "HOSTED_RECOVERY_STAGING_NOT_REGULAR_FILE"
            )

        digest = hashlib.sha256()
        observed = 0
        with path.open("rb") as handle:
            opened_before = os.fstat(handle.fileno())
            if _snapshot(opened_before) != _snapshot(before):
                raise HostedRecoveryContractError(
                    "HOSTED_RECOVERY_ARCHIVE_CHANGED_DURING_VALIDATION"
                )
            for chunk in iter(lambda: handle.read(_CHUNK_BYTES), b""):
                observed += len(chunk)
                if observed > _MAX_ARCHIVE_BYTES:
                    raise HostedRecoveryContractError(
                        "HOSTED_RECOVERY_ARCHIVE_SIZE_EXCEEDED"
                    )
                digest.update(chunk)
            os.fsync(handle.fileno())
            opened_after = os.fstat(handle.fileno())
        after = path.stat(follow_symlinks=False)
    except HostedRecoveryContractError:
        raise
    except OSError as exc:
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_ARCHIVE_READ_INVALID"
        ) from exc

    if observed < _MIN_ARCHIVE_BYTES:
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_ARCHIVE_SIZE_INVALID"
        )
    expected_snapshot = _snapshot(before)
    if (
        _snapshot(opened_before) != expected_snapshot
        or _snapshot(opened_after) != expected_snapshot
        or _snapshot(after) != expected_snapshot
        or observed != before.st_size
    ):
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_ARCHIVE_CHANGED_DURING_VALIDATION"
        )
    return observed, digest.hexdigest(), _identity(before)


def _sync_directory(directory: Path) -> None:
    """Best-effort directory fsync where the platform supports it."""
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


def _regular_identity(path: Path, code: str) -> _FileIdentity:
    metadata = _lstat(path, code)
    if _is_reparse(metadata) or not stat.S_ISREG(metadata.st_mode):
        raise HostedRecoveryContractError(code)
    return _identity(metadata)


def _unlink_if_identity(
    path: Path,
    expected_identity: _FileIdentity,
) -> None:
    try:
        metadata = path.stat(follow_symlinks=False)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_PUBLICATION_CLEANUP_FAILED"
        ) from exc
    if (
        _is_reparse(metadata)
        or not stat.S_ISREG(metadata.st_mode)
        or _identity(metadata) != expected_identity
    ):
        return
    try:
        path.unlink()
        _sync_directory(path.parent)
    except OSError as exc:
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_PUBLICATION_CLEANUP_FAILED"
        ) from exc


def _publish_no_clobber(
    staging_path: Path,
    final_path: Path,
    expected_identity: _FileIdentity,
) -> None:
    if (
        _regular_identity(
            staging_path,
            "HOSTED_RECOVERY_STAGING_NOT_REGULAR_FILE",
        )
        != expected_identity
    ):
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_ARCHIVE_CHANGED_DURING_VALIDATION"
        )

    linked = False
    try:
        os.link(
            staging_path,
            final_path,
            follow_symlinks=False,
        )
        linked = True

        final_identity = _regular_identity(
            final_path,
            "HOSTED_RECOVERY_POST_PROMOTION_VALIDATION_FAILED",
        )
        if final_identity != expected_identity:
            raise HostedRecoveryContractError(
                "HOSTED_RECOVERY_POST_PROMOTION_VALIDATION_FAILED"
            )
        _sync_directory(final_path.parent)
    except FileExistsError as exc:
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_FINAL_ARCHIVE_EXISTS"
        ) from exc
    except HostedRecoveryContractError:
        if linked:
            _unlink_if_identity(final_path, expected_identity)
        raise
    except OSError as exc:
        if linked:
            _unlink_if_identity(final_path, expected_identity)
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_ATOMIC_PUBLICATION_FAILED"
        ) from exc


def _remove_staging_link(
    staging_path: Path,
    expected_identity: _FileIdentity,
) -> None:
    if (
        _regular_identity(
            staging_path,
            "HOSTED_RECOVERY_STAGING_NOT_REGULAR_FILE",
        )
        != expected_identity
    ):
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_STAGING_CHANGED_DURING_PROMOTION"
        )
    try:
        staging_path.unlink()
        _sync_directory(staging_path.parent)
    except OSError as exc:
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_STAGING_CLEANUP_FAILED"
        ) from exc


def finalize_staged_archive(
    staging_path: Path,
    *,
    created_at_utc: str,
) -> dict[str, object]:
    """Publish one validated staging archive without clobbering final state."""
    staging_path = _require_staging_path(staging_path)
    if not _entry_exists(staging_path):
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_STAGING_PATH_MISSING"
        )

    created_at = _parse_created_at(created_at_utc)
    archive_size, archive_sha256, expected_identity = _stream_integrity(
        staging_path
    )
    final_name = (
        f"wp22a-{created_at.strftime('%Y%m%dT%H%M%SZ')}-"
        f"{archive_sha256[:12]}.dump"
    )
    final_path = staging_path.with_name(final_name)

    published = False
    final_verified = False
    try:
        _publish_no_clobber(
            staging_path,
            final_path,
            expected_identity,
        )
        published = True

        promoted_size, promoted_sha256, promoted_identity = _stream_integrity(
            final_path
        )
        if (
            promoted_identity != expected_identity
            or promoted_size != archive_size
            or promoted_sha256 != archive_sha256
        ):
            raise HostedRecoveryContractError(
                "HOSTED_RECOVERY_POST_PROMOTION_VALIDATION_FAILED"
            )
        if not final_path.name.endswith(f"-{archive_sha256[:12]}.dump"):
            raise HostedRecoveryContractError(
                "HOSTED_RECOVERY_FINAL_ARCHIVE_DIGEST_SUFFIX_INVALID"
            )
        final_verified = True

        _remove_staging_link(staging_path, expected_identity)
    except HostedRecoveryContractError:
        if published and not final_verified:
            _unlink_if_identity(final_path, expected_identity)
        raise
    except OSError as exc:
        if published and not final_verified:
            _unlink_if_identity(final_path, expected_identity)
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_ATOMIC_PROMOTION_FAILED"
        ) from exc

    return {
        "created_at_utc": created_at_utc,
        "archive_name": final_path.name,
        "archive_path": str(final_path),
        "archive_sha256": archive_sha256,
        "archive_size_bytes": archive_size,
    }
