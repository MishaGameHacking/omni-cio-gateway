from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / ".github/scripts/deploy_timeweb_backend.sh"


def read() -> str:
    return TARGET.read_text(encoding="utf-8")


def write(content: str) -> None:
    TARGET.write_text(content, encoding="utf-8", newline="\n")


def replace_once(content: str, old: str, new: str) -> str:
    count = content.count(old)
    if count != 1:
        raise RuntimeError(
            f"expected exactly one deployment anchor, found {count}: {old[:160]!r}"
        )
    return content.replace(old, new, 1)


content = read()

content = replace_once(
    content,
    'UPLOAD_ENV="$TMP_DIR/backend.env.upload"\n',
    '''UPLOAD_ENV="$TMP_DIR/backend.env.upload"
KNOWN_HOSTS="$TMP_DIR/analyst-ai-known-hosts"
REMOTE_SCRIPT="$TMP_DIR/analyst-ai-remote-deploy.sh"
ARCHIVE_PATH="$TMP_DIR/backend.tgz"
''',
)

content = replace_once(
    content,
    '  rm -f "$KEY_PATH" "$KEY_PATH.pub" "$UPLOAD_ENV"\n',
    '  rm -f "$KEY_PATH" "$KEY_PATH.pub" "$UPLOAD_ENV" "$KNOWN_HOSTS" "$REMOTE_SCRIPT" "$ARCHIVE_PATH"\n',
)

old_request = '''def request(method, path, body=None):
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
'''
new_request = '''def request(method, path, body=None):
    data = None if body is None else json.dumps(body).encode()
    retryable_statuses = {408, 429, 500, 502, 503, 504}
    last_error = None
    for attempt in range(1, 6):
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
            with urllib.request.urlopen(req, timeout=45) as response:
                raw = response.read()
                return {} if not raw else json.loads(raw)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            last_error = RuntimeError(
                f"Timeweb {method} {path} failed: HTTP {exc.code}: {detail}"
            )
            if exc.code not in retryable_statuses or attempt == 5:
                raise last_error from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            last_error = RuntimeError(
                f"Timeweb {method} {path} connection failed on attempt {attempt}: {exc}"
            )
            if attempt == 5:
                raise last_error from exc
        delay = min(2 ** attempt, 20)
        print(
            f"Timeweb {method} {path} transient failure; retry {attempt}/5 in {delay}s"
        )
        time.sleep(delay)
    raise last_error or RuntimeError(f"Timeweb {method} {path} failed")
'''
content = replace_once(content, old_request, new_request)

old_transport = '''source "$STATE_PATH"

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
'''
new_transport = '''source "$STATE_PATH"

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
    echo "Transient network failure; retry $current/$attempts in ${delay}s: $*" >&2
    sleep "$delay"
    current=$((current + 1))
    if [[ "$delay" -lt 30 ]]; then
      delay=$((delay + 5))
    fi
  done
}

for attempt in $(seq 1 60); do
  if ssh "${SSH_OPTS[@]}" root@"$SERVER_IP" "echo ready" >/dev/null 2>&1; then
    break
  fi
  if [[ "$attempt" -eq 60 ]]; then
    echo "::error::SSH did not become ready after 10 minutes" >&2
    exit 1
  fi
  sleep 10
done

tar -czf "$ARCHIVE_PATH" backend
retry_command 8 10 scp "${SSH_OPTS[@]}" "$ARCHIVE_PATH" root@"$SERVER_IP":/tmp/backend.tgz
'''
content = replace_once(content, old_transport, new_transport)

content = replace_once(
    content,
    '''scp -i "$KEY_PATH"   -o StrictHostKeyChecking=accept-new   "$UPLOAD_ENV" root@"$SERVER_IP":/tmp/backend.env.upload

ssh -i "$KEY_PATH"   -o StrictHostKeyChecking=accept-new   root@"$SERVER_IP" "BACKEND_HOST='$BACKEND_HOST' bash -s" <<'REMOTE'
''',
    '''retry_command 8 10 scp "${SSH_OPTS[@]}" "$UPLOAD_ENV" root@"$SERVER_IP":/tmp/backend.env.upload

cat > "$REMOTE_SCRIPT" <<'REMOTE'
''',
)

content = replace_once(
    content,
    '''systemctl restart analyst-ai-backend
systemctl restart caddy
REMOTE

for attempt in $(seq 1 36); do
''',
    '''systemctl restart analyst-ai-backend
systemctl restart caddy
rm -f /tmp/analyst-ai-remote-deploy.sh
REMOTE

retry_command 8 10 scp "${SSH_OPTS[@]}" "$REMOTE_SCRIPT" root@"$SERVER_IP":/tmp/analyst-ai-remote-deploy.sh
retry_command 8 10 ssh "${SSH_OPTS[@]}" root@"$SERVER_IP" "BACKEND_HOST='$BACKEND_HOST' bash /tmp/analyst-ai-remote-deploy.sh"

for attempt in $(seq 1 36); do
''',
)

write(content)
print("Timeweb deployment resilience applied")
