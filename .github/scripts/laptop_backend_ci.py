"""Run exact-commit backend CI in the owner's existing Windows-hosted WSL."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tarfile
import xml.etree.ElementTree as ET
import zipfile


REPOSITORY = 'MishaGameHacking/omni-cio-gateway'
HOST = 'LAPTOP-NPSGA016'
DISTRIBUTION = 'Ubuntu-24.04'
LEASE_BLOB = 'c9626f3bf90b612a71b9bbf2954d0c134aa29b22'
CLAIM = Path('C:/actions-runner-2/_work/_tool/AnalystLinux/analyst-project-distribution.json')
GUEST_STEPS = ['validate-deploy-script', 'venv', 'requirements', 'dependencies',
               'dependency-versions', 'compile-backend', 'backend-full-suite', 'health-openapi']


def need(value, message):
    if not value:
        raise RuntimeError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def blob(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def regular(path):
    value = path.lstat()
    need(stat.S_ISREG(value.st_mode) and value.st_nlink == 1, 'nonregular_ci_file')
    need(not getattr(value, 'st_file_attributes', 0) & 0x400, 'reparse_ci_file')
    need(path.resolve(strict=True) == path, 'noncanonical_ci_file')
    return path.read_bytes()


def command(args, root, env, *, timeout=60):
    return subprocess.run(args, cwd=root, env=env, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          check=True, timeout=timeout).stdout


def test_command(args, root, env, output, *, timeout):
    try:
        with output.open('xb') as log:
            result = subprocess.run(args, cwd=root, env=env, stdin=subprocess.DEVNULL,
                                    stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
        need(result.returncode == 0, 'windows_test_step_failed:' + output.name)
        return sha(regular(output))
    finally:
        if output.is_file():
            print(output.read_text(encoding='utf-8', errors='replace')[-12000:], flush=True)


def inventory(root, identity, env):
    need(command(['git', 'rev-parse', 'HEAD'], root, env).decode().strip() == identity['tested_merge_sha'],
         'checkout_is_not_exact_event_merge')
    if identity['event_name'] == 'pull_request':
        # Raw commit headers retain parents even when checkout fetch-depth is 1.
        commit = command(['git', 'cat-file', 'commit', 'HEAD'], root, env)
        headers = commit.split(b'\n\n', 1)[0].splitlines()
        parents = [line[7:].decode('ascii') for line in headers if line.startswith(b'parent ')]
        need(parents == [identity['pr_base_sha'], identity['pr_head_sha']],
             'test_merge_does_not_bind_the_event_pr_head_and_base')
    need(not command(['git', 'status', '--porcelain', '--untracked-files=all'], root, env),
         'checkout_contains_changes_or_untracked_sources')
    result = []
    digest = hashlib.sha256()
    listing = command(['git', 'ls-tree', '-r', '-z', 'HEAD'], root, env)
    for entry in sorted(filter(None, listing.split(b'\0'))):
        entry_identity, encoded_name = entry.split(b'\t', 1)
        mode, kind, expected_blob = entry_identity.decode().split()
        name = encoded_name.decode('utf-8')
        path = PurePosixPath(name)
        need(not path.is_absolute() and '..' not in path.parts and '\\' not in name
             and ':' not in name and '.git' not in path.parts, 'unsafe_tracked_source_path')
        need(kind == 'blob' and mode in {'100644', '100755'}, 'linked_or_nonfile_source')
        need(not any(part.casefold() in {'.env', 'local.properties'} or
                     part.casefold().endswith(('.jks', '.keystore')) for part in path.parts),
             'private_configuration_is_not_a_test_input')
        data = regular(root / name)
        need(blob(data) == expected_blob, 'checkout_bytes_differ_from_commit:' + name)
        row = {'path': name, 'bytes': len(data), 'sha256': sha(data),
               'git_blob': expected_blob, 'mode': int(mode, 8) & 0o777}
        result.append(row)
        digest.update(encoded_name + b'\0' + row['sha256'].encode() + b'\0')
    need(result and sum(row['bytes'] for row in result) <= 512 * 1024**2,
         'empty_or_oversized_source_inventory')
    return {**identity, 'complete_source_sha256': digest.hexdigest(), 'files': result}


def guest_path(path):
    need(path.is_absolute() and path.drive.upper() == 'C:', 'unsupported_wsl_transport_drive')
    return '/mnt/c/' + '/'.join(path.parts[1:])


def running_distributions(root, env):
    raw = command(['wsl.exe', '--list', '--running', '--quiet'], root, env)
    encoding = 'utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else (
        'utf-16-le' if b'\0' in raw else 'utf-8')
    return {line.strip() for line in raw.decode(encoding).splitlines()}


def host_environment():
    # Tests do not inherit runner/GitHub, owner, broker, provider or signing secrets.
    names = {'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'PATH', 'PATHEXT', 'TEMP', 'TMP',
             'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'PROGRAMDATA', 'PROGRAMFILES',
             'PROGRAMFILES(X86)', 'COMMONPROGRAMFILES', 'SYSTEMDRIVE'}
    result = {key: value for key, value in os.environ.items() if key.upper() in names}
    result.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1',
                  PIP_CONFIG_FILE=os.devnull, PIP_DISABLE_PIP_VERSION_CHECK='1')
    return result


def read_evidence(archive):
    need(archive.is_file() and archive.stat().st_size <= 64 * 1024**2,
         'missing_or_oversized_linux_evidence')
    with zipfile.ZipFile(archive) as evidence:
        names = evidence.namelist()
        allowed = {'linux-test-report.json', 'backend-tests.xml', *(name + '.log' for name in GUEST_STEPS)}
        need(len(names) == len(set(names)) and set(names) <= allowed
             and sum(info.file_size for info in evidence.infolist()) <= 64 * 1024**2,
             'invalid_linux_evidence_inventory')
        for info in evidence.infolist():
            need(PurePosixPath(info.filename).name == info.filename
                 and '\\' not in info.filename and ':' not in info.filename
                 and not info.is_dir() and info.filename.endswith(('.json', '.log', '.xml'))
                 and info.file_size <= 64 * 1024**2, 'unsafe_linux_evidence_entry')
        return {name: evidence.read(name) for name in names}


def retain_evidence(archive, destination):
    entries = read_evidence(archive)
    destination.mkdir()
    for name, data in entries.items():
        with (destination / name).open('xb') as output:
            output.write(data)


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


def inspect_evidence(archive, manifest):
    entries = read_evidence(archive)
    report = json.loads(entries['linux-test-report.json'])
    need(all(report.get(key) == manifest[key] for key in
             ('event_name', 'tested_merge_sha', 'pr_head_sha', 'pr_base_sha')) and
         report['complete_source_sha256'] == manifest['complete_source_sha256'],
         'linux_evidence_is_not_exact_source')
    need(report['status'] == 'passed' and report['changed_sources'] == []
         and [row['name'] for row in report['steps']] == GUEST_STEPS
         and all(row['exit_code'] == 0 for row in report['steps']), 'linux_backend_gate_failed')
    for row in report['steps']:
        need(sha(entries[row['name'] + '.log']) == row['sha256'], 'linux_log_changed')
    need(sha(entries['backend-tests.xml']) == report['junit_sha256'], 'linux_junit_changed')
    validate_junit(entries['backend-tests.xml'])
    return report


def main():
    need(__debug__ and sys.platform == 'win32' and os.environ.get('COMPUTERNAME') == HOST,
         'backend_ci_requires_the_owner_windows_laptop')
    need(os.environ.get('RUNNER_OS') == 'Windows' and os.environ.get('RUNNER_ARCH') == 'X64'
         and os.environ.get('GITHUB_REPOSITORY') == REPOSITORY, 'wrong_backend_runner')
    identity = {'event_name': os.environ['GITHUB_EVENT_NAME'],
                'tested_merge_sha': os.environ['EXPECTED_TESTED_MERGE_SHA'],
                'pr_head_sha': os.environ['EXPECTED_PR_HEAD_SHA'],
                'pr_base_sha': os.environ['EXPECTED_PR_BASE_SHA']}
    run, attempt = os.environ['GITHUB_RUN_ID'], os.environ['GITHUB_RUN_ATTEMPT']
    need(re.fullmatch(r'[a-f0-9]{40}', identity['tested_merge_sha']) and re.fullmatch(r'[1-9]\d{0,19}', run)
         and re.fullmatch(r'[1-9]\d{0,4}', attempt), 'invalid_ci_identity')
    if identity['event_name'] == 'pull_request':
        need(all(re.fullmatch(r'[a-f0-9]{40}', identity[key]) for key in ('pr_head_sha', 'pr_base_sha')),
             'invalid_pr_source_identity')
    else:
        need(identity['event_name'] == 'push' and os.environ.get('GITHUB_REF') in {
                 'refs/heads/main', 'refs/heads/codex/server-runtime-2026-10-28'}
             and identity['pr_head_sha'] == identity['pr_base_sha'] == '', 'invalid_main_push_identity')
    root = Path(__file__).resolve().parents[2]
    workspace = Path(os.environ['GITHUB_WORKSPACE']).resolve(strict=True)
    need(root == workspace / ('backend-ci-' + run + '-' + attempt), 'wrong_run_owned_checkout')
    need(Path(os.environ['USERPROFILE']).name.casefold() == 'networkservice', 'wrong_service_profile')
    claim = json.loads(regular(CLAIM))
    need(claim.get('distribution') == DISTRIBUTION and claim.get('host') == HOST
         and claim.get('completed_at'), 'project_wsl_installation_is_not_verified')
    lease_path = root / '.github/scripts/emulator_lease.py'
    need(blob(regular(lease_path)) == LEASE_BLOB, 'canonical_host_lease_changed')
    spec = importlib.util.spec_from_file_location('backend_ci_emulator_lease', lease_path)
    lease = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lease)
    env = host_environment()
    state = Path(os.environ['RUNNER_TEMP']).resolve(strict=True) / ('backend-ci-' + run + '-' + attempt)
    need(not state.exists(), 'backend_ci_state_already_exists')
    state.mkdir()
    report = {'host': HOST, 'distribution': DISTRIBUTION, **identity,
              'status': 'failed', 'state': str(state), 'linux_root': '/opt/analyst-ci/runs/backend-' + run + '-' + attempt}
    try:
        with lease.exclusive_emulator():
            manifest = inventory(root, identity, env)
            report['complete_source_sha256'] = manifest['complete_source_sha256']
            report['python_source_audit_sha256'] = test_command(
                [sys.executable, '-I', '.github/scripts/audit_python_sources.py'],
                root, env, state / 'python-source-audit.log', timeout=180)
            report['sonar_helper_tests_sha256'] = test_command(
                ['node', '--test', '.github/scripts/require_clean_sonar.test.cjs'],
                root, env, state / 'sonar-helper-tests.log', timeout=120)
            report['backend_ci_regressions_sha256'] = test_command(
                [sys.executable, '.github/scripts/tests/test_laptop_backend_ci.py', '-v'],
                root, env, state / 'backend-ci-regressions.log', timeout=180)
            source = state / 'linux-source.tar'
            with tarfile.open(source, 'x') as archive:
                for row in manifest['files']:
                    data = regular(root / row['path'])
                    need(sha(data) == row['sha256'], 'source_changed_during_wsl_transport')
                    entry = tarfile.TarInfo(row['path'])
                    entry.size, entry.mode = len(data), row['mode']
                    archive.addfile(entry, io.BytesIO(data))
            manifest_path = state / 'linux-source-manifest.json'
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
            need(DISTRIBUTION not in running_distributions(root, env),
                 'project_wsl_is_already_running_under_another_or_interrupted_task')
            guest = root / '.github/scripts/laptop_backend_guest.py'
            destination = state / 'linux-evidence.zip'
            args = ['wsl.exe', '--distribution', DISTRIBUTION, '--user', 'analyst-ci', '--exec',
                    '/usr/bin/timeout', '--kill-after=15s', '1800s', '/usr/bin/python3', '-I',
                    guest_path(guest), guest_path(source), sha(regular(source)),
                    guest_path(manifest_path), sha(regular(manifest_path)), report['linux_root'],
                    guest_path(destination)]
            try:
                with (state / 'linux-backend.log').open('xb') as output:
                    subprocess.run(args, cwd=root, env=env, stdin=subprocess.DEVNULL,
                                   stdout=output, stderr=subprocess.STDOUT, check=True, timeout=1850)
            finally:
                # The lease is still held. This is the existing project-only distribution.
                try:
                    command(['wsl.exe', '--terminate', DISTRIBUTION], root, env, timeout=60)
                    need(DISTRIBUTION not in running_distributions(root, env), 'owned_wsl_did_not_stop')
                finally:
                    log = state / 'linux-backend.log'
                    if log.is_file():
                        print(log.read_text(encoding='utf-8', errors='replace')[-12000:], flush=True)
                    if destination.is_file():
                        retain_evidence(destination, state / 'guest-evidence')
            linux = inspect_evidence(destination, manifest)
            need(inventory(root, identity, env) == manifest, 'windows_source_changed_during_backend_ci')
            report.update(status='passed', linux=linux, evidence_sha256=sha(regular(destination)))
        with Path(os.environ['GITHUB_OUTPUT']).open('a', encoding='utf-8') as output:
            for key in ('tested_merge_sha', 'pr_head_sha', 'pr_base_sha'):
                output.write(key + '=' + identity[key] + '\n')
    except BaseException as error:
        report.update(status='failed', error_type=type(error).__name__, error=str(error)[:400])
        raise
    finally:
        (state / 'windows-backend-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print('BACKEND_WINDOWS_REPORT=' + json.dumps(report), flush=True)


if __name__ == '__main__':
    main()

