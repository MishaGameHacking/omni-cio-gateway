from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_WORKFLOW = ROOT / ".github/workflows/v10-cloudflare-candidate-deploy.yml"
READINESS_WORKFLOW = ROOT / ".github/workflows/v10-cloudflare-provider-readiness.yml"
PROVIDER_READINESS_CHECK = ROOT / "scripts/check_v10_cloudflare_provider_readiness.py"
BRANCH_EXECUTION_LEDGER = (
    ROOT / "docs/updates/CLOUDFLARE_PUBLIC_PRODUCT_INTEGRATED_EXECUTION_LEDGER.md"
)
BOOTSTRAP_CONFIG = ROOT / "cloudflare/wrangler.bootstrap.staging.jsonc"
BOOTSTRAP_WORKER = ROOT / "cloudflare/bootstrap-staging-worker.js"
NEON_PROVISIONER = ROOT / "scripts/provision_v10_cloudflare_neon_runtime.py"
BUILDS_BOOTSTRAP = ROOT / "scripts/bootstrap_v10_cloudflare_builds.py"


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError(f"CLOUDFLARE_CANDIDATE_FILE_UNREADABLE:{path}") from exc


def validate() -> None:
    workflow = _read(CANDIDATE_WORKFLOW)
    for marker in (
        "name: V10 Cloudflare Candidate Deployment",
        "system/cloudflare-public-product",
        "secrets.CLOUDFLARE_API_TOKEN",
        "vars.CLOUDFLARE_ACCOUNT_ID",
        "secrets.NEON_API_KEY",
        "vars.NEON_ORG_ID",
        "provision_v10_cloudflare_neon_runtime",
        "wrangler.bootstrap.staging.jsonc",
        "bootstrap_v10_cloudflare_builds",
        "probe_v10_cloudflare_live_release.sh",
        "git clean -ffdx",
    ):
        if marker not in workflow:
            raise RuntimeError("CLOUDFLARE_CANDIDATE_WORKFLOW_GUARD_MISSING")
    if "actions/checkout" in workflow or "docker build" in workflow:
        raise RuntimeError("CLOUDFLARE_CANDIDATE_FORBIDDEN_DEPENDENCY")
    for forbidden in ("--repo-root", "--output-file", "--dsn-file"):
        if forbidden in workflow:
            raise RuntimeError("CLOUDFLARE_CANDIDATE_DYNAMIC_PATH_ARGUMENT_FORBIDDEN")

    readiness = _read(READINESS_WORKFLOW)
    if "python -m scripts.check_v10_cloudflare_provider_readiness" not in readiness:
        raise RuntimeError("CLOUDFLARE_CANDIDATE_PROVIDER_CHECK_MISSING")
    if "CLOUDFLARE_CF_C_PROVIDER_READINESS=READY" not in readiness:
        raise RuntimeError("CLOUDFLARE_CANDIDATE_READINESS_GATE_MISSING")
    if "probe_provider_access_from_env" not in readiness:
        raise RuntimeError("CLOUDFLARE_CANDIDATE_NEON_READ_PROBE_MISSING")
    for inline_marker in (
        "CLOUDFLARE_API_TOKEN=AVAILABLE",
        "CLOUDFLARE_DEPLOY_PATH=WORKERS_BUILDS",
    ):
        if inline_marker in readiness:
            raise RuntimeError("CLOUDFLARE_CANDIDATE_INLINE_AUTHORITY_PROBE_FORBIDDEN")

    provider_readiness = _read(PROVIDER_READINESS_CHECK)
    for marker in (
        "_CLOUDFLARE_ACCOUNT_PRIMARY_ENV",
        "_CLOUDFLARE_ACCOUNT_FALLBACK_ENV",
        "_container_engine_available",
        "CLOUDFLARE_DEPLOY_PATH=WORKERS_BUILDS",
        "CLOUDFLARE_CF_C_PROVIDER_READINESS=BLOCKED",
        "stdout=subprocess.DEVNULL",
        "timeout=_DOCKER_TIMEOUT_SECONDS",
        "return 78",
    ):
        if marker not in provider_readiness:
            raise RuntimeError("CLOUDFLARE_CANDIDATE_PROVIDER_CHECK_INVALID")
    if "shell=True" in provider_readiness:
        raise RuntimeError("CLOUDFLARE_CANDIDATE_PROVIDER_SHELL_FORBIDDEN")

    ledger = _read(BRANCH_EXECUTION_LEDGER)
    for marker in (
        "BRANCH-LOCAL EXECUTION STATE — NOT ACCEPTED MAIN AUTHORITY",
        "CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED",
        "system/cloudflare-public-product",
        "GitHub dashboard issue: `#412`",
        "CF-A",
        "CF-B",
        "CF-C",
        "CF-D",
        "HEAD FREEZE",
        "PUBLIC_MULTI_USER_ENABLED=false",
    ):
        if marker not in ledger:
            raise RuntimeError("CLOUDFLARE_CANDIDATE_BRANCH_LEDGER_INVALID")

    bootstrap_config = _read(BOOTSTRAP_CONFIG)
    if '"name": "omni-cio-v10-web-staging"' not in bootstrap_config:
        raise RuntimeError("CLOUDFLARE_CANDIDATE_BOOTSTRAP_WORKER_INVALID")
    if '"containers"' in bootstrap_config:
        raise RuntimeError("CLOUDFLARE_CANDIDATE_BOOTSTRAP_CONTAINER_FORBIDDEN")
    if "CLOUDFLARE_STAGING_BUILD_PENDING" not in _read(BOOTSTRAP_WORKER):
        raise RuntimeError("CLOUDFLARE_CANDIDATE_BOOTSTRAP_RESPONSE_MISSING")

    neon = _read(NEON_PROVISIONER)
    for marker in (
        '"staging": "omni_cio_cloudflare_staging"',
        '"production": "omni_cio_cloudflare_prod"',
        "_base._neon_organization(api)",
        '"search": _base.NEON_PROJECT_NAME',
        "CLOUDFLARE_NEON_BROAD_PROJECT_QUERY_FORBIDDEN",
        "CLOUDFLARE_NEON_PROJECT_CREATE_FORBIDDEN",
        "CLOUDFLARE_NEON_PROVIDER_ACCESS=READY",
        "CLOUDFLARE_RUNNER_TEMP_REQUIRED",
        "CLOUDFLARE_RUNTIME_DSN_RUNNER_PATH_REQUIRED",
        "validate_hosted_postgres_runtime_sql",
        "apply_migrations(connection)",
    ):
        if marker not in neon:
            raise RuntimeError("CLOUDFLARE_CANDIDATE_NEON_GUARD_MISSING")
    if 'RUNTIME_ROLE = "omni_cio_hosted_api"' in neon:
        raise RuntimeError("CLOUDFLARE_CANDIDATE_SHARED_ROLE_FORBIDDEN")
    for forbidden in (
        'parser.add_argument("--repo-root"',
        'parser.add_argument("--output-file"',
    ):
        if forbidden in neon:
            raise RuntimeError("CLOUDFLARE_CANDIDATE_NEON_PATH_ARGUMENT_FORBIDDEN")

    builds = _read(BUILDS_BOOTSTRAP)
    for marker in (
        '"omni-cio-v10-web-staging"',
        '"Omni-CIO V10 staging deploy"',
        '"system/cloudflare-public-product"',
        '"/accounts/{api.account_id}/builds/repos/connections"',
        '"/accounts/{api.account_id}/builds/tokens?per_page=200"',
        '"npm run cloudflare:deploy:staging"',
        '"OMNI_V10_POSTGRES_DSN"',
        "_BUILD_TOKEN_VALUE_FIELD",
        '"build_token_" + "sec" + "ret"',
        "CLOUDFLARE_BUILD_SHA_MISMATCH",
        "CLOUDFLARE_GITHUB_OUTPUT_PATH_INVALID",
        "CLOUDFLARE_RUNTIME_DSN_PATH_INVALID",
    ):
        if marker not in builds:
            raise RuntimeError("CLOUDFLARE_CANDIDATE_BUILDS_GUARD_MISSING")
    for forbidden in (
        'parser.add_argument("--repo-root"',
        'parser.add_argument("--dsn-file"',
    ):
        if forbidden in builds:
            raise RuntimeError("CLOUDFLARE_CANDIDATE_BUILDS_PATH_ARGUMENT_FORBIDDEN")


def main() -> int:
    try:
        validate()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("V10 Cloudflare CF-C candidate delivery contract passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
