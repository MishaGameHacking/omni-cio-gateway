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


def test_runner_service_resolution_is_bound_to_reviewed_runner_root() -> None:
    for path in (PROVISION, COLLECTOR):
        text = path.read_text(encoding="utf-8")
        assert '$runnerServiceMarker = Join-Path $runnerRoot ".service"' in text
        assert "Get-Content -LiteralPath $runnerServiceMarker -Raw" in text
        assert 'Where-Object { $_.Name -eq $serviceName }' in text
        assert "bound to the reviewed runner root" in text
        assert 'Where-Object { $_.Name -like "actions.runner.*" }' not in text


def test_provisioning_hardens_runner_root_and_reviewed_config_with_backup() -> None:
    text = PROVISION.read_text(encoding="utf-8")
    for name in (".runner", ".credentials", ".credentials_rsaparams", ".service"):
        assert f'"{name}"' in text
    assert "runner-config-acl-backup.json" in text
    assert 'name = "."' in text
    assert "Save-RunnerAclBackup" in text
    assert "Set-RunnerRootDenyAcl" in text
    assert "New-DenyRule" in text
    assert "Set-RunnerSensitiveFileAcl" in text
    assert "-Rights Modify" in text
    assert "explicitly denied access to the entire runner root" in text
    assert "SYSTEM, Administrators and the runner service identity" in text


def test_sentinel_acl_repairs_inheritance_and_fails_closed_on_bad_authority() -> None:
    text = PROVISION.read_text(encoding="utf-8")
    sentinel_section = text.split("function Set-SentinelAcl", 1)[1].split(
        "$runner = Get-RunnerServiceSafe", 1
    )[0]
    assert "Get-Acl -LiteralPath $sentinelPath" in sentinel_section
    assert "SetAccessRuleProtection($false, $true)" in sentinel_section
    assert "SetAccessRuleProtection($true, $true)" in sentinel_section
    assert "-Rights ReadPermissions" in sentinel_section
    assert "GetAccessRules(" in sentinel_section
    assert "execution role read grant was not persisted" in sentinel_section
    assert "runner received sentinel data-read authority" in sentinel_section


def test_rollback_is_marker_guarded_restores_root_and_config_acl() -> None:
    text = ROLLBACK.read_text(encoding="utf-8")
    assert "WP6 ownership marker" in text
    assert "Refusing to remove enabled role account" in text
    assert "runner-config-acl-backup.json" in text
    assert '"."' in text
    assert "Restore-RunnerAclBackup" in text
    assert "DirectorySecurity" in text
    assert "SetSecurityDescriptorSddlForm" in text
    assert "GitHub runner registration/service account was not modified" in text
    assert "config.cmd remove" not in text
    assert "svc.cmd uninstall" not in text


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


def test_collector_audits_runner_root_and_sensitive_config_surfaces() -> None:
    text = COLLECTOR.read_text(encoding="utf-8")
    for name in (".runner", ".credentials", ".credentials_rsaparams", ".service"):
        assert f'"{name}"' in text
    assert "Test-AclDeny" in text
    assert "runtimeRunnerRootDeny" in text
    assert "executionRunnerRootDeny" in text
    assert "runnerConfigBroadWriteExposure" in text
    assert "runtimeRunnerWriteGrant" in text


def test_identity_audit_has_no_secret_context_and_uses_headless_exact_sha_bootstrap() -> None:
    text = AUDIT_WORKFLOW.read_text(encoding="utf-8")
    assert "permissions:\n  contents: read" in text
    assert "uses: actions/checkout@" not in text
    for marker in (
        "GITHUB_TOKEN: ${{ github.token }}",
        'GIT_TERMINAL_PROMPT: "0"',
        'GCM_INTERACTIVE: "0"',
        'git config --local credential.helper ""',
        "git config --local --add credential.helper",
        "git config --local --unset-all credential.helper",
        'git checkout --detach "$EXPECTED_HEAD"',
        'test "$(git rev-parse HEAD)" = "$EXPECTED_HEAD"',
        'test -z "$(git config --local --get-all credential.helper || true)"',
    ):
        assert marker in text
    assert "secrets." not in text
    assert "provision_wp6_privilege_boundary.ps1" in text
    assert "collect_wp6_identity_profile.ps1" in text
    assert "assess_v10_wp6_identity_profile.py" in text


def test_owner_apply_runbook_uses_actions_checkout_handoff_without_network_git() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")
    assert "Reviewed checkout hand-off" in text
    assert "persist-credentials: false" in text
    assert "git rev-parse HEAD" in text
    assert "Do **not** run `git fetch` or `git pull`" in text
    apply_section = text.split("## 5. Apply", 1)[1].split("## 6. Verification", 1)[0]
    assert "git fetch" not in apply_section
    assert "git pull" not in apply_section


def test_authoritative_workflow_does_not_log_raw_windows_identity() -> None:
    text = SELF_HOSTED.read_text(encoding="utf-8")
    assert "whoami" not in text.lower()
    assert "Runner identity intentionally not logged." in text
