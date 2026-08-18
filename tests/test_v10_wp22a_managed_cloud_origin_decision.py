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
    rec = payload["recommendation"]
    why = payload["selection_reasoning"]

    assert rec["provider"] == "CLOUD_RU_EVOLUTION"
    assert rec["runtime"] == "EVOLUTION_VM"
    assert rec["runtime_topology"] == (
        "TWO_VM_ACTIVE_ACTIVE_DISTINCT_AZ_BEHIND_GEOREDUNDANT_EVOLUTION_NLB"
    )
    assert rec["runtime_region_requirement"] == "RUSSIA"
    assert rec["runtime_distinct_availability_zones_required"] is True
    assert rec["public_load_balancer_selected_availability_zones"] == 2
    assert rec["public_load_balancer_resource_units_per_selected_az"] == 1
    assert rec["public_load_balancer_total_initial_resource_units"] == 2
    assert rec["public_load_balancer_provider_min_resource_units_per_az"] == 1
    assert rec["public_load_balancer_georedundant_placement_required"] is True
    assert why["runtime_cross_az_placement_required_for_initial_public_production"]
    assert why["nlb_cross_az_placement_required_for_initial_public_production"]
    assert why["nlb_total_two_resource_units_selected_as_one_per_two_az"]


def test_nlb_automation_documentation_conflict_fails_closed() -> None:
    payload = _payload()
    rec = payload["recommendation"]
    why = payload["selection_reasoning"]

    assert rec["public_load_balancer_automation"] == (
        "PINNED_TERRAFORM_PROVIDER_IF_NLB_RESOURCE_ACCEPTANCE_PASSES_"
        "ELSE_CLOUD_RU_PUBLIC_API"
    )
    assert rec["public_load_balancer_terraform_support_state"] == (
        "OFFICIAL_DOCS_CONFLICT_REQUIRES_PINNED_PROVIDER_ACCEPTANCE"
    )
    assert rec["public_load_balancer_service_limitations_says_terraform_unsupported"]
    assert rec["public_load_balancer_terraform_resource_reference_present"]
    assert rec["public_load_balancer_public_api_supported"]
    assert rec["public_load_balancer_apply_blocked_until_automation_path_validated"]
    assert why["nlb_automation_must_be_verified_against_pinned_provider_before_apply"]
    assert why["terraform_only_provider_automation_required"] is False
    assert why["provider_documentation_conflict_must_fail_closed"]


def test_cloudflare_primary_edge_is_rejected() -> None:
    payload = _payload()
    rec = payload["recommendation"]
    candidate = payload["candidate_evaluation"]["CLOUDFLARE_PRIMARY_EDGE"]

    assert rec["cloudflare_primary_or_sole_production_edge_allowed"] is False
    assert rec["cloudflare_primary_edge_rejection_reason"] == (
        "CLOUDFLARE_2026_SUPPORT_DOCS_CONFIRM_SYSTEMATIC_RUSSIA_ISP_"
        "THROTTLING_MAKING_RUSSIAN_USER_ACCESS_UNRELIABLE"
    )
    assert rec["cloudflare_optional_secondary_use"] == (
        "DEFERRED_REQUIRES_SEPARATE_REACHABILITY_DATA_LOCALIZATION_AND_COST_REVIEW"
    )
    assert candidate["result"] == (
        "REJECT_PRIMARY_OR_SOLE_RUSSIAN_USER_PRODUCTION_EDGE"
    )
    assert "not** the primary or sole production edge" in DECISION.read_text(
        encoding="utf-8"
    )


def test_database_uses_provider_recommended_cluster_ha() -> None:
    payload = _payload()
    rec = payload["recommendation"]
    why = payload["selection_reasoning"]

    assert rec["database"] == "CLOUD_RU_MANAGED_POSTGRESQL_PRIVATE_IP"
    assert rec["database_mode"] == "BUSINESS"
    assert rec["database_topology"] == "CLUSTER_HA_THREE_NODE_MULTI_AZ"
    assert rec["database_primary_nodes"] == 1
    assert rec["database_standby_nodes"] == 2
    assert rec["database_availability_zones"] == 3
    assert rec["database_multi_az_required_for_initial_production"]
    assert rec["database_provider_recommended_production_topology_used"]
    assert rec["database_standard_mode_allowed_for_initial_public_production"] is False
    assert (
        rec[
            "database_two_node_primary_standby_allowed_as_initial_public_production_baseline"
        ]
        is False
    )
    assert rec["database_public_ip_allowed"] is False
    assert rec["network"] == (
        "CLOUD_RU_EVOLUTION_VPC_PRIVATE_SUBNETS_ACROSS_REQUIRED_AZS"
    )
    assert why["database_business_mode_required_for_initial_public_production"]
    assert why["database_three_node_multi_az_required_for_initial_public_production"]
    assert why["database_two_node_topology_is_not_initial_public_production_recommendation"]
    assert why["database_standard_mode_is_not_initial_public_production_recommendation"]

    decision = DECISION.read_text(encoding="utf-8")
    selection = SERVICE_SELECTION.read_text(encoding="utf-8")
    assert "Business Cluster HA" in decision
    assert "Primary + 2 Standby" in decision
    assert "Multi-AZ across three availability zones" in decision
    assert "Business Cluster HA" in selection
    assert "Primary + 2 Standby / 3 AZ" in selection


