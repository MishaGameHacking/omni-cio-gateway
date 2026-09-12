from __future__ import annotations

import scripts.bootstrap_v10_cloudflare_builds as builds
import scripts.deploy_v10_cloudflare_neon_bootstrap_function as deployer
from scripts.neon_function_invocation_credential import (
    function_invocation_credential,
    project_invocation_authority_from_env,
)


def _reuse_exact_source(expected_sha: str) -> bool:
    """Accept exact source before unrelated Neon metadata reads.

    Bootstrap-origin custody already binds the target branch/cell to the exact staging
    release. When Neon rejects unauthenticated Function ingress, the only additional
    capability required to prove source reuse is the pre-provisioned branch-scoped
    ``functions:invoke`` secret. Project/branch/Function metadata reads remain part of
    the mutation/convergence path and are deliberately not predecessors of this
    read-only exact-source proof.
    """

    deployer._assert_exact_head(expected_sha)
    target = deployer.read_bootstrap_origin_handoff()
    _, source_digest = deployer._deployment_bundle()

    try:
        if deployer._probe_source_provenance(target, source_digest):
            print("CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY=SKIPPED_EXACT_SOURCE_READY")
            return True
    except builds.BootstrapStopped as exc:
        if exc.code != deployer._SOURCE_PROVENANCE_AUTH_REQUIRED:
            raise

        project_token, project_id = project_invocation_authority_from_env()
        with function_invocation_credential(
            project_token,
            project_id,
            target.branch_id,
        ) as invocation_token:
            if deployer._probe_source_provenance(
                target,
                source_digest,
                invocation_token,
            ):
                print(
                    "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY="
                    "SKIPPED_EXACT_SOURCE_READY_AUTHENTICATED"
                )
                return True

    return False


def deploy_exact_main_bootstrap_function_if_required(
    api: builds.CloudflareApi,
    expected_sha: str,
) -> bool:
    """Reuse exact source first; delegate real drift to hardened convergence."""

    from scripts.manage_v10_cloudflare_production import _runtime_secret_present

    try:
        ready = _runtime_secret_present(api)
    except builds.BootstrapStopped as exc:
        if exc.status != 404:
            raise
        ready = False
    if ready:
        print("CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY=SKIPPED_RUNTIME_SECRET_READY")
        return False

    if _reuse_exact_source(expected_sha):
        return False

    return deployer.deploy_exact_main_bootstrap_function(expected_sha)
