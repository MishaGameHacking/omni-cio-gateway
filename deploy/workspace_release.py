"""Install a laptop-verified server-only release on the existing Timeweb host."""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import base64
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import stat
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request
import zipfile

BASE = 'aad0a117074a1b083021f93ef9ff928102b95557'
WHEEL_SHA = 'c8ca4d9a360dbd5d4b9bb7a8389e2a9ae6a106bee722b496f918040ba2daa17e'
MODULES = {'volume_jobs.py', 'strategy_profiles.py', 'volume_purchases.py', 'volume_state.py', 'telegram_browser_app.py', 'app.py', 'volume_market.py', 'strategy_actions.py', 'strategy_construction.py', 'owner_app.py', 'strategy_activity.py', 'fund_policy.py', 'autonomous_controller.py', 'strategy_sales.py', 'portfolio_mandate.py', 'purchase_policy.py', 'strategy_yield.py'}
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


def dependency_entries(dependency):
    need(dependency['name'] == 'pypdf-6.21.3-py3-none-any.whl'
         and dependency['version'] == '6.21.3' and dependency['sha256'] == WHEEL_SHA,
         'unreviewed_pdf_dependency')
    raw = base64.b64decode(dependency['content_base64'], validate=True)
    need(len(raw) <= 1024 * 1024 and digest(raw) == WHEEL_SHA, 'pdf_dependency_digest_changed')
    with zipfile.ZipFile(io.BytesIO(raw)) as wheel:
        entries = wheel.infolist()
        need(len(entries) <= 300 and sum(item.file_size for item in entries) <= 8 * 1024**2,
             'pdf_dependency_size_invalid')
        result = {}
        for item in entries:
            path = PurePosixPath(item.filename)
            need(not path.is_absolute() and '..' not in path.parts and '\\' not in item.filename
                 and path.parts[0] in {'pypdf', 'pypdf-6.21.3.dist-info'}
                 and not stat.S_ISLNK(item.external_attr >> 16), 'pdf_dependency_path_invalid')
            if not item.is_dir():
                need(item.filename not in result, 'pdf_dependency_duplicate_path')
                result[item.filename] = wheel.read(item)
    need('pypdf/__init__.py' in result and 'pypdf-6.21.3.dist-info/METADATA' in result,
         'pdf_dependency_incomplete')
    return result


def install_dependency(root, entries):
    destination = root / '_osint_vendor'
    need(not destination.exists() and not destination.is_symlink(), 'pdf_dependency_already_present')
    destination.mkdir(mode=0o755)
    metadata = (root / 'app.py').stat()
    try:
        for relative, raw in entries.items():
            path = destination / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as output:
                output.write(raw)
            path.chmod(0o644)
            need(path.read_bytes() == raw, 'pdf_dependency_installed_bytes_changed')
        if hasattr(os, 'chown'):
            for path in [destination, *destination.rglob('*')]:
                os.chown(path, metadata.st_uid, metadata.st_gid)
                if path.is_dir():
                    path.chmod(0o755)
    except BaseException:
        shutil.rmtree(destination)
        raise
    return destination


def verify_dependency(root, entries):
    vendor = root / '_osint_vendor'
    need(vendor.is_dir() and not vendor.is_symlink(), 'pdf_dependency_missing')
    for relative, expected in entries.items():
        need(read_regular(vendor / relative) == expected, 'pdf_dependency_installed_bytes_changed')


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
    dependency = dependency_entries(bundle['pdf_dependency'])
    root = Path('/opt/analyst-ai/backend')
    run_id = envelope['run_id']
    need(re.fullmatch('[0-9]{8,20}', run_id), 'invalid_run_id')
    archive = Path('/var/lib/analyst-ai-build/development') / ('server-runtime-' + run_id)
    with Path('/var/lock/analyst-ai-plan-development.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        verify_base(root, bundle['expected'], bundle['files'])
        verify_dependency(root, dependency)
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
        vendor = None
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
                    need(request('/workspace/presentation')[0] == 401, 'presentation_endpoint_authentication_changed')
                    need(request('/workspace/osint/status')[0] == 401, 'osint_endpoint_authentication_changed')
                    need(request('/workspace/strategy')[0] == 401, 'strategy_endpoint_authentication_changed')
                    need(request('/automation/decisions')[0] == 401, 'decisions_endpoint_authentication_changed')
                    need(request('/automation/strategy-plan')[0] == 401, 'strategy_plan_authentication_changed')
                    need(request(policy_path) == (policy_status, policy_before), 'apk_policy_changed')
                except BaseException:
                    systemctl('stop', *SERVICES)
                    raise

            install(root, backup, bundle['files'], activate)
        except BaseException:
            if vendor is not None:
                shutil.rmtree(vendor)
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
                   'health': 200, 'unauthenticated_live': 401, 'unauthenticated_version': 401, 'unauthenticated_presentation': 401, 'unauthenticated_osint': 401, 'unauthenticated_strategy': 401, 'unauthenticated_decisions': 401,
                   'pdf_dependency_sha256': bundle['pdf_dependency']['sha256'],
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

