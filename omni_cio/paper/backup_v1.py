from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
import stat
from typing import Iterator, Literal
from uuid import uuid4

from pydantic import ValidationError

from omni_cio.contracts.v1.paper_backup import (
    PaperLedgerBackupFileResultV1,
    PaperLedgerBackupRestoreDrillV1,
    PaperLedgerManifestStorageReceiptV1,
)
from omni_cio.contracts.v1.paper_recovery import PaperLedgerRecoveryManifestV1
from omni_cio.paper.recovery_v1 import (
    PaperLedgerRecoveryError,
    build_paper_ledger_recovery_manifest,
    serialize_paper_ledger_recovery_manifest,
    verify_paper_ledger_backup_against_manifest,
    verify_paper_ledger_recovery_manifest,
)
from omni_cio.paper.storage_v1 import (
    ExternalPaperLedgerKeyManager,
    PaperLedgerStorageError,
    load_encrypted_paper_ledger_archive,
    parse_encrypted_paper_ledger_envelope,
)


_MAX_ARCHIVE_FILE_BYTES = 12 * 1024 * 1024
_MAX_MANIFEST_BYTES = 4 * 1024 * 1024
_MAX_ARCHIVE_FILES = 4096
_MIN_MANIFEST_KEY_BYTES = 32
_ARCHIVE_SUFFIX = ".plae"
_MANIFEST_SUFFIX = ".plrm"
_ARCHIVE_NAME_PATTERN = re.compile(
    r"^(?P<sequence>[0-9]{8})-(?P<digest>[0-9a-f]{64})\.plae$"
)
_KEY_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.:-]{2,127}$")
_BACKUP_REFERENCE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{2,255}$")
_STORAGE_LOCK_NAME = ".paper-ledger.lock"
_STORAGE_LOCK_CONTENT = b"paper-ledger-writer\n"


