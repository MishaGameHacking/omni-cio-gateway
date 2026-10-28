"""Install a laptop-verified server-only release on the existing Timeweb host."""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request

BASE = '1da6e6420b51ebe66c8196e3869a2525f0ffe69f'
MODULES = {'autonomous_controller.py', 'volume_live.py', 'server_version.py'}
SERVICES = ('analyst-ai-owner.service', 'analyst-ai-updates.service')
PUBLIC = 'https://analyst-ai-2941515.twc1.net'


def need(condition, code):
    if not condition:
        raise RuntimeError(code)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def validate(bundle):
    need(bundle['schema'] == 1 and bundle['base_commit'] == BASE
         and bundle['host'] == 'LAPTOP-NPSGA016' and bundle['apk_changed'] is False,
         'unexpected_release_contract')
    need(re.fullmatch('[a-f0-9]{40}', bundle['source_commit']), 'invalid_source_commit')
    need(set(bundle['files']) == MODULES, 'unreviewed_module_set')
    expected = bundle['expected']
    need(50 <= len(expected) <= 200 and 'app.py' in expected
         and 'requirements.txt' in expected, 'incomplete_runtime_baseline')
    for name, value in expected.items():
        need(re.fullmatch('[a-z_][a-z0-9_]*\\.py|requirements\\.txt', name)
             and re.fullmatch('[a-f0-9]{64}', value), 'invalid_baseline_identity')
    for name, row in bundle['files'].items():
        data = row['content'].encode('utf-8')
        need(0 < len(data) <= 512 * 1024 and row['before'] == expected.get(name)
             and digest(data) == row['after'], 'invalid_module_identity')


def read_regular(path):
    need(path.is_file() and not path.is_symlink() and path.resolve(strict=True) == path
         and path.stat().st_nlink == 1, 'unsafe_runtime_file')
    return path.read_bytes()


def verify_base(root, expected, changes):
    need(root.is_dir() and root.resolve(strict=True) == root, 'unsafe_runtime_directory')
    for name, value in expected.items():
        need(digest(read_regular(root / name)) == value, 'runtime_changed_since_baseline')
    for name, row in changes.items():
        if row['before'] is None:
            need(not (root / name).exists() and not (root / name).is_symlink(),
                 'new_module_already_exists')


def replace_file(path, raw, template):
    metadata = template.stat()
    temporary = path.with_name(path.name + '.server-release-new')
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(temporary, flags, 0o600)
    try:
        with os.fdopen(fd, 'wb') as output:
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())
        if hasattr(os, 'chown'):
            os.chown(temporary, metadata.st_uid, metadata.st_gid)
        temporary.chmod(metadata.st_mode & 0o777)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def install(root, backup, changes, activate):
    """Stopped-service file transaction; restore all bytes if activation fails."""
    originals = {}
    for name, row in changes.items():
        path = root / name
        originals[name] = read_regular(path) if row['before'] is not None else None
        if originals[name] is not None:
            need(digest(originals[name]) == row['before'], 'module_changed_before_install')
            (backup / name).write_bytes(originals[name])
        else:
            need(not path.exists() and not path.is_symlink(), 'new_module_already_exists')
    written = []
    try:
        for name, row in changes.items():
            path = root / name
            replace_file(path, row['content'].encode('utf-8'), path if path.exists() else root / 'app.py')
            written.append(name)
        activate()
    except BaseException:
        for name in reversed(written):
            path = root / name
            if originals[name] is None:
                path.unlink()
            else:
                replace_file(path, originals[name], path)
        raise


def systemctl(*args):
    result = subprocess.run(['systemctl', *args], capture_output=True, timeout=60)
    need(result.returncode == 0, 'service_operation_failed')
    return result.stdout.decode().strip()


def request(path):
    req = urllib.request.Request(PUBLIC + path, headers={'Cache-Control': 'no-cache'})
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            raw = response.read(1024 * 1024 + 1)
            need(len(raw) <= 1024 * 1024, 'unexpected_public_response_size')
            return response.status, raw
    except urllib.error.HTTPError as error:
        return error.code, b''


def healthy():
    status, raw = request('/health')
    need(status == 200 and json.loads(raw) == {'status': 'ok'}, 'runtime_health_failed')
    need(request('/workspace/live?wait=0')[0] == 401, 'runtime_authentication_changed')
    for service in SERVICES:
        need(systemctl('is-active', service) == 'active', 'runtime_service_inactive')


