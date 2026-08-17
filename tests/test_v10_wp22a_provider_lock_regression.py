from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_wp22a_terraform.ps1"
LOCK = ROOT / "infrastructure" / "cloudflare" / "wp22a" / ".terraform.lock.hcl"
WP5_EVIDENCE_WORKFLOW = ROOT / ".github" / "workflows" / "v10-wp5-local-evidence.yml"


def test_wp22a_derives_content_hash_only_in_isolated_lock_copy() -> None:
    validator = VALIDATOR.read_text(encoding="utf-8")
    source_lock = LOCK.read_text(encoding="utf-8")

    assert "providers lock" in validator
    assert '$fsMirrorArg = "-fs-mirror=$mirrorConfigPath"' in validator
    assert '$platformArg = "-platform=windows_amd64"' in validator
    assert (
        '$providerAddress = "registry.terraform.io/cloudflare/cloudflare"' in validator
    )
    assert "WP22A_OPENTOFU_PROVIDER_LOCK_DERIVATION_FAILED" in validator
    assert "WP22A_SOURCE_PROVIDER_LOCK_MUTATED" in validator
    assert "WP22A_PROVIDER_CONTENT_LOCK_MISSING" in validator
    assert '"h1:[A-Za-z0-9+/]+={0,2}"' in validator
    assert "-lockfile=readonly" in validator

    # The committed source lock remains the reviewed exact ZIP trust anchor, while the
    # validator derives the comparison from the archive authenticated by the bootstrap.
    assert (
        "zh:ca4bf16742a7e59319a482f003d32f6f6abbc5fbf862916ce1a136278e6d420d"
        in source_lock
    )
    assert "$providerArchiveSha256 = (Get-FileHash -Algorithm SHA256" in validator
    assert '[regex]::Escape("zh:$providerArchiveSha256")' in validator
    assert re.search(r'"[0-9a-fA-F]{64}"', validator) is None


def test_wp22a_provider_installation_keeps_registry_fallback_excluded() -> None:
    validator = VALIDATOR.read_text(encoding="utf-8")

    assert 'include = ["registry.terraform.io/cloudflare/cloudflare"]' in validator
    assert 'exclude = ["registry.terraform.io/cloudflare/cloudflare"]' in validator
    assert "filesystem_mirror" in validator


def test_unrelated_wp5_evidence_probe_does_not_route_all_windows_changes() -> None:
    workflow = WP5_EVIDENCE_WORKFLOW.read_text(encoding="utf-8")

    assert "'infrastructure/windows/**'" not in workflow
    assert "'.github/workflows/v10-wp5-local-evidence.yml'" not in workflow
    for path in (
        "infrastructure/windows/collect_owner_node_profile.ps1",
        "infrastructure/windows/measure_wp5_gpu_load.ps1",
        "infrastructure/windows/run_wp5_owner_acceptance.ps1",
        "infrastructure/windows/wp5_node_thresholds.json",
    ):
        assert f"'{path}'" in workflow
    assert "startsWith(github.head_ref, 'v10/wp5-')" in workflow
