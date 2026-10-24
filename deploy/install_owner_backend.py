"""First installation on a new Timeweb Ubuntu VM; never replaces existing data.

Run on the verified new VM, from the reviewed repository checkout. Configuration
is a root-only JSON file, not shell code or command-line secret values. This does
not order a server, restore a database, publish an APK or configure BotFather.
"""
from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
import grp
import hashlib
from http.client import HTTPConnection, HTTPSConnection, HTTPException
from ipaddress import IPv4Address
import json
import os
from pathlib import Path
import re
import secrets
import signal
import shutil
import socket
import ssl
import stat
import subprocess
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
INSTALL = Path('/opt/analyst-ai')
CONFIG = Path('/etc/analyst-ai')
STATE = Path('/var/lib/analyst-ai')
UNIT = Path('/etc/systemd/system/analyst-ai-owner.service')
CADDY_DROPIN = Path('/etc/systemd/system/caddy.service.d/analyst-ai.conf')
INPUT_CONFIG = Path('/root/analyst-ai-owner.json')
ENROLLMENT_CONFIG = Path('/root/analyst-ai-enrollment.json')
ENROLLMENT_CALLBACK = '/auth/telegram/owner-enrollment/callback'
REQUIRED = ('TELEGRAM_CLIENT_ID', 'TELEGRAM_CLIENT_SECRET', 'ANALYST_OWNER_TELEGRAM_SUB', 'BACKEND_PUBLIC_URL', 'EXPECTED_PUBLIC_IPV4')
ENROLLMENT_REQUIRED = tuple(name for name in REQUIRED if name != 'ANALYST_OWNER_TELEGRAM_SUB') + ('TELEGRAM_ENROLLMENT_REDIRECT_URI',)
# The same public X.509 DER pin used by app.tinvest_ssl_context(). Packaging
# must fail before installing if its broker-only trust anchor is absent/changed.
TINVEST_CA_SHA256 = 'd26d2d0231b7c39f92cc738512ba54103519e4405d68b5bd703e9788ca8ecf31'


class InstallError(RuntimeError):
    """Fixed non-secret diagnostics only."""


def _validated_values(values: dict, *, enrollment: bool = False) -> dict[str, str]:
    required = ENROLLMENT_REQUIRED if enrollment else REQUIRED
    if type(values) is not dict or set(values) != set(required):
        raise InstallError('exact_configuration_fields_required')
    for name in required:
        value = values[name]
        if not isinstance(value, str) or not 1 <= len(value) <= 4096 or any(ord(c) < 33 or ord(c) > 126 for c in value):
            raise InstallError('configuration_value_invalid')
    if not re.fullmatch(r'[1-9]\d{0,19}', values['TELEGRAM_CLIENT_ID'], re.ASCII):
        raise InstallError('numeric_telegram_client_id_required')
    # OIDC sub is an opaque, case-sensitive identity. Telegram's profile id
    # is a different claim; never derive or normalize the owner subject from it.
    if not enrollment and len(values['ANALYST_OWNER_TELEGRAM_SUB']) > 256:
        raise InstallError('telegram_oidc_subject_too_long')
    _validate_server_target(values['BACKEND_PUBLIC_URL'], values['EXPECTED_PUBLIC_IPV4'])
    if enrollment and values['TELEGRAM_ENROLLMENT_REDIRECT_URI'] != values['BACKEND_PUBLIC_URL'] + ENROLLMENT_CALLBACK:
        raise InstallError('exact_enrollment_https_redirect_required')
    return dict(values)


def _validate_server_target(public_url: str, expected_ip: str) -> None:
    try:
        address = IPv4Address(expected_ip)
    except ValueError:
        raise InstallError('global_ipv4_required') from None
    if not address.is_global:
        raise InstallError('global_ipv4_required')
    url = urlsplit(public_url)
    host = url.hostname or ''
    if (url.scheme != 'https' or url.netloc != host or url.path or url.query or url.fragment
            or not valid_hostname(host)
            or host == '176.98.178.81.sslip.io'):
        raise InstallError('new_https_hostname_required')


