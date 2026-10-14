#!/usr/bin/env bash
set -euo pipefail

for name in TIMEWEB_CLOUD_TOKEN APK_PATH MANIFEST_PATH HELP_PATH RUNNER_TEMP GITHUB_RUN_ID; do
  if [[ -z "${!name:-}" ]]; then
    echo "::error::${name} is required" >&2
    exit 1
  fi
done

SERVER_ID="9334503"
EXPECTED_IP="176.98.178.81"
EXPECTED_HOST="176.98.178.81.sslip.io"
TMP_DIR="$(cygpath -u "$RUNNER_TEMP")"
KEY_PATH="$TMP_DIR/analyst-ai-release-key"
STATE_PATH="$TMP_DIR/analyst-ai-release-state.env"
APK_UNIX="$(cygpath -u "$APK_PATH")"
MANIFEST_UNIX="$(cygpath -u "$MANIFEST_PATH")"
HELP_UNIX="$(cygpath -u "$HELP_PATH")"

if command -v python >/dev/null 2>&1; then
  PYTHON_CMD=(python)
elif command -v py.exe >/dev/null 2>&1; then
  PYTHON_CMD=(py.exe -3)
else
  PYTHON_CMD=(py -3)
fi

SSH_KEY_ID=""
cleanup() {
  set +e
  rm -f "$KEY_PATH" "$KEY_PATH.pub"
  if [[ -f "$STATE_PATH" ]]; then
    source "$STATE_PATH"
  fi
  if [[ -n "${SSH_KEY_ID:-}" ]]; then
    SERVER_ID="$SERVER_ID" SSH_KEY_ID="$SSH_KEY_ID" "${PYTHON_CMD[@]}" - <<'PY'
import os
import urllib.error
import urllib.request

token = os.environ["TIMEWEB_CLOUD_TOKEN"]
server = os.environ["SERVER_ID"]
key = os.environ["SSH_KEY_ID"]
headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
for url in (
    f"https://api.timeweb.cloud/api/v1/servers/{server}/ssh-keys/{key}",
    f"https://api.timeweb.cloud/api/v1/ssh-keys/{key}",
):
    try:
        urllib.request.urlopen(urllib.request.Request(url, method="DELETE", headers=headers), timeout=30).read()
    except urllib.error.HTTPError as exc:
        if exc.code not in (404, 409, 423):
            print(f"warning: temporary SSH key cleanup HTTP {exc.code}")
    except Exception as exc:
        print(f"warning: temporary SSH key cleanup failed: {type(exc).__name__}")
PY
  fi
}
trap cleanup EXIT

ssh-keygen -t ed25519 -N "" -f "$KEY_PATH" -C "analyst-ai-release-${GITHUB_RUN_ID}" >/dev/null
chmod 600 "$KEY_PATH"

SSH_PUBLIC_KEY_PATH="$(cygpath -w "$KEY_PATH.pub")" STATE_PATH="$(cygpath -w "$STATE_PATH")" \
SERVER_ID="$SERVER_ID" EXPECTED_IP="$EXPECTED_IP" "${PYTHON_CMD[@]}" - <<'PY'
import json
import os
import re
import urllib.error
import urllib.request

BASE = "https://api.timeweb.cloud/api/v1"
TOKEN = os.environ["TIMEWEB_CLOUD_TOKEN"]
SERVER_ID = os.environ["SERVER_ID"]
EXPECTED_IP = os.environ["EXPECTED_IP"]


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
        detail = exc.read().decode(errors="replace")[:500]
        raise RuntimeError(f"Timeweb {method} {path}: HTTP {exc.code}: {detail}") from exc


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def numeric_id(payload):
    for item in walk(payload):
        value = item.get("id")
        if isinstance(value, (int, float)):
            return int(value)
    raise RuntimeError("Timeweb response did not contain an id")

server = request("GET", f"/servers/{SERVER_ID}")
serialized = json.dumps(server, ensure_ascii=False)
if "MSK" not in serialized.upper() and "MOSCOW" not in serialized.upper() and "МОСК" not in serialized.upper():
    raise RuntimeError("Refusing to publish: server is not verified as Moscow")
