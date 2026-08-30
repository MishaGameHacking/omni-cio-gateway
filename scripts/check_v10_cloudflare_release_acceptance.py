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
PACKAGE = ROOT / "package.json"
_REQUIRED_RUNTIME_SECRETS = ["OMNI_V10_POSTGRES_DSN"]
_SECURE_WEB_BUILD = (
    "python scripts/write_v10_cloudflare_build_info.py && "
    "npm ci --ignore-scripts --prefix apps/web && npm run --prefix apps/web build"
)


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
    cutover = _object(contract.get("cutover"), "CUTOVER")
    live = _object(contract.get("live_assertions"), "LIVE_ASSERTIONS")
    fail_closed = _object(contract.get("fail_closed"), "FAIL_CLOSED")
    protected = _object(contract.get("protected_invariants"), "PROTECTED_INVARIANTS")
    _validate_candidate(candidate)
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
        "non_production_versions_upload_is_candidate": False,
    }
    _require_values(candidate, expected, "CLOUDFLARE_RELEASE_CANDIDATE")


def _validate_cutover(cutover: dict[str, Any]) -> None:
    if cutover.get("milestone") != "CF-D" or cutover.get("production_branch") != "main":
        raise RuntimeError("CLOUDFLARE_RELEASE_CUTOVER_INVALID")
    if cutover.get("automatic_git_deploy_required") is not True:
        raise RuntimeError("CLOUDFLARE_RELEASE_AUTOMATIC_DEPLOY_REQUIRED")
    if cutover.get("default_deploy_command") != "npx wrangler deploy":
        raise RuntimeError("CLOUDFLARE_RELEASE_DEPLOY_COMMAND_INVALID")


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
        "public_multi_user_enabled": False,
        "real_trading_enabled": False,
        "health_status": "ok",
        "health_database": "READY",
    }
    _require_values(live, expected, "CLOUDFLARE_RELEASE_LIVE")


def _validate_wrangler(contract: dict[str, Any]) -> None:
    candidate = _object(contract.get("candidate"), "CANDIDATE")
    wrangler = _load(WRANGLER)
    build = _object(wrangler.get("build"), "WRANGLER_BUILD")
    if build.get("command") != _SECURE_WEB_BUILD:
        raise RuntimeError("CLOUDFLARE_RELEASE_SELF_CONTAINED_BUILD_INVALID")
    if wrangler.get("workers_dev") is not True:
        raise RuntimeError("CLOUDFLARE_RELEASE_WORKERS_DEV_REQUIRED")
    _validate_secret_section(wrangler, "PRODUCTION_SECRETS")
    staging = _object(
        _object(wrangler.get("env"), "WRANGLER_ENV").get("staging"), "STAGING"
    )
    if staging.get("name") != candidate["staging_worker_name"]:
        raise RuntimeError("CLOUDFLARE_RELEASE_STAGING_WORKER_INVALID")
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


def _validate_package() -> None:
    package = _load(PACKAGE)
    if package.get("engines") != {"node": "24.18.0", "npm": "10.9.2"}:
        raise RuntimeError("CLOUDFLARE_RELEASE_NODE_BASELINE_INVALID")
    scripts = _object(package.get("scripts"), "SCRIPTS")
    if scripts.get("build") != _SECURE_WEB_BUILD:
        raise RuntimeError("CLOUDFLARE_RELEASE_BUILD_SCRIPT_INVALID")
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
            "CLOUDFLARE_RELEASE_HEALTH_SHA_MISMATCH",
            "CLOUDFLARE_RELEASE_DATABASE_NOT_READY",
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
            '[[ "$#" -ne 1 ]]',
            "--proto '=https'",
            "--tlsv1.2",
            "--max-redirs 0",
            "--max-filesize 65536",
            '"${origin}/api/v10/release"',
            '"${origin}/healthz"',
            "check_v10_cloudflare_live_release.py release",
            "check_v10_cloudflare_live_release.py health",
        ),
        "CLOUDFLARE_RELEASE_PROBE_GUARD_MISSING",
    )


def validate() -> None:
    contract = _load(CONTRACT)
    _validate_contract(contract)
    _validate_wrangler(contract)
    _validate_package()
    _validate_live_verifier()
    _validate_live_probe()


def main() -> int:
    try:
        validate()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("V10 Cloudflare CF-C/CF-D release acceptance contract passed.")
    print("Candidate: isolated staging Worker + Container rollout")
    print("Dependency install lifecycle scripts: DISABLED")
    print("Required runtime secret: OMNI_V10_POSTGRES_DSN in staging and production")
    print("Production branch: main")
    print("Automatic deploy command: npx wrangler deploy")
    print("Live probe: HTTPS-only curl + networkless Python payload verifier")
    print("Live exact-SHA/database acceptance remains fail-closed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
