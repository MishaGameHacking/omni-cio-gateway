#!/usr/bin/env bash
set -euo pipefail

required=(TIMEWEB_CLOUD_TOKEN TELEGRAM_CLIENT_SECRET TELEGRAM_CLIENT_ID GITHUB_RUN_ID RUNNER_TEMP GITHUB_STEP_SUMMARY)
for name in "${required[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "::error::${name} is missing" >&2
    exit 1
  fi
done

TMP_DIR="$(cygpath -u "$RUNNER_TEMP")"
KEY_PATH="$TMP_DIR/analyst-ai-deploy"
STATE_PATH="$TMP_DIR/analyst-ai-timeweb.env"
UPLOAD_ENV="$TMP_DIR/backend.env.upload"

SERVER_ID=""
SSH_KEY_ID=""

if command -v python >/dev/null 2>&1; then
  PYTHON_CMD=(python)
elif command -v py.exe >/dev/null 2>&1; then
  PYTHON_CMD=(py.exe -3)
elif command -v py >/dev/null 2>&1; then
  PYTHON_CMD=(py -3)
else
  echo "::error::Python launcher is not installed on this runner." >&2
  exit 1
fi

cleanup() {
  set +e
  rm -f "$KEY_PATH" "$KEY_PATH.pub" "$UPLOAD_ENV"
  if [[ -f "$STATE_PATH" ]]; then
    source "$STATE_PATH"
  fi
  if [[ -n "${SERVER_ID:-}" && -n "${SSH_KEY_ID:-}" ]]; then
    SERVER_ID="$SERVER_ID" SSH_KEY_ID="$SSH_KEY_ID" "${PYTHON_CMD[@]}" - <<'PY'
import os
import urllib.error
import urllib.request

token = os.environ.get("TIMEWEB_CLOUD_TOKEN", "")
server_id = os.environ.get("SERVER_ID", "")
key_id = os.environ.get("SSH_KEY_ID", "")
headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
for url in (
    f"https://api.timeweb.cloud/api/v1/servers/{server_id}/ssh-keys/{key_id}",
    f"https://api.timeweb.cloud/api/v1/ssh-keys/{key_id}",
):
    try:
        req = urllib.request.Request(url, method="DELETE", headers=headers)
        urllib.request.urlopen(req, timeout=30).read()
    except urllib.error.HTTPError as exc:
        if exc.code not in (404, 409, 423):
            print(f"warning: cleanup failed for {url}: HTTP {exc.code}")
    except Exception as exc:
        print(f"warning: cleanup failed for {url}: {exc}")
PY
  fi
}
trap cleanup EXIT

ssh-keygen -t ed25519 -N "" -f "$KEY_PATH" -C "analyst-ai-ci-${GITHUB_RUN_ID}" >/dev/null
chmod 600 "$KEY_PATH"

SSH_PUBLIC_KEY_PATH="$(cygpath -w "$KEY_PATH.pub")" STATE_PATH="$(cygpath -w "$STATE_PATH")" "${PYTHON_CMD[@]}" - <<'PY'
import json
import os
import re
import time
import urllib.error
import urllib.request

BASE = "https://api.timeweb.cloud/api/v1"
TOKEN = os.environ["TIMEWEB_CLOUD_TOKEN"]
SERVER_NAME = "analyst-ai-backend"
STATUSES = {"on", "off", "installing", "rebooting", "turning_on", "turning_off"}

def request(method, path, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read()
            return {} if not raw else json.loads(raw)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(
            f"Timeweb {method} {path} failed: HTTP {exc.code}: {detail}"
        ) from exc

def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)

def first_numeric_id(payload):
    for item in walk(payload):
        value = item.get("id")
        if isinstance(value, (int, float)):
            return int(value)
    raise RuntimeError(f"Unable to find id in response: {payload}")

with open(os.environ["SSH_PUBLIC_KEY_PATH"], "r", encoding="utf-8") as handle:
    public_key = handle.read().strip()

