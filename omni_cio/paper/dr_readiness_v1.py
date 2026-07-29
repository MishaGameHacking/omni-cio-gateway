from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import stat
from typing import Literal

from pydantic import ValidationError

from omni_cio.contracts.v1.paper_dr import (
    PaperDrBlocker,
    PaperDrReadinessStatus,
    PaperDrWarning,
    PaperLedgerDrArchiveStateV1,
    PaperLedgerDrFilesystemCapacityV1,
    PaperLedgerDrManifestEvidenceV1,
    PaperLedgerDrReadinessPolicyV1,
    PaperLedgerDrReadinessV1,
    PaperLedgerDrTempArtifactV1,
)
from omni_cio.contracts.v1.paper_recovery import PaperLedgerLockDiagnosticV1
from omni_cio.paper.recovery_v1 import (
    PaperLedgerRecoveryError,
    diagnose_paper_ledger_writer_lock,
    parse_paper_ledger_recovery_manifest_unverified,
    verify_paper_ledger_backup_against_manifest,
    verify_paper_ledger_recovery_manifest,
)
from omni_cio.paper.storage_v1 import (
    ExternalPaperLedgerKeyManager,
    PaperLedgerStorageError,
    load_encrypted_paper_ledger_archive,
)


_MAX_MANIFEST_BYTES = 4 * 1024 * 1024
_MANIFEST_PATTERN = re.compile(
    r"^recovery-(?P<sequence>[0-9]{8})-(?P<digest>[0-9a-f]{64})\.plrm$"
)


