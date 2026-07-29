from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import stat
from typing import Any

from pydantic import ValidationError

from omni_cio.contracts.v1.paper_archive import PaperLedgerArchiveRecordV1
from omni_cio.contracts.v1.paper_recovery import (
    PaperLedgerLockDiagnosticV1,
    PaperLedgerRecoveryFileV1,
    PaperLedgerRecoveryManifestV1,
    PaperLedgerRetentionPlanV1,
)
from omni_cio.paper.storage_v1 import (
    ExternalPaperLedgerKeyManager,
    PaperLedgerStorageError,
    load_encrypted_paper_ledger_archive,
    parse_encrypted_paper_ledger_envelope,
)


_MAX_ARCHIVE_FILE_BYTES = 12 * 1024 * 1024
_MAX_MANIFEST_BYTES = 4 * 1024 * 1024
_MIN_SIGNING_KEY_BYTES = 32
_ARCHIVE_NAME_PATTERN = re.compile(
    r"^(?P<sequence>[0-9]{8})-(?P<digest>[0-9a-f]{64})\.plae$"
)
_KEY_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.:-]{2,127}$")
_BACKUP_REFERENCE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{2,255}$")
_LOCK_NAME = ".paper-ledger.lock"
_LOCK_CONTENT = b"paper-ledger-writer\n"


