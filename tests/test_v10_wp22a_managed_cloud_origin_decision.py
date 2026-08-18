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


def test_runtime_and_nlb_are_georedundant() -> None:
    payload = _payload()
    recommendation = payload["recommendation"]
    reasoning = payload["selection_reasoning"]

    assert recommendation["provider"] == "CLOUD_RU_EVOLUTION"
    assert recommendation["runtime"] == "EVOLUTION_VM"
    assert recommendation["runtime_topology"] == (
        "TWO_VM_ACTIVE_ACTIVE_DISTINCT_AZ_BEHIND_GEOREDUNDANT_EVOLUTION_NLB"
    )
    assert recommendation["runtime_region_requirement"] == "RUSSIA"
    assert recommendation["runtime_distinct_availability_zones_required"] is True
    assert recommendation["edge"] == "CLOUD_RU_EVOLUTION_DNS_NLB_NGINX_TLS"
    assert recommendation["public_dns"] == "CLOUD_RU_EVOLUTION_DNS"
    assert recommendation["public_load_balancer"] == "CLOUD_RU_EVOLUTION_L4_NLB"
    assert recommendation["public_load_balancer_selected_availability_zones"] == 2
    assert recommendation["public_load_balancer_resource_units_per_selected_az"] == 1
    assert recommendation["public_load_balancer_total_initial_resource_units"] == 2
    assert recommendation["public_load_balancer_provider_min_resource_units_per_az"] == 1
    assert recommendation["public_load_balancer_georedundant_placement_required"] is True
    assert reasoning["runtime_cross_az_placement_required_for_initial_public_production"] is True
    assert reasoning["nlb_cross_az_placement_required_for_initial_public_production"] is True
    assert reasoning["nlb_total_two_resource_units_selected_as_one_per_two_az"] is True


def test_nlb_automation_documentation_conflict_fails_closed() -> None:
    payload = _payload()
    recommendation = payload["recommendation"]
    reasoning = payload["selection_reasoning"]

    assert recommendation["public_load_balancer_automation"] == (
        "PINNED_TERRAFORM_PROVIDER_IF_NLB_RESOURCE_ACCEPTANCE_PASSES_"
        "ELSE_CLOUD_RU_PUBLIC_API"
    )
    assert recommendation["public_load_balancer_terraform_support_state"] == (
        "OFFICIAL_DOCS_CONFLICT_REQUIRES_PINNED_PROVIDER_ACCEPTANCE"
    )
    assert recommendation["public_load_balancer_service_limitations_says_terraform_unsupported"] is True
    assert recommendation["public_load_balancer_terraform_resource_reference_present"] is True
    assert recommendation["public_load_balancer_public_api_supported"] is True
    assert recommendation["public_load_balancer_apply_blocked_until_automation_path_validated"] is True
    assert reasoning["nlb_automation_must_be_verified_against_pinned_provider_before_apply"] is True
    assert reasoning["terraform_only_provider_automation_required"] is False
    assert reasoning["provider_documentation_conflict_must_fail_closed"] is True


def test_cloudflare_primary_edge_is_rejected_for_russian_user_reachability() -> None:
    payload = _payload()
    recommendation = payload["recommendation"]
    candidate = payload["candidate_evaluation"]["CLOUDFLARE_PRIMARY_EDGE"]

    assert recommendation["cloudflare_primary_or_sole_production_edge_allowed"] is False
    assert recommendation["cloudflare_primary_edge_rejection_reason"] == (
        "CLOUDFLARE_2026_SUPPORT_DOCS_CONFIRM_SYSTEMATIC_RUSSIA_ISP_"
        "THROTTLING_MAKING_RUSSIAN_USER_ACCESS_UNRELIABLE"
    )
    assert recommendation["cloudflare_optional_secondary_use"] == (
        "DEFERRED_REQUIRES_SEPARATE_REACHABILITY_DATA_LOCALIZATION_AND_COST_REVIEW"
    )
    assert candidate["result"] == "REJECT_PRIMARY_OR_SOLE_RUSSIAN_USER_PRODUCTION_EDGE"

    decision = DECISION.read_text(encoding="utf-8")
    assert "not** the primary or sole production edge" in decision


