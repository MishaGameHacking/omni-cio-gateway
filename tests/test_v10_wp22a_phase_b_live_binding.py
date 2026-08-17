from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from check_wp22a_provider_state_binding import (  # noqa: E402
    ProviderStateBindingError,
    validate_access_binding,
    validate_exact_binding,
)
from wp22a_cloudflare_live import Inputs  # noqa: E402


def _inputs() -> Inputs:
    return Inputs(
        account_id="account-expected",
        zone_id="zone-expected",
        hostname="omni.example.com",
        team_name="owner-team",
    )


def _application() -> dict[str, object]:
    return {
        "id": "app-id",
        "allowed_idps": ["idp-id"],
        "auto_redirect_to_identity": True,
    }


def _policies() -> list[dict[str, object]]:
    return [
        {
            "id": "policy-id",
            "name": "Omni-CIO exact Cloudflare account member",
            "decision": "allow",
            "session_duration": "24h",
            "include": [
                {"cloudflare_account_member": {"account_id": "account-expected"}}
            ],
            "require": [{"login_method": {"id": "idp-id"}}],
        }
    ]


def _identity_providers() -> list[dict[str, object]]:
    return [
        {
            "id": "idp-id",
            "type": "cloudflare",
            "config": {"restrict_to_account_members": True},
        }
    ]


def test_access_binding_requires_exact_account_member_and_login_method() -> None:
    policy = validate_access_binding(
        inputs=_inputs(),
        application=_application(),
        policies=_policies(),
        identity_providers=_identity_providers(),
    )
    assert policy["id"] == "policy-id"


def test_access_binding_rejects_everyone_or_extra_policy() -> None:
    policies = _policies()
    policies[0]["include"] = [{"everyone": {}}]
    with pytest.raises(
        ProviderStateBindingError,
        match="WP22A_ACCESS_POLICY_ACCOUNT_MEMBER_INVALID",
    ):
        validate_access_binding(
            inputs=_inputs(),
            application=_application(),
            policies=policies,
            identity_providers=_identity_providers(),
        )

    with pytest.raises(
        ProviderStateBindingError,
        match="WP22A_ACCESS_POLICY_COUNT_INVALID",
    ):
        validate_access_binding(
            inputs=_inputs(),
            application=_application(),
            policies=_policies() + _policies(),
            identity_providers=_identity_providers(),
        )


def test_state_ids_must_match_exact_live_resources() -> None:
    state_ids = {
        "cloudflare_zero_trust_tunnel_cloudflared.omni_cio": "tunnel-id",
        "cloudflare_zero_trust_access_policy.owner": "policy-id",
        "cloudflare_zero_trust_access_application.omni_cio": "app-id",
        "cloudflare_dns_record.omni_cio": "dns-id",
    }
    validate_exact_binding(
        state_ids,
        tunnel={"id": "tunnel-id"},
        application={"id": "app-id"},
        policy={"id": "policy-id"},
        dns_record={"id": "dns-id"},
    )
    poisoned = dict(state_ids)
    poisoned["cloudflare_zero_trust_access_application.omni_cio"] = "other-app"
    with pytest.raises(
        ProviderStateBindingError,
        match="WP22A_PROVIDER_STATE_LIVE_ID_MISMATCH",
    ):
        validate_exact_binding(
            poisoned,
            tunnel={"id": "tunnel-id"},
            application={"id": "app-id"},
            policy={"id": "policy-id"},
            dns_record={"id": "dns-id"},
        )
