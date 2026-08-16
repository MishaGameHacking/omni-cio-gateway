from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROVISIONER = (
    ROOT / "infrastructure" / "windows" / "provision_wp22a_clientless_remote_access.ps1"
)
LAUNCHER = (
    ROOT / "infrastructure" / "windows" / "run_wp22a_clientless_remote_runtime.ps1"
)
TERRAFORM_ROOT = ROOT / "infrastructure" / "cloudflare" / "wp22a"
TERRAFORM = TERRAFORM_ROOT / "main.tf"
TERRAFORM_LOCK = TERRAFORM_ROOT / ".terraform.lock.hcl"
TERRAFORM_BOOTSTRAP = ROOT / "scripts" / "bootstrap_wp22a_terraform.ps1"
TERRAFORM_VALIDATE = ROOT / "scripts" / "validate_wp22a_terraform.ps1"
WORKFLOW = ROOT / ".github" / "workflows" / "v10-wp22a-clientless-access-audit.yml"
GITIGNORE = ROOT / ".gitignore"


def test_cloudflared_binary_is_version_and_hash_pinned() -> None:
    text = PROVISIONER.read_text(encoding="utf-8")
    assert '$cloudflaredVersion = "2026.7.3"' in text
    assert "$cloudflaredSha256 = @(" in text
    for part in (
        "8635da43",
        "3b6df819",
        "4746e88e",
        "d9d25895",
        "66c20e38",
        "bfc2a80e",
        "431a348b",
        "7c765841",
    ):
        assert f'"{part}"' in text
    assert ') -join ""' in text
    assert "Get-FileHash -Algorithm SHA256" in text
    assert "--no-autoupdate" in text


def test_terraform_bootstrap_is_version_and_hash_pinned() -> None:
    text = TERRAFORM_BOOTSTRAP.read_text(encoding="utf-8")
    assert '$version = "1.15.6"' in text
    assert "$expectedSha256 = @(" in text
    for part in (
        "56b4d3a1",
        "57e346f8",
        "fc1e9425",
        "4d0a944e",
        "6fec81f5",
        "8ddd43eb",
        "274b8e0e",
        "bb56e334",
    ):
        assert f'"{part}"' in text
    assert ') -join ""' in text
    assert "Get-FileHash -Algorithm SHA256" in text
    assert "WP22A_TERRAFORM_ARCHIVE_HASH_MISMATCH" in text


def test_tunnel_token_is_never_put_in_task_arguments_or_json_config() -> None:
    text = PROVISIONER.read_text(encoding="utf-8")
    assert 'Read-Host "Cloudflare Tunnel token' in text
    assert "-AsSecureString" in text
    assert "--token-file" in text
    assert "tunnel_token = $token" in text
    assert "tunnel_token = [string]$ownerConfig.tunnel_token" not in text
    assert "-Token " not in text
    assert "TUNNEL_TOKEN=" not in text


def test_owner_identity_is_fingerprinted_before_runtime_storage() -> None:
    text = PROVISIONER.read_text(encoding="utf-8")
    assert "SHA256" in text
    assert "owner_identity_sha256" in text
    assert "Cloudflare OWNER identity used by Access" in text
    launcher = LAUNCHER.read_text(encoding="utf-8")
    assert "ConfigPath" in launcher
    assert "OwnerIdentitySha256" not in launcher
    assert "OMNI_V10_CLOUDFLARE_OWNER_IDENTITY_SHA256" in launcher


def test_runtime_and_tunnel_are_separate_least_privilege_tasks() -> None:
    text = PROVISIONER.read_text(encoding="utf-8")
    assert '$runtimeName = "omni-cio-runtime"' in text
    assert '$cloudflaredTaskName = "OmniCIO.V10.WP22A.Cloudflared"' in text
    assert 'UserId "NT AUTHORITY\\LOCAL SERVICE"' in text
    assert "LogonType ServiceAccount" in text
    assert "RunLevel Limited" in text
    assert "Set-ScheduledTask -TaskName $baseTaskName -Action $remoteAction" in text


def test_remote_runtime_and_tunnel_survive_boot_and_have_no_execution_limit() -> None:
    text = PROVISIONER.read_text(encoding="utf-8")
    assert text.count("New-ScheduledTaskTrigger -AtStartup") >= 2
    assert text.count("-ExecutionTimeLimit ([TimeSpan]::Zero)") >= 2
    assert text.count("-RestartCount 3") >= 2
    assert text.count("-StartWhenAvailable") >= 2
    assert text.count("-AllowStartIfOnBatteries") >= 2
    assert text.count("-DontStopIfGoingOnBatteries") >= 2
    assert "remote_web_task_boot_persistent" in text
    assert "cloudflared_task_boot_persistent" in text


