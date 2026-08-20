from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
import hashlib
import hmac
import os
from pathlib import Path
import stat
from typing import Any

from ._hosted_recovery_contract_v1 import (
    _ARCHIVE_METADATA_RE,
    _ARCHIVE_NAME_RE,
    _EXPECTED_FORCED_RLS,
    _EXPECTED_MANIFEST_FIELDS,
    HostedRecoveryContractError,
    _as_mapping,
    _as_string_sequence,
    _require_created_at,
    _require_release_sha,
    _require_sha256,
    load_hosted_recovery_contract,
    validate_hosted_recovery_contract,
)


_CHUNK_BYTES = 1024 * 1024


def archive_sha256(archive_bytes: bytes) -> str:
    return hashlib.sha256(archive_bytes).hexdigest()


def _is_reparse_point(path: Path) -> bool:
    if os.name != "nt":
        return False
    try:
        attributes = getattr(
            path.stat(follow_symlinks=False),
            "st_file_attributes",
            0,
        )
    except OSError:
        return False
    return bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _require_final_archive_path(archive_path: Path) -> None:
    if not archive_path.is_absolute():
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_ARCHIVE_PATH_NOT_ABSOLUTE"
        )
    if archive_path.name.endswith(".partial"):
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_PARTIAL_ARCHIVE_FORBIDDEN"
        )
    if not _ARCHIVE_NAME_RE.fullmatch(archive_path.name):
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_ARCHIVE_NAME_INVALID"
        )
    try:
        metadata = archive_path.stat(follow_symlinks=False)
    except OSError as exc:
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_ARCHIVE_NOT_REGULAR_FILE"
        ) from exc
    if (
        archive_path.is_symlink()
        or _is_reparse_point(archive_path)
        or not stat.S_ISREG(metadata.st_mode)
    ):
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_ARCHIVE_NOT_REGULAR_FILE"
        )


def _archive_file_integrity(
    archive_path: Path,
    *,
    maximum_archive_bytes: int,
) -> tuple[int, str]:
    _require_final_archive_path(archive_path)
    try:
        path_before = archive_path.stat(follow_symlinks=False)
        digest = hashlib.sha256()
        observed_size = 0
        with archive_path.open("rb") as handle:
            handle_before = os.fstat(handle.fileno())
            if (
                path_before.st_dev,
                path_before.st_ino,
            ) != (
                handle_before.st_dev,
                handle_before.st_ino,
            ):
                raise HostedRecoveryContractError(
                    "HOSTED_RECOVERY_ARCHIVE_CHANGED_DURING_VALIDATION"
                )
            for chunk in iter(lambda: handle.read(_CHUNK_BYTES), b""):
                observed_size += len(chunk)
                if observed_size > maximum_archive_bytes:
                    raise HostedRecoveryContractError(
                        "HOSTED_RECOVERY_ARCHIVE_SIZE_EXCEEDED"
                    )
                digest.update(chunk)
            handle_after = os.fstat(handle.fileno())
        path_after = archive_path.stat(follow_symlinks=False)
    except HostedRecoveryContractError:
        raise
    except OSError as exc:
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_ARCHIVE_READ_INVALID"
        ) from exc

    identity_before = (path_before.st_dev, path_before.st_ino)
    identity_after = (path_after.st_dev, path_after.st_ino)
    handle_identity_before = (
        handle_before.st_dev,
        handle_before.st_ino,
    )
    handle_identity_after = (
        handle_after.st_dev,
        handle_after.st_ino,
    )
    if not (
        identity_before
        == identity_after
        == handle_identity_before
        == handle_identity_after
    ):
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_ARCHIVE_CHANGED_DURING_VALIDATION"
        )
    if (
        observed_size != path_before.st_size
        or path_after.st_size != path_before.st_size
        or handle_after.st_size != handle_before.st_size
        or path_before.st_mtime_ns != path_after.st_mtime_ns
        or handle_before.st_mtime_ns != handle_after.st_mtime_ns
        or path_before.st_ctime_ns != path_after.st_ctime_ns
        or handle_before.st_ctime_ns != handle_after.st_ctime_ns
    ):
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_ARCHIVE_CHANGED_DURING_VALIDATION"
        )
    return observed_size, digest.hexdigest()


