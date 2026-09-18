from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

if __package__:
    from .v10_jsonc import loads_jsonc
else:
    from v10_jsonc import loads_jsonc


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/architecture/V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json"
WRANGLER = ROOT / "wrangler.jsonc"
LIVE_VERIFIER = ROOT / "scripts/check_v10_cloudflare_live_release.py"
LIVE_PROBE = ROOT / "scripts/probe_v10_cloudflare_live_release.sh"
POSTMERGE_GATE = ROOT / "scripts/check_v10_cloudflare_postmerge_release_gate.py"
PRODUCTION_MANAGER = ROOT / "scripts/manage_v10_cloudflare_production.py"
PRODUCTION_BUILD = ROOT / "scripts/run_v10_cloudflare_gated_production.py"
PRODUCTION_WORKFLOW = ROOT / ".github/workflows/v10-cloudflare-production-release.yml"
PRODUCTION_BOOTSTRAP = ROOT / "cloudflare/wrangler.bootstrap.production.jsonc"
PACKAGE = ROOT / "package.json"
_REQUIRED_RUNTIME_SECRETS = ["OMNI_V10_POSTGRES_DSN"]
_SECURE_WEB_BUILD = (
    "python scripts/write_v10_cloudflare_build_info.py && "
    "npm ci --ignore-scripts --prefix apps/web && npm run --prefix apps/web build"
)
_CONTAINER_SOURCE_PATH = "/api/internal/v10/cloudflare/container-source"


def _load(path: Path) -> dict[str, Any]:
    try:
        source = path.read_text(encoding="utf-8")
        value = loads_jsonc(source) if path.suffix == ".jsonc" else json.loads(source)
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"CLOUDFLARE_RELEASE_CONTRACT_UNREADABLE:{path}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"CLOUDFLARE_RELEASE_OBJECT_REQUIRED:{path}")
    return value


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(f"CLOUDFLARE_RELEASE_{label}_INVALID")
    return value


