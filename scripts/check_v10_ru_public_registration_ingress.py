from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/architecture/V10_RU_PUBLIC_REGISTRATION_INGRESS_CONTRACT.json"
AMENDMENT = ROOT / (
    "docs/master-plan/"
    "OMNI_CIO_V10_RU_PUBLIC_REGISTRATION_AND_RUSSIAN_INGRESS_AMENDMENT.md"
)
INDEX = ROOT / "docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md"
STATUS = ROOT / "knowledge/17_V10_CURRENT_PROGRAM_STATUS.md"
WORKFLOW = ROOT / ".github/workflows/v10-engineering-governance.yml"

EXPECTED_PROVIDERS = ["GitHub", "Cloudflare", "Timeweb Cloud"]
EXPECTED_MIGRATION = ["RU-PG-B", "RU-PG-C", "RU-PG-D", "RU-PG-E"]
EXPECTED_SPLITS = [
    "RU-PG-B_PROVIDER_PARITY",
    "RU-PG-C_RUNTIME_TLS_RECOVERY",
    "RU-PG-D_PRODUCTION_DATABASE_CUTOVER",
    "RU-PG-E_NEON_ACTIVE_AUTHORITY_RETIREMENT",
    "RUSSIA_INGRESS_PROVIDER_SPEND_AND_DNS_CUTOVER",
    "LEGAL_REGULATORY_OWNER_ACTIONS",
    "PUBLIC_USER_ACTIVATION",
]


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError(f"RU_PUBLIC_INGRESS_SOURCE_UNREADABLE:{path.name}") from exc


def _load() -> dict[str, Any]:
    try:
        payload = json.loads(_read(CONTRACT))
    except json.JSONDecodeError as exc:
        raise RuntimeError("RU_PUBLIC_INGRESS_CONTRACT_INVALID") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("RU_PUBLIC_INGRESS_CONTRACT_INVALID")
    return payload


