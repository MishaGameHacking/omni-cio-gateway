#!/usr/bin/env python3
"""Configure omnicio.ru HTTPS on the managed Timeweb server.

The script is designed for GitHub Actions on accepted main only. It uses an
ephemeral SSH key: the private key exists only on the runner, while the public
key is temporarily registered in Timeweb and attached to the server.
"""

from __future__ import annotations

import ipaddress
import json
import os
import pathlib
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

API_ROOT = "https://api.timeweb.cloud/api/v1"
SITE_MARKER = 'name="omni-cio-white-site"'
DOMAIN_NAME = "omnicio.ru"
SERVER_NAME = "omni-cio-white-site"
SERVER_COMMENT = "Managed by GitHub Actions: timeweb-white-site"
EXPECTED_SERVER_ID = 9235089
EXPECTED_SERVER_IPV4 = "194.87.151.244"


class DeploymentError(RuntimeError):
    pass


class TimewebApiError(RuntimeError):
    def __init__(self, status_code: int, error_code: str, message: str) -> None:
        super().__init__(
            f"Timeweb API HTTP {status_code}"
            f" error_code={error_code or 'unknown'}"
            f" message={message or 'unknown'}"
        )
        self.status_code = status_code
        self.error_code = error_code


@dataclass(frozen=True)
class DnsAssessment:
    ready: bool
    reason: str