def test_private_secret_and_legal_boundaries_remain_fail_closed() -> None:
    payload = _payload()
    rec = payload["recommendation"]
    why = payload["selection_reasoning"]
    legal = payload["legal_and_data_boundary"]

    assert rec["secret_store"] == "CLOUD_RU_SECRET_MANAGEMENT"
    assert rec["key_management"] == "CLOUD_RU_KEY_MANAGEMENT_OR_REVIEWED_SYSTEM_KEY"
    assert rec["outbound_internet"] == "CLOUD_RU_EVOLUTION_SNAT"
    assert why["managed_postgresql_private_connectivity_required"]
    assert why["managed_secret_store_required_for_tenant_broker_credentials"]
    assert why["owner_home_availability_dependency_allowed"] is False
    assert legal["russian_federal_law_152_fz_article_18_part_5_localization_gate"]
    assert (
        legal[
            "primary_identity_session_tenant_personal_data_outside_russia_allowed_by_this_contract"
        ]
        is False
    )
    assert legal["cross_border_processing_allowed_without_separate_legal_review"] is False
    assert legal["production_legal_signoff_required"]
    assert legal["provider_compliance_does_not_replace_omni_cio_operator_obligations"]


def test_container_apps_and_external_waf_stay_bounded() -> None:
    rec = _payload()["recommendation"]
    assert rec["container_apps_primary_runtime_allowed"] is False
    assert rec["container_apps_rejection_reason"] == (
        "OFFICIAL_CLOUD_RU_DOCS_STATE_NO_MANAGED_POSTGRESQL_CONNECTIVITY_"
        "AND_PUBLIC_DB_PORT_IS_UNSAFE"
    )
    assert rec["initial_managed_external_waf"] == (
        "DEFERRED_PENDING_COST_CAPACITY_AND_CERTIFICATE_CUSTODY_REVIEW"
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

    assert (
        "BUSINESS_THREE_NODE_MULTI_AZ_COSTS_MATERIALLY_MORE_THAN_STANDARD_OR_TWO_NODE"
        in cloud_ru["known_tradeoffs"]
    )
    assert candidates["TIMEWEB_CLOUD"]["result"] == "FALLBACK_LOWER_COST"
    assert candidates["YANDEX_CLOUD"]["result"] == (
        "SECURITY_STRONGER_HIGHER_COST_ALTERNATIVE"
    )
    assert candidates["RENDER"]["result"] == "REJECT_PRIMARY_PRODUCTION_DATA_PLANE"


def test_reference_cost_matches_production_topology() -> None:
    cost = _payload()["cost_boundary"]
    pg_node = "cloud_ru_reference_pg_business_node_4vcpu_8gb_40gb_monthly_rub_approx"
    pg_ha = (
        "cloud_ru_reference_pg_business_cluster_ha_multi_az_"
        "3x_4vcpu_8gb_40gb_monthly_rub_approx"
    )
    nlb = (
        "cloud_ru_reference_nlb_two_az_one_resource_unit_each_"
        "plus_public_ip_monthly_rub_approx"
    )

    assert cost[pg_node] == 7099.2288
    assert cost[pg_ha] == 21297.6864
    assert cost["cloud_ru_reference_two_runtime_vms_with_20gb_disks_monthly_rub_approx"] == 1722.9888
    assert cost[nlb] == 1305.8879904
    assert cost["cloud_ru_reference_public_dns_zone_30_days_monthly_rub_approx"] == 32.94
    assert cost["cloud_ru_certificate_manager_monthly_rub"] == 0
    assert cost["cloud_ru_reference_initial_stack_monthly_rub_approx"] == 24508.8311904
    assert cost["exact_selected_vm_price_revalidation_required_before_purchase"]
    assert cost["exact_selected_database_flavor_revalidation_required_before_purchase"]
    assert cost[
        "database_reference_configuration_is_provider_documented_minimum_not_capacity_guarantee"
    ]
    assert cost["estimate_is_not_purchase_quote"]


def test_money_and_broker_authority_remain_fail_closed() -> None:
    payload = _payload()
    safety = payload["broker_and_money_safety"]
    activation = payload["activation"]

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
    assert activation["cloudflare_product_authentication_allowed"] is False
    assert activation["telegram_vk_product_authentication_required"] is True


def test_service_selection_still_forbids_provider_apply() -> None:
    selection = SERVICE_SELECTION.read_text(encoding="utf-8")
    decision = DECISION.read_text(encoding="utf-8")
    assert "NO PROVIDER APPLY AUTHORIZED" in selection
    assert "OWNER COST APPROVAL REQUIRED BEFORE PROVIDER APPLY" in decision
    assert "provider_apply_authorized=false" in decision
    assert "PUBLIC_MULTI_USER_ENABLED=false" in decision
