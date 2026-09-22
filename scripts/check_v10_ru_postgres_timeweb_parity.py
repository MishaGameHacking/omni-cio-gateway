from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    ROOT / "docs/architecture/V10_RU_POSTGRES_TIMEWEB_SYNTHETIC_PARITY_CONTRACT.json"
)
PROOF = ROOT / "scripts/prove_v10_ru_postgres_timeweb_parity.py"
POSTGRES_RUNTIME = ROOT / "scripts/postgres_runtime_primitives.py"
RUNBOOK = ROOT / "docs/operations/V10_RU_POSTGRES_TIMEWEB_SYNTHETIC_PARITY_RUNBOOK.md"
STATUS = ROOT / "knowledge/17_V10_CURRENT_PROGRAM_STATUS.md"
PROVIDER_RUNTIME = ROOT / "scripts/provider_runtime_primitives.py"

_RETIRED_PROVIDER_RUNTIME_MARKERS = (
    "provision_v10_cloudflare_neon_runtime",
    "provision_v10_render_neon_preview",
    "NEON_API_KEY",
    "NEON_DATABASE_URL",
    "RENDER_API_KEY",
    "RENDER_EXTERNAL_URL",
    "CLOUDFLARE_API_TOKEN",
    "CLOUDFLARE_ACCOUNT_ID",
    "wrangler.jsonc",
)


def _contains_retired_provider_runtime_coupling(source: str) -> bool:
    return any(marker in source for marker in _RETIRED_PROVIDER_RUNTIME_MARKERS)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError("RU_PG_B_SOURCE_UNREADABLE") from exc


def _load_contract() -> dict[str, Any]:
    try:
        payload = json.loads(_read(CONTRACT))
    except json.JSONDecodeError as exc:
        raise RuntimeError("RU_PG_B_CONTRACT_INVALID") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("RU_PG_B_CONTRACT_INVALID")
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


