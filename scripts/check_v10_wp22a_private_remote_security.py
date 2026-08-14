from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "architecture" / "V10_WP22A_PRIVATE_REMOTE_SECURITY_CONTRACT.json"


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
    assert identity["cookie_secure"] is True
    assert identity["cookie_http_only"] is True

    authority = contract["authority"]
    assert authority["gateway_entrypoint"] == "app:app"
    assert authority["trading_methods"] is False
    assert authority["real_trading_enabled"] is False
    assert authority["broker_write_authority_added"] is False
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

    security = _source("omni_cio/web/remote_security_v1.py").lower()
    for required in (
        "tailscale-user-login",
        "x-omni-csrf",
        "origin_required",
        "origin_not_allowed",
        "host_not_allowed",
        "csrf_validation_failed",
        "login_rate_limited",
        "api_mutation_rate_limited",
        "telegram_mini_app_auth_not_active",
    ):
        assert required in security

    launcher = _source("infrastructure/windows/run_wp22a_private_remote_runtime.ps1").lower()
    assert "--host 127.0.0.1" in launcher
    assert "--host 0.0.0.0" not in launcher
    assert "apps.api.private_remote:create_private_remote_app" in launcher
    assert '$env:real_trading_enabled = "0"' in launcher
    assert '$env:public_multi_user_enabled = "0"' in launcher

    tailscale = _source("infrastructure/windows/configure_wp22a_tailscale_serve.ps1").lower()
    assert "tailscale serve" in tailscale
    assert "--bg --https=443" in tailscale
    assert "http://127.0.0.1:$backendport" in tailscale
    assert "tailscale funnel" in tailscale
    assert "--https=443 off" in tailscale
    assert "tailscale funnel --bg" not in tailscale

    frontend = _source("apps/web/src/app-shell/api.ts").lower()
    assert '"x-omni-csrf"' in frontend
    assert "/api/v10/web/session/csrf" in frontend
    shell = _source("apps/web/src/app-shell/app-shell.tsx")
    assert "Приватный OWNER доступ" in shell
    assert "product login provider" in shell.lower()

    print("WP22A private remote security guard: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
