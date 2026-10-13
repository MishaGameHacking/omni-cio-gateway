"""Restore and verify an initial snapshot; no source cutover or deletion."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sqlite3
import sys
import tarfile


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1_048_576), b''):
            h.update(block)
    return h.hexdigest()


def unpack(stage, run, host, expected_hash):
    if Path('/var/lib/analyst-ai/backend.db').exists() or Path('/etc/analyst-ai/backend.env').exists():
        raise RuntimeError('Target already has application data; refusing overwrite')
    archive = stage / 'application.tgz'
    if digest(archive) != expected_hash:
        raise RuntimeError('Archive changed in transit')
    destination = stage / 'restored'
    destination.mkdir(mode=0o700, exist_ok=False)
    with tarfile.open(archive, 'r:gz') as bundle:
        entries = bundle.getmembers()
        for item in entries:
            name = PurePosixPath(item.name)
            if name.is_absolute() or '..' in name.parts or not name.parts or name.parts[0] not in {'data', 'code', 'config', 'manifest.json'}:
                raise RuntimeError('Unexpected archive path')
            if not item.isfile() and not item.isdir():
                raise RuntimeError('Unexpected archive entry type')
        bundle.extractall(destination, filter='data')
    manifest = json.loads((destination / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('source_id') != 9326369 or manifest.get('target_id') != 9334503 or manifest.get('run') != run or manifest.get('final_cutover') is not False:
        raise RuntimeError('Migration manifest identity mismatch')
    files = {str(p.relative_to(destination)) for p in destination.rglob('*') if p.is_file()} - {'manifest.json'}
    if files != set(manifest['files']):
        raise RuntimeError('Migration file set mismatch')
    for name in files:
        if digest(destination / name) != manifest['files'][name]:
            raise RuntimeError('Migration file checksum mismatch')
    for source, target in ((destination / 'data', Path('/var/lib/analyst-ai')), (destination / 'code', Path('/opt/analyst-ai/backend'))):
        if target.exists():
            raise RuntimeError('Target application directory is not empty')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target)
    Path('/opt/analyst-ai').chmod(0o755)
    config = Path('/etc/analyst-ai')
    config.mkdir(mode=0o700, exist_ok=False)
    original = (destination / 'config/backend.env').read_text(encoding='utf-8')
    lines = [line for line in original.splitlines() if not line.startswith(('BACKEND_PUBLIC_URL=', 'ANALYSIS_SCHEDULER_ENABLED='))]
    lines.extend(['BACKEND_PUBLIC_URL=https://' + host, 'ANALYSIS_SCHEDULER_ENABLED=false'])
    (config / 'backend.env').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    (config / 'backend.env').chmod(0o600)
    (config / 'migration-staging.json').write_text(json.dumps({'source_id': 9326369, 'target_id': 9334503,
        'source_snapshot_at': manifest['snapshot_at'], 'run': run, 'cutover': False, 'public_ready': False}), encoding='utf-8')
    shutil.copyfile(destination / 'config/backend.service', '/etc/systemd/system/analyst-ai-backend.service')
    Path('/etc/caddy/Caddyfile').write_text(host + ' {\n    @health path /health\n    handle @health {\n        reverse_proxy 127.0.0.1:8080\n    }\n    handle {\n        respond "Migration staging: not yet switched" 503\n    }\n}\n', encoding='utf-8')
    for path in Path('/opt/analyst-ai/backend').rglob('*'):
        path.chmod(0o755 if path.is_dir() else 0o644)
    Path('/opt/analyst-ai/backend').chmod(0o755)
    for path in [Path('/var/lib/analyst-ai'), *Path('/var/lib/analyst-ai').rglob('*')]:
        shutil.chown(path, user='www-data', group='www-data')
        path.chmod(0o750 if path.is_dir() else 0o640)
    print('RESTORE_COPY=checksums_verified_public_routes_closed', flush=True)


def verify(stage):
    from dotenv import dotenv_values
    from cryptography.fernet import Fernet
    source = dotenv_values(stage / 'restored/config/backend.env')
    target = dotenv_values('/etc/analyst-ai/backend.env')
    if source.get('FERNET_KEY') != target.get('FERNET_KEY') or not target.get('FERNET_KEY'):
        raise RuntimeError('Encryption key was not preserved')
    permitted_changes = {'BACKEND_PUBLIC_URL', 'ANALYSIS_SCHEDULER_ENABLED'}
    if any(source.get(k) != target.get(k) for k in (set(source) | set(target)) - permitted_changes):
        raise RuntimeError('Unexpected configuration change')
    if target.get('ANALYSIS_SCHEDULER_ENABLED') != 'false':
        raise RuntimeError('Staging scheduler must remain disabled')
    cipher = Fernet(target['FERNET_KEY'].encode())
    manifest = json.loads((stage / 'restored/manifest.json').read_text(encoding='utf-8'))
    with sqlite3.connect('file:/var/lib/analyst-ai/backend.db?mode=ro', uri=True) as db:
        if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise RuntimeError('Restored database integrity failure')
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        counts = {name: db.execute('SELECT COUNT(*) FROM "' + name.replace('"', '""') + '"').fetchone()[0] for name in tables}
        if counts != manifest['table_counts']:
            raise RuntimeError('Database row counts differ from consistent snapshot')
        encrypted = db.execute('SELECT tinvest_token_encrypted FROM users WHERE tinvest_token_encrypted IS NOT NULL').fetchall()
        if len(encrypted) != manifest['encrypted_tokens_checked']:
            raise RuntimeError('Token count mismatch')
        for (token,) in encrypted:
            plaintext = cipher.decrypt(bytes(token))
            if not plaintext:
                raise RuntimeError('Invalid decrypted broker token')
            del plaintext
    print('RESTORE_VERIFIED=' + json.dumps({'integrity': 'ok', 'table_counts_equal': True,
        'encryption_key_preserved': True, 'all_tokens_decryptable': True, 'scheduler_enabled': False,
        'source_snapshot_at': manifest['snapshot_at'], 'cutover': False, 'old_server_deleted': False}), flush=True)


def main():
    action, run, host, archive_hash = sys.argv[1:]
    if os.geteuid() != 0 or not re.fullmatch(r'[0-9]{1,20}', run) or not re.fullmatch(r'(?:[0-9]{1,3}\.){3}[0-9]{1,3}\.sslip\.io', host) or not re.fullmatch(r'[0-9a-f]{64}', archive_hash):
        raise RuntimeError('Invalid restore arguments')
    stage = Path('/root/analyst-migration-' + run)
    if action == 'unpack':
        unpack(stage, run, host, archive_hash)
    elif action == 'verify':
        verify(stage)
    else:
        raise RuntimeError('Invalid restore action')

if __name__ == '__main__':
    main()
