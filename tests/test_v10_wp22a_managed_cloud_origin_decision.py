from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/architecture/V10_WP22A_MANAGED_CLOUD_ORIGIN_CONTRACT.json"
DECISION = ROOT / "docs/architecture/V10_WP22A_MANAGED_CLOUD_ORIGIN_DECISION.md"
SERVICE_SELECTION = ROOT / "docs/architecture/V10_WP22A_SERVICE_SELECTION.md"


def _payload() -> dict[str, Any]:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_selection_is_source_only_and_not_apply_authority() -> None:
    payload = _payload()

    assert payload["status"] == "RECOMMENDED_PENDING_OWNER_COST_APPROVAL"
    assert payload["owning_package"] == "WP22A"
    assert payload["phase"] == "SERVICE_HOSTING_ARCHITECTURE_DECISION"

    cost = payload["cost_boundary"]
    assert cost["new_recurring_paid_commitment_required"] is True
    assert cost["owner_cost_approval_required_before_provider_apply"] is True
    assert cost["provider_apply_authorized"] is False
    assert cost["estimate_is_not_purchase_quote"] is True

    activation = payload["activation"]
    assert activation["public_multi_user_enabled"] is False
    assert activation["provider_resources_created"] is False
    assert activation["provider_credentials_allowed_in_pull_request"] is False
    assert activation["wp23_locked"] is True


def test_recommendation_has_private_database_and_secret_boundary() -> None:
    payload = _payload()
    recommendation = payload["recommendation"]
    reasoning = payload["selection_reasoning"]
    legal = payload["legal_and_data_boundary"]

    initial_ha = "database_primary_standby_required_for_initial_production"
    single_node = "database_single_node_is_initial_production_recommendation"
    compliance = (
        "cloud_ru_evolution_152_fz_uz_1_"
        "infrastructure_claim_verified_from_provider_docs"
    )
    provider_obligations = (
        "provider_compliance_does_not_replace_omni_cio_operator_obligations"
    )

    assert recommendation["provider"] == "CLOUD_RU_EVOLUTION"
    assert recommendation["runtime"] == "EVOLUTION_VM"
    assert recommendation["runtime_region_requirement"] == "RUSSIA"
    assert recommendation["database"] == "CLOUD_RU_MANAGED_POSTGRESQL_PRIVATE_IP"
    assert recommendation["database_mode"] == "STANDARD"
    assert recommendation["database_topology"] == "PRIMARY_STANDBY_TWO_NODE"
    assert recommendation[initial_ha] is True
    assert recommendation["database_public_ip_allowed"] is False
    assert recommendation["network"] == "CLOUD_RU_EVOLUTION_VPC_PRIVATE_SUBNET"
    assert recommendation["secret_store"] == "CLOUD_RU_SECRET_MANAGEMENT"
    assert recommendation["key_management"] == (
        "CLOUD_RU_KEY_MANAGEMENT_OR_REVIEWED_SYSTEM_KEY"
    )

    assert reasoning["russian_personal_data_primary_database_required"] is True
    assert reasoning["managed_postgresql_private_connectivity_required"] is True
    assert (
        reasoning["managed_secret_store_required_for_tenant_broker_credentials"]
        is True
    )
    assert reasoning[single_node] is False
    assert reasoning["owner_home_availability_dependency_allowed"] is False

    localization_gate = "russian_federal_law_152_fz_article_18_part_5_localization_gate"
    outside_russia = (
        "primary_identity_session_tenant_personal_data_"
        "outside_russia_allowed_by_this_contract"
    )
    assert legal[localization_gate] is True
    assert legal[outside_russia] is False
    assert legal[compliance] is True
    assert legal[provider_obligations] is True
    assert legal["production_legal_signoff_required"] is True


def test_cloud_ru_container_apps_is_rejected_for_primary_runtime() -> None:
    recommendation = _payload()["recommendation"]

    assert recommendation["container_apps_primary_runtime_allowed"] is False
    assert recommendation["container_apps_rejection_reason"] == (
        "OFFICIAL_CLOUD_RU_DOCS_STATE_NO_MANAGED_POSTGRESQL_CONNECTIVITY_"
        "AND_PUBLIC_DB_PORT_IS_UNSAFE"
    )


def test_candidate_ranking_keeps_bounded_fallbacks() -> None:
    candidates = _payload()["candidate_evaluation"]

    cloud_ru = candidates["CLOUD_RU_EVOLUTION"]
    timeweb = candidates["TIMEWEB_CLOUD"]
    yandex = candidates["YANDEX_CLOUD"]
    render = candidates["RENDER"]

    assert cloud_ru["result"] == "RECOMMENDED_PENDING_COST_APPROVAL"
    assert "EVOLUTION_PLATFORM_152_FZ_UZ_1" in cloud_ru["strengths"]
    assert "MANAGED_POSTGRESQL_PRIMARY_STANDBY" in cloud_ru["strengths"]
    assert timeweb["result"] == "FALLBACK_LOWER_COST"
    assert yandex["result"] == "SECURITY_STRONGER_HIGHER_COST_ALTERNATIVE"
    assert render["result"] == "REJECT_PRIMARY_PRODUCTION_DATA_PLANE"
    assert "NO_RUSSIA_REGION" in render["reasons"]
    assert "FREE_POSTGRES_EXPIRES_AFTER_30_DAYS" in render["reasons"]


def test_reference_cost_uses_ha_database_and_remains_non_binding() -> None:
    cost = _payload()["cost_boundary"]
    pg_ha_cost = (
        "cloud_ru_reference_pg_primary_standby_"
        "2x_1vcpu_2gb_20gb_monthly_rub_approx"
    )
    excluded_costs = (
        "reference_minimum_stack_excludes_domain_extra_object_storage_"
        "traffic_monitoring_and_later_scale"
    )

    assert cost[pg_ha_cost] == 3792.0528
    assert cost["cloud_ru_reference_minimum_stack_monthly_rub_approx"] == 4802.8752
    assert cost[excluded_costs] is True
    assert cost["exact_selected_vm_price_revalidation_required_before_purchase"] is True
    assert cost["estimate_is_not_purchase_quote"] is True


def test_cloudflare_is_edge_not_product_identity() -> None:
    payload = _payload()
    recommendation = payload["recommendation"]
    activation = payload["activation"]
    reasoning = payload["selection_reasoning"]

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
    safety = _payload()["broker_and_money_safety"]

    assert safety["t_invest_public_connector"] == (
        "FAIL_CLOSED_PENDING_BROKER_TERMS_PERMISSION"
    )
    assert safety["broker_credentials"] == "TENANT_SCOPED_ONLY"
    assert safety["broker_write_authority_added"] is False
    assert safety["trading_methods"] is False
    assert safety["real_trading_enabled"] is False
    assert safety["transfer_withdrawal_allowed"] is False
    assert safety["protected_v9_rollback"] is True
    assert safety["app_entrypoint"] == "app:app"


def test_service_selection_still_forbids_provider_apply() -> None:
    selection = SERVICE_SELECTION.read_text(encoding="utf-8")
    decision = DECISION.read_text(encoding="utf-8")

    assert "NO PROVIDER APPLY AUTHORIZED" in selection
    assert "OWNER COST APPROVAL REQUIRED BEFORE PROVIDER APPLY" in decision
    assert "provider_apply_authorized=false" in decision
    assert "PUBLIC_MULTI_USER_ENABLED=false" in decision
