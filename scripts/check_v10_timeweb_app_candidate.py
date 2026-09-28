from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
_WORKFLOW_RELATIVE = ".github/workflows/v10-timeweb-app-candidate.yml"
CONTRACT = ROOT / "docs/architecture/V10_TIMEWEB_APP_EXACT_SHA_CANDIDATE_CONTRACT.json"
CONTROLLER = ROOT / "scripts/timeweb_app_release.py"
WORKFLOW = ROOT / _WORKFLOW_RELATIVE
RUNTIME = ROOT / "apps/api/hosted_runtime.py"
DOCKERFILE = ROOT / "Dockerfile"
RUNBOOK = ROOT / "docs/operations/V10_TIMEWEB_APP_EXACT_SHA_CANDIDATE_RUNBOOK.md"

_EXPECTED_PLAIN_ENV = {
    "OMNI_V10_HOSTED_RUNTIME": "1",
    "OMNI_V10_PUBLIC_HOSTNAME": "omnicio.ru",
    "OMNI_V10_POSTGRES_RUNTIME_ROLE": "omni_cio_hosted_api",
    "OMNI_V10_TRUSTED_EDGE_TLS_TERMINATED": "true",
}
_API_INVALID = "TIMEWEB_APP_CANDIDATE_API_INVALID"
_RUNTIME_ENV_INVALID = "TIMEWEB_APP_CANDIDATE_RUNTIME_ENV_INVALID"
_LIVEZ_PATH = "/livez"
_DOCKER_BIND_ALL_IPV4 = ".".join(("0", "0", "0", "0"))


def _text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError(
            f"TIMEWEB_APP_CANDIDATE_SOURCE_UNREADABLE:{path.name}"
        ) from exc


def _json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(_text(path))
    except json.JSONDecodeError as exc:
        raise RuntimeError("TIMEWEB_APP_CANDIDATE_CONTRACT_INVALID") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("TIMEWEB_APP_CANDIDATE_CONTRACT_INVALID")
    return payload


