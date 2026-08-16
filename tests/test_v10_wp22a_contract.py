from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "architecture" / "V10_WP22A_EXTERNAL_ACCESS_CONTRACT.json"
EXECUTION = ROOT / "docs" / "architecture" / "V10_WP22A_EXECUTION_CONTRACT.md"
ADR = ROOT / "docs" / "architecture" / "ADR-0012-wp22a-clientless-cloudflare-access-tunnel.md"


def load_contract() -> dict[str, object]:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_wp22a_contract_is_fail_closed_until_owner_evidence() -> None:
    value = load_contract()
    assert value["work_package"] == "WP22A"
    assert value["status"] == "IMPLEMENTATION_IN_PROGRESS"

    selected = value["selected_candidate"]
    assert isinstance(selected, dict)
    assert selected["provider"] == "CLOUDFLARE"
    assert selected["services"] == ["ACCESS", "TUNNEL"]
    assert selected["accepted_for_production"] is False
    assert selected["named_tunnel_required"] is True
    assert selected["quick_tunnel_allowed_for_acceptance"] is False

    owner_evidence = value["owner_evidence"]
    assert isinstance(owner_evidence, dict)
    assert owner_evidence["required_before_acceptance"] is True
    assert owner_evidence["status"] == "NOT_YET_COLLECTED"

    locks = value["locks"]
    assert isinstance(locks, dict)
    assert all(locks.values())


def test_origin_requires_cloudflared_access_validation_and_loopback() -> None:
    value = load_contract()
    origin = value["origin"]
    assert isinstance(origin, dict)
    assert origin["loopback_only"] is True
    assert origin["public_inbound_port_allowed"] is False
    assert origin["cloudflared_access_validation_required"] is True
    assert origin["cloudflared_access_team_name_required"] is True
    assert origin["cloudflared_access_audience_required"] is True
    assert origin["cloudflare_access_jwt_required_at_app_boundary"] is True
    assert origin["exact_external_host_allowlist_required"] is True


def test_sessions_csrf_and_invariants_remain_strict() -> None:
    value = load_contract()
    authentication = value["authentication"]
    request_security = value["request_security"]
    invariants = value["invariants"]
    assert isinstance(authentication, dict)
    assert isinstance(request_security, dict)
    assert isinstance(invariants, dict)

    assert authentication["server_side_sessions"] is True
    assert authentication["session_cookie"] == "__Host-omni_v10_session"
    assert authentication["csrf_cookie"] == "__Host-omni_v10_csrf"
    assert authentication["secure_cookie"] is True
    assert authentication["http_only_session_cookie"] is True
    assert authentication["same_site"] == "strict"
    assert request_security["csrf_double_submit_required_for_unsafe_methods"] is True
    assert request_security["https_origin_required_for_unsafe_methods"] is True
    assert request_security["cors_default_deny"] is True

    assert invariants["app"] == "app:app"
    assert invariants["trading_methods"] is False
    assert invariants["REAL_TRADING_ENABLED"] is False
    assert invariants["transfer_withdrawal_authority"] is False
    assert invariants["protected_v9_rollback_preserved"] is True


def test_cloudflare_secrets_are_not_repository_authority() -> None:
    value = load_contract()
    secrets = value["secrets"]
    assert isinstance(secrets, dict)
    assert secrets["cloudflare_api_token_in_repository"] is False
    assert secrets["tunnel_token_in_repository"] is False
    assert secrets["tunnel_token_in_logs"] is False
    assert secrets["tunnel_token_file_runtime_only"] is True
    assert secrets["broker_tokens_unchanged"] is True


def test_human_contracts_preserve_browser_only_and_no_public_origin() -> None:
    execution = EXECUTION.read_text(encoding="utf-8")
    adr = ADR.read_text(encoding="utf-8")
    for text in (execution, adr):
        assert "Cloudflare Access" in text
        assert "Cloudflare Tunnel" in text
        assert "127.0.0.1:8765" in text
        assert "Tailscale" in text
        assert "app:app" in text
        assert "REAL_TRADING_ENABLED=false" in text
    assert "Quick Tunnel" in adr
    assert "Rejected" in adr or "rejected" in adr