key_response = request(
    "POST",
    "/ssh-keys",
    {
        "name": f"analyst-ai-ci-{os.environ['GITHUB_RUN_ID']}",
        "body": public_key,
        "is_default": False,
    },
)
key_id = first_numeric_id(key_response)
with open(os.environ["STATE_PATH"], "w", encoding="utf-8") as out:
    out.write(f"SSH_KEY_ID={key_id}\n")

servers_response = request("GET", "/servers")
server = None
for item in walk(servers_response):
    if item.get("name") == SERVER_NAME and isinstance(item.get("id"), (int, float)):
        server = item
        break

if server is None:
    create_response = None
    last_error = None
    for preset_id in (2573, 2447, 4237, 4795, 5943, 2575, 2449, 4239, 4797, 2613, 3795):
        try:
            create_response = request(
                "POST",
                "/servers",
                {
                    "name": SERVER_NAME,
                    "comment": "Analyst AI backend",
                    "os_id": 99,
                    "preset_id": preset_id,
                    "bandwidth": 1000,
                    "is_ddos_guard": False,
                    "is_local_network": False,
                    "ssh_keys_ids": [key_id],
                },
            )
            print(f"Created backend with preset_id={preset_id}")
            break
        except RuntimeError as exc:
            last_error = exc
            message = str(exc)
            if "no_free_node" not in message and "location_not_available" not in message:
                raise
            print(f"preset_id={preset_id} is unavailable; trying next minimal preset")

    if create_response is None:
        presets_payload = request("GET", "/presets/servers")
        presets = []
        seen = set()
        for item in walk(presets_payload):
            preset_id = item.get("id")
            if not isinstance(preset_id, (int, float)):
                continue
            preset_id = int(preset_id)
            if preset_id in seen:
                continue
            seen.add(preset_id)
            summary = {
                key: item.get(key)
                for key in (
                    "id", "description", "description_short", "cpu", "cpu_frequency",
                    "ram", "disk", "disk_type", "price", "location", "type",
                )
                if key in item
            }
            if len(summary) > 1:
                presets.append(summary)
        print("TIMEWEB_PRESET_DIAGNOSTIC=" + json.dumps(presets[:40], ensure_ascii=False))
        raise last_error or RuntimeError("No suitable Timeweb preset is available")
    server_id = first_numeric_id(create_response)
else:
    server_id = int(server["id"])
    request(
        "POST",
        f"/servers/{server_id}/ssh-keys",
        {"ssh_key_ids": [key_id]},
    )

with open(os.environ["STATE_PATH"], "a", encoding="utf-8") as out:
    out.write(f"SERVER_ID={server_id}\n")

status = None
for _ in range(60):
    detail = request("GET", f"/servers/{server_id}")
    values = [
        item.get("status")
        for item in walk(detail)
        if item.get("status") in STATUSES
    ]
    status = values[0] if values else None
    if status == "on":
        break
    time.sleep(10)

if status != "on":
    raise RuntimeError(f"Server did not reach on state, last status={status!r}")

def find_ipv4(*payloads):
    candidates = []
    for payload in payloads:
        for item in walk(payload):
            for value in item.values():
                if not isinstance(value, str):
                    continue
                match = re.search(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)", value)
                if match:
                    candidates.append(match.group(0))
    return candidates[0] if candidates else None

detail = request("GET", f"/servers/{server_id}")
ips_payload = request("GET", f"/servers/{server_id}/ips")
ip = find_ipv4(detail, ips_payload)

if not ip:
    print("Server has no public IPv4; ordering one IPv4 address")
    request(
        "POST",
        f"/servers/{server_id}/ips",
        {"type": "ipv4"},
    )

last_ips_payload = ips_payload
for _ in range(36):
    detail = request("GET", f"/servers/{server_id}")
    ips_payload = request("GET", f"/servers/{server_id}/ips")
    last_ips_payload = ips_payload
    ip = find_ipv4(detail, ips_payload)
    if ip:
        break
    time.sleep(5)

