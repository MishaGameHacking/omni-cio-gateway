from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
import hashlib
import hmac
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "infrastructure" / "cloudru" / "wp22a" / "hosted-recovery-contract.json"

_EXPECTED_CONTRACT_FIELDS = (
    "schema_version",
    "authority",
    "postgres",
    "integrity",
    "bundle",
    "tenant_boundary",
    "restore",
    "off_runtime",
)
_EXPECTED_AUTHORITY = {
    "provider": "Cloud.ru Evolution",
    "source_only": True,
    "provider_apply_authorized": False,
    "public_ingress_allowed": False,
    "authorized_recurring_rub": 0,
    "public_multi_user_enabled": False,
    "trading_methods_enabled": False,
    "real_trading_enabled": False,
    "protected_v9_entrypoint": "app:app",
    "wp23_unlocked": False,
}
_EXPECTED_DUMP_FLAGS = ("--format=custom", "--no-privileges")
_EXPECTED_RESTORE_FLAGS = ("--exit-on-error", "--no-owner", "--no-privileges")
_EXPECTED_FORCED_RLS = (
    "broker_accounts",
    "broker_connections",
    "broker_connection_accounts",
)
_EXPECTED_MANIFEST_FIELDS = (
    "schema_version",
    "backup_class",
    "created_at_utc",
    "archive_name",
    "archive_sha256",
    "archive_size_bytes",
    "postgres_major",
    "archive_format",
    "source_release_sha",
    "migration_state_sha256",
    "tenant_boundary_sha256",
    "schema_state_sha256",
    "forced_rls_relations",
    "encryption_state",
)
_ARCHIVE_NAME_PATTERN = r"wp22a-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{12}\.dump"
_ARCHIVE_NAME_RE = re.compile(_ARCHIVE_NAME_PATTERN)
_ARCHIVE_TIMESTAMP_RE = re.compile(
    r"^wp22a-([0-9]{8}T[0-9]{6}Z)-[a-f0-9]{12}\.dump$"
)
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
_RELEASE_SHA_RE = re.compile(r"^[a-f0-9]{40}$")
_CREATED_AT_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
_DATABASE_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


class HostedRecoveryContractError(RuntimeError):
    """Fail-closed hosted recovery contract violation."""


