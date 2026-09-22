from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
import hmac
import json
from pathlib import Path
import re
from typing import Any
from uuid import UUID


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "infrastructure" / "hosted" / "hosted-readiness-contract.json"

_EXPECTED_CONTRACT_FIELDS = (
    "schema_version",
    "authority",
    "edge_trust",
    "health",
    "observability",
    "capacity_cost",
    "release",
)
_EXPECTED_AUTHORITY = {
    "provider": "PROVIDER_NEUTRAL_HOSTED_RUNTIME",
    "source_only": True,
    "provider_apply_authorized": False,
    "public_ingress_allowed": False,
    "authorized_recurring_rub": 0,
    "owner_home_availability_dependency_allowed": False,
    "lenovo_production_origin_allowed": False,
    "public_multi_user_enabled": False,
    "trading_methods_enabled": False,
    "real_trading_enabled": False,
    "protected_v9_entrypoint": "app:app",
    "wp23_unlocked": False,
}
_EXPECTED_EDGE_TRUST = {
    "canonical_host_source": "RUNTIME_CONFIGURATION",
    "canonical_https_required": True,
    "trusted_proxy_hops": 1,
    "arbitrary_forwarded_headers_trusted": False,
    "direct_origin_public_access_allowed": False,
    "host_allowlist_required": True,
    "forwarded_proto_required": "https",
    "hsts_required": True,
    "csrf_origin_referer_required": True,
    "cors_policy": "DENY_BY_DEFAULT",
    "private_response_cache_allowed": False,
    "secure_session_cookie_required": True,
    "http_only_session_cookie_required": True,
    "browser_web_storage_session_allowed": False,
}
_EXPECTED_DOMAINS = (
    "application",
    "cloud_provider",
    "database",
    "product_auth",
    "broker_external",
    "recovery",
)
_EXPECTED_STATES = ("READY", "DEGRADED", "OFFLINE", "NOT_APPLICABLE")
_EXPECTED_CORE_DOMAINS = (
    "application",
    "cloud_provider",
    "database",
    "product_auth",
    "recovery",
)
_EXPECTED_HEALTH = {
    "domains": list(_EXPECTED_DOMAINS),
    "states": list(_EXPECTED_STATES),
    "required_core_domains": list(_EXPECTED_CORE_DOMAINS),
    "broker_external_optional_for_platform_readiness": True,
    "database_migration_match_required": True,
    "runtime_acl_match_required": True,
    "tenant_boundary_match_required": True,
    "public_ingress_required_during_phase3": False,
}
_EXPECTED_OBSERVABILITY = {
    "server_generated_correlation_id_required": True,
    "bounded_label_cardinality_required": True,
    "raw_tenant_ids_allowed": False,
    "raw_user_ids_allowed": False,
    "raw_broker_account_ids_allowed": False,
    "credential_values_allowed": False,
    "private_payloads_allowed": False,
    "reason_code_pattern": "^[A-Z][A-Z0-9_]{2,63}$",
    "maximum_evidence_age_seconds": 300,
}
_EXPECTED_CAPACITY_COST = {
    "stage": "SOURCE_ONLY_ZERO_RUB",
    "automatic_paid_overage_allowed": False,
    "maximum_authorized_recurring_rub": 0,
    "apply_requires_owner_budget_approval": True,
    "scale_requires_measured_evidence": True,
    "request_rate_limits_required": True,
    "database_pool_bound_required": True,
    "backup_size_bound_required": True,
    "synthetic_preview_private_data_allowed": False,
    "synthetic_preview_broker_credentials_allowed": False,
}
_EXPECTED_RELEASE = {
    "accepted_main_only": True,
    "exact_commit_required": True,
    "arbitrary_pr_provider_secrets_allowed": False,
    "health_before_traffic_required": True,
    "rollback_to_last_accepted_release_required": True,
    "provider_mutation_performed": False,
}
_EXPECTED_EVIDENCE_FIELDS = {
    "schema_version",
    "correlation_id",
    "release_sha",
    "checked_at_utc",
    "public_ingress_enabled",
    "migration_state_match",
    "runtime_acl_match",
    "tenant_boundary_match",
    "dependencies",
}
_EXPECTED_DEPENDENCY_FIELDS = {"domain", "state", "reason_code"}
_EVIDENCE_VERSION = "v10.wp22a.phase3.hosted-health-evidence.v1"
_RELEASE_SHA_RE = re.compile(r"^[a-f0-9]{40}$")


class HostedReadinessContractError(RuntimeError):
    """Fail-closed hosted edge, health, capacity or evidence violation."""