class PaperLedgerDrAssessmentError(RuntimeError):
    """The DR assessment request itself is invalid or cannot be represented."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise PaperLedgerDrAssessmentError("PAPER_DR_TIMESTAMP_MUST_BE_AWARE")
    return result.astimezone(timezone.utc)


def _inspect_root(
    root: Path | str,
    *,
    blocker: PaperDrBlocker,
) -> tuple[Path | None, PaperDrBlocker | None]:
    path = Path(root)
    if path.is_symlink():
        return None, blocker
    try:
        resolved = path.resolve(strict=True)
    except (FileNotFoundError, OSError):
        return None, blocker
    try:
        info = resolved.stat()
    except OSError:
        return None, blocker
    if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077:
        return None, blocker
    return resolved, None


def _roots_independent(primary: Path, backup: Path) -> bool:
    return not (
        primary == backup
        or primary.is_relative_to(backup)
        or backup.is_relative_to(primary)
    )


def _capacity(
    root: Path,
    *,
    root_role: Literal["primary", "backup"],
    minimum_free_bytes: int,
) -> PaperLedgerDrFilesystemCapacityV1:
    try:
        usage = os.statvfs(root)
        device_id = root.stat().st_dev
    except OSError as exc:
        raise PaperLedgerDrAssessmentError("PAPER_DR_CAPACITY_READ_FAILED") from exc
    total_bytes = usage.f_frsize * usage.f_blocks
    free_bytes = usage.f_frsize * usage.f_bavail
    if total_bytes <= 0 or free_bytes < 0:
        raise PaperLedgerDrAssessmentError("PAPER_DR_CAPACITY_INVALID")
    return PaperLedgerDrFilesystemCapacityV1(
        root_role=root_role,
        device_id=device_id,
        total_bytes=total_bytes,
        free_bytes=free_bytes,
        minimum_free_bytes=minimum_free_bytes,
        sufficient=free_bytes >= minimum_free_bytes,
    )


def _lock_diagnostic(
    root: Path,
    *,
    assessed_at: datetime,
    stale_after_seconds: int,
) -> PaperLedgerLockDiagnosticV1:
    try:
        return diagnose_paper_ledger_writer_lock(
            root,
            observed_at=assessed_at,
            stale_after_seconds=stale_after_seconds,
        )
    except (PaperLedgerRecoveryError, OSError) as exc:
        raise PaperLedgerDrAssessmentError("PAPER_DR_LOCK_DIAGNOSTIC_FAILED") from exc


def _temp_artifacts(
    root: Path,
    *,
    root_role: Literal["primary", "backup"],
    assessed_at: datetime,
    maximum: int,
) -> tuple[PaperLedgerDrTempArtifactV1, ...]:
    try:
        candidates = sorted(
            path for path in root.iterdir() if path.name.startswith(".") and path.name.endswith(".tmp")
        )
    except OSError as exc:
        raise PaperLedgerDrAssessmentError("PAPER_DR_TEMP_SCAN_FAILED") from exc
    if len(candidates) > maximum:
        candidates = candidates[:maximum]
    artifacts: list[PaperLedgerDrTempArtifactV1] = []
    for path in candidates:
        try:
            info = path.lstat()
        except OSError as exc:
            raise PaperLedgerDrAssessmentError("PAPER_DR_TEMP_STAT_FAILED") from exc
        modified_at = datetime.fromtimestamp(info.st_mtime, tz=timezone.utc)
        age_seconds = max(0, int((assessed_at - modified_at).total_seconds()))
        artifacts.append(
            PaperLedgerDrTempArtifactV1(
                root_role=root_role,
                filename=path.name,
                size_bytes=max(0, info.st_size),
                modified_at=modified_at,
                age_seconds=age_seconds,
                regular_file=stat.S_ISREG(info.st_mode),
                symlink_detected=stat.S_ISLNK(info.st_mode),
                permissions_safe=not bool(info.st_mode & 0o077),
            )
        )
    return tuple(artifacts)


def _read_secure_manifest(path: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise PaperLedgerDrAssessmentError("PAPER_DR_MANIFEST_OPEN_FAILED") from exc
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise PaperLedgerDrAssessmentError("PAPER_DR_MANIFEST_NOT_REGULAR")
        if info.st_nlink != 1:
            raise PaperLedgerDrAssessmentError("PAPER_DR_MANIFEST_HARDLINK_FORBIDDEN")
        if info.st_mode & 0o077:
            raise PaperLedgerDrAssessmentError("PAPER_DR_MANIFEST_PERMISSIONS_UNSAFE")
        if info.st_size <= 0 or info.st_size > _MAX_MANIFEST_BYTES:
            raise PaperLedgerDrAssessmentError("PAPER_DR_MANIFEST_SIZE_INVALID")
        chunks: list[bytes] = []
        remaining = info.st_size
        while remaining:
            chunk = os.read(fd, min(remaining, 1024 * 1024))
            if not chunk:
                raise PaperLedgerDrAssessmentError("PAPER_DR_MANIFEST_TRUNCATED")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)
    finally:
        os.close(fd)


def _select_manifest(
    backup_root: Path,
) -> tuple[Path | None, tuple[PaperDrBlocker, ...], tuple[PaperDrWarning, ...]]:
    blockers: list[PaperDrBlocker] = []
    warnings: list[PaperDrWarning] = []
    try:
        candidates = sorted(backup_root.glob("*.plrm"))
    except OSError:
        return None, (PaperDrBlocker.MANIFEST_FILE_INVALID,), ()
    valid: list[tuple[int, Path]] = []
    for path in candidates:
        if path.is_symlink():
            blockers.append(PaperDrBlocker.MANIFEST_FILE_INVALID)
            continue
        match = _MANIFEST_PATTERN.fullmatch(path.name)
        if match is None:
            blockers.append(PaperDrBlocker.MANIFEST_FILE_INVALID)
            continue
        valid.append((int(match.group("sequence")), path))
    if not valid:
        blockers.append(PaperDrBlocker.MANIFEST_MISSING)
        return None, tuple(blockers), tuple(warnings)
    latest_sequence = max(sequence for sequence, _ in valid)
    latest = [path for sequence, path in valid if sequence == latest_sequence]
    if len(latest) != 1:
        blockers.append(PaperDrBlocker.MANIFEST_AMBIGUOUS)
        return None, tuple(blockers), tuple(warnings)
    if len(valid) > 1:
        warnings.append(PaperDrWarning.OLD_MANIFESTS_PRESENT)
    return latest[0], tuple(blockers), tuple(warnings)


def _archive_state(
    *,
    root_role: Literal["primary", "backup"],
    latest: object,
    assessed_at: datetime,
) -> PaperLedgerDrArchiveStateV1:
    sequence = getattr(latest, "sequence")
    record_digest = getattr(latest, "record_digest")
    sealed_at = getattr(latest, "sealed_at")
    ledger = getattr(latest, "ledger")
    event_count = len(getattr(ledger, "events"))
    age_seconds = max(0, int((assessed_at - sealed_at).total_seconds()))
    return PaperLedgerDrArchiveStateV1(
        root_role=root_role,
        latest_sequence=sequence,
        latest_record_digest=record_digest,
        latest_event_count=event_count,
        checkpoint_at=sealed_at,
        checkpoint_age_seconds=age_seconds,
    )


def _build_result(
    *,
    assessed_at: datetime,
    policy: PaperLedgerDrReadinessPolicyV1,
    primary_state: PaperLedgerDrArchiveStateV1 | None,
    backup_state: PaperLedgerDrArchiveStateV1 | None,
    manifest: PaperLedgerDrManifestEvidenceV1 | None,
    primary_lock: PaperLedgerLockDiagnosticV1 | None,
    backup_lock: PaperLedgerLockDiagnosticV1 | None,
    temp_artifacts: tuple[PaperLedgerDrTempArtifactV1, ...],
    capacities: tuple[PaperLedgerDrFilesystemCapacityV1, ...],
    blockers: set[PaperDrBlocker],
    warnings: set[PaperDrWarning],
    primary_backup_match: bool,
    separate_filesystem_device: bool,
) -> PaperLedgerDrReadinessV1:
    status = (
        PaperDrReadinessStatus.READY
        if not blockers
        else PaperDrReadinessStatus.BLOCKED
    )
    try:
        return PaperLedgerDrReadinessV1(
            assessed_at=assessed_at,
            status=status,
            policy=policy,
            primary_state=primary_state,
            backup_state=backup_state,
            manifest=manifest,
            primary_lock=primary_lock,
            backup_lock=backup_lock,
            temp_artifacts=temp_artifacts,
            temp_artifact_count=len(temp_artifacts),
            capacities=capacities,
            blockers=tuple(sorted(blockers, key=lambda value: value.value)),
            warnings=tuple(sorted(warnings, key=lambda value: value.value)),
            primary_backup_match=primary_backup_match,
            separate_filesystem_device=separate_filesystem_device,
        )
    except ValidationError as exc:
        raise PaperLedgerDrAssessmentError("PAPER_DR_RESULT_INVALID") from exc


def assess_paper_ledger_dr_readiness(
    primary_root: Path | str,
    backup_root: Path | str,
    *,
    key_manager: ExternalPaperLedgerKeyManager,
    signing_keys: Mapping[str, bytes],
    manifest_signing_keys: Mapping[str, bytes],
    assessed_at: datetime | None = None,
    policy: PaperLedgerDrReadinessPolicyV1 | None = None,
) -> PaperLedgerDrReadinessV1:
    """Assess paper-ledger disaster-recovery readiness without modifying storage."""

    timestamp = _aware_utc(assessed_at)
    effective_policy = policy or PaperLedgerDrReadinessPolicyV1()
    blockers: set[PaperDrBlocker] = set()
    warnings: set[PaperDrWarning] = set()
    capacities: list[PaperLedgerDrFilesystemCapacityV1] = []
    temp_artifacts: list[PaperLedgerDrTempArtifactV1] = []
    primary_state: PaperLedgerDrArchiveStateV1 | None = None
    backup_state: PaperLedgerDrArchiveStateV1 | None = None
    manifest_evidence: PaperLedgerDrManifestEvidenceV1 | None = None
    primary_lock: PaperLedgerLockDiagnosticV1 | None = None
    backup_lock: PaperLedgerLockDiagnosticV1 | None = None
    primary_backup_match = False
    separate_device = False

    primary, primary_error = _inspect_root(
        primary_root,
        blocker=PaperDrBlocker.PRIMARY_ROOT_INVALID,
    )
    backup, backup_error = _inspect_root(
        backup_root,
        blocker=PaperDrBlocker.BACKUP_ROOT_INVALID,
    )
    if primary_error is not None:
        blockers.add(primary_error)
    if backup_error is not None:
        blockers.add(backup_error)
    if primary is None or backup is None:
        return _build_result(
            assessed_at=timestamp,
            policy=effective_policy,
            primary_state=None,
            backup_state=None,
            manifest=None,
            primary_lock=None,
            backup_lock=None,
            temp_artifacts=(),
            capacities=(),
            blockers=blockers,
            warnings=warnings,
            primary_backup_match=False,
            separate_filesystem_device=False,
        )
    if not _roots_independent(primary, backup):
        blockers.add(PaperDrBlocker.ROOTS_NOT_INDEPENDENT)

    primary_capacity = _capacity(
        primary,
        root_role="primary",
        minimum_free_bytes=effective_policy.minimum_free_bytes_per_root,
    )
    backup_capacity = _capacity(
        backup,
        root_role="backup",
        minimum_free_bytes=effective_policy.minimum_free_bytes_per_root,
    )
    capacities.extend((primary_capacity, backup_capacity))
    if not primary_capacity.sufficient or not backup_capacity.sufficient:
        blockers.add(PaperDrBlocker.CAPACITY_INSUFFICIENT)
    separate_device = primary_capacity.device_id != backup_capacity.device_id
    if not separate_device:
        if effective_policy.require_separate_filesystem_device:
            blockers.add(PaperDrBlocker.FILESYSTEM_DEVICE_NOT_INDEPENDENT)
        else:
            warnings.add(PaperDrWarning.SAME_FILESYSTEM_DEVICE_ALLOWED)

    primary_lock = _lock_diagnostic(
        primary,
        assessed_at=timestamp,
        stale_after_seconds=effective_policy.lock_stale_after_seconds,
    )
    backup_lock = _lock_diagnostic(
        backup,
        assessed_at=timestamp,
        stale_after_seconds=effective_policy.lock_stale_after_seconds,
    )
    if primary_lock.status != "absent":
        blockers.add(PaperDrBlocker.PRIMARY_LOCK_PRESENT)
    if backup_lock.status != "absent":
        blockers.add(PaperDrBlocker.BACKUP_LOCK_PRESENT)

    temp_artifacts.extend(
        _temp_artifacts(
            primary,
            root_role="primary",
            assessed_at=timestamp,
            maximum=effective_policy.maximum_temp_artifacts_per_root,
        )
    )
    temp_artifacts.extend(
        _temp_artifacts(
            backup,
            root_role="backup",
            assessed_at=timestamp,
            maximum=effective_policy.maximum_temp_artifacts_per_root,
        )
    )
    if temp_artifacts:
        blockers.add(PaperDrBlocker.TEMP_ARTIFACT_PRESENT)

    manifest_path, manifest_blockers, manifest_warnings = _select_manifest(backup)
    blockers.update(manifest_blockers)
    warnings.update(manifest_warnings)
    serialized_manifest: bytes | None = None
    verified_manifest = None
    if manifest_path is not None:
        match = _MANIFEST_PATTERN.fullmatch(manifest_path.name)
        try:
            serialized_manifest = _read_secure_manifest(manifest_path)
            parsed = parse_paper_ledger_recovery_manifest_unverified(serialized_manifest)
        except (PaperLedgerDrAssessmentError, PaperLedgerRecoveryError):
            blockers.add(PaperDrBlocker.MANIFEST_FILE_INVALID)
        else:
            manifest_key = manifest_signing_keys.get(parsed.manifest_key_id)
            if manifest_key is None:
                blockers.add(PaperDrBlocker.MANIFEST_KEY_UNAVAILABLE)
            else:
                try:
                    verified_manifest = verify_paper_ledger_recovery_manifest(
                        serialized_manifest,
                        manifest_signing_key=manifest_key,
                    )
                except PaperLedgerRecoveryError:
                    blockers.add(PaperDrBlocker.MANIFEST_AUTHENTICATION_FAILED)
                else:
                    expected_sequence = int(match.group("sequence")) if match else -1
                    expected_digest = match.group("digest") if match else ""
                    if (
                        verified_manifest.latest_sequence != expected_sequence
                        or verified_manifest.manifest_digest != expected_digest
                    ):
                        blockers.add(PaperDrBlocker.MANIFEST_FILENAME_MISMATCH)
                    manifest_age = int((timestamp - verified_manifest.created_at).total_seconds())
                    if manifest_age < 0:
                        blockers.add(PaperDrBlocker.MANIFEST_TIME_IN_FUTURE)
                        manifest_age = 0
                    elif manifest_age > effective_policy.max_manifest_age_seconds:
                        blockers.add(PaperDrBlocker.MANIFEST_STALE)
                    try:
                        manifest_evidence = PaperLedgerDrManifestEvidenceV1(
                            filename=manifest_path.name,
                            manifest_digest=verified_manifest.manifest_digest,
                            manifest_key_id=verified_manifest.manifest_key_id,
                            backup_reference=verified_manifest.backup_reference,
                            created_at=verified_manifest.created_at,
                            age_seconds=manifest_age,
                            latest_sequence=verified_manifest.latest_sequence,
                            latest_record_digest=verified_manifest.latest_record_digest,
                            latest_event_count=verified_manifest.latest_event_count,
                        )
                    except ValidationError:
                        blockers.add(PaperDrBlocker.MANIFEST_FILENAME_MISMATCH)
                        manifest_evidence = None

    primary_latest = None
    try:
        primary_latest = load_encrypted_paper_ledger_archive(
            primary,
            key_manager=key_manager,
            signing_keys=signing_keys,
        )
    except PaperLedgerStorageError:
        blockers.add(PaperDrBlocker.PRIMARY_ARCHIVE_VERIFICATION_FAILED)
    else:
        primary_state = _archive_state(
            root_role="primary",
            latest=primary_latest,
            assessed_at=timestamp,
        )
        if primary_latest.sealed_at > timestamp:
            blockers.add(PaperDrBlocker.CHECKPOINT_TIME_IN_FUTURE)
        elif primary_state.checkpoint_age_seconds > effective_policy.max_checkpoint_age_seconds:
            blockers.add(PaperDrBlocker.CHECKPOINT_STALE)

    backup_latest = None
    if serialized_manifest is not None and verified_manifest is not None:
        manifest_key = manifest_signing_keys.get(verified_manifest.manifest_key_id)
        if manifest_key is not None:
            try:
                backup_latest = verify_paper_ledger_backup_against_manifest(
                    backup,
                    serialized_manifest,
                    key_manager=key_manager,
                    signing_keys=signing_keys,
                    manifest_signing_key=manifest_key,
                    expected_backup_reference=verified_manifest.backup_reference,
                )
            except PaperLedgerRecoveryError:
                blockers.add(PaperDrBlocker.BACKUP_ARCHIVE_VERIFICATION_FAILED)
            else:
                backup_state = _archive_state(
                    root_role="backup",
                    latest=backup_latest,
                    assessed_at=timestamp,
                )
                if backup_latest.sealed_at > timestamp:
                    blockers.add(PaperDrBlocker.CHECKPOINT_TIME_IN_FUTURE)
                elif backup_state.checkpoint_age_seconds > effective_policy.max_checkpoint_age_seconds:
                    blockers.add(PaperDrBlocker.CHECKPOINT_STALE)
    else:
        blockers.add(PaperDrBlocker.BACKUP_ARCHIVE_VERIFICATION_FAILED)

    if primary_latest is not None and backup_latest is not None:
        primary_backup_match = primary_latest == backup_latest
        if not primary_backup_match:
            blockers.add(PaperDrBlocker.SOURCE_BACKUP_MISMATCH)

    return _build_result(
        assessed_at=timestamp,
        policy=effective_policy,
        primary_state=primary_state,
        backup_state=backup_state,
        manifest=manifest_evidence,
        primary_lock=primary_lock,
        backup_lock=backup_lock,
        temp_artifacts=tuple(temp_artifacts),
        capacities=tuple(capacities),
        blockers=blockers,
        warnings=warnings,
        primary_backup_match=primary_backup_match,
        separate_filesystem_device=separate_device,
    )