def _mapping(value: object, code: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(code)
    return value


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise RuntimeError(code)


def _validate_contract(payload: dict[str, Any]) -> None:
    _require(
        payload.get("schema") == "omni-cio.v10.ru-public-registration-ingress.v1",
        "RU_PUBLIC_INGRESS_SCHEMA_INVALID",
    )
    _require(
        payload.get("amendment_number") == 18,
        "RU_PUBLIC_INGRESS_AUTHORITY_INVALID",
    )
    _require(payload.get("owning_issue") == 580, "RU_PUBLIC_INGRESS_DASHBOARD_INVALID")
    _require(
        payload.get("supported_launch_population") == "RUSSIAN_FEDERATION",
        "RU_PUBLIC_INGRESS_POPULATION_INVALID",
    )

    providers = _mapping(payload.get("providers"), "RU_PUBLIC_INGRESS_PROVIDER_INVALID")
    _require(
        providers.get("exact_public_launch_set") == EXPECTED_PROVIDERS,
        "RU_PUBLIC_INGRESS_PROVIDER_SET_INVALID",
    )
    _require(
        providers.get("cloudflare_role") == "ACCEPTED_BUILD_RELEASE_STAGING_FALLBACK",
        "RU_PUBLIC_INGRESS_CLOUDFLARE_ROLE_INVALID",
    )
    _require(
        providers.get("timeweb_role")
        == "RUSSIAN_POSTGRESQL_AND_RUSSIA_FACING_INGRESS_CANDIDATE",
        "RU_PUBLIC_INGRESS_TIMEWEB_ROLE_INVALID",
    )
    _require(
        providers.get("render_active_v10_allowed") is False,
        "RU_PUBLIC_RENDER_REENABLED",
    )
    _require(
        providers.get("cloud_ru_active_v10_allowed") is False,
        "RU_PUBLIC_CLOUD_RU_REENABLED",
    )

    product = _mapping(
        payload.get("product_model"),
        "RU_PUBLIC_INGRESS_PRODUCT_INVALID",
    )
    for key in (
        "one_canonical_web",
        "one_account_tenant_session_authority",
        "same_exact_source_sha_required",
    ):
        _require(product.get(key) is True, "RU_PUBLIC_INGRESS_PRODUCT_INVALID")
    for key in (
        "second_user_facing_product_allowed",
        "auth_bypass_allowed",
        "dual_primary_database_allowed",
        "dual_primary_session_authority_allowed",
    ):
        _require(product.get(key) is False, "RU_PUBLIC_INGRESS_PRODUCT_INVALID")

    reachability = _mapping(
        payload.get("cloudflare_russia_reachability"),
        "RU_PUBLIC_INGRESS_REACHABILITY_INVALID",
    )
    _require(
        reachability.get("cloudflare_only_public_ingress_accepted_for_russia_launch")
        is False,
        "RU_PUBLIC_INGRESS_CLOUDFLARE_ONLY_INVALID",
    )
    _require(
        reachability.get("representative_russian_network_no_vpn_evidence_required")
        is True,
        "RU_PUBLIC_INGRESS_NO_VPN_EVIDENCE_REQUIRED",
    )

    app = _mapping(
        payload.get("timeweb_app_platform_candidate"),
        "RU_PUBLIC_INGRESS_APP_PLATFORM_INVALID",
    )
    _require(
        app.get("approved_for_source_compatibility_work") is True,
        "RU_PUBLIC_APP_SCOPE_INVALID",
    )
    _require(
        app.get("live_public_deploy_authorized_by_contract") is False,
        "RU_PUBLIC_APP_LIVE_WIDENED",
    )
    _require(
        app.get("production_autodeploy_allowed") is False,
        "RU_PUBLIC_APP_AUTODEPLOY_FORBIDDEN",
    )
    _require(
        app.get("explicit_accepted_main_commit_required") is True,
        "RU_PUBLIC_APP_SHA_REQUIRED",
    )
    _require(
        app.get("runtime_secrets_in_repository_allowed") is False,
        "RU_PUBLIC_APP_SECRET_INVALID",
    )

    ingress = _mapping(
        payload.get("ingress_security"),
        "RU_PUBLIC_INGRESS_SECURITY_INVALID",
    )
    for key in (
        "provider_neutral_product_core_required",
        "cloudflare_adapter_remains_thin",
        "timeweb_adapter_must_not_assume_cloudflare_internal_headers",
        "documented_or_empirically_verified_client_ip_contract_required",
        "tls_required",
        "canonical_host_origin_callback_validation_required",
        "csrf_and_secure_cookie_equivalence_required",
        "cross_tenant_negative_required",
        "rollback_required",
    ):
        _require(ingress.get(key) is True, "RU_PUBLIC_INGRESS_SECURITY_INVALID")
    _require(
        ingress.get("arbitrary_forwarded_headers_trusted") is False,
        "RU_PUBLIC_INGRESS_FORWARDED_TRUST_FORBIDDEN",
    )

    database = _mapping(
        payload.get("database_end_state"),
        "RU_PUBLIC_INGRESS_DATABASE_INVALID",
    )
    _require(
        database.get("final_production_provider")
        == "Timeweb Cloud Managed PostgreSQL 18",
        "RU_PUBLIC_INGRESS_DATABASE_PROVIDER_INVALID",
    )
    _require(
        database.get("migration_sequence") == EXPECTED_MIGRATION,
        "RU_PUBLIC_INGRESS_DATABASE_SEQUENCE_INVALID",
    )
    _require(
        database.get("neon_active_production_retirement_stage") == "RU-PG-E",
        "RU_PUBLIC_INGRESS_NEON_RETIREMENT_INVALID",
    )
    _require(
        database.get("neon_delete_before_ru_pg_d_allowed") is False,
        "RU_PUBLIC_INGRESS_NEON_EARLY_DELETE_FORBIDDEN",
    )
    _require(
        database.get("real_russian_user_data_before_ru_pg_d_allowed") is False,
        "RU_PUBLIC_INGRESS_PRECUTOVER_REAL_DATA_FORBIDDEN",
    )

    cost = _mapping(payload.get("cost_policy"), "RU_PUBLIC_INGRESS_COST_INVALID")
    _require(
        cost.get("existing_prepaid_funds_first") is True,
        "RU_PUBLIC_INGRESS_COST_INVALID",
    )
    _require(
        cost.get("spare_capacity_preprovision_allowed") is False,
        "RU_PUBLIC_SPARE_CAPACITY_FORBIDDEN",
    )
    _require(
        cost.get("app_platform_exact_current_price_required_before_purchase") is True,
        "RU_PUBLIC_APP_COST_EVIDENCE_REQUIRED",
    )
    _require(
        cost.get("new_top_up_or_plan_commitment_requires_fresh_owner_approval") is True,
        "RU_PUBLIC_NEW_PAYMENT_AUTHORITY_INVALID",
    )

    activation = _mapping(
        payload.get("activation"),
        "RU_PUBLIC_INGRESS_ACTIVATION_INVALID",
    )
    _require(
        activation.get("public_registration_allowed_by_contract") is False,
        "RU_PUBLIC_INGRESS_PREMATURE_ACTIVATION",
    )
    _require(
        activation.get("telegram_first_allowed_after_owning_gates") is True,
        "RU_PUBLIC_TELEGRAM_PROGRESSIVE_ACTIVATION_INVALID",
    )

    execution = _mapping(
        payload.get("execution"),
        "RU_PUBLIC_INGRESS_EXECUTION_INVALID",
    )
    _require(
        execution.get("umbrella_program_issue") == 580,
        "RU_PUBLIC_INGRESS_DASHBOARD_INVALID",
    )
    _require(
        execution.get("one_unbounded_pr_for_all_stages_allowed") is False,
        "RU_PUBLIC_INGRESS_SPLIT_BOUNDARY_INVALID",
    )
    _require(
        execution.get("mandatory_split_boundaries") == EXPECTED_SPLITS,
        "RU_PUBLIC_INGRESS_SPLIT_BOUNDARY_INVALID",
    )

    protected = _mapping(
        payload.get("protected_invariants"),
        "RU_PUBLIC_INGRESS_INVARIANTS_INVALID",
    )
    for key in (
        "PUBLIC_MULTI_USER_ENABLED",
        "OMNI_V10_TELEGRAM_LOGIN_ENABLED",
        "OMNI_V10_VK_ID_LOGIN_ENABLED",
        "broker_write",
        "trading_methods",
        "REAL_TRADING_ENABLED",
    ):
        _require(protected.get(key) is False, "RU_PUBLIC_INGRESS_INVARIANTS_INVALID")
    _require(
        protected.get("protected_v9_entrypoint") == "app:app",
        "RU_PUBLIC_INGRESS_V9_INVALID",
    )


def _validate_documents() -> None:
    amendment = _read(AMENDMENT)
    for marker in (
        "Russian Public Registration & Reachable Ingress Authority / Amendment 18",
        "one canonical Omni-CIO Web",
        "Timeweb App Platform",
        "RU-PG-B -> RU-PG-C -> RU-PG-D -> RU-PG-E",
        "Neon must not be deleted before",
        "issue #580",
        "PUBLIC_MULTI_USER_ENABLED=false",
    ):
        _require(marker in amendment, "RU_PUBLIC_INGRESS_AMENDMENT_DRIFT")

    index = _read(INDEX)
    _require(
        "### 18. Russian Public Registration & Reachable Ingress Authority" in index,
        "RU_PUBLIC_INGRESS_INDEX_MISSING",
    )

    status = _read(STATUS)
    for marker in (
        "Amendment 18 — Russia-only public registration / reachable ingress",
        "Timeweb Read-Only Proof #11",
        "TIMEWEB_RU_PG_CONTROL_PLANE=READ_ONLY_READY",
        "issue #580",
        "Cloudflare-only public ingress is not sufficient evidence",
    ):
        _require(marker in status, "RU_PUBLIC_INGRESS_STATUS_DRIFT")

    workflow = _read(WORKFLOW)
    _require(
        "python scripts/check_v10_ru_public_registration_ingress.py" in workflow,
        "RU_PUBLIC_INGRESS_GOVERNANCE_WORKFLOW_MISSING",
    )
    _require(
        "tests.test_v10_ru_public_registration_ingress" in workflow,
        "RU_PUBLIC_INGRESS_GOVERNANCE_TEST_MISSING",
    )


def main() -> int:
    try:
        _validate_contract(_load())
        _validate_documents()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(
        "V10 Russia public-registration ingress authority passed: one product, "
        "Timeweb PostgreSQL end-state, Russia-reachable ingress evidence and "
        "cutover/recovery splits remain fail-closed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
