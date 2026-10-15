#!/usr/bin/env bash
set -euo pipefail

MODE="deploy"
if [[ "${1:-}" == "--rollback-after-public-check" ]]; then
  MODE="rollback"
  shift
fi
[[ "$#" -ge 1 ]] || { echo "Deployment run id is required" >&2; exit 1; }
RUN_ID="$1"
shift
if [[ ! "$RUN_ID" =~ ^[A-Za-z0-9-]{1,80}$ ]]; then
  echo "Invalid deployment run id" >&2
  exit 1
fi
if [[ "$MODE" == "deploy" ]]; then
  [[ "$#" -eq 3 ]] || { echo "Deployment digests are required" >&2; exit 1; }
  EXPECTED_ARCHIVE_SHA="$1"
  EXPECTED_JWKS_SHA="$2"
  EXPECTED_REQUIREMENTS_SHA="$3"
  for digest in "$EXPECTED_ARCHIVE_SHA" "$EXPECTED_JWKS_SHA" "$EXPECTED_REQUIREMENTS_SHA"; do
    [[ "$digest" =~ ^[0-9a-f]{64}$ ]] || { echo "Invalid deployment digest" >&2; exit 1; }
  done
else
  [[ "$#" -eq 0 ]] || { echo "Rollback accepts only the run id" >&2; exit 1; }
  EXPECTED_ARCHIVE_SHA=""
  EXPECTED_JWKS_SHA=""
  EXPECTED_REQUIREMENTS_SHA=""
fi
readonly MODE RUN_ID EXPECTED_ARCHIVE_SHA EXPECTED_JWKS_SHA EXPECTED_REQUIREMENTS_SHA
readonly UNIT_NAME="analyst-ai-backend"
readonly UNIT_FILE="/etc/systemd/system/analyst-ai-backend.service"
readonly ENV_FILE="/etc/analyst-ai/backend.env"
readonly BACKEND_ROOT="/opt/analyst-ai"
readonly BACKEND_PATH="$BACKEND_ROOT/backend"
readonly VENV_PYTHON="$BACKEND_ROOT/venv/bin/python"
readonly REMOTE_ROOT="/root/analyst-ai-deploy/$RUN_ID"
readonly ARCHIVE="$REMOTE_ROOT/backend.tgz"
readonly STAGING="$BACKEND_ROOT/backend-next-telegram-auth-$RUN_ID"
readonly BACKUP="$BACKEND_ROOT/rollback/telegram-auth-$RUN_ID"
readonly HEADER_FILE="$REMOTE_ROOT/local.headers"
readonly BODY_FILE="$REMOTE_ROOT/local.body"
readonly PREFLIGHT_DB="$REMOTE_ROOT/preflight.sqlite3"
readonly PUBLIC_HEADER_FILE="$REMOTE_ROOT/public.headers"
readonly PUBLIC_BODY_FILE="$REMOTE_ROOT/public.body"
readonly PUBLIC_HOST="176.98.178.81.sslip.io"
readonly SHA256_RECORD_FORMAT='%s  %s\n'
readonly OLD_EXEC='ExecStart=/opt/analyst-ai/venv/bin/uvicorn app:app --host 127.0.0.1 --port 8080 --workers 1'
readonly NEW_EXEC='ExecStart=/opt/analyst-ai/venv/bin/uvicorn telegram_browser_app:app --host 127.0.0.1 --port 8080 --workers 1'
ACTIVATED=0

rollback() {
  set +e
  echo "TELEGRAM_AUTH_DEPLOYMENT=rolling_back" >&2
  if [[ ! -d "$BACKUP/backend" || ! -f "$BACKUP/analyst-ai-backend.service" ]]; then
    echo "TELEGRAM_AUTH_ROLLBACK=backup_missing" >&2
    return 1
  fi
  systemctl stop "$UNIT_NAME"
  if [[ -d "$BACKUP/backend" ]]; then
    rm -rf "$BACKEND_PATH"
    cp -a "$BACKUP/backend" "$BACKEND_PATH"
  fi
  if [[ -f "$BACKUP/analyst-ai-backend.service" ]]; then
    cp -a "$BACKUP/analyst-ai-backend.service" "$UNIT_FILE"
  fi
  systemctl daemon-reload
  systemctl restart "$UNIT_NAME"
  for _ in $(seq 1 30); do
    if curl --fail --silent --show-error --max-time 5 \
      http://127.0.0.1:8080/health >/dev/null; then
      echo "TELEGRAM_AUTH_ROLLBACK=healthy" >&2
      return
    fi
    sleep 2
  done
  echo "TELEGRAM_AUTH_ROLLBACK=health_failed" >&2
  return 1
}

finish() {
  local rc=$?
  trap - EXIT
  if [[ "$rc" -ne 0 && "$ACTIVATED" -eq 1 ]]; then
    rollback
  fi
  rm -rf "$STAGING"
  rm -f "$ARCHIVE" "$HEADER_FILE" "$BODY_FILE" "$PREFLIGHT_DB" \
    "$PUBLIC_HEADER_FILE" "$PUBLIC_BODY_FILE"
  exit "$rc"
}
trap finish EXIT

