#!/usr/bin/env bash
set -euo pipefail

required=(
  TIMEWEB_CLOUD_TOKEN APK_PATH REPORT_PATH RUNNER_TEMP GITHUB_RUN_ID
  GITHUB_STEP_SUMMARY
)
for name in "${required[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "::error::${name} is required" >&2
    exit 1
  fi
done

readonly SERVER_ID="9334503"
readonly EXPECTED_IP="176.98.178.81"
readonly EXPECTED_HOST="176.98.178.81.sslip.io"
readonly PACKAGE_NAME="ru.omnicio.app.debug"
readonly VERSION_CODE="23"
readonly VERSION_NAME="0.6.0-preview"
readonly APK_SHA256="31a04b49a03e7ac407092d095a6fbf5a736618850a9ea0765a22ab9e814a4b74"
readonly APK_BYTES="4100464"
readonly CERTIFICATE_SHA256="bbce9534fd4cfee8f3bdcaf51a31cce384a4f303f090c8cae9ec558227d59eb1"
readonly MIN_SDK="33"
readonly PUBLISHED_AT="1792031738"
readonly RELEASE_FILENAME="Analyst-AI-${VERSION_CODE}-${APK_SHA256}.apk"

if command -v cygpath >/dev/null 2>&1; then
  TMP_DIR="$(cygpath -u "$RUNNER_TEMP")"
  APK_UNIX="$(cygpath -u "$APK_PATH")"
  REPORT_UNIX="$(cygpath -u "$REPORT_PATH")"
else
  TMP_DIR="$RUNNER_TEMP"
  APK_UNIX="$APK_PATH"
  REPORT_UNIX="$REPORT_PATH"
fi
readonly TMP_DIR APK_UNIX REPORT_UNIX
readonly KEY_PATH="$TMP_DIR/analyst-ai-update-channel-${GITHUB_RUN_ID}"
readonly STATE_PATH="$TMP_DIR/analyst-ai-update-channel-${GITHUB_RUN_ID}.env"
readonly KNOWN_HOSTS="$TMP_DIR/analyst-ai-update-channel-${GITHUB_RUN_ID}.known-hosts"
readonly BACKEND_ARCHIVE="$TMP_DIR/analyst-ai-backend-${GITHUB_RUN_ID}.tgz"
readonly MANIFEST_PATH="$TMP_DIR/analyst-ai-current-${GITHUB_RUN_ID}.json"
readonly REMOTE_SCRIPT="$TMP_DIR/analyst-ai-update-channel-${GITHUB_RUN_ID}.remote.sh"
readonly READBACK_APK="$TMP_DIR/analyst-ai-update-channel-${GITHUB_RUN_ID}.readback.apk"
readonly READBACK_POLICY="$TMP_DIR/analyst-ai-update-channel-${GITHUB_RUN_ID}.policy.json"

if command -v python >/dev/null 2>&1; then
  PYTHON_CMD=(python)
elif command -v py.exe >/dev/null 2>&1; then
  PYTHON_CMD=(py.exe -3)
elif command -v py >/dev/null 2>&1; then
  PYTHON_CMD=(py -3)
else
  echo "::error::Python 3 is required" >&2
  exit 1
fi

SSH_KEY_ID=""
cleanup() {
  set +e
  rm -f \
    "$KEY_PATH" "$KEY_PATH.pub" "$STATE_PATH" "$KNOWN_HOSTS" \
    "$BACKEND_ARCHIVE" "$MANIFEST_PATH" "$REMOTE_SCRIPT" \
    "$READBACK_APK" "$READBACK_POLICY"
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
        urllib.request.urlopen(
            urllib.request.Request(url, method="DELETE", headers=headers), timeout=30
        ).read()
    except urllib.error.HTTPError as exc:
        if exc.code not in (404, 409, 423):
            print(f"warning: temporary SSH key cleanup HTTP {exc.code}")
    except Exception as exc:
        print(f"warning: temporary SSH key cleanup failed: {type(exc).__name__}")
PY
  fi
}
trap cleanup EXIT

