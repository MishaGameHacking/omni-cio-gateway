from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROVISION = ROOT / "infrastructure" / "windows" / "provision_wp6_privilege_boundary.ps1"
ROLLBACK = ROOT / "infrastructure" / "windows" / "rollback_wp6_privilege_boundary.ps1"
COLLECTOR = ROOT / "infrastructure" / "windows" / "collect_wp6_identity_profile.ps1"
AUDIT_WORKFLOW = ROOT / ".github" / "workflows" / "v10-wp6-identity-audit.yml"
SELF_HOSTED = ROOT / ".github" / "workflows" / "self-hosted-windows-smoke.yml"
RUNBOOK = ROOT / "docs" / "operations" / "V10_WP6_PRIVILEGE_SEPARATION_RUNBOOK.md"


def test_wp6_windows_assets_exist() -> None:
    for path in (PROVISION, ROLLBACK, COLLECTOR, AUDIT_WORKFLOW, RUNBOOK):
        assert path.is_file(), path


def test_provisioning_is_dry_run_by_default_and_uses_non_secret_sentinel() -> None:
    text = PROVISION.read_text(encoding="utf-8")
    assert "[switch]$Apply" in text
    assert "if (-not $Apply)" in text
    assert "DRY RUN ONLY" in text
    assert "OMNI-CIO-WP6-NON-SECRET-ACL-SENTINEL-v1" in text
    assert "TINVEST_TRADING_TOKEN" not in text
    assert "TELEGRAM_BOT_TOKEN" not in text


def test_provisioning_refuses_local_system_and_does_not_reconfigure_runner() -> None:
    text = PROVISION.read_text(encoding="utf-8")
    assert 'if ($runnerClass -eq "LOCAL_SYSTEM")' in text
    assert "WP6 will not provision around a privileged CI identity" in text
    assert "ChangeServiceConfig" not in text
    assert "config.cmd remove" not in text
    assert "svc.cmd uninstall" not in text


def test_rollback_is_marker_guarded_and_does_not_remove_runner() -> None:
    text = ROLLBACK.read_text(encoding="utf-8")
    assert "WP6 ownership marker" in text
    assert "Refusing to remove enabled role account" in text
    assert "GitHub runner registration/service was not modified" in text
    assert "actions.runner" not in text


def test_collector_has_privacy_flags_and_does_not_emit_identity_values() -> None:
    text = COLLECTOR.read_text(encoding="utf-8")
    for flag in (
        "raw_usernames_collected = $false",
        "sids_emitted = $false",
        "hostnames_collected = $false",
        "addresses_collected = $false",
        "secret_values_collected = $false",
        "process_lists_collected = $false",
    ):
        assert flag in text
    assert "StartName =" not in text
    assert "currentSid =" in text  # allowed in-memory only
    assert "currentSid = $profile" not in text


def test_identity_audit_has_no_secret_context_and_uses_non_persistent_checkout() -> None:
    text = AUDIT_WORKFLOW.read_text(encoding="utf-8")
    assert "permissions:\n  contents: read" in text
    assert "persist-credentials: false" in text
    assert "secrets." not in text
    assert "collect_wp6_identity_profile.ps1" in text
    assert "assess_v10_wp6_identity_profile.py" in text


def test_authoritative_workflow_does_not_log_raw_windows_identity() -> None:
    text = SELF_HOSTED.read_text(encoding="utf-8")
    assert "whoami" not in text.lower()
    assert "Runner identity intentionally not logged." in text
