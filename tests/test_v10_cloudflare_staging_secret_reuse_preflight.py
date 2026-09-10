from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
READINESS = ROOT / ".github/workflows/v10-cloudflare-provider-readiness.yml"
CANDIDATE = ROOT / ".github/workflows/v10-cloudflare-candidate-deploy.yml"
CONTRACT = ROOT / "docs/architecture/V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json"

_SECRET_PROBE = "python -m scripts.probe_v10_cloudflare_staging_runtime_secret"
_NEON_PROBE = "probe_provider_access_from_env()"
_BOOTSTRAP_OUTPUT = "bootstrap_required"
_RECOVERY_CONDITION = "steps.staging_secret.outputs.bootstrap_required == 'true'"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_provider_readiness_reuses_existing_staging_secret_before_neon_api() -> None:
    source = _read(READINESS)
    secret_probe = source.index(_SECRET_PROBE)
    neon_probe = source.index(_NEON_PROBE)
    ready = source.index("CLOUDFLARE_CF_C_PROVIDER_READINESS=READY")
    assert secret_probe < neon_probe < ready
    assert _BOOTSTRAP_OUTPUT in source
    assert _RECOVERY_CONDITION in source
    assert "CLOUDFLARE_STAGING_DATABASE_ROLE=UNCHANGED" in source
    assert "CLOUDFLARE_STAGING_DATABASE_RECOVERY=REQUIRED" in source


def test_candidate_neon_api_and_role_rotation_are_recovery_only() -> None:
    source = _read(CANDIDATE)
    secret_probe = source.index(_SECRET_PROBE)
    neon_probe = source.index(_NEON_PROBE)
    provision = source.index("python -m scripts.provision_v10_cloudflare_neon_runtime")
    candidate = source.index("python -m scripts.run_v10_cloudflare_gated_candidate")
    assert secret_probe < neon_probe < provision < candidate
    assert source.count(_RECOVERY_CONDITION) >= 2
    assert "CLOUDFLARE_STAGING_DATABASE_ROLE=UNCHANGED" in source
    assert "CLOUDFLARE_STAGING_DATABASE_RECOVERY=REQUIRED" in source


def test_staging_database_reuse_policy_is_machine_readable() -> None:
    contract = json.loads(_read(CONTRACT))
    candidate = contract["candidate"]
    assert candidate["staging_database_secret_reuse_before_neon_management_api_required"] is True
    assert candidate["staging_neon_management_api_required_only_if_database_secret_missing"] is True
    assert candidate["staging_database_secret_reuse_must_not_rotate_runtime_password"] is True
