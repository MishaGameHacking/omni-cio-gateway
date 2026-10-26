"""Backend guest based on the verified N00 WSL test transport; never use live data."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile
import time
import xml.etree.ElementTree as ET
import zipfile


def need(value, message):
    if not value:
        raise RuntimeError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load_manifest(archive, archive_hash, manifest_path, manifest_hash):
    need(sha(Path(archive).read_bytes()) == archive_hash, 'linux_source_archive_changed')
    manifest_bytes = Path(manifest_path).read_bytes()
    need(sha(manifest_bytes) == manifest_hash, 'linux_source_manifest_changed')
    manifest = json.loads(manifest_bytes)
    need(re.fullmatch(r'[a-f0-9]{40}', manifest['tested_merge_sha']), 'invalid_test_merge_sha')
    if manifest['event_name'] == 'pull_request':
        need(all(re.fullmatch(r'[a-f0-9]{40}', manifest[key]) for key in ('pr_head_sha', 'pr_base_sha')),
             'invalid_pr_source_binding')
    else:
        need(manifest['event_name'] == 'push' and manifest['pr_head_sha'] == manifest['pr_base_sha'] == '',
             'invalid_main_push_binding')
    return manifest


def extract_source(archive, manifest, source):
    identities = {row['path']: row for row in manifest['files']}
    need(len(identities) == len(manifest['files']) and identities, 'duplicate_or_empty_source_manifest')
    with tarfile.open(archive) as archive_file:
        names = archive_file.getnames()
        need(len(names) == len(set(names)) and set(names) == set(identities), 'archive_source_inventory_mismatch')
        for member in archive_file:
            relative = PurePosixPath(member.name)
            need(member.isfile() and not relative.is_absolute() and '..' not in relative.parts
                 and '.git' not in relative.parts and '\\' not in member.name and ':' not in member.name,
                 'unsafe_source_archive_entry')
            row = identities[member.name]
            data = archive_file.extractfile(member).read()
            need(len(data) == row['bytes'] and sha(data) == row['sha256']
                 and row['mode'] in {0o644, 0o755}, 'archived_source_bytes_changed')
            target = source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            target.chmod(row['mode'])
    return identities


def validate_junit(data):
    tree = ET.fromstring(data)
    need(tree.tag in {'testsuite', 'testsuites'}, 'invalid_junit_root')
    suites = [tree] if tree.tag == 'testsuite' else list(tree.findall('testsuite'))
    need(suites and all(int(item.attrib['tests']) >= 0 and int(item.attrib.get('skipped', '0')) >= 0
                       and int(item.attrib['failures']) == int(item.attrib['errors']) == 0 for item in suites),
         'pytest_junit_is_not_a_complete_pass')
    need(sum(int(item.attrib['tests']) - int(item.attrib.get('skipped', '0')) for item in suites) > 0
         and any(case.find('skipped') is None for case in tree.iter('testcase'))
         and not list(tree.iter('failure')) and not list(tree.iter('error')),
         'pytest_junit_is_empty_skipped_or_failed')


def main():
    need(__debug__ and sys.platform == 'linux', 'wrong_linux_test_platform')
    import pwd
    need(os.getuid() >= 1000 and pwd.getpwuid(os.getuid()).pw_name == 'analyst-ci', 'wrong_linux_test_identity')
    need('microsoft-standard-WSL2' in os.uname().release and sys.version_info[:2] == (3, 12),
         'wrong_project_linux_runtime')
    release = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
    need(release.get('ID', '').strip('"') == 'ubuntu'
         and release.get('VERSION_ID', '').strip('"') == '24.04', 'wrong_linux_distribution')
    archive, archive_hash, manifest_path, manifest_hash, location, export_path = sys.argv[1:]
    manifest = load_manifest(archive, archive_hash, manifest_path, manifest_hash)
    root = Path(location)
    need(root.parent == Path('/opt/analyst-ci/runs') and root.parent.resolve(strict=True) == root.parent
         and re.fullmatch(r'backend-[1-9]\d{0,19}-[1-9]\d{0,4}', root.name)
         and not root.exists() and not root.is_symlink(), 'invalid_guest_run_root')
    root.mkdir(mode=0o700)
    source, evidence, home = root / 'checkout', root / 'evidence', root / 'home'
    for path in (source, evidence, home):
        path.mkdir(mode=0o700)
    identities = extract_source(archive, manifest, source)

    env = {'PATH': '/usr/bin:/bin', 'HOME': str(home), 'LANG': 'C.UTF-8', 'PYTHONUNBUFFERED': '1',
           'XDG_CONFIG_HOME': str(home / '.config'), 'XDG_CACHE_HOME': str(home / '.cache'),
           'TELEGRAM_CLIENT_ID': '123456', 'TELEGRAM_CLIENT_SECRET': 'test-only',
           'BACKEND_PUBLIC_URL': 'https://example.invalid',
           'TELEGRAM_REDIRECT_URI': 'https://example.invalid/auth/telegram/callback',
           'FERNET_KEY': 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=',
           'DATABASE_PATH': str(root / 'tests.sqlite3'), 'ANALYSIS_SCHEDULER_ENABLED': 'false',
           'AI_EXTERNAL_PROCESSING_APPROVED': 'false', 'PIP_CONFIG_FILE': '/dev/null',
           'PIP_DISABLE_PIP_VERSION_CHECK': '1'}
    report = {key: manifest[key] for key in ('event_name', 'tested_merge_sha', 'pr_head_sha', 'pr_base_sha')}
    report.update({'complete_source_sha256': manifest['complete_source_sha256'],
              'platform': sys.platform, 'python': sys.version, 'uid': os.getuid(),
              'kernel': os.uname().release, 'status': 'failed', 'steps': []})

    def run(name, args, timeout=900, *, database=None):
        print('LINUX_GUEST_STEP=' + name, flush=True)
        target = evidence / (name + '.log')
        started = time.monotonic()
        step_env = dict(env)
        if database is not None:
            step_env['DATABASE_PATH'] = str(database)
        with target.open('xb') as output:
            result = subprocess.run(args, cwd=source, env=step_env, stdin=subprocess.DEVNULL,
                                    stdout=output, stderr=subprocess.STDOUT, timeout=timeout)
        row = {'name': name, 'exit_code': result.returncode, 'seconds': round(time.monotonic() - started, 3),
               'sha256': sha(target.read_bytes())}
        report['steps'].append(row)
        print('LINUX_GUEST_RESULT=' + json.dumps(row), flush=True)
        print(target.read_text(errors='replace')[-9000:], flush=True)
        need(result.returncode == 0, 'linux_test_step_failed:' + name)

    try:
        run('validate-deploy-script', ['/bin/bash', '-n', '.github/scripts/deploy_timeweb_backend.sh'], 60)
        venv = root / 'venv'
        py = str(venv / 'bin/python')
        run('venv', [sys.executable, '-m', 'venv', str(venv)], 120)
        run('requirements', [py, '-m', 'pip', '--require-virtualenv', 'install', '--no-input', '--no-cache-dir',
                             '--index-url', 'https://pypi.org/simple', '-r', 'backend/requirements-dev.txt'])
        run('dependencies', [py, '-m', 'pip', 'check'])
        run('dependency-versions', [py, '-m', 'pip', 'freeze', '--all'])
        run('compile-backend', [py, '-m', 'compileall', '-q', 'backend'])
        junit = evidence / 'backend-tests.xml'
        run('backend-full-suite', [py, '-m', 'pytest', 'backend/tests', '-q', '--junitxml=' + str(junit)], 1200)
        validate_junit(junit.read_bytes())
        report['junit_sha256'] = sha(junit.read_bytes())
        smoke = """from fastapi.testclient import TestClient
from backend.app import app
with TestClient(app) as client:
    health = client.get('/health')
    assert health.status_code == 200 and health.json() == {'status': 'ok'}
    assert client.get('/openapi.json').status_code == 200
print('HEALTH_OPENAPI=passed')
"""
        run('health-openapi', [py, '-c', smoke], 120, database=root / 'health.sqlite3')
        report['status'] = 'passed'
    except BaseException as error:
        report.update(status='failed', error_type=type(error).__name__, error=str(error)[:400])
        raise
    finally:
        changed = [name for name, row in identities.items() if not (source / name).is_file()
                   or (source / name).is_symlink() or sha((source / name).read_bytes()) != row['sha256']]
        report['changed_sources'] = changed
        if changed:
            report['status'] = 'failed_integrity'
        (evidence / 'linux-test-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        with zipfile.ZipFile(export_path, 'x', compression=zipfile.ZIP_DEFLATED) as output:
            for path in evidence.iterdir():
                output.write(path, path.name)
        print('LINUX_TEST_REPORT=' + json.dumps(report), flush=True)
        need(not changed, 'source_files_changed_during_linux_checks')


if __name__ == '__main__':
    main()
