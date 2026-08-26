from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
import re
from typing import Any

from omni_cio.persistence._hosted_recovery_contract_v1 import (
    HostedRecoveryContractError,
)
from omni_cio.persistence._hosted_recovery_restore_v1 import build_restore_commands


_DATABASE_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
_PHASE5_AUTH_INVALIDATION_SQL = (
    "BEGIN; "
    "DELETE FROM omni_cio_v10.provider_auth_transactions; "
    "DELETE FROM omni_cio_v10.web_sessions; "
    "COMMIT;"
)
_PHASE5_AUTH_VERIFY_SQL = (
    "SELECT "
    "(SELECT count(*) FROM omni_cio_v10.provider_auth_transactions), "
    "(SELECT count(*) FROM omni_cio_v10.web_sessions);"
)


def build_phase5_post_restore_auth_commands(
    destination_database: str,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Invalidate restored pre-auth/session authority before runtime exposure.

    Point-in-time backup restore must never resurrect a consumed OAuth/OIDC
    transaction or a session that had already been revoked after the snapshot.
    Account, tenant and durable product state remain intact; users simply
    authenticate again after recovery.
    """

    if not _DATABASE_RE.fullmatch(destination_database):
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_DESTINATION_DATABASE_INVALID"
        )
    cleanup = (
        "psql",
        "--dbname",
        destination_database,
        "--set",
        "ON_ERROR_STOP=1",
        "--command",
        _PHASE5_AUTH_INVALIDATION_SQL,
    )
    verify = (
        "psql",
        "--dbname",
        destination_database,
        "--set",
        "ON_ERROR_STOP=1",
        "--tuples-only",
        "--no-align",
        "--command",
        _PHASE5_AUTH_VERIFY_SQL,
    )
    return cleanup, verify


def build_phase5_restore_commands(
    archive_path: Path,
    destination_database: str,
    *,
    source_database: str,
    manifest: Mapping[str, Any],
    expected_release_sha: str,
    expected_migration_sha256: str,
    expected_tenant_boundary_sha256: str,
    expected_schema_sha256: str,
    required_forced_rls_relations: Sequence[str],
    contract: Mapping[str, Any] | None = None,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Phase-3 validated restore plus mandatory Phase-5 auth invalidation."""

    preflight, restore = build_restore_commands(
        archive_path,
        destination_database,
        source_database=source_database,
        manifest=manifest,
        expected_release_sha=expected_release_sha,
        expected_migration_sha256=expected_migration_sha256,
        expected_tenant_boundary_sha256=expected_tenant_boundary_sha256,
        expected_schema_sha256=expected_schema_sha256,
        required_forced_rls_relations=required_forced_rls_relations,
        contract=contract,
    )
    cleanup, verify = build_phase5_post_restore_auth_commands(destination_database)
    return preflight, restore, cleanup, verify


def validate_phase5_post_restore_auth_evidence(
    evidence: Mapping[str, object],
) -> None:
    expected_fields = {
        "web_sessions_remaining",
        "provider_auth_transactions_remaining",
        "runtime_not_exposed_before_invalidation",
    }
    if set(evidence) != expected_fields:
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_PHASE5_AUTH_EVIDENCE_FIELDS_INVALID"
        )
    for field in (
        "web_sessions_remaining",
        "provider_auth_transactions_remaining",
    ):
        value = evidence[field]
        if isinstance(value, bool) or not isinstance(value, int) or value != 0:
            raise HostedRecoveryContractError(
                f"HOSTED_RECOVERY_PHASE5_{field.upper()}_ZERO_REQUIRED"
            )
    if evidence["runtime_not_exposed_before_invalidation"] is not True:
        raise HostedRecoveryContractError(
            "HOSTED_RECOVERY_PHASE5_RUNTIME_EXPOSURE_BLOCK_REQUIRED"
        )
