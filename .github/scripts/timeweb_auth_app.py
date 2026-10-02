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
import ssl
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
from collections.abc import Iterable

from timeweb_auth_postgres import (
    AmbiguousProviderError,
    EphemeralSsh,
    InfraError,
    TimewebApiError,
    TimewebClient,
    find_managed_server,
    find_vpc,
    integer_value,
    public_ipv4,
)

DOMAIN = "omnicio.ru"
SITE_MARKER = 'name="omni-cio-white-site"'
LEGAL_PAGES = {
    "/legal/privacy.html": "Политика обработки персональных данных",
    "/legal/consent.html": "Согласие на обработку персональных данных",
    "/legal/terms.html": "Пользовательские правила OmniCIO Personal",
}
LEGAL_OPERATOR_MARKERS = (
    "__OMNICIO_OPERATOR_NAME__",
    "__OMNICIO_OPERATOR_ADDRESS__",
    "__OMNICIO_OPERATOR_EMAIL__",
)
RUNTIME_ENV = "/etc/omnicio/runtime.env"
PRODUCT_ENV = "/etc/omnicio/product.env"
LEGACY_RESET_MARKER = "/etc/omnicio/legacy-profile-reset-v1.done"
RELEASE_RE = re.compile(r"^[0-9a-f]{40}$")
BRAND_RUNTIME_FILES = (
    "assets/brand/transparent/omni-sentinel-core-color-1024.png",
    "assets/brand/web/apple-touch-icon-180.png",
    "assets/brand/web/favicon.ico",
    "assets/brand/web/pwa-icon-192.png",
    "assets/brand/web/pwa-icon-512.png",
    "assets/brand/web/pwa-maskable-512.png",
)
BRAND_PUBLIC_MARK = "/assets/brand/omni-sentinel-core-color-1024.png"
WEB_MANIFEST_PATH = "/manifest.webmanifest"
VERSION_PUBLIC_PATH = "/version.js"


def add_summary(line: str) -> None:
    print(line)


def set_output(name: str, value: str) -> None:
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")


def iter_release_files(root: pathlib.Path) -> Iterable[pathlib.Path]:
    paths = ("pyproject.toml", "requirements-runtime.txt", "src", "web", *BRAND_RUNTIME_FILES)
    for relative in paths:
        path = root / relative
        if path.is_file():
            yield path
            continue
        if not path.is_dir():
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
    schema_query = (
        "SELECT CASE WHEN "
        "to_regclass('public.users') IS NOT NULL "
        "AND to_regclass('public.sessions') IS NOT NULL "
        "AND to_regclass('public.legal_acceptances') IS NOT NULL "
        "AND to_regclass('public.vkid_identities') IS NOT NULL "
        "AND to_regclass('public.tbank_connection') IS NOT NULL "
        "AND EXISTS (SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = 'users' "
        "AND column_name = 'role') "
        "THEN 'ready' ELSE 'missing' END"
    )
    command = (
        f"test -s {RUNTIME_ENV} && "
        f"grep -q '^DATABASE_URL=' {RUNTIME_ENV} && "
        f"grep -q '^VKID_FLOW_CRYPTO_KEY=' {RUNTIME_ENV} && "
        f"grep -q '^BROKER_TOKEN_CRYPTO_KEY=' {RUNTIME_ENV} && "
        "command -v psql >/dev/null 2>&1 && "
        "set -a && "
        f". {RUNTIME_ENV} && "
        "set +a && "
        f'test "$(psql "$DATABASE_URL" -Atqc "{schema_query}" 2>/dev/null)" = "ready"'
    )
    try:
        ssh.run(command)
        return True
    except InfraError:
        return False


def _environment_value(value: str) -> str:
    if "\n" in value or "\r" in value:
        raise InfraError("Runtime environment value contains a newline")
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _positive_numeric_id(value: str) -> bool:
    return value.isdigit() and int(value) > 0


