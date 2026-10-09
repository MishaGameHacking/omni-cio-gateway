#!/usr/bin/env python3
"""Reconcile OmniCIO private PostgreSQL and bootstrap server-side secrets."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import pathlib
import re
import shlex
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import suppress
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from inplace_upgrade import (
    MODE as SINGLE_DATABASE_MODE,
)
from inplace_upgrade import (
    OPERATIONS,
    UpgradeBlocked,
    load_plan,
    migration_bodies,
    render_remote_upgrade,
    validate_operation,
)
from timeweb_addresses import network_addresses
from timeweb_http import request_json
from timeweb_recovery import (
    RecoveryBlocked,
    ensure_recovery_point,
    get_schedule,
    inspect_provider_recovery,
    inspect_restore_capacity,
    load_policy,
    validate_budget,
)
from timeweb_ssh_trust import (
    ssh_base_args,
    ssh_host_key_mismatch_message,
    ssh_keygen_executable,
    trusted_host_entry,
    trusted_host_fingerprint,
)
from verify_main_release import ReleaseBlocked, release_context, require_checkout

API_ROOT = "https://api.timeweb.cloud/api"
REMOTE_SECRET_PATH = "/etc/omnicio/auth-secrets.env"
REMOTE_RUNTIME_PATH = "/etc/omnicio/runtime.env"
TIMEWEB_DB_PASSWORD_MIN = 8
TIMEWEB_DB_PASSWORD_MAX = 30
TIMEWEB_DB_PASSWORD_SAFE = frozenset(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    "_-"
)
DB_OWNERSHIP_MARKER = "Managed by GitHub Actions: omnicio-auth-postgres"
SSH_READY_ATTEMPTS = 36
SSH_READY_DELAY_SECONDS = 10
STAGE_SCHEMA_MIGRATION = "schema_migration"
INSPECTION_TIMEOUT_SECONDS = 180
REMOTE_STAGES = frozenset({
    "remote_command", "private_network", "secret_bootstrap", "runtime_env", "psql_client",
    STAGE_SCHEMA_MIGRATION,
})
PSQL_DIAGNOSTIC = re.compile(
    rb"(?:psql:<stdin>:([1-9][0-9]{0,8}):[ \t]*)?"
    rb"(?:ERROR|FATAL|PANIC):[ \t]+([0-9A-Z]{5})"
)
MAX_DIAGNOSTIC_BYTES = 65536
UPGRADE_DIAGNOSTIC = re.compile(rb"^OMNICIO_UPGRADE: ([a-z_]{1,64})$", re.MULTILINE)
UNCONFIRMED_UPGRADE = "In-place upgrade result was not confirmed"


class InfraError(RuntimeError):
    """Deterministic auth infrastructure failure."""


class AmbiguousProviderError(RuntimeError):
    """A mutating provider request may or may not have reached Timeweb."""


class TimewebApiError(RuntimeError):
    """Structured Timeweb API error without exposing secrets."""

    def __init__(self, status_code: int, error_code: str, message: str) -> None:
        super().__init__(
            f"Timeweb API HTTP {status_code} "
            f"error_code={error_code or 'unknown'} "
        )
        self.status_code = status_code
        self.error_code = error_code


@dataclass(frozen=True, slots=True)
class DesiredDatabase:
    cluster_name: str
    instance_name: str
    admin_login: str
    postgres_version: str
    location: str
    availability_zone: str
    max_price_rub: Decimal
    min_cpu: int
    min_ram_mb: int
    min_disk_mb: int


@dataclass(frozen=True, slots=True)
class DatabaseEndpoint:
    host: str
    port: int


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
        api_version: str = "v1",
        payload: dict[str, Any] | None = None,
        timeout: int = 30,
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
            return request_json(request, timeout=timeout)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode(errors="replace")
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = {}
            value = parsed.get("message", "")
            message = (
                "; ".join(str(item) for item in value)
                if isinstance(value, list)
                else str(value or "")
            )
            raise TimewebApiError(
                exc.code,
                str(parsed.get("error_code") or ""),
                message,
            ) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            if method in {"POST", "PUT", "PATCH", "DELETE"}:
                raise AmbiguousProviderError(
                    f"Ambiguous Timeweb {method} {path}: {type(exc).__name__}"
                ) from exc
            raise InfraError(
                f"Timeweb {method} {path} failed: {type(exc).__name__}"
            ) from exc

    def get_servers(self) -> list[dict[str, Any]]:
        return list(self.request("GET", "/servers").get("servers") or [])

    def get_server(self, server_id: int) -> dict[str, Any]:
        return dict(
            self.request("GET", f"/servers/{server_id}").get("server") or {}
        )

    def get_vpcs(self) -> list[dict[str, Any]]:
        return list(
            self.request("GET", "/vpcs", api_version="v2").get("vpcs") or []
        )

    def get_vpc_services(self, vpc_id: str) -> list[dict[str, Any]]:
        return list(
            self.request(
                "GET",
                f"/vpcs/{vpc_id}/services",
                api_version="v2",
            ).get("services")
            or []
        )

    def get_database_types(self) -> list[dict[str, Any]]:
        return list(self.request("GET", "/database-types").get("types") or [])

    def get_database_presets(self) -> list[dict[str, Any]]:
        return list(
            self.request(
                "GET",
                "/presets/dbs",
                api_version="v2",
            ).get("databases_presets")
            or []
        )

    def get_database_clusters(self) -> list[dict[str, Any]]:
        return list(self.request("GET", "/databases").get("dbs") or [])

    def get_database_cluster(self, cluster_id: int) -> dict[str, Any]:
        return dict(
            self.request("GET", f"/databases/{cluster_id}").get("db") or {}
        )

    def create_ssh_key(self, public_key: str, name: str) -> int:
        response = self.request(
            "POST",
            "/ssh-keys",
            payload={"body": public_key, "is_default": False, "name": name},
        )
        key = dict(response.get("ssh_key") or {})
        if "id" not in key:
            raise InfraError("Timeweb did not return the created SSH key id")
        return int(float(key["id"]))

    def attach_ssh_key(self, server_id: int, ssh_key_id: int) -> None:
        self.request(
            "POST",
            f"/servers/{server_id}/ssh-keys",
            payload={"ssh_key_ids": [ssh_key_id]},
        )

    def detach_ssh_key(self, server_id: int, ssh_key_id: int) -> None:
        self.request("DELETE", f"/servers/{server_id}/ssh-keys/{ssh_key_id}")

    def delete_ssh_key(self, ssh_key_id: int) -> None:
        self.request("DELETE", f"/ssh-keys/{ssh_key_id}")


def decimal_value(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise InfraError(f"Invalid numeric provider value: {value!r}") from exc


def integer_value(value: Any) -> int:
    return int(decimal_value(value))


def add_summary(line: str) -> None:
    print(line)


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


def find_vpc(
    vpcs: list[dict[str, Any]],
    *,
    name: str,
    location: str,
    availability_zone: str,
) -> dict[str, Any]:
    matches = [vpc for vpc in vpcs if vpc.get("name") == name]
    if len(matches) != 1:
        raise InfraError(f"Expected exactly one VPC named {name!r}; found {len(matches)}")
    vpc = matches[0]
    if str(vpc.get("location") or "") != location:
        raise InfraError("Managed VPC exists in the wrong location")
    if str(vpc.get("availability_zone") or "") != availability_zone:
        raise InfraError("Managed VPC exists in the wrong availability zone")
    return vpc


def service_matches(
    service: dict[str, Any],
    *,
    resource_id: int,
    resource_name: str,
) -> bool:
    try:
        service_id = integer_value(service.get("id") or 0)
    except InfraError:
        return False
    return (
        service_id == resource_id
        and str(service.get("name") or "") == resource_name
    )


def find_vpc_service(
    services: list[dict[str, Any]],
    *,
    resource_id: int,
    resource_name: str,
) -> dict[str, Any] | None:
    matches = [
        service
        for service in services
        if service_matches(
            service,
            resource_id=resource_id,
            resource_name=resource_name,
        )
    ]
    if len(matches) > 1:
        raise InfraError(
            f"Multiple VPC services match {resource_name!r} id {resource_id}"
        )
    return matches[0] if matches else None


def server_is_attached(
    services: list[dict[str, Any]],
    *,
    server_id: int,
    server_name: str,
) -> bool:
    return (
        find_vpc_service(
            services,
            resource_id=server_id,
            resource_name=server_name,
        )
        is not None
    )


def private_server_cidr(
    vpc: dict[str, Any],
    service: dict[str, Any],
) -> str:
    raw_subnet = str(vpc.get("subnet_v4") or "").strip()
    raw_local_ip = str(service.get("local_ip") or "").strip()
    if not raw_subnet or not raw_local_ip:
        raise InfraError("VPC service inventory does not expose server private IPv4")

    try:
        subnet = ipaddress.ip_network(raw_subnet, strict=False)
        address = ipaddress.ip_address(raw_local_ip)
    except ValueError as exc:
        raise InfraError("Invalid private network address returned by Timeweb") from exc

    if subnet.version != 4 or address.version != 4 or address not in subnet:
        raise InfraError("Server private IPv4 is outside the managed VPC subnet")
    if address in {subnet.network_address, subnet.broadcast_address}:
        raise InfraError("Server private IPv4 is not a usable host address")

    return f"{address}/{subnet.prefixlen}"


def select_postgres_type(
    types: list[dict[str, Any]],
    *,
    version: str,
) -> str:
    matches = [
        item
        for item in types
        if str(item.get("name") or "").strip().lower() in {"postgresql", "postgres"}
        and str(item.get("version") or "").strip() == version
        and not bool(item.get("is_deprecated"))
        and str(item.get("type") or "").strip()
    ]
    if len(matches) != 1:
        raise InfraError(
            f"Expected exactly one supported PostgreSQL {version} type; "
            f"found {len(matches)}"
        )
    return str(matches[0]["type"])


def database_preset_is_compatible(preset: dict[str, Any], desired: DesiredDatabase) -> bool:
    if str(preset.get("type") or "").strip().lower() != "postgres":
        return False
    if str(preset.get("location") or "").strip() != desired.location:
        return False
    price = decimal_value(preset.get("price") or 0)
    if price <= 0 or price > desired.max_price_rub:
        return False
    minimums = {
        "cpu": desired.min_cpu,
        "ram": desired.min_ram_mb,
        "disk": desired.min_disk_mb,
    }
    return all(integer_value(preset.get(key) or 0) >= value for key, value in minimums.items())


def select_database_preset(
    presets: list[dict[str, Any]],
    desired: DesiredDatabase,
) -> dict[str, Any]:
    compatible = [preset for preset in presets if database_preset_is_compatible(preset, desired)]

    if not compatible:
        raise InfraError(
            "No PostgreSQL preset satisfies location, resource, and budget limits"
        )

    return min(
        compatible,
        key=lambda item: (
            decimal_value(item.get("price") or 0),
            integer_value(item.get("ram") or 0),
            integer_value(item.get("disk") or 0),
            integer_value(item.get("cpu") or 0),
            integer_value(item.get("id") or 0),
        ),
    )


def find_database_cluster(
    clusters: list[dict[str, Any]],
    *,
    cluster_name: str,
) -> dict[str, Any] | None:
    matches = [db for db in clusters if db.get("name") == cluster_name]
    if len(matches) > 1:
        raise InfraError(
            f"Multiple database clusters share managed name {cluster_name!r}"
        )
    return matches[0] if matches else None


def public_ipv4(server: dict[str, Any]) -> str:
    values = [
        str(address)
        for address in network_addresses(server, public_only=True)
        if address.version == 4 and not address.is_private
    ]
    if len(values) != 1:
        raise InfraError(
            f"Expected exactly one public IPv4 on managed VDS; found {len(values)}"
        )
    return values[0]


def private_database_endpoint(cluster: dict[str, Any]) -> DatabaseEndpoint | None:
    candidates = [
        str(address)
        for address in network_addresses(cluster)
        if address.version == 4 and address.is_private
    ]

    if not candidates:
        return None
    if len(set(candidates)) != 1:
        raise InfraError("Database cluster exposes multiple private IPv4 addresses")
    return DatabaseEndpoint(
        host=candidates[0],
        port=integer_value(cluster.get("port") or 5432),
    )


def validate_existing_cluster(
    cluster: dict[str, Any],
    *,
    desired: DesiredDatabase,
    db_type: str,
) -> None:
    if str(cluster.get("type") or "") != db_type:
        raise InfraError("Managed database exists with an unexpected engine/version")
    if str(cluster.get("location") or "") != desired.location:
        raise InfraError("Managed database exists in the wrong location")
    if str(cluster.get("availability_zone") or "") != desired.availability_zone:
        raise InfraError("Managed database exists in the wrong availability zone")
    if str(cluster.get("description") or "") != DB_OWNERSHIP_MARKER:
        raise InfraError("Same-name database is not owned by this reconciler")
    if bool(cluster.get("is_enabled_public_network")):
        raise InfraError("Managed auth database unexpectedly has public IPv4 enabled")
    if bool(cluster.get("is_enabled_public_ipv6")):
        raise InfraError("Managed auth database unexpectedly has public IPv6 enabled")


def remote_operation_context(stage: str, migration_step: int | None) -> str:
    if stage not in REMOTE_STAGES:
        raise InfraError("Invalid remote diagnostic stage")
    if migration_step is not None and (
        type(migration_step) is not int or not 1 <= migration_step <= 9999
    ):
        raise InfraError("Invalid remote migration step")
    context = f"stage={stage}"
    if migration_step is not None:
        context += f", migration_step={migration_step}"
    return context


def psql_failure_fields(stderr: bytes) -> str:
    """Allow only a bounded SQLSTATE-only psql line; never return provider text."""
    unknown = "sqlstate=unknown, psql_line=unknown"
    if not isinstance(stderr, bytes) or len(stderr) > MAX_DIAGNOSTIC_BYTES:
        return unknown
    found = None
    for line in stderr.splitlines():
        if len(line) > 256:
            continue
        match = PSQL_DIAGNOSTIC.fullmatch(line)
        if match is not None:
            if found is not None:
                return unknown
            found = match
    if found is None:
        return unknown
    number = found.group(1).decode("ascii") if found.group(1) is not None else "unknown"
    return f"sqlstate={found.group(2).decode('ascii')}, psql_line={number}"


class EphemeralSsh:
    def __init__(
        self,
        *,
        client: TimewebClient,
        server_id: int,
        server_ip: str,
    ) -> None:
        self.client = client
        self.server_id = server_id
        self.server_ip = server_ip
        self._tmp: tempfile.TemporaryDirectory[str] | None = None
        self._key_path: pathlib.Path | None = None
        self._known_hosts: pathlib.Path | None = None
        self._ssh_key_id: int | None = None
        self._expected_host_fingerprint: str | None = None

    def __enter__(self) -> EphemeralSsh:
        try:
            raw_host_entry = os.environ.get("TIMEWEB_SSH_KNOWN_HOSTS", "")
            host_entry = trusted_host_entry(raw_host_entry, self.server_ip)
            self._expected_host_fingerprint = trusted_host_fingerprint(
                raw_host_entry,
                self.server_ip,
            )
        except ValueError as exc:
            raise InfraError("Verified Timeweb SSH host key is missing or invalid") from exc
        self._tmp = tempfile.TemporaryDirectory(prefix="omnicio-auth-ssh-")
        root = pathlib.Path(self._tmp.name)
        self._key_path = root / "id_ed25519"
        self._known_hosts = root / "known_hosts"

        try:
            self._known_hosts.write_text(host_entry, encoding="utf-8")
            subprocess.run(
                [
                    ssh_keygen_executable(), "-q", "-t", "ed25519", "-N", "",
                    "-f", str(self._key_path),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            public_key = self._key_path.with_suffix(".pub").read_text().strip()
            key_name = f"omnicio-auth-{os.environ.get('GITHUB_RUN_ID', 'manual')}"
            self._ssh_key_id = self.client.create_ssh_key(public_key, key_name)
            self.client.attach_ssh_key(self.server_id, self._ssh_key_id)

            last_error = "SSH not attempted"
            for attempt in range(SSH_READY_ATTEMPTS):
                ready, last_error = self._probe()
                if ready:
                    return self
                if attempt + 1 < SSH_READY_ATTEMPTS:
                    time.sleep(SSH_READY_DELAY_SECONDS)
            raise InfraError(
                "Ephemeral SSH key did not become usable within the bounded "
                f"provider propagation window; last SSH error: {last_error[:300]}"
            )
        except Exception:
            self._cleanup()
            raise

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self._cleanup()

    def _cleanup(self) -> None:
        key_id = self._ssh_key_id
        self._ssh_key_id = None
        if key_id is not None:
            with suppress(InfraError, TimewebApiError, AmbiguousProviderError):
                self.client.detach_ssh_key(self.server_id, key_id)
            with suppress(InfraError, TimewebApiError, AmbiguousProviderError):
                self.client.delete_ssh_key(key_id)
        if self._tmp is not None:
            self._tmp.cleanup()
            self._tmp = None
        self._expected_host_fingerprint = None

    def _probe(self) -> tuple[bool, str]:
        if self._key_path is None or self._known_hosts is None:
            raise InfraError("SSH session is not initialized")

        completed = subprocess.run(
            ssh_base_args(self._key_path, self._known_hosts) + [
                f"root@{self.server_ip}", "--", "true",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        if completed.returncode == 0:
            return True, ""
        if self._expected_host_fingerprint is None:
            raise InfraError("Expected SSH host fingerprint is not initialized")
        mismatch = ssh_host_key_mismatch_message(
            completed.stderr,
            expected_fingerprint=self._expected_host_fingerprint,
        )
        if mismatch is not None:
            raise InfraError(mismatch)
        detail = " ".join(
            (completed.stderr or f"ssh exit code {completed.returncode}").split()
        )
        private_path = str(self._key_path)
        if private_path:
            detail = detail.replace(private_path, "<ephemeral-key>")
        return False, detail or f"ssh exit code {completed.returncode}"

    def run(
        self, command: str, *, input_text: str | None = None,
        stage: str = "remote_command", migration_step: int | None = None,
        timeout: int = 90,
    ) -> str:
        context = remote_operation_context(stage, migration_step)
        if self._key_path is None or self._known_hosts is None:
            raise InfraError("SSH session is not initialized")

        payload = None if input_text is None else input_text.encode("utf-8")
        try:
            completed = subprocess.run(
                ssh_base_args(self._key_path, self._known_hosts) + [
                    f"root@{self.server_ip}", "--", command,
                ],
                input=payload,
                check=False,
                capture_output=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            raise InfraError(f"Remote command timed out ({context})") from None
        if completed.returncode != 0:
            detail = f"{context}, exit_code={completed.returncode}"
            if stage == STAGE_SCHEMA_MIGRATION:
                detail += ", " + psql_failure_fields(completed.stderr)
                reason = UPGRADE_DIAGNOSTIC.search(completed.stderr[:MAX_DIAGNOSTIC_BYTES])
                if reason is not None:
                    detail += ", reason=" + reason[1].decode("ascii")
            raise InfraError(f"Remote command failed ({detail})")
        try:
            return completed.stdout.decode("utf-8")
        except UnicodeDecodeError:
            raise InfraError("Remote command returned invalid UTF-8") from None


REMOTE_PRIVATE_NETWORK_CONFIG = r"""set -euo pipefail

