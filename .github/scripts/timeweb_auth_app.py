#!/usr/bin/env python3
"""Deploy the accepted OmniCIO auth application to the managed VDS."""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import pathlib
import re
import socket
import ssl
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
from typing import Iterable

from timeweb_auth_postgres import (
    AmbiguousProviderError,
    EphemeralSsh,
    InfraError,
    TimewebApiError,
    TimewebClient,
    find_managed_server,
    integer_value,
    public_ipv4,
)

DOMAIN = "omnicio.ru"
SITE_MARKER = 'name="omni-cio-white-site"'
RUNTIME_ENV = "/etc/omnicio/runtime.env"
RELEASE_RE = re.compile(r"^[0-9a-f]{40}$")


def add_summary(line: str) -> None:
    print(line)


def set_output(name: str, value: str) -> None:
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")


def iter_release_files(root: pathlib.Path) -> Iterable[pathlib.Path]:
    for relative in ("pyproject.toml", "src", "web"):
        path = root / relative
        if path.is_file():
            yield path
            continue
        for item in sorted(path.rglob("*")):
            if item.is_file() and "__pycache__" not in item.parts:
                yield item


def build_release_archive(root: pathlib.Path) -> str:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for source in iter_release_files(root):
            archive.add(source, arcname=source.relative_to(root), recursive=False)
    raw = buffer.getvalue()
    if not raw:
        raise InfraError("Release archive is empty")
    if len(raw) > 5 * 1024 * 1024:
        raise InfraError("Release archive unexpectedly exceeds 5 MiB")
    return base64.b64encode(raw).decode("ascii")


def runtime_is_ready(ssh: EphemeralSsh) -> bool:
    command = (
        f"test -s {RUNTIME_ENV} && "
        f"grep -q '^DATABASE_URL=' {RUNTIME_ENV} && "
        f"grep -q '^PHONE_CRYPTO_KEY=' {RUNTIME_ENV} && "
        f"grep -q '^REGISTRATION_ENABLED=false$' {RUNTIME_ENV}"
    )
    try:
        ssh.run(command)
        return True
    except InfraError:
        return False


