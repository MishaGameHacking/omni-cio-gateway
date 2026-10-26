"""Deploy exactly three Windows-tested HTML/CSS sources to the pinned owner service.

This payload is a future administrative action, not a local application runner.
It never imports the application, opens a database/configuration secret, installs
dependencies, calls trading/model endpoints, or publishes/installs an APK.
"""
from __future__ import annotations

import datetime
import fcntl
import hashlib
import http.client
import json
import os
from pathlib import Path, PurePosixPath
import pwd
import re
import selectors
import shlex
import signal
import stat
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET
import zipfile

EXPECTED = {}
SOURCE_ROOT = Path('/opt/analyst-ai/backend')
STORE = Path('/opt/analyst-ai/.single_style47-web-deployment')
SERVICES = ('analyst-ai-owner.service', 'analyst-ai-updates.service')
WORKDIRS = frozenset(('/opt/analyst-ai', '/opt/analyst-ai/backend', '/opt/analyst-ai-updates'))
MODULES = frozenset(('owner_app:create_app', 'backend.owner_app:create_app', 'app:app', 'backend.app:app',
                    'telegram_browser_app:app', 'backend.telegram_browser_app:app',
                    'backend.public_updates_app:create_app', 'public_updates_app:create_app'))
EXECUTABLES = frozenset(root + '/venv/bin/' + name for root in ('/opt/analyst-ai', '/opt/analyst-ai-updates')
                       for name in ('python', 'python3', 'uvicorn'))
PROPERTIES = ('ExecStart', 'WorkingDirectory', 'FragmentPath', 'DropInPaths',
              'LoadState', 'ActiveState', 'NeedDaemonReload')

# COMMON_HELPERS
# PUBLIC_CHECKS


def encoded(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + '\n').encode('ascii')


def parsed(raw):
    value = json.loads(raw, object_pairs_hook=unique)
    need(type(value) is dict, 'unexpected_json_root')
    return value


def safe_relative(name):
    need(type(name) is str and 0 < len(name) <= 1024 and '\\' not in name and ':' not in name
         and '\0' not in name and '\n' not in name and '\r' not in name, 'unsafe_archive_member')
    relative = PurePosixPath(name)
    need(not relative.is_absolute() and relative.as_posix() == name and
         not any(part in ('.', '..') for part in relative.parts), 'unsafe_archive_member')


def inventory_checked(raw):
    value = parsed(raw)
    need(set(value) == {'files', 'source_sha256', 'complete_source_sha256'} and
         1 <= len(value['files']) <= 20000, 'wrong_source_inventory')
    code, complete, seen = hashlib.sha256(), hashlib.sha256(), set()
    for name, item in sorted(value['files'].items(), key=lambda row: row[0].encode('utf-8')):
        safe_relative(name)
        need(name.casefold() not in seen and set(item) == {'bytes', 'sha256'}
             and type(item['bytes']) is int and 0 <= item['bytes'] <= 128 * 1024**2
             and re.fullmatch('[a-f0-9]{64}', item['sha256']), 'invalid_source_inventory_identity')
        seen.add(name.casefold())
        record = name.encode('utf-8') + b'\0' + item['sha256'].encode('ascii') + b'\0'
        complete.update(record)
        if name not in ('AGENTS.md', 'README.md') and not name.startswith('docs/'):
            code.update(record)
    need(value['source_sha256'] == EXPECTED['source_sha256'] == code.hexdigest() and
         value['complete_source_sha256'] == EXPECTED['complete_source_sha256'] == complete.hexdigest(),
         'build_inventory_digest_changed')
    return value