CIDR="$1"
PRIVATE_IP="${CIDR%/*}"

PUBLIC_IF="$(
    ip route get 1.1.1.1 2>/dev/null |
    awk '{for (i=1; i<=NF; i++) if ($i == "dev") {print $(i+1); exit}}'
)"
if [ -z "$PUBLIC_IF" ]; then
    echo "Unable to identify public network interface" >&2
    exit 51
fi

EXISTING_IF="$(
    ip -4 -o addr show scope global |
    awk -v target="$PRIVATE_IP" '
        {
            split($4, parts, "/")
            if (parts[1] == target) print $2
        }
    '
)"

if [ -n "$EXISTING_IF" ]; then
    if [ "$(printf '%s\n' "$EXISTING_IF" | sed '/^$/d' | wc -l)" -ne 1 ]; then
        echo "Private IPv4 is assigned to multiple interfaces" >&2
        exit 52
    fi
    PRIVATE_IF="$EXISTING_IF"
else
    CANDIDATES=""
    for sys_path in /sys/class/net/*; do
        iface="${sys_path##*/}"
        [ "$iface" = "lo" ] && continue
        [ "$iface" = "$PUBLIC_IF" ] && continue
        [ -e "/sys/devices/virtual/net/$iface" ] && continue
        [ "$(cat "$sys_path/type" 2>/dev/null || true)" = "1" ] || continue

        # A newly attached Timeweb BGP NIC may legitimately report operstate
        # "down" until an address is assigned. Excluding down interfaces here
        # makes the exact interface we need invisible. Provider ownership,
        # non-virtual Ethernet type, and exclusion of the public route interface
        # are the safety boundaries; the link is brought up immediately below.
        CANDIDATES="$CANDIDATES $iface"
    done

    set -- $CANDIDATES
    if [ "$#" -ne 1 ]; then
        echo "Expected exactly one unconfigured physical private interface" >&2
        exit 53
    fi
    PRIVATE_IF="$1"

    ip link set dev "$PRIVATE_IF" up
    ip addr add "$CIDR" dev "$PRIVATE_IF"