REMOTE_DEPLOY_SCRIPT = r"""set -euo pipefail

SHA="$1"
RELEASE="/opt/omnicio/releases/$SHA"
APP_CURRENT="/opt/omnicio/current"
WEB_BASE="/var/www/omnicio.ru"
WEB_RELEASE="$WEB_BASE/releases/$SHA"
WEB_CURRENT="$WEB_BASE/current"
SERVICE="/etc/systemd/system/omnicio-auth.service"
NGINX_SITE="/etc/nginx/sites-available/omnicio.ru"
STATE="/run/omnicio-auth-deploy-$SHA.state"

test -s /etc/omnicio/runtime.env
test -s /etc/letsencrypt/live/omnicio.ru/fullchain.pem
test -s /etc/letsencrypt/live/omnicio.ru/privkey.pem
test -s "$RELEASE/pyproject.toml"
test -s "$RELEASE/web/index.html"

PREVIOUS_APP="$(readlink -f "$APP_CURRENT" 2>/dev/null || true)"
PREVIOUS_WEB="$(readlink -f "$WEB_CURRENT" 2>/dev/null || true)"
{
    printf 'PREVIOUS_APP=%q\n' "$PREVIOUS_APP"
    printf 'PREVIOUS_WEB=%q\n' "$PREVIOUS_WEB"
} > "$STATE"
chmod 600 "$STATE"

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3-venv ca-certificates nginx curl

if ! id omnicio >/dev/null 2>&1; then
    useradd --system --home /nonexistent --shell /usr/sbin/nologin omnicio
fi

python3 -m venv "$RELEASE/.venv"
"$RELEASE/.venv/bin/python" -m pip install --disable-pip-version-check -q --upgrade pip
"$RELEASE/.venv/bin/python" -m pip install --disable-pip-version-check -q "$RELEASE"

install -d -m 0755 "$WEB_RELEASE/assets"
install -m 0644 "$RELEASE/web/index.html" "$WEB_RELEASE/index.html"
install -m 0644 "$RELEASE/web/app.js" "$WEB_RELEASE/assets/app.js"
install -m 0644 "$RELEASE/web/app.css" "$WEB_RELEASE/assets/app.css"

cat > "$SERVICE.new" <<'EOF'
[Unit]
Description=OmniCIO authentication API
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=omnicio
Group=omnicio
WorkingDirectory=/opt/omnicio/current
EnvironmentFile=/etc/omnicio/runtime.env
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/opt/omnicio/current/.venv/bin/uvicorn omnicio.main:app --host 127.0.0.1 --port 8001 --workers 2 --proxy-headers --forwarded-allow-ips=127.0.0.1
Restart=on-failure
RestartSec=3
TimeoutStartSec=45
TimeoutStopSec=20
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=strict
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
LockPersonality=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
CapabilityBoundingSet=

[Install]
WantedBy=multi-user.target
EOF
mv "$SERVICE.new" "$SERVICE"
chmod 0644 "$SERVICE"

ln -sfn "$RELEASE" "$APP_CURRENT"
systemctl daemon-reload
systemctl enable omnicio-auth.service >/dev/null
systemctl restart omnicio-auth.service

READY=0
for _ in $(seq 1 20); do
    if curl -fsS --max-time 3 http://127.0.0.1:8001/health/ready >/dev/null; then
        READY=1
        break
    fi
    sleep 2
done

if [ "$READY" != "1" ]; then
    if [ -n "$PREVIOUS_APP" ] && [ -d "$PREVIOUS_APP" ]; then
        ln -sfn "$PREVIOUS_APP" "$APP_CURRENT"
        systemctl restart omnicio-auth.service || true
    fi
    exit 41
fi

if [ -f "$NGINX_SITE" ]; then
    cp -a "$NGINX_SITE" "$NGINX_SITE.pre-auth"
fi

cat > "$NGINX_SITE.new" <<'EOF'
server {
    listen 80;
    listen [::]:80;
    server_name omnicio.ru;

    location /.well-known/acme-challenge/ {
        root /var/www/omnicio.ru/current;
        try_files $uri =404;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name omnicio.ru;

    ssl_certificate /etc/letsencrypt/live/omnicio.ru/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/omnicio.ru/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    root /var/www/omnicio.ru/current;
    index index.html;

    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'" always;

    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 5s;
        proxy_read_timeout 30s;
        proxy_send_timeout 30s;
    }

    location /health/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 5s;
        proxy_read_timeout 10s;
    }

    location /assets/ {
        try_files $uri =404;
        add_header Cache-Control "public, max-age=300";
    }

    location / {
        try_files $uri $uri/ /index.html;
        add_header Cache-Control "no-store";
    }
}
EOF

mv "$NGINX_SITE.new" "$NGINX_SITE"
ln -sfn "$NGINX_SITE" /etc/nginx/sites-enabled/omnicio.ru
rm -f /etc/nginx/sites-enabled/default
ln -sfn "$WEB_RELEASE" "$WEB_CURRENT"

if ! nginx -t; then
    if [ -f "$NGINX_SITE.pre-auth" ]; then
        mv "$NGINX_SITE.pre-auth" "$NGINX_SITE"
    fi
    if [ -n "$PREVIOUS_WEB" ] && [ -d "$PREVIOUS_WEB" ]; then
        ln -sfn "$PREVIOUS_WEB" "$WEB_CURRENT"
    fi
    nginx -t || true
    exit 42
fi

systemctl reload nginx
"""


REMOTE_ROLLBACK_SCRIPT = r"""set -euo pipefail

SHA="$1"
STATE="/run/omnicio-auth-deploy-$SHA.state"
NGINX_SITE="/etc/nginx/sites-available/omnicio.ru"

if [ -s "$STATE" ]; then
    . "$STATE"
    if [ -n "$PREVIOUS_APP" ] && [ -d "$PREVIOUS_APP" ]; then
        ln -sfn "$PREVIOUS_APP" /opt/omnicio/current
        systemctl restart omnicio-auth.service || true
    fi
    if [ -n "$PREVIOUS_WEB" ] && [ -d "$PREVIOUS_WEB" ]; then
        ln -sfn "$PREVIOUS_WEB" /var/www/omnicio.ru/current
    fi
fi

if [ -f "$NGINX_SITE.pre-auth" ]; then
    mv "$NGINX_SITE.pre-auth" "$NGINX_SITE"
fi
nginx -t && systemctl reload nginx || true
"""


