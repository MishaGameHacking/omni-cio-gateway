"""One-time, owner-authorized cutover between two fixed Analyst AI installations.

This tool has NO cloud API credentials, deletion, VM creation or tariff operations.
It is uploaded over temporary authenticated SSH by the cutover workflow. Commands
before activate can be rolled back; after the durable activation marker appears,
source writes MUST NOT be resumed without a reverse synchronization.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

SOURCE_HOST = '94.198.220.228.sslip.io'
TARGET_HOST = '176.98.178.81.sslip.io'
SOURCE_ID = 9326369
TARGET_ID = 9334503
ENV = Path('/etc/analyst-ai/backend.env')
DATA = Path('/var/lib/analyst-ai')
CODE = Path('/opt/analyst-ai/backend')
CADDY = Path('/etc/caddy/Caddyfile')
SERVICE = 'analyst-ai-backend'
SOURCE_LOCK = Path('/etc/analyst-ai/source-retired.lock')
DROPIN = Path('/etc/systemd/system/analyst-ai-backend.service.d/90-moscow-migration.conf')
ACTIVE = Path('/etc/analyst-ai/moscow-active.json')
STAGING = Path('/etc/analyst-ai/migration-staging.json')


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def run_command(*args: str, timeout: int = 60, allowed: tuple[int, ...] = (0,)) -> str:
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    require(result.returncode in allowed, 'Command failed: ' + args[0] + ' ' + args[1])
    # Never echo stdout/stderr that could contain settings or user data.
    return result.stdout.strip()


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def write_private(path: Path, text: str) -> None:
    require(not path.is_symlink(), 'Symlink destination refused')
    temporary = path.with_name(path.name + '.new')
    require(not temporary.exists(), 'Unfinished atomic write; reconcile first')
    with temporary.open('x', encoding='utf-8') as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.chmod(0o600)
    temporary.replace(path)


def settings() -> dict:
    from dotenv import dotenv_values
    require(ENV.is_file() and not ENV.is_symlink(), 'Missing regular environment file')
    result = dict(dotenv_values(ENV))
    require(result.get('DATABASE_PATH') == str(DATA / 'backend.db'), 'Unexpected database path')
    require(bool(result.get('FERNET_KEY')), 'Missing original encryption key')
    return result


def load_process_environment() -> dict:
    result = settings()
    for key, value in result.items():
        if value is not None:
            os.environ[key] = value
    return result


def service_stopped() -> None:
    state = run_command('systemctl', 'is-active', SERVICE, allowed=(0, 3))
    require(state == 'inactive', 'Backend must be fully stopped before copying')


def set_caddy(content: str) -> None:
    candidate = CADDY.with_name('Caddyfile.migration')
    write_private(candidate, content)
    run_command('caddy', 'validate', '--config', str(candidate), '--adapter', 'caddyfile')
    candidate.chmod(0o644)
    candidate.replace(CADDY)
    run_command('systemctl', 'reload', 'caddy')
    require(run_command('systemctl', 'is-active', 'caddy') == 'active', 'Caddy not active')


def source_preflight(state: Path) -> None:
    require(settings().get('BACKEND_PUBLIC_URL', '').rstrip('/') == 'https://' + SOURCE_HOST,
            'Not the expected source installation')
    require(not SOURCE_LOCK.exists() and not ACTIVE.exists(), 'Source already locked/activated; reconcile')
    require(run_command('systemctl', 'is-active', SERVICE) == 'active', 'Source is not active')
    require(not DROPIN.exists(), 'Unexpected migration drop-in')
    state.mkdir(mode=0o700, exist_ok=False)
    shutil.copyfile(CADDY, state / 'source.Caddyfile')
    write_private(state / 'source-state.json', json.dumps({'source_id': SOURCE_ID, 'target_id': TARGET_ID,
        'original_environment_sha256': digest(ENV), 'phase': 'preflight'}))
    print('SOURCE_PREFLIGHT=identity_and_original_configuration_saved', flush=True)


def target_preflight(state: Path) -> None:
    require(not ACTIVE.exists(), 'Target already activated; never overwrite it')
    marker = json.loads(STAGING.read_text(encoding='utf-8'))
    require(marker.get('source_id') == SOURCE_ID and marker.get('target_id') == TARGET_ID
            and marker.get('cutover') is False and marker.get('public_ready') is False,
            'Not an isolated verified staging installation')
    current = settings()
    require(current.get('BACKEND_PUBLIC_URL') == 'https://' + TARGET_HOST
            and current.get('ANALYSIS_SCHEDULER_ENABLED') == 'false', 'Staging environment mismatch')
    require(not SOURCE_LOCK.exists() and not DROPIN.exists(), 'Unexpected target lock')
    state.mkdir(mode=0o700, exist_ok=False)
    print('TARGET_PREFLIGHT=isolated_staging_verified', flush=True)


def freeze_source(state: Path, run: str) -> None:
    record = json.loads((state / 'source-state.json').read_text())
    require(record.get('phase') == 'preflight' and not SOURCE_LOCK.exists(), 'Source freeze already attempted')
    require(digest(ENV) == record['original_environment_sha256'], 'Source settings changed')
    set_caddy(SOURCE_HOST + ' {\n    respond "Analyst AI: final migration in progress" 503\n}\n')
    # A durable systemd condition prevents an accidental restart after runner loss or reboot.
    write_private(SOURCE_LOCK, run + '\n')
    DROPIN.parent.mkdir(mode=0o755, exist_ok=True)
    write_private(DROPIN, '[Unit]\nConditionPathExists=!/etc/analyst-ai/source-retired.lock\n')
    run_command('systemctl', 'daemon-reload')
    run_command('systemctl', 'stop', SERVICE, timeout=90)
    service_stopped()
    import migration_snapshot
    argv = sys.argv[:]
    try:
        sys.argv = [sys.argv[0], run]
        with contextlib.redirect_stdout(io.StringIO()) as output:
            migration_snapshot.main()
        snapshot = json.loads(output.getvalue())
    finally:
        sys.argv = argv
    service_stopped()
    record.update({'phase': 'frozen', 'run': run, 'snapshot': snapshot,
        'source_database_sha256': digest(DATA / 'backend.db'),
        'frozen_at': datetime.now(timezone.utc).isoformat()})
    write_private(state / 'source-state.json', json.dumps(record))
    require(re.fullmatch('[0-9a-f]{64}', snapshot['archive_sha256']) is not None, 'Invalid snapshot checksum')
    # Only checksum and booleans leave the source; no DB contents or settings.
    print(json.dumps({'archive_sha256': snapshot['archive_sha256'], 'source_writes_stopped': True,
        'snapshot_at': snapshot['snapshot_at']}), flush=True)


def restore_target(state: Path, run: str, archive_hash: str) -> None:
    require(not ACTIVE.exists(), 'Activated target is never overwritten')
    marker = json.loads(STAGING.read_text())
    require(marker.get('target_id') == TARGET_ID and marker.get('public_ready') is False,
            'Target is not isolated staging')
    require(settings().get('ANALYSIS_SCHEDULER_ENABLED') == 'false', 'Target scheduler already enabled')
    stage = Path('/root/analyst-migration-' + run)
    require(digest(stage / 'application.tgz') == archive_hash, 'Transferred archive checksum mismatch')
    previous = state / 'previous-staging'
    previous.mkdir(mode=0o700, exist_ok=False)
    shutil.copyfile('/etc/systemd/system/analyst-ai-backend.service', previous / 'backend.service')
    shutil.copyfile(CADDY, previous / 'Caddyfile')
    run_command('systemctl', 'stop', SERVICE, timeout=90)
    service_stopped()
    for original, name in ((DATA, 'data'), (CODE, 'code'), (ENV.parent, 'config')):
        require(original.is_dir() and not original.is_symlink(), 'Unexpected target path')
        shutil.move(str(original), str(previous / name))
    import migration_restore
    migration_restore.unpack(stage, run, TARGET_HOST, archive_hash)
    migration_restore.verify(stage)
    from dotenv import set_key, dotenv_values
    set_key(str(ENV), 'TELEGRAM_REDIRECT_URI', 'https://' + TARGET_HOST + '/auth/telegram/callback')
    ENV.chmod(0o600)
    source_settings = dict(dotenv_values(stage / 'restored/config/backend.env'))
    target_settings = settings()
    permitted = {'BACKEND_PUBLIC_URL', 'TELEGRAM_REDIRECT_URI', 'ANALYSIS_SCHEDULER_ENABLED'}
    require(all(source_settings.get(key) == target_settings.get(key)
        for key in (set(source_settings) | set(target_settings)) - permitted), 'Unexpected configuration change')
    write_private(state / 'target-state.json', json.dumps({'source_id': SOURCE_ID, 'target_id': TARGET_ID,
        'run': run, 'phase': 'restored_closed', 'archive_sha256': archive_hash,
        'source_snapshot_at': json.loads((stage / 'restored/manifest.json').read_text())['snapshot_at']}))
    run_command('systemctl', 'daemon-reload')
    run_command('systemctl', 'start', SERVICE)
    wait_local_health()
    print('FINAL_RESTORE=integrity_files_counts_and_original_key_verified_public_closed', flush=True)


def wait_local_health() -> None:
    import httpx
    with httpx.Client(timeout=5, follow_redirects=False) as client:
        for _ in range(30):
            try:
                response = client.get('http://127.0.0.1:8080/health')
                if response.status_code == 200 and response.json() == {'status': 'ok'}:
                    return
            except (httpx.HTTPError, ValueError):
                pass
            time.sleep(1)
    raise RuntimeError('Local backend health failed')


def assert_oauth(location: str) -> str:
    url = urlparse(location)
    query = parse_qs(url.query)
    require(url.scheme == 'https' and url.netloc == 'oauth.telegram.org' and url.path == '/auth',
            'Unexpected Telegram authorization endpoint')
    require(query.get('redirect_uri') == ['https://' + TARGET_HOST + '/auth/telegram/callback'],
            'Wrong Telegram redirect URI')
    require(query.get('code_challenge_method') == ['S256'] and bool(query.get('code_challenge'))
            and query.get('response_type') == ['code'] and bool(query.get('state')), 'OAuth safety fields missing')
    return query['state'][0]


def local_probe(state: Path) -> None:
    """Exercise real local API using a temporary synthetic user; broker reads stay in memory."""
    current = load_process_environment()
    require(current.get('ANALYSIS_SCHEDULER_ENABLED') == 'false' and not ACTIVE.exists(), 'Probe must run isolated')
    import httpx
    sys.path.insert(0, str(CODE))
    import app as backend
    from tinvest_portfolio import get_tinvest_portfolio
    temporary_sub = 'migration-probe-' + secrets.token_hex(16)
    one_time = secrets.token_urlsafe(40)
    code_hash = hashlib.sha256(one_time.encode()).hexdigest()
    probe_id = None
    oauth_state = None
    with httpx.Client(base_url='http://127.0.0.1:8080', timeout=30, follow_redirects=False) as client:
        try:
            require(client.get('/me').status_code == 401, 'Unauthenticated route not protected')
            require(client.get('/tinvest/portfolio').status_code == 401, 'Portfolio authentication not enforced')
            start = client.get('/auth/telegram/start')
            require(start.status_code == 302, 'Telegram start failed')
            oauth_state = assert_oauth(start.headers.get('location', ''))
            with contextlib.closing(sqlite3.connect(DATA / 'backend.db', timeout=10)) as db:
                now = int(time.time())
                cursor = db.execute('INSERT INTO users(telegram_sub,telegram_id,name,created_at,updated_at) VALUES (?,?,?,?,?)',
                    (temporary_sub, temporary_sub, 'Migration diagnostic', now, now))
                probe_id = cursor.lastrowid
                db.execute('INSERT INTO login_codes(code_hash,user_id,expires_at,used) VALUES (?,?,?,0)',
                    (code_hash, probe_id, now + 120))
                db.commit()
            exchanged = client.post('/auth/session', json={'code': one_time})
            require(exchanged.status_code == 200, 'Synthetic session exchange failed')
            session = exchanged.json().get('access_token')
            require(isinstance(session, str) and len(session) >= 32, 'Session missing')
            response = client.get('/me', headers={'Authorization': 'Bearer ' + session})
            require(response.status_code == 200 and response.json().get('telegram_id') == temporary_sub,
                    'Synthetic session identity not preserved')
            require(client.post('/auth/session', json={'code': one_time}).status_code == 401, 'One-time code replay accepted')
            del session
        finally:
            with contextlib.closing(sqlite3.connect(DATA / 'backend.db', timeout=10)) as db:
                if probe_id is not None:
                    db.execute('DELETE FROM sessions WHERE user_id=?', (probe_id,))
                    db.execute('DELETE FROM login_codes WHERE user_id=?', (probe_id,))
                    db.execute('DELETE FROM users WHERE id=? AND telegram_sub=?', (probe_id, temporary_sub))
                if oauth_state:
                    db.execute('DELETE FROM login_transactions WHERE state=?', (oauth_state,))
                db.commit()
    with contextlib.closing(backend.connect()) as db:
        user = db.execute('SELECT * FROM users WHERE tinvest_token_encrypted IS NOT NULL LIMIT 1').fetchone()
    broker_result = 'not_applicable_no_stored_token'
    if user is not None:
        portfolio = get_tinvest_portfolio(currency='RUB', user=user)
        require(portfolio.get('currency') == 'RUB' and isinstance(portfolio.get('accounts'), list), 'Broker portfolio read failed')
        broker_result = 'passed_read_only_portfolio'
        del portfolio, user
    record = json.loads((state / 'target-state.json').read_text())
    record.update({'local_auth_probe': True, 'broker_probe': broker_result, 'phase': 'validated_closed'})
    write_private(state / 'target-state.json', json.dumps(record))
    print('MOSCOW_LOCAL_PROBES=' + json.dumps({'unauthorized_rejected': True,
        'new_redirect_uri': True, 'pkce': True, 'synthetic_session_exchange': True,
        'one_time_replay_rejected': True, 'synthetic_data_removed': True, 'broker': broker_result,
        'real_telegram_login_on_phone': 'not_tested'}), flush=True)


def activate(state: Path) -> None:
    require(not ACTIVE.exists(), 'Target activation already attempted; reconcile before retry')
    record = json.loads((state / 'target-state.json').read_text())
    require(record.get('phase') == 'validated_closed' and record.get('local_auth_probe') is True,
            'Local validation not completed')
    # The marker is written BEFORE enabling any target writer or public route.
    record.update({'phase': 'activating', 'target_writes_may_exist': True})
    write_private(ACTIVE, json.dumps(record))
    from dotenv import set_key
    set_key(str(ENV), 'ANALYSIS_SCHEDULER_ENABLED', 'true')
    ENV.chmod(0o600)
    run_command('systemctl', 'restart', SERVICE)
    wait_local_health()
    set_caddy(TARGET_HOST + ' {\n    encode zstd gzip\n    reverse_proxy 127.0.0.1:8080\n}\n')
    record.update({'phase': 'active', 'activated_at': datetime.now(timezone.utc).isoformat()})
    write_private(ACTIVE, json.dumps(record))
    print('MOSCOW_ACTIVATED=single_backend_writer_and_scheduler_public_routes_open', flush=True)


def bridge_source(state: Path) -> None:
    service_stopped()
    record = json.loads((state / 'source-state.json').read_text())
    require(record.get('phase') == 'frozen' and SOURCE_LOCK.exists(), 'Source not frozen')
    require(digest(DATA / 'backend.db') == record['source_database_sha256'], 'Source database changed after freeze')
    set_caddy(SOURCE_HOST + ' {\n    reverse_proxy https://' + TARGET_HOST + ' {\n'
        '        header_up Host ' + TARGET_HOST + '\n    }\n}\n')
    record.update({'phase': 'bridge_only', 'local_backend_running': False, 'proxy_target': TARGET_HOST})
    write_private(state / 'source-state.json', json.dumps(record))
    print('SOURCE_BRIDGE=old_clients_use_moscow_no_local_database_writer', flush=True)


def rollback_source(state: Path) -> None:
    # Controller invokes this ONLY after positively verifying no target activation marker.
    require((state / 'source-state.json').is_file(), 'No source preflight state')
    DROPIN.unlink(missing_ok=True)
    SOURCE_LOCK.unlink(missing_ok=True)
    run_command('systemctl', 'daemon-reload')
    run_command('systemctl', 'start', SERVICE)
    wait_local_health()
    set_caddy((state / 'source.Caddyfile').read_text())
    print('SOURCE_ROLLBACK=active_before_any_target_activation', flush=True)


def main() -> None:
    require(os.geteuid() == 0, 'Root execution required on the verified VM')
    require(len(sys.argv) in (3, 4), 'Expected action and run')
    action, run = sys.argv[1:3]
    require(re.fullmatch('[0-9]{1,20}', run) is not None, 'Invalid run identifier')
    os.umask(0o077)
    state = Path('/root/analyst-cutover-' + run)
    require(not state.is_symlink(), 'Symlink state directory refused')
    actions = {'source-preflight': lambda: source_preflight(state),
        'target-preflight': lambda: target_preflight(state),
        'freeze-source': lambda: freeze_source(state, run),
        'probe-target': lambda: local_probe(state),
        'activate-target': lambda: activate(state),
        'bridge-source': lambda: bridge_source(state),
        'rollback-source': lambda: rollback_source(state)}
    if action == 'restore-target':
        require(len(sys.argv) == 4 and re.fullmatch('[0-9a-f]{64}', sys.argv[3]) is not None, 'Invalid archive checksum')
        restore_target(state, run, sys.argv[3])
    else:
        require(action in actions and len(sys.argv) == 3, 'Unknown cutover action')
        actions[action]()


if __name__ == '__main__':
    main()