def test_runner_has_explicit_loopback_firewall_block() -> None:
    text = PROVISIONER.read_text(encoding="utf-8")
    assert '$runnerFirewallRuleName = "OmniCIO.V10.WP22A.BlockRunnerLoopback"' in text
    assert "New-NetFirewallRule" in text
    assert "-Direction Outbound" in text
    assert "-Action Block" in text
    assert '-RemoteAddress "127.0.0.1"' in text
    assert "-LocalUser $sddl" in text
    assert "WP22A_RUNNER_LOCAL_SYSTEM_FORBIDDEN" in text


def test_local_web_restore_normalizes_cleanup_before_apply() -> None:
    text = PROVISIONER.read_text(encoding="utf-8")
    restore = text.split("function Restore-AcceptedLocalWeb", maxsplit=1)[1].split(
        "function Test-BootTriggerPresent", maxsplit=1
    )[0]
    cleanup_index = restore.index("Invoke-BaseProvisionerMode -Mode Cleanup")
    apply_index = restore.index("Invoke-BaseProvisionerMode -Mode Apply")
    assert cleanup_index < apply_index
    assert "WP22A_LOCAL_WEB_CLEANUP_FAILED" in restore
    assert "WP22A_LOCAL_WEB_RESTORE_FAILED" in restore
    assert "-not [bool]$restored.ready" in restore


def test_fail_closed_apply_restores_local_web_after_cutover_started() -> None:
    text = PROVISIONER.read_text(encoding="utf-8")
    assert "$baseNormalized = $false" in text
    assert "$baseNormalized = $true" in text
    assert "if ($baseNormalized)" in text
    assert "Remove-Wp22aLocalContour" in text
    assert "Restore-AcceptedLocalWeb" in text
    assert "rollback_attempted = $true" in text
    assert "WP22A_ROLLBACK_LOCAL_WEB_FAILED" in text


def test_cloudflare_intent_consumes_existing_hardened_org_and_default_idp() -> None:
    text = TERRAFORM.read_text(encoding="utf-8")
    assert 'version = "5.22.0"' in text
    assert 'data "cloudflare_zero_trust_organization" "existing"' in text
    assert 'data "cloudflare_zero_trust_access_identity_providers" "existing"' in text
    assert "deny_unmatched_requests == true" in text
    assert "allow_authenticate_via_warp == false" in text
    assert 'idp.type == "cloudflare"' in text
    assert "idp.config.restrict_to_account_members" in text
    assert "length(local.cloudflare_owner_idps) == 1" in text
    assert 'resource "cloudflare_zero_trust_access_identity_provider"' not in text
    assert 'resource "cloudflare_zero_trust_organization"' not in text


def test_cloudflare_intent_hardens_browser_session_and_origin_access() -> None:
    text = TERRAFORM.read_text(encoding="utf-8")
    assert "cloudflare_account_member" in text
    assert "login_method" in text
    assert "enable_binding_cookie       = true" in text
    assert "http_only_cookie_attribute  = true" in text
    assert "allow_iframe                = false" in text
    assert "options_preflight_bypass    = false" in text
    assert "http://127.0.0.1:8765" in text
    assert "required  = true" in text
    assert "aud_tag" in text
    assert 'service = "http_status:404"' in text


def test_dns_publication_waits_for_access_protected_tunnel_ingress() -> None:
    text = TERRAFORM.read_text(encoding="utf-8")
    dns = text.split('resource "cloudflare_dns_record" "omni_cio"', maxsplit=1)[
        1
    ].split('output "access_application_aud"', maxsplit=1)[0]
    assert "depends_on" in dns
    assert "cloudflare_zero_trust_access_application.omni_cio" in dns
    assert "cloudflare_zero_trust_tunnel_cloudflared_config.omni_cio" in dns


def test_cloudflare_provider_version_and_windows_package_hash_are_locked() -> None:
    text = TERRAFORM_LOCK.read_text(encoding="utf-8")
    assert 'provider "registry.terraform.io/cloudflare/cloudflare"' in text
    assert 'version     = "5.22.0"' in text
    assert 'constraints = "5.22.0"' in text
    assert (
        '"zh:ca4bf16742a7e59319a482f003d32f6f6abbc5fbf862916ce1a136278e6d420d"' in text
    )


def test_ci_uses_committed_provider_lock_without_rewriting_it() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    validator = TERRAFORM_VALIDATE.read_text(encoding="utf-8")
    assert "scripts\\validate_wp22a_terraform.ps1" in workflow
    assert 'Join-Path $sourceRoot ".terraform.lock.hcl"' in validator
    assert "-Destination $validateRoot -Force" in validator
    assert "-lockfile=readonly" in validator


def test_terraform_runtime_state_and_variable_values_are_git_ignored() -> None:
    text = GITIGNORE.read_text(encoding="utf-8")
    for marker in (".terraform/", "*.tfstate", "*.tfvars", "*.tfvars.json"):
        assert marker in text
