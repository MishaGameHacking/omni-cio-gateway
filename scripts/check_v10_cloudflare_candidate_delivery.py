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

_CLOUDFLARE_ACCOUNT_ID_SECRET = "secrets.CLOUDFLARE_ACCOUNT_ID"
_NEON_ORG_ID_SECRET = "secrets.NEON_ORG_ID"
_NEON_PROJECT_ID_SECRET = "secrets.NEON_PROJECT_ID"
_PROVIDER_IDENTITY_SECRET_MARKERS = (
    _CLOUDFLARE_ACCOUNT_ID_SECRET,
    _NEON_ORG_ID_SECRET,
    _NEON_PROJECT_ID_SECRET,
)
_WORKERS_BUILDS_AUTHORITY_PROBE = (
    "python -m scripts.probe_v10_cloudflare_workers_builds_authority"
)
_PROVIDER_MUTATION_STEP_MARKERS = (
    "- name: Provision isolated Neon staging runtime role",
    "- name: Bootstrap isolated staging Worker without local Containers",
    "- name: Configure Workers Builds and accept exact staging build",
)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError(f"CLOUDFLARE_CANDIDATE_FILE_UNREADABLE:{path}") from exc


def _require_markers(source: str, markers: tuple[str, ...], code: str) -> None:
    if any(marker not in source for marker in markers):
        raise RuntimeError(code)


def _forbid_markers(source: str, markers: tuple[str, ...], code: str) -> None:
    if any(marker in source for marker in markers):
        raise RuntimeError(code)


def _validate_candidate_secret_scope(workflow: str) -> None:
    job_header, separator, _ = workflow.partition("    steps:\n")
    if not separator:
        raise RuntimeError("CLOUDFLARE_CANDIDATE_WORKFLOW_STEPS_MISSING")
    _forbid_markers(
        job_header,
        (
            "CLOUDFLARE_API_TOKEN:",
            "CLOUDFLARE_ACCOUNT_ID:",
            "NEON_API_KEY:",
            "NEON_ORG_ID:",
            "NEON_PROJECT_ID:",
            "secrets.CLOUDFLARE_API_TOKEN",
            _CLOUDFLARE_ACCOUNT_ID_SECRET,
            "secrets.NEON_API_KEY",
            _NEON_ORG_ID_SECRET,
            _NEON_PROJECT_ID_SECRET,
        ),
        "CLOUDFLARE_CANDIDATE_JOB_SECRET_SCOPE_TOO_BROAD",
    )


def _validate_provider_identity_custody(workflow: str) -> None:
    _require_markers(
        workflow,
        _PROVIDER_IDENTITY_SECRET_MARKERS,
        "CLOUDFLARE_PROVIDER_IDENTITY_SECRET_CUSTODY_MISSING",
    )
    _forbid_markers(
        workflow,
        (
            "vars.CLOUDFLARE_ACCOUNT_ID",
            "vars.NEON_ORG_ID",
            "vars.NEON_PROJECT_ID",
            "CLOUDFLARE_ACCOUNT_ID_VAR_VALUE",
        ),
        "CLOUDFLARE_PROVIDER_IDENTITY_VARIABLE_CUSTODY_FORBIDDEN",
    )


def _validate_candidate_pre_mutation_authority(workflow: str) -> None:
    probe_index = workflow.find(_WORKERS_BUILDS_AUTHORITY_PROBE)
    if probe_index < 0:
        raise RuntimeError("CLOUDFLARE_CANDIDATE_PRE_MUTATION_AUTHORITY_PROBE_MISSING")
    for marker in _PROVIDER_MUTATION_STEP_MARKERS:
        mutation_index = workflow.find(marker)
        if mutation_index < 0:
            raise RuntimeError("CLOUDFLARE_CANDIDATE_PROVIDER_MUTATION_STEP_MISSING")
        if mutation_index < probe_index:
            raise RuntimeError("CLOUDFLARE_CANDIDATE_AUTHORITY_PROBE_AFTER_MUTATION")