def _dict(value: object, code: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(code)
    return value


def _string_set(value: object, code: str) -> set[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise RuntimeError(code)
    return set(value)


def _strict_field_matches(value: object, expected: object) -> bool:
    if isinstance(expected, bool):
        return value is expected
    return value == expected


def _require_strict_fields(
    payload: dict[str, Any],
    expected: dict[str, object],
    code: str,
) -> None:
    for key, expected_value in expected.items():
        if not _strict_field_matches(payload.get(key), expected_value):
            raise RuntimeError(code)


def _validate_root(payload: dict[str, Any]) -> None:
    expected_root = {
        "schema": "omni-cio.v10.timeweb-app-exact-sha-candidate.v1",
        "status": "REPAIR_SOURCE_IMPLEMENTED_EXACT_HEAD_VERIFICATION_REQUIRED",
        "owning_system_update": "TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED",
        "owning_pr": 584,
        "milestone": "P2_TIMEWEB_EXACT_SHA_CANDIDATE",
    }
    for key, expected in expected_root.items():
        if payload.get(key) != expected:
            raise RuntimeError(f"TIMEWEB_APP_CANDIDATE_CONTRACT_DRIFT:{key}")


def _validate_source_authority(payload: dict[str, Any]) -> None:
    source = _dict(
        payload.get("source_authority"),
        "TIMEWEB_APP_CANDIDATE_SOURCE_AUTHORITY_INVALID",
    )
    expected = {
        "repository": "MishaGameHacking/omni-cio-gateway",
        "branch": "main",
        "expected_sha_format": "LOWERCASE_HEX_40",
        "expected_sha_must_equal_observed_main": True,
    }
    if source != expected:
        raise RuntimeError("TIMEWEB_APP_CANDIDATE_SOURCE_AUTHORITY_INVALID")


def _validate_target(payload: dict[str, Any]) -> None:
    target = _dict(payload.get("target"), "TIMEWEB_APP_CANDIDATE_TARGET_INVALID")
    expected = {
        "application_name": "omni-cio-v10",
        "type": "backend",
        "framework": "docker",
        "auto_deploy_allowed": False,
        "application_must_preexist": True,
        "application_creation_authorized_by_controller": False,
        "documented_create_api_network_binding_available": False,
        "initial_create_via_documented_api_allowed": False,
        "immutable_private_network_required_at_creation": True,
        "owner_panel_creation_required_when_create_api_lacks_network": True,
        "settings_patch_authorized_by_controller": False,
        "canonical_public_hostname": "omnicio.ru",
        "canonical_domain_attachment_allowed_in_p2": False,
        "candidate_hostname_env": "OMNI_V10_CANDIDATE_HOSTNAME",
        "canonical_repository_clone_url": (
            "https://github.com/MishaGameHacking/omni-cio-gateway.git"
        ),
        "repository_clone_url_identity_required": True,
        "provider_decorated_repository_full_name_allowed_when_clone_url_exact": True,
        "provider_decorated_repository_name_allowed_when_clone_url_exact": True,
        "provider_repository_metadata_must_be_nonempty": True,
        "github_clone_url_equivalent_case_normalization_allowed": True,
        "github_clone_url_default_https_port_allowed": True,
        "github_clone_url_embedded_credentials_allowed": False,
    }
    if target != expected:
        raise RuntimeError("TIMEWEB_APP_CANDIDATE_TARGET_INVALID")


def _validate_provider_api(payload: dict[str, Any]) -> None:
    api = _dict(payload.get("provider_api"), _API_INVALID)
    expected_reads = {
        "GET /api/v1/apps",
        "GET /api/v1/apps/{app_id}",
        "GET /api/v1/apps/{app_id}/deploys",
    }
    expected_mutations = {"POST /api/v1/apps/{app_id}/deploy"}
    if api.get("base") != "https://api.timeweb.cloud":
        raise RuntimeError(_API_INVALID)
    if _string_set(api.get("read_endpoints"), _API_INVALID) != expected_reads:
        raise RuntimeError(_API_INVALID)
    if _string_set(api.get("mutation_endpoints"), _API_INVALID) != expected_mutations:
        raise RuntimeError(_API_INVALID)
    if api.get("deploy_body_keys") != ["commit_sha"]:
        raise RuntimeError(_API_INVALID)
    if api.get("mutation_retry_allowed") is not False:
        raise RuntimeError("TIMEWEB_APP_CANDIDATE_MUTATION_RETRY_FORBIDDEN")
    if api.get("ambiguous_mutation_reconcile_with_get_only") is not True:
        raise RuntimeError("TIMEWEB_APP_CANDIDATE_RECONCILIATION_INVALID")
    if (
        api.get("successful_but_unprovable_mutation_response_reconcile_with_get_only")
        is not True
    ):
        raise RuntimeError("TIMEWEB_APP_CANDIDATE_RECONCILIATION_INVALID")
    if api.get("existing_inflight_exact_sha_adoption_required") is not True:
        raise RuntimeError("TIMEWEB_APP_CANDIDATE_RECONCILIATION_INVALID")
    if api.get("multiple_inflight_exact_sha_terminal") is not True:
        raise RuntimeError("TIMEWEB_APP_CANDIDATE_RECONCILIATION_INVALID")
    reconcile_budget = api.get("ambiguous_reconcile_minimum_budget_seconds")
    if type(reconcile_budget) is not int or reconcile_budget < 60:
        raise RuntimeError("TIMEWEB_APP_CANDIDATE_RECONCILIATION_INVALID")
    pagination_expected = {
        "deploy_history_pagination_required": True,
        "deploy_history_page_size": 100,
        "deploy_history_max_pages": 100,
        "deploy_history_total_stability_required": True,
        "deploy_history_identity_uniqueness_required": True,
    }
    for key, expected in pagination_expected.items():
        if api.get(key) != expected:
            raise RuntimeError("TIMEWEB_APP_CANDIDATE_PAGINATION_INVALID")


def _validate_runtime_contract(payload: dict[str, Any]) -> None:
    runtime = _dict(payload.get("runtime"), _RUNTIME_ENV_INVALID)
    if runtime.get("required_plain_env") != _EXPECTED_PLAIN_ENV:
        raise RuntimeError(_RUNTIME_ENV_INVALID)
    expected_modes = {
        "preactivation": {
            "PUBLIC_MULTI_USER_ENABLED": "false",
            "OMNI_V10_TELEGRAM_LOGIN_ENABLED": "false",
            "canonical_domain_state": "FORBIDDEN",
            "p5_live_evidence_sha256_required": False,
        },
        "live-operable": {
            "PUBLIC_MULTI_USER_ENABLED": "true",
            "OMNI_V10_TELEGRAM_LOGIN_ENABLED": "true",
            "canonical_domain_state": "REQUIRED",
            "p5_live_evidence_sha256_required": True,
        },
    }
    if runtime.get("activation_modes") != expected_modes:
        raise RuntimeError(_RUNTIME_ENV_INVALID)
    if runtime.get("release_sha_env") != "OMNI_V10_RELEASE_SHA":
        raise RuntimeError(_RUNTIME_ENV_INVALID)
    if runtime.get("release_sha_must_equal_expected_sha") is not True:
        raise RuntimeError(_RUNTIME_ENV_INVALID)
    _require_strict_fields(
        runtime,
        {
            "postgres_dsn_env": "OMNI_V10_POSTGRES_DSN",
            "postgres_dsn_required": True,
            "postgres_private_hostaddr_env": "OMNI_V10_POSTGRES_PRIVATE_HOSTADDR",
            "postgres_private_hostaddr_required": True,
            "postgres_private_network_cidr_env": "OMNI_V10_POSTGRES_PRIVATE_NETWORK_CIDR",
            "postgres_private_network_cidr_required": True,
            "postgres_private_route_rfc1918_required": True,
            "postgres_private_hostaddr_must_be_inside_cidr": True,
            "postgres_tls_hostname_identity_must_remain_dsn_host": True,
            "postgres_binding_sha256_env": "OMNI_V10_POSTGRES_BINDING_SHA256",
            "postgres_binding_sha256_required": True,
            "postgres_binding_sha256_sensitive": False,
            "postgres_binding_sha256_excludes_password": True,
            "postgres_binding_sha256_binds_host_port_database_user_tls": True,
            "postgres_binding_sha256_source": "P3_PREPARE_ACCEPTED_OUTPUT",
            "postgres_binding_sha256_required_before_app_bootstrap": True,
            "provider_masked_sensitive_value_allowed": True,
            "vk_login_must_be_false_or_absent": True,
            "retired_provider_env_forbidden": True,
            "telegram_runtime_credential_custody_accepted_by_p2": False,
        },
        _RUNTIME_ENV_INVALID,
    )


def _validate_acceptance(payload: dict[str, Any]) -> None:
    acceptance = _dict(
        payload.get("acceptance"),
        "TIMEWEB_APP_CANDIDATE_ACCEPTANCE_INVALID",
    )
    expected = {
        "liveness_path": _LIVEZ_PATH,
        "platform_liveness_source": "TIMEWEB_PANEL_HEALTHCHECK",
        "panel_healthcheck_path": _LIVEZ_PATH,
        "dockerfile_healthcheck_path": _LIVEZ_PATH,
        "panel_healthcheck_overrides_dockerfile_healthcheck": True,
        "liveness_https_required": True,
        "liveness_redirect_allowed": False,
        "liveness_status": "ok",
        "liveness_release_sha_must_equal_expected_sha": True,
        "liveness_startup_database_connection_required": False,
        "liveness_database_probe_on_request_allowed": False,
        "database_readiness_owns_database_probe": True,
        "last_known_good_sha_must_come_from_successful_provider_history": True,
        "last_known_good_order_field": "ended_at",
        "last_known_good_order_must_be_provider_timestamp": True,
        "ambiguous_latest_history_terminal": True,
        "automatic_rollback_authorized": False,
        "live_operable_release_requires_p5_live_evidence_sha256": True,
        "deploy_readiness_minimum_budget_seconds": 300,
        "deploy_readiness_maximum_budget_seconds": 900,
        "liveness_retry_on_transient_or_stale_route_required": True,
        "liveness_retry_minimum_budget_seconds": 120,
        "liveness_retry_maximum_budget_seconds": 300,
        "database_readiness_path": "/healthz",
        "database_readiness_https_required": True,
        "database_readiness_redirect_allowed": False,
        "database_readiness_status": "ok",
        "database_readiness_database": "READY",
        "database_readiness_synthetic_preview": False,
        "database_readiness_release_sha_must_equal_expected_sha": True,
        "database_readiness_retry_on_transient_or_unavailable_required": True,
        "database_readiness_retry_minimum_budget_seconds": 120,
        "database_readiness_retry_maximum_budget_seconds": 300,
    }
    if acceptance != expected:
        raise RuntimeError("TIMEWEB_APP_CANDIDATE_ACCEPTANCE_INVALID")


def _validate_github(payload: dict[str, Any]) -> None:
    github = _dict(payload.get("github"), "TIMEWEB_APP_CANDIDATE_GITHUB_INVALID")
    expected = {
        "workflow": _WORKFLOW_RELATIVE,
        "environment": "timeweb-production",
        "manual_dispatch_only": True,
        "provider_binding": "TIMEWEB_CLOUD_API_TOKEN",
        "provider_binding_step_scope_only": True,
    }
    if github != expected:
        raise RuntimeError("TIMEWEB_APP_CANDIDATE_GITHUB_INVALID")


def _validate_orchestration(payload: dict[str, Any]) -> None:
    orchestration = _dict(
        payload.get("orchestration"),
        "TIMEWEB_APP_CANDIDATE_ORCHESTRATION_INVALID",
    )
    expected = {
        "p3_observe_before_physical_candidate_allowed": True,
        "p3_prepare_before_physical_candidate_required": True,
        "app_creation_after_p3_prepare_required": True,
        "p3_accept_before_physical_candidate_allowed": False,
        "candidate_healthz_requires_prepared_database": True,
        "p3_accept_requires_current_candidate_livez_and_healthz": True,
    }
    if orchestration != expected:
        raise RuntimeError("TIMEWEB_APP_CANDIDATE_ORCHESTRATION_INVALID")


def _validate_invariants(payload: dict[str, Any]) -> None:
    invariants = _dict(
        payload.get("protected_invariants"),
        "TIMEWEB_APP_CANDIDATE_INVARIANTS_INVALID",
    )
    expected = {
        "preactivation_is_default": True,
        "public_activation_without_p5_live_evidence_allowed": False,
        "partial_public_telegram_activation_allowed": False,
        "OMNI_V10_VK_ID_LOGIN_ENABLED": False,
        "broker_write": False,
        "trading_methods": False,
        "REAL_TRADING_ENABLED": False,
        "canonical_domain_mutation": False,
        "production_database_cutover": False,
    }
    if invariants != expected:
        raise RuntimeError("TIMEWEB_APP_CANDIDATE_INVARIANTS_INVALID")


def _validate_contract(payload: dict[str, Any]) -> None:
    _validate_root(payload)
    _validate_source_authority(payload)
    _validate_target(payload)
    _validate_provider_api(payload)
    _validate_runtime_contract(payload)
    _validate_acceptance(payload)
    _validate_github(payload)
    _validate_orchestration(payload)
    _validate_invariants(payload)


def _validate_controller(path: Path) -> None:
    source = _text(path)
    required = (
        'API_BASE = "https://api.timeweb.cloud"',
        'CANONICAL_APP_NAME = "omni-cio-v10"',
        'CANONICAL_REPOSITORY = "MishaGameHacking/omni-cio-gateway"',
        'CANONICAL_REPOSITORY_PATH = "/MishaGameHacking/omni-cio-gateway"',
        "def _canonical_repository_url(",
        'parsed.hostname == "github.com"',
        "parsed.username is None",
        "parsed.password is None",
        "port in {None, 443}",
        "path.casefold() == CANONICAL_REPOSITORY_PATH.casefold()",
        "TIMEWEB_APP_RELEASE_REPOSITORY_INVALID",
        'CANONICAL_BRANCH = "main"',
        'CANONICAL_FRAMEWORK = "docker"',
        'DEPLOY_CONFIRMATION = "DEPLOY_EXACT_TIMEWEB_APP_COMMIT"',
        "{_COMMIT_SHA_KEY: expected}",
        '"POST",',
        'f"/api/v1/apps/{safe}/deploy"',
        "TIMEWEB_APP_RELEASE_MAIN_SHA_DRIFT",
        "TIMEWEB_APP_RELEASE_AUTODEPLOY_FORBIDDEN",
        "TIMEWEB_APP_RELEASE_PREMATURE_CANONICAL_DOMAIN",
        "TIMEWEB_APP_RELEASE_CANONICAL_DOMAIN_REQUIRED",
        "RUNTIME_MODE_LIVE_OPERABLE",
        "TIMEWEB_APP_RELEASE_P5_LIVE_EVIDENCE_REQUIRED",
        "TIMEWEB_APP_RELEASE_POSTGRES_DSN_REQUIRED",
        "POSTGRES_BINDING_SHA256_ENV",
        "TIMEWEB_APP_RELEASE_POSTGRES_BINDING_INVALID",
        "TIMEWEB_MASKED_SENSITIVE_VALUE",
        "TIMEWEB_APP_RELEASE_RETIRED_PROVIDER_ENV_PRESENT",
        "TIMEWEB_APP_RELEASE_AMBIGUOUS_UNRESOLVED",
        "TIMEWEB_APP_RELEASE_MULTIPLE_INFLIGHT_EXACT_SHA",
        "_inflight_exact_deploy_id",
        "_DEPLOY_RECONCILE_DELAYS",
        "_POLL_DELAYS",
        "_LIVEZ_RETRY_DELAYS",
        "_MAX_DEPLOY_HISTORY_PAGES = 100",
        "offset={offset}",
        "TIMEWEB_APP_RELEASE_DEPLOY_HISTORY_CHANGED",
        "TIMEWEB_APP_RELEASE_DEPLOY_HISTORY_TRUNCATED",
        "TIMEWEB_APP_RELEASE_DEPLOY_HISTORY_TOO_LARGE",
        "TIMEWEB_APP_RELEASE_DEPLOY_HISTORY_DUPLICATE_ID",
        "TIMEWEB_APP_RELEASE_LIVEZ_SHA_DRIFT",
        "POSTGRES_PRIVATE_HOSTADDR_ENV",
        "POSTGRES_PRIVATE_NETWORK_CIDR_ENV",
        "TIMEWEB_APP_RELEASE_PRIVATE_ROUTE_REQUIRED",
        "TIMEWEB_APP_RELEASE_PRIVATE_ROUTE_INVALID",
        "_HEALTHZ_RETRY_DELAYS",
        "_verify_healthz",
        "TIMEWEB_APP_RELEASE_HEALTHZ_DATABASE_NOT_READY",
        "TIMEWEB_APP_RELEASE_HEALTHZ_SYNTHETIC_PREVIEW_FORBIDDEN",
        "TIMEWEB_APP_RELEASE_HEALTHZ_SHA_DRIFT",
    )
    if any(marker not in source for marker in required):
        raise RuntimeError("TIMEWEB_APP_CANDIDATE_CONTROLLER_MARKER_MISSING")
    forbidden = (
        '"DELETE"',
        '"PATCH"',
        '"PUT"',
        '"/api/v1/apps",\n            operation=',
        "/logs",
        "/stop",
    )
    if any(marker in source for marker in forbidden):
        raise RuntimeError("TIMEWEB_APP_CANDIDATE_CONTROLLER_AUTHORITY_WIDENED")


def _validate_workflow(path: Path) -> None:
    source = _text(path)
    required = (
        "workflow_dispatch:",
        "environment: timeweb-production",
        "TIMEWEB_CLOUD_API_TOKEN: ${{ secrets.TIMEWEB_CLOUD_API_TOKEN }}",
        'test "$EXPECTED_HEAD" = "$OBSERVED_MAIN"',
        "refs/heads/main:refs/remotes/origin/main",
        "python -m scripts.verify_v10_timeweb_github_environment",
        "--environment-name timeweb-production",
        "python -m scripts.check_v10_timeweb_app_candidate",
        "python -m scripts.timeweb_app_release",
        '--observed-main-sha "$OBSERVED_MAIN"',
        "DEPLOY_EXACT_TIMEWEB_APP_COMMIT",
        "runtime_mode",
        "p5_live_evidence_sha256",
        '--runtime-mode "$REQUESTED_RUNTIME_MODE"',
        '--p5-live-evidence-sha256 "$P5_LIVE_EVIDENCE"',
    )
    if any(marker not in source for marker in required):
        raise RuntimeError("TIMEWEB_APP_CANDIDATE_WORKFLOW_DRIFT")
    forbidden = (
        "on:\n  push:",
        "pull_request:",
        "workflow_run:",
        "schedule:",
        "continue-on-error",
        "permissions: write-all",
        "createApp",
        "/api/v1/apps/{app_id}/stop",
    )
    if any(marker in source for marker in forbidden):
        raise RuntimeError("TIMEWEB_APP_CANDIDATE_WORKFLOW_AUTHORITY_WIDENED")
    binding = "TIMEWEB_CLOUD_API_TOKEN: ${{ secrets.TIMEWEB_CLOUD_API_TOKEN }}"
    if source.count(binding) != 1:
        raise RuntimeError("TIMEWEB_APP_CANDIDATE_BINDING_SCOPE_INVALID")
    if source.find(binding) < source.find("steps:"):
        raise RuntimeError("TIMEWEB_APP_CANDIDATE_BINDING_SCOPE_INVALID")


def _validate_runbook(path: Path) -> None:
    source = _text(path)
    required = (
        "OMNI_V10_POSTGRES_PRIVATE_HOSTADDR",
        "OMNI_V10_POSTGRES_PRIVATE_NETWORK_CIDR",
        "OMNI_V10_POSTGRES_BINDING_SHA256",
        "P3 `prepare`",
        "panel health path",
        "priority over",
        "Dockerfile `HEALTHCHECK`",
        "database=READY",
        "synthetic_preview=false",
        "P3 `accept`",
    )
    if any(marker not in source for marker in required):
        raise RuntimeError("TIMEWEB_APP_CANDIDATE_RUNBOOK_DRIFT")


def _validate_dockerfile(path: Path) -> None:
    source = _text(path)
    required = (
        "EXPOSE 8080",
        "HEALTHCHECK",
        f"http://localhost:8080{_LIVEZ_PATH}",
        "apps.api.hosted_runtime:create_app",
        "--host",
        _DOCKER_BIND_ALL_IPV4,
        "--port",
        "8080",
    )
    if any(marker not in source for marker in required):
        raise RuntimeError("TIMEWEB_APP_CANDIDATE_DOCKERFILE_DRIFT")
    if "http://localhost:8080/healthz" in source:
        raise RuntimeError("TIMEWEB_APP_CANDIDATE_DOCKERFILE_LIVENESS_DRIFT")


def _validate_runtime(path: Path) -> None:
    source = _text(path)
    required = (
        '"OMNI_V10_CANDIDATE_HOSTNAME"',
        '"OMNI_V10_POSTGRES_PRIVATE_HOSTADDR"',
        '"OMNI_V10_POSTGRES_PRIVATE_NETWORK_CIDR"',
        "prepare_timeweb_postgres_private_target",
        "_optional_candidate_hostname",
        'additional_hosts=("localhost", *candidate_hosts)',
    )
    if any(marker not in source for marker in required):
        raise RuntimeError("TIMEWEB_APP_CANDIDATE_RUNTIME_HOST_SUPPORT_MISSING")


def validate(root: Path = ROOT) -> None:
    contract = (
        root / "docs/architecture/V10_TIMEWEB_APP_EXACT_SHA_CANDIDATE_CONTRACT.json"
    )
    controller = root / "scripts/timeweb_app_release.py"
    workflow = root / _WORKFLOW_RELATIVE
    runtime = root / "apps/api/hosted_runtime.py"
    dockerfile = root / "Dockerfile"
    runbook = root / "docs/operations/V10_TIMEWEB_APP_EXACT_SHA_CANDIDATE_RUNBOOK.md"
    _validate_contract(_json(contract))
    _validate_controller(controller)
    _validate_workflow(workflow)
    _validate_runtime(runtime)
    _validate_dockerfile(dockerfile)
    _validate_runbook(runbook)


def main() -> int:
    try:
        validate()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("V10_TIMEWEB_APP_EXACT_SHA_CANDIDATE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
