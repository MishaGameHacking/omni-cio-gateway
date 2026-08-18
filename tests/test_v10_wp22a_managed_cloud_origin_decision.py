from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/architecture/V10_WP22A_MANAGED_CLOUD_ORIGIN_CONTRACT.json"
DECISION = ROOT / "docs/architecture/V10_WP22A_MANAGED_CLOUD_ORIGIN_DECISION.md"
SERVICE_SELECTION = ROOT / "docs/architecture/V10_WP22A_SERVICE_SELECTION.md"
COST_POLICY = ROOT / "docs/architecture/V10_FREE_FIRST_COST_DISCIPLINE.md"


def _payload() -> dict[str, Any]:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_selection_is_source_only_and_not_apply_authority() -> None:
    payload = _payload()
    assert payload["status"] == (
        "RECOMMENDED_CLOUD_RU_PRODUCTION_BOUNDARY_FREE_FIRST_PENDING_OWNER_COST_APPROVAL"
    )
    assert payload["owning_package"] == "WP22A"
    assert payload["phase"] == "SERVICE_HOSTING_ARCHITECTURE_DECISION"
    assert payload["accepted_base_main_binding"] == "PR_BASE_REF_VERIFIED_BY_GITHUB"

    cost = payload["cost_strategy"]
    assert cost["current_authorized_recurring_budget_rub"] == 0
    assert cost["provider_apply_authorized"] is False
    assert cost["automatic_paid_overage_allowed"] is False

    activation = payload["activation"]
    assert activation["public_multi_user_enabled"] is False
    assert activation["provider_resources_created"] is False
    assert activation["provider_credentials_allowed_in_pull_request"] is False
    assert activation["wp23_locked"] is True


def test_phase1_selects_managed_cloud_origin_and_security_boundaries() -> None:
    payload = _payload()
    boundary = payload["production_boundary"]
    stage2 = payload["deployment_ladder"]["stage_2"]

    assert boundary["selected_managed_cloud_origin_provider"] == "CLOUD_RU_EVOLUTION"
    assert boundary["selected_primary_region_family"] == "RUSSIA"
    assert boundary["ordinary_browser_public_https_required"] is True
    assert (
        boundary["owner_home_or_lenovo_production_availability_dependency_allowed"]
        is False
    )
    assert boundary["selected_initial_public_edge"] == (
        "DIRECT_EVOLUTION_PUBLIC_IP_WITH_SECURITY_GROUPS_AND_EVOLUTION_DNS"
    )
    assert (
        boundary["selected_tls_boundary"]
        == "EVOLUTION_CERTIFICATE_MANAGER_LETS_ENCRYPT"
    )
    assert boundary["selected_primary_database_boundary"] == (
        "EVOLUTION_MANAGED_POSTGRESQL_PRIVATE_VPC"
    )
    assert boundary["selected_tenant_credential_boundary"].startswith("EVOLUTION_SCMS")
    assert boundary["selected_key_boundary"] == "EVOLUTION_KMS"
    assert boundary["database_public_ip_allowed"] is False
    assert boundary["provider_apply_authorized"] is False

    assert stage2["provider"] == "CLOUD_RU_EVOLUTION"
    assert stage2["provider_selection_is_binding"] is True
    assert stage2["exact_sku_selection_deferred_until_fresh_revalidation"] is True
    assert stage2["database"] == "EVOLUTION_MANAGED_POSTGRESQL_STANDARD_PRIVATE_VPC"
    assert stage2["credential_vault"] == "EVOLUTION_SCMS"
    assert stage2["key_management"] == "EVOLUTION_KMS"