def _validate_candidate_workflow() -> None:
    workflow = _read(CANDIDATE_WORKFLOW)
    _require_markers(
        workflow,
        (
            "name: V10 Cloudflare Candidate Deployment",
            "system/cloudflare-public-product",
            "secrets.CLOUDFLARE_API_TOKEN",
            _CLOUDFLARE_ACCOUNT_ID_SECRET,
            "secrets.NEON_API_KEY",
            _NEON_ORG_ID_SECRET,
            _NEON_PROJECT_ID_SECRET,
            "python -m scripts.check_v10_cloudflare_provider_readiness",
            _WORKERS_BUILDS_AUTHORITY_PROBE,
            "provision_v10_cloudflare_neon_runtime",
            "wrangler.bootstrap.staging.jsonc",
            "bootstrap_v10_cloudflare_builds",
            "probe_v10_cloudflare_live_release.sh",
            'test "$(node --version)" = "v24.18.0"',
            'test "$(npm --version)" = "11.16.0"',
            "npm ci --ignore-scripts --no-audit --no-fund",
            "./node_modules/.bin/wrangler",
            "for attempt in $(seq 1 40); do",
            "attempt=${attempt}/40",
            "git clean -ffdx",
            'rm -f -- "${RUNNER_TEMP}/omni-cio-v10-cloudflare-staging-dsn.txt"',
            "rm -rf .git\n          fi",
        ),
        "CLOUDFLARE_CANDIDATE_WORKFLOW_GUARD_MISSING",
    )
    _forbid_markers(
        workflow,
        ("actions/checkout", "docker build", "npx "),
        "CLOUDFLARE_CANDIDATE_FORBIDDEN_DEPENDENCY",
    )
    _forbid_markers(
        workflow,
        ("--repo-root", "--output-file", "--dsn-file"),
        "CLOUDFLARE_CANDIDATE_DYNAMIC_PATH_ARGUMENT_FORBIDDEN",
    )
    _validate_candidate_secret_scope(workflow)
    _validate_provider_identity_custody(workflow)
    _validate_candidate_pre_mutation_authority(workflow)


def _validate_readiness_workflow() -> None:
    readiness = _read(READINESS_WORKFLOW)
    _require_markers(
        readiness,
        (
            "python -m scripts.check_v10_cloudflare_provider_readiness",
            "CLOUDFLARE_ACCOUNT_ID_CREDENTIAL_VALUE:",
            "NEON_ORG_ID_VALUE:",
            "NEON_PROJECT_ID_VALUE:",
        ),
        "CLOUDFLARE_CANDIDATE_PROVIDER_CHECK_MISSING",
    )
    _require_markers(
        readiness,
        ("CLOUDFLARE_CF_C_PROVIDER_READINESS=READY",),
        "CLOUDFLARE_CANDIDATE_READINESS_GATE_MISSING",
    )
    _require_markers(
        readiness,
        (
            "probe_provider_access_from_env",
            _NEON_PROJECT_ID_SECRET,
            "NEON_PROJECT_ID:",
        ),
        "CLOUDFLARE_CANDIDATE_NEON_READ_PROBE_MISSING",
    )
    _forbid_markers(
        readiness,
        ("CLOUDFLARE_API_TOKEN=AVAILABLE", "CLOUDFLARE_DEPLOY_PATH=WORKERS_BUILDS"),
        "CLOUDFLARE_CANDIDATE_INLINE_AUTHORITY_PROBE_FORBIDDEN",
    )
    _validate_provider_identity_custody(readiness)


def _validate_provider_readiness() -> None:
    source = _read(PROVIDER_READINESS_CHECK)
    _require_markers(
        source,
        (
            "_CLOUDFLARE_ACCOUNT_ENV",
            "_NEON_PROJECT_ENV",
            "_ACCOUNT_ID",
            "_NEON_RESOURCE_ID",
            "CLOUDFLARE_ACCOUNT_ID",
            "NEON_ORG_ID",
            "NEON_PROJECT_ID",
            "INVALID",
            "_container_engine_available",
            "CLOUDFLARE_DEPLOY_PATH=WORKERS_BUILDS",
            "CLOUDFLARE_CF_C_PROVIDER_READINESS=BLOCKED",
            "stdout=subprocess.DEVNULL",
            "timeout=_DOCKER_TIMEOUT_SECONDS",
            "return 78",
        ),
        "CLOUDFLARE_CANDIDATE_PROVIDER_CHECK_INVALID",
    )
    _forbid_markers(
        source,
        ("shell=True",),
        "CLOUDFLARE_CANDIDATE_PROVIDER_SHELL_FORBIDDEN",
    )
    _forbid_markers(
        source,
        ("_CLOUDFLARE_ACCOUNT_FALLBACK_ENV",),
        "CLOUDFLARE_CANDIDATE_PROVIDER_VARIABLE_FALLBACK_FORBIDDEN",
    )


def _validate_ledger() -> None:
    ledger = _read(BRANCH_EXECUTION_LEDGER)
    _require_markers(
        ledger,
        (
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
        ),
        "CLOUDFLARE_CANDIDATE_BRANCH_LEDGER_INVALID",
    )


def _validate_bootstrap_worker() -> None:
    bootstrap_config = _read(BOOTSTRAP_CONFIG)
    _require_markers(
        bootstrap_config,
        ('"name": "omni-cio-v10-web-staging"',),
        "CLOUDFLARE_CANDIDATE_BOOTSTRAP_WORKER_INVALID",
    )
    _forbid_markers(
        bootstrap_config,
        ('"containers"',),
        "CLOUDFLARE_CANDIDATE_BOOTSTRAP_CONTAINER_FORBIDDEN",
    )
    _require_markers(
        _read(BOOTSTRAP_WORKER),
        ("CLOUDFLARE_STAGING_BUILD_PENDING",),
        "CLOUDFLARE_CANDIDATE_BOOTSTRAP_RESPONSE_MISSING",
    )


