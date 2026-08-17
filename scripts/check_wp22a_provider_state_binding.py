from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from wp22a_cloudflare_live import (
    ACCESS_POLICY_NAME,
    TUNNEL_NAME,
    CloudflareClient,
    Inputs,
    Wp22aCloudflareError,
    validate_managed_resources,
)


class ProviderStateBindingError(RuntimeError):
    pass


def _lower(value: Any) -> str:
    return str(value or "").strip().lower()


def _read_state(path: str) -> Mapping[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProviderStateBindingError("WP22A_PROVIDER_STATE_JSON_INVALID") from exc
    if not isinstance(payload, dict):
        raise ProviderStateBindingError("WP22A_PROVIDER_STATE_JSON_NOT_OBJECT")
    return payload


def _walk_resources(module: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    result: list[Mapping[str, Any]] = []
    resources = module.get("resources")
    if isinstance(resources, list):
        result.extend(item for item in resources if isinstance(item, dict))
    children = module.get("child_modules")
    if isinstance(children, list):
        for child in children:
            if isinstance(child, dict):
                result.extend(_walk_resources(child))
    return result


def managed_state_ids(payload: Mapping[str, Any]) -> Mapping[str, str]:
    values = payload.get("values")
    root = values.get("root_module") if isinstance(values, dict) else None
    if not isinstance(root, dict):
        raise ProviderStateBindingError("WP22A_PROVIDER_STATE_ROOT_MISSING")
    ids: dict[str, str] = {}
    for resource in _walk_resources(root):
        if str(resource.get("mode", "managed")) != "managed":
            continue
        address = str(resource.get("address", ""))
        resource_values = resource.get("values")
        if not isinstance(resource_values, dict):
            continue
        resource_id = str(resource_values.get("id", "")).strip()
        if address and resource_id:
            ids[address] = resource_id
    return ids


def validate_exact_binding(
    state_ids: Mapping[str, str],
    *,
    tunnel: Mapping[str, Any],
    application: Mapping[str, Any],
    policy: Mapping[str, Any],
    dns_record: Mapping[str, Any],
) -> None:
    expected = {
        "cloudflare_zero_trust_tunnel_cloudflared.omni_cio": str(
            tunnel.get("id", "")
        ),
        "cloudflare_zero_trust_access_policy.owner": str(policy.get("id", "")),
        "cloudflare_zero_trust_access_application.omni_cio": str(
            application.get("id", "")
        ),
        "cloudflare_dns_record.omni_cio": str(dns_record.get("id", "")),
    }
    if not all(expected.values()):
        raise ProviderStateBindingError("WP22A_LIVE_PROVIDER_RESOURCE_ID_MISSING")
    for address, live_id in expected.items():
        if state_ids.get(address) != live_id:
            raise ProviderStateBindingError("WP22A_PROVIDER_STATE_LIVE_ID_MISMATCH")


def validate_access_binding(
    *,
    inputs: Inputs,
    application: Mapping[str, Any],
    policies: Any,
    identity_providers: Any,
) -> Mapping[str, Any]:
    if not isinstance(identity_providers, list):
        raise ProviderStateBindingError("WP22A_IDENTITY_PROVIDER_LIST_INVALID")
    restricted = [
        provider
        for provider in identity_providers
        if isinstance(provider, dict)
        and _lower(provider.get("type")) == "cloudflare"
        and isinstance(provider.get("config"), dict)
        and provider["config"].get("restrict_to_account_members") is True
    ]
    if len(restricted) != 1 or not str(restricted[0].get("id", "")):
        raise ProviderStateBindingError("WP22A_RESTRICTED_IDP_BINDING_INVALID")
    idp_id = str(restricted[0]["id"])

    allowed_idps = application.get("allowed_idps")
    if not isinstance(allowed_idps, list) or [str(item) for item in allowed_idps] != [
        idp_id
    ]:
        raise ProviderStateBindingError("WP22A_ACCESS_APP_IDP_BINDING_INVALID")
    if application.get("auto_redirect_to_identity") is not True:
        raise ProviderStateBindingError("WP22A_ACCESS_APP_AUTO_REDIRECT_REQUIRED")

    if not isinstance(policies, list) or len(policies) != 1:
        raise ProviderStateBindingError("WP22A_ACCESS_POLICY_COUNT_INVALID")
    policy = policies[0]
    if not isinstance(policy, dict) or _lower(policy.get("name")) != ACCESS_POLICY_NAME.lower():
        raise ProviderStateBindingError("WP22A_ACCESS_POLICY_BINDING_INVALID")
    if _lower(policy.get("decision")) != "allow" or _lower(
        policy.get("session_duration")
    ) != "24h":
        raise ProviderStateBindingError("WP22A_ACCESS_POLICY_SECURITY_INVALID")

    include = policy.get("include")
    if not isinstance(include, list) or len(include) != 1:
        raise ProviderStateBindingError("WP22A_ACCESS_POLICY_INCLUDE_INVALID")
    account_rule = include[0].get("cloudflare_account_member") if isinstance(include[0], dict) else None
    if not isinstance(account_rule, dict) or str(account_rule.get("account_id", "")) != inputs.account_id:
        raise ProviderStateBindingError("WP22A_ACCESS_POLICY_ACCOUNT_MEMBER_INVALID")

    require = policy.get("require")
    if not isinstance(require, list) or len(require) != 1:
        raise ProviderStateBindingError("WP22A_ACCESS_POLICY_REQUIRE_INVALID")
    login_rule = require[0].get("login_method") if isinstance(require[0], dict) else None
    if not isinstance(login_rule, dict) or str(login_rule.get("id", "")) != idp_id:
        raise ProviderStateBindingError("WP22A_ACCESS_POLICY_LOGIN_METHOD_INVALID")
    return policy


def run(state_json_path: str) -> Mapping[str, Any]:
    inputs = Inputs.from_env()
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    client = CloudflareClient(token)
    state_ids = managed_state_ids(_read_state(state_json_path))

    tunnels = client.get(
        f"accounts/{inputs.account_id}/cfd_tunnel", {"name": TUNNEL_NAME}
    )
    applications = client.get(f"accounts/{inputs.account_id}/access/apps")
    dns_records = client.get(
        f"zones/{inputs.zone_id}/dns_records", {"name": inputs.hostname}
    )
    matches = validate_managed_resources(
        inputs=inputs,
        tunnels=tunnels,
        applications=applications,
        dns_records=dns_records,
    )
    tunnel = matches["tunnel"]
    application = matches["application"]
    dns_record = matches["dns"]

    app_id = str(application.get("id", ""))
    policies = client.get(
        f"accounts/{inputs.account_id}/access/apps/{app_id}/policies"
    )
    identity_providers = client.get(
        f"accounts/{inputs.account_id}/access/identity_providers"
    )
    policy = validate_access_binding(
        inputs=inputs,
        application=application,
        policies=policies,
        identity_providers=identity_providers,
    )

    tunnel_id = str(tunnel.get("id", ""))
    tunnel_config = client.get(
        f"accounts/{inputs.account_id}/cfd_tunnel/{tunnel_id}/configurations"
    )
    if not isinstance(tunnel_config, dict):
        raise ProviderStateBindingError("WP22A_TUNNEL_CONFIG_INVALID")
    validate_managed_resources(
        inputs=inputs,
        tunnels=tunnels,
        applications=applications,
        dns_records=dns_records,
        tunnel_config=tunnel_config,
    )

    validate_exact_binding(
        state_ids,
        tunnel=tunnel,
        application=application,
        policy=policy,
        dns_record=dns_record,
    )
    return {
        "status": "PASS",
        "reason": "WP22A_PROVIDER_STATE_LIVE_BINDING_PASS",
        "state_matches_live_resources": True,
        "access_policy_verified": True,
        "tunnel_ingress_verified": True,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print(
            json.dumps(
                {"status": "FAIL", "reason": "WP22A_PROVIDER_STATE_PATH_REQUIRED"},
                sort_keys=True,
            )
        )
        return 2
    try:
        result = run(args[0])
    except (ProviderStateBindingError, Wp22aCloudflareError) as exc:
        print(json.dumps({"status": "FAIL", "reason": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
