from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = (
    ROOT
    / "infrastructure"
    / "postgres"
    / "hosted-recovery-contract.json"
)

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
    "provider": "PROVIDER_NEUTRAL_POSTGRESQL_18",
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
_EXPECTED_RESTORE_FLAGS = (
    "--exit-on-error",
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
_ARCHIVE_NAME_PATTERN = (
    r"wp22a-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{12}\.dump"
)
_ARCHIVE_NAME_RE = re.compile(_ARCHIVE_NAME_PATTERN)
_ARCHIVE_METADATA_RE = re.compile(
    r"^wp22a-([0-9]{8}T[0-9]{6}Z)-([a-f0-9]{12})\.dump$"
)
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
_RELEASE_SHA_RE = re.compile(r"^[a-f0-9]{40}$")
_CREATED_AT_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T"
    r"[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"
)
_DATABASE_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


class HostedRecoveryContractError(RuntimeError):
    """Fail-closed hosted recovery contract violation."""


def _as_mapping(value: object, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise HostedRecoveryContractError(code)
    return value


def _as_string_sequence(
    value: object,
    code: str,
) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise HostedRecoveryContractError(code)
    if any(not isinstance(item, str) for item in value):
        raise HostedRecoveryContractError(code)
    normalized = tuple(value)
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


def load_hosted_recovery_contract(
    path: Path = CONTRACT_PATH,
) -> dict[str, Any]:
    if path.resolve(strict=False) != CONTRACT_PATH.resolve(strict=False):
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_CONTRACT_PATH_INVALID"
        )
    payload = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_CONTRACT_NOT_OBJECT"
        )
    return payload


def validate_hosted_recovery_contract(
    payload: Mapping[str, Any],
) -> None:
    if set(payload) != set(_EXPECTED_CONTRACT_FIELDS):
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_CONTRACT_FIELDS_INVALID"
        )
    if (
        payload.get("schema_version")
        != "v10.hosted-recovery.v2"
    ):
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_CONTRACT_VERSION_INVALID"
        )

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
            "required_restore_flags": list(_EXPECTED_RESTORE_FLAGS),
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
            "minimum_archive_bytes": 1,
            "maximum_archive_bytes": 4_294_967_296,
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
            "archive_name_pattern": _ARCHIVE_NAME_PATTERN,
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