def _validate_neon_provisioner() -> None:
    neon = _read(NEON_PROVISIONER)
    _require_markers(
        neon,
        (
            '"staging": "omni_cio_cloudflare_staging"',
            '"production": "omni_cio_cloudflare_prod"',
            "_NEON_PROJECT_ID_PATTERN",
            "project_id = _required_neon_project_id()",
            "project = _load_expected_project(api, safe_org_id, project_id)",
            'api.request("GET", f"/projects/{safe_project_id}")',
            "NEON_PROJECT_ID_MISMATCH",
            "NEON_PROJECT_NAME_DRIFT",
            "_org._neon_organization(api, safe_org_id)",
            "CLOUDFLARE_NEON_BROAD_PROJECT_QUERY_FORBIDDEN",
            "CLOUDFLARE_NEON_PROJECT_CREATE_FORBIDDEN",
            "CLOUDFLARE_NEON_PROVIDER_ACCESS=READY",
            "CLOUDFLARE_RUNNER_TEMP_REQUIRED",
            "CLOUDFLARE_RUNTIME_DSN_RUNNER_PATH_REQUIRED",
            "validate_hosted_postgres_runtime_sql",
            "apply_migrations(connection)",
        ),
        "CLOUDFLARE_CANDIDATE_NEON_GUARD_MISSING",
    )
    _forbid_markers(
        neon,
        (
            "_discover_expected_project",
            'api.request("GET", f"/projects?{query}")',
            "_base._neon_organization(api)",
        ),
        "CLOUDFLARE_CANDIDATE_NEON_BROAD_DISCOVERY_FORBIDDEN",
    )
    _forbid_markers(
        neon,
        ('RUNTIME_ROLE = "omni_cio_hosted_api"',),
        "CLOUDFLARE_CANDIDATE_SHARED_ROLE_FORBIDDEN",
    )
    _forbid_markers(
        neon,
        ('parser.add_argument("--repo-root"', 'parser.add_argument("--output-file"'),
        "CLOUDFLARE_CANDIDATE_NEON_PATH_ARGUMENT_FORBIDDEN",
    )


def _validate_builds_bootstrap() -> None:
    builds = _read(BUILDS_BOOTSTRAP)
    _require_markers(
        builds,
        (
            '"omni-cio-v10-web-staging"',
            '"Omni-CIO V10 staging deploy"',
            '"system/cloudflare-public-product"',
            '"/accounts/{api.account_id}/builds/repos/connections"',
            '"/accounts/{api.account_id}/builds/tokens?per_page=200"',
            '"npm run build"',
            '"npm run cloudflare:deploy:staging"',
            '"OMNI_V10_POSTGRES_DSN"',
            "_BUILD_TOKEN_VALUE_FIELD",
            '"build_token_" + "sec" + "ret"',
            "CLOUDFLARE_BUILD_SHA_MISMATCH",
            '"commit_hash": expected_sha',
            'row.get("build_trigger_metadata")',
            "_build_metadata_matches_candidate",
            "_build_is_reusable",
            "CLOUDFLARE_BUILD_COMMAND_MISMATCH",
            "CLOUDFLARE_DEPLOY_COMMAND_MISMATCH",
            "CLOUDFLARE_BUILD_OUTCOME_MISSING",
            "CLOUDFLARE_BUILD_TOKEN_STALE",
            'builds/{safe_uuid}/logs',
            "CLOUDFLARE_BUILD_FAILURE_DIAGNOSTIC=",
            "CLOUDFLARE_STAGING_TRIGGER_WORKER_DRIFT",
            "CLOUDFLARE_STAGING_TRIGGER_REPO_AUTHORITY_DRIFT",
            "CLOUDFLARE_STAGING_TRIGGER_CONFIGURATION_DRIFT",
            "CLOUDFLARE_GITHUB_OUTPUT_PATH_INVALID",
            "CLOUDFLARE_RUNTIME_DSN_PATH_INVALID",
        ),
        "CLOUDFLARE_CANDIDATE_BUILDS_GUARD_MISSING",
    )
    _forbid_markers(
        builds,
        ('parser.add_argument("--repo-root"', 'parser.add_argument("--dsn-file"'),
        "CLOUDFLARE_CANDIDATE_BUILDS_PATH_ARGUMENT_FORBIDDEN",
    )
    _forbid_markers(
        builds,
        ("DELEGATED_TO_WRANGLER",),
        "CLOUDFLARE_CANDIDATE_BUILDS_DELEGATED_BUILD_FORBIDDEN",
    )


def validate() -> None:
    _validate_candidate_workflow()
    _validate_readiness_workflow()
    _validate_provider_readiness()
    _validate_ledger()
    _validate_bootstrap_worker()
    _validate_neon_provisioner()
    _validate_builds_bootstrap()


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