# Validate the exact previously published, emulator-tested APK and create the
# canonical server manifest. Never trust a filename or mutable build output.
APK_PATH="$APK_UNIX" REPORT_PATH="$REPORT_UNIX" MANIFEST_PATH="$MANIFEST_PATH" \
PACKAGE_NAME="$PACKAGE_NAME" VERSION_CODE="$VERSION_CODE" VERSION_NAME="$VERSION_NAME" \
APK_SHA256="$APK_SHA256" APK_BYTES="$APK_BYTES" CERTIFICATE_SHA256="$CERTIFICATE_SHA256" \
MIN_SDK="$MIN_SDK" PUBLISHED_AT="$PUBLISHED_AT" "${PYTHON_CMD[@]}" - <<'PY'
import hashlib
import json
import os
from pathlib import Path
import tempfile

apk = Path(os.environ["APK_PATH"])
report_path = Path(os.environ["REPORT_PATH"])
manifest_path = Path(os.environ["MANIFEST_PATH"])
expected = {
    "package": os.environ["PACKAGE_NAME"],
    "version_code": int(os.environ["VERSION_CODE"]),
    "version_name": os.environ["VERSION_NAME"],
    "sha256": os.environ["APK_SHA256"],
    "bytes": int(os.environ["APK_BYTES"]),
    "certificate_sha256": os.environ["CERTIFICATE_SHA256"],
    "min_sdk": int(os.environ["MIN_SDK"]),
}
if not apk.is_file() or apk.is_symlink():
    raise SystemExit("APK is missing or is a symbolic link")
if apk.stat().st_size != expected["bytes"]:
    raise SystemExit("APK size differs from the verified release")
digest = hashlib.sha256(apk.read_bytes()).hexdigest()
if digest != expected["sha256"]:
    raise SystemExit("APK digest differs from the verified release")
raw = report_path.read_bytes()
if len(raw) > 16_384:
    raise SystemExit("verification report is too large")
report = json.loads(raw.decode("utf-8"))
for key, value in expected.items():
    if report.get(key) != value:
        raise SystemExit(f"verification report mismatch: {key}")
if report.get("debuggable") is not False or report.get("test_only") is not False:
    raise SystemExit("distribution APK must be non-debuggable and non-test-only")
if report.get("signature_v2") is not True:
    raise SystemExit("APK signature verification is missing")
if report.get("device_install_test") != "passed_on_emulators_not_a_physical_phone":
    raise SystemExit("installation evidence is missing")