def test_database_uses_provider_recommended_production_cluster_ha() -> None:
    payload = _payload()
    recommendation = payload["recommendation"]
    reasoning = payload["selection_reasoning"]

    assert recommendation["database"] == "CLOUD_RU_MANAGED_POSTGRESQL_PRIVATE_IP"
    assert recommendation["database_mode"] == "BUSINESS"
    assert recommendation["database_topology"] == "CLUSTER_HA_THREE_NODE_MULTI_AZ"
    assert recommendation["database_primary_nodes"] == 1
    assert recommendation["database_standby_nodes"] == 2
    assert recommendation["database_availability_zones"] == 3
    assert recommendation["database_multi_az_required_for_initial_production"] is True
    assert recommendation["database_provider_recommended_production_topology_used"] is True
    assert recommendation["database_standard_mode_allowed_for_initial_public_production"] is False
    assert recommendation["database_two_node_primary_standby_allowed_as_initial_public_production_baseline"] is False
    assert recommendation["database_public_ip_allowed"] is False
    assert recommendation["network"] == "CLOUD_RU_EVOLUTION_VPC_PRIVATE_SUBNETS_ACROSS_REQUIRED_AZS"

    assert reasoning["database_business_mode_required_for_initial_public_production"] is True
    assert reasoning["database_three_node_multi_az_required_for_initial_public_production"] is True
    assert reasoning["database_two_node_topology_is_not_initial_public_production_recommendation"] is True
    assert reasoning["database_standard_mode_is_not_initial_public_production_recommendation"] is True

    decision = DECISION.read_text(encoding="utf-8")
    selection = SERVICE_SELECTION.read_text(encoding="utf-8")
    assert "Business Cluster HA" in decision
    assert "Primary + 2 Standby" in decision
    assert "three different availability zones" in decision
    assert "Business Cluster HA" in selection
    assert "3 AZ" in selection


def test_private_secret_and_legal_boundaries_remain_fail_closed() -> None:
    payload = _payload()
    recommendation = payload["recommendation"]
    reasoning = payload["selection_reasoning"]
    legal = payload["legal_and_data_boundary"]

    assert recommendation["secret_store"] == "CLOUD_RU_SECRET_MANAGEMENT"
    assert recommendation["key_management"] == "CLOUD_RU_KEY_MANAGEMENT_OR_REVIEWED_SYSTEM_KEY"
    assert recommendation["outbound_internet"] == "CLOUD_RU_EVOLUTION_SNAT"
    assert reasoning["managed_postgresql_private_connectivity_required"] is True
    assert reasoning["managed_secret_store_required_for_tenant_broker_credentials"] is True
    assert reasoning["owner_home_availability_dependency_allowed"] is False
    assert legal["russian_federal_law_152_fz_article_18_part_5_localization_gate"] is True
    assert legal["primary_identity_session_tenant_personal_data_outside_russia_allowed_by_this_contract"] is False
    assert legal["cross_border_processing_allowed_without_separate_legal_review"] is False
    assert legal["production_legal_signoff_required"] is True
    assert legal["provider_compliance_does_not_replace_omni_cio_operator_obligations"] is True


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

    assert cloud_ru["result"] == "RECOMMENDED_PENDING_COST_APPROVAL"
    for marker in (
        "THREE_VM_AVAILABILITY_ZONES",
        "MANAGED_POSTGRESQL_BUSINESS_CLUSTER_HA_THREE_NODE_MULTI_AZ",
        "MANAGED_POSTGRESQL_BUSINESS_CLIENT_VPC_ISOLATION",
        "GEOREDUNDANT_NLB_ACROSS_AVAILABILITY_ZONES",
        "EVOLUTION_DNS",
        "EVOLUTION_L4_LOAD_BALANCER_WITH_HEALTH_CHECKS",
        "EVOLUTION_CERTIFICATE_MANAGER_LETS_ENCRYPT",
        "TERRAFORM_NLB_RESOURCE_REFERENCE_PRESENT",
        "PUBLIC_API_FOR_NLB",
    ):
        assert marker in cloud_ru["strengths"]

    assert "BUSINESS_THREE_NODE_MULTI_AZ_COSTS_MATERIALLY_MORE_THAN_STANDARD_OR_TWO_NODE" in cloud_ru["known_tradeoffs"]
    assert candidates["TIMEWEB_CLOUD"]["result"] == "FALLBACK_LOWER_COST"
    assert candidates["YANDEX_CLOUD"]["result"] == "SECURITY_STRONGER_HIGHER_COST_ALTERNATIVE"
    assert candidates["RENDER"]["result"] == "REJECT_PRIMARY_PRODUCTION_DATA_PLANE"


