"""Metadata-only scheduled renewal transport on the reviewed GitHub Ubuntu runner.

Uses the already approved existing-server SSH access path. No app tests run on
this host, no inference key crosses SSH, and no existing key is created/rotated.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import time

from owner_ai_private_transport import (PrivateTransportError, validate_receipt,
    _need, _load_transport, _private_workspace, _private_output, MAX_ENVELOPE, SERVER_ID)

DEPENDENCY_SHA = 'cd1866ee944ccea2259669f4293379241fd4ee02'
SOURCE_FILES = ('tools/owner_ai_renewal_transport.py', 'tools/renew_owner55_ai.py',
    'tools/owner_ai_private_transport.py', 'tools/owner_plan_transport_20261027.py',
    'tools/inspect_owner55_ai.py', 'tools/provision_owner55_ai.py', 'tools/activate_owner55_ai.py',
    'deploy/stage_owner55_ai.py', 'deploy/activate_owner55_ai.py', 'deploy/renew_owner55_ai.py')
DEPENDENCY_FILES = ('deploy/prepare_owner_vm.py', 'deploy/access_owner_vm.py',
    'tools/timeweb_ci_capacity.py', 'tools/timeweb_actions_probe.py', 'tools/timeweb_ci_catalog.py')


def _verify_environment(env, release, kernel, uid):
    _need(os.name == 'posix' and uid > 0 and release.get('ID') == 'ubuntu'
          and release.get('VERSION_ID') == '24.04' and 'microsoft' not in kernel.lower()
          and env.get('GITHUB_ACTIONS') == 'true'
          and env.get('RUNNER_ENVIRONMENT') == 'github-hosted'
          and env.get('RUNNER_OS') == 'Linux'
          and env.get('OWNER_AI_RENEWAL_ADMIN_HOST') == 'reviewed-ubuntu24-metadata-only',
          'reviewed_renewal_admin_host_required')


def _regular(path):
    info = path.lstat()
    _need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
          and info.st_size <= 2 * 1024**2 and path.resolve(strict=True) == path,
          'renewal_source_file_untrusted')
    return path.read_bytes()


def _git(root, *arguments):
    result = subprocess.run(['git', *arguments], cwd=root, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30)
    _need(result.returncode == 0, 'renewal_source_identity_unavailable')
    return result.stdout.decode('utf-8').strip()


def require_renewal_admin():
    """Fail closed before metadata requests unless exact reviewed admin code runs."""
    try:
        _need(os.name == 'posix', 'reviewed_renewal_admin_host_required')
        with Path('/etc/os-release').open('rb') as stream:
            release_raw = stream.read(8193)
        with Path('/proc/sys/kernel/osrelease').open('rb') as stream:
            kernel_raw = stream.read(4097)
        _need(len(release_raw) <= 8192 and len(kernel_raw) <= 4096,
              'reviewed_renewal_admin_host_required')
        release = {key: value.strip('"') for line in release_raw.decode('ascii').splitlines()
                   for key, separator, value in [line.partition('=')] if separator}
        _verify_environment(os.environ, release, kernel_raw.decode('ascii'), os.getuid())
        root = Path(__file__).resolve().parents[1]
        _need(Path.cwd().resolve() == root, 'renewal_source_root_changed')
        expected = os.environ.get('EXPECTED_AI_RENEWAL_TOOLS_SHA', '')
        _need(re.fullmatch('[a-f0-9]{40}', expected) is not None
              and _git(root, 'rev-parse', 'HEAD') == expected, 'renewal_tools_commit_changed')
        dependency = root / '.transport-admin'
        _need(_git(dependency, 'rev-parse', 'HEAD') == DEPENDENCY_SHA, 'renewal_dependency_commit_changed')
        for checkout, names in ((root, SOURCE_FILES), (dependency, DEPENDENCY_FILES)):
            for name in names:
                raw = _regular(checkout / name)
                actual = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
                _need(actual == _git(checkout, 'rev-parse', 'HEAD:' + name), 'renewal_source_bytes_changed')
        temporary = Path(os.environ['RUNNER_TEMP'])
        info = temporary.lstat()
        _need(temporary.is_absolute() and temporary.resolve(strict=True) == temporary
              and stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid(),
              'renewal_private_workspace_parent_required')
    except PrivateTransportError:
        raise
    except Exception:
        raise PrivateTransportError('reviewed_renewal_admin_host_required') from None


@_private_output
def transport_renewal(operation, payload, receipt_contract):
    """Send only public operation/configuration; runtime reads its own AI key."""
    require_renewal_admin()
    secret = None
    _need(isinstance(operation, str) and 0 < len(operation.encode()) <= 128 * 1024,
          'private_operation_size_invalid')
    _need(isinstance(payload, dict), 'private_payload_invalid')
    _need(secret is None or (isinstance(secret, str) and 16 <= len(secret) <= 4096
          and secret.isascii() and not any(character.isspace() for character in secret)),
          'private_credential_invalid')
    _need(not secret or secret not in operation, 'private_credential_embedded_in_code')
    try:
        envelope = json.dumps({'operation': operation, 'payload': payload, 'secret': secret},
                              ensure_ascii=True, allow_nan=False).encode()
    except (ValueError, TypeError):
        raise PrivateTransportError('private_payload_invalid') from None
    _need(len(envelope) <= MAX_ENVELOPE, 'private_envelope_size_invalid')
    # This literal command never contains the token, payload or provider settings.
    bootstrap = ("import json,sys; raw=sys.stdin.buffer.read(524289); "
                 "assert len(raw)<=524288; e=json.loads(raw); "
                 "exec(compile(e['operation'],'owner-private-operation','exec'),"
                 "{'ENVELOPE':e,'__name__':'__main__'})")
    try:
        transport = _load_transport()
        status, data = transport.api('GET', '/servers/' + str(SERVER_ID))
        server = data.get('server', {})
        _need(status == 200 and transport.SERVER_ID == SERVER_ID
              and server.get('name') == 'Analyst AI runtime 20261025'
              and server.get('project_id') == 2941515
              and server.get('availability_zone') == 'ams-1'
              and transport.p.cloud.public_ipv4(server) == transport.IP,
              'private_server_identity_invalid')
    except Exception:
        raise PrivateTransportError('private_transport_preflight_failed') from None
    access, p = transport.access, transport.p
    access.SERVER_ID = SERVER_ID
    operation_started, receipt, key_id = False, None, None
    attached_attempted, cleanup_ok, failure = False, True, None
    with _private_workspace(lambda: {'operation_started': operation_started,
            'temporary_key_removed': cleanup_ok, 'validated_receipt': receipt}) as directory:
        folder = Path(directory)
        try:
            folder.chmod(0o700)
            p.cloud.generate_key(folder / 'client')
            private_info = (folder / 'client').lstat()
            _need(stat.S_ISREG(private_info.st_mode) and private_info.st_nlink == 1
                  and private_info.st_uid == os.getuid()
                  and not private_info.st_mode & 0o077,
                  'private_ssh_key_permissions_invalid')
            public = (folder / 'client.pub').read_text().strip()
            # Creation can succeed remotely even when its response is lost.
            # Without a verified ID there is no safe key to delete by guess.
            cleanup_ok = False
            created = access.request(transport.TOKEN, 'POST', '/ssh-keys', {
                'name': 'analyst-private-admin-' + os.environ['GITHUB_RUN_ID'],
                'body': public, 'is_default': False})
            key = created.get('ssh_key', created.get('ssh-key', {}))
            _need(type(key.get('id')) is int and key['id'] > 0
                  and key.get('body', '').split()[:2] == public.split()[:2],
                  'private_temporary_key_identity_invalid')
            key_id = key['id']
            attached_attempted = True
            access.request(transport.TOKEN, 'POST', '/servers/' + str(SERVER_ID) + '/ssh-keys',
                           {'ssh_key_ids': [key_id]})
            command = p.ssh_command(folder, transport.IP, transport.HOST_KEY)
            command[1:1] = ['-o', 'ServerAliveInterval=20', '-o', 'ServerAliveCountMax=3']
            for attempt in range(12):
                try:
                    p.remote(command, 'test $(id -u) = 0', timeout=12)
                    break
                except (p.ProbeError, subprocess.TimeoutExpired):
                    if attempt == 11:
                        raise PrivateTransportError('private_ssh_unavailable') from None
                    time.sleep(5)
            operation_started = True
            result = subprocess.run([*command, 'python3 -c ' + shlex.quote(bootstrap)],
                                    input=envelope, stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL, timeout=240)
            _need(result.returncode == 0, 'private_remote_operation_failed')
            receipt = validate_receipt(result.stdout, receipt_contract,
                                       (secret, transport.TOKEN))
        except PrivateTransportError as error:
            failure = str(error)
        except Exception:
            failure = 'private_transport_failed'
        finally:
            if key_id is not None:
                detached = not attached_attempted
                try:
                    if attached_attempted:
                        access.request(transport.TOKEN, 'DELETE',
                            '/servers/' + str(SERVER_ID) + '/ssh-keys/' + str(key_id))
                        detached = True
                except Exception:
                    detached = False
                try:
                    access.request(transport.TOKEN, 'DELETE', '/ssh-keys/' + str(key_id))
                    cleanup_ok = detached
                except Exception:
                    cleanup_ok = False
    if failure or not cleanup_ok:
        raise PrivateTransportError(failure or 'private_temporary_key_cleanup_failed',
            operation_started=operation_started, temporary_key_removed=cleanup_ok,
            validated_receipt=receipt) from None
    return receipt