manifest = {
    "schema_version": 1,
    "package_name": expected["package"],
    "version_code": expected["version_code"],
    "version_name": expected["version_name"],
    "apk_sha256": expected["sha256"],
    "apk_bytes": expected["bytes"],
    "certificate_sha256": expected["certificate_sha256"],
    "min_sdk": expected["min_sdk"],
    "published_at": int(os.environ["PUBLISHED_AT"]),
    "notes": "Проверенная версия Analyst AI 0.6.0-preview. Исправлен серверный канал проверки версии.",
}
text = json.dumps(manifest, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"
manifest_path.parent.mkdir(parents=True, exist_ok=True)
with tempfile.NamedTemporaryFile(
    mode="w", encoding="utf-8", dir=manifest_path.parent, delete=False
) as handle:
    staged = Path(handle.name)
    handle.write(text)
    handle.flush()
    os.fsync(handle.fileno())
os.replace(staged, manifest_path)
print("Verified immutable APK and canonical release manifest")
PY

if [[ ! -d backend ]]; then
  echo "::error::Run this script from the repository root" >&2
  exit 1
fi
tar -czf "$BACKEND_ARCHIVE" backend

ssh-keygen -t ed25519 -N "" -f "$KEY_PATH" -C "analyst-ai-update-channel-${GITHUB_RUN_ID}" >/dev/null
chmod 600 "$KEY_PATH"

if command -v cygpath >/dev/null 2>&1; then
  SSH_PUBLIC_KEY_PATH="$(cygpath -w "$KEY_PATH.pub")"
  STATE_PATH_FOR_PY="$(cygpath -w "$STATE_PATH")"
else
  SSH_PUBLIC_KEY_PATH="$KEY_PATH.pub"
  STATE_PATH_FOR_PY="$STATE_PATH"
fi

SSH_PUBLIC_KEY_PATH="$SSH_PUBLIC_KEY_PATH" STATE_PATH="$STATE_PATH_FOR_PY" \
SERVER_ID="$SERVER_ID" EXPECTED_IP="$EXPECTED_IP" "${PYTHON_CMD[@]}" - <<'PY'
import json
import os
import re
import time
import urllib.error
import urllib.request

BASE = "https://api.timeweb.cloud/api/v1"
TOKEN = os.environ["TIMEWEB_CLOUD_TOKEN"]
SERVER_ID = os.environ["SERVER_ID"]
EXPECTED_IP = os.environ["EXPECTED_IP"]


def request(method, path, body=None):
    data = None if body is None else json.dumps(body).encode()
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    last = None
    for attempt in range(1, 6):
        try:
            req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
            with urllib.request.urlopen(req, timeout=45) as response:
                raw = response.read()
                return {} if not raw else json.loads(raw)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:500]
            last = RuntimeError(f"Timeweb {method} {path}: HTTP {exc.code}: {detail}")
            if exc.code not in {408, 429, 500, 502, 503, 504}:
                raise last from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            last = RuntimeError(f"Timeweb {method} {path}: {type(exc).__name__}")
        if attempt == 5:
            raise last or RuntimeError("Timeweb request failed")
        time.sleep(min(2 ** attempt, 20))
    raise AssertionError("unreachable")


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
        if type(value) is int and value > 0:
            return value
    raise RuntimeError("Timeweb response did not contain a numeric id")

server = request("GET", f"/servers/{SERVER_ID}")
serialized = json.dumps(server, ensure_ascii=False)
if not any(marker in serialized.upper() for marker in ("MSK", "MOSCOW", "МОСК")):
    raise RuntimeError("Refusing repair: target server is not verified as Moscow")