def _validate_contract(payload: dict[str, Any]) -> None:
    _require(
        payload.get("schema"),
        "omni-cio.v10.ru-postgres-timeweb-synthetic-parity.v1",
        "RU_PG_B_SCHEMA_INVALID",
    )
    _require(
        payload.get("stage"),
        "RU-PG-B_PROVIDER_SYNTHETIC_POSTGRES18_PARITY",
        "RU_PG_B_STAGE_INVALID",
    )
    _require(
        payload.get("status"),
        "SOURCE_READY_PROVIDER_EVIDENCE_PENDING",
        "RU_PG_B_STATUS_INVALID",
    )

    provider = _mapping(payload.get("provider"), "RU_PG_B_PROVIDER_INVALID")
    _require(provider.get("name"), "Timeweb Cloud", "RU_PG_B_PROVIDER_INVALID")
    _require(provider.get("postgres_major"), 18, "RU_PG_B_PROVIDER_INVALID")
    _require(
        provider.get("required_terraform_location"),
        "ru-3",
        "RU_PG_B_PROVIDER_INVALID",
    )
    _require(
        provider.get("provider_purchase_authorized_by_source_change"),
        False,
        "RU_PG_B_COST_AUTHORITY_INVALID",
    )

    beta = _mapping(
        payload.get("beta_configuration"),
        "RU_PG_B_BETA_CONFIGURATION_INVALID",
    )
    expected_beta = {
        "owner_selected_on": "2026-09-19",
        "provider": "Timeweb Cloud",
        "service": "Managed PostgreSQL",
        "postgres_major": 18,
        "region": "Moscow",
        "availability_zone": "MSK-1",
        "terraform_location": "ru-3",
        "cpu": 1,
        "ram_gb": 2,
        "nvme_gb": 20,
        "base_monthly_price_rub": 790,
        "owner_base_cost_approval_recorded": True,
        "public_ipv4_addon_included_in_base_price": False,
        "public_ipv4_addon_authorized": True,
        "public_ipv4_monthly_price_rub": 200,
        "backup_storage_addon_included_in_base_price": False,
        "backup_storage_addon_authorized": False,
        "scale_up_only_after_capacity_evidence": True,
        "scale_down_supported_by_provider": False,
    }
    _require(
        beta,
        expected_beta,
        "RU_PG_B_BETA_CONFIGURATION_INVALID",
    )

    runtime = _mapping(
        payload.get("proof_runtime"),
        "RU_PG_B_RUNTIME_INVALID",
    )
    _require(
        runtime.get("sslmode_required"),
        "verify-full",
        "RU_PG_B_TLS_POLICY_INVALID",
    )
    _require(
        runtime.get("sslrootcert_required"),
        True,
        "RU_PG_B_TLS_POLICY_INVALID",
    )
    _require(
        runtime.get("provider_location_env_is_expectation_only"),
        True,
        "RU_PG_B_LOCATION_EVIDENCE_INVALID",
    )

    evidence = _mapping(payload.get("evidence"), "RU_PG_B_EVIDENCE_INVALID")
    _require(evidence.get("accepted"), False, "RU_PG_B_PREMATURE_ACCEPTANCE")
    for key in (
        "secret_values_allowed",
        "dsn_allowed",
        "password_allowed",
        "real_user_payload_allowed",
    ):
        _require(evidence.get(key), False, "RU_PG_B_EVIDENCE_INVALID")
    for key in (
        "provider_identity_evidence_required",
        "provider_location_evidence_required",
        "exact_cluster_location_required",
    ):
        _require(evidence.get(key), True, "RU_PG_B_EVIDENCE_INVALID")

    minimum = _mapping(
        payload.get("minimum_tier"),
        "RU_PG_B_MINIMUM_TIER_INVALID",
    )
    _require(
        minimum.get("accepted_for_omni_cio"),
        False,
        "RU_PG_B_MINIMUM_TIER_INVALID",
    )
    _require(
        minimum.get("sql_createrole_escape_hatch_assumed"),
        False,
        "RU_PG_B_MINIMUM_TIER_INVALID",
    )
    _require(
        minimum.get("real_provider_createrole_proof_required"),
        True,
        "RU_PG_B_MINIMUM_TIER_INVALID",
    )

    parity = _mapping(
        payload.get("parity"),
        "RU_PG_B_PARITY_INVALID",
    )
    _require(
        parity.get("runtime_role"),
        "omni_cio_timeweb_synthetic",
        "RU_PG_B_RUNTIME_ROLE_INVALID",
    )
    for key in (
        "reuse_provider_neutral_runtime_sql_renderer",
        "reuse_provider_neutral_runtime_role_convergence",
        "reuse_provider_neutral_runtime_verification",
        "reuse_provider_neutral_postgres_retry",
        "migration_retry_idempotence_required",
        "alter_default_privileges_probe_required",
    ):
        _require(parity.get(key), True, "RU_PG_B_REUSE_INVALID")
    _require(
        parity.get("production_runtime_role_mutated_in_ru_pg_b"),
        False,
        "RU_PG_B_PRODUCTION_ROLE_MUTATION_INVALID",
    )

    next_stage = _mapping(
        payload.get("next_stage"),
        "RU_PG_B_NEXT_STAGE_INVALID",
    )
    _require(next_stage.get("allowed"), False, "RU_PG_B_NEXT_STAGE_INVALID")

    invariants = _mapping(
        payload.get("protected_invariants"),
        "RU_PG_B_INVARIANTS_INVALID",
    )
    required_false = (
        "PUBLIC_MULTI_USER_ENABLED",
        "OMNI_V10_TELEGRAM_LOGIN_ENABLED",
        "OMNI_V10_VK_ID_LOGIN_ENABLED",
        "production_database_cutover_allowed",
        "broker_write",
        "trading_methods",
        "REAL_TRADING_ENABLED",
        "wp23_unlocked",
        "web_visual_started",
    )
    for key in required_false:
        _require(invariants.get(key), False, "RU_PG_B_INVARIANTS_INVALID")
    _require(
        invariants.get("current_neon_production_authority_preserved"),
        True,
        "RU_PG_B_INVARIANTS_INVALID",
    )