def test_free_first_lowest_cost_safe_policy_is_binding() -> None:
    payload = _payload()
    policy = payload["cost_strategy"]

    assert policy["policy"] == "FREE_FIRST_LOWEST_COST_SAFE"
    assert policy["prefer_already_owned_or_free_before_paid"]
    assert policy["free_service_must_meet_hard_security_legal_recovery_requirements"]
    assert policy[
        "lowest_cost_paid_option_used_only_when_no_safe_free_option_meets_the_gate"
    ]
    assert policy["multiple_free_or_low_cost_services_allowed"]
    assert policy["multi_provider_composition_requires_bounded_failure_domains"]
    assert policy[
        "multi_provider_composition_requires_portable_source_controlled_interfaces"
    ]
    assert policy[
        "do_not_fragment_identity_session_primary_database_or_raw_credential_custody_for_marginal_savings"
    ]
    assert policy["code_can_compensate_for_noncritical_service_limitations"]
    assert policy[
        "code_cannot_compensate_for_missing_legal_permission_data_localization_credential_custody_or_recovery"
    ]
    assert policy[
        "owner_product_experience_required_before_new_recurring_paid_commitment"
    ]

    text = COST_POLICY.read_text(encoding="utf-8")
    assert "already owned / open source / safe free tier / grant / bonus" in text
    assert "lowest-cost safe paid option" in text
    assert (
        "A cheaper service that cannot satisfy a hard gate is **not** the better option"
        in text
    )
    assert "A required architecture decision still gets made" in text


def test_cost_ladder_keeps_zero_recurring_target_until_measured_need() -> None:
    ladder = _payload()["deployment_ladder"]

    stage0 = ladder["stage_0"]
    assert stage0["name"] == "ZERO_RECURRING_PROOF_OF_PRODUCT"
    assert stage0["target_owner_out_of_pocket_rub_per_month"] == 0
    assert stage0["real_public_user_registration_allowed"] is False
    assert stage0["real_tenant_private_data_allowed"] is False
    assert stage0["broker_credentials_allowed"] is False
    assert stage0["t_invest_public_connector_allowed"] is False

    stage1 = ladder["stage_1"]
    assert stage1["preferred_provider"] == "CLOUD_RU_EVOLUTION"
    assert stage1["target_owner_out_of_pocket_rub_per_month"] == 0
    assert stage1["hard_spend_cap_required"]
    assert stage1["automatic_paid_overage_allowed"] is False
    assert stage1["production_claim_allowed"] is False
    assert stage1["real_tenant_private_state_allowed"] is False

    stage2 = ladder["stage_2"]
    assert stage2["provider"] == "CLOUD_RU_EVOLUTION"
    assert stage2["monthly_cost_target"] == (
        "LOWEST_COST_CLOUD_RU_TOPOLOGY_THAT_MEETS_ALL_HARD_REQUIREMENTS"
    )
    assert stage2["owner_cost_approval_required"]
    assert stage2["measured_load_required_before_sizing"]

    stage3 = ladder["stage_3"]
    assert stage3["provider"] == "CLOUD_RU_EVOLUTION"
    assert stage3["is_initial_spend_commitment"] is False
    assert stage3["activation_requires_measured_sla_load_failure_budget_or_user_demand"]


def test_free_and_bonus_snapshot_is_explicitly_mutable_and_no_overage() -> None:
    snapshot = _payload()["free_and_bonus_snapshot"]
    assert snapshot["snapshot_date"] == "2026-08-18"
    assert snapshot["mutable_facts_must_be_revalidated_before_use"]

    cloud = snapshot["cloud_ru_evolution"]
    assert cloud["container_services_free_vcpu_hours_per_month"] == 25
    assert cloud["container_services_free_ram_gb_hours_per_month"] == 50
    assert cloud["object_storage_free_gb_standard"] == 15
    assert cloud["dns_free_requests_per_month"] == 1_000_000
    assert cloud["card_link_bonus_rub"] == 4000
    assert cloud["new_free_vm_creation_assumed_available_for_new_account_now"] is False
    assert cloud["new_free_vm_registration_cutoff_date"] == "2026-06-30"
    assert cloud["free_tier_overage_is_billable"] is True
    assert cloud["free_tier_is_not_production_sla_evidence"]

    cost = _payload()["cost_boundary"]
    assert cost["current_owner_out_of_pocket_target_rub_per_month"] == 0
    assert cost["hard_spend_boundary_required_before_free_tier_apply"] is True
    assert cost["automatic_paid_overage_allowed"] is False