if [[ "$MODE" == "rollback" ]]; then
  ACTIVATED=1
  if ! rollback; then
    ACTIVATED=0
    exit 1
  fi
  ACTIVATED=0
  echo "TELEGRAM_AUTH_EXTERNAL_ROLLBACK=passed"
  exit 0
fi

[[ -d "$REMOTE_ROOT" && ! -L "$REMOTE_ROOT" ]] || {
  echo "Private deployment directory missing or linked" >&2
  exit 1
}
[[ "$(stat -c '%u' "$REMOTE_ROOT")" == "0" ]] || {
  echo "Private deployment directory is not owned by root" >&2
  exit 1
}
[[ "$(stat -c '%a' "$REMOTE_ROOT")" == "700" ]] || {
  echo "Private deployment directory permissions are not 0700" >&2
  exit 1
}
[[ -f "$ARCHIVE" && ! -L "$ARCHIVE" ]] || { echo "Deployment archive missing" >&2; exit 1; }
printf "$SHA256_RECORD_FORMAT" "$EXPECTED_ARCHIVE_SHA" "$ARCHIVE" | sha256sum -c -
[[ -d "$BACKEND_PATH" && ! -L "$BACKEND_PATH" ]] || { echo "Current backend missing" >&2; exit 1; }
[[ -f "$UNIT_FILE" && ! -L "$UNIT_FILE" ]] || { echo "Backend unit missing" >&2; exit 1; }
[[ -f "$ENV_FILE" && ! -L "$ENV_FILE" ]] || { echo "Backend environment missing" >&2; exit 1; }
[[ -x "$VENV_PYTHON" ]] || { echo "Backend Python environment missing" >&2; exit 1; }
systemctl is-active --quiet "$UNIT_NAME" || { echo "Backend service is not active" >&2; exit 1; }

grep -Fx 'WorkingDirectory=/opt/analyst-ai/backend' "$UNIT_FILE" >/dev/null
grep -Fx 'EnvironmentFile=/etc/analyst-ai/backend.env' "$UNIT_FILE" >/dev/null
old_count="$(grep -Fxc "$OLD_EXEC" "$UNIT_FILE" || true)"
new_count="$(grep -Fxc "$NEW_EXEC" "$UNIT_FILE" || true)"
if [[ "$old_count" -eq 0 && "$new_count" -eq 0 ]]; then
  echo "Backend ExecStart does not match an audited entry point" >&2
  exit 1
fi
if [[ "$old_count" -gt 1 || "$new_count" -gt 1 || $((old_count + new_count)) -ne 1 ]]; then
  echo "Backend unit contains an ambiguous ExecStart" >&2
  exit 1
fi

rm -rf "$STAGING"
mkdir -p "$STAGING"
archive_entries="$(tar -tzf "$ARCHIVE")"
if grep -Eq '(^/|(^|/)\.\.(/|$))' <<<"$archive_entries"; then
  echo "Backend archive contains an unsafe path" >&2
  exit 1
fi
tar -xzf "$ARCHIVE" -C "$STAGING"
[[ -d "$STAGING/backend" ]] || { echo "Staged backend missing" >&2; exit 1; }
if find "$STAGING/backend" -type l -print -quit | grep -q .; then
  echo "Staged backend contains a symbolic link" >&2
  exit 1
fi
printf "$SHA256_RECORD_FORMAT" "$EXPECTED_JWKS_SHA" "$STAGING/backend/telegram_jwks.json" | sha256sum -c -
printf "$SHA256_RECORD_FORMAT" "$EXPECTED_REQUIREMENTS_SHA" "$STAGING/backend/requirements.txt" | sha256sum -c -
printf "$SHA256_RECORD_FORMAT" "$EXPECTED_REQUIREMENTS_SHA" "$BACKEND_PATH/requirements.txt" | sha256sum -c -

"$VENV_PYTHON" -m compileall -q "$STAGING/backend"
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a
DATABASE_PATH="$PREFLIGHT_DB" STAGED_BACKEND="$STAGING/backend" "$VENV_PYTHON" - <<'PY'
import os
from pathlib import Path
import sys

staged = Path(os.environ["STAGED_BACKEND"])
sys.path.insert(0, str(staged))
import telegram_browser_app as module

module.legacy.init_db()
start_routes = [
    route for route in module.app.router.routes
    if getattr(route, "path", None) == "/auth/telegram/start"
    and "GET" in (getattr(route, "methods", None) or set())
]
complete_routes = [
    route for route in module.app.router.routes
    if getattr(route, "path", None) == "/auth/telegram/complete"
    and "POST" in (getattr(route, "methods", None) or set())
]
if len(start_routes) != 1 or len(complete_routes) != 1:
    raise SystemExit("Telegram browser routes are not registered exactly once")
