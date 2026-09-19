from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

if __package__:
    from .v10_jsonc import loads_jsonc
else:
    from v10_jsonc import loads_jsonc


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    ROOT
    / "docs/architecture/V10_RU_POSTGRES_DATA_RESIDENCY_MIGRATION_CONTRACT.json"
)
AMENDMENT = (
    ROOT
    / "docs/master-plan/OMNI_CIO_V10_RU_POSTGRES_DATA_RESIDENCY_MIGRATION_AMENDMENT.md"
)
INDEX = ROOT / "docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md"
PLATFORM_CONTRACT = (
    ROOT / "docs/architecture/V10_CLOUDFLARE_PLATFORM_AUTHORITY_CONTRACT.json"
)
LEGAL_GATES = ROOT / "docs/legal/V10_RU_COMMERCIAL_LEGAL_GATES.md"
WRANGLER = ROOT / "wrangler.jsonc"
RUNTIME_SQL = ROOT / "infrastructure/cloudru/wp22a/hosted-postgres-runtime.sql"
MIGRATIONS = ROOT / "omni_cio/persistence/migrations"
NEON_RUNTIME = ROOT / "scripts/provision_v10_cloudflare_neon_runtime.py"

EXPECTED_SEQUENCE = [
    "RU-PG-A_AUTHORITY_SOURCE_COMPATIBILITY",
    "RU-PG-B_PROVIDER_SYNTHETIC_POSTGRES18_PARITY",
    "RU-PG-C_CLOUDFLARE_TLS_RECOVERY_PARITY",
    "RU-PG-D_PRODUCTION_DATABASE_CUTOVER",
    "RU-PG-E_NEON_PRODUCTION_AUTHORITY_RETIREMENT",
]


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError("RU_POSTGRES_SOURCE_UNREADABLE") from exc


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(_read(path))
    except json.JSONDecodeError as exc:
        raise RuntimeError("RU_POSTGRES_CONTRACT_INVALID") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("RU_POSTGRES_CONTRACT_INVALID")
    return payload


