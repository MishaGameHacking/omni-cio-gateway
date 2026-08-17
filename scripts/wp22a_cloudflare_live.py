from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


API_ROOT = "https://api.cloudflare.com/client/v4"
TUNNEL_NAME = "omni-cio-v10-owner-web"
ACCESS_APP_NAME = "Omni-CIO OWNER Web"
ACCESS_POLICY_NAME = "Omni-CIO exact Cloudflare account member"


class Wp22aCloudflareError(RuntimeError):
    pass


def _lower(value: Any) -> str:
    return str(value or "").strip().lower()


def _result(payload: Mapping[str, Any]) -> Any:
    if payload.get("success") is not True:
        raise Wp22aCloudflareError("WP22A_CLOUDFLARE_API_UNSUCCESSFUL")
    if "result" not in payload:
        raise Wp22aCloudflareError("WP22A_CLOUDFLARE_API_RESULT_MISSING")
    return payload["result"]


@dataclass(frozen=True)
class Inputs:
    account_id: str
    zone_id: str
    hostname: str
    team_name: str

    @classmethod
    def from_env(cls) -> "Inputs":
        values = {
            "account_id": os.environ.get("WP22A_CLOUDFLARE_ACCOUNT_ID", "").strip(),
            "zone_id": os.environ.get("WP22A_CLOUDFLARE_ZONE_ID", "").strip(),
            "hostname": os.environ.get("WP22A_EXTERNAL_HOST", "").strip().lower(),
            "team_name": os.environ.get("WP22A_CLOUDFLARE_TEAM_NAME", "").strip().lower(),
        }
        if not all(values.values()):
            raise Wp22aCloudflareError("WP22A_PROTECTED_PROVIDER_INPUT_MISSING")
        return cls(**values)


