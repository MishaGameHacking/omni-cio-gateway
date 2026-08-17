from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


MANAGED_ADDRESSES = {
    "cloudflare_zero_trust_tunnel_cloudflared.omni_cio",
    "cloudflare_zero_trust_access_policy.owner",
    "cloudflare_zero_trust_access_application.omni_cio",
    "cloudflare_zero_trust_tunnel_cloudflared_config.omni_cio",
    "cloudflare_dns_record.omni_cio",
}
DATA_ADDRESSES = {
    "data.cloudflare_zero_trust_organization.existing",
    "data.cloudflare_zero_trust_access_identity_providers.existing",
}
ALLOWED_ADDRESSES = MANAGED_ADDRESSES | DATA_ADDRESSES
RISKY_KEY_FRAGMENTS = ("token", "secret", "password", "credential")


class StateGuardError(RuntimeError):
    pass


def _lower(value: Any) -> str:
    return str(value or "").strip().lower()


def _read(path: str) -> Mapping[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StateGuardError("WP22A_PROVIDER_JSON_INVALID") from exc
    if not isinstance(payload, dict):
        raise StateGuardError("WP22A_PROVIDER_JSON_NOT_OBJECT")
    return payload


def _walk_resources(module: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    resources: list[Mapping[str, Any]] = []
    raw_resources = module.get("resources", [])
    if isinstance(raw_resources, list):
        resources.extend(item for item in raw_resources if isinstance(item, dict))
    child_modules = module.get("child_modules", [])
    if isinstance(child_modules, list):
        for child in child_modules:
            if isinstance(child, dict):
                resources.extend(_walk_resources(child))
    return resources


def _resource_map(values: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    root = values.get("root_module")
    if not isinstance(root, dict):
        raise StateGuardError("WP22A_PROVIDER_ROOT_MODULE_MISSING")
    result: dict[str, Mapping[str, Any]] = {}
    for resource in _walk_resources(root):
        address = str(resource.get("address", ""))
        if not address or address in result:
            raise StateGuardError("WP22A_PROVIDER_RESOURCE_ADDRESS_INVALID")
        result[address] = resource
    return result


def _scan_for_secret_like_values(value: Any, path: str = "") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            lowered = str(key).lower()
            if any(fragment in lowered for fragment in RISKY_KEY_FRAGMENTS):
                if child not in (None, "", False, [], {}):
                    raise StateGuardError("WP22A_PROVIDER_STATE_SECRET_LIKE_VALUE_PRESENT")
            _scan_for_secret_like_values(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _scan_for_secret_like_values(child, f"{path}[{index}]")


def _values(resource: Mapping[str, Any]) -> Mapping[str, Any]:
    values = resource.get("values")
    if not isinstance(values, dict):
        raise StateGuardError("WP22A_PROVIDER_RESOURCE_VALUES_INVALID")
    return values


def validate_state_values(
    values: Mapping[str, Any],
    *,
    account_id: str,
    zone_id: str,
    hostname: str,
    team_name: str,
) -> None:
    resources = _resource_map(values)
    unknown = set(resources) - ALLOWED_ADDRESSES
    if unknown:
        raise StateGuardError("WP22A_PROVIDER_STATE_UNKNOWN_RESOURCE")
    missing = MANAGED_ADDRESSES - set(resources)
    if missing:
        raise StateGuardError("WP22A_PROVIDER_STATE_MANAGED_RESOURCE_MISSING")

    for resource in resources.values():
        _scan_for_secret_like_values(_values(resource))

    tunnel = _values(resources["cloudflare_zero_trust_tunnel_cloudflared.omni_cio"])
    if (
        str(tunnel.get("account_id", "")) != account_id
        or _lower(tunnel.get("name")) != "omni-cio-v10-owner-web"
        or _lower(tunnel.get("config_src")) != "cloudflare"
    ):
        raise StateGuardError("WP22A_PROVIDER_STATE_TUNNEL_BINDING_INVALID")

    policy = _values(resources["cloudflare_zero_trust_access_policy.owner"])
    if (
        str(policy.get("account_id", "")) != account_id
        or _lower(policy.get("name")) != "omni-cio exact cloudflare account member"
        or _lower(policy.get("decision")) != "allow"
        or _lower(policy.get("session_duration")) != "24h"
    ):
        raise StateGuardError("WP22A_PROVIDER_STATE_POLICY_INVALID")

    application = _values(
        resources["cloudflare_zero_trust_access_application.omni_cio"]
    )
    if (
        str(application.get("account_id", "")) != account_id
        or _lower(application.get("name")) != "omni-cio owner web"
        or _lower(application.get("domain")) != hostname.lower()
        or _lower(application.get("type")) != "self_hosted"
        or application.get("allow_authenticate_via_warp") is not False
        or application.get("allow_iframe") is not False
        or application.get("enable_binding_cookie") is not True
        or application.get("http_only_cookie_attribute") is not True
        or application.get("options_preflight_bypass") is not False
    ):
        raise StateGuardError("WP22A_PROVIDER_STATE_APPLICATION_INVALID")

    dns = _values(resources["cloudflare_dns_record.omni_cio"])
    if (
        str(dns.get("zone_id", "")) != zone_id
        or _lower(dns.get("name")) != hostname.lower()
        or _lower(dns.get("type")) != "cname"
        or dns.get("proxied") is not True
    ):
        raise StateGuardError("WP22A_PROVIDER_STATE_DNS_INVALID")

    config_values = _values(
        resources["cloudflare_zero_trust_tunnel_cloudflared_config.omni_cio"]
    )
    if str(config_values.get("account_id", "")) != account_id:
        raise StateGuardError("WP22A_PROVIDER_STATE_TUNNEL_CONFIG_ACCOUNT_INVALID")
    config = config_values.get("config")
    ingress = config.get("ingress") if isinstance(config, dict) else None
    if not isinstance(ingress, list) or len(ingress) != 2:
        raise StateGuardError("WP22A_PROVIDER_STATE_TUNNEL_INGRESS_INVALID")
    first, second = ingress
    if not isinstance(first, dict) or not isinstance(second, dict):
        raise StateGuardError("WP22A_PROVIDER_STATE_TUNNEL_INGRESS_INVALID")
    if (
        _lower(first.get("hostname")) != hostname.lower()
        or _lower(first.get("service")) != "http://127.0.0.1:8765"
        or _lower(second.get("service")) != "http_status:404"
    ):
        raise StateGuardError("WP22A_PROVIDER_STATE_TUNNEL_INGRESS_INVALID")
    origin_request = first.get("origin_request") or first.get("originRequest")
    access = origin_request.get("access") if isinstance(origin_request, dict) else None
    if (
        not isinstance(access, dict)
        or access.get("required") is not True
        or _lower(access.get("team_name") or access.get("teamName"))
        != team_name.lower()
    ):
        raise StateGuardError("WP22A_PROVIDER_STATE_TUNNEL_ACCESS_INVALID")


def validate_state_document(payload: Mapping[str, Any]) -> None:
    values = payload.get("values")
    if not isinstance(values, dict):
        raise StateGuardError("WP22A_PROVIDER_STATE_VALUES_MISSING")
    account_id = os.environ.get("WP22A_CLOUDFLARE_ACCOUNT_ID", "").strip()
    zone_id = os.environ.get("WP22A_CLOUDFLARE_ZONE_ID", "").strip()
    hostname = os.environ.get("WP22A_EXTERNAL_HOST", "").strip().lower()
    team_name = os.environ.get("WP22A_CLOUDFLARE_TEAM_NAME", "").strip().lower()
    if not all((account_id, zone_id, hostname, team_name)):
        raise StateGuardError("WP22A_PROVIDER_STATE_EXPECTATION_MISSING")
    validate_state_values(
        values,
        account_id=account_id,
        zone_id=zone_id,
        hostname=hostname,
        team_name=team_name,
    )


def validate_plan_document(payload: Mapping[str, Any], *, destroy: bool) -> None:
    changes = payload.get("resource_changes")
    if not isinstance(changes, list):
        raise StateGuardError("WP22A_PROVIDER_PLAN_RESOURCE_CHANGES_MISSING")
    for resource in changes:
        if not isinstance(resource, dict):
            raise StateGuardError("WP22A_PROVIDER_PLAN_CHANGE_INVALID")
        address = str(resource.get("address", ""))
        mode = str(resource.get("mode", "managed"))
        if mode != "managed":
            continue
        if address not in MANAGED_ADDRESSES:
            raise StateGuardError("WP22A_PROVIDER_PLAN_UNKNOWN_RESOURCE")
        change = resource.get("change")
        actions = change.get("actions") if isinstance(change, dict) else None
        if not isinstance(actions, list):
            raise StateGuardError("WP22A_PROVIDER_PLAN_ACTION_INVALID")
        action_tuple = tuple(str(action) for action in actions)
        if destroy:
            if action_tuple not in {("delete",), ("no-op",)}:
                raise StateGuardError("WP22A_PROVIDER_DESTROY_PLAN_ACTION_INVALID")
        else:
            if action_tuple not in {("create",), ("update",), ("no-op",)}:
                raise StateGuardError("WP22A_PROVIDER_APPLY_PLAN_ACTION_INVALID")
    planned_values = payload.get("planned_values")
    if not destroy and isinstance(planned_values, dict):
        account_id = os.environ.get("WP22A_CLOUDFLARE_ACCOUNT_ID", "").strip()
        zone_id = os.environ.get("WP22A_CLOUDFLARE_ZONE_ID", "").strip()
        hostname = os.environ.get("WP22A_EXTERNAL_HOST", "").strip().lower()
        team_name = os.environ.get("WP22A_CLOUDFLARE_TEAM_NAME", "").strip().lower()
        if all((account_id, zone_id, hostname, team_name)):
            validate_state_values(
                planned_values,
                account_id=account_id,
                zone_id=zone_id,
                hostname=hostname,
                team_name=team_name,
            )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    state_parser = subparsers.add_parser("state")
    state_parser.add_argument("path")
    plan_parser = subparsers.add_parser("plan")
    plan_parser.add_argument("path")
    plan_parser.add_argument("--destroy", action="store_true")
    args = parser.parse_args(argv)
    try:
        payload = _read(args.path)
        if args.command == "state":
            validate_state_document(payload)
        else:
            validate_plan_document(payload, destroy=bool(args.destroy))
    except StateGuardError as exc:
        print(json.dumps({"status": "FAIL", "reason": str(exc)}, sort_keys=True))
        return 2
    print(
        json.dumps(
            {"status": "PASS", "reason": "WP22A_PROVIDER_STATE_GUARD_PASS"},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
