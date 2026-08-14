from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    ROOT / "docs" / "architecture" / "V10_WP22A_PRIVATE_REMOTE_SECURITY_CONTRACT.json"
)


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def main() -> int:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert contract["work_package"] == "WP22A"
    decision = contract["decision"]
    assert decision["public_ingress_required"] is False
    assert decision["selected_transport"] == "TAILSCALE_SERVE_PRIVATE"
    assert decision["tailscale_funnel_allowed"] is False
    assert decision["backend_bind"] == "127.0.0.1"
    assert decision["public_multi_user_enabled"] is False

    identity = contract["identity"]
    assert identity["ordinary_product_login_providers"] == ["telegram", "vk_id"]
    assert identity["tailscale_is_product_login_provider"] is False
    assert identity["server_side_session_required"] is True
    assert (
        identity["private_owner_session_scope"]
        == "CANONICAL_OWNER_USER_AND_TENANT_ONLY"
    )
    assert identity["foreign_user_or_tenant_session"] == "REJECT"
    assert identity["session_idle_lifetime_minutes"] == 120
    assert identity["session_absolute_lifetime_hours"] == 24
    assert identity["session_rotation_on_private_remote_login"] is True
    assert identity["cookie_secure"] is True
    assert identity["cookie_http_only"] is True
    assert identity["cookie_same_site"] == "strict"

    request_security = contract["request_security"]
    assert request_security["backend_peer_loopback_required"] is True
    assert request_security["live_server_session_required_for_unsafe_methods"] is True
    assert request_security["hsts_max_age_seconds"] == 31536000
    assert request_security["private_response_cache_control"] == "no-store"
    assert request_security["frame_embedding"] == "DENY"

    boundary = contract["tailscale_boundary"]
    assert boundary["identity_header_rfc2047_decode_required"] is True
    assert boundary["backend_must_remain_loopback"] is True
    assert boundary["runtime_config_acl"] == "SYSTEM_ADMINS_RUNTIME_READ_ONLY_ONLY"

    acceptance_runtime = contract["acceptance_runtime"]
    assert acceptance_runtime["principal"] == "omni-cio-runtime"
    assert acceptance_runtime["principal_must_be_non_admin"] is True
    assert acceptance_runtime["scheduled_task_logon"] == "PASSWORD_EPHEMERAL_LOCAL_ONLY"
    assert acceptance_runtime["scheduled_task_s4u_allowed"] is False
    assert acceptance_runtime["postgres_authentication"] == "SSPI"
    assert acceptance_runtime["postgres_trust_allowed"] is False
    assert acceptance_runtime["database_password_persisted"] is False
    assert acceptance_runtime["cleanup_after_rehearsal_required"] is True

    owner_evidence = contract["owner_evidence"]
    assert owner_evidence["physical_rehearsal_required"] is True
    assert owner_evidence["tailnet_policy_owner_only_confirmation_required"] is True
    assert owner_evidence["owner_remote_https_confirmation_required"] is True
    assert owner_evidence["non_owner_denial_deterministic_required"] is True
    assert (
        owner_evidence["foreign_tenant_session_denial_deterministic_required"] is True
    )
    assert owner_evidence["physical_non_owner_identity_required"] is False
    assert owner_evidence["local_fallback_confirmation_required"] is True
    assert owner_evidence["private_config_runner_read_allowed"] is False
    assert owner_evidence["sanitized_evidence_runner_read_allowed"] is True
    assert owner_evidence["sanitized_evidence_runner_write_allowed"] is False
    assert owner_evidence["exact_head_binding_required"] is True
    assert owner_evidence["source_hash_binding_required"] is True

    authority = contract["authority"]
    assert authority["gateway_entrypoint"] == "app:app"
    assert authority["trading_methods"] is False
    assert authority["real_trading_enabled"] is False
    assert authority["broker_write_authority_added"] is False
    assert authority["transfer_withdrawal_authority_added"] is False
    assert authority["real_plan_approval_surface_published"] is False

    remote_app = _source("apps/api/private_remote.py").lower()
    for forbidden in (
        "0.0.0.0",
        "cloudflared",
        "cloudflare tunnel",
        "broker_trading",
        "omni_cio.real_trading",
        "post_order",
        "withdraw",
        "currency_transfer",
    ):
        assert forbidden not in remote_app
    assert "secure_cookie=true" in remote_app
    assert "public_multi_user_enabled" in remote_app
    assert "real_trading_enabled" in remote_app
    assert "idle_lifetime=timedelta(hours=2)" in remote_app
    assert "absolute_lifetime=timedelta(hours=24)" in remote_app
    assert "sessions=sessions" in remote_app
    assert "apply_migrations" not in remote_app
    assert "_require_read_only_migration_state" in remote_app
    assert "select version, name, sha256" in remote_app
    assert "discover_migrations" in remote_app

    security = _source("omni_cio/web/remote_security_v1.py").lower()
    for required in (
        "tailscale-user-login",
        "decode_header",
        "x-omni-csrf",
        "backend_peer_not_loopback",
        "origin_required",
        "origin_not_allowed",
        "host_not_allowed",
        "authentication_required",
        "private_remote_owner_session_required",
        "csrf_validation_failed",
        "login_rate_limited",
        "api_mutation_rate_limited",
        "telegram_mini_app_auth_not_active",
        "strict-transport-security",
        "x-content-type-options",
        "x-frame-options",
        "referrer-policy",
    ):
        assert required in security

    launcher = _source(
        "infrastructure/windows/run_wp22a_private_remote_runtime.ps1"
    ).lower()
    assert "--host 127.0.0.1" in launcher
    assert "--host 0.0.0.0" not in launcher
    assert "apps.api.private_remote:create_private_remote_app" in launcher
    assert '$env:real_trading_enabled = "0"' in launcher
    assert '$env:public_multi_user_enabled = "0"' in launcher
    deployment_marker = ".omni-cio-wp22a-private-deployment"
    assert deployment_marker in launcher
    assert ".omni-cio-wp22a-private-remote-deployment" not in launcher

    tailscale_source = _source(
        "infrastructure/windows/configure_wp22a_tailscale_serve.ps1"
    )
    tailscale = tailscale_source.lower()
    assert "tailscale serve" in tailscale
    assert "--bg --https=443" in tailscale
    assert "http://127.0.0.1:$backendport" in tailscale
    assert "Test-Wp22aServeMapping" in tailscale_source
    assert "Test-Wp22aFunnelDisabled" in tailscale_source
    assert "AllowFunnel" in tailscale_source
    assert "WP22A_REFUSES_EXISTING_SERVE_CONFIGURATION" in tailscale_source
    assert "WP22A_REFUSES_EXISTING_FUNNEL_CONFIGURATION" in tailscale_source
    assert "SelfTestStatusParser" in tailscale_source
    assert "$tailscale funnel" not in tailscale
    assert "funnel status --json" not in tailscale
    assert "$OwnerLogin.Trim().ToLowerInvariant()" not in tailscale_source
    assert "Resolve-IdentitySid" in tailscale_source
    assert "$allowedSidValues" in tailscale_source
    assert "ReadAndExecute" in tailscale_source

    provisioner = _source(
        "infrastructure/windows/provision_wp22a_private_remote_runtime.ps1"
    )
    provisioner_lower = provisioner.lower()
    assert "omni-cio-runtime" in provisioner
    assert "OmniCIO.V10.WP22APrivateRemoteAcceptance" in provisioner
    assert "SeBatchLogonRight" in provisioner
    assert "SeDenyBatchLogonRight" in provisioner
    assert "Register-ScheduledTask" in provisioner
    assert "-Password $runtimePassword" in provisioner
    assert "-RunLevel Limited" in provisioner
    assert "-LogonType S4U" not in provisioner
    assert deployment_marker in provisioner
    assert "GRANT SELECT ON ALL TABLES IN SCHEMA omni_cio_v10" in provisioner
    assert "postgres_trust_used = $false" in provisioner
    assert "database_password_persisted = $false" in provisioner
    assert "runtime_password_logged_or_exported = $false" in provisioner
    assert "broker_trading" not in provisioner_lower

    finalizer = _source(
        "infrastructure/windows/finalize_wp22a_private_remote_evidence.ps1"
    )
    for required in (
        "TailnetPolicyNarrowConfirmed",
        "OwnerRemoteCabinetConfirmed",
        "LocalFallbackConfirmed",
        "non_owner_identity_denial_deterministic = $true",
        "serve_disabled_after_rehearsal",
        "temporary_runtime_cleaned",
        "raw_owner_identity_recorded = $false",
        "raw_tailnet_hostname_recorded = $false",
        "broker_secret_recorded = $false",
        "Test-FunnelDisabledFromServeConfig",
        "Test-ServeTransportRemoved",
    ):
        assert required in finalizer
    assert "NonOwnerDeniedConfirmed" not in finalizer
    assert "$tailscale funnel" not in finalizer.lower()
    assert "funnel status --json" not in finalizer.lower()
    assert "owner_login" not in finalizer.lower()
    assert "portfolio_total" not in finalizer.lower()

    runner_probe = _source(
        "infrastructure/windows/audit_wp22a_private_remote_runner.ps1"
    )
    assert "runner_private_config_read_allowed" in runner_probe
    assert "runner_private_config_write_allowed" in runner_probe
    assert "runner_evidence_write_allowed" in runner_probe
    assert "ready = [bool]$ready" in runner_probe

    assessor = _source("scripts/assess_v10_wp22a_owner_evidence.py")
    assert "OWNER_PRIVATE_REMOTE_SANITIZED" in assessor
    assert "source hash mismatch" in assessor
    assert "runner_private_config_read_allowed" in assessor
    assert "non_owner_identity_denial_deterministic" in assessor
    assert "public_ingress" in assessor

    validator = _source(
        "infrastructure/windows/validate_wp22a_private_runtime_helper.ps1"
    )
    assert "Wp22aAccountRights" in validator
    assert "helper_compiled = $true" in validator
    assert "mutation_performed = $false" in validator

    owner_workflow = _source(
        ".github/workflows/v10-wp22a-owner-private-remote-audit.yml"
    )
    assert "WP22A_OWNER_PRIVATE_REMOTE_GATE=OWNER_ACTION_REQUIRED" in owner_workflow
    assert "assess_v10_wp22a_owner_evidence.py" in owner_workflow
    assert "audit_wp22a_private_remote_runner.ps1" in owner_workflow
    assert "retention-days: 3" in owner_workflow

    frontend = _source("apps/web/src/app-shell/api.ts").lower()
    assert '"x-omni-csrf"' in frontend
    assert "/api/v10/web/session/csrf" in frontend
    shell = _source("apps/web/src/app-shell/app-shell.tsx")
    assert "Приватный OWNER доступ" in shell
    assert "product login provider" in shell.lower()

    threat_model = _source("docs/architecture/V10_THREAT_MODEL.md")
    assert "WP22A threat-model update" in threat_model
    assert (
        "T22 — Private remote access spoofing or accidental public exposure"
        in threat_model
    )
    assert (
        "OWNER tailnet HTTPS/Tailscale Serve <-> loopback-only private Web runtime"
        in threat_model
    )

    print("WP22A private remote security guard: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
