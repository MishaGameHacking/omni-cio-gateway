"""First installation on a new Timeweb Ubuntu VM; never replaces existing data.

Run on the verified new VM, from the reviewed repository checkout. Configuration
is a root-only JSON file, not shell code or command-line secret values. This does
not order a server, restore a database, publish an APK or configure BotFather.
"""
from __future__ import annotations

import argparse
import base64
from ipaddress import IPv4Address
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import stat
import subprocess
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
INSTALL = Path('/opt/analyst-ai')
CONFIG = Path('/etc/analyst-ai')
STATE = Path('/var/lib/analyst-ai')
UNIT = Path('/etc/systemd/system/analyst-ai-owner.service')
REQUIRED = ('TELEGRAM_CLIENT_ID', 'TELEGRAM_CLIENT_SECRET', 'ANALYST_OWNER_TELEGRAM_SUB', 'BACKEND_PUBLIC_URL', 'EXPECTED_PUBLIC_IPV4')


class InstallError(RuntimeError):
    """Fixed non-secret diagnostics only."""


def validated_config(values: dict) -> dict[str, str]:
    if type(values) is not dict or set(values) != set(REQUIRED):
        raise InstallError('exact_configuration_fields_required')
    for name in REQUIRED:
        value = values[name]
        if not isinstance(value, str) or not 1 <= len(value) <= 4096 or any(ord(c) < 33 or ord(c) > 126 for c in value):
            raise InstallError('configuration_value_invalid')
    for name in ('TELEGRAM_CLIENT_ID', 'ANALYST_OWNER_TELEGRAM_SUB'):
        if not re.fullmatch(r'[1-9][0-9]{0,19}', values[name], re.ASCII):
            raise InstallError('numeric_telegram_identity_required')
    try:
        address = IPv4Address(values['EXPECTED_PUBLIC_IPV4'])
    except ValueError:
        raise InstallError('global_ipv4_required') from None
    if not address.is_global:
        raise InstallError('global_ipv4_required')
    url = urlsplit(values['BACKEND_PUBLIC_URL'])
    host = url.hostname or ''
    if (url.scheme != 'https' or url.netloc != host or url.path or url.query or url.fragment
            or len(host) > 253 or not re.fullmatch(r'[a-z0-9]+(?:[a-z0-9.-]*[a-z0-9])?', host)
            or re.fullmatch(r'[0-9.]+', host)
            or '.' not in host or any(not part or len(part) > 63 or part.startswith('-') or part.endswith('-') for part in host.split('.'))
            or host == '176.98.178.81.sslip.io'):
        raise InstallError('new_https_hostname_required')
    return dict(values)


def load_config(path: Path) -> dict[str, str]:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > 16384:
        raise InstallError('configuration_must_be_root_owned_0600_regular_file')
    try:
        return validated_config(json.loads(path.read_text(encoding='utf-8')))
    except (ValueError, UnicodeError):
        raise InstallError('invalid_configuration_json') from None


def environment_text(values: dict[str, str], fernet_key: str) -> str:
    # EnvironmentFile is parsed by systemd, never sourced by a shell.
    settings = {name: value for name, value in validated_config(values).items() if name != 'EXPECTED_PUBLIC_IPV4'}
    settings.update({'FERNET_KEY': fernet_key,
                'DATABASE_PATH': str(STATE / 'backend.db'), 'APP_DEEP_LINK': 'analystai://auth'}
    )
    return ''.join(name + '=' + json.dumps(value, ensure_ascii=True) + '\n' for name, value in settings.items())


def run(command: list[str], *, timeout: int = 1200) -> None:
    result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout, check=False)
    if result.returncode:
        raise InstallError('installation_command_failed_' + Path(command[0]).name)


def source_files() -> list[Path]:
    backend = ROOT / 'backend'
    paths = sorted(path for path in backend.iterdir() if path.suffix in {'.py', '.json'} or path.name == 'requirements.txt')
    required = {'owner_app.py', 'owner_access.py', 'app.py', 'telegram_browser_app.py', 'telegram_jwks.json', 'requirements.txt'}
    if not required.issubset({path.name for path in paths}) or any(not path.is_file() or path.is_symlink() for path in paths):
        raise InstallError('reviewed_backend_sources_required')
    return paths


