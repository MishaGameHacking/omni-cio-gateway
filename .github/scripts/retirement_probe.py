"""Read-only retirement checks executed via SSH stdin; never mutate app data."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

SOURCE = 9326369
TARGET = 9334503
RUN = '38362757807'
HOST = '176.98.178.81.sslip.io'
DATA = Path('/var/lib/analyst-ai/backend.db')
ENV = Path('/etc/analyst-ai/backend.env')
ARCHIVE = Path('/root/analyst-migration-' + RUN) / 'application.tgz'
CUTOVER = Path('/root/analyst-cutover-' + RUN)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(path):
    require(path.is_file() and not path.is_symlink(), 'Missing regular recovery file')
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def service_state():
    result = subprocess.run(['systemctl', 'is-active', 'analyst-ai-backend'],
        capture_output=True, text=True, timeout=15, check=False)
    require(result.returncode in (0, 3), 'Cannot inspect backend service')
    return result.stdout.strip()


def probe(role):
    require(os.geteuid() == 0, 'Expected authenticated administrative SSH')
    if role == 'source':
        record = json.loads((CUTOVER / 'source-state.json').read_text())
        require(record.get('source_id') == SOURCE and record.get('target_id') == TARGET,
            'Source marker identity mismatch')
        require(record.get('phase') == 'bridge_only' and record.get('local_backend_running') is False,
            'Old server is not a retired proxy')
        require(record.get('proxy_target') == HOST and service_state() == 'inactive', 'Source still writes')
        require(Path('/etc/analyst-ai/source-retired.lock').read_text().strip() == RUN, 'Source guard changed')
        require(digest(DATA) == record['source_database_sha256'], 'Source data changed after final snapshot')
        checksum = digest(ARCHIVE)
        require(checksum == record['snapshot']['archive_sha256'], 'Source archive changed')
        return {'role': role, 'source_frozen': True, 'archive_sha256': checksum}
    require(role == 'target', 'Unknown probe role')
    record = json.loads(Path('/etc/analyst-ai/moscow-active.json').read_text())
    require(record.get('source_id') == SOURCE and record.get('target_id') == TARGET,
        'Target marker identity mismatch')
    require(record.get('run') == RUN and record.get('phase') == 'active', 'Moscow cutover not active')
    require(record.get('target_writes_may_exist') is True and service_state() == 'active', 'Moscow backend not active')
    checksum = digest(ARCHIVE)
    require(checksum == record['archive_sha256'], 'Target recovery archive changed')
    from dotenv import dotenv_values
    from cryptography.fernet import Fernet
    current = dotenv_values(ENV)
    original = dotenv_values(ARCHIVE.parent / 'restored/config/backend.env')
    require(current.get('FERNET_KEY') and current.get('FERNET_KEY') == original.get('FERNET_KEY'), 'Original encryption key not preserved')
    require(current.get('DATABASE_PATH') == str(DATA) and current.get('BACKEND_PUBLIC_URL') == 'https://' + HOST,
        'Moscow environment identity changed')
    require(current.get('ANALYSIS_SCHEDULER_ENABLED') == 'true', 'Moscow scheduler not configured')
    cipher = Fernet(current['FERNET_KEY'].encode())
    with sqlite3.connect(DATA.as_uri() + '?mode=ro', uri=True, timeout=15) as db:
        require(db.execute('PRAGMA integrity_check').fetchall() == [('ok',)], 'Moscow database integrity failure')
        for (encrypted,) in db.execute('SELECT tinvest_token_encrypted FROM users WHERE tinvest_token_encrypted IS NOT NULL'):
            value = cipher.decrypt(bytes(encrypted))
            require(bool(value), 'Moscow stored token cannot be decrypted')
            del value
    return {'role': role, 'moscow_active': True, 'integrity': True, 'original_key_preserved': True,
        'stored_tokens_decryptable': True, 'archive_sha256': checksum}


if __name__ == '__main__':
    try:
        result = probe(sys.argv[1] if len(sys.argv) == 2 else '')
    except Exception as error:
        # Do not print settings, user values or exception details from dependencies.
        print('READ_ONLY_RETIREMENT_PROBE_FAILED=' + type(error).__name__, file=sys.stderr)
        sys.exit(1)
    print(json.dumps(result, sort_keys=True))
