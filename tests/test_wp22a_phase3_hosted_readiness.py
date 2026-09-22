from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from omni_cio.observability.hosted_readiness_v1 import (
    HostedReadinessContractError,
    aggregate_hosted_runtime_state,
    load_hosted_readiness_contract,
    validate_hosted_health_evidence,
    validate_hosted_readiness_contract,
)


NOW = datetime(2026, 8, 20, 21, 40, tzinfo=UTC)
_RELEASE_SHA = "".join(("912e3eee", "44f73d15", "d9a81186", "515957c1", "f3d6cbb8"))


def _contract() -> dict[str, object]:
    return load_hosted_readiness_contract()


def _evidence() -> dict[str, object]:
    return {
        "schema_version": "v10.wp22a.phase3.hosted-health-evidence.v1",
        "correlation_id": "00000000-0000-4000-8000-000000000001",
        "release_sha": _RELEASE_SHA,
        "checked_at_utc": "2026-08-20T21:40:00Z",
        "public_ingress_enabled": False,
        "migration_state_match": True,
        "runtime_acl_match": True,
        "tenant_boundary_match": True,
        "dependencies": [
            {
                "domain": "application",
                "state": "READY",
                "reason_code": "APPLICATION_READY",
            },
            {
                "domain": "cloud_provider",
                "state": "READY",
                "reason_code": "PROVIDER_READY",
            },
            {
                "domain": "database",
                "state": "READY",
                "reason_code": "DATABASE_READY",
            },
            {
                "domain": "product_auth",
                "state": "READY",
                "reason_code": "AUTH_READY",
            },
            {
                "domain": "broker_external",
                "state": "NOT_APPLICABLE",
                "reason_code": "BROKER_NOT_ACTIVATED",
            },
            {
                "domain": "recovery",
                "state": "READY",
                "reason_code": "RECOVERY_READY",
            },
        ],
    }


def _dependency(evidence: dict[str, object], domain: str) -> dict[str, object]:
    dependencies = evidence["dependencies"]
    assert isinstance(dependencies, list)
    item = next(
        candidate
        for candidate in dependencies
        if isinstance(candidate, dict) and candidate.get("domain") == domain
    )
    return item


def test_hosted_readiness_contract_path_is_fixed(tmp_path: Path) -> None:
    alternate = tmp_path / "hosted-readiness-contract.json"
    alternate.write_text("{}", encoding="utf-8")
    with pytest.raises(HostedReadinessContractError, match="CONTRACT_PATH_INVALID"):
        load_hosted_readiness_contract(alternate)


def test_hosted_readiness_contract_is_provider_neutral_and_fail_closed() -> None:
    payload = _contract()
    validate_hosted_readiness_contract(payload)

    authority = payload["authority"]
    edge = payload["edge_trust"]
    capacity = payload["capacity_cost"]
    release = payload["release"]
    assert isinstance(authority, dict)
    assert isinstance(edge, dict)
    assert isinstance(capacity, dict)
    assert isinstance(release, dict)

    assert authority["provider"] == "PROVIDER_NEUTRAL_HOSTED_RUNTIME"
    assert authority["provider_apply_authorized"] is False
    assert authority["public_ingress_allowed"] is False
    assert authority["authorized_recurring_rub"] == 0
    assert authority["owner_home_availability_dependency_allowed"] is False
    assert authority["lenovo_production_origin_allowed"] is False
    assert authority["public_multi_user_enabled"] is False
    assert authority["trading_methods_enabled"] is False
    assert authority["real_trading_enabled"] is False
    assert authority["protected_v9_entrypoint"] == "app:app"
    assert authority["wp23_unlocked"] is False

    assert edge["canonical_host_source"] == "RUNTIME_CONFIGURATION"
    assert edge["canonical_https_required"] is True
    assert edge["arbitrary_forwarded_headers_trusted"] is False
    assert edge["direct_origin_public_access_allowed"] is False
    assert edge["host_allowlist_required"] is True
    assert edge["csrf_origin_referer_required"] is True
    assert edge["cors_policy"] == "DENY_BY_DEFAULT"
    assert edge["secure_session_cookie_required"] is True
    assert edge["http_only_session_cookie_required"] is True
    assert edge["browser_web_storage_session_allowed"] is False

    assert capacity["automatic_paid_overage_allowed"] is False
    assert capacity["maximum_authorized_recurring_rub"] == 0
    assert capacity["apply_requires_owner_budget_approval"] is True
    assert capacity["synthetic_preview_private_data_allowed"] is False
    assert capacity["synthetic_preview_broker_credentials_allowed"] is False

    assert release["accepted_main_only"] is True
    assert release["exact_commit_required"] is True
    assert release["arbitrary_pr_provider_secrets_allowed"] is False
    assert release["provider_mutation_performed"] is False