if not ip:
    print("TIMEWEB_IP_DIAGNOSTIC=" + json.dumps(last_ips_payload, ensure_ascii=False))
    raise RuntimeError("No public IPv4 address found after ordering IPv4")

host = f"{ip}.sslip.io"
with open(os.environ["STATE_PATH"], "w", encoding="utf-8") as out:
    out.write(f"SERVER_ID={server_id}\n")
    out.write(f"SSH_KEY_ID={key_id}\n")
    out.write(f"SERVER_IP={ip}\n")
    out.write(f"BACKEND_HOST={host}\n")
    out.write(f"BACKEND_URL=https://{host}\n")
    out.write(f"CALLBACK_URL=https://{host}/auth/telegram/callback\n")

print(f"Timeweb server ready: id={server_id}, host={host}")
PY

source "$STATE_PATH"

for attempt in $(seq 1 36); do
  if ssh -i "$KEY_PATH"     -o BatchMode=yes     -o ConnectTimeout=5     -o StrictHostKeyChecking=accept-new     root@"$SERVER_IP" "echo ready" >/dev/null 2>&1; then
    break
  fi
  if [[ "$attempt" -eq 36 ]]; then
    echo "::error::SSH did not become ready" >&2
    exit 1
  fi
  sleep 10
done

tar -czf "$TMP_DIR/backend.tgz" backend
scp -i "$KEY_PATH"   -o StrictHostKeyChecking=accept-new   "$TMP_DIR/backend.tgz" root@"$SERVER_IP":/tmp/backend.tgz

for value in \
  "$TELEGRAM_CLIENT_ID" \
  "$TELEGRAM_CLIENT_SECRET" \
  "${TIMEWEB_AI_TOKEN:-}" \
  "${TIMEWEB_AI_BASE_URL:-}" \
  "${AI_MODEL_FAST:-}" \
  "${AI_MODEL_STANDARD:-}" \
  "${AI_MODEL_PREMIUM:-}"; do
  if [[ "$value" == *$'\n'* || "$value" == *$'\r'* ]]; then
    echo "::error::Deployment environment values must not contain newlines." >&2
    exit 1
  fi
done

{
  printf 'TELEGRAM_CLIENT_ID=%s\n' "$TELEGRAM_CLIENT_ID"
  printf 'TELEGRAM_CLIENT_SECRET=%s\n' "$TELEGRAM_CLIENT_SECRET"
  printf 'BACKEND_PUBLIC_URL=https://%s\n' "$BACKEND_HOST"
  printf 'APP_DEEP_LINK=analystai://auth\n'
  printf 'DATABASE_PATH=/var/lib/analyst-ai/backend.db\n'

  if [[ -n "${TIMEWEB_AI_TOKEN:-}" ]]; then
    printf 'TIMEWEB_AI_TOKEN=%s\n' "$TIMEWEB_AI_TOKEN"
    printf 'TIMEWEB_AI_BASE_URL=%s\n' "${TIMEWEB_AI_BASE_URL:-https://api.timeweb.ai/v1}"
    printf 'AI_MODEL_FAST=%s\n' "${AI_MODEL_FAST:-}"
    printf 'AI_MODEL_STANDARD=%s\n' "${AI_MODEL_STANDARD:-}"
    printf 'AI_MODEL_PREMIUM=%s\n' "${AI_MODEL_PREMIUM:-}"
  fi
} > "$UPLOAD_ENV"
chmod 600 "$UPLOAD_ENV"

scp -i "$KEY_PATH"   -o StrictHostKeyChecking=accept-new   "$UPLOAD_ENV" root@"$SERVER_IP":/tmp/backend.env.upload

ssh -i "$KEY_PATH"   -o StrictHostKeyChecking=accept-new   root@"$SERVER_IP" "BACKEND_HOST='$BACKEND_HOST' bash -s" <<'REMOTE'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