def archive_inputs():
    archive = Path(EXPECTED['archive_path'])
    special = Path('/var/lib/analyst-ai-build')
    for parent in reversed(archive.parents):
        info = parent.lstat()
        owners = {0, pwd.getpwnam('analyst-build').pw_uid} if parent == special else {0}
        need(stat.S_ISDIR(info.st_mode) and parent.resolve(strict=True) == parent and
             info.st_uid in owners and not info.st_mode & 0o022, 'untrusted_build_archive_parent')
    before = archive.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_uid == 0 and before.st_nlink == 1 and
         not before.st_mode & 0o022 and before.st_size == EXPECTED['archive']['bytes'], 'wrong_build_archive_file')
    with os.fdopen(os.open(archive, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        need(stable(os.fstat(stream.fileno())) == stable(before), 'build_archive_replaced')
        digest_value, count = hashlib.sha256(), 0
        for block in iter(lambda: stream.read(1024**2), b''):
            count += len(block)
            need(count <= EXPECTED['archive']['bytes'], 'build_archive_grew')
            digest_value.update(block)
        need(count == before.st_size and digest_value.hexdigest() == EXPECTED['archive']['sha256'],
             'full_build_archive_digest_changed')
        stream.seek(0)
        with zipfile.ZipFile(stream) as bundle:
            entries = bundle.infolist()
            names = [entry.filename for entry in entries]
            need(len(entries) <= 20000 and len(names) == len(set(names)) and
                 sum(entry.file_size for entry in entries) <= 490 * 1024**2, 'invalid_build_archive_inventory')
            for entry in entries:
                safe_relative(entry.filename)
                need(not entry.is_dir() and not entry.flag_bits & 1 and
                     stat.S_IFMT(entry.external_attr >> 16) in (0, stat.S_IFREG), 'unsafe_build_archive_type')

            def member(name, limit, files=None):
                row = bundle.getinfo(name)
                need(row.file_size <= limit, 'selected_archive_member_too_large')
                with bundle.open(row) as source:
                    raw = source.read(limit + 1)
                need(len(raw) == row.file_size <= limit, 'archive_member_truncated')
                if files is not None:
                    need(files[name] == identity(raw), 'archive_member_envelope_mismatch')
                return raw

            envelope = parsed(member('windows-development-envelope.json', 8 * 1024**2))
            need(envelope['schema'] == 1 and envelope['kind'] == 'windows_check_build_source_archive' and
                 envelope['base_commit'] == EXPECTED['base_commit'] and
                 envelope['source_sha256'] == EXPECTED['source_sha256'] and
                 envelope['complete_source_sha256'] == EXPECTED['complete_source_sha256'] and
                 all(envelope[key] is False for key in ('runtime_pass', 'publication_authorized', 'phone_verified')),
                 'wrong_build_archive_envelope')
            files = envelope['files']
            need(set(files) == set(names) - {'windows-development-envelope.json'} and
                 len(files) == EXPECTED['archive_files'], 'build_envelope_inventory_changed')
            for name, item in files.items():
                need(set(item) == {'bytes', 'sha256'} and item['bytes'] == bundle.getinfo(name).file_size and
                     re.fullmatch('[a-f0-9]{64}', item['sha256']), 'invalid_build_envelope_identity')
            actual = {}
            for key, name in (('build_report', 'windows-development.json'), ('build_controller', 'controller.json'),
                              ('source_inventory', 'source-final.json')):
                raw = member('evidence/' + name, 8 * 1024**2, files)
                need(identity(raw) == EXPECTED[key], 'wrong_original_build_evidence')
                actual[key] = parsed(raw)
            need(actual['build_report'] == envelope['report'] and actual['build_controller'] == envelope['controller'],
                 'archive_envelope_report_conflict')
            report = actual['build_report']
            need(report['status'] == 'passed_check_and_build_only' and report['github'] == EXPECTED['github'] and
                 report['source_sha256'] == report['source_sha256_after'] == EXPECTED['source_sha256'],
                 'archive_build_identity_or_status_changed')
            inventory = inventory_checked(member('evidence/source-final.json', 8 * 1024**2, files))
            need({'source/' + name: value for name, value in inventory['files'].items()} ==
                 {name: value for name, value in files.items() if name.startswith('source/')},
                 'archive_source_inventory_disagrees')
            linux = parsed(member('evidence/linux-linux-test-report.json', 2 * 1024**2, files))
            need(linux['source_sha256'] == EXPECTED['source_sha256'] and linux['status'] == 'passed' and
                 linux['changed_sources'] == [] and linux['platform'] == 'linux' and
                 {'compile-backend', 'backend-full-suite', 'health-openapi'} <= {row['name'] for row in linux['steps']} and
                 all(type(row['exit_code']) is int and row['exit_code'] == 0 for row in linux['steps']),
                 'real_backend_test_run_not_passed')
            junit_raw = member('evidence/linux-backend-tests.xml', 32 * 1024**2, files)
            need(b'<!DOCTYPE' not in junit_raw.upper() and b'<!ENTITY' not in junit_raw.upper(), 'junit_declarations_not_allowed')
            tree = ET.fromstring(junit_raw)
            need(tree.tag in ('testsuite', 'testsuites') and not tree.findall('.//failure') and not tree.findall('.//error'),
                 'archived_backend_tests_failed')
            suites = list(tree.iter('testsuite'))
            need(suites and all(int(suite.get('errors', '-1')) == int(suite.get('failures', '-1')) == 0 and
                 int(suite.get('tests', '0')) > 0 for suite in suites), 'archived_backend_junit_counters_failed')
            cases = [case for case in tree.iter('testcase') if case.get('classname') in {
                'backend.tests.test_owned_web_theme.OwnedWebThemeTests', 'test_owned_web_theme.OwnedWebThemeTests'}]
            need(len(cases) == len(EXPECTED['web_test_names']) and
                 {case.get('name') for case in cases} == set(EXPECTED['web_test_names']) and
                 all(case.find('skipped') is None for case in cases), 'six_actual_html_security_tests_missing_or_skipped')
            test_raw = member('source/backend/tests/test_owned_web_theme.py', 2 * 1024**2, files)
            need(identity(test_raw) == EXPECTED['web_test_source'], 'tested_html_contract_source_changed')
            desired = {}
            for name, row in EXPECTED['web_sources'].items():
                raw = member('source/backend/' + name, 2 * 1024**2, files)
                need(identity(raw) == row['new'], 'tested_web_source_changed')
                desired[name] = raw
        need(stable(os.fstat(stream.fileno())) == stable(before) == stable(archive.lstat()),
             'build_archive_changed_during_read')
    return desired, {'original_html_test_count': len(cases), 'original_backend_junit': identity(junit_raw),
                     'original_linux_report': files['evidence/linux-linux-test-report.json']}


def trusted_directory(path, create=False):
    if create and not path.exists():
        os.mkdir(path, 0o700)
    for item in (path, *path.parents):
        info = item.lstat()
        need(stat.S_ISDIR(info.st_mode) and item.resolve(strict=True) == item and info.st_uid == 0 and
             not info.st_mode & 0o022, 'untrusted_deployment_directory')
    if path == STORE or STORE in path.parents:
        need(not path.stat().st_mode & 0o077, 'deployment_backup_directory_must_be_root_only')
    return path.stat()


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def create_file(path, raw, metadata=None):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        if metadata is not None:
            os.fchown(stream.fileno(), metadata['uid'], metadata['gid'])
            os.fchmod(stream.fileno(), metadata['mode'])
        os.fsync(stream.fileno())
    need(identity(trusted_read(path, 2 * 1024**2)) == identity(raw), 'staged_file_readback_failed')


def write_journal(folder, value):
    temporary = folder / ('journal-' + uuid.uuid4().hex + '.tmp')
    create_file(temporary, encoded(value))
    os.replace(temporary, folder / 'journal.json')
    sync_directory(folder)


def source_identities():
    return {name: identity(trusted_read(SOURCE_ROOT / name, 2 * 1024**2)) for name in EXPECTED['web_sources']}


def service_binding(service, *, required_active):
    observed = service_observation(service)
    expected = dict(EXPECTED['services'][service])
    if not required_active:
        need(observed.get('active_state') in {'active', 'inactive', 'failed', 'activating', 'deactivating'},
             'owner_service_state_unknown')
        expected['active_state'] = observed['active_state']
    need(observed == expected, 'effective_service_binding_changed')


def safeguards(*, owner_active):
    for name, expected in EXPECTED['untouched_sources'].items():
        need(identity(trusted_read(Path(name), 2 * 1024**2)) == expected, 'unrelated_runtime_source_changed')
    need(identity(trusted_read(Path('/etc/caddy/Caddyfile'), 128 * 1024)) == EXPECTED['caddy_file'],
         'caddy_file_changed')
    metadata, _ = active_caddy()
    need(metadata == {'status': 'observed', **EXPECTED['active_caddy']}, 'active_caddy_changed')
    for service in SERVICES:
        service_binding(service, required_active=(service != SERVICES[0] or owner_active))


def service_pid(name):
    need(name in SERVICES, 'unexpected_service_pid')
    result = subprocess.run(['systemctl', 'show', name, '--property=MainPID', '--value'], stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=5, check=False)
    need(result.returncode == 0 and len(result.stdout) <= 32 and re.fullmatch(rb'[0-9]+\n?', result.stdout),
         'service_pid_unavailable')
    return int(result.stdout)


def owner_action(action):
    need(action in {'stop', 'start'}, 'owner_action_not_allowlisted')
    result = subprocess.run(['systemctl', action, SERVICES[0]], stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=45, check=False)
    need(result.returncode == 0, 'owner_' + action + '_failed')
    if action == 'stop':
        need(service_pid(SERVICES[0]) == 0, 'owner_did_not_stop')


def local_health():
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        connection = http.client.HTTPConnection('127.0.0.1', 8080, timeout=2)
        try:
            connection.request('GET', '/health')
            response = connection.getresponse()
            raw = response.read(1025)
            if response.status == 200 and len(raw) <= 1024 and json.loads(raw) == {'status': 'ok'}:
                return
        except (OSError, ValueError, http.client.HTTPException):
            pass
        finally:
            connection.close()
        time.sleep(0.5)
    raise ObservationError('local_owner_health_failed')


def replace_sources(folder, sources, metadata):
    need(folder.stat().st_dev == SOURCE_ROOT.stat().st_dev, 'stage_not_on_source_filesystem')
    staged = {}
    for name, raw in sources.items():
        path = folder / ('stage-' + uuid.uuid4().hex + '-' + name)
        create_file(path, raw, metadata[name])
        staged[name] = path
    for name, path in staged.items():
        current = identity(trusted_read(SOURCE_ROOT / name, 2 * 1024**2))
        need(current in (EXPECTED['web_sources'][name]['old'], EXPECTED['web_sources'][name]['new']),
             'source_replacement_would_overwrite_unrelated_bytes')
        os.replace(path, SOURCE_ROOT / name)
        sync_directory(SOURCE_ROOT)
    need(source_identities() == {name: identity(raw) for name, raw in sources.items()}, 'replaced_source_readback_failed')
    for name, old in metadata.items():
        info = (SOURCE_ROOT / name).lstat()
        need({'uid': info.st_uid, 'gid': info.st_gid, 'mode': stat.S_IMODE(info.st_mode)} == old,
             'source_ownership_or_mode_changed')


def rollback(folder, journal):
    old = {name: trusted_read(folder / ('original-' + name), 2 * 1024**2) for name in EXPECTED['web_sources']}
    need(all(identity(raw) == EXPECTED['web_sources'][name]['old'] for name, raw in old.items()),
         'rollback_bytes_not_original_runtime')
    current = source_identities()
    need(all(current[name] in (row['old'], row['new']) for name, row in EXPECTED['web_sources'].items()),
         'rollback_would_overwrite_unrelated_source')
    # A Caddy outage or update-service verification failure must not suppress
    # restoration of this transaction's original source bytes. Only the exact
    # owner unit/invocation and owned file identities gate the restore itself.
    service_binding(SERVICES[0], required_active=False)
    owner_action('stop')
    replace_sources(folder, old, journal['metadata'])
    owner_action('start')
    local_health()
    service_binding(SERVICES[0], required_active=True)
    public_verified = False
    try:
        public_check(expected_policy=journal['original_policy_sha256'])
        public_verified = True
    except (ObservationError, OSError, ValueError, http.client.HTTPException):
        pass
    journal.update(phase='rolled_back', rollback_succeeded=True, rollback_public_verified=public_verified,
                   completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
    write_journal(folder, journal)
    return public_verified


def deploy_locked(folder, desired, build_evidence):
    expected_old = {name: row['old'] for name, row in EXPECTED['web_sources'].items()}
    expected_new = {name: row['new'] for name, row in EXPECTED['web_sources'].items()}
    binding = {key: EXPECTED[key] for key in ('source_sha256', 'source_backup_commit', 'archive', 'build_report')}
    journal_path = folder / 'journal.json'
    if journal_path.exists():
        journal = parsed(trusted_read(journal_path, 65536))
        need(journal['schema'] == 1 and journal['binding'] == binding and
             set(journal['metadata']) == set(expected_old), 'foreign_or_invalid_deployment_journal')
        for metadata in journal['metadata'].values():
            need(set(metadata) == {'uid', 'gid', 'mode'} and metadata['uid'] == 0 and
                 type(metadata['gid']) is int and metadata['gid'] >= 0 and
                 metadata['mode'] in (0o644, 0o640), 'invalid_original_source_metadata')
        if journal['phase'] == 'committed':
            need(source_identities() == expected_new, 'committed_theme_source_changed')
            safeguards(owner_active=True)
            public = public_check(expected_style=EXPECTED['callback_style_sha256'])
            return receipt('already_deployed_verified', build_evidence, public, True)
        need(journal['phase'] in {'prepared', 'installing', 'verifying', 'rolled_back', 'rollback_failed'},
             'unknown_deployment_phase')
        # A retry resumes only this exact transaction. Never accept a random
        # mixed source tree as a usable starting state.
        if journal['phase'] != 'rolled_back':
            # Recovery is already a restoration path. Keep it protected against
            # a second interrupt just like the ordinary failure restoration.
            for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
                signal.signal(signum, signal.SIG_IGN)
            try:
                rollback(folder, journal)
            finally:
                for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
                    signal.signal(signum, interrupted)
        need(source_identities() == expected_old, 'rollback_did_not_restore_old_source')
    else:
        need(source_identities() == expected_old, 'current_runtime_not_exact_observed44')
        safeguards(owner_active=True)
        previous = public_check()
        metadata = {}
        for name, item in expected_old.items():
            path = SOURCE_ROOT / name
            raw = trusted_read(path, 2 * 1024**2)
            need(identity(raw) == item, 'source_changed_before_backup')
            info = path.lstat()
            need(info.st_uid == 0 and stat.S_IMODE(info.st_mode) in (0o644, 0o640),
                 'runtime_source_metadata_not_expected')
            metadata[name] = {'uid': info.st_uid, 'gid': info.st_gid, 'mode': stat.S_IMODE(info.st_mode)}
            backup = folder / ('original-' + name)
            if backup.exists():
                need(identity(trusted_read(backup, 2 * 1024**2)) == item, 'partial_backup_differs')
            else:
                create_file(backup, raw)
        journal = {'schema': 1, 'binding': binding, 'metadata': metadata, 'phase': 'prepared',
                   'original_policy_sha256': previous['update_policy_sha256'], 'rollback_succeeded': False}
        write_journal(folder, journal)
    safeguards(owner_active=True)
    public_check(expected_policy=journal['original_policy_sha256'])
    updates_pid = service_pid(SERVICES[1])
    need(updates_pid > 0, 'update_service_not_running')
    try:
        journal.update(phase='installing', rollback_succeeded=False)
        write_journal(folder, journal)
        owner_action('stop')
        need(source_identities() == expected_old, 'old_source_changed_after_stop')
        replace_sources(folder, desired, journal['metadata'])
        journal['phase'] = 'verifying'
        write_journal(folder, journal)
        owner_action('start')
        local_health()
        safeguards(owner_active=True)
        need(service_pid(SERVICES[1]) == updates_pid, 'update_service_changed_during_deployment')
        public = public_check(expected_style=EXPECTED['callback_style_sha256'],
                              expected_policy=journal['original_policy_sha256'])
        journal.update(phase='committed', completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
        write_journal(folder, journal)
        return receipt('deployed_verified', build_evidence, public, False)
    except BaseException:
        # Do not permit a second interrupt to truncate the owned restoration.
        for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            signal.signal(signum, signal.SIG_IGN)
        try:
            public_verified = rollback(folder, journal)
        except BaseException:
            journal['phase'] = 'rollback_failed'
            try:
                write_journal(folder, journal)
            except BaseException:
                pass
            raise ObservationError('deployment_failed_rollback_requires_review') from None
        code = ('deployment_failed_original_sources_restored' if public_verified else
                'deployment_failed_original_sources_restored_public_unverified')
        raise ObservationError(code) from None


def receipt(status, evidence, public, idempotent):
    return {'schema': 1, 'kind': 'single_style47_exact_three_file_web_deployment', 'status': status,
            'runtime_server_id': 9417611, 'public_host': PUBLIC_HOST,
            'source_sha256': EXPECTED['source_sha256'], 'source_backup_commit': EXPECTED['source_backup_commit'],
            'archive': EXPECTED['archive'], 'build_report': EXPECTED['build_report'],
            'web_sources': {name: row['new'] for name, row in EXPECTED['web_sources'].items()},
            'observed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'full_windows_check_and_build_passed': True, 'actual_html_test_evidence': evidence,
            'public': public, 'idempotent_verification': idempotent,
            'owner_service_restart_performed': not idempotent,
            'other_services_restarted_by_deployer': False, 'caddy_or_service_configuration_changed': False,
            'database_or_environment_files_opened_by_deployer': False,
            'normal_owner_startup_has_possible_database_effects': True,
            'help_deployed': False, 'dependencies_changed': False, 'apk_published_or_installed': False,
            'trading_or_model_routes_called': False, 'physical_phone_verified': False,
            'full_android_runtime_matrix_passed': False}


def main():
    need(__debug__ and sys.platform == 'linux' and os.geteuid() == 0, 'pinned_linux_root_transport_required')
    need(set(EXPECTED['web_sources']) == {'app.py', 'telegram_browser_app.py', 'owner_app.py'}, 'deployment_scope_changed')
    desired, evidence = archive_inputs()
    trusted_directory(SOURCE_ROOT)
    trusted_directory(STORE, create=True)
    lock_path = STORE / 'deployment.lock'
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'r+b') as lock:
        info = os.fstat(lock.fileno())
        need(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_nlink == 1 and
             not info.st_mode & 0o077 and stable(info) == stable(lock_path.lstat()), 'unsafe_deployment_lock')
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        folder = STORE / EXPECTED['source_sha256']
        trusted_directory(folder, create=True)
        result = deploy_locked(folder, desired, evidence)
        print(json.dumps(result, ensure_ascii=True, sort_keys=True), flush=True)


def interrupted(signum, frame):
    raise ObservationError('administrative_transport_interrupted')


if __name__ == '__main__':
    for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(signum, interrupted)
    try:
        main()
    except BaseException as error:
        # No traceback, subprocess text, config, file body, credentials or URL
        # parameters may escape. ObservationError messages are finite literals.
        code = str(error) if isinstance(error, ObservationError) else 'bounded_web_deployment_failed'
        print(json.dumps({'schema': 1, 'kind': 'single_style47_web_deployment_failure', 'code': code}), flush=True)
        # Return the bounded failure JSON through the existing capture transport.
        # The hosted receiver persists it and requires a successful receipt; it
        # explicitly fails the workflow for this kind. No success is inferred
        # from the transport exit status.