def test_hosted_readiness_contract_path_is_provider_neutral() -> None:
    from omni_cio.observability.hosted_readiness_v1 import CONTRACT_PATH

    normalized = CONTRACT_PATH.as_posix().lower()
    assert "infrastructure/hosted" in normalized
    assert "cloudru" not in normalized


def test_hosted_readiness_contract_rejects_unknown_top_level_field() -> None:
    payload = deepcopy(_contract())
    payload["unexpected"] = True
    with pytest.raises(HostedReadinessContractError, match="CONTRACT_FIELDS_INVALID"):
        validate_hosted_readiness_contract(payload)


@pytest.mark.parametrize(
    ("section", "field", "value", "expected"),
    [
        ("authority", "provider_apply_authorized", True, "AUTHORITY_DRIFT"),
        ("edge_trust", "direct_origin_public_access_allowed", True, "EDGE_DRIFT"),
        ("observability", "raw_tenant_ids_allowed", True, "OBSERVABILITY_DRIFT"),
        (
            "capacity_cost",
            "automatic_paid_overage_allowed",
            True,
            "CAPACITY_COST_DRIFT",
        ),
        ("release", "provider_mutation_performed", True, "RELEASE_DRIFT"),
    ],
)
def test_hosted_readiness_contract_rejects_drift(
    section: str,
    field: str,
    value: object,
    expected: str,
) -> None:
    payload = deepcopy(_contract())
    target = payload[section]
    assert isinstance(target, dict)
    target[field] = value
    with pytest.raises(HostedReadinessContractError, match=expected):
        validate_hosted_readiness_contract(payload)


def test_hosted_health_evidence_accepts_broker_not_activated() -> None:
    evidence = _evidence()
    states = validate_hosted_health_evidence(
        evidence, expected_release_sha=_RELEASE_SHA, now_utc=NOW
    )

    assert states["broker_external"] == "NOT_APPLICABLE"
    assert (
        aggregate_hosted_runtime_state(
            evidence, expected_release_sha=_RELEASE_SHA, now_utc=NOW
        )
        == "READY"
    )


@pytest.mark.parametrize(
    ("domain", "state", "expected"),
    [
        ("broker_external", "OFFLINE", "DEGRADED"),
        ("product_auth", "OFFLINE", "OFFLINE"),
        ("recovery", "OFFLINE", "OFFLINE"),
        ("recovery", "DEGRADED", "DEGRADED"),
        ("application", "DEGRADED", "DEGRADED"),
        ("cloud_provider", "OFFLINE", "OFFLINE"),
        ("database", "OFFLINE", "OFFLINE"),
    ],
)
def test_hosted_runtime_state_distinguishes_failure_domains(
    domain: str,
    state: str,
    expected: str,
) -> None:
    evidence = _evidence()
    dependency = _dependency(evidence, domain)
    dependency["state"] = state
    dependency["reason_code"] = f"{domain.upper()}_{state}"

    assert (
        aggregate_hosted_runtime_state(
            evidence, expected_release_sha=_RELEASE_SHA, now_utc=NOW
        )
        == expected
    )


@pytest.mark.parametrize(
    "field",
    ["migration_state_match", "runtime_acl_match", "tenant_boundary_match"],
)
def test_hosted_runtime_state_fails_offline_on_structural_mismatch(field: str) -> None:
    evidence = _evidence()
    evidence[field] = False
    assert (
        aggregate_hosted_runtime_state(
            evidence, expected_release_sha=_RELEASE_SHA, now_utc=NOW
        )
        == "OFFLINE"
    )


