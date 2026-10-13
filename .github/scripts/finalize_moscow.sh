#!/usr/bin/env bash
set -euo pipefail
umask 077
[[ "${GITHUB_RUN_ID:-}" =~ ^[0-9]{1,20}$ ]] || exit 1
RUN="$GITHUB_RUN_ID"
TMP="$(cygpath -u "$RUNNER_TEMP")"
PRIVATE="$(mktemp -d "$TMP/analyst-final-cutover.XXXXXXXX")"
KEY="$PRIVATE/identity"
STATE="$PRIVATE/access.json"
KNOWN="$PRIVATE/known_hosts"
export MIGRATION_STATE_WINDOWS="$(cygpath -w "$STATE")"
export MIGRATION_PUBLIC_WINDOWS="$(cygpath -w "$KEY.pub")"
SOURCE_IP=94.198.220.228
TARGET_IP=176.98.178.81
TOOLS="/root/analyst-cutover-tools-$RUN"
STAGE="/root/analyst-migration-$RUN"
FROZEN_ATTEMPT=0
SSH_OPTIONS=(-i "$KEY" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=10 -o ServerAliveInterval=10 -o ServerAliveCountMax=3 -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile="$KNOWN")
remote() {
    local ip="$1" action="$2"
    shift 2
    ssh "${SSH_OPTIONS[@]}" root@"$ip" "/opt/analyst-ai/venv/bin/python '$TOOLS/moscow_cutover.py' '$action' '$RUN' $*"
}
cleanup() {
    local original=$?
    trap - EXIT
    set +e
    if [[ "$original" != 0 && "$FROZEN_ATTEMPT" = 1 ]]; then
        # A positive remote absence test is mandatory. Network failure is NOT absence.
        if ssh "${SSH_OPTIONS[@]}" root@"$TARGET_IP" 'test ! -e /etc/analyst-ai/moscow-active.json'; then
            remote "$SOURCE_IP" rollback-source || echo 'SOURCE_ROLLBACK_FAILED=manual_recovery_required'
        else
            echo 'ROLLBACK_BLOCKED=target_active_or_unreachable_never_resume_stale_source'
        fi
    fi
    py.exe -3 .github/scripts/migration_access.py cleanup
    local key_result=$?
    rm -f "$KEY" "$KEY.pub" "$KNOWN" "$STATE" "$PRIVATE/snapshot.json"
    rmdir "$PRIVATE" 2>/dev/null
    if [[ "$original" = 0 && "$key_result" != 0 ]]; then exit "$key_result"; fi
    exit "$original"
}
trap cleanup EXIT
ssh-keygen -t ed25519 -N '' -f "$KEY" -C "analyst-migrate-$RUN" >/dev/null
chmod 600 "$KEY"
py.exe -3 - <<'PY'
import sys
sys.path.insert(0, '.github/scripts')
import migration_access as access
access.validate_pair()
if access.ipv4(access.SOURCE) != '94.198.220.228' or access.ipv4(access.TARGET) != '176.98.178.81':
    raise RuntimeError('Exact existing addresses required; no IP order permitted')
original = access.api
def bounded(method, path, payload=None, key_id=None):
    if method == 'POST' and path.endswith('/ips'):
        raise RuntimeError('Final cutover never orders IP addresses')
    return original(method, path, payload, key_id)
access.api = bounded
access.prepare()
PY
for ip in "$SOURCE_IP" "$TARGET_IP"; do
    ready=0
    for attempt in $(seq 1 24); do
        if ssh "${SSH_OPTIONS[@]}" root@"$ip" 'test "$(id -u)" = 0' >/dev/null 2>&1; then ready=1; break; fi
        sleep 5
    done
    [[ "$ready" = 1 ]] || { echo 'SSH readiness failed; source not frozen'; exit 1; }
    ssh "${SSH_OPTIONS[@]}" root@"$ip" "umask 077; mkdir '$TOOLS'"
    for name in moscow_cutover.py migration_snapshot.py migration_restore.py; do
        ssh "${SSH_OPTIONS[@]}" root@"$ip" "umask 077; cat > '$TOOLS/$name'" < ".github/scripts/$name"
    done
    ssh "${SSH_OPTIONS[@]}" root@"$ip" "/opt/analyst-ai/venv/bin/python -m py_compile '$TOOLS/moscow_cutover.py' '$TOOLS/migration_snapshot.py' '$TOOLS/migration_restore.py'"
