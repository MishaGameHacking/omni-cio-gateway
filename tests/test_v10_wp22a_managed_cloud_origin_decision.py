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
    assert payload["status"] == "RECOMMENDED_STAGED_FREE_FIRST_PENDING_OWNER_COST_APPROVAL"
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


def test_free_first_lowest_cost_safe_policy_is_binding() -> None:
    payload = _payload()
    policy = payload["cost_strategy"]

    assert policy["policy"] == "FREE_FIRST_LOWEST_COST_SAFE"
    assert policy["prefer_already_owned_or_free_before_paid"]
    assert policy["free_service_must_meet_hard_security_legal_recovery_requirements"]
    assert policy["lowest_cost_paid_option_used_only_when_no_safe_free_option_meets_the_gate"]
    assert policy["multiple_free_or_low_cost_services_allowed"]
    assert policy["multi_provider_composition_requires_bounded_failure_domains"]
    assert policy["multi_provider_composition_requires_portable_source_controlled_interfaces"]
    assert policy[
        "do_not_fragment_identity_session_primary_database_or_raw_credential_custody_for_marginal_savings"
    ]
    assert policy["code_can_compensate_for_noncritical_service_limitations"]
    assert policy[
        "code_cannot_compensate_for_missing_legal_permission_data_localization_credential_custody_or_recovery"
    ]
    assert policy["owner_product_experience_required_before_new_recurring_paid_commitment"]

    text = COST_POLICY.read_text(encoding="utf-8")
    assert "already owned / open source / safe free tier / grant / bonus" in text
    assert "lowest-cost safe paid option" in text
    assert "A cheaper service that cannot satisfy a hard gate is **not** the better option" in text


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
    assert stage1["target_owner_out_of_pocket_rub_per_month"] == 0
    assert stage1["hard_spend_cap_required"]
    assert stage1["automatic_paid_overage_allowed"] is False
    assert stage1["production_claim_allowed"] is False

    stage2 = ladder["stage_2"]
    assert stage2["provider"] == "UNSELECTED_UNTIL_FRESH_REVALIDATION"
    assert stage2["monthly_cost_target"] == "LOWEST_COST_OPTION_THAT_MEETS_ALL_HARD_REQUIREMENTS"
    assert stage2["owner_cost_approval_required"]
    assert stage2["measured_load_required_before_sizing"]

    stage3 = ladder["stage_3"]
    assert stage3["is_initial_spend_commitment"] is False
    assert stage3["activation_requires_measured_sla_load_failure_budget_or_user_demand"]


def test_free_and_bonus_snapshot_is_explicitly_mutable() -> None:
    snapshot = _payload()["free_and_bonus_snapshot"]
    assert snapshot["snapshot_date"] == "2026-08-18"
    assert snapshot["mutable_facts_must_be_revalidated_before_use"]

    cloud = snapshot["cloud_ru_evolution"]
    assert cloud["container_services_free_vcpu_hours_per_month"] == 25
    assert cloud["container_services_free_ram_gb_hours_per_month"] == 50
    assert cloud["object_storage_free_gb_standard"] == 15
    assert cloud["card_link_bonus_rub"] == 4000
    assert cloud["new_free_vm_creation_assumed_available_for_new_account_now"] is False
    assert cloud["new_free_vm_registration_cutoff_date"] == "2026-06-30"
    assert cloud["free_tier_is_not_production_sla_evidence"]

    yandex = snapshot["yandex_cloud"]
    assert yandex["new_customer_grant_rub_min_for_ru_resident"] == 4000
    assert yandex["grant_valid_days"] == 60
    assert yandex["grant_is_not_permanent_free_production"]

    timeweb = snapshot["timeweb_cloud"]
    assert timeweb["vps_hourly_billing"]
    assert timeweb["minimum_payment_rub"] == 50
    assert timeweb["support_test_bonus_available"]
    assert timeweb["grant_or_test_bonus_is_not_permanent_free_production"]


def test_free_preview_cannot_receive_real_private_or_broker_state() -> None:
    rec = _payload()["recommendation"]
    assert rec["container_apps_synthetic_preview_allowed"]
    assert rec["container_apps_primary_real_user_runtime_allowed"] is False
    assert rec["container_apps_real_tenant_private_state_allowed"] is False
    assert rec["credential_vault_for_real_tenant_credentials"] == (
        "REQUIRES_REVIEWED_ENCRYPTED_TENANT_SCOPED_BOUNDARY"
    )
    assert rec["database_public_ip_allowed"] is False


def test_cloudflare_primary_edge_remains_rejected() -> None:
    payload = _payload()
    rec = payload["recommendation"]
    candidate = payload["candidate_evaluation"]["CLOUDFLARE_PRIMARY_EDGE"]

    assert rec["cloudflare_primary_or_sole_production_edge_allowed"] is False
    assert "RUSSIAN_ISP_THROTTLING" in rec["cloudflare_primary_edge_rejection_reason"]
    assert candidate["result"] == "REJECT_PRIMARY_OR_SOLE_RUSSIAN_USER_PRODUCTION_EDGE"

    decision = DECISION.read_text(encoding="utf-8")
    assert "rejected as the primary or sole normal Russian USER production edge" in decision