def test_hosted_health_evidence_rejects_stale_or_future_timestamp() -> None:
    stale = _evidence()
    stale["checked_at_utc"] = (NOW - timedelta(seconds=301)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    with pytest.raises(HostedReadinessContractError, match="EVIDENCE_STALE"):
        validate_hosted_health_evidence(
            stale, expected_release_sha=_RELEASE_SHA, now_utc=NOW
        )

    future = _evidence()
    future["checked_at_utc"] = (NOW + timedelta(seconds=6)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    with pytest.raises(HostedReadinessContractError, match="EVIDENCE_FROM_FUTURE"):
        validate_hosted_health_evidence(
            future, expected_release_sha=_RELEASE_SHA, now_utc=NOW
        )


def test_hosted_health_evidence_rejects_missing_or_duplicate_domains() -> None:
    missing = _evidence()
    dependencies = missing["dependencies"]
    assert isinstance(dependencies, list)
    dependencies.pop()
    with pytest.raises(HostedReadinessContractError, match="DOMAINS_INCOMPLETE"):
        validate_hosted_health_evidence(
            missing, expected_release_sha=_RELEASE_SHA, now_utc=NOW
        )

    duplicate = _evidence()
    dependencies = duplicate["dependencies"]
    assert isinstance(dependencies, list)
    dependencies[-1] = dict(dependencies[0])
    with pytest.raises(HostedReadinessContractError, match="DOMAIN_DUPLICATE"):
        validate_hosted_health_evidence(
            duplicate, expected_release_sha=_RELEASE_SHA, now_utc=NOW
        )


def test_hosted_health_evidence_rejects_unknown_top_level_field() -> None:
    evidence = _evidence()
    evidence["raw_diagnostic"] = "private payload"
    with pytest.raises(HostedReadinessContractError, match="EVIDENCE_FIELDS_INVALID"):
        validate_hosted_health_evidence(
            evidence,
            expected_release_sha=_RELEASE_SHA,
            now_utc=NOW,
        )


def test_hosted_health_evidence_rejects_unbounded_or_private_metadata() -> None:
    extra = _evidence()
    application = _dependency(extra, "application")
    application["raw_tenant_id"] = "tenant:v1:private"
    with pytest.raises(HostedReadinessContractError, match="DEPENDENCY_FIELDS_INVALID"):
        validate_hosted_health_evidence(
            extra, expected_release_sha=_RELEASE_SHA, now_utc=NOW
        )

    bad_reason = _evidence()
    application = _dependency(bad_reason, "application")
    application["reason_code"] = "tenant:v1:private"
    with pytest.raises(HostedReadinessContractError, match="REASON_CODE_INVALID"):
        validate_hosted_health_evidence(
            bad_reason, expected_release_sha=_RELEASE_SHA, now_utc=NOW
        )


def test_hosted_health_evidence_rejects_not_applicable_core_domain() -> None:
    evidence = _evidence()
    application = _dependency(evidence, "application")
    application["state"] = "NOT_APPLICABLE"
    application["reason_code"] = "APPLICATION_NOT_APPLICABLE"

    with pytest.raises(
        HostedReadinessContractError,
        match="CORE_DOMAIN_NOT_APPLICABLE",
    ):
        validate_hosted_health_evidence(
            evidence,
            expected_release_sha=_RELEASE_SHA,
            now_utc=NOW,
        )


def test_hosted_health_evidence_binds_release_and_correlation_id() -> None:
    release_drift = _evidence()
    release_drift["release_sha"] = "0" * 40
    with pytest.raises(HostedReadinessContractError, match="RELEASE_SHA_MISMATCH"):
        validate_hosted_health_evidence(
            release_drift, expected_release_sha=_RELEASE_SHA, now_utc=NOW
        )

    invalid_correlation = _evidence()
    invalid_correlation["correlation_id"] = "not-a-server-generated-uuid"
    with pytest.raises(HostedReadinessContractError, match="CORRELATION_ID_INVALID"):
        validate_hosted_health_evidence(
            invalid_correlation, expected_release_sha=_RELEASE_SHA, now_utc=NOW
        )


def test_hosted_health_evidence_keeps_phase3_public_ingress_off() -> None:
    evidence = _evidence()
    evidence["public_ingress_enabled"] = True
    with pytest.raises(
        HostedReadinessContractError,
        match="PUBLIC_INGRESS_FORBIDDEN",
    ):
        validate_hosted_health_evidence(
            evidence,
            expected_release_sha=_RELEASE_SHA,
            now_utc=NOW,
        )


def test_hosted_health_evidence_rejects_non_boolean_structural_flags() -> None:
    evidence = _evidence()
    evidence["tenant_boundary_match"] = 1
    with pytest.raises(
        HostedReadinessContractError,
        match="TENANT_BOUNDARY_MATCH_INVALID",
    ):
        validate_hosted_health_evidence(
            evidence,
            expected_release_sha=_RELEASE_SHA,
            now_utc=NOW,
        )
