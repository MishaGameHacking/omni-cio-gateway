from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/v10-cloudflare-production-release.yml"
CONTRACT = ROOT / "docs/architecture/V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json"
_LEGACY = ROOT / "tests/_v10_cloudflare_cf_d_direct_bootstrap_legacy.py"
_REPLACED = {
    "test_production_release_uses_direct_function_not_public_staging_relay",
    "test_direct_bootstrap_transport_is_machine_readable",
}


def _load_legacy_tests() -> None:
    spec = importlib.util.spec_from_file_location("_cf_d_direct_legacy", _LEGACY)
    if spec is None or spec.loader is None:
        raise RuntimeError("CF_D_DIRECT_LEGACY_TEST_MODULE_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name in dir(module):
        if name.startswith("test_") and name not in _REPLACED:
            globals()[name] = getattr(module, name)


def _workflow_step(source: str, name: str) -> str:
    start = source.index(f"      - name: {name}")
    end = source.index("\n      - name:", start + 1)
    return source[start:end]


_load_legacy_tests()


def test_production_release_uses_project_scoped_runtime_provisioner() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    anchor_name = (
        "      - name: Bootstrap production Worker anchor without public route if "
        "absent"
    )
    anchor = source.index(anchor_name)
    probe_start = source.index("      - name: Probe production database secret")
    bootstrap_start = source.index(
        "      - name: Bootstrap production database secret if missing"
    )
    confirm_start = source.index(
        "      - name: Confirm production database secret ready"
    )
    assert anchor < probe_start < bootstrap_start < confirm_start

    probe = _workflow_step(source, "Probe production database secret")
    bootstrap = _workflow_step(
        source,
        "Bootstrap production database secret if missing",
    )
    confirm = _workflow_step(source, "Confirm production database secret ready")

    assert "probe-runtime-secret" in probe
    assert "bootstrap_required=false" in probe
    assert "bootstrap_required=true" in probe
    assert "NEON_API_KEY:" not in probe
    assert "NEON_FUNCTION_INVOKE_API_TOKEN" not in probe

    assert "python -m scripts.provision_v10_cloudflare_neon_runtime" in bootstrap
    assert '--expected-sha "$EXPECTED_HEAD"' in bootstrap
    assert "--environment production" in bootstrap
    assert "NEON_API_KEY: ${{ secrets.NEON_API_KEY }}" in bootstrap
    assert "NEON_ORG_ID: ${{ secrets.NEON_ORG_ID }}" in bootstrap
    assert "NEON_PROJECT_ID: ${{ secrets.NEON_PROJECT_ID }}" in bootstrap
    assert "set +e" in bootstrap
    assert "neon_rc=$?" in bootstrap
    assert 'if [ "$neon_rc" -ne 0 ]; then' in bootstrap
    assert "python -m scripts.probe_v10_neon_authority_diagnostics || true" in bootstrap
    assert 'exit "$neon_rc"' in bootstrap
    assert bootstrap.index(
        "python -m scripts.provision_v10_cloudflare_neon_runtime"
    ) < bootstrap.index("python -m scripts.probe_v10_neon_authority_diagnostics")
    assert bootstrap.index(
        "python -m scripts.probe_v10_neon_authority_diagnostics"
    ) < bootstrap.index('test -s "$dsn_file"')
    assert "put-runtime-secret" in bootstrap
    assert "bootstrap_v10_cloudflare_production_database_direct" not in bootstrap
    assert "NEON_FUNCTION_DEPLOY_API_KEY" not in bootstrap
    assert "NEON_FUNCTION_INVOKE_API_TOKEN" not in bootstrap

    assert "probe-runtime-secret" in confirm
    assert "NEON_API_KEY:" not in confirm
    assert "NEON_FUNCTION_INVOKE_API_TOKEN" not in confirm
    assert "NEON_FUNCTION_DEPLOY_API_KEY" not in source
    assert "NEON_FUNCTION_INVOKE_API_TOKEN" not in source


def test_direct_bootstrap_transport_is_machine_readable() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    candidate = contract["candidate"]
    cutover = contract["cutover"]

    assert (
        candidate["staging_bootstrap_origin_private_control_plane_handoff_for_main"]
        is True
    )
    assert candidate["staging_neon_management_api_credential_binding"] == (
        "NEON_API_KEY"
    )
    assert candidate["staging_neon_authority_exposed_only_if_database_secret_missing"]
    assert not candidate["staging_legacy_function_deploy_credential_active_dependency"]

    assert cutover["production_database_bootstrap_active_transport"] == (
        "PROJECT_SCOPED_NEON_RUNTIME_PROVISIONER"
    )
    assert (
        cutover["production_database_bootstrap_project_scoped_credential_binding"]
        == "NEON_API_KEY"
    )
    assert (
        cutover[
            "production_database_bootstrap_project_scoped_credential_environment_alias"
        ]
        == "NEON_API_KEY"
    )
    assert not cutover[
        "production_database_bootstrap_runtime_management_function_deploy_alias_allowed"
    ]
    legacy_dependency = (
        "production_database_bootstrap_legacy_function_deploy_credential_"
        "active_dependency"
    )
    assert not cutover[legacy_dependency]
    assert (
        cutover["production_database_bootstrap_project_scoped_authority_required"]
        is True
    )
    assert (
        cutover[
            "production_database_bootstrap_organization_wide_authority_required"
        ]
        is False
    )
    assert (
        cutover[
            "production_database_bootstrap_management_authority_only_if_secret_missing"
        ]
        is True
    )
    assert cutover["production_database_bootstrap_exact_sha_required"] is True
    assert cutover["production_database_bootstrap_postgres18_required"] is True
    assert cutover["production_database_bootstrap_migrations_required"] is True
    assert cutover["production_database_bootstrap_runtime_role"] == (
        "omni_cio_cloudflare_prod"
    )
    assert (
        cutover[
            "production_database_bootstrap_runtime_role_least_privilege_required"
        ]
        is True
    )
    assert cutover["production_database_bootstrap_force_rls_required"] is True
    assert cutover["production_database_bootstrap_runner_temp_dsn_only"] is True
    assert cutover["production_database_bootstrap_dsn_logging_allowed"] is False
    assert cutover["production_database_bootstrap_dsn_artifact_allowed"] is False
    assert (
        cutover["production_database_bootstrap_neon_authority_failure_diagnostic_required"]
        is True
    )
    assert (
        cutover[
            "production_database_bootstrap_neon_authority_failure_diagnostic_read_only"
        ]
        is True
    )
    assert (
        cutover[
            "production_database_bootstrap_neon_authority_failure_diagnostic_non_authoritative"
        ]
        is True
    )
    assert (
        cutover[
            "production_database_bootstrap_neon_authority_failure_original_exit_preserved"
        ]
        is True
    )
    assert (
        cutover[
            "production_database_bootstrap_neon_authority_failure_may_convert_red_to_green"
        ]
        is False
    )

    assert (
        cutover["production_database_bootstrap_function_active_transport"] is False
    )
    assert (
        cutover["production_database_bootstrap_function_retained_legacy_component"]
        is True
    )
    assert cutover["production_database_bootstrap_github_oidc_required"] is False
    assert (
        cutover[
            "production_database_bootstrap_github_oidc_required_for_legacy_"
            "function_transport"
        ]
        is True
    )
    assert (
        cutover["production_database_bootstrap_public_staging_relay_active"] is False
    )
    assert cutover["production_database_bootstrap_function_origin_custody"] == (
        "RESTRICTED_RUNNER_TEMP_TARGET_DESCRIPTOR"
    )
    assert cutover["production_database_bootstrap_tls_minimum_version"] == "TLSv1.2"
