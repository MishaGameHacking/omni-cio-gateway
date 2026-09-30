#!/usr/bin/env python3
"""Reconcile the minimal Timeweb white-site infrastructure.

The desired state is intentionally narrow: one Ubuntu 24.04 server, one public
IPv4, Nginx, and a blank white page. The module uses only the Python standard
library so the deployment runner has no package-install bootstrap dependency.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

API_ROOT = "https://api.timeweb.cloud/api"
PLACEMENT_CAPACITY_ERROR_CODE = "no_free_node"
LOCATION_CAPACITY_ERROR_CODE = "servers_is_run_out_error"


class DeploymentError(RuntimeError):
    """A deterministic deployment/configuration failure."""


class AmbiguousProviderError(RuntimeError):
    """A provider request may or may not have reached Timeweb."""


class TimewebApiError(RuntimeError):
    """A structured Timeweb API error with safe operational metadata."""

    def __init__(
        self,
        *,
        status_code: int,
        error_code: str,
        message: str,
        response_id: str,
    ) -> None:
        super().__init__(
            f"Timeweb API returned HTTP {status_code}"
            f" error_code={error_code or 'unknown'}"
            f" response_id={response_id or 'unknown'}"
            f" message={message or 'unknown'}"
        )
        self.status_code = status_code
        self.error_code = error_code
        self.provider_message = message
        self.response_id = response_id


@dataclass(frozen=True)
class Placement:
    preset_id: int
    location: str
    availability_zone: str | None
    price_rub: Decimal
    cpu: int
    ram_mb: int
    disk_mb: int
    bandwidth_mbps: int

    @property
    def label(self) -> str:
        zone = self.availability_zone or "provider-auto"
        return f"{self.preset_id}@{zone}"


class TimewebClient:
    def __init__(self, token: str) -> None:
        if not token:
            raise DeploymentError("TIMEWEB_CLOUD_TOKEN is missing or empty.")
        self._token = token

    def request(
        self,
        method: str,
        path: str,
        *,
        api_version: str = "v1",
        payload: dict[str, Any] | None = None,
        timeout: int = 30,
    ) -> dict[str, Any]:
        if not path.startswith("/"):
            raise DeploymentError(f"Invalid Timeweb API path: {path!r}")

        data = None
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
        }
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(
            f"{API_ROOT}/{api_version}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8")
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                error = json.loads(body)
            except json.JSONDecodeError:
                error = {}
            message_value = error.get("message", "")
            if isinstance(message_value, list):
                message = "; ".join(str(item) for item in message_value)
            else:
                message = str(message_value or "")
            raise TimewebApiError(
                status_code=exc.code,
                error_code=str(error.get("error_code") or ""),
                message=message,
                response_id=str(error.get("response_id") or ""),
            ) from exc
        except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
            raise AmbiguousProviderError(
                f"Ambiguous Timeweb {method} {path}: {type(exc).__name__}"
            ) from exc

    def get_servers(self) -> list[dict[str, Any]]:
        return list(self.request("GET", "/servers").get("servers") or [])

    def get_server(self, server_id: int) -> dict[str, Any]:
        return dict(
            self.request("GET", f"/servers/{server_id}").get("server") or {}
        )

    def get_server_os(self) -> list[dict[str, Any]]:
        return list(
            self.request("GET", "/os/servers").get("servers_os") or []
        )

    def get_server_presets(self) -> list[dict[str, Any]]:
        return list(
            self.request("GET", "/presets/servers").get("server_presets") or []
        )

    def get_locations(self) -> list[dict[str, Any]]:
        return list(
            self.request(
                "GET",
                "/locations",
                api_version="v2",
            ).get("locations")
            or []
        )

    def create_server(self, payload: dict[str, Any]) -> dict[str, Any]:
        return dict(
            self.request(
                "POST",
                "/servers",
                payload=payload,
                timeout=45,
            ).get("server")
            or {}
        )


def decimal_value(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise DeploymentError(f"Invalid numeric provider value: {value!r}") from exc


def integer_value(value: Any) -> int:
    return int(decimal_value(value))


def os_disk_min_mb(value: Any) -> Decimal:
    disk_min = decimal_value(value or 0)
    # Timeweb preset disk values are MB. Current OS requirements returned by the
    # API use small GB-like values for some images. Preserve the existing safe
    # conversion until the provider publishes explicit units on that field.
    if Decimal("0") < disk_min < Decimal("1024"):
        return disk_min * Decimal("1024")
    return disk_min


def select_ubuntu_2404(client: TimewebClient) -> dict[str, Any]:
    matches = [
        item
        for item in client.get_server_os()
        if str(item.get("name", "")).lower() == "ubuntu"
        and str(item.get("version", "")) == "24.04"
    ]
    if not matches:
        raise DeploymentError(
            "Ubuntu 24.04 is not available in the current Timeweb OS list."
        )
    return max(matches, key=lambda item: decimal_value(item.get("id", 0)))


def select_compatible_presets(
    *,
    os_info: dict[str, Any],
    presets: list[dict[str, Any]],
    target_location: str,
) -> list[dict[str, Any]]:
    requirements = dict(os_info.get("requirements") or {})
    cpu_min = decimal_value(requirements.get("cpu_min") or 0)
    ram_min = decimal_value(requirements.get("ram_min") or 0)
    disk_min_mb = os_disk_min_mb(requirements.get("disk_min") or 0)
    bandwidth_min = decimal_value(requirements.get("bandwidth_min") or 0)

    normalized_target_location = target_location.strip().lower()
    compatible: list[dict[str, Any]] = []
    for preset in presets:
        preset_location = str(preset.get("location") or "").strip().lower()
        if preset_location != normalized_target_location:
            continue

        price = decimal_value(preset.get("price") or 0)
        if price <= 0:
            continue
        if decimal_value(preset.get("cpu") or 0) < cpu_min:
            continue
        if decimal_value(preset.get("ram") or 0) < ram_min:
            continue
        if decimal_value(preset.get("disk") or 0) < disk_min_mb:
            continue
        if decimal_value(preset.get("bandwidth") or 0) < bandwidth_min:
            continue
        compatible.append(preset)

    return sorted(
        compatible,
        key=lambda item: (
            decimal_value(item.get("price") or 0),
            decimal_value(item.get("ram") or 0),
            decimal_value(item.get("disk") or 0),
            decimal_value(item.get("cpu") or 0),
            str(item.get("location") or ""),
            decimal_value(item.get("id") or 0),
        ),
    )


def select_budget_presets(
    *,
    os_info: dict[str, Any],
    presets: list[dict[str, Any]],
    max_server_price_rub: Decimal,
    target_location: str,
) -> list[dict[str, Any]]:
    return [
        preset
        for preset in select_compatible_presets(
            os_info=os_info,
            presets=presets,
            target_location=target_location,
        )
        if decimal_value(preset.get("price") or 0) <= max_server_price_rub
    ]


def availability_zones_by_location(
    locations: list[dict[str, Any]],
) -> dict[str, tuple[str, ...]]:
    result: dict[str, tuple[str, ...]] = {}
    for item in locations:
        location = str(item.get("location") or "").strip()
        if not location:
            continue
        zones = tuple(
            str(zone).strip()
            for zone in (item.get("availability_zones") or [])
            if str(zone).strip()
        )
        result[location.lower()] = zones
    return result


def build_placements(
    *,
    presets: list[dict[str, Any]],
    locations: list[dict[str, Any]],
    target_location: str,
    target_availability_zone: str,
) -> list[Placement]:
    zone_map = availability_zones_by_location(locations)
    normalized_target_location = target_location.strip().lower()
    normalized_target_zone = target_availability_zone.strip().lower()

    provider_zones = zone_map.get(normalized_target_location) or ()
    matching_zone = next(
        (
            zone
            for zone in provider_zones
            if zone.strip().lower() == normalized_target_zone
        ),
        None,
    )
    if matching_zone is None:
        raise DeploymentError(
            f"Timeweb location {target_location!r} does not currently expose "
            f"availability zone {target_availability_zone!r}."
        )

    placements: list[Placement] = []
    seen: set[int] = set()

    for preset in presets:
        preset_id = integer_value(preset["id"])
        location = str(preset.get("location") or "").strip()
        if location.lower() != normalized_target_location:
            continue
        if preset_id in seen:
            continue
        seen.add(preset_id)
        placements.append(
            Placement(
                preset_id=preset_id,
                location=location,
                availability_zone=matching_zone,
                price_rub=decimal_value(preset.get("price") or 0),
                cpu=integer_value(preset.get("cpu") or 0),
                ram_mb=integer_value(preset.get("ram") or 0),
                disk_mb=integer_value(preset.get("disk") or 0),
                bandwidth_mbps=integer_value(
                    preset.get("bandwidth") or 100
                ),
            )
        )

    return placements


def find_named_server(
    client: TimewebClient,
    server_name: str,
) -> dict[str, Any] | None:
    matches = [
        server
        for server in client.get_servers()
        if server.get("name") == server_name
    ]
    if len(matches) > 1:
        raise DeploymentError(
            f"Multiple Timeweb servers share the managed name {server_name!r}; "
            "refusing to guess resource authority."
        )
    return matches[0] if matches else None


def server_id(server: dict[str, Any]) -> int:
    return integer_value(server["id"])


def public_ipv4_addresses(server: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for network in server.get("networks") or []:
        network_type = str(network.get("type") or "").lower()
        if network_type in {"local", "private"}:
            continue
        for item in network.get("ips") or []:
            value = item.get("ip")
            if not value:
                continue
            try:
                address = ipaddress.ip_address(value)
            except ValueError:
                continue
            if address.version == 4:
                result.append(value)
    return result


def add_summary(line: str) -> None:
    """Emit operational context to the workflow log.

    GitHub-provided output/summary file paths are intentionally not opened from
    Python. The workflow log is the canonical diagnostic surface for this
    reconciler and avoids treating environment-controlled paths as file sinks.
    """
    print(line)


def reconcile_after_ambiguous_create(
    *,
    client: TimewebClient,
    server_name: str,
    server_comment: str,
    attempts: int = 6,
    sleep_seconds: int = 10,
) -> dict[str, Any] | None:
    for _ in range(attempts):
        time.sleep(sleep_seconds)
        server = find_named_server(client, server_name)
        if server and server.get("comment") == server_comment:
            return server
    return None


def wait_for_ipv4(
    client: TimewebClient,
    server_id_value: int,
    *,
    attempts: int = 30,
    sleep_seconds: int = 10,
) -> tuple[dict[str, Any], str]:
    latest: dict[str, Any] = {}
    for _ in range(attempts):
        latest = client.get_server(server_id_value)
        addresses = public_ipv4_addresses(latest)
        if addresses:
            return latest, addresses[0]
        time.sleep(sleep_seconds)
    raise DeploymentError(
        f"Server {server_id_value} exists, but no public IPv4 appeared "
        "within the readiness window."
    )


def wait_for_web_port(
    ip: str,
    *,
    attempts: int = 36,
    sleep_seconds: int = 10,
) -> None:
    """Wait until Nginx accepts TCP connections on the bootstrap HTTP port.

    No credentials or application data are sent over clear text. Content and
    certificate readiness are verified later by the dedicated HTTPS workflow.
    """
    address = ipaddress.ip_address(ip)
    if address.version != 4:
        raise DeploymentError("Bootstrap web readiness requires a public IPv4.")

    last_error = "not attempted"
    for _ in range(attempts):
        try:
            with socket.create_connection((str(address), 80), timeout=5):
                return
        except (OSError, TimeoutError, socket.timeout) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        time.sleep(sleep_seconds)
    raise DeploymentError(
        "Server control plane is reachable, but the Nginx TCP port did not "
        f"become ready within the readiness window: {last_error}"
    )


def cloud_init_script() -> str:
    return """#!/bin/sh