def _read(path: Path, label: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError(f"CLOUDFLARE_RELEASE_{label}_UNREADABLE") from exc


def _require_values(
    section: dict[str, Any], expected: dict[str, Any], prefix: str
) -> None:
    for key, value in expected.items():
        if section.get(key) != value:
            raise RuntimeError(f"{prefix}_{key.upper()}_INVALID")


def _require_markers(source: str, markers: tuple[str, ...], code: str) -> None:
    if any(marker not in source for marker in markers):
        raise RuntimeError(code)


def _forbid_markers(source: str, markers: tuple[str, ...], code: str) -> None:
    if any(marker in source for marker in markers):
        raise RuntimeError(code)


def _validate_contract(contract: dict[str, Any]) -> None:
    if contract.get("schema") != "omni-cio.v10.cloudflare-release-acceptance.v1":
        raise RuntimeError("CLOUDFLARE_RELEASE_SCHEMA_INVALID")
    candidate = _object(contract.get("candidate"), "CANDIDATE")
    gate = _object(contract.get("post_merge_gate"), "POST_MERGE_GATE")
    cutover = _object(contract.get("cutover"), "CUTOVER")
    live = _object(contract.get("live_assertions"), "LIVE_ASSERTIONS")
    fail_closed = _object(contract.get("fail_closed"), "FAIL_CLOSED")
    protected = _object(contract.get("protected_invariants"), "PROTECTED_INVARIANTS")
    _validate_candidate(candidate)
    _validate_post_merge_gate(gate)
    _validate_cutover(cutover)
    _validate_live(live)
    if any(value is not False for value in fail_closed.values()):
        raise RuntimeError("CLOUDFLARE_RELEASE_FAIL_CLOSED_INVALID")
    if protected.get("broker_write") is not False:
        raise RuntimeError("CLOUDFLARE_RELEASE_BROKER_WRITE_INVALID")
    if protected.get("trading_methods") is not False:
        raise RuntimeError("CLOUDFLARE_RELEASE_TRADING_METHODS_INVALID")
    if protected.get("REAL_TRADING_ENABLED") is not False:
        raise RuntimeError("CLOUDFLARE_RELEASE_REAL_TRADING_INVALID")


def _validate_candidate(candidate: dict[str, Any]) -> None:
    if candidate.get("milestone") != "CF-C":
        raise RuntimeError("CLOUDFLARE_RELEASE_CANDIDATE_MILESTONE_INVALID")
    if candidate.get("provider_mutation_allowed") is not True:
        raise RuntimeError("CLOUDFLARE_RELEASE_CANDIDATE_MUTATION_INVALID")
    if candidate.get("production_promotion_allowed") is not False:
        raise RuntimeError("CLOUDFLARE_RELEASE_CANDIDATE_PROMOTION_INVALID")
    expected = {
        "staging_environment": "staging",
        "staging_worker_name": "omni-cio-v10-web-staging",
        "staging_deploy_command": "npm run cloudflare:deploy:staging",
        "staging_database_binding": "OMNI_V10_POSTGRES_DSN",
        "staging_container_rollout_required": True,
        "staging_container_image_source_probe_required": True,
        "staging_container_image_source_path": _CONTAINER_SOURCE_PATH,
        "staging_container_image_source_exact_sha_required": True,
        "staging_container_image_source_probe_before_production_bootstrap_required": True,
        "non_production_versions_upload_is_candidate": False,
    }
    _require_values(candidate, expected, "CLOUDFLARE_RELEASE_CANDIDATE")


def _validate_post_merge_gate(gate: dict[str, Any]) -> None:
    expected = {
        "trigger_workflow": "Regression Shield",
        "trigger_event": "workflow_run",
        "required_source_event": "push",
        "required_head_branch": "main",
        "minimum_successful_push_workflows": 11,
        "all_observed_latest_push_workflows_must_succeed": True,
        "current_main_recheck_required": True,
        "recheck_immediately_before_promotion": True,
        "exact_main_staging_rehearsal_required": True,
        "direct_cloudflare_git_production_deploy_allowed": False,
        "release_workflow": ".github/workflows/v10-cloudflare-production-release.yml",
    }
    _require_values(gate, expected, "CLOUDFLARE_RELEASE_POST_MERGE")
    names = gate.get("required_core_push_workflows")
    if names != ["Regression Shield", "V10 Engineering Governance"]:
        raise RuntimeError("CLOUDFLARE_RELEASE_POST_MERGE_CORE_WORKFLOWS_INVALID")


def _validate_cutover(cutover: dict[str, Any]) -> None:
    expected = {
        "milestone": "CF-D",
        "provider_mutation_allowed": True,
        "production_promotion_allowed": True,
        "production_branch": "main",
        "automatic_git_deploy_required": False,
        "gated_post_merge_deploy_required": True,
        "production_worker_name": "omni-cio-v10-web",
        "production_workers_dev": False,
        "default_deploy_command": "npm run cloudflare:deploy",
        "production_build_transport": "WORKERS_BUILDS_GATED_MANUAL_EXACT_MAIN",
        "persistent_production_build_trigger_allowed": False,
        "stale_production_build_quarantine_before_snapshot_required": True,
        "unknown_production_trigger_fails_closed": True,
        "container_rollout_required": True,
        "production_container_image_source_probe_required": True,
        "production_container_image_source_exact_sha_required": True,
        "custom_domain_required": True,
        "custom_domain_suffix": ".ru",
        "production_database_binding": "OMNI_V10_POSTGRES_DSN",
        "production_database_secret_bootstrap_if_missing_only": True,
        "production_database_secret_rotation_each_release_allowed": False,
        "rollback_version_snapshot_required": True,
        "rollback_on_failed_live_acceptance_required": True,
        "post_merge_exact_sha_probe_required": True,
    }
    _require_values(cutover, expected, "CLOUDFLARE_RELEASE_CUTOVER")


def _validate_live(live: dict[str, Any]) -> None:
    expected = {
        "https_only": True,
        "redirects_followed": False,
        "max_response_bytes": 65536,
        "network_probe_script": "scripts/probe_v10_cloudflare_live_release.sh",
        "payload_verifier_script": "scripts/check_v10_cloudflare_live_release.py",
        "python_network_io_allowed": False,
        "trusted_origin_environment_variable": "OMNI_V10_CLOUDFLARE_ORIGIN",
        "trusted_custom_host_environment_variable": "OMNI_V10_CLOUDFLARE_CUSTOM_HOST",
        "workers_dev_suffix": ".workers.dev",
        "ip_literal_origin_allowed": False,
        "local_internal_origin_allowed": False,
        "release_platform": "cloudflare",
        "release_backend": "container",
        "release_static_assets": True,
        "public_multi_user_expectation_must_be_explicit": True,
        "staging_public_multi_user_enabled": False,
        "production_public_multi_user_enabled": False,
        "real_trading_enabled": False,
        "container_source_endpoint": _CONTAINER_SOURCE_PATH,
        "container_source_status": "ok",
        "container_image_source_sha_exact": True,
        "health_status": "ok",
        "health_database": "READY",
    }
    _require_values(live, expected, "CLOUDFLARE_RELEASE_LIVE")


def _validate_wrangler(contract: dict[str, Any]) -> None:
    candidate = _object(contract.get("candidate"), "CANDIDATE")
    cutover = _object(contract.get("cutover"), "CUTOVER")
    wrangler = _load(WRANGLER)
    build = _object(wrangler.get("build"), "WRANGLER_BUILD")
    if build.get("command") != _SECURE_WEB_BUILD:
        raise RuntimeError("CLOUDFLARE_RELEASE_SELF_CONTAINED_BUILD_INVALID")
    if wrangler.get("name") != cutover["production_worker_name"]:
        raise RuntimeError("CLOUDFLARE_RELEASE_PRODUCTION_WORKER_INVALID")
    if wrangler.get("workers_dev") is not False:
        raise RuntimeError("CLOUDFLARE_RELEASE_PRODUCTION_WORKERS_DEV_INVALID")
    _validate_secret_section(wrangler, "PRODUCTION_SECRETS")
    staging = _object(
        _object(wrangler.get("env"), "WRANGLER_ENV").get("staging"), "STAGING"
    )
    if staging.get("name") != candidate["staging_worker_name"]:
        raise RuntimeError("CLOUDFLARE_RELEASE_STAGING_WORKER_INVALID")
    if staging.get("workers_dev") is not True:
        raise RuntimeError("CLOUDFLARE_RELEASE_STAGING_WORKERS_DEV_INVALID")
    _validate_secret_section(staging, "STAGING_SECRETS")
    _validate_staging_container(staging)


def _validate_secret_section(parent: dict[str, Any], label: str) -> None:
    secrets = _object(parent.get("secrets"), label)
    if secrets.get("required") != _REQUIRED_RUNTIME_SECRETS:
        raise RuntimeError(f"CLOUDFLARE_RELEASE_{label}_INVALID")


def _validate_staging_container(staging: dict[str, Any]) -> None:
    expected_container = {
        "class_name": "Backend",
        "image": "./Dockerfile.cloudflare",
        "max_instances": 1,
        "instance_type": "lite",
        "rollout_active_grace_period": 0,
        "rollout_step_percentage": 100,
    }
    if staging.get("containers") != [expected_container]:
        raise RuntimeError("CLOUDFLARE_RELEASE_STAGING_CONTAINER_INVALID")
    durable = _object(staging.get("durable_objects"), "STAGING_DURABLE_OBJECTS")
    if durable.get("bindings") != [{"name": "BACKEND", "class_name": "Backend"}]:
        raise RuntimeError("CLOUDFLARE_RELEASE_STAGING_BINDING_INVALID")
    expected_migrations = [
        {"tag": "cloudflare-container-v1", "new_sqlite_classes": ["Backend"]}
    ]
    if staging.get("migrations") != expected_migrations:
        raise RuntimeError("CLOUDFLARE_RELEASE_STAGING_MIGRATION_INVALID")


def _validate_production_bootstrap() -> None:
    bootstrap = _load(PRODUCTION_BOOTSTRAP)
    expected = {
        "name": "omni-cio-v10-web",
        "main": "./bootstrap-production-worker.js",
        "compatibility_date": "2026-08-29",
        "workers_dev": False,
    }
    _require_values(bootstrap, expected, "CLOUDFLARE_RELEASE_PRODUCTION_BOOTSTRAP")


def _validate_package() -> None:
    package = _load(PACKAGE)
    if package.get("engines") != {"node": "24.18.0", "npm": "10.9.2"}:
        raise RuntimeError("CLOUDFLARE_RELEASE_NODE_BASELINE_INVALID")
    scripts = _object(package.get("scripts"), "SCRIPTS")
    if scripts.get("build") != _SECURE_WEB_BUILD:
        raise RuntimeError("CLOUDFLARE_RELEASE_BUILD_SCRIPT_INVALID")
    if scripts.get("cloudflare:deploy") != (
        "wrangler deploy --containers-rollout=immediate"
    ):
        raise RuntimeError("CLOUDFLARE_RELEASE_PRODUCTION_DEPLOY_INVALID")
    if scripts.get("cloudflare:deploy:staging") != (
        "wrangler deploy --env staging --containers-rollout=immediate"
    ):
        raise RuntimeError("CLOUDFLARE_RELEASE_STAGING_DEPLOY_INVALID")
    dependencies = _object(package.get("dependencies"), "DEPENDENCIES")
    dev_dependencies = _object(package.get("devDependencies"), "DEV_DEPENDENCIES")
    if dependencies.get("@cloudflare/containers") != "0.3.7":
        raise RuntimeError("CLOUDFLARE_RELEASE_CONTAINERS_VERSION_INVALID")
    if dev_dependencies.get("wrangler") != "4.127.1":
        raise RuntimeError("CLOUDFLARE_RELEASE_WRANGLER_VERSION_INVALID")


def _validate_live_verifier() -> None:
    verifier = _read(LIVE_VERIFIER, "VERIFIER")
    _require_markers(
        verifier,
        (
            "CLOUDFLARE_RELEASE_ORIGIN_INVALID",
            "CLOUDFLARE_RELEASE_ORIGIN_NOT_ALLOWED",
            "CLOUDFLARE_RELEASE_ORIGIN_REQUIRED",
            "OMNI_V10_CLOUDFLARE_ORIGIN",
            "OMNI_V10_CLOUDFLARE_CUSTOM_HOST",
            "ipaddress.ip_address(hostname)",
            'hostname.endswith(".workers.dev")',
            '_CONTAINER_SOURCE_PATH = "/api/internal/v10/cloudflare/container-source"',
            "verify_container_source",
            "CLOUDFLARE_RELEASE_CONTAINER_IMAGE_SHA_MISMATCH",
            "CLOUDFLARE_RELEASE_HEALTH_SHA_MISMATCH",
            "CLOUDFLARE_RELEASE_DATABASE_NOT_READY",
            "CLOUDFLARE_RELEASE_PUBLIC_MULTI_USER_EXPECTATION_INVALID",
            "_expected_public_multi_user",
            "_MAX_BYTES = 65_536",
            "sys.stdin.buffer.read(_MAX_BYTES + 1)",
        ),
        "CLOUDFLARE_RELEASE_VERIFIER_GUARD_MISSING",
    )
    _forbid_markers(
        verifier,
        (
            "urllib.request",
            "requests.",
            "httpx.",
            "socket.create_connection",
            "http.client",
        ),
        "CLOUDFLARE_RELEASE_PYTHON_NETWORK_IO_FORBIDDEN",
    )


def _validate_live_probe() -> None:
    probe = _read(LIVE_PROBE, "PROBE")
    _require_markers(
        probe,
        (
            '[[ "$#" -ne 2 ]]',
            'expected_public_multi_user="$2"',
            "true|false)",
            "--proto '=https'",
            "--tlsv1.2",
            "--max-redirs 0",
            "--max-filesize 65536",
            '"${origin}/api/v10/release"',
            '"${origin}/api/internal/v10/cloudflare/container-source"',
            '"${origin}/healthz"',
            'check_v10_cloudflare_live_release.py release "$sha" "$expected_public_multi_user"',
            "check_v10_cloudflare_live_release.py container-source",
            "check_v10_cloudflare_live_release.py health",
        ),
        "CLOUDFLARE_RELEASE_PROBE_GUARD_MISSING",
    )


def _validate_postmerge_gate_source() -> None:
    source = _read(POSTMERGE_GATE, "POSTMERGE_GATE")
    _require_markers(
        source,
        (
            '"branch": "main"',
            '"event": "push"',
            '"head_sha": expected_sha',
            "CLOUDFLARE_POSTMERGE_MAIN_SUPERSEDED",
            "CLOUDFLARE_POSTMERGE_PUSH_WORKFLOW_NOT_SUCCESS",
            "required_core_push_workflows",
            "minimum_successful_push_workflows",
        ),
        "CLOUDFLARE_RELEASE_POSTMERGE_GATE_GUARD_MISSING",
    )


def _validate_production_manager_source() -> None:
    source = _read(PRODUCTION_MANAGER, "PRODUCTION_MANAGER")
    _require_markers(
        source,
        (
            "CLOUDFLARE_PRODUCTION_DATABASE_SECRET=REUSED",
            "CLOUDFLARE_PRODUCTION_DATABASE_SECRET=BOOTSTRAP_REQUIRED",
            'if not zone_name.endswith(".ru")',
            '"service": _PRODUCTION_WORKER',
            "CLOUDFLARE_PRODUCTION_ROLLBACK_SNAPSHOT=READY",
            "/deployments",
            "CLOUDFLARE_PRODUCTION_SPLIT_DEPLOYMENT_FORBIDDEN",
        ),
        "CLOUDFLARE_RELEASE_PRODUCTION_MANAGER_GUARD_MISSING",
    )
    _forbid_markers(
        source,
        (
            "print(dsn)",
            "print(runtime_uri)",
        ),
        "CLOUDFLARE_RELEASE_PRODUCTION_MANAGER_SECRET_OUTPUT_FORBIDDEN",
    )


def _validate_production_build_source() -> None:
    source = _read(PRODUCTION_BUILD, "PRODUCTION_BUILD")
    _require_markers(
        source,
        (
            '"branch": _SOURCE_BRANCH',
            '_SOURCE_BRANCH = "main"',
            '_DEPLOY_COMMAND = "npm run cloudflare:deploy"',
            "CLOUDFLARE_PRODUCTION_AUTODEPLOY_FORBIDDEN",
            "CLOUDFLARE_PRODUCTION_TRIGGER_RACE",
            "CLOUDFLARE_PRODUCTION_STALE_BUILDS=QUARANTINED",
            "CLOUDFLARE_PRODUCTION_PROVIDER_ACTIVITY=QUARANTINED",
            "--quarantine-only",
            "CLOUDFLARE_PRODUCTION_GATED_TRIGGER=QUARANTINED",
            "CLOUDFLARE_CF_D_PRODUCTION_BUILD=DEPLOYED",
        ),
        "CLOUDFLARE_RELEASE_PRODUCTION_BUILD_GUARD_MISSING",
    )


def _validate_production_workflow(live: dict[str, Any]) -> None:
    workflow = _read(PRODUCTION_WORKFLOW, "PRODUCTION_WORKFLOW")
    staging_expected = str(live["staging_public_multi_user_enabled"]).lower()
    production_expected = str(live["production_public_multi_user_enabled"]).lower()
    staging_probe = (
        'bash scripts/probe_v10_cloudflare_live_release.sh "$EXPECTED_HEAD" '
        + staging_expected
    )
    production_probe = (
        'bash scripts/probe_v10_cloudflare_live_release.sh "$EXPECTED_HEAD" '
        + production_expected
    )
    staging_start = workflow.find("Accept exact-main staging rehearsal")
    production_start = workflow.find("Accept canonical Cloudflare production release")
    if staging_start < 0 or production_start <= staging_start:
        raise RuntimeError("CLOUDFLARE_RELEASE_PRODUCTION_WORKFLOW_GUARD_MISSING")
    staging_block = workflow[staging_start:production_start]
    production_block = workflow[production_start:]
    if staging_probe not in staging_block or production_probe not in production_block:
        raise RuntimeError(
            "CLOUDFLARE_RELEASE_PUBLIC_MULTI_USER_EXPECTATION_WIRING_INVALID"
        )
    markers = (
        "workflow_run:",
        "- Regression Shield",
        "github.event.workflow_run.conclusion == 'success'",
        "check_v10_cloudflare_postmerge_release_gate",
        "--source-branch main",
        "validate-domain-config",
        "probe-runtime-secret",
        "Quarantine stale production Builds before rollback snapshot",
        "--quarantine-only",
        "snapshot-active-deployment",
        "run_v10_cloudflare_gated_production",
        "attach-domain",
        "probe_v10_cloudflare_live_release.sh",
        "wrangler rollback",
        "previous_version_id",
        "OMNI_V10_PRODUCTION_DEPLOY_ATTEMPTED=1",
    )
    _require_markers(
        workflow,
        markers,
        "CLOUDFLARE_RELEASE_PRODUCTION_WORKFLOW_GUARD_MISSING",
    )
    _forbid_markers(
        workflow,
        (
            "on:\n  push:\n    branches:\n      - main",
            "continue-on-error: true",
        ),
        "CLOUDFLARE_RELEASE_DIRECT_PRODUCTION_AUTODEPLOY_FORBIDDEN",
    )


def validate() -> None:
    contract = _load(CONTRACT)
    _validate_contract(contract)
    _validate_wrangler(contract)
    _validate_production_bootstrap()
    _validate_package()
    _validate_live_verifier()
    _validate_live_probe()
    _validate_postmerge_gate_source()
    _validate_production_manager_source()
    _validate_production_build_source()
    _validate_production_workflow(
        _object(contract.get("live_assertions"), "LIVE_ASSERTIONS")
    )


def main() -> int:
    try:
        validate()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("V10 Cloudflare CF-C/CF-D release acceptance contract passed.")
    print("Candidate: isolated staging Worker + Container exact-SHA rollout")
    print("Container image source: exact-SHA serving probe required before bootstrap")
    print("Production: post-merge exact-main gated Workers Build only")
    print("Direct Cloudflare Git production auto-deploy: FORBIDDEN")
    print("Production workers.dev: DISABLED; canonical .ru Custom Domain required")
    print("Production database secret: reuse; bootstrap only when absent")
    print("Live probe: HTTPS-only curl + networkless Python payload verifier")
    print("Rollback: captured prior Worker version + fail-closed live acceptance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
