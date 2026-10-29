"""Exact-source Ubuntu administration guard for the existing private transport.

This host executes administrative metadata/configuration delivery only. Project
builds and tests remain on the owner's laptop; no brokerage action is available.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import re
import stat
import subprocess

from owner_ai_private_transport import PrivateTransportError, _need, _private_output, _transport_secret

DEPENDENCY_SHA = 'cd1866ee944ccea2259669f4293379241fd4ee02'
SOURCE_FILES = ('tools/owner_ai_admin_transport.py', 'tools/admin_owner55_ai.py',
    'tools/owner55_ai_guest.py', 'tools/owner_ai_private_transport.py',
    'tools/owner_plan_transport_20261027.py', 'tools/inspect_owner55_ai.py',
    'tools/provision_owner55_ai.py', 'tools/activate_owner55_ai.py',
    'deploy/stage_owner55_ai.py', 'deploy/activate_owner55_ai.py', 'tools/adopt_supplied_owner55_ai.py',
    'tools/provision_owner55_bootstrap.py', 'deploy/provision_owner55_bootstrap.py',
    'tools/sync_owner55_ai_key.py', 'deploy/sync_owner55_ai_key.py')
DEPENDENCY_FILES = ('deploy/prepare_owner_vm.py', 'deploy/access_owner_vm.py',
    'tools/timeweb_ci_capacity.py', 'tools/timeweb_actions_probe.py', 'tools/timeweb_ci_catalog.py')


def _verify_environment(env, release, kernel, uid):
    _need(os.name == 'posix' and uid > 0 and release.get('ID') == 'ubuntu'
          and release.get('VERSION_ID') == '24.04' and 'microsoft' not in kernel.lower()
          and env.get('GITHUB_ACTIONS') == 'true'
          and env.get('RUNNER_ENVIRONMENT') == 'github-hosted'
          and env.get('RUNNER_OS') == 'Linux'
          and env.get('OWNER_AI_ADMIN_HOST') == 'reviewed-ubuntu24-administration-only',
          'reviewed_ai_admin_host_required')


def _git(root, *arguments):
    result = subprocess.run(['git', *arguments], cwd=root, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30)
    _need(result.returncode == 0, 'admin_source_identity_unavailable')
    return result.stdout.decode('utf-8').strip()


def require_admin_guard():
    """Verify host and exact reviewed private delivery sources before Cloud GET."""
    try:
        _need(os.name == 'posix', 'reviewed_ai_admin_host_required')
        with Path('/etc/os-release').open('rb') as stream:
            release_raw = stream.read(8193)
        with Path('/proc/sys/kernel/osrelease').open('rb') as stream:
            kernel_raw = stream.read(4097)
        _need(len(release_raw) <= 8192 and len(kernel_raw) <= 4096, 'reviewed_ai_admin_host_required')
        release = {key: value.strip('"') for line in release_raw.decode('ascii').splitlines()
                   for key, separator, value in [line.partition('=')] if separator}
        _verify_environment(os.environ, release, kernel_raw.decode('ascii'), os.getuid())
        root = Path(__file__).resolve().parents[1]
        _need(Path.cwd().resolve() == root, 'admin_source_root_changed')
        expected = os.environ.get('EXPECTED_AI_ADMIN_TOOLS_SHA', '')
        _need(re.fullmatch('[a-f0-9]{40}', expected) is not None
              and _git(root, 'rev-parse', 'HEAD') == expected, 'admin_tools_commit_changed')
        dependency = root / '.transport-admin'
        _need(_git(dependency, 'rev-parse', 'HEAD') == DEPENDENCY_SHA, 'admin_dependency_commit_changed')
        for checkout, names in ((root, SOURCE_FILES), (dependency, DEPENDENCY_FILES)):
            for name in names:
                path = checkout / name
                info = path.lstat()
                _need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                      and 0 < info.st_size <= 2 * 1024**2 and path.resolve(strict=True) == path,
                      'admin_source_file_untrusted')
                raw = path.read_bytes()
                actual = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
                _need(actual == _git(checkout, 'rev-parse', 'HEAD:' + name), 'admin_source_bytes_changed')
        temporary = Path(os.environ['RUNNER_TEMP'])
        info = temporary.lstat()
        _need(temporary.is_absolute() and temporary.resolve(strict=True) == temporary
              and stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid(),
              'admin_private_workspace_parent_required')
    except PrivateTransportError:
        raise
    except Exception:
        raise PrivateTransportError('reviewed_ai_admin_host_required') from None


@_private_output
def transport_admin(operation, payload, secret, receipt_contract):
    require_admin_guard()
    return _transport_secret(operation, payload, secret, receipt_contract)