done
STATUS="$(curl --silent --show-error --max-time 15 --output /dev/null --write-out '%{http_code}' "https://$TARGET_IP.sslip.io/me")"
[[ "$STATUS" = 503 ]] || { echo 'Target is not isolated staging; source unchanged'; exit 1; }
remote "$SOURCE_IP" source-preflight
remote "$TARGET_IP" target-preflight
FROZEN_ATTEMPT=1
remote "$SOURCE_IP" freeze-source > "$PRIVATE/snapshot.json"
ARCHIVE_SHA="$(SNAPSHOT_WINDOWS="$(cygpath -w "$PRIVATE/snapshot.json")" py.exe -3 - <<'PY'
import json, os, re, sys
from pathlib import Path
record = json.loads(Path(os.environ['SNAPSHOT_WINDOWS']).read_text())
value = record['archive_sha256']
if record.get('source_writes_stopped') is not True or not re.fullmatch('[0-9a-f]{64}', value):
    raise RuntimeError('Invalid frozen-source snapshot receipt')
sys.stdout.buffer.write(value.encode('ascii'))
PY
)"
[[ "$ARCHIVE_SHA" =~ ^[0-9a-f]{64}$ ]] || exit 1
echo 'FINAL_SOURCE_SNAPSHOT=source_stopped_consistent_database_and_all_private_files'
ssh "${SSH_OPTIONS[@]}" root@"$TARGET_IP" "umask 077; mkdir '$STAGE'"
scp -3 "${SSH_OPTIONS[@]}" "root@$SOURCE_IP:$STAGE/application.tgz" "root@$TARGET_IP:$STAGE/application.tgz"
remote "$TARGET_IP" restore-target "$ARCHIVE_SHA"
remote "$TARGET_IP" probe-target
# Confirm source still cannot write before the irreversible writer switch boundary.
ssh "${SSH_OPTIONS[@]}" root@"$SOURCE_IP" 'test -f /etc/analyst-ai/source-retired.lock && test "$(systemctl is-active analyst-ai-backend)" = inactive'
remote "$TARGET_IP" activate-target
remote "$SOURCE_IP" bridge-source
py.exe -3 - <<'PY'
import json, sys, urllib.request, urllib.error
sys.path.insert(0, '.github/scripts')
from moscow_cutover import assert_oauth
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None
opener = urllib.request.build_opener(NoRedirect())
def get(url):
    try:
        response = opener.open(url, timeout=20)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        return response.code, response.headers, response.read(200001)
for host in ('176.98.178.81.sslip.io', '94.198.220.228.sslip.io'):
    status, _, body = get('https://' + host + '/health')
    if status != 200 or json.loads(body) != {'status': 'ok'}:
        raise RuntimeError('Public health failed')
    status, _, _ = get('https://' + host + '/me')
    if status != 401:
        raise RuntimeError('Public authentication guard failed')
    status, headers, _ = get('https://' + host + '/auth/telegram/start')
    if status != 302:
        raise RuntimeError('Public Telegram redirect failed')
    assert_oauth(headers.get('Location', ''))
    print('PUBLIC_CUTOVER_CHECK=' + json.dumps({'host': host, 'health': True, 'auth_required': True, 'redirect_to_moscow': True}))
print('FINAL_CUTOVER_VERIFIED=moscow_active_source_bridge_only_old_vm_not_deleted')
PY
