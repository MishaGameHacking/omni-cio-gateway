"""Read-only production diagnostics for the Moscow Telegram OIDC handoff.

The script verifies the exact existing Timeweb server, attaches a short-lived SSH
key, runs bounded non-secret connectivity/log checks, and always removes the key.
It does not modify the backend, environment, database, firewall, or DNS.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

API_BASE = "https://api.timeweb.cloud/api/v1"
SERVER_ID = "9334503"
EXPECTED_IP = "176.98.178.81"


def request(token: str, method: str, path: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    last: Exception | None = None
    for attempt in range(1, 6):
        try:
            req = urllib.request.Request(API_BASE + path, data=data, method=method, headers=headers)
            with urllib.request.urlopen(req, timeout=45) as response:
                raw = response.read()
            return {} if not raw else json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            last = RuntimeError(f"Timeweb {method} {path}: HTTP {exc.code}: {detail}")
            if exc.code not in {408, 429, 500, 502, 503, 504}:
                raise last from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            last = RuntimeError(f"Timeweb {method} {path}: {type(exc).__name__}")
        if attempt == 5:
            raise last or RuntimeError("Timeweb request failed")
        time.sleep(min(2**attempt, 20))
    raise AssertionError("unreachable")


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def numeric_id(payload: dict) -> int:
    for item in walk(payload):
        value = item.get("id")
        if type(value) is int and value > 0:
            return value
    raise RuntimeError("Timeweb response did not contain a numeric id")


def verify_server(token: str) -> None:
    server = request(token, "GET", f"/servers/{SERVER_ID}")
    ips = request(token, "GET", f"/servers/{SERVER_ID}/ips")
    serialized = json.dumps([server, ips], ensure_ascii=False)
    if not any(marker in serialized.upper() for marker in ("MSK", "MOSCOW", "МОСК")):
        raise RuntimeError("Refusing diagnostics: target server is not verified as Moscow")
    found = set(re.findall(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)", serialized))
    if EXPECTED_IP not in found:
        raise RuntimeError("Refusing diagnostics: expected Moscow IP is not attached")


def command_path(name: str) -> str:
    path = shutil.which(name)
    if path:
        return path
    raise RuntimeError(f"Required command is unavailable: {name}")


def remote_script() -> str:
    return r'''#!/usr/bin/env bash
set -euo pipefail

readonly ENV_FILE="/etc/analyst-ai/backend.env"
readonly UNIT="analyst-ai-backend"
[[ -f "$ENV_FILE" ]] || { echo "DIAG_ENV_FILE=missing"; exit 1; }
systemctl is-active --quiet "$UNIT" || { echo "DIAG_SERVICE=inactive"; exit 1; }
echo "DIAG_SERVICE=active"

# Load values only for local consistency checks. Secret values are never printed.
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a
for required in TELEGRAM_CLIENT_ID TELEGRAM_CLIENT_SECRET BACKEND_PUBLIC_URL FERNET_KEY; do
  if [[ -z "${!required:-}" ]]; then
    echo "DIAG_REQUIRED_ENV_${required}=missing"
    exit 1
  fi
  echo "DIAG_REQUIRED_ENV_${required}=present"
done
printf 'DIAG_BACKEND_PUBLIC_URL=%s\n' "${BACKEND_PUBLIC_URL:-}"
printf 'DIAG_TELEGRAM_REDIRECT_URI=%s\n' "${TELEGRAM_REDIRECT_URI:-${BACKEND_PUBLIC_URL%/}/auth/telegram/callback}"
printf 'DIAG_APP_DEEP_LINK=%s\n' "${APP_DEEP_LINK:-analystai://auth}"
for proxy in HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy; do
  if [[ -n "${!proxy:-}" ]]; then
    echo "DIAG_PROXY_${proxy}=present"
  else
    echo "DIAG_PROXY_${proxy}=absent"
  fi
done

PYTHON_BIN=""
for candidate in /opt/analyst-ai/venv/bin/python /opt/analyst-ai/.venv/bin/python /opt/analyst-ai/venv/bin/python3 /usr/bin/python3; do
  if [[ -x "$candidate" ]]; then PYTHON_BIN="$candidate"; break; fi
done
[[ -n "$PYTHON_BIN" ]] || { echo "DIAG_PYTHON=missing"; exit 1; }
echo "DIAG_PYTHON=present"

"$PYTHON_BIN" - <<'PROBE_PY'
from __future__ import annotations
import json
import socket
import ssl
import urllib.request

import certifi
import httpx

HOST = "oauth.telegram.org"
URLS = (
    "https://oauth.telegram.org/.well-known/openid-configuration",
    "https://oauth.telegram.org/.well-known/jwks.json",
)

try:
    addresses = sorted({item[4][0] for item in socket.getaddrinfo(HOST, 443, type=socket.SOCK_STREAM)})
    print("DIAG_DNS=ok count=" + str(len(addresses)), flush=True)
except Exception as exc:
    print("DIAG_DNS=error type=" + type(exc).__name__, flush=True)

for url in URLS:
    label = "discovery" if url.endswith("openid-configuration") else "jwks"
    try:
        with httpx.Client(
            timeout=httpx.Timeout(15.0, connect=10.0),
            verify=certifi.where(),
            trust_env=False,
            follow_redirects=False,
            headers={"Accept": "application/json", "User-Agent": "Analyst-AI-telegram-diagnostic/1"},
        ) as client:
            response = client.get(url)
        body = response.content
        parsed = response.json() if response.status_code == 200 and len(body) <= 65536 else None
        detail = ""
        if label == "jwks" and isinstance(parsed, dict):
            keys = parsed.get("keys")
            detail = " keys=" + str(len(keys) if isinstance(keys, list) else -1)
        print(
            f"DIAG_HTTPX_{label}=status:{response.status_code} bytes:{len(body)}{detail}",
            flush=True,
        )
    except Exception as exc:
        cause = exc.__cause__
        cause_name = type(cause).__name__ if cause is not None else "none"
        print(
            f"DIAG_HTTPX_{label}=error type:{type(exc).__name__} cause:{cause_name}",
            flush=True,
        )

context = ssl.create_default_context(cafile=certifi.where())
try:
    request = urllib.request.Request(URLS[1], headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=15, context=context) as response:
        body = response.read(65537)
        status = response.status
    parsed = json.loads(body.decode("utf-8"))
    keys = parsed.get("keys") if isinstance(parsed, dict) else None
    print(
        "DIAG_URLLIB_JWKS=status:" + str(status)
        + " bytes:" + str(len(body))
        + " keys:" + str(len(keys) if isinstance(keys, list) else -1),
        flush=True,
    )
except Exception as exc:
    print("DIAG_URLLIB_JWKS=error type:" + type(exc).__name__, flush=True)
PROBE_PY

# Print only bounded authentication-related server diagnostics. No request query,
# authorization code, session token, client secret, or user profile is emitted.
echo "DIAG_JOURNAL_BEGIN"
journalctl -u "$UNIT" --since "90 minutes ago" --no-pager --output=short-iso \
  | grep -E 'Telegram token exchange is unavailable|Telegram signing keys are temporarily unavailable|Telegram token exchange returned HTTP|Telegram ID token is invalid|oauth\.telegram\.org|ConnectError|ConnectTimeout|ReadTimeout|SSLCertVerificationError|CERTIFICATE_VERIFY_FAILED|Temporary failure in name resolution|Name or service not known|Network is unreachable|PyJWK' \
  | tail -n 160 \
  | sed -E 's/(code=)[^ &]+/\1<redacted>/g; s/(state=)[^ &]+/\1<redacted>/g' \
  || true
echo "DIAG_JOURNAL_END"

echo "TELEGRAM_DIAGNOSTIC=complete"
'''


def cleanup_key(token: str, key_id: int | None) -> None:
    if key_id is None:
        return
    for path in (
        f"/servers/{SERVER_ID}/ssh-keys/{key_id}",
        f"/ssh-keys/{key_id}",
    ):
        try:
            request(token, "DELETE", path)
        except Exception as exc:
            print(f"warning: temporary SSH key cleanup failed: {type(exc).__name__}", flush=True)


def main() -> int:
    token = os.environ.get("TIMEWEB_CLOUD_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TIMEWEB_CLOUD_TOKEN is required")
    verify_server(token)

    run_id = os.environ.get("GITHUB_RUN_ID", "local")
    if not re.fullmatch(r"[A-Za-z0-9-]{1,80}", run_id):
        raise RuntimeError("Invalid run identifier")

    ssh = command_path("ssh")
    ssh_keygen = command_path("ssh-keygen")
    key_id: int | None = None
    with tempfile.TemporaryDirectory(prefix="analyst-ai-telegram-diagnostic-") as temporary:
        root = Path(temporary)
        private_key = root / "diagnostic-key"
        known_hosts = root / "known-hosts"
        subprocess.run(
            [
                ssh_keygen,
                "-t",
                "ed25519",
                "-N",
                "",
                "-f",
                str(private_key),
                "-C",
                f"analyst-ai-telegram-diagnostic-{run_id}",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            public_key = private_key.with_suffix(".pub").read_text(encoding="utf-8").strip()
            created = request(
                token,
                "POST",
                "/ssh-keys",
                {
                    "name": f"analyst-ai-telegram-diagnostic-{run_id}",
                    "body": public_key,
                    "is_default": False,
                },
            )
            key_id = numeric_id(created)
            request(token, "POST", f"/servers/{SERVER_ID}/ssh-keys", {"ssh_key_ids": [key_id]})

            options = [
                "-i",
                str(private_key),
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=10",
                "-o",
                "ConnectionAttempts=2",
                "-o",
                "ServerAliveInterval=10",
                "-o",
                "ServerAliveCountMax=3",
                "-o",
                "StrictHostKeyChecking=accept-new",
                "-o",
                f"UserKnownHostsFile={known_hosts}",
            ]
            ready = False
            for _ in range(36):
                probe = subprocess.run(
                    [ssh, *options, f"root@{EXPECTED_IP}", "echo ready"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    timeout=25,
                )
                if probe.returncode == 0:
                    ready = True
                    break
                time.sleep(10)
            if not ready:
                raise RuntimeError("Verified Moscow server SSH did not become ready")

            completed = subprocess.run(
                [ssh, *options, f"root@{EXPECTED_IP}", "bash", "-s"],
                input=remote_script(),
                text=True,
                encoding="utf-8",
                errors="strict",
                check=False,
                timeout=180,
            )
            if completed.returncode != 0:
                raise RuntimeError(f"Remote Telegram diagnostics failed with exit {completed.returncode}")
            return 0
        finally:
            cleanup_key(token, key_id)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(
            f"TELEGRAM_DIAGNOSTIC=failed type={type(error).__name__}",
            file=sys.stderr,
            flush=True,
        )
        raise