class CloudflareClient:
    def __init__(self, token: str, api_root: str = API_ROOT) -> None:
        if not token.strip():
            raise Wp22aCloudflareError("WP22A_CLOUDFLARE_API_TOKEN_MISSING")
        self._token = token.strip()
        self._api_root = api_root.rstrip("/")

    def get(self, path: str, query: Mapping[str, str] | None = None) -> Any:
        url = f"{self._api_root}/{path.lstrip('/')}"
        if query:
            url = f"{url}?{urllib.parse.urlencode(query)}"
        request = urllib.request.Request(
            url,
            method="GET",
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/json",
                "User-Agent": "Omni-CIO-V10-WP22A/1",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise Wp22aCloudflareError("WP22A_CLOUDFLARE_API_REQUEST_FAILED") from exc
        if not isinstance(payload, dict):
            raise Wp22aCloudflareError("WP22A_CLOUDFLARE_API_PAYLOAD_INVALID")
        return _result(payload)


def hostname_is_first_level(hostname: str, zone_name: str) -> bool:
    host_labels = [label for label in hostname.strip(".").lower().split(".") if label]
    zone_labels = [label for label in zone_name.strip(".").lower().split(".") if label]
    return (
        len(host_labels) == len(zone_labels) + 1
        and host_labels[1:] == zone_labels
        and bool(host_labels[0])
    )


def certificate_covers(hostname: str, certificate_hosts: Sequence[str]) -> bool:
    hostname = hostname.lower().strip(".")
    for candidate in certificate_hosts:
        name = candidate.lower().strip().strip(".")
        if name == hostname:
            return True
        if name.startswith("*."):
            zone = name[2:]
            if hostname_is_first_level(hostname, zone):
                return True
    return False


def _active_universal_certificate_covers(hostname: str, packs: Any) -> bool:
    if not isinstance(packs, list):
        return False
    for pack in packs:
        if not isinstance(pack, dict):
            continue
        if _lower(pack.get("type")) != "universal" or _lower(pack.get("status")) != "active":
            continue
        certificates = pack.get("certificates")
        if not isinstance(certificates, list):
            continue
        for certificate in certificates:
            if not isinstance(certificate, dict):
                continue
            if _lower(certificate.get("status")) not in {"", "active"}:
                continue
            hosts = certificate.get("hosts")
            if isinstance(hosts, list) and certificate_covers(
                hostname, [str(host) for host in hosts]
            ):
                return True
    return False


def validate_preflight_snapshot(
    *,
    inputs: Inputs,
    zone: Mapping[str, Any],
    universal_ssl: Mapping[str, Any],
    certificate_packs: Any,
    organization: Mapping[str, Any],
    identity_providers: Any,
) -> None:
    if str(zone.get("id", "")) != inputs.zone_id:
        raise Wp22aCloudflareError("WP22A_ZONE_ID_MISMATCH")
    account = zone.get("account")
    if not isinstance(account, dict) or str(account.get("id", "")) != inputs.account_id:
        raise Wp22aCloudflareError("WP22A_ZONE_ACCOUNT_MISMATCH")
    zone_name = _lower(zone.get("name"))
    if _lower(zone.get("status")) != "active" or _lower(zone.get("type")) != "full":
        raise Wp22aCloudflareError("WP22A_ZONE_NOT_ACTIVE_FULL_DNS")
    if bool(zone.get("paused")):
        raise Wp22aCloudflareError("WP22A_ZONE_PAUSED")
    if not hostname_is_first_level(inputs.hostname, zone_name):
        raise Wp22aCloudflareError("WP22A_HOSTNAME_NOT_FIRST_LEVEL")
    if universal_ssl.get("enabled") is not True:
        raise Wp22aCloudflareError("WP22A_UNIVERSAL_SSL_DISABLED")
    if not _active_universal_certificate_covers(inputs.hostname, certificate_packs):
        raise Wp22aCloudflareError("WP22A_UNIVERSAL_CERTIFICATE_NOT_ACTIVE_OR_COVERED")
    expected_auth_domain = f"{inputs.team_name}.cloudflareaccess.com"
    if _lower(organization.get("auth_domain")) != expected_auth_domain:
        raise Wp22aCloudflareError("WP22A_ZERO_TRUST_ORGANIZATION_MISMATCH")
    if organization.get("allow_authenticate_via_warp") is not False:
        raise Wp22aCloudflareError("WP22A_ZERO_TRUST_WARP_AUTH_NOT_DISABLED")
    if organization.get("deny_unmatched_requests") is not True:
        raise Wp22aCloudflareError("WP22A_ZERO_TRUST_DENY_UNMATCHED_NOT_ENABLED")
    if not isinstance(identity_providers, list):
        raise Wp22aCloudflareError("WP22A_IDENTITY_PROVIDER_LIST_INVALID")
    restricted = [
        provider
        for provider in identity_providers
        if isinstance(provider, dict)
        and _lower(provider.get("type")) == "cloudflare"
        and isinstance(provider.get("config"), dict)
        and provider["config"].get("restrict_to_account_members") is True
    ]
    if len(restricted) != 1:
        raise Wp22aCloudflareError("WP22A_RESTRICTED_CLOUDFLARE_IDP_COUNT_INVALID")


def _list_exact(items: Any, key: str, value: str) -> list[Mapping[str, Any]]:
    if not isinstance(items, list):
        return []
    expected = value.lower()
    return [
        item
        for item in items
        if isinstance(item, dict) and _lower(item.get(key)) == expected
    ]


def validate_no_managed_resources(
    *, tunnels: Any, applications: Any, dns_records: Any, hostname: str
) -> None:
    if _list_exact(tunnels, "name", TUNNEL_NAME):
        raise Wp22aCloudflareError("WP22A_STATE_MISSING_BUT_TUNNEL_EXISTS")
    if _list_exact(applications, "name", ACCESS_APP_NAME) or _list_exact(
        applications, "domain", hostname
    ):
        raise Wp22aCloudflareError("WP22A_STATE_MISSING_BUT_ACCESS_APP_EXISTS")
    if _list_exact(dns_records, "name", hostname):
        raise Wp22aCloudflareError("WP22A_STATE_MISSING_BUT_DNS_EXISTS")


def validate_managed_resources(
    *,
    inputs: Inputs,
    tunnels: Any,
    applications: Any,
    dns_records: Any,
    tunnel_config: Mapping[str, Any] | None = None,
    require_healthy_tunnel: bool = False,
) -> Mapping[str, Any]:
    tunnel_matches = _list_exact(tunnels, "name", TUNNEL_NAME)
    if len(tunnel_matches) != 1:
        raise Wp22aCloudflareError("WP22A_TUNNEL_COUNT_INVALID")
    tunnel = tunnel_matches[0]
    if _lower(tunnel.get("config_src")) != "cloudflare":
        raise Wp22aCloudflareError("WP22A_TUNNEL_CONFIG_SOURCE_INVALID")
    if require_healthy_tunnel and _lower(tunnel.get("status")) != "healthy":
        raise Wp22aCloudflareError("WP22A_TUNNEL_NOT_HEALTHY")

    app_matches = _list_exact(applications, "name", ACCESS_APP_NAME)
    if len(app_matches) != 1:
        raise Wp22aCloudflareError("WP22A_ACCESS_APP_COUNT_INVALID")
    app = app_matches[0]
    if _lower(app.get("domain")) != inputs.hostname or _lower(app.get("type")) != "self_hosted":
        raise Wp22aCloudflareError("WP22A_ACCESS_APP_BINDING_INVALID")
    required_app_bools = {
        "allow_authenticate_via_warp": False,
        "allow_iframe": False,
        "app_launcher_visible": False,
        "enable_binding_cookie": True,
        "http_only_cookie_attribute": True,
        "options_preflight_bypass": False,
    }
    for key, expected in required_app_bools.items():
        if app.get(key) is not expected:
            raise Wp22aCloudflareError("WP22A_ACCESS_APP_SECURITY_INVALID")

    dns_matches = _list_exact(dns_records, "name", inputs.hostname)
    if len(dns_matches) != 1:
        raise Wp22aCloudflareError("WP22A_DNS_RECORD_COUNT_INVALID")
    record = dns_matches[0]
    if _lower(record.get("type")) != "cname" or record.get("proxied") is not True:
        raise Wp22aCloudflareError("WP22A_DNS_RECORD_SECURITY_INVALID")
    tunnel_id = str(tunnel.get("id", ""))
    expected_target = f"{tunnel_id}.cfargotunnel.com".lower()
    if _lower(record.get("content")) != expected_target:
        raise Wp22aCloudflareError("WP22A_DNS_TUNNEL_BINDING_INVALID")

    if tunnel_config is not None:
        config = tunnel_config.get("config")
        ingress = config.get("ingress") if isinstance(config, dict) else None
        if not isinstance(ingress, list) or len(ingress) != 2:
            raise Wp22aCloudflareError("WP22A_TUNNEL_INGRESS_INVALID")
        first, second = ingress
        if not isinstance(first, dict) or not isinstance(second, dict):
            raise Wp22aCloudflareError("WP22A_TUNNEL_INGRESS_INVALID")
        if _lower(first.get("hostname")) != inputs.hostname:
            raise Wp22aCloudflareError("WP22A_TUNNEL_HOST_BINDING_INVALID")
        if _lower(first.get("service")) != "http://127.0.0.1:8765":
            raise Wp22aCloudflareError("WP22A_TUNNEL_ORIGIN_INVALID")
        origin_request = first.get("originRequest") or first.get("origin_request")
        access = origin_request.get("access") if isinstance(origin_request, dict) else None
        if not isinstance(access, dict) or access.get("required") is not True:
            raise Wp22aCloudflareError("WP22A_TUNNEL_ACCESS_VALIDATION_MISSING")
        if _lower(access.get("teamName") or access.get("team_name")) != inputs.team_name:
            raise Wp22aCloudflareError("WP22A_TUNNEL_ACCESS_TEAM_INVALID")
        if _lower(second.get("service")) != "http_status:404":
            raise Wp22aCloudflareError("WP22A_TUNNEL_CATCH_ALL_INVALID")

    return {"tunnel": tunnel, "application": app, "dns": record}


def _fetch_preflight(client: CloudflareClient, inputs: Inputs) -> None:
    zone = client.get(f"zones/{inputs.zone_id}")
    universal = client.get(f"zones/{inputs.zone_id}/ssl/universal/settings")
    packs = client.get(
        f"zones/{inputs.zone_id}/ssl/certificate_packs", {"status": "all"}
    )
    organization = client.get(f"accounts/{inputs.account_id}/access/organizations")
    idps = client.get(f"accounts/{inputs.account_id}/access/identity_providers")
    if not all(isinstance(value, dict) for value in (zone, universal, organization)):
        raise Wp22aCloudflareError("WP22A_PREFLIGHT_RESPONSE_SHAPE_INVALID")
    validate_preflight_snapshot(
        inputs=inputs,
        zone=zone,
        universal_ssl=universal,
        certificate_packs=packs,
        organization=organization,
        identity_providers=idps,
    )


def _managed_lists(client: CloudflareClient, inputs: Inputs) -> tuple[Any, Any, Any]:
    tunnels = client.get(
        f"accounts/{inputs.account_id}/cfd_tunnel", {"name": TUNNEL_NAME}
    )
    apps = client.get(f"accounts/{inputs.account_id}/access/apps")
    dns = client.get(
        f"zones/{inputs.zone_id}/dns_records", {"name": inputs.hostname}
    )
    return tunnels, apps, dns


def run(command: str) -> Mapping[str, Any]:
    inputs = Inputs.from_env()
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    client = CloudflareClient(token)
    _fetch_preflight(client, inputs)
    if command == "preflight":
        return {
            "status": "PASS",
            "reason": "WP22A_CLOUDFLARE_PREFLIGHT_PASS",
            "zone_active_full_dns": True,
            "first_level_hostname": True,
            "universal_ssl_covered": True,
            "zero_trust_hardened": True,
            "restricted_cloudflare_idp": True,
        }

    tunnels, apps, dns = _managed_lists(client, inputs)
    if command == "assert-empty":
        validate_no_managed_resources(
            tunnels=tunnels,
            applications=apps,
            dns_records=dns,
            hostname=inputs.hostname,
        )
        return {"status": "PASS", "reason": "WP22A_NO_MANAGED_LIVE_RESOURCES"}

    matches = validate_managed_resources(
        inputs=inputs,
        tunnels=tunnels,
        applications=apps,
        dns_records=dns,
        require_healthy_tunnel=command == "verify-live",
    )
    tunnel_id = str(matches["tunnel"].get("id", ""))
    tunnel_config = client.get(
        f"accounts/{inputs.account_id}/cfd_tunnel/{tunnel_id}/configurations"
    )
    if not isinstance(tunnel_config, dict):
        raise Wp22aCloudflareError("WP22A_TUNNEL_CONFIG_RESPONSE_INVALID")
    validate_managed_resources(
        inputs=inputs,
        tunnels=tunnels,
        applications=apps,
        dns_records=dns,
        tunnel_config=tunnel_config,
        require_healthy_tunnel=command == "verify-live",
    )
    return {
        "status": "PASS",
        "reason": (
            "WP22A_CLOUDFLARE_LIVE_PASS"
            if command == "verify-live"
            else "WP22A_CLOUDFLARE_PROVIDER_STATE_PASS"
        ),
        "access_application": True,
        "tunnel_ingress": True,
        "proxied_dns": True,
        "catch_all_deny": True,
        "tunnel_healthy": command == "verify-live",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=("preflight", "assert-empty", "verify", "verify-live")
    )
    args = parser.parse_args(argv)
    try:
        result = run(args.command)
    except Wp22aCloudflareError as exc:
        print(json.dumps({"status": "FAIL", "reason": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
