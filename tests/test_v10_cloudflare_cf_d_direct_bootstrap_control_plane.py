from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/v10-cloudflare-production-release.yml"
HOSTED_ADAPTER = ROOT / "scripts/bootstrap_v10_cloudflare_neon_hosted_egress.py"
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
    end = source.find("\n      - name:", start + 1)
    if end == -1:
        end = len(source)
    return source[start:end]


def _workflow_job(source: str, job_id: str, next_job_id: str | None) -> str:
    start = source.index(f"  {job_id}:\n")
    if next_job_id is None:
        return source[start:]
    end = source.index(f"  {next_job_id}:\n", start + 1)
    return source[start:end]


def _workflow_job_header(section: str) -> str:
    return section.split("    steps:\n", 1)[0]


_load_legacy_tests()


def test_archived_production_release_preserves_runtime_provisioner_evidence() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    adapter = HOSTED_ADAPTER.read_text(encoding="utf-8")
    rehearse = _workflow_job(source, "rehearse", "bootstrap_production_database")
    hosted = _workflow_job(source, "bootstrap_production_database", "promote")
    promote = _workflow_job(source, "promote", "release_outcome")

    anchor_name = (
        "      - name: Bootstrap production Worker anchor without public route if "
        "absent"
    )
    anchor = rehearse.index(anchor_name)
    probe_start = rehearse.index("      - name: Probe production database secret")
    assert anchor < probe_start

    probe = _workflow_step(rehearse, "Probe production database secret")
    bootstrap = _workflow_step(
        hosted,
        "Bootstrap production database secret through hosted egress",
    )
    confirm = _workflow_step(promote, "Confirm production database secret ready")

    assert "probe-runtime-secret" in probe
    assert "bootstrap_required=false" in probe
    assert "bootstrap_required=true" in probe
    assert "NEON_API_KEY:" not in probe
    assert "NEON_FUNCTION_INVOKE_API_TOKEN" not in probe

    rehearse_header = _workflow_job_header(rehearse)
    hosted_header = _workflow_job_header(hosted)
    promote_header = _workflow_job_header(promote)
    for header in (rehearse_header, hosted_header, promote_header):
        assert "if: ${{ false }}" in header
        assert "false &&" not in header

    assert "needs.rehearse.outputs.production_bootstrap_required == 'true'" not in (
        hosted_header
    )
    assert "runs-on: ubuntu-24.04" in hosted
    assert "python -m scripts.bootstrap_v10_cloudflare_neon_hosted_egress" in bootstrap
    assert "bootstrap-production" in bootstrap
    assert '--expected-sha "$EXPECTED_HEAD"' in bootstrap
    assert "NEON_API_KEY: ${{ secrets.NEON_API_KEY }}" in bootstrap
    assert "NEON_ORG_ID: ${{ secrets.NEON_ORG_ID }}" in bootstrap
    assert "NEON_PROJECT_ID: ${{ secrets.NEON_PROJECT_ID }}" in bootstrap
    assert "set +e" in bootstrap
    assert "hosted_rc=$?" in bootstrap
    assert 'if [ "$hosted_rc" -ne 0 ]; then' in bootstrap
    assert "python -m scripts.probe_v10_neon_authority_diagnostics || true" in bootstrap
    assert 'exit "$hosted_rc"' in bootstrap
    assert "bootstrap_v10_cloudflare_production_database_direct" not in bootstrap
    assert "NEON_FUNCTION_DEPLOY_API_KEY" not in bootstrap
    assert "NEON_FUNCTION_INVOKE_API_TOKEN" not in bootstrap

    custody_index = adapter.index("_resync_production_branch_custody(expected_sha)")
    runtime_index = adapter.index('runtime.run(expected_sha, "production")')
    secret_index = adapter.index("production.put_runtime_secret()")
    assert custody_index < runtime_index < secret_index
    assert 'gated.run(expected_sha, source_branch="main")' in adapter
    assert "bootstrap_origin_sync_token" not in adapter
    assert "fetch_bootstrap_origin_custody" not in adapter
    assert "write_bootstrap_origin_handoff" not in adapter
    assert "branches?limit=100" not in adapter

    assert "probe-runtime-secret" in confirm
    assert "NEON_API_KEY:" not in confirm
    assert "NEON_FUNCTION_INVOKE_API_TOKEN" not in confirm
    assert "NEON_FUNCTION_DEPLOY_API_KEY" not in source
    assert "NEON_FUNCTION_INVOKE_API_TOKEN" not in source
    assert "needs.bootstrap_production_database.result == 'success'" not in (
        promote_header
    )


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
        cutover["production_database_bootstrap_organization_wide_authority_required"]
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
        cutover["production_database_bootstrap_runtime_role_least_privilege_required"]
        is True
    )
    assert cutover["production_database_bootstrap_force_rls_required"] is True
    assert cutover["production_database_bootstrap_runner_temp_dsn_only"] is True
    assert cutover["production_database_bootstrap_dsn_logging_allowed"] is False
    assert cutover["production_database_bootstrap_dsn_artifact_allowed"] is False
    assert (
        cutover[
            "production_database_bootstrap_neon_authority_failure_diagnostic_required"
        ]
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
            "production_database_bootstrap_neon_authority_failure_diagnostic_"
            "non_authoritative"
        ]
        is True
    )
    assert (
        cutover[
            "production_database_bootstrap_neon_authority_failure_original_exit_"
            "preserved"
        ]
        is True
    )
    assert (
        cutover[
            "production_database_bootstrap_neon_authority_failure_may_convert_red_"
            "to_green"
        ]
        is False
    )

    assert cutover["production_database_bootstrap_function_active_transport"] is False
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
    assert cutover["production_database_bootstrap_public_staging_relay_active"] is False
    assert cutover["production_database_bootstrap_function_origin_custody"] == (
        "RESTRICTED_RUNNER_TEMP_TARGET_DESCRIPTOR"
    )
    assert cutover["production_database_bootstrap_tls_minimum_version"] == "TLSv1.2"
