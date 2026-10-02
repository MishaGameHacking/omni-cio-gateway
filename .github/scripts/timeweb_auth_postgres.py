#!/usr/bin/env python3
"""Reconcile OmniCIO private PostgreSQL and bootstrap server-side secrets."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import pathlib
import shlex
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from timeweb_ssh_trust import ssh_base_args, trusted_host_entry

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
            f"message={message or 'unknown'}"
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
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode()
                return json.loads(raw) if raw else {}
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
        except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
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

    def create_database_cluster(self, payload: dict[str, Any]) -> dict[str, Any]:
        return dict(
            self.request(
                "POST",
                "/databases",
                payload=payload,
                timeout=45,
            ).get("db")
            or {}
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


def select_database_preset(
    presets: list[dict[str, Any]],
    desired: DesiredDatabase,
) -> dict[str, Any]:
    compatible: list[dict[str, Any]] = []
    for preset in presets:
        if str(preset.get("type") or "").strip().lower() != "postgres":
            continue
        if str(preset.get("location") or "").strip() != desired.location:
            continue

        price = decimal_value(preset.get("price") or 0)
        if price <= 0 or price > desired.max_price_rub:
            continue
        if integer_value(preset.get("cpu") or 0) < desired.min_cpu:
            continue
        if integer_value(preset.get("ram") or 0) < desired.min_ram_mb:
            continue
        if integer_value(preset.get("disk") or 0) < desired.min_disk_mb:
            continue
        compatible.append(preset)

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
    values: list[str] = []
    for network in server.get("networks") or []:
        network_type = str(network.get("type") or "").lower()
        if network_type in {"local", "private"}:
            continue
        for item in network.get("ips") or []:
            raw = str(item.get("ip") or "").strip()
            if not raw:
                continue
            try:
                address = ipaddress.ip_address(raw)
            except ValueError:
                continue
            if address.version == 4 and not address.is_private:
                values.append(str(address))
    if len(values) != 1:
        raise InfraError(
            f"Expected exactly one public IPv4 on managed VDS; found {len(values)}"
        )
    return values[0]


def private_database_endpoint(cluster: dict[str, Any]) -> DatabaseEndpoint | None:
    candidates: list[str] = []
    for network in cluster.get("networks") or []:
        for item in network.get("ips") or []:
            raw = str(item.get("ip") or "").strip()
            if not raw:
                continue
            try:
                address = ipaddress.ip_address(raw)
            except ValueError:
                continue
            if address.version == 4 and address.is_private:
                candidates.append(str(address))

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


def create_payload(
    *,
    desired: DesiredDatabase,
    db_type: str,
    preset: dict[str, Any],
    vpc_id: str,
    password: str,
) -> dict[str, Any]:
    return {
        "name": desired.cluster_name,
        "type": db_type,
        "admin": {
            "login": desired.admin_login,
            "password": password,
            "description": "OmniCIO application database user",
        },
        "instance": {
            "name": desired.instance_name,
            "description": "OmniCIO account and authentication data",
        },
        "preset_id": integer_value(preset["id"]),
        "network": {"id": vpc_id},
        "is_public_ipv6": False,
        "description": DB_OWNERSHIP_MARKER,
        "availability_zone": desired.availability_zone,
        "disk_autoscaling": {"is_enabled": False},
    }


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

    def __enter__(self) -> EphemeralSsh:
        try:
            host_entry = trusted_host_entry(
                os.environ.get("TIMEWEB_SSH_KNOWN_HOSTS", ""), self.server_ip,
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
                    "/usr/bin/ssh-keygen", "-q", "-t", "ed25519", "-N", "",
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

            for _ in range(18):
                try:
                    self.run("true")
                    return self
                except InfraError:
                    time.sleep(10)
            raise InfraError("Ephemeral SSH key did not become usable in time")
        except Exception:
            self._cleanup()
            raise

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self._cleanup()

    def _cleanup(self) -> None:
        key_id = self._ssh_key_id
        self._ssh_key_id = None
        if key_id is not None:
            try:
                self.client.detach_ssh_key(self.server_id, key_id)
            except (InfraError, TimewebApiError, AmbiguousProviderError):
                pass
            try:
                self.client.delete_ssh_key(key_id)
            except (InfraError, TimewebApiError, AmbiguousProviderError):
                pass
        if self._tmp is not None:
            self._tmp.cleanup()
            self._tmp = None

    def run(self, command: str, *, input_text: str | None = None) -> str:
        if self._key_path is None or self._known_hosts is None:
            raise InfraError("SSH session is not initialized")

        completed = subprocess.run(
            ssh_base_args(self._key_path, self._known_hosts) + [
                f"root@{self.server_ip}", "--", command,
            ],
            input=input_text,
            check=False,
            capture_output=True,
            text=True,
            timeout=90,
        )
        if completed.returncode != 0:
            raise InfraError(
                f"Remote command failed with exit code {completed.returncode}"
            )
        return completed.stdout


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


REMOTE_DB_PASSWORD_ROTATE = r"""
from __future__ import annotations

import os
import pathlib
import secrets

path = pathlib.Path("/etc/omnicio/auth-secrets.env")
if not path.is_file():
    raise SystemExit("auth secret file does not exist")

lines = path.read_text().splitlines()
new_password = secrets.token_urlsafe(18)
updated = []
replaced = False