def _as_mapping(value: object, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise HostedRecoveryContractError(code)
    return value


def _as_string_sequence(value: object, code: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise HostedRecoveryContractError(code)
    normalized = tuple(str(item) for item in value)
    if len(normalized) != len(set(normalized)):
        raise HostedRecoveryContractError(code)
    return normalized


def _require_exact_mapping(actual: Mapping[str, Any], expected: Mapping[str, object], code: str) -> None:
    if set(actual) != set(expected):
        raise HostedRecoveryContractError(code)
    for key, expected_value in expected.items():
        actual_value = actual[key]
        if type(actual_value) is not type(expected_value) or actual_value != expected_value:
            raise HostedRecoveryContractError(code)


def _require_sha256(value: object, code: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise HostedRecoveryContractError(code)
    return value


def _require_release_sha(value: object, code: str) -> str:
    if not isinstance(value, str) or not _RELEASE_SHA_RE.fullmatch(value):
        raise HostedRecoveryContractError(code)
    return value


def _require_created_at(value: object, code: str) -> str:
    if not isinstance(value, str) or not _CREATED_AT_RE.fullmatch(value):
        raise HostedRecoveryContractError(code)
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise HostedRecoveryContractError(code) from exc
    return value


def load_hosted_recovery_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    if path.resolve(strict=False) != CONTRACT_PATH.resolve(strict=False):
        raise HostedRecoveryContractError("HOSTED_RECOVERY_CONTRACT_PATH_INVALID")
    payload = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise HostedRecoveryContractError("HOSTED_RECOVERY_CONTRACT_NOT_OBJECT")
    return payload


def validate_hosted_recovery_contract(payload: Mapping[str, Any]) -> None:
    if set(payload) != set(_EXPECTED_CONTRACT_FIELDS):
        raise HostedRecoveryContractError("HOSTED_RECOVERY_CONTRACT_FIELDS_INVALID")
    if payload.get("schema_version") != "v10.wp22a.phase3.hosted-recovery.v1":
        raise HostedRecoveryContractError("HOSTED_RECOVERY_CONTRACT_VERSION_INVALID")

    authority = _as_mapping(payload.get("authority"), "HOSTED_RECOVERY_AUTHORITY_INVALID")
    _require_exact_mapping(authority, _EXPECTED_AUTHORITY, "HOSTED_RECOVERY_AUTHORITY_DRIFT")

    postgres = _as_mapping(payload.get("postgres"), "HOSTED_RECOVERY_POSTGRES_INVALID")
    _require_exact_mapping(
        postgres,
        {
            "major": 18,
            "backup_tool": "pg_dump",
            "restore_tool": "pg_restore",
            "archive_format": "CUSTOM",
            "required_dump_flags": list(_EXPECTED_DUMP_FLAGS),
            "required_restore_flags": list(_EXPECTED_RESTORE_FLAGS),
            "restore_list_preflight_required": True,
            "restore_into_separate_database_required": True,
            "restore_exit_on_error_required": True,
            "runtime_acl_reapply_required": True,
            "forced_rls_reverify_required": True,
        },
        "HOSTED_RECOVERY_POSTGRES_DRIFT",
    )

    integrity = _as_mapping(payload.get("integrity"), "HOSTED_RECOVERY_INTEGRITY_INVALID")
    _require_exact_mapping(
        integrity,
        {
            "algorithm": "SHA256",
            "hash_before_restore_required": True,
            "archive_size_bound_required": True,
            "atomic_promotion_required": True,
            "temporary_suffix": ".partial",
            "corrupt_backup_rejection_required": True,
            "minimum_archive_bytes": 1,
            "maximum_archive_bytes": 4294967296,
        },
        "HOSTED_RECOVERY_INTEGRITY_DRIFT",
    )

    bundle = _as_mapping(payload.get("bundle"), "HOSTED_RECOVERY_BUNDLE_INVALID")
    _require_exact_mapping(
        bundle,
        {
            "backup_class": "POSTGRES_LOGICAL_PRIVATE_STATE",
            "archive_name_pattern": _ARCHIVE_NAME_PATTERN,
            "manifest_schema_version": "v10.wp22a.phase3.hosted-recovery-manifest.v1",
            "allowed_manifest_fields": list(_EXPECTED_MANIFEST_FIELDS),
            "encryption_state": "EXTERNAL_ENVELOPE_REQUIRED",
        },
        "HOSTED_RECOVERY_BUNDLE_DRIFT",
    )

    tenant_boundary = _as_mapping(
        payload.get("tenant_boundary"), "HOSTED_RECOVERY_TENANT_BOUNDARY_INVALID"
    )
    _require_exact_mapping(
        tenant_boundary,
        {
            "tenant_setting": "omni_cio.tenant_id",
            "raw_tenant_ids_in_manifest_allowed": False,
            "tenant_boundary_digest_required": True,
            "forced_rls_relations": list(_EXPECTED_FORCED_RLS),
            "cross_tenant_negative_rehearsal_required": True,
            "unscoped_default_deny_required": True,
        },
        "HOSTED_RECOVERY_TENANT_BOUNDARY_DRIFT",
    )

    restore = _as_mapping(payload.get("restore"), "HOSTED_RECOVERY_RESTORE_INVALID")
    _require_exact_mapping(
        restore,
        {
            "replacement_runtime_required": True,
            "accepted_release_sha_match_required": True,
            "migration_state_match_required": True,
            "schema_state_match_required": True,
            "tenant_boundary_match_required": True,
            "restore_catalog_recheck_required": True,
            "restore_to_original_database_in_rehearsal_allowed": False,
            "rollback_to_last_accepted_release_required": True,
            "temporary_state_cleanup_required": True,
        },
        "HOSTED_RECOVERY_RESTORE_DRIFT",
    )

    off_runtime = _as_mapping(payload.get("off_runtime"), "HOSTED_RECOVERY_OFF_RUNTIME_INVALID")
    _require_exact_mapping(
        off_runtime,
        {
            "encrypted_copy_required": True,
            "github_allowed": False,
            "ci_artifact_allowed": False,
            "plaintext_object_storage_allowed": False,
            "real_provider_credentials_in_source_allowed": False,
            "real_broker_credentials_in_source_allowed": False,
        },
        "HOSTED_RECOVERY_OFF_RUNTIME_DRIFT",
    )


def archive_sha256(archive_bytes: bytes) -> str:
    return hashlib.sha256(archive_bytes).hexdigest()


def _require_final_archive_path(archive_path: Path) -> None:
    if not archive_path.is_absolute():
        raise HostedRecoveryContractError("HOSTED_RECOVERY_ARCHIVE_PATH_NOT_ABSOLUTE")
    if archive_path.name.endswith(".partial"):
        raise HostedRecoveryContractError("HOSTED_RECOVERY_PARTIAL_ARCHIVE_FORBIDDEN")
    if not _ARCHIVE_NAME_RE.fullmatch(archive_path.name):
        raise HostedRecoveryContractError("HOSTED_RECOVERY_ARCHIVE_NAME_INVALID")
    if archive_path.is_symlink() or not archive_path.is_file():
        raise HostedRecoveryContractError("HOSTED_RECOVERY_ARCHIVE_NOT_REGULAR_FILE")


def _archive_file_integrity(archive_path: Path) -> tuple[int, str]:
    _require_final_archive_path(archive_path)
    try:
        size_before = archive_path.stat().st_size
        digest = hashlib.sha256()
        observed_size = 0
        with archive_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                observed_size += len(chunk)
                digest.update(chunk)
        size_after = archive_path.stat().st_size
    except OSError as exc:
        raise HostedRecoveryContractError("HOSTED_RECOVERY_ARCHIVE_READ_INVALID") from exc
    if observed_size != size_before or size_after != size_before:
        raise HostedRecoveryContractError("HOSTED_RECOVERY_ARCHIVE_CHANGED_DURING_VALIDATION")
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
    active_contract = contract if contract is not None else load_hosted_recovery_contract()
    validate_hosted_recovery_contract(active_contract)

    expected_release_sha = _require_release_sha(
        expected_release_sha, "HOSTED_RECOVERY_EXPECTED_RELEASE_SHA_INVALID"
    )
    expected_migration_sha256 = _require_sha256(
        expected_migration_sha256, "HOSTED_RECOVERY_EXPECTED_MIGRATION_SHA256_INVALID"
    )
    expected_tenant_boundary_sha256 = _require_sha256(
        expected_tenant_boundary_sha256, "HOSTED_RECOVERY_EXPECTED_TENANT_BOUNDARY_SHA256_INVALID"
    )
    expected_schema_sha256 = _require_sha256(
        expected_schema_sha256, "HOSTED_RECOVERY_EXPECTED_SCHEMA_SHA256_INVALID"
    )
    required_forced_rls = _as_string_sequence(
        required_forced_rls_relations, "HOSTED_RECOVERY_REQUIRED_FORCED_RLS_INVALID"
    )
    if required_forced_rls != _EXPECTED_FORCED_RLS:
        raise HostedRecoveryContractError("HOSTED_RECOVERY_REQUIRED_FORCED_RLS_DRIFT")

    if set(manifest) != set(_EXPECTED_MANIFEST_FIELDS):
        raise HostedRecoveryContractError("HOSTED_RECOVERY_MANIFEST_FIELDS_INVALID")

    bundle = _as_mapping(active_contract["bundle"], "HOSTED_RECOVERY_BUNDLE_INVALID")
    integrity = _as_mapping(active_contract["integrity"], "HOSTED_RECOVERY_INTEGRITY_INVALID")

    if manifest["schema_version"] != bundle["manifest_schema_version"]:
        raise HostedRecoveryContractError("HOSTED_RECOVERY_MANIFEST_VERSION_INVALID")
    if manifest["backup_class"] != bundle["backup_class"]:
        raise HostedRecoveryContractError("HOSTED_RECOVERY_BACKUP_CLASS_INVALID")

    created_at = _require_created_at(
        manifest["created_at_utc"], "HOSTED_RECOVERY_CREATED_AT_INVALID"
    )

    archive_name = manifest["archive_name"]
    if not isinstance(archive_name, str):
        raise HostedRecoveryContractError("HOSTED_RECOVERY_ARCHIVE_NAME_INVALID")
    if archive_name.endswith(str(integrity["temporary_suffix"])):
        raise HostedRecoveryContractError("HOSTED_RECOVERY_PARTIAL_ARCHIVE_FORBIDDEN")
    if "/" in archive_name or "\\" in archive_name or ".." in archive_name:
        raise HostedRecoveryContractError("HOSTED_RECOVERY_ARCHIVE_PATH_INVALID")
    if not _ARCHIVE_NAME_RE.fullmatch(archive_name):
        raise HostedRecoveryContractError("HOSTED_RECOVERY_ARCHIVE_NAME_INVALID")
    timestamp_match = _ARCHIVE_TIMESTAMP_RE.fullmatch(archive_name)
    if timestamp_match is None:
        raise HostedRecoveryContractError("HOSTED_RECOVERY_ARCHIVE_NAME_INVALID")
    try:
        archive_created_at = datetime.strptime(
            timestamp_match.group(1), "%Y%m%dT%H%M%SZ"
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_ARCHIVE_TIMESTAMP_INVALID"
        ) from exc
    if archive_created_at != created_at:
        raise HostedRecoveryContractError("HOSTED_RECOVERY_ARCHIVE_TIMESTAMP_MISMATCH")

    _require_final_archive_path(archive_path)
    if archive_path.name != archive_name:
        raise HostedRecoveryContractError("HOSTED_RECOVERY_ARCHIVE_MANIFEST_NAME_MISMATCH")

    archive_size = manifest["archive_size_bytes"]
    if type(archive_size) is not int or archive_size < int(integrity["minimum_archive_bytes"]):
        raise HostedRecoveryContractError("HOSTED_RECOVERY_ARCHIVE_SIZE_INVALID")
    if archive_size > int(integrity["maximum_archive_bytes"]):
        raise HostedRecoveryContractError("HOSTED_RECOVERY_ARCHIVE_SIZE_EXCEEDED")
    try:
        path_size = archive_path.stat().st_size
    except OSError as exc:
        raise HostedRecoveryContractError("HOSTED_RECOVERY_ARCHIVE_READ_INVALID") from exc
    if archive_size != path_size:
        raise HostedRecoveryContractError("HOSTED_RECOVERY_ARCHIVE_SIZE_MISMATCH")

    actual_size, actual_hash = _archive_file_integrity(archive_path)
    if archive_size != actual_size:
        raise HostedRecoveryContractError("HOSTED_RECOVERY_ARCHIVE_CHANGED_DURING_VALIDATION")
    declared_hash = _require_sha256(
        manifest["archive_sha256"], "HOSTED_RECOVERY_ARCHIVE_SHA256_INVALID"
    )
    if not hmac.compare_digest(declared_hash, actual_hash):
        raise HostedRecoveryContractError("HOSTED_RECOVERY_ARCHIVE_SHA256_MISMATCH")

    if manifest["postgres_major"] != 18:
        raise HostedRecoveryContractError("HOSTED_RECOVERY_POSTGRES_MAJOR_INVALID")
    if manifest["archive_format"] != "CUSTOM":
        raise HostedRecoveryContractError("HOSTED_RECOVERY_ARCHIVE_FORMAT_INVALID")

    source_release_sha = _require_release_sha(
        manifest["source_release_sha"], "HOSTED_RECOVERY_RELEASE_SHA_INVALID"
    )
    if not hmac.compare_digest(source_release_sha, expected_release_sha):
        raise HostedRecoveryContractError("HOSTED_RECOVERY_SOURCE_RELEASE_MISMATCH")

    expected_digests = {
        "migration_state_sha256": expected_migration_sha256,
        "tenant_boundary_sha256": expected_tenant_boundary_sha256,
        "schema_state_sha256": expected_schema_sha256,
    }
    for field, expected_value in expected_digests.items():
        actual_value = _require_sha256(manifest[field], f"HOSTED_RECOVERY_{field.upper()}_INVALID")
        if not hmac.compare_digest(actual_value, expected_value):
            raise HostedRecoveryContractError(f"HOSTED_RECOVERY_{field.upper()}_MISMATCH")

    forced_rls = _as_string_sequence(
        manifest["forced_rls_relations"], "HOSTED_RECOVERY_FORCED_RLS_INVALID"
    )
    if forced_rls != required_forced_rls:
        raise HostedRecoveryContractError("HOSTED_RECOVERY_FORCE_RLS_MISMATCH")

    if manifest["encryption_state"] != bundle["encryption_state"]:
        raise HostedRecoveryContractError("HOSTED_RECOVERY_ENCRYPTION_STATE_INVALID")


def build_dump_command(
    archive_path: Path,
    source_database: str,
) -> tuple[Path, tuple[str, ...]]:
    if not archive_path.is_absolute():
        raise HostedRecoveryContractError("HOSTED_RECOVERY_ARCHIVE_PATH_NOT_ABSOLUTE")
    if not _ARCHIVE_NAME_RE.fullmatch(archive_path.name):
        raise HostedRecoveryContractError("HOSTED_RECOVERY_ARCHIVE_NAME_INVALID")
    if not _DATABASE_RE.fullmatch(source_database):
        raise HostedRecoveryContractError("HOSTED_RECOVERY_SOURCE_DATABASE_INVALID")

    partial_path = archive_path.with_name(f"{archive_path.name}.partial")
    command = (
        "pg_dump",
        *_EXPECTED_DUMP_FLAGS,
        "--file",
        str(partial_path),
        "--dbname",
        source_database,
    )
    return partial_path, command


def build_restore_commands(
    archive_path: Path,
    destination_database: str,
    *,
    manifest: Mapping[str, Any],
    expected_release_sha: str,
    expected_migration_sha256: str,
    expected_tenant_boundary_sha256: str,
    expected_schema_sha256: str,
    required_forced_rls_relations: Sequence[str],
    contract: Mapping[str, Any] | None = None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if not _DATABASE_RE.fullmatch(destination_database):
        raise HostedRecoveryContractError("HOSTED_RECOVERY_DESTINATION_DATABASE_INVALID")

    validate_recovery_manifest(
        manifest,
        archive_path,
        expected_release_sha=expected_release_sha,
        expected_migration_sha256=expected_migration_sha256,
        expected_tenant_boundary_sha256=expected_tenant_boundary_sha256,
        expected_schema_sha256=expected_schema_sha256,
        required_forced_rls_relations=required_forced_rls_relations,
        contract=contract,
    )

    preflight = ("pg_restore", "--list", str(archive_path))
    restore = (
        "pg_restore",
        *_EXPECTED_RESTORE_FLAGS,
        "--dbname",
        destination_database,
        str(archive_path),
    )
    return preflight, restore


def validate_restore_evidence(
    evidence: Mapping[str, Any],
    *,
    expected_release_sha: str,
    expected_migration_sha256: str,
    expected_tenant_boundary_sha256: str,
    expected_schema_sha256: str,
    required_forced_rls_relations: Sequence[str],
) -> None:
    expected_release_sha = _require_release_sha(
        expected_release_sha, "HOSTED_RECOVERY_EXPECTED_RELEASE_SHA_INVALID"
    )
    expected_migration_sha256 = _require_sha256(
        expected_migration_sha256, "HOSTED_RECOVERY_EXPECTED_MIGRATION_SHA256_INVALID"
    )
    expected_tenant_boundary_sha256 = _require_sha256(
        expected_tenant_boundary_sha256, "HOSTED_RECOVERY_EXPECTED_TENANT_BOUNDARY_SHA256_INVALID"
    )
    expected_schema_sha256 = _require_sha256(
        expected_schema_sha256, "HOSTED_RECOVERY_EXPECTED_SCHEMA_SHA256_INVALID"
    )
    required_forced_rls = _as_string_sequence(
        required_forced_rls_relations, "HOSTED_RECOVERY_REQUIRED_FORCED_RLS_INVALID"
    )
    if required_forced_rls != _EXPECTED_FORCED_RLS:
        raise HostedRecoveryContractError("HOSTED_RECOVERY_REQUIRED_FORCED_RLS_DRIFT")

    required_fields = {
        "restored_into_separate_database",
        "restore_list_preflight_passed",
        "restore_catalog_rechecked",
        "replacement_runtime_recovery_rehearsed",
        "accepted_release_sha",
        "migration_state_sha256",
        "tenant_boundary_sha256",
        "schema_state_sha256",
        "forced_rls_relations",
        "unscoped_access_denied",
        "cross_tenant_access_denied",
        "runtime_acl_reapplied",
        "rollback_release_available",
        "temporary_state_cleaned",
    }
    if set(evidence) != required_fields:
        raise HostedRecoveryContractError("HOSTED_RECOVERY_EVIDENCE_FIELDS_INVALID")

    expected_values = {
        "accepted_release_sha": expected_release_sha,
        "migration_state_sha256": expected_migration_sha256,
        "tenant_boundary_sha256": expected_tenant_boundary_sha256,
        "schema_state_sha256": expected_schema_sha256,
    }
    for field, expected_value in expected_values.items():
        if evidence[field] != expected_value:
            raise HostedRecoveryContractError(f"HOSTED_RECOVERY_{field.upper()}_MISMATCH")

    forced_rls = _as_string_sequence(
        evidence["forced_rls_relations"], "HOSTED_RECOVERY_EVIDENCE_FORCED_RLS_INVALID"
    )
    if forced_rls != required_forced_rls:
        raise HostedRecoveryContractError("HOSTED_RECOVERY_EVIDENCE_FORCE_RLS_MISMATCH")

    required_true_fields = (
        "restored_into_separate_database",
        "restore_list_preflight_passed",
        "restore_catalog_rechecked",
        "replacement_runtime_recovery_rehearsed",
        "unscoped_access_denied",
        "cross_tenant_access_denied",
        "runtime_acl_reapplied",
        "rollback_release_available",
        "temporary_state_cleaned",
    )
    for field in required_true_fields:
        if evidence[field] is not True:
            raise HostedRecoveryContractError(f"HOSTED_RECOVERY_{field.upper()}_REQUIRED")
