"""Verified Windows-to-WSL administrative launcher; secrets travel via WSLENV."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

HOST = 'LAPTOP-NPSGA016'
DISTRO = 'Ubuntu-24.04'
DEPENDENCY_SHA = 'cd1866ee944ccea2259669f4293379241fd4ee02'
LEASE_BLOB = 'c9626f3bf90b612a71b9bbf2954d0c134aa29b22'
CLAIM = Path('C:/actions-runner-2/_work/_tool/AnalystLinux/analyst-project-distribution.json')
SOURCE_FILES = ('tools/launch_owner55_ai_wsl.py', 'tools/owner55_ai_guest.py', 'tools/inspect_owner55_ai.py',
    'tools/provision_owner55_ai.py', 'tools/owner_ai_private_transport.py',
    'tools/owner_plan_transport_20261027.py', 'deploy/stage_owner55_ai.py',
    'tools/activate_owner55_ai.py', 'deploy/activate_owner55_ai.py')
DEPENDENCY_FILES = ('deploy/prepare_owner_vm.py', 'deploy/access_owner_vm.py',
    'tools/timeweb_ci_capacity.py', 'tools/timeweb_actions_probe.py', 'tools/timeweb_ci_catalog.py')
FORWARDED = ('TIMEWEB_CLOUD_TOKEN', 'OWNER_AI_PROVISION_REVIEW', 'OWNER_AI_ACTION',
    'OWNER_AI_EXPECTED_BUDGET_SOURCES', 'GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT', 'OWNER_AI_HOST_VERIFIED',
    'OWNER_AI_ACTIVATION_REVIEW', 'OWNER_AI_STAGED_KEY_ID', 'OWNER_AI_CREATION_RUN_ID')


def need(value, code):
    if not value:
        raise RuntimeError(code)


def regular(path):
    info = path.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= 2 * 1024**2
         and not getattr(info, 'st_file_attributes', 0) & 0x400
         and path.resolve(strict=True) == path, 'untrusted_launcher_source')
    return path.read_bytes()


def git(root, *arguments):
    result = subprocess.run(['git', *arguments], cwd=root, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30)
    need(result.returncode == 0, 'launcher_source_identity_unavailable')
    return result.stdout.decode('utf-8').strip()


def blob(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


def source_bundle(root):
    expected = os.environ.get('EXPECTED_AI_TOOLS_SHA', '')
    need(re.fullmatch('[a-f0-9]{40}', expected) and git(root, 'rev-parse', 'HEAD') == expected,
         'launcher_tools_commit_changed')
    dependency = root / '.transport-admin'
    need(git(dependency, 'rev-parse', 'HEAD') == DEPENDENCY_SHA, 'launcher_dependency_commit_changed')
    files = {}
    for checkout, prefix, paths in ((root, '', SOURCE_FILES),
                                  (dependency, '.transport-admin/', DEPENDENCY_FILES)):
        for name in paths:
            raw = regular(checkout / name)
            need(blob(raw) == git(checkout, 'rev-parse', 'HEAD:' + name), 'launcher_source_bytes_changed')
            files[prefix + name] = {'content': raw.decode('utf-8'), 'sha256': hashlib.sha256(raw).hexdigest()}
    return {'schema': 1, 'tools_commit': expected, 'dependency_commit': DEPENDENCY_SHA, 'files': files}


def guest_environment(source):
    names = {'SYSTEMROOT', 'WINDIR', 'PATH', 'PATHEXT', 'TEMP', 'TMP', 'USERPROFILE',
             'APPDATA', 'LOCALAPPDATA', 'PROGRAMDATA', 'COMSPEC'}
    result = {key: value for key, value in source.items() if key.upper() in names}
    for name in FORWARDED:
        need(name in source and isinstance(source[name], str), 'launcher_required_environment_missing')
        result[name] = source[name]
    result['OWNER_AI_HOST_VERIFIED'] = HOST + ':' + DISTRO
    result['WSLENV'] = ':'.join(name + '/u' for name in FORWARDED)
    return result


def running(root, env):
    result = subprocess.run(['wsl.exe', '--list', '--running', '--quiet'], cwd=root, env=env,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30)
    need(result.returncode == 0, 'launcher_wsl_inventory_failed')
    raw = result.stdout
    encoding = 'utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else ('utf-16-le' if b'\0' in raw else 'utf-8')
    return {line.strip() for line in raw.decode(encoding).splitlines()}


def main():
    need(sys.platform == 'win32' and os.environ.get('COMPUTERNAME') == HOST,
         'owner_windows_launcher_required')
    need(Path(os.environ['USERPROFILE']).name.casefold() == 'networkservice', 'owner_runner_profile_required')
    root = Path.cwd().resolve(strict=True)
    need(root.drive.upper() == 'C:', 'launcher_source_drive_invalid')
    claim = json.loads(regular(CLAIM))
    need(claim.get('host') == HOST and claim.get('distribution') == DISTRO and claim.get('completed_at'),
         'owner_existing_wsl_claim_required')
    lease_path = root / '.github/scripts/emulator_lease.py'
    need(blob(regular(lease_path)) == LEASE_BLOB, 'canonical_host_lease_changed')
    spec = importlib.util.spec_from_file_location('owner_ai_host_lease', lease_path)
    lease = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lease)
    envelope = json.dumps(source_bundle(root)).encode()
    token = os.environ.get('TIMEWEB_CLOUD_TOKEN', '')
    need(16 <= len(token) <= 8192 and not any(c.isspace() for c in token)
         and token.encode() not in envelope, 'protected_cloud_credential_required')
    environment = guest_environment({**os.environ, 'OWNER_AI_HOST_VERIFIED': HOST + ':' + DISTRO})
    guest = '/mnt/c/' + '/'.join((root / 'tools/owner55_ai_guest.py').parts[1:])
    output, exit_code, terminated = b'', 1, False
    with lease.exclusive_emulator():
        need(DISTRO not in running(root, environment), 'owner_wsl_already_in_use')
        try:
            result = subprocess.run(['wsl.exe', '--distribution', DISTRO, '--user', 'analyst-ci', '--exec',
                '/usr/bin/timeout', '--kill-after=10s', '900s', '/usr/bin/python3', '-I', guest],
                cwd=root, env=environment, input=envelope, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, timeout=930)
            output, exit_code = result.stdout, result.returncode
        finally:
            stopped = subprocess.run(['wsl.exe', '--terminate', DISTRO], cwd=root, env=environment,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
            terminated = stopped.returncode == 0 and DISTRO not in running(root, environment)
    # The guest validator permits only scalar receipt values and a bounded result.
    guest_spec = importlib.util.spec_from_file_location('owner_ai_guest_receipt', root / 'tools/owner55_ai_guest.py')
    guest_module = importlib.util.module_from_spec(guest_spec)
    guest_spec.loader.exec_module(guest_module)
    report = guest_module.validate_report(output, token)
    report['owned_wsl_stopped'] = terminated
    print(json.dumps(report), flush=True)
    need(exit_code == 0 and terminated and report['local_cleanup_succeeded']
         and report['status'] == 'completed' and report['exit_code'] == 0,
         'owner_ai_operation_requires_inspection')


if __name__ == '__main__':
    try:
        main()
    except BaseException:
        print(json.dumps({'status': 'requires_inspection', 'reason': 'owner_ai_launcher_failed',
                          'automatic_retry_permitted': False}), flush=True)
        raise SystemExit(1) from None