class PaperLedgerRecoveryError(RuntimeError):
    """Recovery, backup or retention evidence failed closed."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise PaperLedgerRecoveryError("PAPER_RECOVERY_TIMESTAMP_MUST_BE_AWARE")
    return result.astimezone(timezone.utc)


def _validate_signing_key(signing_key: bytes) -> bytes:
    if not isinstance(signing_key, bytes) or len(signing_key) < _MIN_SIGNING_KEY_BYTES:
        raise PaperLedgerRecoveryError("PAPER_RECOVERY_SIGNING_KEY_TOO_SHORT")
    return signing_key


def _validate_key_id(value: str) -> str:
    if _KEY_ID_PATTERN.fullmatch(value) is None:
        raise PaperLedgerRecoveryError("PAPER_RECOVERY_KEY_ID_INVALID")
    return value


def _validate_backup_reference(value: str) -> str:
    if _BACKUP_REFERENCE_PATTERN.fullmatch(value) is None:
        raise PaperLedgerRecoveryError("PAPER_RECOVERY_BACKUP_REFERENCE_INVALID")
    return value


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PaperLedgerRecoveryError("PAPER_RECOVERY_CANONICALIZATION_FAILED") from exc


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PaperLedgerRecoveryError("PAPER_RECOVERY_DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _resolve_existing_directory(root: Path | str) -> Path:
    path = Path(root)
    if path.is_symlink():
        raise PaperLedgerRecoveryError("PAPER_RECOVERY_ROOT_SYMLINK_FORBIDDEN")
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise PaperLedgerRecoveryError("PAPER_RECOVERY_ROOT_MISSING") from exc
    if not resolved.is_dir():
        raise PaperLedgerRecoveryError("PAPER_RECOVERY_ROOT_NOT_DIRECTORY")
    return resolved


def _read_secure_archive_file(path: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise PaperLedgerRecoveryError("PAPER_RECOVERY_FILE_OPEN_FAILED") from exc
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise PaperLedgerRecoveryError("PAPER_RECOVERY_FILE_NOT_REGULAR")
        if info.st_mode & 0o077:
            raise PaperLedgerRecoveryError("PAPER_RECOVERY_FILE_PERMISSIONS_UNSAFE")
        if info.st_size <= 0 or info.st_size > _MAX_ARCHIVE_FILE_BYTES:
            raise PaperLedgerRecoveryError("PAPER_RECOVERY_FILE_SIZE_INVALID")
        chunks: list[bytes] = []
        remaining = info.st_size
        while remaining:
            chunk = os.read(fd, min(remaining, 1024 * 1024))
            if not chunk:
                raise PaperLedgerRecoveryError("PAPER_RECOVERY_FILE_TRUNCATED")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)
    finally:
        os.close(fd)


def _archive_evidence(root: Path | str) -> tuple[PaperLedgerRecoveryFileV1, ...]:
    storage_root = _resolve_existing_directory(root)
    candidates = sorted(storage_root.glob("*.plae"))
    if not candidates:
        raise PaperLedgerRecoveryError("PAPER_RECOVERY_ARCHIVE_EMPTY")

    evidence: list[PaperLedgerRecoveryFileV1] = []
    for expected_sequence, path in enumerate(candidates, start=1):
        if path.is_symlink():
            raise PaperLedgerRecoveryError("PAPER_RECOVERY_FILE_SYMLINK_FORBIDDEN")
        match = _ARCHIVE_NAME_PATTERN.fullmatch(path.name)
        if match is None:
            raise PaperLedgerRecoveryError("PAPER_RECOVERY_FILENAME_INVALID")
        sequence = int(match.group("sequence"))
        if sequence != expected_sequence:
            raise PaperLedgerRecoveryError("PAPER_RECOVERY_SEQUENCE_GAP")
        raw = _read_secure_archive_file(path)
        try:
            envelope = parse_encrypted_paper_ledger_envelope(raw)
        except PaperLedgerStorageError as exc:
            raise PaperLedgerRecoveryError("PAPER_RECOVERY_ENVELOPE_INVALID") from exc
        record_digest = match.group("digest")
        if envelope.sequence != sequence:
            raise PaperLedgerRecoveryError("PAPER_RECOVERY_FILENAME_SEQUENCE_MISMATCH")
        if envelope.record_digest != record_digest:
            raise PaperLedgerRecoveryError("PAPER_RECOVERY_FILENAME_DIGEST_MISMATCH")
        evidence.append(
            PaperLedgerRecoveryFileV1(
                sequence=sequence,
                filename=path.name,
                record_digest=record_digest,
                envelope_digest=_sha256(raw),
                size_bytes=len(raw),
            )
        )
    return tuple(evidence)


def _files_digest(files: Sequence[PaperLedgerRecoveryFileV1]) -> str:
    payload = [file.model_dump(mode="json") for file in files]
    return _sha256(_canonical_json_bytes(payload))


def _manifest_core(
    *,
    created_at: datetime,
    manifest_key_id: str,
    backup_reference: str,
    files: tuple[PaperLedgerRecoveryFileV1, ...],
    latest: PaperLedgerArchiveRecordV1,
) -> dict[str, object]:
    return {
        "format_version": "1.0",
        "manifest_format": "paper-ledger-recovery-manifest-v1",
        "authentication_algorithm": "hmac-sha256",
        "created_at": created_at.isoformat(),
        "manifest_key_id": manifest_key_id,
        "backup_reference": backup_reference,
        "files": [file.model_dump(mode="json") for file in files],
        "archive_file_count": len(files),
        "latest_sequence": latest.sequence,
        "latest_record_digest": latest.record_digest,
        "latest_event_count": len(latest.ledger.events),
        "files_digest": _files_digest(files),
        "primary_archive_verified": True,
        "backup_archive_verified": True,
        "checkpoint_verified": True,
        "full_chain_required_for_online_recovery": True,
        "retention_execution_allowed": False,
        "paper_only": True,
        "broker_order_created": False,
        "execution_ready": False,
        "trading_methods": False,
    }


def build_paper_ledger_recovery_manifest(
    primary_root: Path | str,
    backup_root: Path | str,
    *,
    key_manager: ExternalPaperLedgerKeyManager,
    signing_keys: Mapping[str, bytes],
    manifest_signing_key: bytes,
    manifest_key_id: str,
    backup_reference: str,
    created_at: datetime | None = None,
) -> PaperLedgerRecoveryManifestV1:
    """Verify primary and byte-identical backup archives before sealing a checkpoint."""

    key = _validate_signing_key(manifest_signing_key)
    normalized_key_id = _validate_key_id(manifest_key_id)
    normalized_reference = _validate_backup_reference(backup_reference)
    timestamp = _aware_utc(created_at)

    primary_files = _archive_evidence(primary_root)
    backup_files = _archive_evidence(backup_root)
    if primary_files != backup_files:
        raise PaperLedgerRecoveryError("PAPER_RECOVERY_BACKUP_EVIDENCE_MISMATCH")

    try:
        primary_latest = load_encrypted_paper_ledger_archive(
            primary_root,
            key_manager=key_manager,
            signing_keys=signing_keys,
        )
        backup_latest = load_encrypted_paper_ledger_archive(
            backup_root,
            key_manager=key_manager,
            signing_keys=signing_keys,
        )
    except PaperLedgerStorageError as exc:
        raise PaperLedgerRecoveryError("PAPER_RECOVERY_ARCHIVE_VERIFICATION_FAILED") from exc
    if primary_latest != backup_latest:
        raise PaperLedgerRecoveryError("PAPER_RECOVERY_BACKUP_STATE_MISMATCH")
    if timestamp < primary_latest.sealed_at:
        raise PaperLedgerRecoveryError("PAPER_RECOVERY_MANIFEST_PREDATES_ARCHIVE")

    core = _manifest_core(
        created_at=timestamp,
        manifest_key_id=normalized_key_id,
        backup_reference=normalized_reference,
        files=primary_files,
        latest=primary_latest,
    )
    core_bytes = _canonical_json_bytes(core)
    manifest_digest = _sha256(core_bytes)
    authentication_tag = hmac.new(key, core_bytes, hashlib.sha256).hexdigest()
    try:
        return PaperLedgerRecoveryManifestV1.model_validate(
            {
                **core,
                "manifest_digest": manifest_digest,
                "authentication_tag": authentication_tag,
            }
        )
    except ValidationError as exc:
        raise PaperLedgerRecoveryError("PAPER_RECOVERY_MANIFEST_INVALID") from exc


def serialize_paper_ledger_recovery_manifest(
    manifest: PaperLedgerRecoveryManifestV1,
) -> bytes:
    return _canonical_json_bytes(manifest.model_dump(mode="json"))


def parse_paper_ledger_recovery_manifest_unverified(
    serialized: bytes | str,
) -> PaperLedgerRecoveryManifestV1:
    if isinstance(serialized, str):
        raw = serialized.encode("utf-8")
    elif isinstance(serialized, bytes):
        raw = serialized
    else:
        raise PaperLedgerRecoveryError("PAPER_RECOVERY_INPUT_TYPE_INVALID")
    if not raw or len(raw) > _MAX_MANIFEST_BYTES:
        raise PaperLedgerRecoveryError("PAPER_RECOVERY_MANIFEST_SIZE_INVALID")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise PaperLedgerRecoveryError("PAPER_RECOVERY_UTF8_INVALID") from exc
    try:
        value = json.loads(text, object_pairs_hook=_no_duplicate_keys)
    except PaperLedgerRecoveryError:
        raise
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise PaperLedgerRecoveryError("PAPER_RECOVERY_JSON_INVALID") from exc
    if not isinstance(value, dict):
        raise PaperLedgerRecoveryError("PAPER_RECOVERY_ROOT_NOT_OBJECT")
    try:
        return PaperLedgerRecoveryManifestV1.model_validate(value)
    except ValidationError as exc:
        raise PaperLedgerRecoveryError("PAPER_RECOVERY_CONTRACT_INVALID") from exc


def _core_from_manifest(manifest: PaperLedgerRecoveryManifestV1) -> dict[str, object]:
    return _manifest_core(
        created_at=manifest.created_at,
        manifest_key_id=manifest.manifest_key_id,
        backup_reference=manifest.backup_reference,
        files=manifest.files,
        latest=PaperLedgerArchiveRecordV1.model_construct(
            sequence=manifest.latest_sequence,
            record_digest=manifest.latest_record_digest,
            ledger=type("LedgerSummary", (), {"events": range(manifest.latest_event_count)})(),
        ),
    )


def _manifest_core_from_fields(
    manifest: PaperLedgerRecoveryManifestV1,
) -> dict[str, object]:
    return {
        "format_version": manifest.format_version,
        "manifest_format": manifest.manifest_format,
        "authentication_algorithm": manifest.authentication_algorithm,
        "created_at": manifest.created_at.isoformat(),
        "manifest_key_id": manifest.manifest_key_id,
        "backup_reference": manifest.backup_reference,
        "files": [file.model_dump(mode="json") for file in manifest.files],
        "archive_file_count": manifest.archive_file_count,
        "latest_sequence": manifest.latest_sequence,
        "latest_record_digest": manifest.latest_record_digest,
        "latest_event_count": manifest.latest_event_count,
        "files_digest": manifest.files_digest,
        "primary_archive_verified": manifest.primary_archive_verified,
        "backup_archive_verified": manifest.backup_archive_verified,
        "checkpoint_verified": manifest.checkpoint_verified,
        "full_chain_required_for_online_recovery": (
            manifest.full_chain_required_for_online_recovery
        ),
        "retention_execution_allowed": manifest.retention_execution_allowed,
        "paper_only": manifest.paper_only,
        "broker_order_created": manifest.broker_order_created,
        "execution_ready": manifest.execution_ready,
        "trading_methods": manifest.trading_methods,
    }


def verify_paper_ledger_recovery_manifest(
    serialized: bytes | str,
    *,
    manifest_signing_key: bytes,
    expected_backup_reference: str | None = None,
) -> PaperLedgerRecoveryManifestV1:
    key = _validate_signing_key(manifest_signing_key)
    manifest = parse_paper_ledger_recovery_manifest_unverified(serialized)
    if expected_backup_reference is not None:
        expected = _validate_backup_reference(expected_backup_reference)
        if manifest.backup_reference != expected:
            raise PaperLedgerRecoveryError("PAPER_RECOVERY_BACKUP_REFERENCE_MISMATCH")
    if manifest.files_digest != _files_digest(manifest.files):
        raise PaperLedgerRecoveryError("PAPER_RECOVERY_FILES_DIGEST_MISMATCH")
    core_bytes = _canonical_json_bytes(_manifest_core_from_fields(manifest))
    expected_digest = _sha256(core_bytes)
    if not hmac.compare_digest(manifest.manifest_digest, expected_digest):
        raise PaperLedgerRecoveryError("PAPER_RECOVERY_MANIFEST_DIGEST_MISMATCH")
    expected_tag = hmac.new(key, core_bytes, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(manifest.authentication_tag, expected_tag):
        raise PaperLedgerRecoveryError("PAPER_RECOVERY_AUTHENTICATION_FAILED")
    return manifest


def verify_paper_ledger_backup_against_manifest(
    backup_root: Path | str,
    serialized_manifest: bytes | str,
    *,
    key_manager: ExternalPaperLedgerKeyManager,
    signing_keys: Mapping[str, bytes],
    manifest_signing_key: bytes,
    expected_backup_reference: str | None = None,
) -> PaperLedgerArchiveRecordV1:
    manifest = verify_paper_ledger_recovery_manifest(
        serialized_manifest,
        manifest_signing_key=manifest_signing_key,
        expected_backup_reference=expected_backup_reference,
    )
    if _archive_evidence(backup_root) != manifest.files:
        raise PaperLedgerRecoveryError("PAPER_RECOVERY_BACKUP_EVIDENCE_MISMATCH")
    try:
        latest = load_encrypted_paper_ledger_archive(
            backup_root,
            key_manager=key_manager,
            signing_keys=signing_keys,
        )
    except PaperLedgerStorageError as exc:
        raise PaperLedgerRecoveryError("PAPER_RECOVERY_BACKUP_VERIFICATION_FAILED") from exc
    if latest.sequence != manifest.latest_sequence:
        raise PaperLedgerRecoveryError("PAPER_RECOVERY_BACKUP_SEQUENCE_MISMATCH")
    if latest.record_digest != manifest.latest_record_digest:
        raise PaperLedgerRecoveryError("PAPER_RECOVERY_BACKUP_DIGEST_MISMATCH")
    if len(latest.ledger.events) != manifest.latest_event_count:
        raise PaperLedgerRecoveryError("PAPER_RECOVERY_BACKUP_EVENT_COUNT_MISMATCH")
    return latest


def build_paper_ledger_retention_plan(
    serialized_manifest: bytes | str,
    *,
    manifest_signing_key: bytes,
    keep_last_records: int,
    planned_at: datetime | None = None,
) -> PaperLedgerRetentionPlanV1:
    if isinstance(keep_last_records, bool) or keep_last_records <= 0:
        raise PaperLedgerRecoveryError("PAPER_RETENTION_KEEP_COUNT_INVALID")
    manifest = verify_paper_ledger_recovery_manifest(
        serialized_manifest,
        manifest_signing_key=manifest_signing_key,
    )
    if keep_last_records > manifest.archive_file_count:
        raise PaperLedgerRecoveryError("PAPER_RETENTION_KEEP_COUNT_EXCEEDS_ARCHIVE")
    candidate_count = manifest.archive_file_count - keep_last_records
    candidates = tuple(file.filename for file in manifest.files[:candidate_count])
    retained = tuple(file.filename for file in manifest.files[candidate_count:])
    try:
        return PaperLedgerRetentionPlanV1(
            planned_at=_aware_utc(planned_at),
            recovery_manifest_digest=manifest.manifest_digest,
            latest_sequence=manifest.latest_sequence,
            keep_last_records=keep_last_records,
            retained_files=retained,
            candidate_files=candidates,
            retained_count=len(retained),
            candidate_count=len(candidates),
            backup_restore_required=bool(candidates),
            online_chain_preserved_after_candidates=not candidates,
        )
    except ValidationError as exc:
        raise PaperLedgerRecoveryError("PAPER_RETENTION_PLAN_INVALID") from exc


def diagnose_paper_ledger_writer_lock(
    root: Path | str,
    *,
    observed_at: datetime | None = None,
    stale_after_seconds: int = 900,
) -> PaperLedgerLockDiagnosticV1:
    if isinstance(stale_after_seconds, bool) or stale_after_seconds <= 0:
        raise PaperLedgerRecoveryError("PAPER_LOCK_STALE_THRESHOLD_INVALID")
    timestamp = _aware_utc(observed_at)
    lock_path = Path(root) / _LOCK_NAME
    if not lock_path.lexists() if hasattr(lock_path, "lexists") else not os.path.lexists(lock_path):
        return PaperLedgerLockDiagnosticV1(
            observed_at=timestamp,
            status="absent",
            stale_after_seconds=stale_after_seconds,
            content_valid=False,
            permissions_safe=False,
            regular_file=False,
            symlink_detected=False,
        )

    info = lock_path.lstat()
    symlink_detected = stat.S_ISLNK(info.st_mode)
    regular_file = stat.S_ISREG(info.st_mode)
    permissions_safe = not bool(info.st_mode & 0o077)
    age_seconds = max(0, int(timestamp.timestamp() - info.st_mtime))
    content_valid = False
    if regular_file and not symlink_detected and info.st_size <= 1024:
        try:
            content_valid = _read_secure_archive_file(lock_path) == _LOCK_CONTENT
        except PaperLedgerRecoveryError:
            content_valid = False
    valid = content_valid and permissions_safe and regular_file and not symlink_detected
    if not valid:
        status_value = "invalid"
    elif age_seconds >= stale_after_seconds:
        status_value = "stale_candidate"
    else:
        status_value = "active"
    return PaperLedgerLockDiagnosticV1(
        observed_at=timestamp,
        status=status_value,
        age_seconds=age_seconds,
        stale_after_seconds=stale_after_seconds,
        content_valid=content_valid,
        permissions_safe=permissions_safe,
        regular_file=regular_file,
        symlink_detected=symlink_detected,
    )