set -eu
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y nginx
cat > /var/www/html/index.html <<'EOF'
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="omni-cio-white-site" content="1">
  <title></title>
  <style>
    html, body {
      width: 100%;
      height: 100%;
      margin: 0;
      background: #fff;
    }
  </style>
</head>
<body></body>
</html>
EOF
systemctl enable nginx
systemctl restart nginx
"""


def create_payload(
    *,
    os_info: dict[str, Any],
    placement: Placement,
    server_name: str,
    server_comment: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": server_name,
        "comment": server_comment,
        "os_id": integer_value(os_info["id"]),
        "preset_id": placement.preset_id,
        "bandwidth": placement.bandwidth_mbps,
        "is_ddos_guard": False,
        "network": {"floating_ip": "create_ip"},
        "cloud_init": cloud_init_script(),
    }
    if placement.availability_zone:
        payload["availability_zone"] = placement.availability_zone
    return payload


def create_with_capacity_fallback(
    *,
    client: TimewebClient,
    os_info: dict[str, Any],
    placements: list[Placement],
    server_name: str,
    server_comment: str,
) -> tuple[dict[str, Any] | None, list[str]]:
    capacity_failures: list[str] = []
    exhausted_locations: set[str] = set()

    for placement in placements:
        if placement.location in exhausted_locations:
            capacity_failures.append(placement.label)
            add_summary(
                f"- Skipping `{placement.label}`: location "
                f"`{placement.location}` is already proven out of capacity."
            )
            continue

        payload = create_payload(
            os_info=os_info,
            placement=placement,
            server_name=server_name,
            server_comment=server_comment,
        )
        add_summary(
            "- Create candidate: "
            f"preset `{placement.preset_id}`, "
            f"zone `{placement.availability_zone or 'provider-auto'}`, "
            f"price {placement.price_rub} RUB."
        )

        try:
            created = client.create_server(payload)
        except AmbiguousProviderError:
            add_summary(
                "- Create response was ambiguous; performing bounded "
                "read-only reconciliation before any further mutation."
            )
            created = reconcile_after_ambiguous_create(
                client=client,
                server_name=server_name,
                server_comment=server_comment,
            )
            if not created:
                raise DeploymentError(
                    "Create request had an ambiguous result and reconciliation "
                    "did not prove whether a server was created. Refusing to "
                    "issue another create mutation."
                )
            return created, capacity_failures
        except TimewebApiError as exc:
            is_placement_capacity = (
                exc.status_code == 409
                and exc.error_code == PLACEMENT_CAPACITY_ERROR_CODE
            )
            is_location_capacity = (
                exc.status_code in {400, 409}
                and exc.error_code == LOCATION_CAPACITY_ERROR_CODE
            )

            if is_placement_capacity:
                capacity_failures.append(placement.label)
                add_summary(
                    f"- Capacity unavailable for `{placement.label}`; "
                    "trying the next pre-approved placement."
                )
                continue

            if is_location_capacity:
                capacity_failures.append(placement.label)
                exhausted_locations.add(placement.location)
                add_summary(
                    f"- Location `{placement.location}` is out of server "
                    "capacity; remaining candidates in that location will be "
                    "skipped without provider mutations."
                )
                continue

            if exc.status_code in {409, 423}:
                add_summary(
                    "- Provider returned a conflict/locked response; "
                    "performing bounded read-only reconciliation."
                )
                created = reconcile_after_ambiguous_create(
                    client=client,
                    server_name=server_name,
                    server_comment=server_comment,
                )
                if created:
                    return created, capacity_failures
            raise

        if created:
            return created, capacity_failures

        raise DeploymentError(
            "Timeweb returned success without a server object; refusing to "
            "guess whether the create mutation succeeded."
        )

    return None, capacity_failures


def reconcile(
    *,
    client: TimewebClient,
    mode: str,
    confirm: str,
    server_name: str,
    server_comment: str,
    max_server_price_rub: Decimal,
    target_location: str,
    target_availability_zone: str,
) -> int:
    add_summary("## Timeweb white site")
    add_summary(f"- Mode: `{mode}`")
    add_summary(
        f"- Desired state: `present`; Moscow placement "
        f"`{target_location}/{target_availability_zone}`; server budget "
        f"ceiling: {max_server_price_rub} RUB/month API price."
    )

    ubuntu = select_ubuntu_2404(client)
    server_presets = client.get_server_presets()
    compatible_presets = select_compatible_presets(
        os_info=ubuntu,
        presets=server_presets,
        target_location=target_location,
    )
    if not compatible_presets:
        raise DeploymentError(
            "No Ubuntu 24.04 server preset satisfies the current requirements "
            f"in Timeweb location {target_location!r}."
        )

    presets = [
        preset
        for preset in compatible_presets
        if decimal_value(preset.get("price") or 0) <= max_server_price_rub
    ]
    if not presets:
        cheapest = compatible_presets[0]
        cheapest_price = decimal_value(cheapest.get("price") or 0)
        add_summary(
            "- Result: `pending_budget`. Cheapest compatible Moscow preset "
            f"is `{integer_value(cheapest['id'])}` at "
            f"{cheapest_price} RUB/month server price, above the approved "
            f"{max_server_price_rub} RUB ceiling."
        )
        add_summary(
            "- No Timeweb resource was created or changed. Increase the "
            "versioned budget ceiling only after explicit approval."
        )
        print(
            "::warning title=Timeweb budget pending::Cheapest compatible "
            f"Moscow server is {cheapest_price} RUB/month, above the approved "
            f"{max_server_price_rub} RUB ceiling. No resource was created."
        )
        return 0

    placements = build_placements(
        presets=presets,
        locations=client.get_locations(),
        target_location=target_location,
        target_availability_zone=target_availability_zone,
    )
    if not placements:
        raise DeploymentError(
            "No Timeweb placement candidate could be derived from the current "
            "preset and location catalogs."
        )

    candidate_labels = ", ".join(item.label for item in placements)
    add_summary(
        f"- Placement candidates within budget: {len(placements)} "
        f"(`{candidate_labels}`)."
    )
    add_summary(
        "- Public IPv4: required and requested with the server; "
        "Timeweb bills IPv4 separately."
    )

    existing = find_named_server(client, server_name)
    if existing:
        existing_id = server_id(existing)
        addresses = public_ipv4_addresses(existing)
        add_summary(
            f"- Existing server: `{server_name}` (id `{existing_id}`, "
            f"status `{existing.get('status', 'unknown')}`)."
        )
        if addresses:
            add_summary(f"- IPv4: http://{addresses[0]}/")

        if existing.get("comment") != server_comment:
            raise DeploymentError(
                "A same-name server already exists but is not marked as "
                "managed by this reconciler. Refusing to mutate it."
            )

        existing_location = str(existing.get("location") or "").lower()
        existing_zone = str(existing.get("availability_zone") or "").lower()
        if (
            existing_location != target_location.lower()
            or existing_zone != target_availability_zone.lower()
        ):
            raise DeploymentError(
                "Managed server exists outside the required Moscow placement: "
                f"actual={existing_location or 'unknown'}/"
                f"{existing_zone or 'unknown'}, required="
                f"{target_location}/{target_availability_zone}. "
                "Automatic cross-region migration/deletion is not permitted."
            )

        if mode == "plan":
            add_summary(
                "- Plan result: managed server already exists; no resource "
                "would be created."
            )
            return 0

        latest, ip = wait_for_ipv4(client, existing_id)
        add_summary(
            f"- Server status: `{latest.get('status', 'unknown')}`; "
            f"IPv4: {ip}"
        )
        wait_for_web_port(ip)
        add_summary(f"- Result: existing managed server web port is ready on {ip}.")
        return 0

    if mode == "plan":
        add_summary(
            "- Plan result: no managed server exists. Reconcile/deploy would "
            "create at most one server within the budget ceiling."
        )
        add_summary("- No Timeweb resource was created or changed.")
        return 0

    if mode == "deploy" and confirm != "CREATE":
        raise DeploymentError(
            "Manual deploy requires the confirmation input to be exactly CREATE."
        )
    if mode not in {"deploy", "reconcile"}:
        raise DeploymentError(f"Unsupported action mode: {mode!r}")

    created, capacity_failures = create_with_capacity_fallback(
        client=client,
        os_info=ubuntu,
        placements=placements,
        server_name=server_name,
        server_comment=server_comment,
    )
    if not created:
        blocked = ", ".join(capacity_failures) or "none"
        add_summary(
            "- Result: `pending_capacity`. Timeweb reported insufficient "
            f"capacity for every pre-approved placement ({blocked})."
        )
        add_summary(
            "- No server was created. Scheduled reconciliation will retry "
            "without increasing the approved server budget."
        )
        print(
            "::warning title=Timeweb capacity pending::No approved Moscow "
            "placement currently has a free node. Scheduled reconciliation "
            "will retry without increasing the server budget."
        )
        return 0

    if "id" not in created:
        created = find_named_server(client, server_name) or {}
    if "id" not in created:
        raise DeploymentError(
            "Timeweb did not return or reconcile a created server ID."
        )

    created_id = server_id(created)
    add_summary(f"- Created server id: `{created_id}`.")
    latest, ip = wait_for_ipv4(client, created_id)
    add_summary(
        f"- Server status: `{latest.get('status', 'unknown')}`; "
        f"IPv4: {ip}"
    )
    wait_for_web_port(ip)
    add_summary(f"- Result: managed server web port is ready on {ip}.")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("plan", "deploy", "reconcile"),
        required=True,
    )
    parser.add_argument("--confirm", default="")
    parser.add_argument("--server-name", required=True)
    parser.add_argument("--server-comment", required=True)
    parser.add_argument("--max-server-price-rub", required=True)
    parser.add_argument("--target-location", required=True)
    parser.add_argument("--target-availability-zone", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        max_price = decimal_value(args.max_server_price_rub)
        if max_price <= 0:
            raise DeploymentError("Server budget ceiling must be positive.")

        client = TimewebClient(os.environ.get("TIMEWEB_CLOUD_TOKEN", ""))
        return reconcile(
            client=client,
            mode=args.mode,
            confirm=args.confirm,
            server_name=args.server_name,
            server_comment=args.server_comment,
            max_server_price_rub=max_price,
            target_location=args.target_location,
            target_availability_zone=args.target_availability_zone,
        )
    except (DeploymentError, TimewebApiError) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