def upload_release(
    ssh: EphemeralSsh,
    *,
    archive_b64: str,
    release_sha: str,
) -> None:
    release = f"/opt/omnicio/releases/{release_sha}"
    command = (
        f"rm -rf {release}; "
        f"install -d -m 0755 {release}; "
        f"base64 -d | tar -xzf - -C {release}"
    )
    ssh.run(command, input_text=archive_b64)


def deploy_remote(ssh: EphemeralSsh, *, release_sha: str) -> None:
    ssh.run(f"bash -s -- {release_sha}", input_text=REMOTE_DEPLOY_SCRIPT)


def rollback_remote(ssh: EphemeralSsh, *, release_sha: str) -> None:
    try:
        ssh.run(f"bash -s -- {release_sha}", input_text=REMOTE_ROLLBACK_SCRIPT)
    except InfraError:
        pass


def verify_public() -> None:
    context = ssl.create_default_context()
    root_request = urllib.request.Request(
        f"https://{DOMAIN}/",
        headers={"User-Agent": "omnicio-auth-deploy/1.0"},
    )
    config_request = urllib.request.Request(
        f"https://{DOMAIN}/api/auth/config",
        headers={"User-Agent": "omnicio-auth-deploy/1.0"},
    )

    try:
        with urllib.request.urlopen(
            root_request,
            timeout=15,
            context=context,
        ) as response:
            root_body = response.read().decode(errors="replace")
            if response.status != 200 or SITE_MARKER not in root_body:
                raise InfraError("Public auth page verification failed")

        with urllib.request.urlopen(
            config_request,
            timeout=15,
            context=context,
        ) as response:
            payload = json.loads(response.read().decode())
            if response.status != 200:
                raise InfraError("Public auth config returned non-200")
            if payload.get("registration_enabled") is not False:
                raise InfraError(
                    "Registration unexpectedly became enabled during app deploy"
                )
    except (
        urllib.error.URLError,
        TimeoutError,
        socket.timeout,
        ssl.SSLError,
        json.JSONDecodeError,
    ) as exc:
        raise InfraError(
            f"Public application verification failed: {type(exc).__name__}"
        ) from exc


def reconcile(
    client: TimewebClient,
    *,
    server_name: str,
    server_comment: str,
    release_sha: str,
    repository_root: pathlib.Path,
) -> int:
    if not RELEASE_RE.fullmatch(release_sha):
        raise InfraError("Release SHA must be a full lowercase 40-character SHA")

    add_summary("## OmniCIO auth application deploy")
    server_summary = find_managed_server(
        client.get_servers(),
        name=server_name,
        comment=server_comment,
    )
    server_id = integer_value(server_summary["id"])
    server = client.get_server(server_id)
    archive_b64 = build_release_archive(repository_root)

    with EphemeralSsh(
        client=client,
        server_id=server_id,
        server_ip=public_ipv4(server),
    ) as ssh:
        if not runtime_is_ready(ssh):
            add_summary(
                "- Result: pending_database. PostgreSQL/runtime secrets are "
                "not ready; no application or Nginx configuration was changed."
            )
            set_output("status", "pending_database")
            return 0

        upload_release(ssh, archive_b64=archive_b64, release_sha=release_sha)
        deploy_remote(ssh, release_sha=release_sha)

        try:
            for _ in range(6):
                try:
                    verify_public()
                    break
                except InfraError:
                    time.sleep(5)
            else:
                raise InfraError("Public verification did not become healthy")
        except InfraError:
            rollback_remote(ssh, release_sha=release_sha)
            raise

    add_summary(
        f"- Result: app_ready. Release {release_sha[:12]} is healthy over HTTPS; "
        "registration remains disabled."
    )
    set_output("status", "app_ready")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-name", required=True)
    parser.add_argument("--server-comment", required=True)
    parser.add_argument("--release-sha", required=True)
    parser.add_argument("--repository-root", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        client = TimewebClient(os.environ.get("TIMEWEB_CLOUD_TOKEN", ""))
        return reconcile(
            client,
            server_name=args.server_name,
            server_comment=args.server_comment,
            release_sha=args.release_sha,
            repository_root=pathlib.Path(args.repository_root).resolve(),
        )
    except (
        InfraError,
        TimewebApiError,
        AmbiguousProviderError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