def test_free_preview_cannot_receive_real_private_or_broker_state() -> None:
    ladder = _payload()["deployment_ladder"]
    assert ladder["stage_0"]["optional_cloud_preview"].endswith(
        "FREE_TIER_SYNTHETIC_NON_PRIVATE_ONLY"
    )
    assert ladder["stage_1"]["real_tenant_private_state_allowed"] is False
    assert ladder["stage_0"]["broker_credentials_allowed"] is False


def test_cloud_ru_selection_reasoning_prefers_total_security_boundary() -> None:
    why = _payload()["selection_reasoning"]

    assert why[
        "cloud_ru_selected_because_hard_boundaries_are_available_in_one_russia_provider"
    ]
    assert why["native_managed_postgresql_private_network"]
    assert why["native_scms_service_fee_free"]
    assert why["native_kms_service_fee_free"]
    assert why["native_certificate_manager_service_fee_free"]
    assert why["native_object_storage_free_tier_available"]
    assert why[
        "timeweb_raw_compute_can_be_cheaper_but_equivalent_managed_credential_boundary_not_selected"
    ]
    assert why[
        "timeweb_vault_path_requires_kubernetes_or_self_managed_operational_boundary"
    ]
    assert why[
        "single_provider_security_core_preferred_over_cross_provider_credential_bootstrap_for_marginal_compute_savings"
    ]
    assert why["ha_spend_deferred_until_measured_need"]


def test_cloudflare_primary_edge_remains_rejected() -> None:
    payload = _payload()
    boundary = payload["production_boundary"]
    candidate = payload["candidate_evaluation"]["CLOUDFLARE_PRIMARY_EDGE"]

    assert boundary["cloudflare_primary_or_sole_production_edge_allowed"] is False
    assert candidate["result"] == "REJECT_PRIMARY_OR_SOLE_RUSSIAN_USER_PRODUCTION_EDGE"

    decision = DECISION.read_text(encoding="utf-8")
    assert (
        "rejected as the primary or sole normal Russian USER production edge"
        in decision
    )


def test_ha_cloud_ru_topology_is_reference_not_startup_commitment() -> None:
    payload = _payload()
    stage3 = payload["deployment_ladder"]["stage_3"]
    cost = payload["cost_boundary"]

    assert stage3["provider"] == "CLOUD_RU_EVOLUTION"
    assert stage3["reference_topology"] == (
        "TWO_APP_VM_MULTI_AZ_PLUS_GEOREDUNDANT_NLB_PLUS_BUSINESS_POSTGRESQL_CLUSTER_HA_THREE_NODE_MULTI_AZ"
    )
    assert stage3["reference_monthly_rub_approx"] == 24508.8311904
    assert stage3["is_initial_spend_commitment"] is False
    assert (
        cost["cloud_ru_reference_ha_scale_up_stack_monthly_rub_approx"]
        == 24508.8311904
    )
    assert cost["ha_reference_is_not_initial_purchase_quote_or_commitment"]


def test_paid_pilot_provider_is_selected_but_sku_and_apply_are_deferred() -> None:
    payload = _payload()
    stage2 = payload["deployment_ladder"]["stage_2"]
    cost = payload["cost_boundary"]

    assert stage2["provider"] == "CLOUD_RU_EVOLUTION"
    assert stage2["exact_sku_selection_deferred_until_fresh_revalidation"] is True
    assert cost["new_recurring_paid_commitment_required_now"] is False
    assert cost["current_owner_out_of_pocket_target_rub_per_month"] == 0
    assert cost["provider_apply_authorized"] is False
    assert cost["stage_2_exact_total_monthly_cost_unset_until_sku_revalidation"] is True

    decision = DECISION.read_text(encoding="utf-8")
    selection = SERVICE_SELECTION.read_text(encoding="utf-8")
    assert "Selected provider: **Cloud.ru Evolution**" in decision
    assert (
        "Cloud.ru Evolution is the selected production managed-cloud provider/boundary"
        in selection
    )


