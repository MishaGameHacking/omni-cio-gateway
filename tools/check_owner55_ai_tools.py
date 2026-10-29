"""Run synthetic AI administration checks inside the owner's existing WSL."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.github/scripts'))
import emulator_lease


def main():
    if sys.platform != 'win32' or os.environ.get('COMPUTERNAME') != 'LAPTOP-NPSGA016':
        raise RuntimeError('owner_laptop_required')
    raw = (ROOT / '.github/scripts/emulator_lease.py').read_bytes()
    if hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() != 'c9626f3bf90b612a71b9bbf2954d0c134aa29b22':
        raise RuntimeError('canonical_host_lease_changed')
    claim = json.loads(Path('C:/actions-runner-2/_work/_tool/AnalystLinux/analyst-project-distribution.json').read_text())
    if claim.get('distribution') != 'Ubuntu-24.04' or claim.get('host') != 'LAPTOP-NPSGA016' or not claim.get('completed_at'):
        raise RuntimeError('project_distribution_identity_changed')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if commit != os.environ.get('GITHUB_SHA') or ROOT.drive.upper() != 'C:':
        raise RuntimeError('reviewed_source_identity_changed')
    linux_script = '/mnt/c/' + '/'.join(ROOT.parts[1:]) + '/tools/run_owner55_ai_tests.py'
    environment = {key: value for key, value in os.environ.items() if key.upper() in {
        'SYSTEMROOT', 'WINDIR', 'PATH', 'PATHEXT', 'TEMP', 'TMP', 'USERPROFILE', 'COMPUTERNAME',
        'LOCALAPPDATA', 'APPDATA', 'PROGRAMDATA', 'COMSPEC'}}
    with emulator_lease.exclusive_emulator():
        try:
            subprocess.run(['wsl.exe', '--distribution', 'Ubuntu-24.04', '--user', 'analyst-ci', '--exec',
                '/usr/bin/env', '-i', 'PATH=/usr/bin:/bin', 'LANG=C.UTF-8',
                '/usr/bin/timeout', '--kill-after=5s', '120s', '/usr/bin/python3', '-I', linux_script],
                cwd=ROOT, env=environment, stdin=subprocess.DEVNULL, check=True, timeout=150)
        finally:
            subprocess.run(['wsl.exe', '--terminate', 'Ubuntu-24.04'], cwd=ROOT, env=environment,
                stdin=subprocess.DEVNULL, check=True, timeout=60)
    print(json.dumps({'status': 'passed', 'source_commit': commit, 'host': 'LAPTOP-NPSGA016',
        'distribution': 'Ubuntu-24.04', 'synthetic_tests_only': True, 'cloud_credentials_supplied': False,
        'provider_key_created': False, 'production_modified': False}), flush=True)


if __name__ == '__main__':
    main()
