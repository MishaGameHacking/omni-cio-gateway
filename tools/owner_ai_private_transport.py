"""Memory-only secret delivery over the pinned existing owner SSH transport.

No call executes at import. The caller owns provider provisioning and the remote
operation; this module neither creates AI keys nor enables a provider or trading.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import tempfile
import time

SERVER_ID = 9417611
MAX_RECEIPT = 16 * 1024
MAX_ENVELOPE = 512 * 1024
PRIVATE_ROOT = Path('/home/analyst-ci/.local/state/analyst-owner-ai')
WSL_HOST_MARKER = 'LAPTOP-NPSGA016:Ubuntu-24.04'


class PrivateTransportError(RuntimeError):
    def __init__(self, code, *, operation_started=False, temporary_key_removed=True,
                 validated_receipt=None):
        super().__init__(code)
        self.operation_started = operation_started
        self.temporary_key_removed = temporary_key_removed
        self.validated_receipt = validated_receipt


def _need(condition, code):
    if not condition:
        raise PrivateTransportError(code)


def _kernel_release():
    with Path('/proc/sys/kernel/osrelease').open('rb') as source:
        raw = source.read(4097)
    _need(len(raw) <= 4096, 'owner_wsl_runtime_required')
    return raw.decode('ascii').lower()


def require_owner_wsl():
    """Require the owner's verified WSL launcher and Linux-private temp storage."""
    try:
        _need(os.name == 'posix', 'owner_wsl_runtime_required')
        import pwd
        uid = os.getuid()
        _need(uid > 0 and pwd.getpwnam('analyst-ci').pw_uid == uid
              and 'microsoft' in _kernel_release()
              and os.environ.get('WSL_DISTRO_NAME') == 'Ubuntu-24.04'
              and os.environ.get('OWNER_AI_HOST_VERIFIED') == WSL_HOST_MARKER,
              'owner_wsl_runtime_required')
        root = PRIVATE_ROOT.resolve(strict=True)
        temporary = Path(os.environ['RUNNER_TEMP'])
        _need(root == PRIVATE_ROOT and temporary.is_absolute()
              and temporary.resolve(strict=True) == temporary
              and temporary.is_relative_to(root), 'owner_private_temporary_directory_required')
        for path in (root, temporary):
            info = path.lstat()
            _need(stat.S_ISDIR(info.st_mode) and info.st_uid == uid
                  and not info.st_mode & 0o077, 'owner_private_temporary_directory_required')
    except PrivateTransportError:
        raise
    except Exception:
        raise PrivateTransportError('owner_wsl_runtime_required') from None


def _object(pairs):
    value = {}
    for key, item in pairs:
        _need(key not in value, 'private_receipt_duplicate_key')
        value[key] = item
    return value


def validate_receipt(raw, contract, secrets=()):
    """Only exact scalar fields and explicitly enumerated strings may escape."""
    _need(isinstance(raw, bytes) and 0 < len(raw) <= MAX_RECEIPT,
          'private_receipt_size_invalid')
    _need(not any(secret and secret.encode() in raw for secret in secrets),
          'private_receipt_contains_credential')
    try:
        value = json.loads(raw, object_pairs_hook=_object)
    except (ValueError, UnicodeError, TypeError):
        raise PrivateTransportError('private_receipt_invalid_json') from None
    _need(isinstance(value, dict) and set(value) == set(contract),
          'private_receipt_fields_invalid')
    _need(not any(isinstance(item, str) and secret and secret in item
                  for item in value.values() for secret in secrets),
          'private_receipt_contains_credential')
    for key, rule in contract.items():
        _need(re.fullmatch('[a-z_]{1,64}', key) is not None,
              'private_receipt_contract_invalid')
        item = value[key]
        if rule is bool:
            _need(type(item) is bool, 'private_receipt_value_invalid')
        elif rule is int:
            _need(type(item) is int and 0 <= item <= 10**15, 'private_receipt_value_invalid')
        else:
            _need(isinstance(rule, (set, frozenset)) and 0 < len(rule) <= 32
                  and all(isinstance(entry, str) and 0 < len(entry) <= 128 for entry in rule),
                  'private_receipt_contract_invalid')
            _need(isinstance(item, str) and item in rule, 'private_receipt_value_invalid')
    _need(value.get('server_id') == SERVER_ID, 'private_receipt_server_invalid')
    return value


def _load_transport():
    # The workflow checks out the unchanged transport and its pinned dependencies.
    # Import lazily so synthetic tests never need cloud credentials.
    import owner_plan_transport_20261027 as transport
    return transport


@contextmanager
def _private_workspace(outcome):
    try:
        with tempfile.TemporaryDirectory(prefix='analyst-private-admin-',
                                         dir=os.environ['RUNNER_TEMP']) as directory:
            yield directory
    except Exception:
        # Local workspace cleanup can fail after a committed remote mutation.
        # Preserve that outcome instead of turning it into a preflight failure.
        raise PrivateTransportError('private_local_workspace_failed', **outcome()) from None


def transport_secret(operation, payload, secret, receipt_contract):
    """Return a sanitized receipt, or a fixed-code error with outcome metadata.

    The new credential is ENVELOPE['secret'] on the remote side. Never delete a
    newly provisioned key after an error with operation_started=True unless a
    separate inspected result proves the key was not stored on the server.
    """
    require_owner_wsl()
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