def _strict_boolean_environment(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    normalized = raw.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise InfraError(f"{name} must be true or false")


def registration_enabled() -> bool:
    return _strict_boolean_environment("REGISTRATION_ENABLED", False)


def registration_max_users() -> int:
    raw = os.environ.get("REGISTRATION_MAX_USERS", "1").strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise InfraError("REGISTRATION_MAX_USERS must be an integer") from exc
    if value <= 0:
        raise InfraError("REGISTRATION_MAX_USERS must be positive")
    return value


def vkid_configuration_ready() -> bool:
    return _positive_numeric_id(os.environ.get("VKID_APP_ID", "").strip())


def legacy_profile_reset_enabled() -> bool:
    return _strict_boolean_environment("LEGACY_PROFILE_RESET_ENABLED", False)


def validate_product_environment() -> None:
    required_names = (
        "LEGAL_PRIVACY_VERSION",
        "LEGAL_CONSENT_VERSION",
        "LEGAL_TERMS_VERSION",
    )
    missing = [
        name
        for name in required_names
        if not os.environ.get(name, "").strip()
    ]
    if missing:
        raise InfraError(
            "Required auth product configuration is missing: "
            + ", ".join(missing)
        )

    if not vkid_configuration_ready():
        raise InfraError("VKID_APP_ID must be a positive numeric value")

    if registration_enabled():
        if not _strict_boolean_environment("MULTIUSER_LEGAL_APPROVED", False):
            raise InfraError(
                "Registration requires an explicit reviewed legal approval gate"
            )
        if not _strict_boolean_environment("RKN_NOTIFICATION_CONFIRMED", False):
            raise InfraError(
                "Registration requires the confirmed personal-data regulatory gate"
            )
        registration_max_users()

        operator_name = os.environ.get("LEGAL_OPERATOR_NAME", "").strip()
        operator_address = os.environ.get("LEGAL_OPERATOR_ADDRESS", "").strip()
        operator_email = os.environ.get("LEGAL_OPERATOR_EMAIL", "").strip()
        if not 3 <= len(operator_name) <= 200:
            raise InfraError("LEGAL_OPERATOR_NAME must contain 3-200 characters")
        if not 5 <= len(operator_address) <= 300:
            raise InfraError("LEGAL_OPERATOR_ADDRESS must contain 5-300 characters")
        if not re.fullmatch(
            r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}",
            operator_email,
        ):
            raise InfraError("LEGAL_OPERATOR_EMAIL must be a valid email address")


def validate_legal_documents(repository_root: pathlib.Path) -> None:
    for relative in (
        "web/legal/privacy.html",
        "web/legal/consent.html",
        "web/legal/terms.html",
    ):
        path = repository_root / relative
        try:
            body = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise InfraError(f"Legal document is unavailable: {relative}") from exc
        missing = [marker for marker in LEGAL_OPERATOR_MARKERS if marker not in body]
        if missing:
            raise InfraError(
                f"Legal document {relative} is missing operator placeholders"
            )


def build_product_environment() -> str:
    values = {
        "VKID_APP_ID": os.environ.get("VKID_APP_ID", "").strip(),
        "VKID_LOGIN_ENABLED": "true" if vkid_configuration_ready() else "false",
        "REGISTRATION_ENABLED": "true" if registration_enabled() else "false",
        "REGISTRATION_MAX_USERS": str(registration_max_users()),
        "LEGAL_OPERATOR_NAME": os.environ.get("LEGAL_OPERATOR_NAME", "").strip(),
        "LEGAL_OPERATOR_ADDRESS": os.environ.get("LEGAL_OPERATOR_ADDRESS", "").strip(),
        "LEGAL_OPERATOR_EMAIL": os.environ.get("LEGAL_OPERATOR_EMAIL", "").strip(),
        "LEGAL_PRIVACY_VERSION": os.environ.get("LEGAL_PRIVACY_VERSION", "").strip(),
        "LEGAL_CONSENT_VERSION": os.environ.get("LEGAL_CONSENT_VERSION", "").strip(),
        "LEGAL_TERMS_VERSION": os.environ.get("LEGAL_TERMS_VERSION", "").strip(),
        "VKID_FLOW_TTL_SECONDS": os.environ.get("VKID_FLOW_TTL_SECONDS", "600").strip(),
        "SESSION_TTL_SECONDS": os.environ.get("SESSION_TTL_SECONDS", "34560000").strip(),
    }
    return "".join(
        f"{name}={_environment_value(value)}\n"
        for name, value in values.items()
    )


def product_environment_backup_paths(release_sha: str) -> tuple[str, str]:
    if not RELEASE_RE.fullmatch(release_sha):
        raise InfraError("Release SHA must be a full lowercase 40-character SHA")
    return (
        f"{PRODUCT_ENV}.pre-{release_sha}",
        f"{PRODUCT_ENV}.pre-{release_sha}.state",
    )