def validated_config(values: dict) -> dict[str, str]:
    return _validated_values(values)


def validated_enrollment_config(values: dict) -> dict[str, str]:
    return _validated_values(values, enrollment=True)


def valid_hostname(host: str) -> bool:
    if len(host) > 253 or '.' not in host or host.replace('.', '').isdecimal():
        return False
    return all(re.fullmatch(r'[a-z\d-]{1,63}', part, re.ASCII) and
               part[0].isalnum() and part[-1].isalnum() for part in host.split('.'))


def load_config(*, enrollment: bool = False) -> dict[str, str]:
    # Fixed root-owned path, opened atomically without following a symlink.
    # CLI input never chooses a file for the privileged installer to read.
    path = ENROLLMENT_CONFIG if enrollment else INPUT_CONFIG
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        with os.fdopen(descriptor, 'r', encoding='utf-8') as source:
            info = os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > 16384:
                raise InstallError('configuration_must_be_root_owned_0600_regular_file')
            document = source.read(16385)
            if len(document) > 16384:
                raise InstallError('configuration_too_large')
            return _validated_values(json.loads(document), enrollment=enrollment)
    except ValueError:
        raise InstallError('invalid_configuration_json') from None


def environment_text(values: dict[str, str], fernet_key: str) -> str:
    # EnvironmentFile is parsed by systemd, never sourced by a shell.
    settings = {name: value for name, value in validated_config(values).items() if name != 'EXPECTED_PUBLIC_IPV4'}
    settings.update({'FERNET_KEY': fernet_key,
                'DATABASE_PATH': str(STATE / 'backend.db'), 'APP_DEEP_LINK': 'analystai://auth'}
    )
    return ''.join(name + '=' + json.dumps(value, ensure_ascii=True) + '\n' for name, value in settings.items())


def run(command: list[str], *, timeout: int = 1200) -> None:
    # Venv and wheel files are public code read by the service account. A root
    # shell with umask 077 must not make them inaccessible. Secrets are written
    # separately with explicit mode 0600; the service keeps its own UMask=0077.
    result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            timeout=timeout, check=False, umask=0o022)
    if result.returncode:
        raise InstallError('installation_command_failed_' + Path(command[0]).name)


def source_files() -> list[Path]:
    backend = ROOT / 'backend'
    paths = sorted(path for path in backend.iterdir() if path.suffix in {'.py', '.json'} or path.name == 'requirements.txt')
    certificate = backend / 'certs/russian_trusted_root_ca.pem'
    paths.append(certificate)
    required = {'owner_app.py', 'owner_access.py', 'app.py', 'telegram_browser_app.py', 'telegram_oidc.py', 'telegram_jwks.json', 'requirements.txt'}
    if (not required.issubset({path.name for path in paths}) or certificate.parent.is_symlink()
            or any(not path.is_file() or path.is_symlink() for path in paths)):
        raise InstallError('reviewed_backend_sources_required')
    try:
        der = ssl.PEM_cert_to_DER_cert(certificate.read_text(encoding='ascii'))
    except (OSError, ValueError):
        raise InstallError('reviewed_broker_certificate_required') from None
    if hashlib.sha256(der).hexdigest() != TINVEST_CA_SHA256:
        raise InstallError('reviewed_broker_certificate_required')
    return paths


def install_sources(paths: list[Path]) -> None:
    """Copy reviewed public code/assets with their paths and service readability."""
    for directory in (INSTALL, INSTALL / 'backend', INSTALL / 'backend/certs'):
        directory.mkdir(mode=0o755)
        directory.chmod(0o755)
    for path in paths:
        destination = INSTALL / 'backend' / path.relative_to(ROOT / 'backend')
        shutil.copyfile(path, destination)
        destination.chmod(0o644)


