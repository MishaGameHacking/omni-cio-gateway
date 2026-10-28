"""Package exact laptop-verified backend changes without building an APK."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess

BASE = '5384abda0bf1b47a50ad136189eeab7e77d51dab'


def git(*args):
    return subprocess.check_output(['git', *args], timeout=60)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def baseline_inventory():
    names = git('ls-tree', '-r', '--name-only', BASE, 'backend').decode().splitlines()
    expected = {}
    for name in names:
        relative = Path(name).relative_to('backend').as_posix()
        if '/' not in relative and (relative.endswith('.py') or relative == 'requirements.txt'):
            expected[relative] = digest(git('show', BASE + ':' + name))
    return expected


def changed_modules(expected):
    changed = git('diff', '--name-status', BASE, 'HEAD', '--', 'backend').decode().splitlines()
    files = {}
    for line in changed:
        status, name = line.split('\t')
        if name.startswith('backend/tests/'):
            continue
        relative = Path(name).relative_to('backend').as_posix()
        if status not in {'A', 'M'} or '/' in relative or not relative.endswith('.py'):
            raise RuntimeError('deployment_scope_requires_separate_review')
        raw = Path(name).read_bytes()
        if raw != git('show', 'HEAD:' + name):
            raise RuntimeError('source_changed_after_verification')
        files[relative] = {'before': expected.get(relative), 'after': digest(raw),
                           'content': raw.decode('utf-8')}
    if not files or len(files) > 24:
        raise RuntimeError('invalid_release_size')
    return files


def main():
    if os.environ.get('COMPUTERNAME') != 'LAPTOP-NPSGA016':
        raise RuntimeError('owner_laptop_required')
    source = git('rev-parse', 'HEAD').decode().strip()
    if source != os.environ['GITHUB_SHA'] or git('status', '--porcelain'):
        raise RuntimeError('source_not_exact_clean_event')
    run, attempt = os.environ['GITHUB_RUN_ID'], os.environ['GITHUB_RUN_ATTEMPT']
    state = Path(os.environ['RUNNER_TEMP']) / ('backend-ci-' + run + '-' + attempt)
    report_bytes = (state / 'windows-backend-report.json').read_bytes()
    report = json.loads(report_bytes)
    if not (report['status'] == 'passed' and report['tested_merge_sha'] == source
            and report['host'] == 'LAPTOP-NPSGA016'
            and report['linux']['status'] == 'passed'
            and report['linux']['changed_sources'] == []):
        raise RuntimeError('exact_laptop_verification_required')
    expected = baseline_inventory()
    files = changed_modules(expected)
    bundle = {'schema': 1, 'base_commit': BASE, 'source_commit': source,
              'run_id': run, 'run_attempt': attempt, 'host': report['host'],
              'source_sha256': report['complete_source_sha256'],
              'verification_sha256': digest(report_bytes), 'expected': expected,
              'files': files, 'apk_changed': False}
    raw = (json.dumps(bundle, ensure_ascii=True, sort_keys=True) + '\n').encode()
    target = state / 'server-runtime.json'
    target.write_bytes(raw)
    with Path(os.environ['GITHUB_OUTPUT']).open('a', encoding='utf-8') as output:
        output.write('bundle_sha256=' + digest(raw) + '\n')
    print(json.dumps({'source_commit': source, 'bundle_sha256': digest(raw),
                      'changed_server_modules': sorted(files), 'apk_changed': False}))


if __name__ == '__main__':
    main()