def test_ha_cloud_ru_topology_is_reference_not_startup_commitment() -> None:
    payload = _payload()
    rec = payload["recommendation"]
    stage3 = payload["deployment_ladder"]["stage_3"]
    cost = payload["cost_boundary"]

    assert rec["preferred_ha_scale_up_provider"] == "CLOUD_RU_EVOLUTION"
    assert rec["ha_reference_runtime_topology"] == (
        "TWO_VM_ACTIVE_ACTIVE_DISTINCT_AZ_BEHIND_GEOREDUNDANT_EVOLUTION_NLB"
    )
    assert rec["ha_reference_database_mode"] == "BUSINESS"
    assert rec["ha_reference_database_topology"] == "CLUSTER_HA_THREE_NODE_MULTI_AZ"
    assert rec["ha_reference_database_primary_nodes"] == 1
    assert rec["ha_reference_database_standby_nodes"] == 2
    assert rec["ha_reference_database_availability_zones"] == 3

    assert stage3["reference_monthly_rub_approx"] == 24508.8311904
    assert stage3["is_initial_spend_commitment"] is False
    assert cost["cloud_ru_reference_ha_scale_up_stack_monthly_rub_approx"] == 24508.8311904
    assert cost["ha_reference_is_not_initial_purchase_quote_or_commitment"]


def test_paid_pilot_provider_is_deliberately_unselected() -> None:
    payload = _payload()
    rec = payload["recommendation"]
    assert rec["paid_pilot_provider"] == "UNSELECTED_UNTIL_REVALIDATION"
    assert payload["cost_boundary"]["new_recurring_paid_commitment_required_now"] is False
    assert payload["cost_boundary"]["current_owner_out_of_pocket_target_rub_per_month"] == 0

    decision = DECISION.read_text(encoding="utf-8")
    selection = SERVICE_SELECTION.read_text(encoding="utf-8")
    assert "paid-pilot provider is intentionally **UNSELECTED**" in decision
    assert "Provider/topology remains **UNSELECTED**" in selection


def test_nlb_automation_documentation_conflict_fails_closed() -> None:
    rec = _payload()["recommendation"]
    assert rec["public_load_balancer_automation"] == (
        "PINNED_TERRAFORM_PROVIDER_IF_NLB_RESOURCE_ACCEPTANCE_PASSES_"
        "ELSE_CLOUD_RU_PUBLIC_API"
    )
    assert rec["public_load_balancer_terraform_support_state"] == (
        "OFFICIAL_DOCS_CONFLICT_REQUIRES_PINNED_PROVIDER_ACCEPTANCE"
    )
    assert rec["public_load_balancer_apply_blocked_until_automation_path_validated"]


def test_legal_and_data_boundaries_are_price_independent() -> None:
    legal = _payload()["legal_and_data_boundary"]
    assert legal["production_legal_signoff_required"]
    assert legal["russian_federal_law_152_fz_localization_gate"]
    assert legal[
        "primary_identity_session_tenant_personal_data_outside_russia_allowed_by_this_contract"
    ] is False
    assert legal["cross_border_processing_allowed_without_separate_legal_review"] is False
    assert legal["free_or_discounted_service_does_not_waive_legal_security_or_broker_gates"]


def test_candidate_ranking_keeps_free_and_low_cost_fallbacks() -> None:
    candidates = _payload()["candidate_evaluation"]
    assert candidates["CLOUD_RU_EVOLUTION"]["result"] == (
        "PREFERRED_FREE_PREVIEW_AND_HA_SCALE_UP_CANDIDATE"
    )
    assert candidates["YANDEX_CLOUD"]["result"] == "GRANT_BACKED_SECURITY_STRONG_ALTERNATIVE"
    assert candidates["TIMEWEB_CLOUD"]["result"] == "LOW_COST_TEST_AND_PILOT_ALTERNATIVE"
    assert candidates["RENDER"]["result"] == (
        "SYNTHETIC_PREVIEW_ONLY_NOT_RUSSIA_PRIVATE_DATA_PLANE"
    )
    assert "SCMS_AND_KMS" in candidates["CLOUD_RU_EVOLUTION"]["strengths"]
    assert (
        "FULL_TENANT_CREDENTIAL_CUSTODY_BOUNDARY_REQUIRES_SEPARATE_REVIEW"
        in candidates["TIMEWEB_CLOUD"]["known_tradeoffs"]
    )


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


def test_service_selection_preserves_inherited_source_markers() -> None:
    selection = SERVICE_SELECTION.read_text(encoding="utf-8")
    for marker in (
        "public HTTPS hostname",
        "public TLS/certificate lifecycle",
        "Production-origin provider selection is not yet made",
        "No provider mutation is authorized",
        "managed-cloud production origin independent of OWNER home infrastructure",
        "A tunnel whose sole production origin is the PROJECT OWNER's home Lenovo/network is forbidden",
        "NO PROVIDER APPLY AUTHORIZED",
    ):
        assert marker in selection

    decision = DECISION.read_text(encoding="utf-8")
    assert "OWNER COST APPROVAL REQUIRED BEFORE PAID PROVIDER APPLY" in decision
    assert "provider_apply_authorized=false" in decision
    assert "PUBLIC_MULTI_USER_ENABLED=false" in decision