def test_candidate_ranking_preserves_fallbacks_without_fragmenting_security_core() -> (
    None
):
    candidates = _payload()["candidate_evaluation"]

    assert candidates["CLOUD_RU_EVOLUTION"]["result"] == (
        "SELECTED_PRODUCTION_ORIGIN_AND_FREE_PREVIEW_PROVIDER"
    )
    assert (
        candidates["YANDEX_CLOUD"]["result"] == "STRONG_MANAGED_FALLBACK_NOT_SELECTED"
    )
    assert candidates["TIMEWEB_CLOUD"]["result"] == (
        "LOW_COST_COMPUTE_FALLBACK_NOT_SELECTED_FOR_SECURITY_CORE"
    )
    assert candidates["RENDER"]["result"] == (
        "SYNTHETIC_PREVIEW_ONLY_NOT_RUSSIA_PRIVATE_DATA_PLANE"
    )
    assert "SCMS_AND_KMS" in candidates["CLOUD_RU_EVOLUTION"]["strengths"]
    assert (
        "DOCUMENTED_VAULT_PATH_IS_KUBERNETES_ADDON_WITH_SELF_MANAGED_INITIALIZATION_AND_HA_OPERATIONS"
        in candidates["TIMEWEB_CLOUD"]["known_tradeoffs"]
    )


def test_provider_automation_is_fail_closed() -> None:
    automation = _payload()["automation_boundary"]
    assert automation["terraform_preferred_for_supported_cloud_ru_resources"]
    assert automation[
        "public_api_fallback_allowed_only_when_reviewed_terraform_resource_is_not_accepted"
    ]
    assert automation["nlb_exact_provider_schema_acceptance_required_before_apply"]
    assert automation["provider_identity_cannot_be_product_identity"]
    assert automation["provider_credentials_allowed_in_pull_request"] is False
    assert automation["privileged_apply_only_from_reviewed_accepted_main_boundary"]


def test_legal_and_data_boundaries_are_price_independent() -> None:
    legal = _payload()["legal_and_data_boundary"]
    assert legal["production_legal_signoff_required"]
    assert legal["russian_federal_law_152_fz_localization_gate"]
    assert (
        legal[
            "primary_identity_session_tenant_personal_data_outside_russia_allowed_by_this_contract"
        ]
        is False
    )
    assert (
        legal["cross_border_processing_allowed_without_separate_legal_review"] is False
    )
    assert legal[
        "free_or_discounted_service_does_not_waive_legal_security_or_broker_gates"
    ]


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
    assert activation["telegram_vk_product_authentication_required"] is True


def test_service_selection_preserves_inherited_markers_and_new_authority() -> None:
    selection = SERVICE_SELECTION.read_text(encoding="utf-8")
    for marker in (
        "public HTTPS hostname",
        "public TLS/certificate lifecycle",
        "Production-origin provider selection is not yet made",
        "No provider mutation is authorized",
        "managed-cloud production origin independent of OWNER home infrastructure",
        "A tunnel whose sole production origin is the PROJECT OWNER's home Lenovo/network is forbidden",
        "NO PROVIDER APPLY AUTHORIZED",
        "Cloud.ru Evolution is the selected production managed-cloud provider/boundary",
    ):
        assert marker in selection

    decision = DECISION.read_text(encoding="utf-8")
    assert "OWNER COST APPROVAL REQUIRED BEFORE ANY PAID APPLY" in decision
    assert "provider_apply_authorized=false" in decision
    assert "PUBLIC_MULTI_USER_ENABLED=false" in decision
    assert (
        "Selected managed-cloud production origin/provider boundary: Cloud.ru Evolution"
        in decision
    )