def write_product_environment(ssh: EphemeralSsh, *, release_sha: str) -> None:
    backup, state = product_environment_backup_paths(release_sha)
    command = (
        "set -euo pipefail; umask 077; "
        f"tmp={PRODUCT_ENV}.tmp-{release_sha}; "
        f"if [ -f {PRODUCT_ENV} ]; then "
        f"cp -p {PRODUCT_ENV} {backup}; printf 'present\\n' > {state}; "
        f"else rm -f {backup}; printf 'absent\\n' > {state}; fi; "
        'cat > "$tmp"; chmod 600 "$tmp"; '
        f"mv -f \"$tmp\" {PRODUCT_ENV}"
    )
    ssh.run(command, input_text=build_product_environment())


def commit_product_environment(ssh: EphemeralSsh, *, release_sha: str) -> None:
    backup, state = product_environment_backup_paths(release_sha)
    ssh.run(f"rm -f {backup} {state}")


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
apt-get install -y -qq python3-venv ca-certificates nginx curl openssl

install_tbank_trusted_ca() {
    CERT_TMP="$(mktemp -d)"
    ROOT_CER="$CERT_TMP/russian_trusted_root_ca.cer"
    SUB_CER="$CERT_TMP/russian_trusted_sub_ca.cer"
    ROOT_PEM="$CERT_TMP/russian_trusted_root_ca.pem"
    SUB_PEM="$CERT_TMP/russian_trusted_sub_ca.pem"

    curl --fail --location --silent --show-error --retry 3 \
        --connect-timeout 10 --max-time 30 \
        -o "$ROOT_CER" \
        "https://gu-st.ru/content/Other/doc/russian_trusted_root_ca.cer"
    curl --fail --location --silent --show-error --retry 3 \
        --connect-timeout 10 --max-time 30 \
        -o "$SUB_CER" \
        "https://gu-st.ru/content/Other/doc/russian_trusted_sub_ca.cer"

    if openssl x509 -in "$ROOT_CER" -noout >/dev/null 2>&1; then
        cp "$ROOT_CER" "$ROOT_PEM"
    else
        openssl x509 -inform DER -in "$ROOT_CER" -out "$ROOT_PEM"
    fi
    if openssl x509 -in "$SUB_CER" -noout >/dev/null 2>&1; then
        cp "$SUB_CER" "$SUB_PEM"
    else
        openssl x509 -inform DER -in "$SUB_CER" -out "$SUB_PEM"
    fi

    openssl x509 -in "$ROOT_PEM" -noout -subject | grep -F "Russian Trusted Root CA" >/dev/null
    openssl x509 -in "$SUB_PEM" -noout -subject | grep -F "Russian Trusted Sub CA" >/dev/null
    openssl verify -CAfile "$ROOT_PEM" "$SUB_PEM" >/dev/null

    install -m 0644 "$ROOT_PEM" /usr/local/share/ca-certificates/russian_trusted_root_ca.crt
    install -m 0644 "$SUB_PEM" /usr/local/share/ca-certificates/russian_trusted_sub_ca.crt
    update-ca-certificates >/dev/null
    rm -rf "$CERT_TMP"
}

install_tbank_trusted_ca

if curl --silent --show-error --connect-timeout 5 --max-time 10 \
    -o /dev/null "https://invest-public-api.tbank.ru/"; then
    echo "T-Invest TLS probe: ok"
else
    echo "T-Invest TLS probe: failed" >&2
fi

if ! id omnicio >/dev/null 2>&1; then
    useradd --system --home /nonexistent --shell /usr/sbin/nologin omnicio
fi

python3 -m venv "$RELEASE/.venv"
"$RELEASE/.venv/bin/python" -m pip install --disable-pip-version-check -q \
    --only-binary=:all: --require-hashes -r "$RELEASE/requirements-runtime.txt"
"$RELEASE/.venv/bin/python" -m pip install --disable-pip-version-check -q \
    --no-deps --no-build-isolation --no-index --only-binary=:all: "$RELEASE"