def test_reference_cost_includes_three_node_database_and_georedundant_edge() -> None:
    cost = _payload()["cost_boundary"]
    pg_node = "cloud_ru_reference_pg_business_node_4vcpu_8gb_40gb_monthly_rub_approx"
    pg_ha = "cloud_ru_reference_pg_business_cluster_ha_multi_az_3x_4vcpu_8gb_40gb_monthly_rub_approx"
    two_vms = "cloud_ru_reference_two_runtime_vms_with_20gb_disks_monthly_rub_approx"
    nlb = "cloud_ru_reference_nlb_two_az_one_resource_unit_each_plus_public_ip_monthly_rub_approx"
    excluded = (
        "reference_initial_stack_excludes_domain_extra_object_storage_traffic_"
        "monitoring_external_waf_ddos_service_and_later_scale"
    )

    assert cost[pg_node] == 7099.2288
    assert cost[pg_ha] == 21297.6864
    assert cost[two_vms] == 1722.9888
    assert cost[nlb] == 1305.8879904
    assert cost["cloud_ru_reference_public_dns_zone_30_days_monthly_rub_approx"] == 32.94
    assert cost["cloud_ru_certificate_manager_monthly_rub"] == 0
    assert cost["cloud_ru_reference_initial_stack_monthly_rub_approx"] == 24508.8311904
    assert cost[excluded] is True
    assert cost["exact_selected_vm_price_revalidation_required_before_purchase"] is True
    assert cost["exact_selected_database_flavor_revalidation_required_before_purchase"] is True
    assert cost["database_reference_configuration_is_provider_documented_minimum_not_capacity_guarantee"] is True
    assert cost["estimate_is_not_purchase_quote"] is True


def test_managed_external_waf_is_not_silently_added_to_base_cost() -> None:
    recommendation = _payload()["recommendation"]
    assert recommendation["initial_managed_external_waf"] == (
        "DEFERRED_PENDING_COST_CAPACITY_AND_CERTIFICATE_CUSTODY_REVIEW"
    )
    assert recommendation["initial_edge_abuse_controls"] == (
        "NGINX_PLUS_APPLICATION_RATE_LIMIT_HOST_CSRF_ORIGIN_SESSION_"
        "AND_SECURITY_HEADER_CONTROLS"
    )


def test_money_and_broker_authority_remain_fail_closed() -> None:
    payload = _payload()
    safety = payload["broker_and_money_safety"]
    activation = payload["activation"]

    assert safety["t_invest_public_connector"] == "FAIL_CLOSED_PENDING_BROKER_TERMS_PERMISSION"
    assert safety["broker_credentials"] == "TENANT_SCOPED_ONLY"
    assert safety["broker_write_authority_added"] is False
    assert safety["trading_methods"] is False
    assert safety["real_trading_enabled"] is False
    assert safety["transfer_withdrawal_allowed"] is False
    assert safety["protected_v9_rollback"] is True
    assert safety["app_entrypoint"] == "app:app"
    assert activation["cloudflare_product_authentication_allowed"] is False
    assert activation["telegram_vk_product_authentication_required"] is True


def test_service_selection_still_forbids_provider_apply() -> None:
    selection = SERVICE_SELECTION.read_text(encoding="utf-8")
    decision = DECISION.read_text(encoding="utf-8")
    assert "NO PROVIDER APPLY AUTHORIZED" in selection
    assert "OWNER COST APPROVAL REQUIRED BEFORE PROVIDER APPLY" in decision
    assert "provider_apply_authorized=false" in decision
    assert "PUBLIC_MULTI_USER_ENABLED=false" in decision
