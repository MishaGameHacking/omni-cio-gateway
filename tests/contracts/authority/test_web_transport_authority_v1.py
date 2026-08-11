from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_wp17_transport_cannot_import_real_execution_or_trade_secret_authority() -> None:
    sources = "\n".join(
        (
            _source("apps/api/app.py"),
            _source("omni_cio/web/api_v1.py"),
            _source("omni_cio/web/provisioning_v1.py"),
            _source("omni_cio/web/broker_vault_v1.py"),
        )
    ).lower()

    for forbidden in (
        "omni_cio.real_trading",
        "broker_trading",
        "stop_orders",
        ".orders",
        "post_order",
        "withdraw",
        "currency_transfer",
        "pay_in",
        "real_trading_enabled=true",
    ):
        assert forbidden not in sources


def test_wp17_api_is_not_the_protected_gateway_entrypoint() -> None:
    app_source = _source("apps/api/app.py")
    protected = _source("app.py")

    assert "def create_local_private_app" in app_source
    assert "app =" not in app_source
    assert "app =" in protected
    assert "apps.api.app" not in protected


def test_browser_authority_is_derived_from_server_session_not_client_tenant() -> None:
    source = _source("omni_cio/web/api_v1.py")
    assert "scope = _require_session" in source
    assert "tenant_id=scope.tenant_id" in source
    assert 'body.get("tenant_id")' not in source
    assert 'request.query_params.get("tenant_id")' not in source


def test_read_vault_is_structurally_bounded_under_wp8_read_broker_child() -> None:
    source = _source("omni_cio/web/broker_vault_v1.py")
    assert r"secrets\read-broker\connections" in source
    assert "_CRYPTPROTECT_LOCAL_MACHINE = 0x4" in source
    assert "broker_trading" not in source
    assert "_SECRET_REF_RE.fullmatch" in source
