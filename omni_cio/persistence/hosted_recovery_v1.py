from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import hmac
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = (
    ROOT
    / "infrastructure"
    / "cloudru"
    / "wp22a"
    / "hosted-recovery-contract.json"
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
_EXPECTED_DUMP_FLAGS = (
    "--format=custom",
    "--no-owner",
    "--no-privileges",
)
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


def _require_exact_mapping(
    actual: Mapping[str, Any],
    expected: Mapping[str, object],
    code: str,
) -> None:
    if set(actual) != set(expected):
        raise HostedRecoveryContractError(code)
    for key, expected_value in expected.items():
        actual_value = actual[key]
        if type(actual_value) is not type(expected_value):
            raise HostedRecoveryContractError(code)
        if actual_value != expected_value:
            raise HostedRecoveryContractError(code)


def load_hosted_recovery_contract(
    path: Path = CONTRACT_PATH,
) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise HostedRecoveryContractError("HOSTED_RECOVERY_CONTRACT_NOT_OBJECT")
    return payload


def validate_hosted_recovery_contract(payload: Mapping[str, Any]) -> None:
    if payload.get("schema_version") != "v10.wp22a.phase3.hosted-recovery.v1":
        raise HostedRecoveryContractError("HOSTED_RECOVERY_CONTRACT_VERSION_INVALID")

    authority = _as_mapping(
        payload.get("authority"),
        "HOSTED_RECOVERY_AUTHORITY_INVALID",
    )
    _require_exact_mapping(
        authority,
        _EXPECTED_AUTHORITY,
        "HOSTED_RECOVERY_AUTHORITY_DRIFT",
    )

    postgres = _as_mapping(
        payload.get("postgres"),
        "HOSTED_RECOVERY_POSTGRES_INVALID",
    )
    _require_exact_mapping(
        postgres,
        {
            "major": 18,
            "backup_tool": "pg_dump",
            "restore_tool": "pg_restore",
            "archive_format": "CUSTOM",
            "required_dump_flags": list(_EXPECTED_DUMP_FLAGS),
            "restore_list_preflight_required": True,
            "restore_into_separate_database_required": True,
            "restore_exit_on_error_required": True,
            "runtime_acl_reapply_required": True,
            "forced_rls_reverify_required": True,
        },
        "HOSTED_RECOVERY_POSTGRES_DRIFT",
    )

    integrity = _as_mapping(
        payload.get("integrity"),
        "HOSTED_RECOVERY_INTEGRITY_INVALID",
    )
    _require_exact_mapping(
        integrity,
        {
            "algorithm": "SHA256",
            "hash_before_restore_required": True,
            "archive_size_bound_required": True,
            "atomic_promotion_required": True,
            "temporary_suffix": ".partial",
            "corrupt_backup_rejection_required": True,
            "maximum_archive_bytes": 4294967296,
        },
        "HOSTED_RECOVERY_INTEGRITY_DRIFT",
    )

    bundle = _as_mapping(
        payload.get("bundle"),
        "HOSTED_RECOVERY_BUNDLE_INVALID",
    )
    _require_exact_mapping(
        bundle,
        {
            "backup_class": "POSTGRES_LOGICAL_PRIVATE_STATE",
            "archive_name_pattern": (
                r"wp22a-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{12}\.dump"
            ),
            "manifest_schema_version": (
                "v10.wp22a.phase3.hosted-recovery-manifest.v1"
            ),
            "allowed_manifest_fields": list(_EXPECTED_MANIFEST_FIELDS),
            "encryption_state": "EXTERNAL_ENVELOPE_REQUIRED",
        },
        "HOSTED_RECOVERY_BUNDLE_DRIFT",
    )

    tenant_boundary = _as_mapping(
        payload.get("tenant_boundary"),
        "HOSTED_RECOVERY_TENANT_BOUNDARY_INVALID",
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

    restore = _as_mapping(
        payload.get("restore"),
        "HOSTED_RECOVERY_RESTORE_INVALID",
    )
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

    off_runtime = _as_mapping(
        payload.get("off_runtime"),
        "HOSTED_RECOVERY_OFF_RUNTIME_INVALID",
    )
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


def _require_sha256(value: object, code: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise HostedRecoveryContractError(code)
    return value


def validate_recovery_manifest(
    manifest: Mapping[str, Any],
    archive_bytes: bytes,
    contract: Mapping[str, Any] | None = None,
) -> None:
    active_contract = (
        contract if contract is not None else load_hosted_recovery_contract()
    )
    validate_hosted_recovery_contract(active_contract)

    if tuple(manifest.keys()) != _EXPECTED_MANIFEST_FIELDS:
        raise HostedRecoveryContractError("HOSTED_RECOVERY_MANIFEST_FIELDS_INVALID")

    bundle = _as_mapping(
        active_contract["bundle"],
        "HOSTED_RECOVERY_BUNDLE_INVALID",
    )
    integrity = _as_mapping(
        active_contract["integrity"],
        "HOSTED_RECOVERY_INTEGRITY_INVALID",
    )

    if manifest["schema_version"] != bundle["manifest_schema_version"]:
        raise HostedRecoveryContractError("HOSTED_RECOVERY_MANIFEST_VERSION_INVALID")
    if manifest["backup_class"] != bundle["backup_class"]:
        raise HostedRecoveryContractError("HOSTED_RECOVERY_BACKUP_CLASS_INVALID")

    created_at = manifest["created_at_utc"]
    if not isinstance(created_at, str) or not _CREATED_AT_RE.fullmatch(created_at):
        raise HostedRecoveryContractError("HOSTED_RECOVERY_CREATED_AT_INVALID")

    archive_name = manifest["archive_name"]
    if not isinstance(archive_name, str):
        raise HostedRecoveryContractError("HOSTED_RECOVERY_ARCHIVE_NAME_INVALID")
    archive_pattern = str(bundle["archive_name_pattern"])
    if not re.fullmatch(archive_pattern, archive_name):
        raise HostedRecoveryContractError("HOSTED_RECOVERY_ARCHIVE_NAME_INVALID")
    if archive_name.endswith(str(integrity["temporary_suffix"])):
        raise HostedRecoveryContractError("HOSTED_RECOVERY_PARTIAL_ARCHIVE_FORBIDDEN")
    if "/" in archive_name or "\\" in archive_name or ".." in archive_name:
        raise HostedRecoveryContractError("HOSTED_RECOVERY_ARCHIVE_PATH_INVALID")

    declared_hash = _require_sha256(
        manifest["archive_sha256"],
        "HOSTED_RECOVERY_ARCHIVE_SHA256_INVALID",
    )
    actual_hash = archive_sha256(archive_bytes)
    if not hmac.compare_digest(declared_hash, actual_hash):
        raise HostedRecoveryContractError("HOSTED_RECOVERY_ARCHIVE_HASH_MISMATCH")

    archive_size = manifest["archive_size_bytes"]
    if type(archive_size) is not int or archive_size < 0:
        raise HostedRecoveryContractError("HOSTED_RECOVERY_ARCHIVE_SIZE_INVALID")
    if archive_size != len(archive_bytes):
        raise HostedRecoveryContractError("HOSTED_RECOVERY_ARCHIVE_SIZE_MISMATCH")
    maximum_archive_bytes = int(integrity["maximum_archive_bytes"])
    if archive_size > maximum_archive_bytes:
        raise HostedRecoveryContractError("HOSTED_RECOVERY_ARCHIVE_SIZE_EXCEEDED")

    if manifest["postgres_major"] != 18:
        raise HostedRecoveryContractError("HOSTED_RECOVERY_POSTGRES_MAJOR_INVALID")
    if manifest["archive_format"] != "CUSTOM":
        raise HostedRecoveryContractError("HOSTED_RECOVERY_ARCHIVE_FORMAT_INVALID")

    source_release_sha = manifest["source_release_sha"]
    if not isinstance(source_release_sha, str) or not _RELEASE_SHA_RE.fullmatch(
        source_release_sha
    ):
        raise HostedRecoveryContractError("HOSTED_RECOVERY_RELEASE_SHA_INVALID")

    for field in (
        "migration_state_sha256",
        "tenant_boundary_sha256",
        "schema_state_sha256",
    ):
        _require_sha256(
            manifest[field],
            f"HOSTED_RECOVERY_{field.upper()}_INVALID",
        )

    forced_rls = _as_string_sequence(
        manifest["forced_rls_relations"],
        "HOSTED_RECOVERY_FORCED_RLS_INVALID",
    )
    if forced_rls != _EXPECTED_FORCED_RLS:
        raise HostedRecoveryContractError("HOSTED_RECOVERY_FORCED_RLS_DRIFT")

    if manifest["encryption_state"] != bundle["encryption_state"]:
        raise HostedRecoveryContractError("HOSTED_RECOVERY_ENCRYPTION_STATE_INVALID")


def build_restore_commands(
    archive_path: Path,
    destination_database: str,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if not archive_path.is_absolute():
        raise HostedRecoveryContractError("HOSTED_RECOVERY_ARCHIVE_PATH_NOT_ABSOLUTE")
    if archive_path.name.endswith(".partial"):
        raise HostedRecoveryContractError("HOSTED_RECOVERY_PARTIAL_ARCHIVE_FORBIDDEN")
    if not _DATABASE_RE.fullmatch(destination_database):
        raise HostedRecoveryContractError("HOSTED_RECOVERY_DESTINATION_DB_INVALID")

    preflight = ("pg_restore", "--list", str(archive_path))
    restore = (
        "pg_restore",
        "--exit-on-error",
        "--no-owner",
        "--no-privileges",
        "--dbname",
        destination_database,
        str(archive_path),
    )
    return preflight, restore


def validate_restore_evidence(
    evidence: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> None:
    required_fields = {
        "restored_into_separate_database",
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
    if evidence["restored_into_separate_database"] is not True:
        raise HostedRecoveryContractError("HOSTED_RECOVERY_SEPARATE_DB_REQUIRED")

    comparisons = {
        "accepted_release_sha": "source_release_sha",
        "migration_state_sha256": "migration_state_sha256",
        "tenant_boundary_sha256": "tenant_boundary_sha256",
        "schema_state_sha256": "schema_state_sha256",
    }
    for evidence_field, manifest_field in comparisons.items():
        if evidence[evidence_field] != manifest[manifest_field]:
            raise HostedRecoveryContractError(
                f"HOSTED_RECOVERY_{evidence_field.upper()}_MISMATCH"
            )

    forced_rls = _as_string_sequence(
        evidence["forced_rls_relations"],
        "HOSTED_RECOVERY_EVIDENCE_FORCED_RLS_INVALID",
    )
    if forced_rls != _EXPECTED_FORCED_RLS:
        raise HostedRecoveryContractError("HOSTED_RECOVERY_EVIDENCE_FORCED_RLS_DRIFT")

    for field in (
        "unscoped_access_denied",
        "cross_tenant_access_denied",
        "runtime_acl_reapplied",
        "rollback_release_available",
        "temporary_state_cleaned",
    ):
        if evidence[field] is not True:
            raise HostedRecoveryContractError(
                f"HOSTED_RECOVERY_{field.upper()}_REQUIRED"
            )
