from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AMENDMENT = (
    ROOT / "docs/master-plan/OMNI_CIO_V10_TIMEWEB_FULL_PRODUCTION_DELIVERY_AMENDMENT.md"
)
CONTRACT = ROOT / "docs/architecture/V10_TIMEWEB_FULL_PRODUCTION_DELIVERY_CONTRACT.json"
RUNTIME = ROOT / "apps/api/hosted_runtime.py"
HOSTED_APP = ROOT / "apps/api/hosted_app.py"
POSTGRES_CONNECTION = ROOT / "apps/api/postgres_web_connection.py"
TELEGRAM_AUTH = ROOT / "apps/api/telegram_auth.py"
TELEGRAM_READINESS = (
    ROOT
    / "docs/architecture/V10_TELEGRAM_PUBLIC_USER_ACTIVATION_READINESS_CONTRACT.json"
)
DOCKERFILE = ROOT / "Dockerfile"

_CANONICAL_ORIGIN = "https://omnicio.ru"
_CANONICAL_CALLBACK = "https://omnicio.ru/api/v10/web/auth/telegram/callback"
_EXPECTED_BRANCH = "system/timeweb-platform-consolidation-tw-b"
_SECRET_ENV_NAMES = {
    "OMNI_V10_POSTGRES_DSN",
    "OMNI_V10_TELEGRAM_OIDC_CLIENT_ID",
    "OMNI_V10_TELEGRAM_OIDC_CLIENT_SECRET",
    "OMNI_V10_IDENTITY_BINDING_KEY_HEX",
    "OMNI_V10_CSRF_BINDING_KEY_HEX",
}


def _text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError(
            f"TIMEWEB_FULL_DELIVERY_SOURCE_UNREADABLE:{path.relative_to(ROOT)}"
        ) from exc


def _json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(_text(path))
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"TIMEWEB_FULL_DELIVERY_JSON_INVALID:{path.relative_to(ROOT)}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError("TIMEWEB_FULL_DELIVERY_JSON_ROOT_INVALID")
    return payload


def _require_equal(payload: dict[str, Any], key: str, expected: Any) -> None:
    if payload.get(key) != expected:
        raise RuntimeError(f"TIMEWEB_FULL_DELIVERY_CONTRACT_DRIFT:{key}")


