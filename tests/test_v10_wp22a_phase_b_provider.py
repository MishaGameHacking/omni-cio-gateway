from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest


ROOT = Path(__file__).resolve().parents[1]
LIVE_PATH = ROOT / "scripts" / "wp22a_cloudflare_live.py"
STATE_PATH = ROOT / "scripts" / "wp22a_provider_state_guard.py"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


LIVE = _load("wp22a_cloudflare_live_test", LIVE_PATH)
STATE = _load("wp22a_provider_state_guard_test", STATE_PATH)


def _inputs():
    return LIVE.Inputs(
        account_id="account-expected",
        zone_id="zone-expected",
        hostname="omni.example.com",
        team_name="omni-owner",
    )


def _preflight_snapshot():
    return {
        "zone": {
            "id": "zone-expected",
            "name": "example.com",
            "status": "active",
            "type": "full",
            "paused": False,
            "account": {"id": "account-expected"},
        },
        "universal_ssl": {"enabled": True},
        "certificate_packs": [
            {
                "type": "universal",
                "status": "active",
                "certificates": [
                    {
                        "status": "active",
                        "hosts": ["example.com", "*.example.com"],
                    }
                ],
            }
        ],
        "organization": {
            "auth_domain": "omni-owner.cloudflareaccess.com",
            "allow_authenticate_via_warp": False,
            "deny_unmatched_requests": True,
        },
        "identity_providers": [
            {
                "type": "cloudflare",
                "config": {"restrict_to_account_members": True},
            }
        ],
    }


def test_preflight_accepts_active_full_dns_universal_ssl_and_restricted_idp() -> None:
    LIVE.validate_preflight_snapshot(inputs=_inputs(), **_preflight_snapshot())


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        (("zone", "type", "partial"), "WP22A_ZONE_NOT_ACTIVE_FULL_DNS"),
        (("universal_ssl", "enabled", False), "WP22A_UNIVERSAL_SSL_DISABLED"),
        (
            ("organization", "allow_authenticate_via_warp", True),
            "WP22A_ZERO_TRUST_WARP_AUTH_NOT_DISABLED",
        ),
        (
            ("organization", "deny_unmatched_requests", False),
            "WP22A_ZERO_TRUST_DENY_UNMATCHED_NOT_ENABLED",
        ),
    ],
)
def test_preflight_fails_closed_on_security_regression(mutation, reason: str) -> None:
    snapshot = _preflight_snapshot()
    group, key, value = mutation
    snapshot[group][key] = value
    with pytest.raises(LIVE.Wp22aCloudflareError, match=reason):
        LIVE.validate_preflight_snapshot(inputs=_inputs(), **snapshot)


def test_preflight_rejects_deeper_hostname_even_with_wildcard_certificate() -> None:
    inputs = LIVE.Inputs(
        account_id="account-expected",
        zone_id="zone-expected",
        hostname="deep.omni.example.com",
        team_name="omni-owner",
    )
    with pytest.raises(
        LIVE.Wp22aCloudflareError, match="WP22A_HOSTNAME_NOT_FIRST_LEVEL"
    ):
        LIVE.validate_preflight_snapshot(inputs=inputs, **_preflight_snapshot())


def test_missing_state_refuses_preexisting_wp22a_resources() -> None:
    with pytest.raises(
        LIVE.Wp22aCloudflareError, match="WP22A_STATE_MISSING_BUT_TUNNEL_EXISTS"
    ):
        LIVE.validate_no_managed_resources(
            tunnels=[{"name": LIVE.TUNNEL_NAME}],
            applications=[],
            dns_records=[],
            hostname="omni.example.com",
        )


def _managed_provider_values():
    resources = [
        {
            "address": "cloudflare_zero_trust_tunnel_cloudflared.omni_cio",
            "values": {
                "account_id": "account-expected",
                "name": "omni-cio-v10-owner-web",
                "config_src": "cloudflare",
                "id": "tunnel-id",
            },
        },
        {
            "address": "cloudflare_zero_trust_access_policy.owner",
            "values": {
                "account_id": "account-expected",
                "name": "Omni-CIO exact Cloudflare account member",
                "decision": "allow",
                "session_duration": "24h",
            },
        },
        {
            "address": "cloudflare_zero_trust_access_application.omni_cio",
            "values": {
                "account_id": "account-expected",
                "name": "Omni-CIO OWNER Web",
                "domain": "omni.example.com",
                "type": "self_hosted",
                "allow_authenticate_via_warp": False,
                "allow_iframe": False,
                "enable_binding_cookie": True,
                "http_only_cookie_attribute": True,
                "options_preflight_bypass": False,
            },
        },
        {
            "address": "cloudflare_zero_trust_tunnel_cloudflared_config.omni_cio",
            "values": {
                "account_id": "account-expected",
                "config": {
                    "ingress": [
                        {
                            "hostname": "omni.example.com",
                            "service": "http://127.0.0.1:8765",
                            "origin_request": {
                                "access": {
                                    "required": True,
                                    "team_name": "omni-owner",
                                }
                            },
                        },
                        {"service": "http_status:404"},
                    ]
                },
            },
        },
        {
            "address": "cloudflare_dns_record.omni_cio",
            "values": {
                "zone_id": "zone-expected",
                "name": "omni.example.com",
                "type": "CNAME",
                "proxied": True,
            },
        },
    ]
    return {"root_module": {"resources": resources}}


def test_provider_state_guard_accepts_only_exact_wp22a_resource_shape() -> None:
    STATE.validate_state_values(
        _managed_provider_values(),
        account_id="account-expected",
        zone_id="zone-expected",
        hostname="omni.example.com",
        team_name="omni-owner",
    )


def test_provider_state_guard_rejects_secret_like_values() -> None:
    values = _managed_provider_values()
    values["root_module"]["resources"][0]["values"]["tunnel_token"] = "forbidden"
    with pytest.raises(
        STATE.StateGuardError, match="WP22A_PROVIDER_STATE_SECRET_LIKE_VALUE_PRESENT"
    ):
        STATE.validate_state_values(
            values,
            account_id="account-expected",
            zone_id="zone-expected",
            hostname="omni.example.com",
            team_name="omni-owner",
        )


def test_provider_plan_rejects_destroy_replace_during_apply() -> None:
    payload = {
        "resource_changes": [
            {
                "address": "cloudflare_dns_record.omni_cio",
                "mode": "managed",
                "change": {"actions": ["delete", "create"]},
            }
        ]
    }
    with pytest.raises(
        STATE.StateGuardError, match="WP22A_PROVIDER_APPLY_PLAN_ACTION_INVALID"
    ):
        STATE.validate_plan_document(payload, destroy=False)


def test_provider_helpers_do_not_contain_tunnel_token_data_source() -> None:
    terraform = (
        ROOT / "infrastructure" / "cloudflare" / "wp22a" / "main.tf"
    ).read_text(encoding="utf-8")
    assert "cloudflare_zero_trust_tunnel_cloudflared_token" not in terraform
    assert "tunnel_secret" not in terraform
    assert "CLOUDFLARE_API_TOKEN" not in terraform


def test_sanitized_cli_failure_contains_reason_only(capsys, monkeypatch) -> None:
    monkeypatch.delenv("WP22A_CLOUDFLARE_ACCOUNT_ID", raising=False)
    exit_code = LIVE.main(["preflight"])
    output = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert output == {
        "status": "FAIL",
        "reason": "WP22A_PROTECTED_PROVIDER_INPUT_MISSING",
    }