def check_target() -> None:
    if os.geteuid() != 0:
        raise InstallError('root_required_on_verified_new_vm')
    os_release = {key: value for line in Path('/etc/os-release').read_text().splitlines() if '=' in line
                  for key, value in [line.split('=', 1)]}
    if os_release.get('ID', '').strip('"') != 'ubuntu' or os_release.get('VERSION_ID', '').strip('"') != '24.04':
        raise InstallError('ubuntu_24_04_required')
    if any(path.exists() or path.is_symlink() for path in (INSTALL, CONFIG, STATE, UNIT, Path('/etc/caddy'), CADDY_DROPIN.parent)):
        raise InstallError('existing_installation_refused_no_data_replaced')
    if shutil.disk_usage('/').free < 5 * 1024**3:
        raise InstallError('five_gib_free_disk_required')


class LocalTLSConnection(HTTPSConnection):
    """Verify this VM's certificate using SNI, without configurable destinations."""

    def __init__(self, hostname: str):
        if not valid_hostname(hostname):
            raise InstallError('invalid_tls_hostname')
        super().__init__('127.0.0.1', 443, timeout=5)
        self.public_hostname = hostname

    def connect(self):
        raw = socket.create_connection(('127.0.0.1', 443), timeout=5)
        try:
            self.sock = ssl.create_default_context().wrap_socket(raw, server_hostname=self.public_hostname)
        except BaseException:
            raw.close()
            raise


def probe(hostname: str | None = None) -> bool:
    # Requests are always to this VM. No config URL, proxy environment, redirect,
    # file scheme or alternate network destination is accepted by this probe.
    connection = LocalTLSConnection(hostname) if hostname else HTTPConnection('127.0.0.1', 8080, timeout=5)
    headers = {'Host': hostname} if hostname else {}
    try:
        connection.request('GET', '/health', headers=headers)
        with connection.getresponse() as response:
            if response.status != 200 or json.loads(response.read(1024)) != {'status': 'ok'}:
                return False
        connection.request('GET', '/workspace', headers=headers)
        with connection.getresponse() as response:
            return response.status == 401
    except (OSError, ValueError, HTTPException):
        return False
    finally:
        connection.close()


def wait_healthy(hostname: str | None = None) -> None:
    for _ in range(30):
        if probe(hostname):
            return
        time.sleep(2)
    raise InstallError('health_or_authentication_probe_failed')


def write_new(path: Path, content: str, mode: int, *, directory: int | None = None,
              group_id: int | None = None) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode, dir_fd=directory)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
        if group_id is not None:
            os.fchown(output.fileno(), 0, group_id)
        os.fchmod(output.fileno(), mode)
        output.write(content)