fi

if [ "$PRIVATE_IF" = "$PUBLIC_IF" ]; then
    echo "Refusing to configure the public interface as private" >&2
    exit 54
fi

install -d -m 0755 /etc/netplan
cat > /etc/netplan/99-omnicio-private.yaml <<EOF
network:
  version: 2
  renderer: networkd
  ethernets:
    $PRIVATE_IF:
      dhcp4: false
      dhcp6: false
      optional: true
      addresses:
        - "$CIDR"
EOF
chmod 600 /etc/netplan/99-omnicio-private.yaml
netplan generate

ip -4 addr show dev "$PRIVATE_IF" | grep -Fq "inet $CIDR"
"""


def ensure_server_private_network(
    ssh: EphemeralSsh,
    *,
    private_cidr: str,
) -> None:
    ssh.run(
        f"bash -s -- {shlex.quote(private_cidr)}",
        input_text=REMOTE_PRIVATE_NETWORK_CONFIG,
        stage="private_network",
    )


def is_valid_timeweb_db_password(value: str) -> bool:
    return (
        TIMEWEB_DB_PASSWORD_MIN <= len(value) <= TIMEWEB_DB_PASSWORD_MAX
        and all(char in TIMEWEB_DB_PASSWORD_SAFE for char in value)
    )


def parse_secret_bundle(raw: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in raw.splitlines():
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise InfraError("Malformed server-side auth secret file")
        key, value = line.split("=", 1)
        values[key] = value

    required = {
        "OMNICIO_DB_ADMIN_PASSWORD",
        "CLIENT_IP_KEY",
        "BROKER_TOKEN_CRYPTO_KEY",
        "VKID_FLOW_CRYPTO_KEY",
    }
    if required - values.keys():
        raise InfraError("Server-side auth secret file is incomplete")
    return values


REMOTE_SECRET_BOOTSTRAP = r"""
from __future__ import annotations