def check_target() -> None:
    if os.geteuid() != 0:
        raise InstallError('root_required_on_verified_new_vm')
    os_release = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
    if os_release.get('ID', '').strip('"') != 'ubuntu' or os_release.get('VERSION_ID', '').strip('"') != '24.04':
        raise InstallError('ubuntu_24_04_required')
    if any(path.exists() or path.is_symlink() for path in (INSTALL, CONFIG, STATE, UNIT, Path('/etc/caddy'))):
        raise InstallError('existing_installation_refused_no_data_replaced')
    if shutil.disk_usage('/').free < 5 * 1024**3:
        raise InstallError('five_gib_free_disk_required')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise InstallError('health_redirect_refused')


def probe(base_url: str) -> bool:
    opener = urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(base_url + '/health', timeout=5) as response:
            if response.status != 200 or json.loads(response.read(1024)) != {'status': 'ok'}:
                return False
        try:
            with opener.open(base_url + '/workspace', timeout=5):
                return False
        except urllib.error.HTTPError as error:
            status = error.code
            error.close()
            return status == 401
    except (OSError, ValueError, InstallError):
        return False


def wait_healthy(base_url: str) -> None:
    for _ in range(30):
        if probe(base_url):
            return
        time.sleep(2)
    raise InstallError('health_or_authentication_probe_failed')


def write_new(path: Path, content: str, mode: int) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
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


def install(values: dict[str, str]) -> None:
    check_target()
    paths = source_files()
    hostname = urlsplit(values['BACKEND_PUBLIC_URL']).hostname
    check_address(values)
    run(['apt-get', 'update'])
    run(['apt-get', 'install', '-y', '--no-install-recommends', 'python3-venv', 'ca-certificates', 'caddy'])
    run(['useradd', '--system', '--user-group', '--home-dir', str(STATE), '--no-create-home', '--shell', '/usr/sbin/nologin', 'analyst-ai'])
    CONFIG.mkdir(mode=0o700)
    (INSTALL / 'backend').mkdir(parents=True, mode=0o755)
    STATE.mkdir(mode=0o700)
    shutil.chown(STATE, user='analyst-ai', group='analyst-ai')
    for path in paths:
        shutil.copyfile(path, INSTALL / 'backend' / path.name)
    run(['python3', '-m', 'venv', str(INSTALL / 'venv')])
    run([str(INSTALL / 'venv/bin/python'), '-m', 'pip', 'install', '--only-binary=:all:', '-r', str(INSTALL / 'backend/requirements.txt')])
    fernet_key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('ascii')
    write_new(CONFIG / 'backend.env', environment_text(values, fernet_key), 0o600)
    write_new(UNIT, (ROOT / 'deploy/analyst-ai-owner.service').read_text(), 0o644)
    run(['systemctl', 'daemon-reload'])
    try:
        run(['systemctl', 'start', 'analyst-ai-owner'])
        wait_healthy('http://127.0.0.1:8080')
        caddy_file = CONFIG / 'Caddyfile'
        write_new(caddy_file, hostname + ' {\n\treverse_proxy 127.0.0.1:8080\n}\n', 0o644)
        # caddy service can read the proxy config without reading backend.env.
        CONFIG.chmod(0o711)
        run(['caddy', 'validate', '--config', str(caddy_file), '--adapter', 'caddyfile'])
        dropin = Path('/etc/systemd/system/caddy.service.d')
        dropin.mkdir(exist_ok=True)
        write_new(dropin / 'analyst-ai.conf', '[Service]\nExecStart=\nExecStart=/usr/bin/caddy run --config /etc/analyst-ai/Caddyfile\nExecReload=\nExecReload=/usr/bin/caddy reload --config /etc/analyst-ai/Caddyfile --force\n', 0o644)
        run(['systemctl', 'daemon-reload'])
        run(['systemctl', 'restart', 'caddy'])
        wait_healthy(values['BACKEND_PUBLIC_URL'])
        run(['systemctl', 'enable', 'analyst-ai-owner', 'caddy'])
    except (InstallError, OSError, subprocess.SubprocessError):
        # A failed fresh install stays stopped; retain state/key for diagnosis.
        run(['systemctl', 'stop', 'analyst-ai-owner'])
        raise
    print('OWNER_BACKEND_INSTALL=healthy_authenticated_single_worker')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--install', action='store_true')
    options = parser.parse_args()
    try:
        values = load_config(options.config)
        source_files()
        if options.install:
            install(values)
        else:
            print('OWNER_BACKEND_INSTALL=configuration_and_sources_validated_only')
    except (InstallError, OSError, subprocess.SubprocessError) as error:
        print('OWNER_BACKEND_INSTALL_ERROR=' + (str(error) if isinstance(error, InstallError) else type(error).__name__))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