def check_address(values: dict[str, str]) -> None:
    expected = values['EXPECTED_PUBLIC_IPV4']
    host = urlsplit(values['BACKEND_PUBLIC_URL']).hostname
    addresses = {entry[4][0] for entry in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
    if addresses != {expected}:
        raise InstallError('dns_does_not_identify_exact_new_server')
    result = subprocess.run(['ip', '-j', '-4', 'address', 'show'], capture_output=True, check=True, timeout=10)
    devices = json.loads(result.stdout)
    local = {entry.get('local') for device in devices for entry in device.get('addr_info', [])}
    if expected not in local:
        raise InstallError('public_ip_not_assigned_to_this_vm')


def caddy_text(hostname: str, *, enrollment: bool = False) -> str:
    if not valid_hostname(hostname):
        raise InstallError('invalid_tls_hostname')
    if enrollment:
        # The global logger includes http.log.error, whose request URI could
        # contain code/state on an upstream failure. Disable it for this short
        # bootstrap stage as well as leaving site access logging disabled.
        # https://caddyserver.com/docs/caddyfile/options#log
        return ('{\n\tlog default {\n\t\toutput discard\n\t}\n}\n' + hostname + ' {\n'
                '\t@enrollment {\n\t\tmethod GET\n\t\tpath ' + ENROLLMENT_CALLBACK + '\n\t}\n'
                '\thandle @enrollment {\n\t\treverse_proxy 127.0.0.1:8765\n\t}\n'
                '\thandle {\n\t\trespond "owner-enrollment-only" 404\n\t}\n}\n')
    # Old callback URLs never reach Uvicorn's access log after the listener is
    # gone. The normal application login endpoints are separate and unchanged.
    return (hostname + ' {\n\thandle ' + ENROLLMENT_CALLBACK + ' {\n\t\trespond 410\n\t}\n'
            '\thandle {\n\t\treverse_proxy 127.0.0.1:8080\n\t}\n}\n')


def write_caddy_config(name: str, hostname: str, *, enrollment: bool = False) -> Path:
    try:
        group_id = grp.getgrnam('caddy').gr_gid
    except KeyError:
        raise InstallError('caddy_service_group_required') from None
    directory = os.open(CONFIG, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        # Only root may change config. The packaged caddy:caddy service needs
        # directory traversal and Caddyfile read access, not world access or env.
        os.fchown(directory, 0, group_id)
        os.fchmod(directory, 0o750)
        write_new(Path(name), caddy_text(hostname, enrollment=enrollment), 0o640,
                  directory=directory, group_id=group_id)
    finally:
        os.close(directory)
    return CONFIG / name


def configure_caddy(hostname: str, *, enrollment: bool) -> Path:
    caddy_file = write_caddy_config('Caddyfile', hostname, enrollment=enrollment)
    run(['caddy', 'validate', '--config', str(caddy_file), '--adapter', 'caddyfile'])
    # PID 1 reads this system-unit override as root. The caddy service itself
    # only needs the separate group-readable Caddyfile, not this directory.
    CADDY_DROPIN.parent.mkdir(mode=0o700)
    directory = os.open(CADDY_DROPIN.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fchmod(directory, 0o700)
        write_new(Path(CADDY_DROPIN.name), '[Service]\nExecStart=\nExecStart=/usr/bin/caddy run --config /etc/analyst-ai/Caddyfile\nExecReload=\nExecReload=/usr/bin/caddy reload --config /etc/analyst-ai/Caddyfile --force\n', 0o644, directory=directory)
    finally:
        os.close(directory)
    run(['systemctl', 'daemon-reload'])
    return caddy_file


def enrollment_tls_ready(hostname: str) -> bool:
    connection = LocalTLSConnection(hostname)
    try:
        for path in ('/health', '/workspace'):
            connection.request('GET', path, headers={'Host': hostname})
            with connection.getresponse() as response:
                if response.status != 404 or response.read(256) != b'owner-enrollment-only':
                    return False
        return True
    except (OSError, HTTPException):
        return False
    finally:
        connection.close()


def complete_enrollment(values: dict[str, str], hostname: str, caddy_file: Path) -> dict[str, str]:
    run(['systemctl', 'start', 'caddy'])
    for _ in range(30):
        if enrollment_tls_ready(hostname):
            break
        time.sleep(2)
    else:
        raise InstallError('enrollment_tls_probe_failed')
    run([str(INSTALL / 'venv/bin/python'), str(ROOT / 'deploy/enroll_owner.py')], timeout=900)
    confirmed = load_config()
    if any(confirmed[name] != values[name] for name in REQUIRED if name != 'ANALYST_OWNER_TELEGRAM_SUB'):
        raise InstallError('confirmed_configuration_does_not_match_enrollment')
    run(['systemctl', 'stop', 'caddy'])
    # These two public files belong exclusively to this fresh invocation. The
    # private owner JSON is published no-replace by the enrollment CLI instead.
    runtime_config = write_caddy_config('Caddyfile.runtime', hostname)
    run(['caddy', 'validate', '--config', str(runtime_config), '--adapter', 'caddyfile'])
    os.replace(runtime_config, caddy_file)
    return confirmed


@contextmanager
def cancel_on_signals():
    """SSH hangup / normal termination use the same fail-closed cleanup as Ctrl-C."""
    def cancel(_number, _frame):
        raise KeyboardInterrupt
    previous = {number: signal.signal(number, cancel) for number in (signal.SIGHUP, signal.SIGTERM)}
    try:
        yield
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)


def stop_failed_installation() -> None:
    commands = [['systemctl', 'disable', '--now', 'caddy']]
    if UNIT.exists():
        commands.append(['systemctl', 'stop', 'analyst-ai-owner'])
    incomplete = False
    for command in commands:
        try:
            result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    timeout=30, check=False)
            incomplete = incomplete or result.returncode != 0
        except (OSError, subprocess.SubprocessError):
            incomplete = True
    if incomplete:
        print('OWNER_BACKEND_INSTALL_CLEANUP=incomplete_check_service_state')


def install(values: dict[str, str], *, enroll_owner: bool = False) -> None:
    values = _validated_values(values, enrollment=enroll_owner)
    check_target()
    paths = source_files()
    hostname = urlsplit(values['BACKEND_PUBLIC_URL']).hostname
    check_address(values)
    if enroll_owner:
        if INPUT_CONFIG.exists() or INPUT_CONFIG.is_symlink():
            raise InstallError('existing_owner_configuration_refused')
        if not os.isatty(0) or stat.S_IMODE(os.fstat(0).st_mode) & 0o077:
            raise InstallError('private_interactive_terminal_required_run_mesg_n')
        script = ROOT / 'deploy/enroll_owner.py'
        if not script.is_file() or script.is_symlink():
            raise InstallError('reviewed_enrollment_script_required')
    try:
        run(['apt-get', 'update'])
        run(['apt-get', 'install', '-y', '--no-install-recommends', 'python3-venv', 'ca-certificates', 'caddy'])
        # A package failure or SSH interruption can happen after autostart;
        # the cleanup boundary therefore includes the entire mutating phase.
        run(['systemctl', 'disable', '--now', 'caddy'])
        run(['useradd', '--system', '--user-group', '--home-dir', str(STATE), '--no-create-home', '--shell', '/usr/sbin/nologin', 'analyst-ai'])
        CONFIG.mkdir(mode=0o700)
        install_sources(paths)
        STATE.mkdir(mode=0o700)
        shutil.chown(STATE, user='analyst-ai', group='analyst-ai')
        run(['python3', '-m', 'venv', str(INSTALL / 'venv')])
        run([str(INSTALL / 'venv/bin/python'), '-m', 'pip', 'install', '--only-binary=:all:', '-r', str(INSTALL / 'backend/requirements.txt')])
        caddy_file = configure_caddy(hostname, enrollment=enroll_owner)
        if enroll_owner:
            values = complete_enrollment(values, hostname, caddy_file)
        # No key, application environment, service unit, database or backend
        # listener is created before the explicit identity confirmation.
        fernet_key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('ascii')
        write_new(CONFIG / 'backend.env', environment_text(values, fernet_key), 0o600)
        write_new(UNIT, (ROOT / 'deploy/analyst-ai-owner.service').read_text(), 0o644)
        run(['systemctl', 'daemon-reload'])
        run(['systemctl', 'start', 'analyst-ai-owner'])
        wait_healthy()
        run(['systemctl', 'restart', 'caddy'])
        wait_healthy(hostname)
        run(['systemctl', 'enable', 'analyst-ai-owner', 'caddy'])
    except (InstallError, OSError, subprocess.SubprocessError, KeyboardInterrupt):
        stop_failed_installation()
        raise
    print('OWNER_BACKEND_INSTALL=local_health_auth_and_tls_verified_external_check_pending')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--install', action='store_true')
    parser.add_argument('--enroll-owner', action='store_true')
    options = parser.parse_args()
    try:
        values = load_config(enrollment=options.enroll_owner)
        source_files()
        if options.install:
            with cancel_on_signals():
                install(values, enroll_owner=options.enroll_owner)
        else:
            print('OWNER_BACKEND_INSTALL=configuration_and_sources_validated_only')
    except KeyboardInterrupt:
        print('OWNER_BACKEND_INSTALL_ERROR=cancelled')
        return 1
    except (InstallError, OSError, subprocess.SubprocessError) as error:
        print('OWNER_BACKEND_INSTALL_ERROR=' + (str(error) if isinstance(error, InstallError) else type(error).__name__))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