import base64
import os
import pathlib
import secrets

path = pathlib.Path("/etc/omnicio/auth-secrets.env")
path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)

values = {}
if path.exists():
    for line in path.read_text().splitlines():
        if not line:
            continue
        if "=" not in line:
            raise SystemExit("malformed auth secret file")
        key, value = line.split("=", 1)
        values[key] = value
else:
    values = {
        "OMNICIO_DB_ADMIN_PASSWORD": secrets.token_urlsafe(18),
    }

changed = not path.exists()
generated_keys = (
    "CLIENT_IP_KEY",
    "BROKER_TOKEN_CRYPTO_KEY",
    "VKID_FLOW_CRYPTO_KEY",
)
for key in generated_keys:
    if key not in values:
        values[key] = base64.urlsafe_b64encode(os.urandom(32)).decode()
        changed = True

if changed:
    content = "".join(f"{key}={value}\n" for key, value in values.items())
    temp = path.with_suffix(".tmp")
    temp.write_text(content)
    os.chmod(temp, 0o600)
    temp.replace(path)

os.chmod(path, 0o600)
print(path.read_text(), end="")
"""


def load_or_create_server_secrets(ssh: EphemeralSsh) -> dict[str, str]:
    raw = ssh.run("python3 -", input_text=REMOTE_SECRET_BOOTSTRAP, stage="secret_bootstrap")
    values = parse_secret_bundle(raw)
    if not is_valid_timeweb_db_password(values["OMNICIO_DB_ADMIN_PASSWORD"]):
        raise InfraError("Stored database password is invalid; automatic rotation is disabled")
    return values


def write_runtime_env(
    ssh: EphemeralSsh,
    *,
    endpoint: DatabaseEndpoint,
    desired: DesiredDatabase,
    secrets: dict[str, str],
) -> None:
    password = urllib.parse.quote(secrets["OMNICIO_DB_ADMIN_PASSWORD"], safe="")
    database_url = (
        f"postgresql://{desired.admin_login}:{password}@"
        f"{endpoint.host}:{endpoint.port}/{desired.instance_name}?sslmode=prefer"
    )
    content = "\n".join(
        [
            f"DATABASE_URL={database_url}",
            f"CLIENT_IP_KEY={secrets['CLIENT_IP_KEY']}",
            f"BROKER_TOKEN_CRYPTO_KEY={secrets['BROKER_TOKEN_CRYPTO_KEY']}",
            f"VKID_FLOW_CRYPTO_KEY={secrets['VKID_FLOW_CRYPTO_KEY']}",
            "REGISTRATION_ENABLED=false",
            "",
        ]
    )
    ssh.run(
        "umask 077; mkdir -p /etc/omnicio; "
        f"cat > {shlex.quote(REMOTE_RUNTIME_PATH)}; "
        f"chmod 600 {shlex.quote(REMOTE_RUNTIME_PATH)}",
        input_text=content,
        stage="runtime_env",
    )


def run_schema_migration(
    ssh: EphemeralSsh,
    *,
    migration_sql: str,
    migration_step: int,
    endpoint: DatabaseEndpoint,
    desired: DesiredDatabase,
) -> None:
    ssh.run(
        "command -v psql >/dev/null 2>&1 || "
        "(apt-get update -qq && "
        "DEBIAN_FRONTEND=noninteractive apt-get install -y -qq postgresql-client)",
        stage="psql_client", migration_step=migration_step,
    )
    host = shlex.quote(endpoint.host)
    port = shlex.quote(str(endpoint.port))
    user = shlex.quote(desired.admin_login)
    database = shlex.quote(desired.instance_name)
    secret_file = shlex.quote(REMOTE_SECRET_PATH)
    command = (
        f"set -a; . {secret_file}; set +a; "
        'export PGPASSWORD="$OMNICIO_DB_ADMIN_PASSWORD"; '
        'export PGCONNECT_TIMEOUT=10; '
        'export PGOPTIONS="-c statement_timeout=30000 -c lock_timeout=5000"; '
        f"psql -h {host} -p {port} -U {user} -d {database} "
        "-X -f - -v ON_ERROR_STOP=1 -v VERBOSITY=sqlstate -v SHOW_CONTEXT=never -q"
    )
    ssh.run(
        command, input_text=migration_sql,
        stage=STAGE_SCHEMA_MIGRATION, migration_step=migration_step,
    )


def _blocked_inspection_check(value: Any) -> bool:
    return (isinstance(value, dict) and set(value) == {"status", "code"}
            and value.get("status") == "blocked" and isinstance(value.get("code"), str)
            and re.fullmatch(r"[a-z_]{1,64}", value["code"]) is not None)


def _valid_inspected_configuration(value: Any) -> bool:
    if _blocked_inspection_check(value):
        return True
    return (isinstance(value, dict) and set(value) == {
        "status", "smtp_delivery_verified", "market_token_configured",
        "market_distribution_approved",
    } and value.get("status") == "configuration_ready"
            and value.get("smtp_delivery_verified") is False
            and type(value.get("market_token_configured")) is bool
            and type(value.get("market_distribution_approved")) is bool)


def _valid_inspected_probe(value: Any, operation: str, message_id: str) -> bool:
    if not isinstance(value, dict) or set(value) != {"status", "code", "message_id"}:
        return False
    if operation != "email_probe":
        return value == {"status": "not_requested", "code": "not_requested", "message_id": ""}
    if value.get("message_id") == "":
        return _blocked_inspection_check({key: value[key] for key in ("status", "code")})
    if value.get("message_id") != message_id:
        return False
    return (value.get("status"), value.get("code")) in (
        ("accepted", "email_provider_accepted"), ("queued", "email_temporary_rejection"),
        ("failed", "email_provider_rejected"), ("failed", "email_recipient_rejected"),
        ("uncertain", "email_result_unknown"),
    )


def _valid_inspection_result(result: dict[str, Any], operation: str, message_id: str) -> bool:
    if (result.get("operation") != operation
            or result.get("schema") not in ("source_ready", "target_ready")):
        return False
    recovery = result.get("recovery")
    if (not isinstance(recovery, dict)
            or (recovery != {"status": "ready", "code": "recovery_verified"}
                and not _blocked_inspection_check(recovery))):
        return False
    configuration = result.get("configuration")
    probe = result.get("email_probe")
    if (not isinstance(configuration, dict) or not isinstance(probe, dict)
            or not _valid_inspected_configuration(configuration)
            or not _valid_inspected_probe(probe, operation, message_id)):
        return False
    ready = (recovery["status"] == "ready" and configuration["status"] == "configuration_ready"
             and probe["status"] in ("not_requested", "accepted"))
    return result.get("status") == ("preflight_ready" if ready else "preflight_blocked")


def _read_upgrade_result(
    raw: str, *, cluster_id: int, release_sha: str, operation: str, message_id: str,
) -> dict[str, Any]:
    if len(raw) > 16384:
        raise InfraError(UNCONFIRMED_UPGRADE)
    try:
        result = json.loads(raw)
    except ValueError:
        raise InfraError(UNCONFIRMED_UPGRADE) from None
    keys = {"status", "cluster_id", "release_sha", "new_database_copies"}
    if operation != "apply":
        keys.update({"operation", "schema", "recovery", "configuration", "email_probe"})
    if (not isinstance(result, dict) or set(result) != keys
            or type(result.get("cluster_id")) is not int
            or result.get("cluster_id") != cluster_id or result.get("release_sha") != release_sha
            or type(result.get("new_database_copies")) is not int
            or result["new_database_copies"] != 0):
        raise InfraError(UNCONFIRMED_UPGRADE)
    if operation == "apply":
        valid = result.get("status") in ("applied", "already_applied")
    else:
        valid = _valid_inspection_result(result, operation, message_id)
    if not valid:
        raise InfraError(UNCONFIRMED_UPGRADE)
    return result


def run_inplace_upgrade(
    ssh: EphemeralSsh, *, migration_sqls: list[str], release_sha: str,
    endpoint: DatabaseEndpoint, desired: DesiredDatabase, operation: str = "preflight",
) -> dict[str, Any]:
    cluster_id = load_policy().cluster_id
    program = render_remote_upgrade(
        migration_sqls, release_sha=release_sha, operation=operation,
        database={"cluster_id": cluster_id, "host": endpoint.host, "port": endpoint.port,
                  "database": desired.instance_name, "user": desired.admin_login},
    )
    message_id = ""
    if operation == "email_probe":
        from timeweb_auth_app import DOMAIN, _smtp_probe_parameters

        _, tag = _smtp_probe_parameters(release_sha)
        message_id = f"<{tag}@{DOMAIN}>"
    command = "/opt/omnicio/current/.venv/bin/python -I -"
    timeout = 90
    if operation != "apply":
        # Prevent imported installed modules from creating bytecode caches. The
        # server deadline survives a disconnected client and never retries mail.
        command = (f"timeout --kill-after=5s {INSPECTION_TIMEOUT_SECONDS}s "
                   "/opt/omnicio/current/.venv/bin/python -I -B -")
        timeout = INSPECTION_TIMEOUT_SECONDS + 20
    raw = ssh.run(command, input_text=program, stage=STAGE_SCHEMA_MIGRATION,
                  migration_step=30, timeout=timeout)
    return _read_upgrade_result(raw, cluster_id=cluster_id, release_sha=release_sha,
                                operation=operation, message_id=message_id)


def wait_for_database_endpoint(
    client: TimewebClient,
    cluster_id: int,
    *,
    attempts: int = 30,
    sleep_seconds: int = 10,
) -> tuple[dict[str, Any], DatabaseEndpoint]:
    for _ in range(attempts):
        cluster = client.get_database_cluster(cluster_id)
        endpoint = private_database_endpoint(cluster)
        status = str(cluster.get("status") or "").lower()
        if endpoint is not None and status not in {
            "creating",
            "installing",
            "pending",
            "starting",
        }:
            return cluster, endpoint
        time.sleep(sleep_seconds)
    raise InfraError(
        "Database cluster did not expose a ready private endpoint in time"
    )


def validate_migration_request(
    migration_sqls: list[str], *, backup_only: bool, release_sha: str | None,
    operation: str = "preflight",
) -> bool:
    validate_operation(operation, release_sha=release_sha, backup_only=backup_only)
    if backup_only and release_sha is not None:
        raise InfraError("Scheduled verification cannot authorize a pre-release copy")
    single_database = load_policy().mode == SINGLE_DATABASE_MODE
    if not single_database and not backup_only and operation != "apply":
        raise UpgradeBlocked("inspection_requires_single_existing_database")
    if single_database and not backup_only:
        if not isinstance(release_sha, str) or re.fullmatch(r"[0-9a-f]{40}", release_sha) is None:
            raise InfraError("In-place upgrade requires an exact accepted release")
        migration_bodies(load_plan(), migration_sqls)
    return single_database


def apply_database_release(
    ssh: EphemeralSsh, *, single_database: bool, migration_sqls: list[str], release_sha: str | None,
    endpoint: DatabaseEndpoint, desired: DesiredDatabase, server_private_cidr: str,
) -> None:
    if single_database:
        run_inplace_upgrade(ssh, migration_sqls=migration_sqls, release_sha=release_sha or "",
                            endpoint=endpoint, desired=desired, operation="apply")
        return
    ensure_server_private_network(ssh, private_cidr=server_private_cidr)
    secret_bundle = load_or_create_server_secrets(ssh)
    write_runtime_env(ssh, endpoint=endpoint, desired=desired, secrets=secret_bundle)
    for migration_step, migration_sql in enumerate(migration_sqls, start=1):
        run_schema_migration(ssh, migration_sql=migration_sql, migration_step=migration_step,
                             endpoint=endpoint, desired=desired)


def reconcile_recovery_policy(
    client: TimewebClient, ssh: EphemeralSsh, cluster: dict[str, Any], *,
    cluster_id: int, single_database: bool, backup_only: bool, release_sha: str | None,
) -> None:
    """Keep release checks read-only; retain existing policy maintenance authority."""
    if single_database and not backup_only:
        policy = load_policy()
        validate_budget(cluster, policy)
        if get_schedule(client, cluster_id)["is_enabled"] is not False:
            raise RecoveryBlocked("The single-database copy schedule is not disabled")
        return
    ensure_recovery_point(client, ssh, cluster, release_sha=release_sha)
    if not single_database:
        inspect_restore_capacity(client, ssh, cluster_id)


def inspect_database_release(
    ssh: EphemeralSsh, *, migration_sqls: list[str], release_sha: str,
    endpoint: DatabaseEndpoint, desired: DesiredDatabase, operation: str,
) -> int:
    report = run_inplace_upgrade(
        ssh, migration_sqls=migration_sqls, release_sha=release_sha,
        endpoint=endpoint, desired=desired, operation=operation,
    )
    # Preserve both safe component outcomes before reporting a blocked job.
    # SMTP provider acceptance remains distinct from receipt in the mailbox.
    add_summary(json.dumps(report, sort_keys=True, ensure_ascii=True))
    set_output("status", report["status"])
    set_output("cluster_id", str(report["cluster_id"]))
    if report["status"] != "preflight_ready":
        print("::error::Live release preflight is blocked; inspect the component codes.",
              file=sys.stderr)
        return 1
    return 0


def reconcile(
    client: TimewebClient,
    *,
    desired: DesiredDatabase,
    server_name: str,
    server_comment: str,
    vpc_name: str,
    migration_sqls: list[str],
    backup_only: bool = False,
    release_sha: str | None = None,
    operation: str = "preflight",
) -> int:
    single_database = validate_migration_request(
        migration_sqls, backup_only=backup_only, release_sha=release_sha, operation=operation,
    )
    add_summary("## OmniCIO auth PostgreSQL")
    add_summary(
        f"- Desired: PostgreSQL {desired.postgres_version}, "
        f"{desired.location}/{desired.availability_zone}, private-only."
    )

    server_summary = find_managed_server(
        client.get_servers(),
        name=server_name,
        comment=server_comment,
    )
    server_id = integer_value(server_summary["id"])
    server = client.get_server(server_id)

    vpc = find_vpc(
        client.get_vpcs(),
        name=vpc_name,
        location=desired.location,
        availability_zone=desired.availability_zone,
    )
    vpc_id = str(vpc["id"])
    services = client.get_vpc_services(vpc_id)

    server_vpc_service = find_vpc_service(
        services,
        resource_id=server_id,
        resource_name=server_name,
    )
    if server_vpc_service is None:
        raise InfraError("Production VDS is missing from the approved private VPC")

    server_private_cidr = private_server_cidr(vpc, server_vpc_service)

    database_types = client.get_database_types()
    database_presets = client.get_database_presets()
    database_clusters = client.get_database_clusters()

    db_type = select_postgres_type(
        database_types,
        version=desired.postgres_version,
    )
    preset = select_database_preset(database_presets, desired)
    preset_id = integer_value(preset["id"])
    preset_price = decimal_value(preset.get("price") or 0)
    add_summary(
        f"- Selected DB preset {preset_id}: "
        f"{integer_value(preset.get('cpu') or 0)} CPU, "
        f"{integer_value(preset.get('ram') or 0)} MB RAM, "
        f"{integer_value(preset.get('disk') or 0)} MB disk, "
        f"{preset_price} RUB/month API price."
    )

    existing = find_database_cluster(
        database_clusters,
        cluster_name=desired.cluster_name,
    )
    if existing is None or integer_value(existing["id"]) != load_policy().cluster_id:
        raise InfraError(
            "Expected production database is missing or replaced; automatic creation is disabled"
        )

    add_summary("- Provider recovery inspection (read-only; not release readiness):")
    add_summary(json.dumps(inspect_provider_recovery(client), sort_keys=True, ensure_ascii=True))

    with EphemeralSsh(
        client=client,
        server_id=server_id,
        server_ip=public_ipv4(server),
    ) as ssh:
        cluster_id = integer_value(existing["id"])
        add_summary(f"- Reusing managed PostgreSQL cluster id {cluster_id}.")

        cluster, endpoint = wait_for_database_endpoint(client, cluster_id)
        validate_existing_cluster(cluster, desired=desired, db_type=db_type)

        current_services = client.get_vpc_services(vpc_id)
        if not any(
            service_matches(
                item,
                resource_id=cluster_id,
                resource_name=desired.cluster_name,
            )
            for item in current_services
        ):
            raise InfraError(
                "Managed PostgreSQL cluster is not attached to approved VPC"
            )

        reconcile_recovery_policy(
            client, ssh, cluster, cluster_id=cluster_id, single_database=single_database,
            backup_only=backup_only, release_sha=release_sha,
        )
        if backup_only:
            status = "single_database_policy_ready" if single_database else "recovery_point_ready"
            set_output("status", status)
            add_summary(f"- Scheduled verification completed: {status}; "
                        "schema and runtime unchanged.")
            return 0
        if operation != "apply":
            return inspect_database_release(
                ssh, migration_sqls=migration_sqls, release_sha=release_sha or "",
                endpoint=endpoint, desired=desired, operation=operation,
            )
        apply_database_release(
            ssh, single_database=single_database, migration_sqls=migration_sqls,
            release_sha=release_sha, endpoint=endpoint, desired=desired,
            server_private_cidr=server_private_cidr,
        )

    add_summary(
        "- Result: database_ready. PostgreSQL is private-only, runtime "
        "credentials are root-only on the managed VDS, and schema migration "
        "completed."
    )
    set_output("status", "database_ready")
    set_output("cluster_id", str(cluster_id))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-name", required=True)
    parser.add_argument("--server-comment", required=True)
    parser.add_argument("--vpc-name", required=True)
    parser.add_argument("--cluster-name", required=True)
    parser.add_argument("--instance-name", required=True)
    parser.add_argument("--admin-login", required=True)
    parser.add_argument("--postgres-version", required=True)
    parser.add_argument("--location", required=True)
    parser.add_argument("--availability-zone", required=True)
    parser.add_argument("--max-price-rub", required=True)
    parser.add_argument("--min-cpu", type=int, required=True)
    parser.add_argument("--min-ram-mb", type=int, required=True)
    parser.add_argument("--min-disk-mb", type=int, required=True)
    parser.add_argument("--migration", action="append", required=True)
    parser.add_argument("--backup-only", action="store_true")
    parser.add_argument("--operation", choices=OPERATIONS,
                        default=os.environ.get("OMNICIO_POSTGRES_OPERATION", "preflight"))
    return parser.parse_args()


def load_migrations(paths: list[str]) -> list[str]:
    """Read only direct SQL files from this checkout's migrations directory."""
    migration_dir = pathlib.Path(__file__).resolve().parents[2] / "migrations"
    statements: list[str] = []
    for value in paths:
        supplied = pathlib.Path(value)
        if supplied.parent != pathlib.Path("migrations") or supplied.suffix != ".sql":
            raise InfraError("Migration must be a direct repository migrations/*.sql file")
        candidate = migration_dir / supplied.name
        try:
            if candidate.is_symlink():
                raise InfraError("Migration symlinks are not allowed")
            resolved = candidate.resolve(strict=True)
            if resolved.parent != migration_dir or not resolved.is_file():
                raise InfraError("Migration is outside the approved directory")
            statements.append(resolved.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise InfraError("Migration SQL file is unavailable or invalid") from exc
    return statements


def main() -> int:
    args = parse_args()
    try:
        migration_sqls = load_migrations(args.migration)
        release_sha = None
        if not args.backup_only:
            release_sha, _ = release_context()
            require_checkout(release_sha)
        validate_operation(args.operation, release_sha=release_sha, backup_only=args.backup_only)
        client = TimewebClient(os.environ.get("TIMEWEB_CLOUD_TOKEN", ""))
        return reconcile(
            client,
            desired=DesiredDatabase(
                cluster_name=args.cluster_name,
                instance_name=args.instance_name,
                admin_login=args.admin_login,
                postgres_version=args.postgres_version,
                location=args.location,
                availability_zone=args.availability_zone,
                max_price_rub=decimal_value(args.max_price_rub),
                min_cpu=args.min_cpu,
                min_ram_mb=args.min_ram_mb,
                min_disk_mb=args.min_disk_mb,
            ),
            server_name=args.server_name,
            server_comment=args.server_comment,
            vpc_name=args.vpc_name,
            migration_sqls=migration_sqls,
            backup_only=args.backup_only,
            release_sha=release_sha,
            operation=args.operation,
        )
    except (
        InfraError, TimewebApiError, AmbiguousProviderError, RecoveryBlocked, ReleaseBlocked,
        UpgradeBlocked,
    ) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