def database_path():
    result = Path('/var/lib/analyst-ai/backend.db')
    for line in Path('/etc/analyst-ai/backend.env').read_text().splitlines():
        key, separator, value = line.partition('=')
        if key == 'DATABASE_PATH' and separator:
            fields = shlex.split(value)
            need(len(fields) == 1, 'invalid_database_configuration')
            result = Path(fields[0])
    need(result.is_file() and not result.is_symlink() and result.resolve(strict=True) == result
         and result.is_relative_to('/var/lib/analyst-ai'), 'unsafe_database_location')
    return result


def run(envelope):
    import fcntl
    need(os.getuid() == 0, 'runtime_deployment_identity_required')
    bundle = envelope['payload']
    validate(bundle)
    root = Path('/opt/analyst-ai/backend')
    run_id = envelope['run_id']
    need(re.fullmatch('[0-9]{8,20}', run_id), 'invalid_run_id')
    archive = Path('/var/lib/analyst-ai-build/development') / ('server-runtime-' + run_id)
    with Path('/var/lock/analyst-ai-plan-development.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        verify_base(root, bundle['expected'], bundle['files'])
        healthy()
        policy_path = '/client/update-policy?package_name=ru.omnicio.app.debug'
        policy_status, policy_before = request(policy_path)
        need(policy_status == 200, 'apk_policy_unavailable')
        old_pids = {service: systemctl('show', service, '--property=MainPID', '--value')
                    for service in SERVICES}
        database = database_path()
        archive.mkdir(mode=0o700)
        backup = archive / 'previous-source'
        backup.mkdir(mode=0o700)
        (archive / 'source-bundle.json').write_text(json.dumps(bundle), encoding='utf-8')
        systemctl('stop', *SERVICES)
        try:
            verify_base(root, bundle['expected'], bundle['files'])
            with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as source:
                with closing(sqlite3.connect(archive / 'before.sqlite3')) as target:
                    source.backup(target)
            (archive / 'before.sqlite3').chmod(0o600)

            def activate():
                for name, row in bundle['files'].items():
                    need(digest(read_regular(root / name)) == row['after'],
                         'installed_source_verification_failed')
                systemctl('start', *SERVICES)
                try:
                    for attempt in range(8):
                        try:
                            healthy()
                            break
                        except (RuntimeError, urllib.error.URLError):
                            if attempt == 7:
                                raise
                            time.sleep(2)
                    for service in SERVICES:
                        need(systemctl('show', service, '--property=MainPID', '--value') not in {'0', old_pids[service]},
                             'runtime_process_not_replaced')
                    need(request('/workspace/version')[0] == 401, 'version_endpoint_authentication_changed')
                    need(request(policy_path) == (policy_status, policy_before), 'apk_policy_changed')
                except BaseException:
                    systemctl('stop', *SERVICES)
                    raise

            install(root, backup, bundle['files'], activate)
        except BaseException:
            systemctl('start', *SERVICES)
            healthy()
            (archive / 'failure.json').write_text(json.dumps({'status': 'failed', 'previous_service_restarted': True}))
            raise
        installed = {name: digest(read_regular(root / name)) for name in bundle['files']}
        need(all(installed[name] == row['after'] for name, row in bundle['files'].items()),
             'installed_source_verification_failed')
        receipt = {'schema': 1, 'status': 'deployed', 'server_id': 9417611,
                   'source_commit': bundle['source_commit'], 'test_run_id': bundle['run_id'],
                   'deployment_run_id': run_id, 'installed_sha256': installed,
                   'checked_at_utc': datetime.now(timezone.utc).isoformat(),
                   'health': 200, 'unauthenticated_live': 401, 'unauthenticated_version': 401,
                   'apk_policy_sha256': digest(policy_before), 'apk_changed': False,
                   'database_backup_created': True, 'tests_executed_on_timeweb': False,
                   'physical_phone_verified': False}
        (archive / 'deployment.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
        print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    try:
        run(ENVELOPE)
    except Exception as error:
        code = str(error)
        if re.fullmatch('[a-z_]{1,100}', code) is None:
            code = type(error).__name__
        print(json.dumps({'status': 'failed', 'code': code, 'server_id': 9417611}), flush=True)
        raise