install -d -m 0755 "$WEB_RELEASE/assets" "$WEB_RELEASE/assets/brand" "$WEB_RELEASE/legal"
install -m 0644 "$RELEASE/web/manifest.webmanifest" "$WEB_RELEASE/manifest.webmanifest"
install -m 0644 "$RELEASE/web/app.js" "$WEB_RELEASE/assets/app.js"
install -m 0644 "$RELEASE/web/app.css" "$WEB_RELEASE/assets/app.css"
install -m 0644 "$RELEASE/assets/brand/transparent/omni-sentinel-core-color-1024.png" "$WEB_RELEASE/assets/brand/omni-sentinel-core-color-1024.png"
install -m 0644 "$RELEASE/assets/brand/web/apple-touch-icon-180.png" "$WEB_RELEASE/assets/brand/apple-touch-icon-180.png"
install -m 0644 "$RELEASE/assets/brand/web/favicon.ico" "$WEB_RELEASE/assets/brand/favicon.ico"
install -m 0644 "$RELEASE/assets/brand/web/pwa-icon-192.png" "$WEB_RELEASE/assets/brand/pwa-icon-192.png"
install -m 0644 "$RELEASE/assets/brand/web/pwa-icon-512.png" "$WEB_RELEASE/assets/brand/pwa-icon-512.png"
install -m 0644 "$RELEASE/assets/brand/web/pwa-maskable-512.png" "$WEB_RELEASE/assets/brand/pwa-maskable-512.png"
set -a
. /etc/omnicio/product.env
set +a

python3 - "$RELEASE/web/legal" "$WEB_RELEASE/legal" <<'PY'
import html
import os
import pathlib
import sys

source = pathlib.Path(sys.argv[1])
destination = pathlib.Path(sys.argv[2])
replacements = {
    "__OMNICIO_OPERATOR_NAME__": html.escape(os.environ["LEGAL_OPERATOR_NAME"], quote=True),
    "__OMNICIO_OPERATOR_ADDRESS__": html.escape(os.environ["LEGAL_OPERATOR_ADDRESS"], quote=True),
    "__OMNICIO_OPERATOR_EMAIL__": html.escape(os.environ["LEGAL_OPERATOR_EMAIL"], quote=True),
}
for name in ("privacy.html", "consent.html", "terms.html"):
    body = (source / name).read_text(encoding="utf-8")
    for marker, value in replacements.items():
        body = body.replace(marker, value)
    if "__OMNICIO_OPERATOR_" in body:
        raise SystemExit(f"unresolved legal operator marker: {name}")
    (destination / name).write_text(body, encoding="utf-8")
PY
chmod 0644 "$WEB_RELEASE/legal/privacy.html" "$WEB_RELEASE/legal/consent.html" "$WEB_RELEASE/legal/terms.html"

python3 - "$RELEASE/pyproject.toml" "$SHA" "$RELEASE/web/index.html" "$WEB_RELEASE/index.html" "$WEB_RELEASE/version.js" <<'PY'
import json
import pathlib
import sys
import tomllib

with open(sys.argv[1], "rb") as handle:
    version = str(tomllib.load(handle)["project"]["version"])
build = sys.argv[2][:12]
template = pathlib.Path(sys.argv[3]).read_text(encoding="utf-8")
for marker in ("__OMNICIO_VERSION__", "__OMNICIO_BUILD__"):
    if marker not in template:
        raise SystemExit(f"missing release marker: {marker}")