apt-get update -y
apt-get install -y python3-venv caddy

install -d -m 0755 /opt/analyst-ai
rm -rf /opt/analyst-ai/backend
tar -xzf /tmp/backend.tgz -C /opt/analyst-ai
python3 -m venv /opt/analyst-ai/venv
/opt/analyst-ai/venv/bin/pip install   --disable-pip-version-check   --no-cache-dir   -r /opt/analyst-ai/backend/requirements.txt

install -d -m 0700 /etc/analyst-ai
install -d -o www-data -g www-data -m 0750 /var/lib/analyst-ai

if [[ -f /etc/analyst-ai/backend.env ]]; then
  EXISTING_FERNET="$(sed -n 's/^FERNET_KEY=//p' /etc/analyst-ai/backend.env | head -n 1)"
else
  EXISTING_FERNET=""
fi

if [[ -z "$EXISTING_FERNET" ]]; then
  EXISTING_FERNET="$(
    /opt/analyst-ai/venv/bin/python -c       'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
  )"
fi

cat /tmp/backend.env.upload > /etc/analyst-ai/backend.env
printf 'FERNET_KEY=%s\n' "$EXISTING_FERNET" >> /etc/analyst-ai/backend.env
chmod 0600 /etc/analyst-ai/backend.env
rm -f /tmp/backend.env.upload /tmp/backend.tgz

cat > /etc/systemd/system/analyst-ai-backend.service <<'UNIT'
[Unit]
Description=Analyst AI backend
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/analyst-ai/backend
EnvironmentFile=/etc/analyst-ai/backend.env
ExecStart=/opt/analyst-ai/venv/bin/uvicorn app:app --host 127.0.0.1 --port 8080 --workers 1
Restart=always
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/analyst-ai

[Install]
WantedBy=multi-user.target
UNIT

cat > /etc/caddy/Caddyfile <<EOF
$BACKEND_HOST {
    encode zstd gzip
    reverse_proxy 127.0.0.1:8080
}
EOF

systemctl daemon-reload
systemctl enable --now analyst-ai-backend
systemctl enable --now caddy
systemctl restart analyst-ai-backend
systemctl restart caddy
REMOTE

for attempt in $(seq 1 36); do
  if curl --fail --silent --show-error --max-time 10 "$BACKEND_URL/health" | grep -q '"ok"'; then
    echo "Backend is healthy: $BACKEND_URL"
    break
  fi
  if [[ "$attempt" -eq 36 ]]; then
    echo "::error::Backend HTTPS health check failed" >&2
    exit 1
  fi
  sleep 10
done

AUTH_HEADERS="$TMP_DIR/telegram-auth.headers"
AUTH_STATUS="$(
  curl --silent --show-error     --output /dev/null     --dump-header "$AUTH_HEADERS"     --write-out '%{http_code}'     --max-time 15     "$BACKEND_URL/auth/telegram/start"
)"
if [[ "$AUTH_STATUS" != "302" ]] || ! grep -qi '^location: https://oauth.telegram.org/auth' "$AUTH_HEADERS"; then
  echo "::error::Telegram login start endpoint did not return the expected OAuth redirect" >&2
  exit 1
fi
echo "Telegram login start endpoint is ready."

{
  echo "## Analyst AI backend"
  echo ""
  printf '%s\n' "- Backend: $BACKEND_URL"
  printf '%s\n' "- Telegram callback to allow in BotFather: $CALLBACK_URL"
  if [[ -n "${TIMEWEB_AI_TOKEN:-}" ]]; then
    printf '%s\n' "- Timeweb AI Gateway: configuration delivered to backend"
  else
    printf '%s\n' "- Timeweb AI Gateway: disabled (TIMEWEB_AI_TOKEN is not configured)"
  fi
} >> "$GITHUB_STEP_SUMMARY"

echo "BACKEND_URL=$BACKEND_URL"
echo "CALLBACK_URL=$CALLBACK_URL"