ips = request("GET", f"/servers/{SERVER_ID}/ips")
found = set(re.findall(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)", json.dumps([server, ips])))
if EXPECTED_IP not in found:
    raise RuntimeError(f"Refusing repair: expected IP {EXPECTED_IP} is not attached")

with open(os.environ["SSH_PUBLIC_KEY_PATH"], encoding="utf-8") as handle:
    public_key = handle.read().strip()
created = request("POST", "/ssh-keys", {
    "name": f"analyst-ai-update-channel-{os.environ['GITHUB_RUN_ID']}",
    "body": public_key,
    "is_default": False,
})
key_id = numeric_id(created)
request("POST", f"/servers/{SERVER_ID}/ssh-keys", {"ssh_key_ids": [key_id]})
with open(os.environ["STATE_PATH"], "w", encoding="utf-8") as handle:
    handle.write(f"SSH_KEY_ID={key_id}\n")
print(f"Temporary key attached to verified Moscow server {SERVER_ID}")
PY

# The state file is generated from a validated integer only.
# shellcheck disable=SC1090
source "$STATE_PATH"
readonly SSH_KEY_ID

SSH_OPTS=(
  -i "$KEY_PATH"
  -o BatchMode=yes
  -o ConnectTimeout=10
  -o ConnectionAttempts=3
  -o ServerAliveInterval=10
  -o ServerAliveCountMax=3
  -o StrictHostKeyChecking=accept-new
  -o UserKnownHostsFile="$KNOWN_HOSTS"
)

retry_command() {
  local attempts="$1"
  local delay="$2"
  shift 2
  local current=1
  while true; do
    if "$@"; then
      return 0
    fi
    if [[ "$current" -ge "$attempts" ]]; then
      echo "::error::Command failed after $attempts attempts: $*" >&2
      return 1
    fi
    echo "Transient command failure; retry $current/$attempts in ${delay}s" >&2
    sleep "$delay"
    current=$((current + 1))
    if [[ "$delay" -lt 30 ]]; then delay=$((delay + 5)); fi
  done
}

for attempt in $(seq 1 60); do
  if ssh "${SSH_OPTS[@]}" root@"$EXPECTED_IP" "echo ready" >/dev/null 2>&1; then
    break
  fi
  if [[ "$attempt" -eq 60 ]]; then
    echo "::error::Verified Moscow server SSH did not become ready" >&2
    exit 1
  fi
  sleep 10
done

retry_command 8 10 scp "${SSH_OPTS[@]}" "$BACKEND_ARCHIVE" root@"$EXPECTED_IP":/tmp/analyst-ai-backend.tgz
retry_command 8 10 scp "${SSH_OPTS[@]}" "$APK_UNIX" root@"$EXPECTED_IP":/tmp/analyst-ai-release.apk
retry_command 8 10 scp "${SSH_OPTS[@]}" "$MANIFEST_PATH" root@"$EXPECTED_IP":/tmp/analyst-ai-current.json

cat > "$REMOTE_SCRIPT" <<'REMOTE'
#!/usr/bin/env bash
set -euo pipefail

: "${RUN_ID:?}"
: "${PACKAGE_NAME:?}"
: "${RELEASE_FILENAME:?}"
: "${EXPECTED_APK_SHA:?}"
: "${EXPECTED_APK_BYTES:?}"
: "${EXPECTED_MANIFEST_SHA:?}"

readonly BACKEND_ROOT="/opt/analyst-ai"
readonly BACKEND_PATH="$BACKEND_ROOT/backend"
readonly STAGING_ROOT="$BACKEND_ROOT/backend-next-$RUN_ID"
readonly BACKUP_ROOT="$BACKEND_ROOT/rollback/update-channel-$RUN_ID"
readonly ENV_FILE="/etc/analyst-ai/backend.env"
readonly RELEASE_ROOT="/var/lib/analyst-ai/releases/$PACKAGE_NAME"
readonly RELEASE_APK="$RELEASE_ROOT/$RELEASE_FILENAME"
readonly RETAINED_MANIFEST="$RELEASE_ROOT/${RELEASE_FILENAME%.apk}.json"

rollback() {
  set +e
  echo "Rolling back backend and environment after failed update-channel repair" >&2
  if [[ -d "$BACKUP_ROOT/backend" ]]; then
    rm -rf "$BACKEND_PATH"
    cp -a "$BACKUP_ROOT/backend" "$BACKEND_PATH"
  fi
  if [[ -f "$BACKUP_ROOT/backend.env" ]]; then
    cp -a "$BACKUP_ROOT/backend.env" "$ENV_FILE"
  fi
  systemctl daemon-reload
  systemctl restart analyst-ai-backend
}
finish() {
  local rc=$?
  trap - EXIT
  if [[ "$rc" -ne 0 ]]; then rollback; fi
  exit "$rc"
}
trap finish EXIT

[[ -d "$BACKEND_PATH" ]] || { echo "Current backend directory missing" >&2; exit 1; }
[[ -f "$ENV_FILE" ]] || { echo "Current backend environment missing" >&2; exit 1; }
systemctl cat analyst-ai-backend >/dev/null

printf '%s  %s\n' "$EXPECTED_APK_SHA" /tmp/analyst-ai-release.apk | sha256sum -c -
[[ "$(stat -c %s /tmp/analyst-ai-release.apk)" == "$EXPECTED_APK_BYTES" ]]
printf '%s  %s\n' "$EXPECTED_MANIFEST_SHA" /tmp/analyst-ai-current.json | sha256sum -c -

install -d -m 0700 "$BACKUP_ROOT"
cp -a "$BACKEND_PATH" "$BACKUP_ROOT/backend"
cp -a "$ENV_FILE" "$BACKUP_ROOT/backend.env"

rm -rf "$STAGING_ROOT"
install -d -m 0755 "$STAGING_ROOT"
tar -xzf /tmp/analyst-ai-backend.tgz -C "$STAGING_ROOT"
[[ -f "$STAGING_ROOT/backend/app.py" ]]
/opt/analyst-ai/venv/bin/python -m compileall -q "$STAGING_ROOT/backend"
rm -rf "$BACKEND_PATH"
mv "$STAGING_ROOT/backend" "$BACKEND_PATH"
rmdir "$STAGING_ROOT"
chown -R root:root "$BACKEND_PATH"
find "$BACKEND_PATH" -type d -exec chmod 0755 {} +
find "$BACKEND_PATH" -type f -exec chmod 0644 {} +

python3 - "$ENV_FILE" <<'PY'
import os
from pathlib import Path
import stat
import tempfile
import sys

path = Path(sys.argv[1])
lines = path.read_text(encoding="utf-8").splitlines()
keys = {"ANDROID_RELEASE_DIR", "ANDROID_UPDATES_ENABLED"}
kept = [line for line in lines if line.split("=", 1)[0] not in keys]
kept.extend([
    "ANDROID_RELEASE_DIR=/var/lib/analyst-ai/releases",
    # Serve a verified policy now, but do not yet reject legacy authenticated
    # clients. Enforcement can be activated only after the owner verifies 0.6.0.
    "ANDROID_UPDATES_ENABLED=false",
])
text = "\n".join(kept) + "\n"
with tempfile.NamedTemporaryFile(
    mode="w", encoding="utf-8", dir=path.parent, delete=False
) as handle:
    staged = Path(handle.name)
    handle.write(text)
    handle.flush()
    os.fsync(handle.fileno())
os.chmod(staged, stat.S_IRUSR | stat.S_IWUSR)
os.replace(staged, path)
PY

install -d -o www-data -g www-data -m 0750 "$RELEASE_ROOT"
install -o www-data -g www-data -m 0640 \
  /tmp/analyst-ai-release.apk "$RELEASE_APK.next"
mv -f "$RELEASE_APK.next" "$RELEASE_APK"
install -o www-data -g www-data -m 0640 \
  /tmp/analyst-ai-current.json "$RETAINED_MANIFEST.next"
mv -f "$RETAINED_MANIFEST.next" "$RETAINED_MANIFEST"
install -o www-data -g www-data -m 0640 \
  /tmp/analyst-ai-current.json "$RELEASE_ROOT/current.json.next"
sync
mv -f "$RELEASE_ROOT/current.json.next" "$RELEASE_ROOT/current.json"

systemctl daemon-reload
systemctl restart analyst-ai-backend
for attempt in $(seq 1 30); do
  if curl --fail --silent --show-error --max-time 5 \
      http://127.0.0.1:8080/health | grep -q '"ok"'; then
    break
  fi
  if [[ "$attempt" -eq 30 ]]; then
    journalctl -u analyst-ai-backend -n 80 --no-pager >&2 || true
    exit 1
  fi
  sleep 1
done

curl --fail --silent --show-error --max-time 10 \
  "http://127.0.0.1:8080/client/update-policy?package_name=$PACKAGE_NAME" \
  -o /tmp/analyst-ai-policy-readback.json
python3 - /tmp/analyst-ai-policy-readback.json "$PACKAGE_NAME" "$RELEASE_FILENAME" <<'PY'
import json
from pathlib import Path
import sys

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
package = sys.argv[2]
filename = sys.argv[3]
assert payload["schema_version"] == 1
assert payload["package_name"] == package
assert payload["version_code"] == 23
assert payload["minimum_version_code"] == 23
assert payload["version_name"] == "0.6.0-preview"
assert payload["apk_sha256"] == "31a04b49a03e7ac407092d095a6fbf5a736618850a9ea0765a22ab9e814a4b74"
assert payload["apk_bytes"] == 4100464
assert payload["apk_path"] == "/client/apk/" + filename
PY
curl --fail --silent --show-error --max-time 30 \
  "http://127.0.0.1:8080/client/apk/$RELEASE_FILENAME?package_name=$PACKAGE_NAME" \
  -o /tmp/analyst-ai-apk-readback.apk
printf '%s  %s\n' "$EXPECTED_APK_SHA" /tmp/analyst-ai-apk-readback.apk | sha256sum -c -
[[ "$(stat -c %s /tmp/analyst-ai-apk-readback.apk)" == "$EXPECTED_APK_BYTES" ]]

rm -f \
  /tmp/analyst-ai-backend.tgz /tmp/analyst-ai-release.apk \
  /tmp/analyst-ai-current.json /tmp/analyst-ai-policy-readback.json \
  /tmp/analyst-ai-apk-readback.apk
trap - EXIT
echo "Moscow backend and canonical update channel repaired successfully"
REMOTE
chmod 0700 "$REMOTE_SCRIPT"
retry_command 8 10 scp "${SSH_OPTS[@]}" "$REMOTE_SCRIPT" root@"$EXPECTED_IP":/tmp/analyst-ai-update-channel-repair.sh

MANIFEST_SHA="$(sha256sum "$MANIFEST_PATH" | awk '{print $1}')"
retry_command 8 10 ssh "${SSH_OPTS[@]}" root@"$EXPECTED_IP" \
  "RUN_ID='$GITHUB_RUN_ID' PACKAGE_NAME='$PACKAGE_NAME' RELEASE_FILENAME='$RELEASE_FILENAME' EXPECTED_APK_SHA='$APK_SHA256' EXPECTED_APK_BYTES='$APK_BYTES' EXPECTED_MANIFEST_SHA='$MANIFEST_SHA' bash /tmp/analyst-ai-update-channel-repair.sh"

# Verify through the same public HTTPS hostname used by the Android APK.
curl --fail --silent --show-error --max-time 15 \
  "https://$EXPECTED_HOST/health" | grep -q '"ok"'
curl --fail --silent --show-error --max-time 15 \
  "https://$EXPECTED_HOST/client/update-policy?package_name=$PACKAGE_NAME" \
  -o "$READBACK_POLICY"
POLICY_PATH="$READBACK_POLICY" PACKAGE_NAME="$PACKAGE_NAME" RELEASE_FILENAME="$RELEASE_FILENAME" \
"${PYTHON_CMD[@]}" - <<'PY'
import json
import os
from pathlib import Path

payload = json.loads(Path(os.environ["POLICY_PATH"]).read_text(encoding="utf-8"))
assert payload["schema_version"] == 1
assert payload["package_name"] == os.environ["PACKAGE_NAME"]
assert payload["version_code"] == 23
assert payload["minimum_version_code"] == 23
assert payload["version_name"] == "0.6.0-preview"
assert payload["apk_sha256"] == "31a04b49a03e7ac407092d095a6fbf5a736618850a9ea0765a22ab9e814a4b74"
assert payload["apk_bytes"] == 4100464
assert payload["apk_path"] == "/client/apk/" + os.environ["RELEASE_FILENAME"]
PY
curl --fail --silent --show-error --max-time 60 \
  "https://$EXPECTED_HOST/client/apk/$RELEASE_FILENAME?package_name=$PACKAGE_NAME" \
  -o "$READBACK_APK"
printf '%s  %s\n' "$APK_SHA256" "$READBACK_APK" | sha256sum -c -
[[ "$(wc -c < "$READBACK_APK" | tr -d '[:space:]')" == "$APK_BYTES" ]]

{
  echo "## Moscow update channel repaired"
  echo
  echo "- Exact server: $SERVER_ID / $EXPECTED_IP / Moscow"
  echo "- Public policy: https://$EXPECTED_HOST/client/update-policy?package_name=$PACKAGE_NAME"
  echo "- Current version: $VERSION_NAME (code $VERSION_CODE)"
  echo "- APK SHA-256: $APK_SHA256"
  echo "- Backend deployment: updated in place; database and existing secrets preserved"
  echo "- Mandatory enforcement: remains disabled until physical-device verification"
} >> "$GITHUB_STEP_SUMMARY"

echo "UPDATE_CHANNEL_REPAIR=success"