class TimewebClient:
    def __init__(self, token: str) -> None:
        if not token:
            raise DeploymentError("TIMEWEB_CLOUD_TOKEN is missing or empty.")
        self._token = token

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        timeout: int = 30,
    ) -> dict[str, Any]:
        data = None
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
        }
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(
            API_ROOT + path,
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(url=request, timeout=timeout) as response:
                body = response.read().decode("utf-8")
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                parsed = {}
            message_value = parsed.get("message", "")
            if isinstance(message_value, list):
                message = "; ".join(str(item) for item in message_value)
            else:
                message = str(message_value or "")
            raise TimewebApiError(
                exc.code,
                str(parsed.get("error_code") or ""),
                message,
            ) from exc

    def get_servers(self) -> list[dict[str, Any]]:
        return list(self.request("GET", "/servers").get("servers") or [])

    def get_server(self, server_id: int) -> dict[str, Any]:
        return dict(
            self.request("GET", f"/servers/{server_id}").get("server") or {}
        )

    def create_ssh_key(self, public_key: str, name: str) -> int:
        response = self.request(
            "POST",
            "/ssh-keys",
            {
                "body": public_key,
                "is_default": False,
                "name": name,
            },
        )
        key = dict(response.get("ssh_key") or {})
        if "id" not in key:
            raise DeploymentError("Timeweb did not return the created SSH key ID.")
        return int(float(key["id"]))

    def attach_ssh_key(self, server_id: int, ssh_key_id: int) -> None:
        self.request(
            "POST",
            f"/servers/{server_id}/ssh-keys",
            {"ssh_key_ids": [ssh_key_id]},
        )

    def detach_ssh_key(self, server_id: int, ssh_key_id: int) -> None:
        self.request(
            "DELETE",
            f"/servers/{server_id}/ssh-keys/{ssh_key_id}",
        )

    def delete_ssh_key(self, ssh_key_id: int) -> None:
        self.request("DELETE", f"/ssh-keys/{ssh_key_id}")


def add_summary(line: str) -> None:
    """Emit operational context to the workflow log only."""
    print(line)


def find_managed_server(
    client: TimewebClient,
    *,
    server_name: str,
    server_comment: str,
) -> dict[str, Any]:
    matches = [
        server
        for server in client.get_servers()
        if server.get("name") == server_name
    ]
    if len(matches) != 1:
        raise DeploymentError(
            f"Expected exactly one managed server named {server_name!r}; "
            f"found {len(matches)}."
        )
    server = matches[0]
    if server.get("comment") != server_comment:
        raise DeploymentError(
            "Target server exists but is not marked as managed by this project."
        )
    return client.get_server(int(float(server["id"])))


def public_addresses(server: dict[str, Any]) -> tuple[set[str], set[str]]:
    ipv4: set[str] = set()
    ipv6: set[str] = set()

    for network in server.get("networks") or []:
        network_type = str(network.get("type") or "").lower()
        if network_type in {"local", "private"}:
            continue
        for item in network.get("ips") or []:
            value = str(item.get("ip") or "").strip()
            if not value:
                continue
            try:
                address = ipaddress.ip_address(value)
            except ValueError:
                continue
            canonical = str(address)
            if address.version == 4:
                ipv4.add(canonical)
            else:
                ipv6.add(canonical)

    return ipv4, ipv6


def resolve_addresses(domain: str, family: socket.AddressFamily) -> set[str]:
    try:
        rows = socket.getaddrinfo(
            domain,
            80,
            family=family,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror:
        return set()

    result: set[str] = set()
    for row in rows:
        sockaddr = row[4]
        if sockaddr:
            result.add(str(sockaddr[0]))
    return result


def assess_dns(
    *,
    expected_ipv4: str,
    dns_ipv4: set[str],
    dns_ipv6: set[str],
) -> DnsAssessment:
    if expected_ipv4 not in dns_ipv4:
        return DnsAssessment(
            False,
            "A record does not yet resolve to the managed Timeweb IPv4.",
        )

    # For the initial production cutover we intentionally validate over IPv4
    # only. A stale AAAA can make Let's Encrypt prefer an unrelated IPv6 host.
    if dns_ipv6:
        return DnsAssessment(
            False,
            "AAAA record is still present. Remove it before issuing HTTPS.",
        )

    return DnsAssessment(True, "DNS is ready for IPv4 HTTP-01 validation.")


def verify_https() -> bool:
    request = urllib.request.Request(
        f"https://{DOMAIN_NAME}/",
        headers={"User-Agent": "omni-cio-deploy-verifier/1.0"},
    )
    try:
        with urllib.request.urlopen(
            url=request,
            timeout=15,
            context=ssl.create_default_context(),
        ) as response:
            body = response.read().decode("utf-8", errors="replace")
            return response.status == 200 and SITE_MARKER in body
    except (urllib.error.URLError, TimeoutError, socket.timeout, ssl.SSLError):
        return False


REMOTE_SCRIPT = r"""set -euo pipefail

DOMAIN="omnicio.ru"
WEBROOT="/var/www/${DOMAIN}/html"
NGINX_SITE="/etc/nginx/sites-available/${DOMAIN}"

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y nginx certbot python3-certbot-nginx ca-certificates

install -d -m 0755 "${WEBROOT}"
cat > "${WEBROOT}/index.html" <<'EOF'
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

cat > "${NGINX_SITE}" <<EOF
server {
    listen 80;
    listen [::]:80;

    server_name ${DOMAIN};
    root ${WEBROOT};
    index index.html;

    location /.well-known/acme-challenge/ {
        try_files \$uri =404;
    }

    location / {
        try_files \$uri \$uri/ =404;
    }
}
EOF

ln -sfn "${NGINX_SITE}" "/etc/nginx/sites-enabled/${DOMAIN}"
rm -f /etc/nginx/sites-enabled/default

nginx -t
systemctl enable nginx
systemctl reload nginx

certbot --nginx   --non-interactive   --agree-tos   --register-unsafely-without-email   --redirect   -d "${DOMAIN}"

if systemctl list-unit-files certbot.timer >/dev/null 2>&1; then
    systemctl enable --now certbot.timer
fi

nginx -t
systemctl reload nginx
"""


def capture_host_key(known_hosts: pathlib.Path) -> None:
    """Capture the pinned server key, then require strict matching for SSH."""
    result = subprocess.run(
        ["ssh-keyscan", "-T", "10", "-t", "ed25519", EXPECTED_SERVER_IPV4],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=20,
        check=False,
    )
    host_keys = [
        line
        for line in result.stdout.splitlines()
        if line and not line.startswith("#")
    ]
    if result.returncode != 0 or not host_keys:
        detail = (result.stderr or "no ED25519 host key returned").strip()
        raise DeploymentError(
            "Unable to capture the managed server SSH host key: "
            + detail[:300]
        )

    known_hosts.write_text("\n".join(host_keys) + "\n", encoding="utf-8")


def ssh_base_args(private_key: pathlib.Path, known_hosts: pathlib.Path) -> list[str]:
    return [
        "ssh",
        "-i",
        str(private_key),
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        f"UserKnownHostsFile={known_hosts}",
        "-o",
        "LogLevel=ERROR",
    ]


def wait_for_ssh(
    *,
    private_key: pathlib.Path,
    known_hosts: pathlib.Path,
    attempts: int = 18,
) -> None:
    command = ssh_base_args(private_key, known_hosts) + [
        f"root@{EXPECTED_SERVER_IPV4}",
        "true",
    ]
    last_error = "SSH not attempted"
    for _ in range(attempts):
        result = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=20,
            check=False,
        )
        if result.returncode == 0:
            return
        last_error = (result.stderr or "SSH failed").strip()
        time.sleep(10)
    raise DeploymentError(
        "Ephemeral SSH key was attached but SSH did not become ready: "
        + last_error[:300]
    )


def configure_remote_https(
    *,
    private_key: pathlib.Path,
    known_hosts: pathlib.Path,
) -> None:
    command = ssh_base_args(private_key, known_hosts) + [
        f"root@{EXPECTED_SERVER_IPV4}",
        "bash",
        "-s",
    ]
    result = subprocess.run(
        tuple(command),
        input=REMOTE_SCRIPT,
        text=True,
        timeout=900,
        check=False,
    )
    if result.returncode != 0:
        raise DeploymentError(
            f"Remote HTTPS configuration failed with exit code "
            f"{result.returncode}."
        )


def cleanup_ephemeral_key(
    *,
    client: TimewebClient,
    server_id: int,
    ssh_key_id: int,
) -> None:
    detach_error: Exception | None = None
    try:
        client.detach_ssh_key(server_id, ssh_key_id)
    except Exception as exc:
        detach_error = exc
        add_summary(
            "- Warning: failed to detach the ephemeral SSH public key from "
            "the server; its private half no longer exists after this runner."
        )

    try:
        client.delete_ssh_key(ssh_key_id)
    except Exception:
        add_summary(
            "- Warning: failed to delete the ephemeral SSH public key record "
            "from Timeweb."
        )

    if detach_error:
        print(f"::warning::{detach_error}", file=sys.stderr)


def validate_managed_server_identity(
    server: dict[str, Any],
) -> tuple[int, set[str]]:
    server_id = int(float(server["id"]))
    server_ipv4, server_ipv6 = public_addresses(server)

    if server_id != EXPECTED_SERVER_ID:
        raise DeploymentError(
            "Managed server identity changed. Update the pinned server ID "
            "through reviewed repository state before remote administration."
        )
    if server_ipv4 != {EXPECTED_SERVER_IPV4}:
        raise DeploymentError(
            "Managed server IPv4 changed. Update the pinned IPv4 through "
            "reviewed repository state before remote administration."
        )

    return server_id, server_ipv6


def configure_with_ephemeral_key(
    *,
    client: TimewebClient,
    server_id: int,
) -> None:
    with tempfile.TemporaryDirectory(prefix="omni-cio-tls-") as tempdir:
        temp_path = pathlib.Path(tempdir)
        private_key = temp_path / "id_ed25519"
        known_hosts = temp_path / "known_hosts"

        subprocess.run(
            [
                "ssh-keygen",
                "-q",
                "-t",
                "ed25519",
                "-N",
                "",
                "-C",
                "omni-cio-github-actions-ephemeral",
                "-f",
                str(private_key),
            ],
            check=True,
            timeout=30,
        )
        public_key = private_key.with_suffix(".pub").read_text(
            encoding="utf-8"
        ).strip()
        capture_host_key(known_hosts)

        run_id = os.environ.get("GITHUB_RUN_ID", "")
        if run_id and not run_id.isdigit():
            raise DeploymentError("GITHUB_RUN_ID must contain digits only.")
        key_name = f"gha-omnicio-tls-{run_id or int(time.time())}"
        ssh_key_id = client.create_ssh_key(public_key, key_name)
        attached = False
        try:
            client.attach_ssh_key(server_id, ssh_key_id)
            attached = True
            add_summary(
                "- Temporary SSH public key attached for server configuration."
            )
            wait_for_ssh(
                private_key=private_key,
                known_hosts=known_hosts,
            )
            configure_remote_https(
                private_key=private_key,
                known_hosts=known_hosts,
            )
        finally:
            if attached:
                cleanup_ephemeral_key(
                    client=client,
                    server_id=server_id,
                    ssh_key_id=ssh_key_id,
                )
            else:
                try:
                    client.delete_ssh_key(ssh_key_id)
                except Exception:
                    pass


def run(*, client: TimewebClient) -> int:
    add_summary("## omnicio.ru HTTPS bootstrap")

    if verify_https():
        add_summary(f"- HTTPS is already ready: https://{DOMAIN_NAME}/")
        return 0

    server = find_managed_server(
        client,
        server_name=SERVER_NAME,
        server_comment=SERVER_COMMENT,
    )
    server_id, server_ipv6 = validate_managed_server_identity(server)
    ipv4 = EXPECTED_SERVER_IPV4
    dns_ipv4 = resolve_addresses(DOMAIN_NAME, socket.AF_INET)
    dns_ipv6 = resolve_addresses(DOMAIN_NAME, socket.AF_INET6)

    add_summary(f"- Managed server: id `{server_id}`, IPv4 `{ipv4}`.")
    add_summary(
        f"- DNS A: `{', '.join(sorted(dns_ipv4)) or 'none'}`; "
        f"AAAA: `{', '.join(sorted(dns_ipv6)) or 'none'}`."
    )
    if server_ipv6:
        add_summary(
            f"- Server currently reports IPv6: "
            f"`{', '.join(sorted(server_ipv6))}`."
        )

    assessment = assess_dns(
        expected_ipv4=ipv4,
        dns_ipv4=dns_ipv4,
        dns_ipv6=dns_ipv6,
    )
    if not assessment.ready:
        add_summary(f"- Result: `pending_dns`. {assessment.reason}")
        add_summary(
            "- No SSH key was created and no server configuration was changed. "
            "A scheduled accepted-main run will retry after DNS delegation/propagation."
        )
        print(
            "::warning title=DNS pending::omnicio.ru is not yet publicly "
            "delegated/resolved to the managed Timeweb IPv4."
        )
        return 0

    configure_with_ephemeral_key(
        client=client,
        server_id=server_id,
    )

    if not verify_https():
        raise DeploymentError(
            "Nginx/Certbot completed, but public HTTPS verification failed."
        )

    add_summary(f"- HTTPS verified successfully: https://{DOMAIN_NAME}/")
    add_summary("- HTTP is redirected to HTTPS by Certbot/Nginx.")
    add_summary("- Certbot renewal timer is enabled on the server.")
    return 0


def main() -> int:
    try:
        client = TimewebClient(os.environ.get("TIMEWEB_CLOUD_TOKEN", ""))
        return run(client=client)
    except (DeploymentError, TimewebApiError, subprocess.SubprocessError) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