class PaperLedgerBackupError(RuntimeError):
    """Encrypted paper-ledger backup replication or restore drill failed closed."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise PaperLedgerBackupError("PAPER_BACKUP_TIMESTAMP_MUST_BE_AWARE")
    return result.astimezone(timezone.utc)


def _validate_manifest_inputs(
    *,
    manifest_signing_key: bytes,
    manifest_key_id: str,
    backup_reference: str,
) -> None:
    if (
        not isinstance(manifest_signing_key, bytes)
        or len(manifest_signing_key) < _MIN_MANIFEST_KEY_BYTES
    ):
        raise PaperLedgerBackupError("PAPER_BACKUP_MANIFEST_KEY_TOO_SHORT")
    if _KEY_ID_PATTERN.fullmatch(manifest_key_id) is None:
        raise PaperLedgerBackupError("PAPER_BACKUP_MANIFEST_KEY_ID_INVALID")
    if _BACKUP_REFERENCE_PATTERN.fullmatch(backup_reference) is None:
        raise PaperLedgerBackupError("PAPER_BACKUP_REFERENCE_INVALID")


def _resolve_primary(root: Path | str) -> Path:
    path = Path(root)
    if path.is_symlink():
        raise PaperLedgerBackupError("PAPER_BACKUP_PRIMARY_SYMLINK_FORBIDDEN")
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise PaperLedgerBackupError("PAPER_BACKUP_PRIMARY_MISSING") from exc
    if not resolved.is_dir():
        raise PaperLedgerBackupError("PAPER_BACKUP_PRIMARY_NOT_DIRECTORY")
    if resolved.stat().st_mode & 0o077:
        raise PaperLedgerBackupError("PAPER_BACKUP_PRIMARY_PERMISSIONS_UNSAFE")
    return resolved


def _prepare_backup(root: Path | str) -> Path:
    path = Path(root)
    if path.is_symlink():
        raise PaperLedgerBackupError("PAPER_BACKUP_ROOT_SYMLINK_FORBIDDEN")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    resolved = path.resolve(strict=True)
    if not resolved.is_dir():
        raise PaperLedgerBackupError("PAPER_BACKUP_ROOT_NOT_DIRECTORY")
    os.chmod(resolved, 0o700)
    return resolved


def _write_all(fd: int, payload: bytes) -> None:
    view = memoryview(payload)
    written = 0
    while written < len(view):
        amount = os.write(fd, view[written:])
        if amount <= 0:
            raise PaperLedgerBackupError("PAPER_BACKUP_WRITE_STALLED")
        written += amount


def _fsync_directory(root: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    fd = os.open(root, flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


@contextmanager
def _exclusive_storage_lock(root: Path) -> Iterator[None]:
    lock_path = root / _STORAGE_LOCK_NAME
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(lock_path, flags, 0o600)
    except FileExistsError as exc:
        raise PaperLedgerBackupError("PAPER_BACKUP_CONCURRENT_STORAGE_ACCESS") from exc
    except OSError as exc:
        raise PaperLedgerBackupError("PAPER_BACKUP_LOCK_CREATE_FAILED") from exc
    try:
        _write_all(fd, _STORAGE_LOCK_CONTENT)
        os.fsync(fd)
        yield
    finally:
        os.close(fd)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass
        _fsync_directory(root)


def _read_secure_file(path: Path, *, maximum_size: int) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise PaperLedgerBackupError("PAPER_BACKUP_FILE_OPEN_FAILED") from exc
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise PaperLedgerBackupError("PAPER_BACKUP_FILE_NOT_REGULAR")
        if info.st_nlink != 1:
            raise PaperLedgerBackupError("PAPER_BACKUP_FILE_HARDLINK_FORBIDDEN")
        if info.st_mode & 0o077:
            raise PaperLedgerBackupError("PAPER_BACKUP_FILE_PERMISSIONS_UNSAFE")
        if info.st_size <= 0 or info.st_size > maximum_size:
            raise PaperLedgerBackupError("PAPER_BACKUP_FILE_SIZE_INVALID")
        chunks: list[bytes] = []
        remaining = info.st_size
        while remaining:
            chunk = os.read(fd, min(remaining, 1024 * 1024))
            if not chunk:
                raise PaperLedgerBackupError("PAPER_BACKUP_FILE_TRUNCATED")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)
    finally:
        os.close(fd)


def _atomic_write(root: Path, target: Path, payload: bytes) -> None:
    temporary = root / f".{target.name}.{uuid4().hex}.tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(temporary, flags, 0o600)
    except OSError as exc:
        raise PaperLedgerBackupError("PAPER_BACKUP_TEMP_CREATE_FAILED") from exc
    try:
        _write_all(fd, payload)
        os.fsync(fd)
    except Exception:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise
    finally:
        os.close(fd)
    try:
        os.replace(temporary, target)
        os.chmod(target, 0o600)
        _fsync_directory(root)
    except Exception as exc:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise PaperLedgerBackupError("PAPER_BACKUP_ATOMIC_REPLACE_FAILED") from exc


def _source_archive_files(root: Path) -> tuple[tuple[Path, bytes, int, str, str], ...]:
    candidates = sorted(root.glob(f"*{_ARCHIVE_SUFFIX}"))
    if not candidates:
        raise PaperLedgerBackupError("PAPER_BACKUP_SOURCE_ARCHIVE_EMPTY")
    if len(candidates) > _MAX_ARCHIVE_FILES:
        raise PaperLedgerBackupError("PAPER_BACKUP_SOURCE_ARCHIVE_TOO_LARGE")

    files: list[tuple[Path, bytes, int, str, str]] = []
    for expected_sequence, path in enumerate(candidates, start=1):
        if path.is_symlink():
            raise PaperLedgerBackupError("PAPER_BACKUP_SOURCE_FILE_SYMLINK_FORBIDDEN")
        match = _ARCHIVE_NAME_PATTERN.fullmatch(path.name)
        if match is None:
            raise PaperLedgerBackupError("PAPER_BACKUP_SOURCE_FILENAME_INVALID")
        sequence = int(match.group("sequence"))
        if sequence != expected_sequence:
            raise PaperLedgerBackupError("PAPER_BACKUP_SOURCE_SEQUENCE_GAP")
        payload = _read_secure_file(path, maximum_size=_MAX_ARCHIVE_FILE_BYTES)
        try:
            envelope = parse_encrypted_paper_ledger_envelope(payload)
        except PaperLedgerStorageError as exc:
            raise PaperLedgerBackupError("PAPER_BACKUP_SOURCE_ENVELOPE_INVALID") from exc
        record_digest = match.group("digest")
        if envelope.sequence != sequence:
            raise PaperLedgerBackupError("PAPER_BACKUP_SOURCE_SEQUENCE_MISMATCH")
        if envelope.record_digest != record_digest:
            raise PaperLedgerBackupError("PAPER_BACKUP_SOURCE_DIGEST_MISMATCH")
        files.append(
            (
                path,
                payload,
                sequence,
                record_digest,
                hashlib.sha256(payload).hexdigest(),
            )
        )
    return tuple(files)


def _ensure_backup_has_no_extra_files(
    backup_root: Path,
    source_names: Sequence[str],
) -> None:
    source_set = set(source_names)
    backup_names = {path.name for path in backup_root.glob(f"*{_ARCHIVE_SUFFIX}")}
    extras = backup_names - source_set
    if extras:
        raise PaperLedgerBackupError("PAPER_BACKUP_EXTRA_ARCHIVE_FILES")


def _copy_archive_file(
    backup_root: Path,
    *,
    source_path: Path,
    source_payload: bytes,
    filename: str,
    sequence: int,
    record_digest: str,
    envelope_digest: str,
) -> PaperLedgerBackupFileResultV1:
    target = backup_root / filename
    outcome: Literal["copied", "already_present_identical"]
    atomic_write: bool
    if target.exists() or target.is_symlink():
        if target.is_symlink():
            raise PaperLedgerBackupError("PAPER_BACKUP_TARGET_SYMLINK_FORBIDDEN")
        if os.path.samefile(source_path, target):
            raise PaperLedgerBackupError("PAPER_BACKUP_TARGET_NOT_INDEPENDENT")
        existing = _read_secure_file(target, maximum_size=_MAX_ARCHIVE_FILE_BYTES)
        if existing != source_payload:
            raise PaperLedgerBackupError("PAPER_BACKUP_IMMUTABLE_FILE_CONFLICT")
        outcome = "already_present_identical"
        atomic_write = False
    else:
        _atomic_write(backup_root, target, source_payload)
        outcome = "copied"
        atomic_write = True
    try:
        return PaperLedgerBackupFileResultV1(
            sequence=sequence,
            filename=filename,
            record_digest=record_digest,
            envelope_digest=envelope_digest,
            size_bytes=len(source_payload),
            outcome=outcome,
            atomic_write=atomic_write,
        )
    except ValidationError as exc:
        raise PaperLedgerBackupError("PAPER_BACKUP_FILE_RESULT_INVALID") from exc


def _manifest_filename(manifest: PaperLedgerRecoveryManifestV1) -> str:
    return (
        f"recovery-{manifest.latest_sequence:08d}-"
        f"{manifest.manifest_digest}{_MANIFEST_SUFFIX}"
    )


def _store_manifest(
    backup_root: Path,
    manifest: PaperLedgerRecoveryManifestV1,
    *,
    manifest_signing_key: bytes,
    stored_at: datetime,
) -> PaperLedgerManifestStorageReceiptV1:
    payload = serialize_paper_ledger_recovery_manifest(manifest)
    verified = verify_paper_ledger_recovery_manifest(
        payload,
        manifest_signing_key=manifest_signing_key,
        expected_backup_reference=manifest.backup_reference,
    )
    if verified != manifest:
        raise PaperLedgerBackupError("PAPER_BACKUP_MANIFEST_ROUND_TRIP_MISMATCH")
    filename = _manifest_filename(manifest)
    target = backup_root / filename
    outcome: Literal["stored", "already_present_identical"]
    atomic_write: bool
    if target.exists() or target.is_symlink():
        if target.is_symlink():
            raise PaperLedgerBackupError("PAPER_BACKUP_MANIFEST_SYMLINK_FORBIDDEN")
        existing = _read_secure_file(target, maximum_size=_MAX_MANIFEST_BYTES)
        if existing != payload:
            raise PaperLedgerBackupError("PAPER_BACKUP_MANIFEST_IMMUTABLE_CONFLICT")
        outcome = "already_present_identical"
        atomic_write = False
    else:
        _atomic_write(backup_root, target, payload)
        outcome = "stored"
        atomic_write = True
    stored_payload = _read_secure_file(target, maximum_size=_MAX_MANIFEST_BYTES)
    verify_paper_ledger_recovery_manifest(
        stored_payload,
        manifest_signing_key=manifest_signing_key,
        expected_backup_reference=manifest.backup_reference,
    )
    try:
        return PaperLedgerManifestStorageReceiptV1(
            stored_at=stored_at,
            filename=filename,
            manifest_digest=manifest.manifest_digest,
            latest_sequence=manifest.latest_sequence,
            size_bytes=len(payload),
            outcome=outcome,
            atomic_write=atomic_write,
        )
    except ValidationError as exc:
        raise PaperLedgerBackupError("PAPER_BACKUP_MANIFEST_RECEIPT_INVALID") from exc


def run_paper_ledger_backup_restore_drill(
    primary_root: Path | str,
    backup_root: Path | str,
    *,
    key_manager: ExternalPaperLedgerKeyManager,
    signing_keys: Mapping[str, bytes],
    manifest_signing_key: bytes,
    manifest_key_id: str,
    backup_reference: str,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> PaperLedgerBackupRestoreDrillV1:
    """Replicate encrypted paper records and prove a complete backup restoration."""

    start = _aware_utc(started_at)
    completion_override = _aware_utc(completed_at) if completed_at is not None else None
    if completion_override is not None and completion_override < start:
        raise PaperLedgerBackupError("PAPER_BACKUP_COMPLETION_PREDATES_START")
    _validate_manifest_inputs(
        manifest_signing_key=manifest_signing_key,
        manifest_key_id=manifest_key_id,
        backup_reference=backup_reference,
    )
    primary = _resolve_primary(primary_root)
    backup_path = Path(backup_root)
    if backup_path.exists() and not backup_path.is_symlink():
        resolved_existing_backup = backup_path.resolve(strict=True)
        if os.path.samefile(primary, resolved_existing_backup):
            raise PaperLedgerBackupError("PAPER_BACKUP_ROOT_NOT_DISTINCT")
    backup = _prepare_backup(backup_path)
    if os.path.samefile(primary, backup):
        raise PaperLedgerBackupError("PAPER_BACKUP_ROOT_NOT_DISTINCT")

    with ExitStack() as stack:
        for root in sorted((primary, backup), key=lambda value: str(value)):
            stack.enter_context(_exclusive_storage_lock(root))

        try:
            source_latest_before = load_encrypted_paper_ledger_archive(
                primary,
                key_manager=key_manager,
                signing_keys=signing_keys,
            )
        except PaperLedgerStorageError as exc:
            raise PaperLedgerBackupError("PAPER_BACKUP_SOURCE_VERIFICATION_FAILED") from exc
        if (
            completion_override is not None
            and completion_override < source_latest_before.sealed_at
        ):
            raise PaperLedgerBackupError("PAPER_BACKUP_COMPLETION_PREDATES_SOURCE")

        source_files = _source_archive_files(primary)
        source_names = tuple(file[0].name for file in source_files)
        _ensure_backup_has_no_extra_files(backup, source_names)
        results = tuple(
            _copy_archive_file(
                backup,
                source_path=path,
                source_payload=payload,
                filename=path.name,
                sequence=sequence,
                record_digest=record_digest,
                envelope_digest=envelope_digest,
            )
            for path, payload, sequence, record_digest, envelope_digest in source_files
        )
        _ensure_backup_has_no_extra_files(backup, source_names)

        source_files_after = _source_archive_files(primary)
        if tuple(
            (item[0].name, item[4], len(item[1])) for item in source_files_after
        ) != tuple((item[0].name, item[4], len(item[1])) for item in source_files):
            raise PaperLedgerBackupError("PAPER_BACKUP_SOURCE_CHANGED_DURING_DRILL")
        try:
            source_latest_after = load_encrypted_paper_ledger_archive(
                primary,
                key_manager=key_manager,
                signing_keys=signing_keys,
            )
        except PaperLedgerStorageError as exc:
            raise PaperLedgerBackupError("PAPER_BACKUP_SOURCE_RECHECK_FAILED") from exc
        if source_latest_after != source_latest_before:
            raise PaperLedgerBackupError("PAPER_BACKUP_SOURCE_STATE_CHANGED")

        completion = completion_override or _aware_utc(None)
        try:
            manifest = build_paper_ledger_recovery_manifest(
                primary,
                backup,
                key_manager=key_manager,
                signing_keys=signing_keys,
                manifest_signing_key=manifest_signing_key,
                manifest_key_id=manifest_key_id,
                backup_reference=backup_reference,
                created_at=completion,
            )
        except PaperLedgerRecoveryError as exc:
            raise PaperLedgerBackupError("PAPER_BACKUP_MANIFEST_BUILD_FAILED") from exc
        receipt = _store_manifest(
            backup,
            manifest,
            manifest_signing_key=manifest_signing_key,
            stored_at=completion,
        )
        stored_manifest = _read_secure_file(
            backup / receipt.filename,
            maximum_size=_MAX_MANIFEST_BYTES,
        )
        try:
            restored_latest = verify_paper_ledger_backup_against_manifest(
                backup,
                stored_manifest,
                key_manager=key_manager,
                signing_keys=signing_keys,
                manifest_signing_key=manifest_signing_key,
                expected_backup_reference=backup_reference,
            )
        except PaperLedgerRecoveryError as exc:
            raise PaperLedgerBackupError("PAPER_BACKUP_RESTORE_DRILL_FAILED") from exc
        if restored_latest != source_latest_before:
            raise PaperLedgerBackupError("PAPER_BACKUP_RESTORED_STATE_MISMATCH")

    copied_count = sum(result.outcome == "copied" for result in results)
    already_present_count = len(results) - copied_count
    try:
        return PaperLedgerBackupRestoreDrillV1(
            started_at=start,
            completed_at=completion,
            backup_reference=backup_reference,
            source_latest_sequence=source_latest_before.sequence,
            source_latest_record_digest=source_latest_before.record_digest,
            source_event_count=len(source_latest_before.ledger.events),
            files=results,
            source_file_count=len(results),
            copied_count=copied_count,
            already_present_count=already_present_count,
            manifest=manifest,
            manifest_storage=receipt,
        )
    except ValidationError as exc:
        raise PaperLedgerBackupError("PAPER_BACKUP_DRILL_RESULT_INVALID") from exc