def _section(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise RuntimeError(f"TIMEWEB_FULL_DELIVERY_SECTION_INVALID:{key}")
    return value


def _validate_authority(payload: dict[str, Any]) -> None:
    _require_equal(
        payload,
        "schema",
        "omni-cio.v10.timeweb-full-production-delivery.v1",
    )
    _require_equal(
        payload,
        "status",
        "BRANCH_LOCAL_IMPLEMENTATION_COMPLETE_FINAL_EXACT_HEAD_VERIFICATION_REQUIRED",
    )
    _require_equal(payload, "owning_issue", 580)
    _require_equal(payload, "owning_pr", 584)
    _require_equal(payload, "branch", _EXPECTED_BRANCH)
    _require_equal(payload, "canonical_domain", "omnicio.ru")
    _require_equal(payload, "canonical_origin", _CANONICAL_ORIGIN)
    _require_equal(payload, "telegram_redirect_uri", _CANONICAL_CALLBACK)

    amendment = _text(AMENDMENT)
    required = (
        "OWNER-APPROVED BRANCH-LOCAL IMPLEMENTATION AUTHORITY",
        "PR #584",
        "exact-SHA Timeweb App Platform candidate/release control",
        "Timeweb PostgreSQL 18 production cutover/recovery control",
        "canonical `omnicio.ru` DNS/TLS/public-ingress acceptance",
        "Telegram-only production login readiness and activation control",
        "does not authorize",
        "broker write",
        "a merge of PR #584 without the required exact-head landing confirmation",
    )
    for marker in required:
        if marker not in amendment:
            raise RuntimeError(
                f"TIMEWEB_FULL_DELIVERY_AMENDMENT_MARKER_MISSING:{marker}"
            )


def _validate_release(payload: dict[str, Any]) -> None:
    release = _section(payload, "release")
    expected = {
        "source_authority": "GITHUB_PROTECTED_MAIN",
        "deployment_platform": "TIMEWEB_APP_PLATFORM",
        "exact_commit_sha_required": True,
        "production_autodeploy_allowed": False,
        "runtime_release_env": "OMNI_V10_RELEASE_SHA",
        "liveness_path": "/livez",
        "platform_liveness_source": "DOCKERFILE_HEALTHCHECK",
        "dockerfile_healthcheck_path": "/livez",
        "panel_healthcheck_overrides_dockerfile_healthcheck": False,
        "database_readiness_path": "/healthz",
        "candidate_database_readiness_required": True,
        "candidate_database_ready_value": "READY",
        "candidate_synthetic_preview_required": False,
        "deployed_sha_must_equal_accepted_main_sha": True,
        "last_known_good_rollback_required": True,
        "mismatch_state": "OUT_OF_SYNC/DEPLOYMENT_BLOCKED",
    }
    for key, value in expected.items():
        if release.get(key) != value:
            raise RuntimeError(f"TIMEWEB_FULL_DELIVERY_RELEASE_DRIFT:{key}")


def _require_source_markers(
    source: str,
    markers: tuple[str, ...],
    *,
    error_prefix: str,
) -> None:
    for marker in markers:
        if marker not in source:
            raise RuntimeError(f"{error_prefix}:{marker}")


def _validate_runtime_contract(runtime: dict[str, Any]) -> None:
    if runtime.get("dockerfile") != "Dockerfile" or runtime.get("port") != 8080:
        raise RuntimeError("TIMEWEB_FULL_DELIVERY_RUNTIME_SOURCE_DRIFT")
    if runtime.get("app_factory") != "apps.api.hosted_runtime:create_app":
        raise RuntimeError("TIMEWEB_FULL_DELIVERY_RUNTIME_ENTRYPOINT_DRIFT")
    if runtime.get("credential_values_in_repository_allowed") is not False:
        raise RuntimeError("TIMEWEB_FULL_DELIVERY_SECRET_POLICY_DRIFT")

    expected_capacity = {
        "private_postgres_hostaddr_env": "OMNI_V10_POSTGRES_PRIVATE_HOSTADDR",
        "private_postgres_network_cidr_env": "OMNI_V10_POSTGRES_PRIVATE_NETWORK_CIDR",
        "private_postgres_route_required": True,
        "private_postgres_tls_hostname_identity_from_dsn": True,
        "postgres_binding_sha256_env": "OMNI_V10_POSTGRES_BINDING_SHA256",
        "postgres_binding_sha256_required": True,
        "postgres_binding_sha256_sensitive": False,
        "postgres_binding_sha256_source": "P3_PREPARE_ACCEPTED_OUTPUT",
        "liveness_startup_database_dependency_allowed": False,
        "database_pool_lazy_initialization_required": True,
        "postgres_pool_max_size": 4,
        "postgres_pool_acquire_timeout_seconds": 5,
        "single_serialized_runtime_connection_allowed": False,
        "session_lookup_event_loop_blocking_allowed": False,
    }
    for key, value in expected_capacity.items():
        if runtime.get(key) != value:
            raise RuntimeError(f"TIMEWEB_FULL_DELIVERY_RUNTIME_CAPACITY_DRIFT:{key}")

    names = runtime.get("runtime_credential_env_names")
    if not isinstance(names, list) or set(names) != _SECRET_ENV_NAMES:
        raise RuntimeError("TIMEWEB_FULL_DELIVERY_SECRET_ENV_DRIFT")


def _validate_runtime_sources() -> None:
    _require_source_markers(
        _text(DOCKERFILE),
        (
            "EXPOSE 8080",
            "apps.api.hosted_runtime:create_app",
            "http://localhost:8080/livez",
        ),
        error_prefix="TIMEWEB_FULL_DELIVERY_DOCKER_DRIFT",
    )

    hosted_runtime = _text(RUNTIME)
    _require_source_markers(
        hosted_runtime,
        (
            "OMNI_V10_HOSTED_RUNTIME",
            "OMNI_V10_PUBLIC_HOSTNAME",
            "OMNI_V10_RELEASE_SHA",
            "OMNI_V10_POSTGRES_DSN",
            "OMNI_V10_POSTGRES_PRIVATE_HOSTADDR",
            "OMNI_V10_POSTGRES_PRIVATE_NETWORK_CIDR",
            "OMNI_V10_POSTGRES_BINDING_SHA256",
            "OMNI_V10_POSTGRES_RUNTIME_ROLE",
            "prepare_timeweb_postgres_private_target",
            'canonical_origin=f"https://{hostname}"',
            "provider_route_installer=install_telegram_auth_routes_v1",
            "_BoundedWebConnectionPool",
            "_DATABASE_POOL_MAX_SIZE = 4",
            "_BoundedWebConnectionPool(\n        None,",
            "_DATABASE_POOL_ACQUIRE_TIMEOUT_SECONDS = 5.0",
            "connect=lambda:",
        ),
        error_prefix="TIMEWEB_FULL_DELIVERY_HOSTED_RUNTIME_DRIFT",
    )
    if "_SerializedWebConnection(" in hosted_runtime:
        raise RuntimeError("TIMEWEB_FULL_DELIVERY_SINGLE_CONNECTION_FORBIDDEN")

    _require_source_markers(
        _text(HOSTED_APP),
        (
            "from starlette.concurrency import run_in_threadpool",
            "scope = await run_in_threadpool(",
            "async def _resolve_session(",
        ),
        error_prefix="TIMEWEB_FULL_DELIVERY_EVENT_LOOP_DRIFT",
    )
    _require_source_markers(
        _text(POSTGRES_CONNECTION),
        (
            "class _BoundedWebConnectionPool",
            "WEB_RUNTIME_POSTGRES_POOL_EXHAUSTED",
            "transaction_connection",
            "LifoQueue",
        ),
        error_prefix="TIMEWEB_FULL_DELIVERY_POOL_DRIFT",
    )


def _validate_runtime(payload: dict[str, Any]) -> None:
    runtime = _section(payload, "runtime")
    _validate_runtime_contract(runtime)
    _validate_runtime_sources()


def _validate_postgres(payload: dict[str, Any]) -> None:
    postgres = _section(payload, "postgres")
    expected = {
        "engine": "PostgreSQL",
        "major_version": 18,
        "canonical_runtime_contract": "infrastructure/postgres/hosted-postgres-runtime-contract.json",
        "production_cutover_contract": "docs/architecture/V10_TIMEWEB_POSTGRES_PRODUCTION_CUTOVER_CONTRACT.json",
        "production_cutover_controller": "scripts/timeweb_postgres_production_cutover.py",
        "production_cutover_workflow": ".github/workflows/v10-timeweb-postgres-production-cutover.yml",
        "migrations_required": True,
        "least_privilege_required": True,
        "rls_required": True,
        "force_rls_required": True,
        "cross_tenant_negative_required": True,
        "backup_restore_required": True,
        "production_cutover_requires_independent_acceptance": True,
    }
    for key, value in expected.items():
        if postgres.get(key) != value:
            raise RuntimeError(f"TIMEWEB_FULL_DELIVERY_POSTGRES_DRIFT:{key}")


def _validate_public_ingress(payload: dict[str, Any]) -> None:
    ingress = _section(payload, "public_ingress")
    expected = {
        "custom_domain": "omnicio.ru",
        "tls_required": True,
        "cloudflare_required_hop": False,
        "owner_home_network_dependency_allowed": False,
        "representative_russian_no_vpn_evidence_required": True,
        "undocumented_provider_domain_api_allowed": False,
        "controller": "scripts/timeweb_public_ingress_acceptance.py",
        "workflow": ".github/workflows/v10-timeweb-public-ingress-acceptance.yml",
        "runbook": "docs/operations/V10_TIMEWEB_PUBLIC_INGRESS_ACCEPTANCE_RUNBOOK.md",
        "operations": ["observe", "accept"],
        "provider_api_mode": "READ_ONLY",
        "provider_domain_mutation_by_controller_allowed": False,
        "owner_panel_domain_attachment_when_no_documented_api": True,
        "automatic_lets_encrypt_expected": True,
        "public_https_probe_required": True,
        "exact_release_sha_required": True,
        "database_readiness_required": True,
        "security_headers_required": True,
        "retired_edge_headers_forbidden": True,
        "p3_recovery_evidence_digest_required": True,
        "russian_no_vpn_evidence_digest_required": True,
        "rollback_release_sha_required": True,
        "rollback_evidence_digest_required": True,
        "public_activation_must_remain_false": True,
    }
    if ingress != expected:
        raise RuntimeError("TIMEWEB_FULL_DELIVERY_INGRESS_DRIFT")


def _validate_telegram(payload: dict[str, Any]) -> None:
    telegram = _section(payload, "telegram")
    expected = {
        "provider": "TELEGRAM",
        "oidc_authorization_code_pkce_required": True,
        "allowed_scope": ["openid"],
        "bot_access_scope_allowed": False,
        "public_multi_user_flag": "PUBLIC_MULTI_USER_ENABLED",
        "provider_activation_flag": "OMNI_V10_TELEGRAM_LOGIN_ENABLED",
        "flags_must_transition_together": True,
        "current_public_multi_user_enabled": False,
        "current_telegram_login_enabled": False,
        "provider_credential_custody": "TIMEWEB_APP_PLATFORM_ENVIRONMENT",
        "real_login_account_tenant_session_proof_required": True,
        "cross_tenant_negative_required": True,
        "activation_contract": "docs/architecture/V10_TIMEWEB_TELEGRAM_PUBLIC_ACTIVATION_CONTRACT.json",
        "activation_controller": "scripts/timeweb_telegram_public_activation.py",
        "activation_workflow": ".github/workflows/v10-timeweb-telegram-public-activation.yml",
        "activation_runbook": "docs/operations/V10_TELEGRAM_LOGIN_PRODUCTION_ACTIVATION_RUNBOOK.md",
        "identity_binding_fingerprint_env": "OMNI_V10_IDENTITY_BINDING_FINGERPRINT_SHA256",
        "identity_binding_fingerprint_algorithm": "SHA-256",
        "identity_binding_fingerprint_match_required": True,
        "silent_identity_binding_key_rotation_allowed": False,
        "identity_binding_rekey_requires_reviewed_migration": True,
        "horizontal_app_scaling_without_distributed_abuse_control_allowed": False,
    }
    for key, value in expected.items():
        if telegram.get(key) != value:
            raise RuntimeError(f"TIMEWEB_FULL_DELIVERY_TELEGRAM_DRIFT:{key}")

    source = _text(TELEGRAM_AUTH)
    for marker in (
        "PUBLIC_MULTI_USER_ENABLED",
        "OMNI_V10_TELEGRAM_LOGIN_ENABLED",
        "TELEGRAM_AUTH_ACTIVATION_FLAGS_MISMATCH",
        "allowed_providers=(IdentityProviderV1.TELEGRAM,)",
        "OMNI_V10_IDENTITY_BINDING_FINGERPRINT_SHA256",
        "TELEGRAM_AUTH_IDENTITY_BINDING_FINGERPRINT_MISMATCH",
    ):
        if marker not in source:
            raise RuntimeError(f"TIMEWEB_FULL_DELIVERY_TELEGRAM_SOURCE_DRIFT:{marker}")

    readiness = _json(TELEGRAM_READINESS)
    if readiness.get("activation_allowed") is not False:
        raise RuntimeError("TIMEWEB_FULL_DELIVERY_PREMATURE_PUBLIC_ACTIVATION")
    if readiness.get("canonical_origin") != _CANONICAL_ORIGIN:
        raise RuntimeError("TIMEWEB_FULL_DELIVERY_TELEGRAM_ORIGIN_DRIFT")
    if readiness.get("canonical_redirect_uri") != _CANONICAL_CALLBACK:
        raise RuntimeError("TIMEWEB_FULL_DELIVERY_TELEGRAM_CALLBACK_DRIFT")


def _validate_post_merge_acceptance(payload: dict[str, Any]) -> None:
    expected = {
        "contract": "docs/architecture/V10_TIMEWEB_POST_MERGE_PRODUCTION_ACCEPTANCE_CONTRACT.json",
        "controller": "scripts/timeweb_production_acceptance.py",
        "guard": "scripts/check_v10_timeweb_post_merge_production_acceptance.py",
        "workflow": ".github/workflows/v10-timeweb-post-merge-production-acceptance.yml",
        "runbook": "docs/operations/V10_TIMEWEB_POST_MERGE_PRODUCTION_ACCEPTANCE_RUNBOOK.md",
        "exact_main_required": True,
        "public_probe_only": True,
        "provider_mutation_allowed": False,
        "secret_access_allowed": False,
        "acceptance_seal_algorithm": "SHA-256",
        "rollback_evidence_required": True,
    }
    if _section(payload, "post_merge_acceptance") != expected:
        raise RuntimeError("TIMEWEB_FULL_DELIVERY_P6_DRIFT")


def _validate_external_gates(payload: dict[str, Any]) -> None:
    gates = _section(payload, "external_action_gates")
    required = {
        "app_creation_or_paid_capacity",
        "immutable_network_selection",
        "production_database_cutover",
        "dns_tls_cutover",
        "telegram_registration_and_credentials",
        "legal_privacy_regulatory",
        "public_activation",
        "destructive_decommission",
    }
    if set(gates) != required:
        raise RuntimeError("TIMEWEB_FULL_DELIVERY_EXTERNAL_GATE_SET_DRIFT")
    for key, value in gates.items():
        if not isinstance(value, str) or not value.endswith(("REQUIRED", "ONLY")):
            raise RuntimeError(f"TIMEWEB_FULL_DELIVERY_EXTERNAL_GATE_INVALID:{key}")


def _validate_provider_convergence_policy(payload: dict[str, Any]) -> None:
    expected = {
        "retry_observation_not_authority": True,
        "transient_http_statuses": [408, 429, 500, 502, 503, 504],
        "transient_network_failures_may_retry_bounded_read_only_observation": True,
        "authentication_or_authorization_failure_retry_allowed": False,
        "semantic_or_security_mismatch_retry_allowed": False,
        "mutation_replay_after_timeout_or_ambiguous_result_allowed": False,
        "exact_identity_inflight_state_adoption_required_when_supported": True,
        "duplicate_inflight_exact_identity_terminal": True,
        "provider_history_pagination_must_be_exhaustive": True,
        "asynchronous_provider_success_may_precede_readiness": True,
        "local_polling_budget_is_provider_sla": False,
        "stage_specific_sanitized_timeout_required": True,
        "provider_response_body_logging_allowed": False,
        "rollback_requires_get_reconciliation": True,
        "final_observation_after_last_backoff_required": True,
        "post_exposure_validation_read_only_required": True,
        "public_probe_transient_retry_required": True,
        "postgres_connect_transient_retry_required": True,
        "tls_listener_not_ready_may_retry_bounded_readiness": True,
        "tls_transport_timeout_distinct_from_certificate_failure": True,
        "tls_certificate_verification_failure_retry_allowed": False,
        "authority_expansion_on_recovery_allowed": False,
    }
    if _section(payload, "provider_convergence_policy") != expected:
        raise RuntimeError("TIMEWEB_FULL_DELIVERY_PROVIDER_CONVERGENCE_DRIFT")


def _validate_milestones(payload: dict[str, Any]) -> None:
    expected = [
        {"id": "P1_SOURCE_RUNTIME_CONVERGENCE", "state": "CERTIFIED_GREEN_SOURCE_BASE"},
        {
            "id": "P2_TIMEWEB_EXACT_SHA_CANDIDATE",
            "state": "REPAIR_SOURCE_IMPLEMENTED_EXACT_HEAD_VERIFICATION_REQUIRED",
        },
        {
            "id": "P3_POSTGRES18_PRODUCTION_CUTOVER",
            "state": "CERTIFIED_GREEN_BRANCH_LOCAL",
        },
        {
            "id": "P4_OMNICIO_RU_DNS_TLS",
            "state": "CERTIFIED_GREEN_BRANCH_LOCAL",
        },
        {
            "id": "P5_TELEGRAM_PUBLIC_ACTIVATION",
            "state": "CERTIFIED_GREEN_BRANCH_LOCAL",
        },
        {
            "id": "P5_5_TIMEWEB_WORKTREE_CONVERGENCE",
            "state": "IMPLEMENTATION_COMPLETE_FINAL_EXACT_HEAD_VERIFICATION_REQUIRED",
        },
        {
            "id": "P6_POST_MERGE_PRODUCTION_ACCEPTANCE",
            "state": "SOURCE_IMPLEMENTATION_COMPLETE_POST_MERGE_EXECUTION_REQUIRED",
        },
    ]
    if payload.get("branch_milestones") != expected:
        raise RuntimeError("TIMEWEB_FULL_DELIVERY_MILESTONE_DRIFT")


def _validate_execution_sequence(payload: dict[str, Any]) -> None:
    expected = [
        "P2_SOURCE_REPAIR_ACCEPTED_MAIN",
        "P3_OBSERVE",
        "P3_PREPARE",
        "P3_RECOVERY_EVIDENCE",
        "TIMEWEB_APP_CREATE_IN_ACCEPTED_PRIVATE_NETWORK",
        "TIMEWEB_TECHNICAL_DOMAIN_BOOTSTRAP",
        "P2_PHYSICAL_EXACT_SHA_CANDIDATE",
        "P3_ACCEPT",
        "P4_CANONICAL_DOMAIN_TLS",
    ]
    if payload.get("execution_sequence") != expected:
        raise RuntimeError("TIMEWEB_FULL_DELIVERY_EXECUTION_SEQUENCE_DRIFT")


def _validate_merge_readiness(payload: dict[str, Any]) -> None:
    expected = {
        "repository_implementation_complete": True,
        "exact_head_ci_required": True,
        "unresolved_blocking_threads_required_zero": True,
        "squash_merge_required": True,
        "post_merge_acceptance_required": True,
        "production_accepted_before_merge": False,
    }
    if _section(payload, "merge_readiness") != expected:
        raise RuntimeError("TIMEWEB_FULL_DELIVERY_MERGE_READINESS_DRIFT")


def _validate_protected_invariants(payload: dict[str, Any]) -> None:
    protected = _section(payload, "protected_invariants")
    for key in (
        "broker_write",
        "trading_methods",
        "REAL_TRADING_ENABLED",
        "transfer_withdrawal",
        "margin_leverage",
        "uncovered_short",
        "browser_tenant_selection",
        "web_visual_started",
        "wp23_unlocked",
        "merge_without_exact_head_confirmation",
    ):
        if protected.get(key) is not False:
            raise RuntimeError(f"TIMEWEB_FULL_DELIVERY_AUTHORITY_WIDENED:{key}")


def validate(root: Path = ROOT) -> None:
    global \
        ROOT, \
        AMENDMENT, \
        CONTRACT, \
        RUNTIME, \
        HOSTED_APP, \
        POSTGRES_CONNECTION, \
        TELEGRAM_AUTH, \
        TELEGRAM_READINESS, \
        DOCKERFILE
    original = (
        ROOT,
        AMENDMENT,
        CONTRACT,
        RUNTIME,
        HOSTED_APP,
        POSTGRES_CONNECTION,
        TELEGRAM_AUTH,
        TELEGRAM_READINESS,
        DOCKERFILE,
    )
    if root != ROOT:
        ROOT = root
        AMENDMENT = (
            root
            / "docs/master-plan/OMNI_CIO_V10_TIMEWEB_FULL_PRODUCTION_DELIVERY_AMENDMENT.md"
        )
        CONTRACT = (
            root
            / "docs/architecture/V10_TIMEWEB_FULL_PRODUCTION_DELIVERY_CONTRACT.json"
        )
        RUNTIME = root / "apps/api/hosted_runtime.py"
        HOSTED_APP = root / "apps/api/hosted_app.py"
        POSTGRES_CONNECTION = root / "apps/api/postgres_web_connection.py"
        TELEGRAM_AUTH = root / "apps/api/telegram_auth.py"
        TELEGRAM_READINESS = (
            root
            / "docs/architecture/V10_TELEGRAM_PUBLIC_USER_ACTIVATION_READINESS_CONTRACT.json"
        )
        DOCKERFILE = root / "Dockerfile"
    try:
        payload = _json(CONTRACT)
        _validate_authority(payload)
        _validate_release(payload)
        _validate_runtime(payload)
        _validate_postgres(payload)
        _validate_public_ingress(payload)
        _validate_telegram(payload)
        _validate_post_merge_acceptance(payload)
        _validate_external_gates(payload)
        _validate_provider_convergence_policy(payload)
        _validate_milestones(payload)
        _validate_execution_sequence(payload)
        _validate_merge_readiness(payload)
        _validate_protected_invariants(payload)
    finally:
        (
            ROOT,
            AMENDMENT,
            CONTRACT,
            RUNTIME,
            HOSTED_APP,
            POSTGRES_CONNECTION,
            TELEGRAM_AUTH,
            TELEGRAM_READINESS,
            DOCKERFILE,
        ) = original


def main() -> int:
    try:
        validate()
    except RuntimeError as exc:
        print(f"V10_TIMEWEB_FULL_PRODUCTION_DELIVERY=FAIL code={exc}", file=sys.stderr)
        return 1
    print(
        "V10_TIMEWEB_FULL_PRODUCTION_DELIVERY=PASS "
        "scope=PR584 repository_implementation external_actions=fail_closed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
