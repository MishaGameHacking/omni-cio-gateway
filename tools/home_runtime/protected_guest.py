"""Configure the dedicated Windows user's guest and supervise its read-only research services."""
from __future__ import annotations

import configparser
import hashlib
import http.client
import json
import os
from pathlib import Path
import pwd
import sys
import time

MARK = Path('/etc/analyst-protected-home')
VALUE = 'analyst-dedicated-windows-account-1'
TOOLS = Path('/opt/analyst-home-bootstrap')
APP = '853090e11dcefef693366159c97316e55045c4c9'


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def configure():
    require(os.geteuid() == 0 and 'VERSION_ID="24.04"' in Path('/etc/os-release').read_text(), 'wrong guest')
    for marker, value in [(MARK, VALUE), (MARK.with_name('analyst-home-stage'), 'analyst-home-public-stage-1')]:
        if marker.exists():
            require(not marker.is_symlink() and marker.read_text().strip() == value, 'foreign guest')
        else:
            with marker.open('x') as fp:
                fp.write(value + '\n')
            marker.chmod(0o644)
    conf = Path('/etc/wsl.conf')
    require(not conf.is_symlink(), 'foreign settings')
    parsed = configparser.ConfigParser(interpolation=None)
    parsed.optionxform = str
    parsed.read(conf)
    for section, values in {'boot': {'systemd': 'true'}, 'interop': {'enabled': 'false', 'appendWindowsPath': 'false'},
                            'automount': {'enabled': 'false'}}.items():
        if not parsed.has_section(section):
            parsed.add_section(section)
        parsed[section].update(values)
    tmp = conf.with_suffix('.analyst-new')
    with tmp.open('x') as fp:
        parsed.write(fp)
    tmp.chmod(0o644)
    tmp.replace(conf)
    TOOLS.mkdir(mode=0o755, exist_ok=True)
    require(TOOLS.resolve() == TOOLS and TOOLS.stat().st_uid == 0 and not TOOLS.stat().st_mode & 0o022, 'unsafe tools')


def isolated():
    return (MARK.read_text().strip() == VALUE and Path('/proc/1/comm').read_text().strip() == 'systemd'
            and not any(m.split()[1] in ('/mnt/c', '/mnt/d') for m in Path('/proc/mounts').read_text().splitlines()))


def health():
    if not Path('/run/analyst-local-ai/research.sock').is_socket():
        return False
    conn = http.client.HTTPConnection('127.0.0.1', 18158, timeout=4)
    try:
        conn.request('GET', '/health')
        reply = conn.getresponse()
        return reply.status == 200 and json.loads(reply.read(4096)) == {'status': 'ok'}
    except (OSError, ValueError, http.client.HTTPException):
        return False
    finally:
        conn.close()


def watch():
    require(os.geteuid() == pwd.getpwnam('analyst-ai').pw_uid and isolated(), 'host identity')
    # A real Windows-side foreground WSL client remains attached for the duration of the boot.
    misses = 0
    while misses < 5:
        misses = 0 if health() else misses + 1
        time.sleep(15)
    raise RuntimeError('service unavailable')


if __name__ == '__main__':
    action = sys.argv[1]
    if action == 'configure':
        configure()
    elif action == 'isolation':
        require(isolated(), 'guest isolation')
    elif action == 'verify-file':
        path = TOOLS / sys.argv[2]
        require(path.parent == TOOLS and path.is_file() and not path.is_symlink()
                and hashlib.sha256(path.read_bytes()).hexdigest() == sys.argv[3], 'protected script checksum')
    elif action == 'watch':
        watch()
    else:
        raise SystemExit(2)
