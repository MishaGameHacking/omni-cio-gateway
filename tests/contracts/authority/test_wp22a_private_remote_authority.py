from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _has_module_level_app_assignment(source: str) -> bool:
    module = ast.parse(source)
    for node in module.body:
        if isinstance(node, ast.Assign):
            if any(
                isinstance(target, ast.Name) and target.id == "app"
                for target in node.targets
            ):
                return True
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "app":
                return True
    return False


def test_wp22a_private_remote_is_not_protected_gateway_entrypoint() -> None:
    remote = _source("apps/api/private_remote.py")
    protected = _source("app.py")
    assert "def create_private_remote_app" in remote
    assert not _has_module_level_app_assignment(remote)
    assert _has_module_level_app_assignment(protected)
    assert "apps.api.private_remote" not in protected


def test_wp22a_remote_transport_cannot_import_real_or_trade_authority() -> None:
    source = "\n".join(
        (
            _source("apps/api/private_remote.py"),
            _source("omni_cio/web/remote_security_v1.py"),
        )
    ).lower()
    for forbidden in (
        "omni_cio.real_trading",
        "broker_trading",
        "post_order",
        "stop_orders",
        "withdraw",
        "currency_transfer",
        "pay_in",
        "real_trading_enabled=true",
    ):
        assert forbidden not in source


def test_wp22a_runtime_is_loopback_only_and_funnel_is_structurally_off() -> None:
    launcher = _source(
        "infrastructure/windows/run_wp22a_private_remote_runtime.ps1"
    ).lower()
    assert "--host 127.0.0.1" in launcher
    assert "--host 0.0.0.0" not in launcher

    configure = _source("infrastructure/windows/configure_wp22a_tailscale_serve.ps1")
    configure_lower = configure.lower()
    assert "tailscale serve" in configure_lower
    assert "--bg --https=443" in configure_lower
    assert "Test-Wp22aFunnelDisabled" in configure
    assert "AllowFunnel" in configure
    assert "WP22A_REFUSES_EXISTING_FUNNEL_CONFIGURATION" in configure
    assert "$tailscale funnel" not in configure_lower
    assert "funnel status --json" not in configure_lower


def test_wp22a_finalizer_attempts_both_runtime_and_transport_teardown() -> None:
    finalizer = _source(
        "infrastructure/windows/finalize_wp22a_private_remote_evidence.ps1"
    )
    cleanup_try = finalizer.index("$cleanupFailure = $false")
    transport_try = finalizer.index("$transportFailure = $false")
    cleanup_fail_closed = finalizer.index(
        'if ($cleanupFailure) { throw "WP22A_EVIDENCE_RUNTIME_CLEANUP_FAILED" }'
    )
    transport_fail_closed = finalizer.index(
        'if ($transportFailure) { throw "WP22A_EVIDENCE_TRANSPORT_CLEANUP_FAILED" }'
    )
    evidence_write = finalizer.index("$evidence | ConvertTo-Json")
    assert cleanup_try < transport_try < cleanup_fail_closed
    assert transport_try < transport_fail_closed < evidence_write
    assert "Test-FunnelDisabledFromServeConfig" in finalizer
    assert "$tailscale funnel" not in finalizer.lower()


def test_wp22a_does_not_add_tailscale_as_product_identity_provider() -> None:
    contract = json.loads(
        _source("docs/architecture/V10_WP22A_PRIVATE_REMOTE_SECURITY_CONTRACT.json")
    )
    assert contract["identity"]["ordinary_product_login_providers"] == [
        "telegram",
        "vk_id",
    ]
    assert contract["identity"]["tailscale_is_product_login_provider"] is False
    web_contract = _source("apps/web/src/app-shell/contracts.ts")
    assert 'IdentityProvider = "telegram" | "vk_id"' in web_contract
    assert 'IdentityProvider = "tailscale"' not in web_contract


def test_wp22a_frontend_keeps_auth_material_out_of_web_storage() -> None:
    source = "\n".join(
        (
            _source("apps/web/src/app-shell/api.ts"),
            _source("apps/web/src/app-shell/app-shell.tsx"),
        )
    ).lower()
    assert "localstorage" not in source
    assert "sessionstorage" not in source
