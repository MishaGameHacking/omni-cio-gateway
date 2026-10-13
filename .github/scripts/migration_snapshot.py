"""Source-only initial private app snapshot, not the final quiesced cutover."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import tarfile
import time
from datetime import datetime, timezone


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1_048_576), b''):
            result.update(block)
    return result.hexdigest()


def backup_database(source, target):
    deadline = time.monotonic() + 120
    def progress(status, remaining, total):
        if time.monotonic() > deadline:
            raise RuntimeError('Snapshot deadline exceeded')
    with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True, timeout=10) as live:
        with sqlite3.connect(target) as backup:
            live.backup(backup, pages=128, progress=progress, sleep=0.1)
            if backup.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                raise RuntimeError('Database integrity check failed')
    target.chmod(0o600)


def main():
    run = sys.argv[1]
    if not re.fullmatch(r'[0-9]{1,20}', run) or os.geteuid() != 0:
        raise RuntimeError('Invalid execution context')
    os.umask(0o077)
    stage = Path('/root/analyst-migration-' + run)
    stage.mkdir(mode=0o700, exist_ok=False)
    bundle = stage / 'bundle'
    bundle.mkdir(mode=0o700)
    data = Path('/var/lib/analyst-ai')
    environment = Path('/etc/analyst-ai/backend.env')
    code = Path('/opt/analyst-ai/backend')
    if any(p.is_symlink() for p in (data, environment, code)) or not (data / 'backend.db').is_file():
        raise RuntimeError('Unexpected application layout')
    from dotenv import dotenv_values
    settings = dotenv_values(environment)
    if settings.get('DATABASE_PATH') != str(data / 'backend.db'):
        raise RuntimeError('Application database path mismatch')
    from cryptography.fernet import Fernet
    cipher = Fernet(settings.get('FERNET_KEY', '').encode())
    copied = bundle / 'data'
    copied.mkdir(mode=0o700)
    for source in sorted(data.rglob('*')):
        relative = source.relative_to(data)
        if source.is_symlink():
            raise RuntimeError('Symlink in persistent application data')
        destination = copied / relative
        if source.is_dir():
            destination.mkdir(mode=0o700, exist_ok=True)
            continue
        if not source.is_file():
            raise RuntimeError('Unexpected persistent data type')
        if source.name.endswith(('-wal', '-shm', '-journal')):
            continue
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with source.open('rb') as handle:
            sqlite_file = handle.read(16) == b'SQLite format 3\x00'
        if sqlite_file:
            backup_database(source, destination)
        else:
            shutil.copyfile(source, destination)
            destination.chmod(0o600)
    code_target = bundle / 'code'
    code_target.mkdir(mode=0o700)
    for source in sorted(code.rglob('*')):
        relative = source.relative_to(code)
        if '__pycache__' in relative.parts or source.suffix == '.pyc':
            continue
        if source.is_symlink():
            raise RuntimeError('Unexpected symlink in application code')
        destination = code_target / relative
        if source.is_dir():
            destination.mkdir(mode=0o700, exist_ok=True)
        elif source.is_file():
            destination.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
            shutil.copyfile(source, destination)
        else:
            raise RuntimeError('Unexpected application code object')
    config = bundle / 'config'
    config.mkdir(mode=0o700)
    for source, name in ((environment, 'backend.env'),
            (Path('/etc/systemd/system/analyst-ai-backend.service'), 'backend.service'),
            (Path('/etc/caddy/Caddyfile'), 'Caddyfile')):
        if source.is_symlink() or not source.is_file():
            raise RuntimeError('Unexpected configuration layout')
        shutil.copyfile(source, config / name)
        (config / name).chmod(0o600)
    with sqlite3.connect((copied / 'backend.db').as_uri() + '?mode=ro', uri=True) as db:
        tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        counts = {name: db.execute('SELECT COUNT(*) FROM "' + name.replace('"', '""') + '"').fetchone()[0] for name in tables}
        encrypted = db.execute('SELECT tinvest_token_encrypted FROM users WHERE tinvest_token_encrypted IS NOT NULL').fetchall()
        for (token,) in encrypted:
            plain = cipher.decrypt(bytes(token))
            if not plain:
                raise RuntimeError('Empty broker token after decrypting snapshot')
            del plain
    hashes = {str(p.relative_to(bundle)): digest(p) for p in bundle.rglob('*') if p.is_file()}
    manifest = {'source_id': 9326369, 'target_id': 9334503, 'run': run,
        'snapshot_at': datetime.now(timezone.utc).isoformat(), 'final_cutover': False,
        'files': hashes, 'table_counts': counts, 'encrypted_tokens_checked': len(encrypted)}
    (bundle / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True), encoding='utf-8')
    archive = stage / 'application.tgz'
    with tarfile.open(archive, 'w:gz') as output:
        for path in sorted(bundle.rglob('*')):
            output.add(path, arcname=str(path.relative_to(bundle)), recursive=False)
    archive.chmod(0o600)
    print(json.dumps({'archive_sha256': digest(archive), 'bytes': archive.stat().st_size,
        'data_files': len([k for k in hashes if k.startswith('data/')]),
        'database_tables': len(counts), 'snapshot_at': manifest['snapshot_at'],
        'all_tokens_decryptable': True, 'final_cutover': False}), flush=True)

if __name__ == '__main__':
    main()
