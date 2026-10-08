#!/usr/bin/env python3
"""Reconcile the private network required by OmniCIO auth/PostgreSQL."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from timeweb_http import request_json

API_ROOT = "https://api.timeweb.cloud/api"


class InfraError(RuntimeError):
    """Deterministic auth infrastructure failure."""


class TimewebApiError(RuntimeError):
    """Structured Timeweb API failure without secrets."""

    def __init__(self, status_code: int, error_code: str, message: str) -> None:
        super().__init__(
            f"Timeweb API HTTP {status_code} "
            f"error_code={error_code or 'unknown'} "
        )
        self.status_code = status_code
        self.error_code = error_code


@dataclass(frozen=True, slots=True)
class DesiredNetwork:
    name: str
    subnet_v4: str
    location: str
    availability_zone: str


class TimewebClient:
    def __init__(self, token: str) -> None:
        if not token:
            raise InfraError("TIMEWEB_CLOUD_TOKEN is missing or empty")
        self._token = token

    def request(
        self,
        method: str,
        path: str,
        *,
        api_version: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = None
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
        }
        if payload is not None:
            body = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(
            f"{API_ROOT}/{api_version}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            return request_json(request, timeout=30)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode(errors="replace")
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = {}
            value = parsed.get("message", "")
            if isinstance(value, list):
                message = "; ".join(str(item) for item in value)
            else:
                message = str(value or "")
            raise TimewebApiError(
                exc.code,
                str(parsed.get("error_code") or ""),
                message,
            ) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise InfraError("Timeweb request outcome was not confirmed") from exc

    def get_servers(self) -> list[dict[str, Any]]:
        return list(self.request("GET", "/servers", api_version="v1").get("servers") or [])

    def get_vpcs(self) -> list[dict[str, Any]]:
        return list(self.request("GET", "/vpcs", api_version="v2").get("vpcs") or [])

    def get_server_presets(self) -> list[dict[str, Any]]:
        return list(
            self.request("GET", "/presets/servers", api_version="v1").get(
                "server_presets"
            )
            or []
        )

    def create_vpc(self, desired: DesiredNetwork) -> dict[str, Any]:
        response = self.request(
            "POST",
            "/vpcs",
            api_version="v2",
            payload={
                "name": desired.name,
                "subnet_v4": desired.subnet_v4,
                "location": desired.location,
                "availability_zone": desired.availability_zone,
                "description": "Private network for OmniCIO application and PostgreSQL",
            },
        )
        return dict(response.get("vpc") or {})

    def get_vpc_services(self, vpc_id: str) -> list[dict[str, Any]]:
        response = self.request(
            "GET",
            f"/vpcs/{vpc_id}/services",
            api_version="v2",
        )
        return list(response.get("services") or [])


def add_summary(line: str) -> None:
    print(line)
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def set_output(name: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")


def find_managed_server(
    servers: list[dict[str, Any]],
    *,
    name: str,
    comment: str,
) -> dict[str, Any]:
    matches = [server for server in servers if server.get("name") == name]
    if len(matches) != 1:
        raise InfraError(
            f"Expected exactly one managed server named {name!r}; found {len(matches)}"
        )
    server = matches[0]
    if server.get("comment") != comment:
        raise InfraError("Same-name server is not owned by this reconciler")
    return server


def server_supports_private_network(
    server: dict[str, Any],
    presets: list[dict[str, Any]],
) -> bool:
    preset_id = int(float(server.get("preset_id") or 0))
    if preset_id <= 0:
        raise InfraError("Managed VDS has no preset_id; cannot prove VPC compatibility")

    matches = [
        preset
        for preset in presets
        if int(float(preset.get("id") or 0)) == preset_id
    ]
    if len(matches) != 1:
        raise InfraError(
            f"Expected exactly one server preset {preset_id}; found {len(matches)}"
        )
    return bool(matches[0].get("is_allowed_local_network"))


def find_vpc(vpcs: list[dict[str, Any]], desired: DesiredNetwork) -> dict[str, Any] | None:
    matches = [vpc for vpc in vpcs if vpc.get("name") == desired.name]
    if len(matches) > 1:
        raise InfraError(f"Multiple VPCs share managed name {desired.name!r}")
    if not matches:
        return None

    vpc = matches[0]
    actual = (
        str(vpc.get("subnet_v4") or ""),
        str(vpc.get("location") or ""),
        str(vpc.get("availability_zone") or ""),
    )
    expected = (desired.subnet_v4, desired.location, desired.availability_zone)
    if actual != expected:
        raise InfraError(
            "Managed VPC exists with unexpected immutable placement/subnet: "
            f"actual={actual!r}, expected={expected!r}"
        )
    return vpc


def server_is_attached(
    services: list[dict[str, Any]],
    *,
    server_id: int,
    server_name: str,
) -> bool:
    for service in services:
        service_id = int(float(service.get("id") or 0))
        service_type = str(service.get("type") or "").lower()
        service_name = str(service.get("name") or "")
        if service_id == server_id and service_name == server_name:
            return service_type in {"server", "vds", "cloud_server", ""}
    return False


def reconcile(
    client: TimewebClient,
    *,
    desired: DesiredNetwork,
    server_name: str,
    server_comment: str,
) -> int:
    add_summary("## OmniCIO auth private network")
    add_summary(
        f"- Desired VPC: `{desired.name}`, `{desired.location}/"
        f"{desired.availability_zone}`, subnet `{desired.subnet_v4}`."
    )

    server = find_managed_server(
        client.get_servers(),
        name=server_name,
        comment=server_comment,
    )
    server_id = int(float(server["id"]))
    add_summary(f"- Managed VDS: `{server_name}` (id `{server_id}`).")

    if not server_supports_private_network(server, client.get_server_presets()):
        add_summary(
            "- Result: `pending_server_preset`. The current VDS tariff does not "
            "allow a private network."
        )
        add_summary(
            "- No VPC or database was created. The VDS must first be moved to a "
            "Timeweb tariff with `is_allowed_local_network=true`."
        )
        set_output("status", "pending_server_preset")
        return 0

    vpc = find_vpc(client.get_vpcs(), desired)
    if vpc is None:
        add_summary("- VPC does not exist; creating the approved private network.")
        vpc = client.create_vpc(desired)
        if "id" not in vpc:
            raise InfraError("Timeweb returned success without a VPC id")
        add_summary(f"- Created VPC id: `{vpc['id']}`.")

    vpc_id = str(vpc["id"])
    services = client.get_vpc_services(vpc_id)
    if not server_is_attached(
        services,
        server_id=server_id,
        server_name=server_name,
    ):
        add_summary(
            "- Result: `pending_server_network`. The managed VDS is not yet "
            "attached to this VPC."
        )
        add_summary(
            "- Timeweb's public API exposes VPC creation/read operations but no "
            "documented existing-service attach mutation. No undocumented API call "
            "will be guessed."
        )
        add_summary(
            "- No database was created. Attach the existing VDS to this VPC in "
            "Timeweb Cloud, then rerun/allow the next reconcile."
        )
        set_output("status", "pending_server_network")
        set_output("vpc_id", vpc_id)
        return 0

    add_summary("- Managed VDS is attached to the private VPC.")
    add_summary("- Result: `network_ready`.")
    set_output("status", "network_ready")
    set_output("vpc_id", vpc_id)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-name", required=True)
    parser.add_argument("--server-comment", required=True)
    parser.add_argument("--vpc-name", required=True)
    parser.add_argument("--subnet-v4", required=True)
    parser.add_argument("--location", required=True)
    parser.add_argument("--availability-zone", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        client = TimewebClient(os.environ.get("TIMEWEB_CLOUD_TOKEN", ""))
        return reconcile(
            client,
            desired=DesiredNetwork(
                name=args.vpc_name,
                subnet_v4=args.subnet_v4,
                location=args.location,
                availability_zone=args.availability_zone,
            ),
            server_name=args.server_name,
            server_comment=args.server_comment,
        )
    except (InfraError, TimewebApiError) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