def _mapping(value: object, code: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(code)
    return value


def _require(actual: object, expected: object, code: str) -> None:
    if actual != expected:
        raise RuntimeError(code)


def _require_markers(
    source: str,
    markers: tuple[str, ...],
    code: str,
) -> None:
    for marker in markers:
        if marker not in source:
            raise RuntimeError(code)


def _validate_identity(payload: dict[str, Any]) -> None:
    _require(
        payload.get("schema"),
        "omni-cio.v10.ru-postgres-data-residency-migration.v1",
        "RU_POSTGRES_SCHEMA_INVALID",
    )
    _require(
        payload.get("amendment_number"),
        17,
        "RU_POSTGRES_AMENDMENT_INVALID",
    )
    _require(payload.get("owning_issue"), 559, "RU_POSTGRES_ISSUE_INVALID")
    _require(
        payload.get("progress_effect_percent"),
        0,
        "RU_POSTGRES_PROGRESS_INVALID",
    )


def _validate_candidate(payload: dict[str, Any]) -> None:
    candidate = _mapping(
        payload.get("candidate"),
        "RU_POSTGRES_CANDIDATE_INVALID",
    )
    expected = {
        "provider": "Timeweb Cloud",
        "service": "Managed PostgreSQL",
        "postgres_major": 18,
        "preferred_region": "Moscow",
        "preferred_terraform_location": "ru-3",
        "provider_mutation_authorized_by_amendment": False,
        "purchase_authorized_by_amendment": False,
        "external_facts_revalidated_on": "2026-09-19",
        "external_facts_must_be_revalidated_before_purchase": True,
        "minimum_1cpu_1gb_8gb_tier_accepted": False,
        "minimum_tier_blocker": (
            "ADDITIONAL_DATABASE_USERS_DOCUMENTED_UNAVAILABLE"
        ),
    }
    _require(candidate, expected, "RU_POSTGRES_CANDIDATE_INVALID")


def _validate_parity(payload: dict[str, Any]) -> None:
    parity = _mapping(
        payload.get("postgresql_parity"),
        "RU_POSTGRES_PARITY_INVALID",
    )
    required_true = (
        "separate_bootstrap_and_runtime_identities_required",
        "runtime_login_required",
        "existing_migrations_reused_by_default",
        "force_rls_required",
        "cross_tenant_negative_required",
        "alter_default_privileges_semantics_required",
    )
    required_false = (
        "runtime_superuser_allowed",
        "runtime_createdb_allowed",
        "runtime_createrole_allowed",
        "runtime_replication_allowed",
        "runtime_bypassrls_allowed",
        "runtime_role_membership_widening_allowed",
        "runtime_database_owner_allowed",
        "runtime_schema_owner_allowed",
        "runtime_object_owner_allowed",
        "provider_specific_tokens_in_application_migrations_allowed",
    )
    for key in required_true:
        _require(parity.get(key), True, "RU_POSTGRES_PARITY_INVALID")
    for key in required_false:
        _require(parity.get(key), False, "RU_POSTGRES_PARITY_INVALID")


def _validate_network(payload: dict[str, Any]) -> None:
    network = _mapping(
        payload.get("network"),
        "RU_POSTGRES_NETWORK_INVALID",
    )
    required_true = (
        "cloudflare_container_direct_postgres_protocol_target",
        "tls_required",
        "certificate_verification_required",
        "hostname_verification_required_when_provider_certificate_model_supports_it",
        "public_ip_requires_owning_security_acceptance",
    )
    required_false = (
        "plaintext_database_credential_transport_allowed",
        "sslmode_disable_allowed",
        "runtime_dsn_in_repository_allowed",
        "hyperdrive_required",
    )
    for key in required_true:
        _require(network.get(key), True, "RU_POSTGRES_NETWORK_INVALID")
    for key in required_false:
        _require(network.get(key), False, "RU_POSTGRES_NETWORK_INVALID")


def _validate_recovery(payload: dict[str, Any]) -> None:
    recovery = _mapping(
        payload.get("recovery"),
        "RU_POSTGRES_RECOVERY_INVALID",
    )
    _require(
        recovery.get("provider_physical_backups_are_additive_only"),
        True,
        "RU_POSTGRES_RECOVERY_INVALID",
    )
    _require(
        recovery.get("logical_backup_tool"),
        "pg_dump",
        "RU_POSTGRES_RECOVERY_INVALID",
    )
    _require(
        recovery.get("logical_restore_tool"),
        "pg_restore",
        "RU_POSTGRES_RECOVERY_INVALID",
    )
    _require(
        recovery.get("archive_format"),
        "CUSTOM",
        "RU_POSTGRES_RECOVERY_INVALID",
    )
    for key in (
        "restore_to_separate_database_required",
        "integrity_validation_required",
        "migration_schema_tenant_revalidation_required",
        "cross_tenant_restore_negative_required",
    ):
        _require(recovery.get(key), True, "RU_POSTGRES_RECOVERY_INVALID")


def _validate_data_boundary(payload: dict[str, Any]) -> None:
    data = _mapping(
        payload.get("data_boundary"),
        "RU_POSTGRES_DATA_BOUNDARY_INVALID",
    )
    for key in (
        "synthetic_data_only_before_production_cutover",
        "current_neon_authority_retained_until_equivalent_cutover",
        "neon_historical_evidence_preserved",
        "neon_dev_synthetic_only_after_retirement",
        "qualified_legal_data_flow_review_required_before_public_activation",
    ):
        _require(data.get(key), True, "RU_POSTGRES_DATA_BOUNDARY_INVALID")
    _require(
        data.get(
            "real_ru_user_personal_data_on_candidate_before_cutover_allowed"
        ),
        False,
        "RU_POSTGRES_DATA_BOUNDARY_INVALID",
    )


def _validate_sequence_and_invariants(payload: dict[str, Any]) -> None:
    _require(
        payload.get("execution_sequence"),
        EXPECTED_SEQUENCE,
        "RU_POSTGRES_SEQUENCE_INVALID",
    )
    invariants = _mapping(
        payload.get("protected_invariants"),
        "RU_POSTGRES_INVARIANTS_INVALID",
    )
    expected = {
        "PUBLIC_MULTI_USER_ENABLED": False,
        "OMNI_V10_TELEGRAM_LOGIN_ENABLED": False,
        "OMNI_V10_VK_ID_LOGIN_ENABLED": False,
        "broker_write": False,
        "trading_methods": False,
        "REAL_TRADING_ENABLED": False,
        "protected_v9_entrypoint": "app:app",
        "wp23_unlocked": False,
        "web_visual_started_by_this_amendment": False,
    }
    _require(invariants, expected, "RU_POSTGRES_INVARIANTS_INVALID")


def _validate_contract(payload: dict[str, Any]) -> None:
    _validate_identity(payload)
    _validate_candidate(payload)
    _validate_parity(payload)
    _validate_network(payload)
    _validate_recovery(payload)
    _validate_data_boundary(payload)
    _validate_sequence_and_invariants(payload)


def _validate_migrations(root: Path) -> None:
    migrations = root / MIGRATIONS.relative_to(ROOT)
    paths = sorted(migrations.glob("*.sql"))
    if not paths:
        raise RuntimeError("RU_POSTGRES_MIGRATIONS_MISSING")
    forbidden = ("neon", "timeweb", "cloudflare", ".neon.tech")
    for path in paths:
        source = _read(path).lower()
        if any(token in source for token in forbidden):
            raise RuntimeError("RU_POSTGRES_MIGRATION_PROVIDER_COUPLING")
        if "create extension" in source:
            raise RuntimeError(
                "RU_POSTGRES_MIGRATION_EXTENSION_DEPENDENCY_UNPROVEN"
            )


def _validate_runtime_sql(root: Path) -> None:
    source = _read(root / RUNTIME_SQL.relative_to(ROOT))
    _require_markers(
        source,
        (
            "runtime_user.rolsuper",
            "runtime_user.rolcreatedb",
            "runtime_user.rolcreaterole",
            "runtime_user.rolreplication",
            "runtime_user.rolbypassrls",
            "HOSTED_API_USER_ROLE_MEMBERSHIP_PRESENT",
            "HOSTED_API_DATABASE_OWNERSHIP_FORBIDDEN",
            "HOSTED_API_SCHEMA_OWNERSHIP_FORBIDDEN",
            "HOSTED_API_OBJECT_OWNERSHIP_FORBIDDEN",
            "FORCE ROW LEVEL SECURITY",
        ),
        "RU_POSTGRES_RUNTIME_BOUNDARY_DRIFT",
    )


def _validate_current_authority(root: Path) -> None:
    platform = _load_json(root / PLATFORM_CONTRACT.relative_to(ROOT))
    database = _mapping(
        platform.get("database"),
        "RU_POSTGRES_PLATFORM_DATABASE_INVALID",
    )
    _require(
        database.get("neon_postgresql_authority_preserved"),
        True,
        "RU_POSTGRES_PREMATURE_NEON_RETIREMENT",
    )
    _require(
        database.get("accepted_postgresql_major"),
        18,
        "RU_POSTGRES_MAJOR_DRIFT",
    )

    neon_runtime = _read(root / NEON_RUNTIME.relative_to(ROOT))
    _require_markers(
        neon_runtime,
        (
            "NEON_FRANKFURT_REGION_REQUIRED",
            "CLOUDFLARE_NEON_POSTGRES18=VERIFIED",
        ),
        "RU_POSTGRES_PREMATURE_NEON_RUNTIME_REMOVAL",
    )

    legal = _read(root / LEGAL_GATES.relative_to(ROOT))
    _require_markers(
        legal,
        (
            "PERSONAL_DATA_FLOW_AND_LOCALIZATION_REVIEW_COMPLETE",
            "localization requirements for Russian citizens",
        ),
        "RU_POSTGRES_LEGAL_GATE_DRIFT",
    )


def _validate_fail_closed_flags(root: Path) -> None:
    try:
        wrangler = loads_jsonc(_read(root / WRANGLER.relative_to(ROOT)))
    except (ValueError, TypeError) as exc:
        raise RuntimeError("RU_POSTGRES_WRANGLER_INVALID") from exc
    if not isinstance(wrangler, dict):
        raise RuntimeError("RU_POSTGRES_WRANGLER_INVALID")
    expected = {
        "PUBLIC_MULTI_USER_ENABLED": "false",
        "OMNI_V10_TELEGRAM_LOGIN_ENABLED": "false",
        "OMNI_V10_VK_ID_LOGIN_ENABLED": "false",
    }
    production = _mapping(
        wrangler.get("vars"),
        "RU_POSTGRES_PRODUCTION_FLAGS_INVALID",
    )
    environments = _mapping(
        wrangler.get("env"),
        "RU_POSTGRES_STAGING_FLAGS_INVALID",
    )
    staging = _mapping(
        environments.get("staging"),
        "RU_POSTGRES_STAGING_FLAGS_INVALID",
    )
    staging_vars = _mapping(
        staging.get("vars"),
        "RU_POSTGRES_STAGING_FLAGS_INVALID",
    )
    for key, value in expected.items():
        _require(
            production.get(key),
            value,
            "RU_POSTGRES_PRODUCTION_FLAGS_INVALID",
        )
        _require(
            staging_vars.get(key),
            value,
            "RU_POSTGRES_STAGING_FLAGS_INVALID",
        )


def _validate_docs(root: Path) -> None:
    amendment = _read(root / AMENDMENT.relative_to(ROOT))
    index = _read(root / INDEX.relative_to(ROOT))
    _require_markers(
        amendment,
        (
            "Russian PostgreSQL Data-Residency Migration Authority / Amendment 17",
            "RU-PG-A",
            "RU-PG-E",
            "Timeweb Cloud Managed PostgreSQL 18",
            "minimum 1 CPU / 1 GB RAM / 8 GB NVMe tariff",
            "Only then may RU-PG-B provider bootstrap begin.",
        ),
        "RU_POSTGRES_AMENDMENT_DRIFT",
    )
    _require_markers(
        index,
        (
            "### 17. Russian PostgreSQL Data-Residency Migration Authority",
            "OMNI_CIO_V10_RU_POSTGRES_DATA_RESIDENCY_MIGRATION_AMENDMENT.md",
            "V10_RU_POSTGRES_DATA_RESIDENCY_MIGRATION_CONTRACT.json",
        ),
        "RU_POSTGRES_INDEX_DRIFT",
    )


def validate(root: Path = ROOT) -> None:
    payload = _load_json(root / CONTRACT.relative_to(ROOT))
    _validate_contract(payload)
    _validate_migrations(root)
    _validate_runtime_sql(root)
    _validate_current_authority(root)
    _validate_fail_closed_flags(root)
    _validate_docs(root)


def main() -> int:
    try:
        validate()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(
        "V10 RU PostgreSQL data-residency migration authority check passed; "
        "RU-PG-B remains provider-gated."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