for line in lines:
    if line.startswith("OMNICIO_DB_ADMIN_PASSWORD="):
        updated.append(f"OMNICIO_DB_ADMIN_PASSWORD={new_password}")
        replaced = True
    else:
        updated.append(line)

if not replaced:
    raise SystemExit("database admin password key is missing")

temp = path.with_suffix(".tmp")
temp.write_text("\n".join(updated) + "\n")
os.chmod(temp, 0o600)
temp.replace(path)
os.chmod(path, 0o600)
print(path.read_text(), end="")
"""


def load_or_create_server_secrets(
    ssh: EphemeralSsh,
    *,
    allow_db_password_rotation: bool,
) -> dict[str, str]:
    raw = ssh.run("python3 -", input_text=REMOTE_SECRET_BOOTSTRAP)
    values = parse_secret_bundle(raw)
    password = values["OMNICIO_DB_ADMIN_PASSWORD"]

    if is_valid_timeweb_db_password(password):
        return values

    if not allow_db_password_rotation:
        raise InfraError(
            "Stored database admin password violates the provider policy and "
            "cannot be rotated after a managed cluster exists"
        )

    rotated = ssh.run("python3 -", input_text=REMOTE_DB_PASSWORD_ROTATE)
    values = parse_secret_bundle(rotated)
    if not is_valid_timeweb_db_password(values["OMNICIO_DB_ADMIN_PASSWORD"]):
        raise InfraError("Generated database admin password violates provider policy")
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
    )


def run_schema_migration(
    ssh: EphemeralSsh,
    *,
    migration_sql: str,
    endpoint: DatabaseEndpoint,
    desired: DesiredDatabase,
) -> None:
    ssh.run(
        "command -v psql >/dev/null 2>&1 || "
        "(apt-get update -qq && "
        "DEBIAN_FRONTEND=noninteractive apt-get install -y -qq postgresql-client)"
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
        "-v ON_ERROR_STOP=1 -q"
    )
    ssh.run(command, input_text=migration_sql)


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


def reconcile_after_ambiguous_create(
    client: TimewebClient,
    *,
    cluster_name: str,
    attempts: int = 6,
    sleep_seconds: int = 10,
) -> dict[str, Any] | None:
    for _ in range(attempts):
        time.sleep(sleep_seconds)
        existing = find_database_cluster(
            client.get_database_clusters(),
            cluster_name=cluster_name,
        )
        if existing:
            return existing
    return None


def reconcile(
    client: TimewebClient,
    *,
    desired: DesiredDatabase,
    server_name: str,
    server_comment: str,
    vpc_name: str,
    migration_sqls: list[str],
) -> int:
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
        add_summary(
            "- Result: pending_server_network. The managed VDS is not yet "
            "attached to the approved private VPC."
        )
        add_summary("- No database was created or changed.")
        set_output("status", "pending_server_network")
        return 0

    server_private_cidr = private_server_cidr(vpc, server_vpc_service)

    try:
        database_types = client.get_database_types()
        database_presets = client.get_database_presets()
        database_clusters = client.get_database_clusters()
    except TimewebApiError as exc:
        if exc.status_code == 403:
            add_summary(
                "- Result: pending_token_permission. The Timeweb API token "
                "does not currently have DBaaS access; no database was created "
                "or changed."
            )
            set_output("status", "pending_token_permission")
            return 0
        raise

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

    with EphemeralSsh(
        client=client,
        server_id=server_id,
        server_ip=public_ipv4(server),
    ) as ssh:
        ensure_server_private_network(
            ssh,
            private_cidr=server_private_cidr,
        )
        add_summary(
            f"- Managed VDS private IPv4 configured as {server_private_cidr}."
        )

        secret_bundle = load_or_create_server_secrets(
            ssh,
            allow_db_password_rotation=existing is None,
        )

        if existing is None:
            payload = create_payload(
                desired=desired,
                db_type=db_type,
                preset=preset,
                vpc_id=vpc_id,
                password=secret_bundle["OMNICIO_DB_ADMIN_PASSWORD"],
            )
            add_summary("- Creating the approved private PostgreSQL cluster.")
            try:
                cluster = client.create_database_cluster(payload)
            except AmbiguousProviderError:
                add_summary(
                    "- Create result was ambiguous; reconciling by managed "
                    "cluster name before any retry."
                )
                cluster = reconcile_after_ambiguous_create(
                    client,
                    cluster_name=desired.cluster_name,
                )
                if cluster is None:
                    raise InfraError(
                        "Database create was ambiguous and reconciliation did "
                        "not prove the resulting state"
                    )
            if "id" not in cluster:
                raise InfraError("Timeweb returned database success without an id")
            cluster_id = integer_value(cluster["id"])
            add_summary(f"- Created PostgreSQL cluster id {cluster_id}.")
        else:
            cluster_id = integer_value(existing["id"])
            cluster = client.get_database_cluster(cluster_id)
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

        write_runtime_env(
            ssh,
            endpoint=endpoint,
            desired=desired,
            secrets=secret_bundle,
        )
        for migration_sql in migration_sqls:
            run_schema_migration(
                ssh,
                migration_sql=migration_sql,
                endpoint=endpoint,
                desired=desired,
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
        )
    except (InfraError, TimewebApiError, AmbiguousProviderError) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
