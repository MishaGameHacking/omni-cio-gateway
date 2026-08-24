from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "knowledge" / "17_V10_CURRENT_PROGRAM_STATUS.md"
CONTRACT = (
    ROOT
    / "docs"
    / "architecture"
    / "V10_WP22A_PHASE4_FREE_PREVIEW_CONTRACT.json"
)
AUTHORIZATION = (
    ROOT
    / "docs"
    / "architecture"
    / "V10_WP22A_PHASE4_FREE_PREVIEW_AUTHORIZATION.md"
)


def _contract() -> dict[str, Any]:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_phase3_and_phase4_are_accepted_and_phase5_is_current() -> None:
    text = STATUS.read_text(encoding="utf-8")

    assert (
        "PHASE 3 ACCEPTED / PHASE 4 ACCEPTED / "
        "PHASE 5 TECHNICAL CLOSEOUT AUTHORIZED / "
        "PUBLIC PRODUCTION ACTIVATION LOCKED" in text
    )
    assert "Block E / WP22A Phase 3 — **ACCEPTED**" in text
    assert "Block E / WP22A Phase 4 — **ACCEPTED**" in text
    assert (
        "Block E / WP22A Phase 5 — "
        "**INTEGRATED TECHNICAL CLOSEOUT AUTHORIZED CURRENT INCREMENT**"
        in text
    )
    assert (
        "## Current next package — WP22A Phase 5 — Integrated technical closeout"
        in text
    )


def test_exact_phase3_acceptance_evidence_is_pinned() -> None:
    payload = _contract()
    authority = payload["authority"]
    assert isinstance(authority, dict)

    chunks = authority["accepted_main_sha_chunks"]
    assert isinstance(chunks, list)
    assert "".join(chunks) == (
        "fbd50b2a"
        "a5029170"
        "d9aabf17"
        "8103e2e7"
        "61648422"
    )
    assert authority["phase3_accepted"] is True
    assert authority["phase4_authorized"] is True


def test_owner_authority_is_zero_cost_and_no_paid_fallback() -> None:
    authority = _contract()["authority"]
    assert isinstance(authority, dict)

    assert authority["owner_authorization_scope"] == (
        "ZERO_COST_SYNTHETIC_PUBLIC_PREVIEW_ONLY"
    )
    assert authority["authorized_recurring_rub"] == 0
    assert authority["authorized_recurring_usd"] == 0
    assert authority["payment_method_charge_allowed"] is False
    assert authority["automatic_paid_overage_allowed"] is False


def test_provider_and_github_boundaries_are_fail_closed() -> None:
    payload = _contract()
    providers = payload["providers"]
    github = payload["github_boundary"]
    assert isinstance(providers, dict)
    assert isinstance(github, dict)

    assert providers == {
        "preview_web": "Render",
        "preview_database": "Neon",
        "production_provider_remains": "Cloud.ru Evolution",
        "cloudru_production_apply_authorized": False,
    }
    assert github["accepted_main_only"] is True
    assert github["pull_request_secret_access_allowed"] is False
    assert github["ordinary_ci_secret_access_allowed"] is False
    assert github["required_secret_names"] == [
        "RENDER_API_KEY",
        "NEON_API_KEY",
    ]
    assert github["secret_values_in_source_allowed"] is False
    assert github["secret_values_in_logs_allowed"] is False
    assert github["secret_values_in_artifacts_allowed"] is False
    assert github["idempotent_apply_required"] is True
    assert github["expected_head_verification_required"] is True


def test_preview_reuses_existing_product_and_preserves_v9() -> None:
    service = _contract()["preview_service"]
    assert isinstance(service, dict)

    assert service["name"] == "omni-cio-v10-web"
    assert service["render_plan"] == "free"
    assert service["branch"] == "main"
    assert service["protected_v9_service_mutation_allowed"] is False
    assert service["protected_v9_entrypoint"] == "app:app"
    assert service["react_source"] == "apps/web"
    assert service["api_source"] == "apps/api"
    assert service["single_origin_required"] is True
    assert service["bind_host"] == "0.0.0.0"
    assert service["bind_port_from_environment"] == "PORT"


