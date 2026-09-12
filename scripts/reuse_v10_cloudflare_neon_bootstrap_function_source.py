from __future__ import annotations

import scripts.bootstrap_v10_cloudflare_builds as builds


def deploy_exact_main_bootstrap_function_if_required(
    api: builds.CloudflareApi,
    expected_sha: str,
) -> bool:
    """Defer legacy Function convergence to bounded direct runtime bootstrap.

    The production runtime secret is the only consumer that previously required the
    Neon Function bootstrap contour. If that secret already exists, no database
    bootstrap work is needed. If it is missing, the production release now uses the
    accepted project-scoped Neon runtime provisioner after the production Worker
    anchor exists, so Function provenance/deployment authority is intentionally not a
    predecessor of exact-main staging acceptance.
    """

    from scripts.manage_v10_cloudflare_production import _runtime_secret_present

    builds._expected_sha(expected_sha)
    try:
        ready = _runtime_secret_present(api)
    except builds.BootstrapStopped as exc:
        if exc.status != 404:
            raise
        ready = False
    if ready:
        print("CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY=SKIPPED_RUNTIME_SECRET_READY")
        return False

    print(
        "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY="
        "DEFERRED_PROJECT_SCOPED_RUNTIME_BOOTSTRAP"
    )
    return False