def _as_mapping(value: object, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise HostedReadinessContractError(code)
    return value


def _as_sequence(value: object, code: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise HostedReadinessContractError(code)
    return value


def _require_exact_mapping(
    actual: Mapping[str, Any],
    expected: Mapping[str, object],
    code: str,
) -> None:
    if set(actual) != set(expected):
        raise HostedReadinessContractError(code)
    for key, expected_value in expected.items():
        actual_value = actual[key]
        if type(actual_value) is not type(expected_value):
            raise HostedReadinessContractError(code)
        if actual_value != expected_value:
            raise HostedReadinessContractError(code)


def _parse_utc(value: object, code: str) -> datetime:
    if not isinstance(value, str):
        raise HostedReadinessContractError(code)
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError as exc:
        raise HostedReadinessContractError(code) from exc
    return parsed


def load_hosted_readiness_contract(
    path: Path = CONTRACT_PATH,
) -> dict[str, Any]:
    if path.resolve(strict=False) != CONTRACT_PATH.resolve(strict=False):
        raise HostedReadinessContractError("HOSTED_READINESS_CONTRACT_PATH_INVALID")
    try:
        payload = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HostedReadinessContractError(
            "HOSTED_READINESS_CONTRACT_READ_INVALID"
        ) from exc
    if not isinstance(payload, dict):
        raise HostedReadinessContractError("HOSTED_READINESS_CONTRACT_NOT_OBJECT")
    return payload


def validate_hosted_readiness_contract(payload: Mapping[str, Any]) -> None:
    if set(payload) != set(_EXPECTED_CONTRACT_FIELDS):
        raise HostedReadinessContractError("HOSTED_READINESS_CONTRACT_FIELDS_INVALID")
    if payload.get("schema_version") != "v10.hosted-readiness.v2":
        raise HostedReadinessContractError("HOSTED_READINESS_CONTRACT_VERSION_INVALID")

    _require_exact_mapping(
        _as_mapping(payload.get("authority"), "HOSTED_READINESS_AUTHORITY_INVALID"),
        _EXPECTED_AUTHORITY,
        "HOSTED_READINESS_AUTHORITY_DRIFT",
    )
    _require_exact_mapping(
        _as_mapping(payload.get("edge_trust"), "HOSTED_READINESS_EDGE_INVALID"),
        _EXPECTED_EDGE_TRUST,
        "HOSTED_READINESS_EDGE_DRIFT",
    )
    _require_exact_mapping(
        _as_mapping(payload.get("health"), "HOSTED_READINESS_HEALTH_INVALID"),
        _EXPECTED_HEALTH,
        "HOSTED_READINESS_HEALTH_DRIFT",
    )
    _require_exact_mapping(
        _as_mapping(
            payload.get("observability"),
            "HOSTED_READINESS_OBSERVABILITY_INVALID",
        ),
        _EXPECTED_OBSERVABILITY,
        "HOSTED_READINESS_OBSERVABILITY_DRIFT",
    )
    _require_exact_mapping(
        _as_mapping(
            payload.get("capacity_cost"),
            "HOSTED_READINESS_CAPACITY_COST_INVALID",
        ),
        _EXPECTED_CAPACITY_COST,
        "HOSTED_READINESS_CAPACITY_COST_DRIFT",
    )
    _require_exact_mapping(
        _as_mapping(payload.get("release"), "HOSTED_READINESS_RELEASE_INVALID"),
        _EXPECTED_RELEASE,
        "HOSTED_READINESS_RELEASE_DRIFT",
    )


def validate_hosted_health_evidence(
    evidence: Mapping[str, Any],
    *,
    expected_release_sha: str,
    now_utc: datetime | None = None,
    contract: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    active_contract = (
        contract if contract is not None else load_hosted_readiness_contract()
    )
    validate_hosted_readiness_contract(active_contract)

    if set(evidence) != _EXPECTED_EVIDENCE_FIELDS:
        raise HostedReadinessContractError("HOSTED_HEALTH_EVIDENCE_FIELDS_INVALID")
    if evidence.get("schema_version") != _EVIDENCE_VERSION:
        raise HostedReadinessContractError("HOSTED_HEALTH_EVIDENCE_VERSION_INVALID")

    correlation_id = evidence.get("correlation_id")
    if not isinstance(correlation_id, str):
        raise HostedReadinessContractError("HOSTED_HEALTH_CORRELATION_ID_INVALID")
    try:
        parsed_correlation_id = UUID(correlation_id)
    except ValueError as exc:
        raise HostedReadinessContractError(
            "HOSTED_HEALTH_CORRELATION_ID_INVALID"
        ) from exc
    if (
        parsed_correlation_id.version != 4
        or str(parsed_correlation_id) != correlation_id
    ):
        raise HostedReadinessContractError("HOSTED_HEALTH_CORRELATION_ID_INVALID")

    if (
        not isinstance(expected_release_sha, str)
        or _RELEASE_SHA_RE.fullmatch(expected_release_sha) is None
    ):
        raise HostedReadinessContractError("HOSTED_HEALTH_EXPECTED_RELEASE_SHA_INVALID")
    release_sha = evidence.get("release_sha")
    if (
        not isinstance(release_sha, str)
        or _RELEASE_SHA_RE.fullmatch(release_sha) is None
    ):
        raise HostedReadinessContractError("HOSTED_HEALTH_RELEASE_SHA_INVALID")
    if not hmac.compare_digest(release_sha, expected_release_sha):
        raise HostedReadinessContractError("HOSTED_HEALTH_RELEASE_SHA_MISMATCH")

    public_ingress_enabled = evidence.get("public_ingress_enabled")
    if type(public_ingress_enabled) is not bool:
        raise HostedReadinessContractError("HOSTED_HEALTH_PUBLIC_INGRESS_STATE_INVALID")
    if public_ingress_enabled:
        raise HostedReadinessContractError("HOSTED_HEALTH_PUBLIC_INGRESS_FORBIDDEN")

    checked_at = _parse_utc(
        evidence.get("checked_at_utc"),
        "HOSTED_HEALTH_EVIDENCE_TIMESTAMP_INVALID",
    )
    now = now_utc or datetime.now(UTC)
    if now.tzinfo is None or now.utcoffset() is None:
        raise HostedReadinessContractError("HOSTED_HEALTH_NOW_NOT_UTC_AWARE")
    now = now.astimezone(UTC)
    observability = _as_mapping(
        active_contract["observability"],
        "HOSTED_READINESS_OBSERVABILITY_INVALID",
    )
    if checked_at > now + timedelta(seconds=5):
        raise HostedReadinessContractError("HOSTED_HEALTH_EVIDENCE_FROM_FUTURE")
    age = (now - checked_at).total_seconds()
    if age > int(observability["maximum_evidence_age_seconds"]):
        raise HostedReadinessContractError("HOSTED_HEALTH_EVIDENCE_STALE")

    for field in (
        "migration_state_match",
        "runtime_acl_match",
        "tenant_boundary_match",
    ):
        if type(evidence[field]) is not bool:
            raise HostedReadinessContractError(f"HOSTED_HEALTH_{field.upper()}_INVALID")

    reason_pattern = re.compile(str(observability["reason_code_pattern"]))
    dependencies = _as_sequence(
        evidence.get("dependencies"),
        "HOSTED_HEALTH_DEPENDENCIES_INVALID",
    )
    normalized: dict[str, str] = {}
    for item in dependencies:
        dependency = _as_mapping(item, "HOSTED_HEALTH_DEPENDENCY_INVALID")
        if set(dependency) != _EXPECTED_DEPENDENCY_FIELDS:
            raise HostedReadinessContractError(
                "HOSTED_HEALTH_DEPENDENCY_FIELDS_INVALID"
            )
        domain = dependency.get("domain")
        state = dependency.get("state")
        reason_code = dependency.get("reason_code")
        if not isinstance(domain, str) or domain not in _EXPECTED_DOMAINS:
            raise HostedReadinessContractError("HOSTED_HEALTH_DOMAIN_INVALID")
        if domain in normalized:
            raise HostedReadinessContractError("HOSTED_HEALTH_DOMAIN_DUPLICATE")
        if not isinstance(state, str) or state not in _EXPECTED_STATES:
            raise HostedReadinessContractError("HOSTED_HEALTH_STATE_INVALID")
        if state == "NOT_APPLICABLE" and domain != "broker_external":
            raise HostedReadinessContractError(
                "HOSTED_HEALTH_CORE_DOMAIN_NOT_APPLICABLE"
            )
        if (
            not isinstance(reason_code, str)
            or reason_pattern.fullmatch(reason_code) is None
        ):
            raise HostedReadinessContractError("HOSTED_HEALTH_REASON_CODE_INVALID")
        normalized[domain] = state

    if set(normalized) != set(_EXPECTED_DOMAINS):
        raise HostedReadinessContractError("HOSTED_HEALTH_DOMAINS_INCOMPLETE")
    return normalized


def aggregate_hosted_runtime_state(
    evidence: Mapping[str, Any],
    *,
    expected_release_sha: str,
    now_utc: datetime | None = None,
    contract: Mapping[str, Any] | None = None,
) -> str:
    states = validate_hosted_health_evidence(
        evidence,
        expected_release_sha=expected_release_sha,
        now_utc=now_utc,
        contract=contract,
    )
    if not all(
        evidence[field]
        for field in (
            "migration_state_match",
            "runtime_acl_match",
            "tenant_boundary_match",
        )
    ):
        return "OFFLINE"

    if any(states[domain] == "OFFLINE" for domain in _EXPECTED_CORE_DOMAINS):
        return "OFFLINE"
    if any(states[domain] == "DEGRADED" for domain in _EXPECTED_CORE_DOMAINS):
        return "DEGRADED"

    if states["broker_external"] in {"DEGRADED", "OFFLINE"}:
        return "DEGRADED"
    return "READY"