def test_database_is_postgresql18_free_tls_and_tenant_safe() -> None:
    database = _contract()["preview_database"]
    assert isinstance(database, dict)

    assert database["engine"] == "postgresql"
    assert database["major_version"] == 18
    assert database["region_preference"] == "EUROPE_FRANKFURT"
    assert database["free_plan_required"] is True
    assert database["tls_required"] is True
    assert database["pooled_runtime_connection_required"] is True
    assert database["migration_connection_separate_when_supported"] is True
    assert database["bootstrap_connection_runtime_use_allowed"] is False
    assert database["runtime_role_creation"] == "SQL_ONLY"
    assert database["neon_control_plane_runtime_role_allowed"] is False
    assert database["neon_superuser_membership_allowed"] is False
    assert database["bypass_rls_allowed"] is False
    assert database["runtime_role_attributes"] == {
        "login": True,
        "superuser": False,
        "createdb": False,
        "createrole": False,
        "replication": False,
        "bypassrls": False,
    }
    assert database["least_privilege_runtime_role_required"] is True
    assert database["tenant_rls_verification_required"] is True
    assert database["force_rls_verification_required"] is True


def test_preview_is_synthetic_and_does_not_activate_product_authority() -> None:
    payload = _contract()
    data = payload["preview_data"]
    safety = payload["safety"]
    assert isinstance(data, dict)
    assert isinstance(safety, dict)

    assert data["synthetic_only"] is True
    assert data["real_user_registration_allowed"] is False
    assert data["real_tenant_private_data_allowed"] is False
    assert data["real_broker_credentials_allowed"] is False
    assert data["real_portfolio_payload_allowed"] is False
    assert data["public_tinvest_connector_allowed"] is False
    assert data["demo_identity_may_select_production_tenant"] is False
    for key in (
        "public_multi_user_enabled",
        "billing_enabled",
        "trial_enabled",
        "subscription_enforcement",
        "premium_feature_gating",
        "trading_methods",
        "real_trading_enabled",
        "broker_write_enabled",
        "wp23_unlocked",
    ):
        assert safety[key] is False


def test_acceptance_and_stop_conditions_remain_explicit() -> None:
    payload = _contract()
    acceptance = payload["acceptance"]
    stop_conditions = payload["stop_conditions"]
    assert isinstance(acceptance, dict)
    assert isinstance(stop_conditions, list)

    for key in (
        "credential_preflight_required",
        "database_migrations_required",
        "schema_digest_match_required",
        "release_sha_match_required",
        "health_before_traffic_required",
        "external_https_probe_required",
        "private_response_cache_no_store_required",
        "rollback_to_last_accepted_release_required",
        "phase5_acceptance_not_implied",
    ):
        assert acceptance[key] is True
    assert acceptance["provider_identity_logged_allowed"] is False
    assert stop_conditions == [
        "INVALID_OR_INSUFFICIENT_PROVIDER_KEY",
        "PAYMENT_OR_CARD_REQUIRED",
        "FREE_PLAN_UNAVAILABLE",
        "ACCOUNT_VERIFICATION_REQUIRES_OWNER",
        "PAID_OVERAGE_REQUIRED",
        "PROTECTED_V9_MUTATION_REQUIRED",
        "REAL_PRIVATE_OR_BROKER_DATA_REQUIRED",
        "CLOUDRU_PRODUCTION_MUTATION_REQUIRED",
    ]


def test_human_authorization_contract_carries_required_markers() -> None:
    text = AUTHORIZATION.read_text(encoding="utf-8")

    for marker in (
        "AUTHORIZED ON ACCEPTANCE / ZERO-COST SYNTHETIC PREVIEW ONLY",
        "WP22A — External Web Access / Product Authentication Security Gate",
        "omni-cio-v10-web",
        "runtime role created with SQL only, never through Neon Console/CLI/API",
        "NO `neon_superuser`, predefined broad role or `BYPASSRLS` membership",
        "`PUBLIC_MULTI_USER_ENABLED=false`",
        "`trading_methods=false`",
        "`REAL_TRADING_ENABLED=false`",
        "Phase 5 still owns normal USER login/logout/session acceptance",
    ):
        assert marker.casefold() in text.casefold()
