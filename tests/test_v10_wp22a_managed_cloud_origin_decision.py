from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/architecture/V10_WP22A_MANAGED_CLOUD_ORIGIN_CONTRACT.json"
DECISION = ROOT / "docs/architecture/V10_WP22A_MANAGED_CLOUD_ORIGIN_DECISION.md"
SERVICE_SELECTION = ROOT / "docs/architecture/V10_WP22A_SERVICE_SELECTION.md"


def _payload() -> dict[str, object]:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_managed_cloud_origin_recommendation_is_source_only_and_not_apply_authority() -> None:
    payload = _payload()

    assert payload["status"] == "RECOMMENDED_PENDING_OWNER_COST_APPROVAL"
    assert payload["owning_package"] == "WP22A"
    assert payload["phase"] == "SERVICE_HOSTING_ARCHITECTURE_DECISION"

    cost = payload["cost_boundary"]
    assert isinstance(cost, dict)
    assert cost["new_recurring_paid_commitment_required"] is True
    assert cost["owner_cost_approval_required_before_provider_apply"] is True
    assert cost["provider_apply_authorized"] is False
    assert cost["estimate_is_not_purchase_quote"] is True

    activation = payload["activation"]
    assert isinstance(activation, dict)
    assert activation["public_multi_user_enabled"] is False
    assert activation["provider_resources_created"] is False
    assert activation["provider_credentials_allowed_in_pull_request"] is False
    assert activation["wp23_locked"] is True


def test_recommendation_uses_russian_managed_cloud_private_database_and_secret_boundary() -> None:
    payload = _payload()
    recommendation = payload["recommendation"]
    reasoning = payload["selection_reasoning"]
    legal = payload["legal_and_data_boundary"]

    assert isinstance(recommendation, dict)
    assert isinstance(reasoning, dict)
    assert isinstance(legal, dict)

    assert recommendation["provider"] == "CLOUD_RU_EVOLUTION"
    assert recommendation["runtime"] == "EVOLUTION_VM"
    assert recommendation["runtime_region_requirement"] == "RUSSIA"
    assert recommendation["database"] == "CLOUD_RU_MANAGED_POSTGRESQL_PRIVATE_IP"
    assert recommendation["database_public_ip_allowed"] is False
    assert recommendation["network"] == "CLOUD_RU_EVOLUTION_VPC_PRIVATE_SUBNET"
    assert recommendation["secret_store"] == "CLOUD_RU_SECRET_MANAGEMENT"
    assert recommendation["key_management"] == "CLOUD_RU_KEY_MANAGEMENT_OR_REVIEWED_SYSTEM_KEY"

    assert reasoning["russian_personal_data_primary_database_required"] is True
    assert reasoning["managed_postgresql_private_connectivity_required"] is True
    assert reasoning["managed_secret_store_required_for_tenant_broker_credentials"] is True
    assert reasoning["owner_home_availability_dependency_allowed"] is False

    assert legal["russian_federal_law_152_fz_article_18_part_5_localization_gate"] is True
    assert legal["primary_identity_session_tenant_personal_data_outside_russia_allowed_by_this_contract"] is False
    assert legal["production_legal_signoff_required"] is True


def test_cloud_ru_container_apps_is_rejected_for_primary_runtime_with_managed_postgresql() -> None:
    payload = _payload()
    recommendation = payload["recommendation"]
    assert isinstance(recommendation, dict)

    assert recommendation["container_apps_primary_runtime_allowed"] is False
    assert (
        recommendation["container_apps_rejection_reason"]
        == "OFFICIAL_CLOUD_RU_DOCS_STATE_NO_MANAGED_POSTGRESQL_CONNECTIVITY_AND_PUBLIC_DB_PORT_IS_UNSAFE"
    )


def test_candidate_ranking_rejects_render_primary_data_plane_and_keeps_bounded_fallbacks() -> None:
    payload = _payload()
    candidates = payload["candidate_evaluation"]
    assert isinstance(candidates, dict)

    cloud_ru = candidates["CLOUD_RU_EVOLUTION"]
    timeweb = candidates["TIMEWEB_CLOUD"]
    yandex = candidates["YANDEX_CLOUD"]
    render = candidates["RENDER"]
    for candidate in (cloud_ru, timeweb, yandex, render):
        assert isinstance(candidate, dict)

    assert cloud_ru["result"] == "RECOMMENDED_PENDING_COST_APPROVAL"
    assert timeweb["result"] == "FALLBACK_LOWER_COST"
    assert yandex["result"] == "SECURITY_STRONGER_HIGHER_COST_ALTERNATIVE"
    assert render["result"] == "REJECT_PRIMARY_PRODUCTION_DATA_PLANE"
    assert "NO_RUSSIA_REGION" in render["reasons"]
    assert "FREE_POSTGRES_EXPIRES_AFTER_30_DAYS" in render["reasons"]


def test_cloudflare_stays_edge_not_product_identity_and_home_origin_stays_forbidden() -> None:
    payload = _payload()
    recommendation = payload["recommendation"]
    activation = payload["activation"]
    reasoning = payload["selection_reasoning"]
    assert isinstance(recommendation, dict)
    assert isinstance(activation, dict)
    assert isinstance(reasoning, dict)

    assert recommendation["edge"] == "CLOUDFLARE_DNS_TLS_WAF_DDOS_TUNNEL"
    assert recommendation["product_identity_at_edge"] is False
    assert activation["cloudflare_product_authentication_allowed"] is False
    assert activation["telegram_vk_product_authentication_required"] is True
    assert reasoning["owner_home_availability_dependency_allowed"] is False

    decision = DECISION.read_text(encoding="utf-8")
    assert "Cloudflare is an edge and origin-protection component only" in decision
    assert "managed-cloud VM" in decision
    assert "PROJECT OWNER home Lenovo" in decision


def test_money_and_broker_authority_remain_fail_closed() -> None:
    payload = _payload()
    safety = payload["broker_and_money_safety"]
    assert isinstance(safety, dict)

    assert safety["t_invest_public_connector"] == "FAIL_CLOSED_PENDING_BROKER_TERMS_PERMISSION"
    assert safety["broker_credentials"] == "TENANT_SCOPED_ONLY"
    assert safety["broker_write_authority_added"] is False
    assert safety["trading_methods"] is False
    assert safety["real_trading_enabled"] is False
    assert safety["transfer_withdrawal_allowed"] is False
    assert safety["protected_v9_rollback"] is True
    assert safety["app_entrypoint"] == "app:app"


def test_current_service_selection_still_forbids_provider_apply_until_cost_approval() -> None:
    selection = SERVICE_SELECTION.read_text(encoding="utf-8")
    decision = DECISION.read_text(encoding="utf-8")

    assert "NO PROVIDER APPLY AUTHORIZED" in selection
    assert "OWNER COST APPROVAL REQUIRED BEFORE PROVIDER APPLY" in decision
    assert "provider_apply_authorized=false" in decision
    assert "PUBLIC_MULTI_USER_ENABLED=false" in decision