response = module.telegram_browser_start()
body = response.body.decode("utf-8")
required = (
    "https://oauth.telegram.org/js/telegram-login.js?3",
    "Продолжить в Telegram",
    "/auth/telegram/complete",
)
if any(value not in body for value in required):
    raise SystemExit("Telegram browser login page failed preflight")
if os.environ["TELEGRAM_CLIENT_SECRET"] in body:
    raise SystemExit("Telegram client secret leaked into the login page")
if response.headers.get("cross-origin-opener-policy") != "same-origin-allow-popups":
    raise SystemExit("Telegram popup policy is missing")
PY

mkdir -p "$BACKUP"
[[ ! -e "$BACKUP/backend" ]] || { echo "Deployment backup already exists" >&2; exit 1; }
cp -a "$BACKEND_PATH" "$BACKUP/backend"
cp -a "$UNIT_FILE" "$BACKUP/analyst-ai-backend.service"
ACTIVATED=1

systemctl stop "$UNIT_NAME"
rm -rf "$BACKEND_PATH"
mv "$STAGING/backend" "$BACKEND_PATH"
chown -R root:www-data "$BACKEND_PATH"
find "$BACKEND_PATH" -type d -exec chmod 0755 {} +
find "$BACKEND_PATH" -type f -exec chmod 0644 {} +

UNIT_FILE="$UNIT_FILE" OLD_EXEC="$OLD_EXEC" NEW_EXEC="$NEW_EXEC" "$VENV_PYTHON" - <<'PY'
import os
from pathlib import Path
import tempfile

path = Path(os.environ["UNIT_FILE"])
old = os.environ["OLD_EXEC"]
new = os.environ["NEW_EXEC"]
text = path.read_text(encoding="utf-8")
old_count = text.count(old)
new_count = text.count(new)
if old_count == 1 and new_count == 0:
    updated = text.replace(old, new)
elif old_count == 0 and new_count == 1:
    updated = text
else:
    raise SystemExit("Backend unit entry point is ambiguous")
with tempfile.NamedTemporaryFile(
    mode="w", encoding="utf-8", dir=path.parent, delete=False, newline="\n"
) as handle:
    staged = Path(handle.name)
    handle.write(updated)
    handle.flush()
    os.fsync(handle.fileno())
staged.chmod(path.stat().st_mode)
os.replace(staged, path)
PY

systemctl daemon-reload
systemctl restart "$UNIT_NAME"
for _ in $(seq 1 45); do
  if curl --fail --silent --show-error --max-time 5 \
    http://127.0.0.1:8080/health >/dev/null; then
    break
  fi
  sleep 2
done
curl --fail --silent --show-error --max-time 10 \
  http://127.0.0.1:8080/health | grep -F '"status":"ok"' >/dev/null
curl --fail --silent --show-error --max-time 15 \
  -D "$HEADER_FILE" -o "$BODY_FILE" \
  http://127.0.0.1:8080/auth/telegram/start

grep -Fi 'cross-origin-opener-policy: same-origin-allow-popups' "$HEADER_FILE" >/dev/null
grep -Fi 'cache-control:' "$HEADER_FILE" | grep -Fi 'no-store' >/dev/null
grep -F 'https://oauth.telegram.org/js/telegram-login.js?3' "$BODY_FILE" >/dev/null
grep -F 'Продолжить в Telegram' "$BODY_FILE" >/dev/null
grep -F '/auth/telegram/complete' "$BODY_FILE" >/dev/null
BODY_FILE="$BODY_FILE" "$VENV_PYTHON" - <<'PY'
import os
from pathlib import Path

body = Path(os.environ["BODY_FILE"]).read_text(encoding="utf-8")
secret = os.environ["TELEGRAM_CLIENT_SECRET"]
if not secret or secret in body:
    raise SystemExit("Telegram client secret exposure check failed")
PY

systemctl is-active --quiet "$UNIT_NAME"
grep -Fxc "$NEW_EXEC" "$UNIT_FILE" | grep -Fx '1' >/dev/null

curl --fail --silent --show-error --max-time 15 \
  --resolve "$PUBLIC_HOST:443:127.0.0.1" \
  "https://$PUBLIC_HOST/health" | grep -F '"status":"ok"' >/dev/null
curl --fail --silent --show-error --max-time 20 \
  --resolve "$PUBLIC_HOST:443:127.0.0.1" \
  -D "$PUBLIC_HEADER_FILE" -o "$PUBLIC_BODY_FILE" \
  "https://$PUBLIC_HOST/auth/telegram/start"
grep -Fi 'cross-origin-opener-policy: same-origin-allow-popups' "$PUBLIC_HEADER_FILE" >/dev/null
grep -Fi 'cache-control:' "$PUBLIC_HEADER_FILE" | grep -Fi 'no-store' >/dev/null
grep -F 'https://oauth.telegram.org/js/telegram-login.js?3' "$PUBLIC_BODY_FILE" >/dev/null
grep -F '/auth/telegram/complete' "$PUBLIC_BODY_FILE" >/dev/null

ACTIVATED=0
echo "TELEGRAM_AUTH_DEPLOYMENT=passed"