def _validate_proof_source() -> None:
    source = _read(PROOF)
    _require_markers(
        source,
        (
            "OMNI_V10_RU_PG_BOOTSTRAP_DSN",
            "TIMEWEB_SYNTHETIC_ONLY",
            "OMNI_V10_RU_PG_PROVIDER_LOCATION",
            'host.endswith(".neon.tech")',
            "RU_PG_NEON_TARGET_FORBIDDEN",
            "require_postgres_18",
            "validate_hosted_postgres_runtime_sql",
            "apply_migrations",
            "postgres_runtime_primitives as postgres_runtime",
            "provider_runtime_primitives as provider_base",
            "RUNTIME_SQL = postgres_runtime.RUNTIME_SQL",
            'RUNTIME_ROLE = "omni_cio_timeweb_synthetic"',
            "postgres_runtime.render_runtime_sql(RUNTIME_ROLE)",
            "postgres_runtime.converge_runtime_role(",
            "postgres_runtime.verify_runtime(runtime, RUNTIME_ROLE)",
            "provider_base._connect_postgres_with_retry(",
            "RU_PG_MIGRATION_RETRY_DRIFT",
            "def _verify_default_privileges(",
            "ALTER DEFAULT PRIVILEGES IN SCHEMA {}",
            "RU_PG_DEFAULT_PRIVILEGES_NOT_EFFECTIVE",
            "pg_catalog.pg_stat_ssl",
            "RU_PG_TLS_VERIFY_FULL_REQUIRED",
            "RU_PG_TLS_ROOT_CERT_REQUIRED",
            "RU_PG_RLS_UNSCOPED_READ_LEAK",
            "RU_PG_RLS_CROSS_TENANT_READ_LEAK",
            "RU_PG_RLS_CROSS_TENANT_WRITE_ALLOWED",
            "RU_PG_RLS_CROSS_TENANT_WRITE_WRONG_FAILURE",
            'exc.sqlstate != "42501"',
            "RU_PG_TIMEWEB_SYNTHETIC_PARITY=PASS",
        ),
        "RU_PG_B_PROOF_SOURCE_DRIFT",
    )
    for forbidden in (
        "TIMEWEB_CLOUD_TOKEN",
        "api.timeweb.cloud",
        "NEON_API_KEY",
        "OMNI_V10_POSTGRES_DSN",
        "PUBLIC_MULTI_USER_ENABLED=true",
        "infrastructure/cloudru",
        "wrangler.jsonc",
    ):
        if forbidden in source:
            raise RuntimeError("RU_PG_B_PROOF_AUTHORITY_WIDENED")


def _validate_provider_neutral_runtime() -> None:
    postgres_runtime = _read(POSTGRES_RUNTIME)
    provider_runtime = _read(PROVIDER_RUNTIME)
    _require_markers(
        postgres_runtime,
        (
            "def render_runtime_sql(runtime_role: str) -> str:",
            "def converge_runtime_role(",
            "CREATE ROLE {} WITH LOGIN NOSUPERUSER NOCREATEDB ",
            "NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}",
            "def verify_runtime(connection: Any, runtime_role: str) -> None:",
            "POSTGRES_RUNTIME_ROLE_DRIFT",
            "POSTGRES_RUNTIME_ROLE_MEMBERSHIP_PRESENT",
            "POSTGRES_RUNTIME_FORCE_RLS_DRIFT",
        ),
        "RU_PG_B_POSTGRES_RUNTIME_PRIMITIVES_DRIFT",
    )
    _require_markers(
        provider_runtime,
        (
            "def _connect_postgres_with_retry(",
            "connect_timeout=_DATABASE_CONNECT_TIMEOUT_SECONDS",
            "_TRANSIENT_RETRY_DELAYS_SECONDS",
        ),
        "RU_PG_B_PROVIDER_RUNTIME_PRIMITIVES_DRIFT",
    )
    if any(
        _contains_retired_provider_runtime_coupling(source)
        for source in (postgres_runtime, provider_runtime)
    ):
        raise RuntimeError("RU_PG_B_PROVIDER_NEUTRAL_RUNTIME_DRIFT")


def _validate_docs() -> None:
    runbook = _read(RUNBOOK)
    status = _read(STATUS)
    _require_markers(
        runbook,
        (
            "RU-PG-B",
            "synthetic",
            "OMNI_V10_RU_PG_BOOTSTRAP_DSN",
            "TIMEWEB_SYNTHETIC_ONLY",
            "real personal data",
            "RU_PG_TIMEWEB_SYNTHETIC_PARITY=PASS",
            "TW-D",
        ),
        "RU_PG_B_RUNBOOK_DRIFT",
    )
    _require_markers(
        status,
        (
            "Amendment 17 / RU-PG-A is accepted",
            "RU-PG-B",
            "PR #560",
            "Production Release #86",
        ),
        "RU_PG_B_STATUS_DOC_DRIFT",
    )


def validate() -> None:
    _validate_contract(_load_contract())
    _validate_proof_source()
    _validate_provider_neutral_runtime()
    _validate_docs()


def main() -> int:
    try:
        validate()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(
        "V10 RU-PG-B Timeweb synthetic parity source contract passed; "
        "provider evidence remains pending."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
