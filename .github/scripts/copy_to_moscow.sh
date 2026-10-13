#!/usr/bin/env bash
set -euo pipefail
umask 077
[[ "${GITHUB_RUN_ID:-}" =~ ^[0-9]+$ ]] || exit 1
RUN="$GITHUB_RUN_ID"
ROOT_TMP="$(cygpath -u "$RUNNER_TEMP")"
PRIVATE="$(mktemp -d "$ROOT_TMP/analyst-migration.XXXXXXXX")"
KEY="$PRIVATE/identity"
STATE="$PRIVATE/access.json"
KNOWN="$PRIVATE/known_hosts"
export MIGRATION_STATE_WINDOWS="$(cygpath -w "$STATE")"
export MIGRATION_PUBLIC_WINDOWS="$(cygpath -w "$KEY.pub")"
REMOTE_TOOLS="/root/analyst-migration-tools-$RUN"
REMOTE_STAGE="/root/analyst-migration-$RUN"
SOURCE_IP=''
TARGET_IP=''
SSH_OPTIONS=(-i "$KEY" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=10 -o ServerAliveInterval=10 -o ServerAliveCountMax=3 -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile="$KNOWN")
cleanup() {
    local original=$?
    trap - EXIT
    set +e
    if [[ -n "$SOURCE_IP" && -f "$KEY" ]]; then
        ssh "${SSH_OPTIONS[@]}" root@"$SOURCE_IP" "rm -f '$REMOTE_TOOLS/snapshot.py'; rmdir '$REMOTE_TOOLS'" >/dev/null 2>&1
    fi
    py.exe -3 .github/scripts/migration_access.py cleanup
    local cleanup_result=$?
    rm -f "$KEY" "$KEY.pub" "$KNOWN" "$STATE" "$PRIVATE/pair.env" "$PRIVATE/snapshot.json"
    rmdir "$PRIVATE" 2>/dev/null
    if [[ $original -eq 0 && $cleanup_result -ne 0 ]]; then exit "$cleanup_result"; fi
    exit "$original"
}
trap cleanup EXIT
ssh-keygen -t ed25519 -N '' -f "$KEY" -C "analyst-migrate-$RUN" >/dev/null
chmod 600 "$KEY"
py.exe -3 .github/scripts/migration_access.py prepare
py.exe -3 - <<'PY' > "$PRIVATE/pair.env"
import ipaddress, json, os, sys
from pathlib import Path
state = json.loads(Path(os.environ['MIGRATION_STATE_WINDOWS']).read_text())
for name in ('source_ip', 'target_ip'):
    value = ipaddress.ip_address(state[name])
    if value.version != 4 or not value.is_global:
        raise RuntimeError('Unexpected transfer address')
    sys.stdout.buffer.write((name.upper() + '=' + str(value) + '\n').encode('ascii'))
PY
source "$PRIVATE/pair.env"
HOST="$TARGET_IP.sslip.io"
for ip in "$SOURCE_IP" "$TARGET_IP"; do
    ready=0
    for attempt in $(seq 1 30); do
        if ssh "${SSH_OPTIONS[@]}" root@"$ip" 'test "$(id -u)" = 0' >/dev/null 2>&1; then ready=1; break; fi
        sleep 5
    done
    [[ "$ready" = 1 ]] || { echo 'SSH readiness failed; no source stop/delete'; exit 1; }
done
ssh "${SSH_OPTIONS[@]}" root@"$SOURCE_IP" "umask 077; mkdir '$REMOTE_TOOLS' && cat > '$REMOTE_TOOLS/snapshot.py'" < .github/scripts/migration_snapshot.py
ssh "${SSH_OPTIONS[@]}" root@"$SOURCE_IP" "/opt/analyst-ai/venv/bin/python '$REMOTE_TOOLS/snapshot.py' '$RUN'" > "$PRIVATE/snapshot.json"
ARCHIVE_SHA="$(SNAPSHOT_WINDOWS="$(cygpath -w "$PRIVATE/snapshot.json")" py.exe -3 - <<'PY'
import json, os, re, sys
from pathlib import Path
record = json.loads(Path(os.environ['SNAPSHOT_WINDOWS']).read_text())
value = record['archive_sha256']
if not re.fullmatch(r'[0-9a-f]{64}', value): raise RuntimeError('Invalid snapshot checksum')
sys.stdout.buffer.write(value.encode('ascii'))
PY
)"
[[ "$ARCHIVE_SHA" =~ ^[0-9a-f]{64}$ ]] || exit 1
echo 'SOURCE_SNAPSHOT=consistent_private_copy_created_and_tokens_verified'
ssh "${SSH_OPTIONS[@]}" root@"$TARGET_IP" "umask 077; mkdir '$REMOTE_STAGE'"
# Two authenticated SSH connections; no archive or secret is a GitHub artifact.
scp -3 "${SSH_OPTIONS[@]}" "root@$SOURCE_IP:$REMOTE_STAGE/application.tgz" "root@$TARGET_IP:$REMOTE_STAGE/application.tgz"
ssh "${SSH_OPTIONS[@]}" root@"$TARGET_IP" "umask 077; cat > '$REMOTE_STAGE/restore.py'" < .github/scripts/migration_restore.py
ssh "${SSH_OPTIONS[@]}" root@"$TARGET_IP" "RUN='$RUN' HOST='$HOST' ARCHIVE_SHA='$ARCHIVE_SHA' bash -s" <<'REMOTE'
set -euo pipefail
umask 077
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3-venv caddy
STAGE="/root/analyst-migration-$RUN"
python3 "$STAGE/restore.py" unpack "$RUN" "$HOST" "$ARCHIVE_SHA"
umask 022
python3 -m venv /opt/analyst-ai/venv
/opt/analyst-ai/venv/bin/pip install --disable-pip-version-check --no-cache-dir -r /opt/analyst-ai/backend/requirements.txt
umask 077
/opt/analyst-ai/venv/bin/python "$STAGE/restore.py" verify "$RUN" "$HOST" "$ARCHIVE_SHA"
caddy validate --config /etc/caddy/Caddyfile
systemctl daemon-reload
systemctl enable --now analyst-ai-backend
systemctl enable --now caddy
systemctl restart caddy
for i in $(seq 1 30); do
    if curl --fail --silent --max-time 5 http://127.0.0.1:8080/health | grep -q '"ok"'; then break; fi
    sleep 2
    [[ "$i" != 30 ]] || exit 1
done
systemctl is-active --quiet analyst-ai-backend
systemctl is-active --quiet caddy
echo 'MOSCOW_LOCAL_HEALTH=passed_scheduler_off'
REMOTE
for i in $(seq 1 36); do
    if curl --fail --silent --max-time 10 "https://$HOST/health" | grep -q '"ok"'; then break; fi
    sleep 5
    [[ "$i" != 36 ]] || { echo 'Target TLS/health not ready; source unchanged'; exit 1; }
done
STAGING_STATUS="$(curl --silent --output /dev/null --max-time 15 --write-out '%{http_code}' "https://$HOST/me")"
[[ "$STAGING_STATUS" = 503 ]] || { echo 'Staging route isolation check failed'; exit 1; }
curl --fail --silent --max-time 15 "https://$SOURCE_IP.sslip.io/health" | grep -q '"ok"'
echo "MOSCOW_STAGING_VERIFIED target_id=9334503 host=$HOST data_snapshot_copied=true source_operational=true public_user_routes=closed scheduler=off final_cutover=false old_deleted=false"