rendered = (
    template
    .replace("__OMNICIO_VERSION__", version)
    .replace("__OMNICIO_BUILD__", build)
)
pathlib.Path(sys.argv[4]).write_text(rendered, encoding="utf-8")
payload = {"version": version, "build": build}
pathlib.Path(sys.argv[5]).write_text(
    "window.OMNICIO_RELEASE = "
    + json.dumps(payload, separators=(",", ":"))
    + ";\n",
    encoding="utf-8",
)
PY
chmod 0644 "$WEB_RELEASE/index.html" "$WEB_RELEASE/version.js"

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
EnvironmentFile=/etc/omnicio/product.env
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
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

    location = /assets/app.css {
        try_files $uri =404;
        add_header Cache-Control "no-cache";
    }

    location = /assets/app.js {
        try_files $uri =404;
        add_header Cache-Control "no-cache";
    }

    location /assets/ {
        try_files $uri =404;
        add_header Cache-Control "public, max-age=86400";
    }

    location = /manifest.webmanifest {
        try_files $uri =404;
        add_header Cache-Control "no-cache";
    }

    location = /version.js {
        try_files $uri =404;
        add_header Cache-Control "no-cache";
    }

    location / {
        try_files $uri $uri/ /index.html;
        add_header Cache-Control "no-cache";
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
PRODUCT_ENV="/etc/omnicio/product.env"
PRODUCT_ENV_BACKUP="$PRODUCT_ENV.pre-$SHA"
PRODUCT_ENV_STATE="$PRODUCT_ENV.pre-$SHA.state"

if [ -f "$PRODUCT_ENV_STATE" ]; then
    PRODUCT_ENV_PREVIOUS="$(cat "$PRODUCT_ENV_STATE")"
    if [ "$PRODUCT_ENV_PREVIOUS" = "present" ]; then
        test -f "$PRODUCT_ENV_BACKUP"
        cp -p "$PRODUCT_ENV_BACKUP" "$PRODUCT_ENV"
    elif [ "$PRODUCT_ENV_PREVIOUS" = "absent" ]; then
        rm -f "$PRODUCT_ENV"
    else
        exit 44
    fi
fi

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


def retire_legacy_profile(ssh: EphemeralSsh) -> None:
    if not legacy_profile_reset_enabled():
        return

    try:
        ssh.run(f"test -f {LEGACY_RESET_MARKER}")
        return
    except InfraError:
        pass

    sql = """
BEGIN;
SELECT pg_advisory_xact_lock(hashtextextended('omnicio-legacy-profile-reset', 0));

DO $$
DECLARE
    total_users bigint;
    legacy_users bigint;
BEGIN
    SELECT count(*) INTO total_users FROM users;
    SELECT count(*) INTO legacy_users FROM users WHERE public_id = 1;

    IF total_users > 1 THEN
        RAISE EXCEPTION 'legacy reset refuses a database containing multiple users';
    END IF;
    IF total_users = 1 AND legacy_users <> 1 THEN
        RAISE EXCEPTION 'legacy reset refuses to delete a non-legacy user';
    END IF;
END
$$;

INSERT INTO audit_events (user_id, event_type, metadata)
SELECT id, 'legacy_profile_retired', '{"reason":"limited_user_cutover"}'::jsonb
FROM users
WHERE public_id = 1;

DELETE FROM users
WHERE public_id = 1;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM users WHERE public_id = 1) THEN
        RAISE EXCEPTION 'legacy reset postcondition failed';
    END IF;
END
$$;

COMMIT;
"""
    command = (
        "set -a && "
        f". {RUNTIME_ENV} && "
        "set +a && "
        'export PGCONNECT_TIMEOUT=10; '
        'export PGOPTIONS="-c statement_timeout=30000 -c lock_timeout=5000"; '
        'psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -q'
    )
    ssh.run(command, input_text=sql)
    ssh.run(
        f"umask 077; install -d -m 0700 /etc/omnicio; "
        f"touch {LEGACY_RESET_MARKER}; chmod 0600 {LEGACY_RESET_MARKER}"
    )


def rollback_remote(ssh: EphemeralSsh, *, release_sha: str) -> None:
    try:
        ssh.run(f"bash -s -- {release_sha}", input_text=REMOTE_ROLLBACK_SCRIPT)
    except InfraError:
        pass


def fetch_public(path: str, context: ssl.SSLContext) -> tuple[bytes, str]:
    request = urllib.request.Request(
        f"https://{DOMAIN}{path}",
        headers={"User-Agent": "omnicio-auth-deploy/1.0"},
    )
    with urllib.request.urlopen(request, timeout=15, context=context) as response:
        if response.status != 200:
            raise InfraError(f"Public application returned non-200: {path}")
        body = response.read(4 * 1024 * 1024 + 1)
        if len(body) > 4 * 1024 * 1024:
            raise InfraError(f"Public application response is too large: {path}")
        return body, response.headers.get_content_type()


def verify_public_root(body: bytes, release_sha: str) -> None:
    root_body = body.decode(errors="replace")
    required = {
        SITE_MARKER: "Public auth page verification failed",
        BRAND_PUBLIC_MARK: "Public auth page does not use approved brand mark",
        WEB_MANIFEST_PATH: "Public auth page does not expose web manifest",
        release_sha[:12]: "Public auth page asset build does not match release",
    }
    for marker, message in required.items():
        if marker not in root_body:
            raise InfraError(message)
    if "__OMNICIO_VERSION__" in root_body or "__OMNICIO_BUILD__" in root_body:
        raise InfraError("Public auth page contains unresolved release markers")


def verify_public_config(body: bytes) -> None:
    payload = json.loads(body)
    if not isinstance(payload, dict):
        raise InfraError("Public auth config is not an object")

    expected_registration = registration_enabled()
    if payload.get("registration_enabled") is not expected_registration:
        raise InfraError("Public registration mode does not match deployment config")
    expected_mode = "limited_registration" if expected_registration else "closed"
    if payload.get("mode") != expected_mode:
        raise InfraError("Public access mode does not match deployment config")
    if payload.get("registration_max_users") != registration_max_users():
        raise InfraError("Public registration capacity does not match deployment config")
    if payload.get("auth_provider") != "vkid":
        raise InfraError("Public auth provider is not VK ID")

    expected_login = vkid_configuration_ready()
    if payload.get("login_enabled") is not expected_login:
        raise InfraError("Public VK ID readiness does not match deployment config")


def verify_public_assets(context: ssl.SSLContext, release_sha: str) -> None:
    brand, content_type = fetch_public(BRAND_PUBLIC_MARK, context)
    if content_type != "image/png" or not brand:
        raise InfraError("Public approved brand mark verification failed")

    manifest_body, _ = fetch_public(WEB_MANIFEST_PATH, context)
    manifest = json.loads(manifest_body)
    if not isinstance(manifest, dict) or not isinstance(manifest.get("icons"), list):
        raise InfraError("Public web manifest verification failed")

    version_body, _ = fetch_public(VERSION_PUBLIC_PATH, context)
    version = version_body.decode()
    if "window.OMNICIO_RELEASE" not in version:
        raise InfraError("Public application version marker is missing")
    if release_sha[:12] not in version:
        raise InfraError("Public application build does not match release")


def verify_public(release_sha: str) -> None:
    context = ssl.create_default_context()
    try:
        root, _ = fetch_public("/", context)
        verify_public_root(root, release_sha)
        verify_public_assets(context, release_sha)
        config, _ = fetch_public("/api/auth/config", context)
        verify_public_config(config)
        for path, marker in LEGAL_PAGES.items():
            body, _ = fetch_public(path, context)
            rendered = body.decode(errors="replace")
            if marker not in rendered:
                raise InfraError(f"Public legal page verification failed: {path}")
            if "__OMNICIO_OPERATOR_" in rendered:
                raise InfraError(f"Public legal page contains unresolved operator data: {path}")
    except (
        urllib.error.URLError, TimeoutError, ssl.SSLError, json.JSONDecodeError, UnicodeDecodeError,
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
    cluster_name: str,
    vpc_name: str,
    location: str,
    availability_zone: str,
) -> int:
    if not RELEASE_RE.fullmatch(release_sha):
        raise InfraError("Release SHA must be a full lowercase 40-character SHA")

    add_summary("## OmniCIO auth application deploy")
    validate_product_environment()
    validate_legal_documents(repository_root)
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
        location=location,
        availability_zone=availability_zone,
    )
    services = client.get_vpc_services(str(vpc["id"]))
    databases = [
        service
        for service in services
        if str(service.get("name") or "") == cluster_name
    ]
    if not databases:
        add_summary(
            "- Result: pending_database. Managed PostgreSQL is not present in "
            "the approved VPC; no SSH key, application, or Nginx configuration "
            "was changed."
        )
        set_output("status", "pending_database")
        return 0
    if len(databases) != 1:
        raise InfraError("Multiple same-name database services exist in the VPC")

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

        try:
            write_product_environment(ssh, release_sha=release_sha)
            deploy_remote(ssh, release_sha=release_sha)
            for _ in range(6):
                try:
                    verify_public(release_sha)
                    break
                except InfraError:
                    time.sleep(5)
            else:
                raise InfraError("Public verification did not become healthy")

            # The legacy account is removed only after the replacement release
            # is already healthy. The reset itself is one transaction and
            # refuses to touch a database containing more than one user.
            retire_legacy_profile(ssh)
            commit_product_environment(ssh, release_sha=release_sha)
        except InfraError:
            rollback_remote(ssh, release_sha=release_sha)
            raise

    vkid_ready = vkid_configuration_ready()
    login_state = "enabled" if vkid_ready else "fail-closed pending VK ID configuration"
    registration_state = (
        f"open with capacity {registration_max_users()}"
        if registration_enabled()
        else "closed"
    )
    add_summary(
        f"- Result: app_ready. Release {release_sha[:12]} is healthy over HTTPS; "
        f"VK ID login is {login_state}; registration is {registration_state}."
    )
    set_output("status", "app_ready")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-name", required=True)
    parser.add_argument("--server-comment", required=True)
    parser.add_argument("--release-sha", required=True)
    parser.add_argument("--repository-root", required=True)
    parser.add_argument("--cluster-name", required=True)
    parser.add_argument("--vpc-name", required=True)
    parser.add_argument("--location", required=True)
    parser.add_argument("--availability-zone", required=True)
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
            cluster_name=args.cluster_name,
            vpc_name=args.vpc_name,
            location=args.location,
            availability_zone=args.availability_zone,
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