def validate_recovery_manifest(
    manifest: Mapping[str, Any],
    archive_path: Path,
    *,
    expected_release_sha: str,
    expected_migration_sha256: str,
    expected_tenant_boundary_sha256: str,
    expected_schema_sha256: str,
    required_forced_rls_relations: Sequence[str],
    contract: Mapping[str, Any] | None = None,
) -> None:
    active_contract = (
        contract
        if contract is not None
        else load_hosted_recovery_contract()
    )
    validate_hosted_recovery_contract(active_contract)

    expected_release = _require_release_sha(
        expected_release_sha,
        "HOSTED_RECOVERY_EXPECTED_RELEASE_SHA_INVALID",
    )
    expected_migration = _require_sha256(
        expected_migration_sha256,
        "HOSTED_RECOVERY_EXPECTED_MIGRATION_SHA256_INVALID",
    )
    expected_tenant = _require_sha256(
        expected_tenant_boundary_sha256,
        "HOSTED_RECOVERY_EXPECTED_TENANT_BOUNDARY_SHA256_INVALID",
    )
    expected_schema = _require_sha256(
        expected_schema_sha256,
        "HOSTED_RECOVERY_EXPECTED_SCHEMA_SHA256_INVALID",
    )
    required_forced_rls = _as_string_sequence(
        required_forced_rls_relations,
        "HOSTED_RECOVERY_REQUIRED_FORCED_RLS_INVALID",
    )
    if required_forced_rls != _EXPECTED_FORCED_RLS:
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_REQUIRED_FORCED_RLS_DRIFT"
        )
    if set(manifest) != set(_EXPECTED_MANIFEST_FIELDS):
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_MANIFEST_FIELDS_INVALID"
        )

    bundle = _as_mapping(
        active_contract["bundle"],
        "HOSTED_RECOVERY_BUNDLE_INVALID",
    )
    integrity = _as_mapping(
        active_contract["integrity"],
        "HOSTED_RECOVERY_INTEGRITY_INVALID",
    )
    if manifest["schema_version"] != bundle["manifest_schema_version"]:
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_MANIFEST_VERSION_INVALID"
        )
    if manifest["backup_class"] != bundle["backup_class"]:
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_BACKUP_CLASS_INVALID"
        )

    created_at = _require_created_at(
        manifest["created_at_utc"],
        "HOSTED_RECOVERY_CREATED_AT_INVALID",
    )
    archive_name = manifest["archive_name"]
    if not isinstance(archive_name, str):
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_ARCHIVE_NAME_INVALID"
        )
    if archive_name.endswith(str(integrity["temporary_suffix"])):
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_PARTIAL_ARCHIVE_FORBIDDEN"
        )
    if "/" in archive_name or "\\" in archive_name or ".." in archive_name:
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_ARCHIVE_PATH_INVALID"
        )
    metadata_match = _ARCHIVE_METADATA_RE.fullmatch(archive_name)
    if metadata_match is None:
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_ARCHIVE_NAME_INVALID"
        )
    try:
        archive_created_at = datetime.strptime(
            metadata_match.group(1),
            "%Y%m%dT%H%M%SZ",
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_ARCHIVE_TIMESTAMP_INVALID"
        ) from exc
    if archive_created_at != created_at:
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_ARCHIVE_TIMESTAMP_MISMATCH"
        )

    _require_final_archive_path(archive_path)
    if archive_path.name != archive_name:
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_ARCHIVE_MANIFEST_NAME_MISMATCH"
        )

    archive_size = manifest["archive_size_bytes"]
    minimum_size = int(integrity["minimum_archive_bytes"])
    maximum_size = int(integrity["maximum_archive_bytes"])
    if type(archive_size) is not int or archive_size < minimum_size:
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_ARCHIVE_SIZE_INVALID"
        )
    if archive_size > maximum_size:
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_ARCHIVE_SIZE_EXCEEDED"
        )
    try:
        path_size = archive_path.stat(follow_symlinks=False).st_size
    except OSError as exc:
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_ARCHIVE_READ_INVALID"
        ) from exc
    if archive_size != path_size:
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_ARCHIVE_SIZE_MISMATCH"
        )

    actual_size, actual_hash = _archive_file_integrity(
        archive_path,
        maximum_archive_bytes=maximum_size,
    )
    if archive_size != actual_size:
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_ARCHIVE_CHANGED_DURING_VALIDATION"
        )
    declared_hash = _require_sha256(
        manifest["archive_sha256"],
        "HOSTED_RECOVERY_ARCHIVE_SHA256_INVALID",
    )
    if not hmac.compare_digest(declared_hash, actual_hash):
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_ARCHIVE_SHA256_MISMATCH"
        )
    if not hmac.compare_digest(
        metadata_match.group(2),
        declared_hash[:12],
    ):
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_ARCHIVE_DIGEST_SUFFIX_MISMATCH"
        )

    if manifest["postgres_major"] != 18:
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_POSTGRES_MAJOR_INVALID"
        )
    if manifest["archive_format"] != "CUSTOM":
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_ARCHIVE_FORMAT_INVALID"
        )

    source_release = _require_release_sha(
        manifest["source_release_sha"],
        "HOSTED_RECOVERY_RELEASE_SHA_INVALID",
    )
    if not hmac.compare_digest(source_release, expected_release):
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_SOURCE_RELEASE_MISMATCH"
        )

    expected_digests = {
        "migration_state_sha256": expected_migration,
        "tenant_boundary_sha256": expected_tenant,
        "schema_state_sha256": expected_schema,
    }
    for field, expected_value in expected_digests.items():
        actual_value = _require_sha256(
            manifest[field],
            f"HOSTED_RECOVERY_{field.upper()}_INVALID",
        )
        if not hmac.compare_digest(actual_value, expected_value):
            raise HostedRecoveryContractError(
                f"HOSTED_RECOVERY_{field.upper()}_MISMATCH"
            )

    forced_rls = _as_string_sequence(
        manifest["forced_rls_relations"],
        "HOSTED_RECOVERY_FORCED_RLS_INVALID",
    )
    if forced_rls != required_forced_rls:
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_FORCE_RLS_MISMATCH"
        )
    if manifest["encryption_state"] != bundle["encryption_state"]:
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_ENCRYPTION_STATE_INVALID"
        )