ips = request("GET", f"/servers/{SERVER_ID}/ips")
found = set(re.findall(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)", json.dumps([server, ips])))
if EXPECTED_IP not in found:
    raise RuntimeError(f"Refusing to publish: expected IP {EXPECTED_IP} not attached")

with open(os.environ["SSH_PUBLIC_KEY_PATH"], encoding="utf-8") as handle:
    public_key = handle.read().strip()
created = request("POST", "/ssh-keys", {
    "name": f"analyst-ai-release-{os.environ['GITHUB_RUN_ID']}",
    "body": public_key,
    "is_default": False,
})
key_id = numeric_id(created)
request("POST", f"/servers/{SERVER_ID}/ssh-keys", {"ssh_key_ids": [key_id]})
with open(os.environ["STATE_PATH"], "w", encoding="utf-8") as handle:
    handle.write(f"SSH_KEY_ID={key_id}\n")
print(f"Temporary SSH key {key_id} attached to verified Moscow server {SERVER_ID}")
PY

source "$STATE_PATH"

for attempt in $(seq 1 36); do
  if ssh -i "$KEY_PATH" -o BatchMode=yes -o ConnectTimeout=5 \
      -o StrictHostKeyChecking=accept-new root@"$EXPECTED_IP" "echo ready" >/dev/null 2>&1; then
    break
  fi
  if [[ "$attempt" -eq 36 ]]; then
    echo "::error::Moscow server SSH did not become ready" >&2
    exit 1
  fi
  sleep 5
done

MANIFEST_SHA="$(sha256sum "$MANIFEST_UNIX" | awk '{print $1}')"
APK_SHA="$(sha256sum "$APK_UNIX" | awk '{print $1}')"
VERSION_CODE="$("${PYTHON_CMD[@]}" -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["version_code"])' "$(cygpath -w "$MANIFEST_UNIX")")"
MANIFEST_APK_SHA="$("${PYTHON_CMD[@]}" -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["sha256"])' "$(cygpath -w "$MANIFEST_UNIX")")"
if [[ "$APK_SHA" != "$MANIFEST_APK_SHA" ]]; then
  echo "::error::Manifest APK hash does not match artifact" >&2
  exit 1
fi

scp -i "$KEY_PATH" -o StrictHostKeyChecking=accept-new \
  "$APK_UNIX" root@"$EXPECTED_IP":/tmp/analyst-ai-release.apk
scp -i "$KEY_PATH" -o StrictHostKeyChecking=accept-new \
  "$MANIFEST_UNIX" root@"$EXPECTED_IP":/tmp/analyst-ai-current.json
scp -i "$KEY_PATH" -o StrictHostKeyChecking=accept-new \
  "$HELP_UNIX" root@"$EXPECTED_IP":/tmp/analyst-ai-update-help.html

ssh -i "$KEY_PATH" -o StrictHostKeyChecking=accept-new root@"$EXPECTED_IP" \
  "EXPECTED_APK_SHA='$APK_SHA' EXPECTED_MANIFEST_SHA='$MANIFEST_SHA' VERSION_CODE='$VERSION_CODE' HOST='$EXPECTED_HOST' bash -s" <<'REMOTE'
set -euo pipefail
printf '%s  %s\n' "$EXPECTED_APK_SHA" /tmp/analyst-ai-release.apk | sha256sum -c -
printf '%s  %s\n' "$EXPECTED_MANIFEST_SHA" /tmp/analyst-ai-current.json | sha256sum -c -

install -d -m 0755 "/var/lib/analyst-ai/releases/$VERSION_CODE"
install -m 0644 /tmp/analyst-ai-release.apk "/var/lib/analyst-ai/releases/$VERSION_CODE/$EXPECTED_APK_SHA.apk"
install -m 0644 /tmp/analyst-ai-update-help.html /var/lib/analyst-ai/releases/help.html
install -m 0644 /tmp/analyst-ai-current.json /var/lib/analyst-ai/releases/current.json.next
sync
mv -f /var/lib/analyst-ai/releases/current.json.next /var/lib/analyst-ai/releases/current.json
rm -f /tmp/analyst-ai-release.apk /tmp/analyst-ai-current.json /tmp/analyst-ai-update-help.html

cp -a /etc/caddy/Caddyfile "/etc/caddy/Caddyfile.before-release-${VERSION_CODE}"
cat > /etc/caddy/Caddyfile <<EOF_CADDY
$HOST {
    encode zstd gzip
    route {
        @release_manifest path /releases/current.json /releases/help.html
        header @release_manifest Cache-Control "no-store"
        header @release_manifest X-Content-Type-Options "nosniff"

        @release_apk path_regexp release_apk ^/releases/[0-9]+/[0-9a-f]{64}\\.apk$
        header @release_apk Cache-Control "public, max-age=31536000, immutable"
        header @release_apk X-Content-Type-Options "nosniff"

        handle /releases/* {
            root * /var/lib/analyst-ai
            file_server
        }

        handle {
            reverse_proxy 127.0.0.1:8080
        }
    }
}
EOF_CADDY
if ! caddy validate --config /etc/caddy/Caddyfile; then
  cp -a "/etc/caddy/Caddyfile.before-release-${VERSION_CODE}" /etc/caddy/Caddyfile
  exit 1
fi
systemctl reload caddy
REMOTE

for attempt in $(seq 1 24); do
  if curl --fail --silent --show-error --max-time 10 \
      "https://$EXPECTED_HOST/releases/current.json" -o "$TMP_DIR/current-readback.json"; then
    break
  fi
  if [[ "$attempt" -eq 24 ]]; then
    echo "::error::Release manifest did not become reachable" >&2
    exit 1
  fi
  sleep 5
done

READBACK_SHA="$(sha256sum "$TMP_DIR/current-readback.json" | awk '{print $1}')"
if [[ "$READBACK_SHA" != "$MANIFEST_SHA" ]]; then
  echo "::error::Published manifest read-back mismatch" >&2
  exit 1
fi
curl --fail --silent --show-error --max-time 20 --head \
  "https://$EXPECTED_HOST/releases/$VERSION_CODE/$APK_SHA.apk" >/dev/null

echo "MOSCOW_RELEASE_URL=https://$EXPECTED_HOST/releases/$VERSION_CODE/$APK_SHA.apk"
echo "MOSCOW_MANIFEST_URL=https://$EXPECTED_HOST/releases/current.json"
