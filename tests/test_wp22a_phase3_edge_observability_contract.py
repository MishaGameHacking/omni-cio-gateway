from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "infrastructure" / "cloudru" / "wp22a" / "edge-observability-contract.json"


def _payload() -> dict[str, object]:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_edge_observability_contract_preserves_phase3_locks() -> None:
    authority = _payload()["authority"]

    assert authority["provider"] == "Cloud.ru Evolution"
    assert authority["source_only"] is True
    assert authority["provider_apply_authorized"] is False
    assert authority["public_ingress_enabled"] is False
    assert authority["authorized_recurring_rub"] == 0
    assert authority["public_multi_user_enabled"] is False
    assert authority["trading_methods_enabled"] is False
    assert authority["real_trading_enabled"] is False
    assert authority["protected_v9_entrypoint"] == "app:app"
    assert authority["wp23_unlocked"] is False


def test_edge_trust_is_fail_closed_before_public_activation() -> None:
    edge = _payload()["edge_trust"]

    assert edge["https_required_before_public_activation"] is True
    assert edge["trusted_proxy_chain_required"] is True
    assert edge["forwarded_proto_trust_allowlist_required"] is True
    assert edge["host_allowlist_required"] is True
    assert edge["hsts_required"] is True
    assert edge["csrf_origin_validation_required"] is True
    assert edge["cors_default"] == "deny"
    assert edge["private_response_cache_default"] == "no-store"
    assert edge["engineering_identity_product_bypass_allowed"] is False
    assert edge["direct_origin_public_access_allowed"] is False


def test_observability_forbids_private_or_secret_logging() -> None:
    observability = _payload()["observability"]

    assert observability["tenant_payload_logging_allowed"] is False
    assert observability["broker_credential_logging_allowed"] is False
    assert observability["session_identifier_logging_allowed"] is False
    assert observability["private_portfolio_logging_allowed"] is False
    assert observability["sanitized_correlation_id_required"] is True
    assert observability["dependency_degradation_must_preserve_trust_boundary"] is True
    assert observability["required_health_domains"] == [
        "application",
        "database",
        "cloud_provider",
        "identity_provider",
        "external_broker",
    ]
    assert observability["runtime_states"] == [
        "READY",
        "PARTIAL",
        "STALE",
        "DEGRADED",
        "BLOCKED",
        "ERROR",
        "OFFLINE",
        "RECOVERING",
        "OWNER_ACTION_REQUIRED",
    ]


def test_capacity_and_cost_remain_bounded_and_zero_rub_first() -> None:
    capacity = _payload()["capacity_and_cost"]

    assert capacity["registration_enabled"] is False
    assert capacity["public_rate_limits_required_before_activation"] is True
    assert capacity["bounded_request_body_required"] is True
    assert capacity["bounded_concurrency_required"] is True
    assert capacity["bounded_background_work_required"] is True
    assert capacity["cost_alerting_required_before_paid_activation"] is True
    assert capacity["automatic_paid_scale_up_allowed"] is False
    assert capacity["free_bonus_stage_first"] is True
    assert capacity["owner_cost_approval_required_before_recurring_spend"] is True


def test_incident_boundary_does_not_depend_on_owner_home_infrastructure() -> None:
    incident = _payload()["incident_and_recovery"]

    assert incident["last_accepted_release_rollback_required"] is True
    assert incident["provider_outage_distinct_from_application_error"] is True
    assert incident["broker_outage_distinct_from_application_error"] is True
    assert incident["lenovo_required_for_public_availability"] is False
    assert incident["owner_home_network_required_for_public_availability"] is False
