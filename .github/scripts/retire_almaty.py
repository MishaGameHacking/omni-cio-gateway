"""Retire only owner-confirmed old VM 9326369 and its orphaned IPv4.

No target mutation, provisioning, resize, restore, account/security changes or
confirmation bypass. A provider 423 stops retirement; no guessed OTPs/retries.
"""
from __future__ import annotations
import ipaddress
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import parse_qs, urlparse
from uuid import UUID

SOURCE = 9326369
TARGET = 9334503
DISK = 26060189
BACKUP = 106582657
OLD_IP = '94.198.220.228'
NEW_IP = '176.98.178.81'
BASE = 'https://api.timeweb.cloud/api/v1'
HOST = 'https://' + NEW_IP + '.sslip.io'
BACKUP_PATH = f'/servers/{TARGET}/disks/{DISK}/backups/{BACKUP}'


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class CloudError(RuntimeError):
    def __init__(self, status):
        super().__init__('Cloud HTTP ' + str(status))
        self.status = status


def permitted(method, path, key_id=None, ip_id=None):
    reads = {'/servers', '/floating-ips', BACKUP_PATH}
    reads |= {f'/servers/{n}' for n in (SOURCE, TARGET)}
    reads |= {f'/servers/{n}/ips' for n in (SOURCE, TARGET)}
    writes = {('POST', '/ssh-keys')}
    writes |= {('POST', f'/servers/{n}/ssh-keys') for n in (SOURCE, TARGET)}
    if type(key_id) is int and key_id > 0:
        writes |= {('DELETE', f'/servers/{n}/ssh-keys/{key_id}') for n in (SOURCE, TARGET)}
        writes.add(('DELETE', f'/ssh-keys/{key_id}'))
    if ip_id is not None and str(UUID(ip_id)) == ip_id:
        reads.add('/floating-ips/' + ip_id)
        writes.add(('DELETE', '/floating-ips/' + ip_id))
    writes.add(('DELETE', f'/servers/{SOURCE}'))
    return method == 'GET' and path in reads or (method, path) in writes


def cloud(method, path, body=None, *, key_id=None, ip_id=None, allow_missing=False):
    require(permitted(method, path, key_id, ip_id), 'Operation outside retirement scope')
    credential = os.environ.get('TIMEWEB_CLOUD_TOKEN', '').strip()
    require(bool(credential), 'Missing cloud credential')
    req = urllib.request.Request(BASE + path, method=method,
        data=None if body is None else json.dumps(body).encode(),
        headers={'Authorization': 'Bearer ' + credential, 'Accept': 'application/json', 'Content-Type': 'application/json'})
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=35) as response:
            raw = response.read(2000001)
        require(len(raw) <= 2000000, 'Oversized cloud response')
        value = json.loads(raw) if raw else {}
        require(isinstance(value, dict), 'Malformed cloud response')
        return value
    except urllib.error.HTTPError as error:
        if allow_missing and method == 'GET' and error.code == 404:
            return None
        # Do not expose confirmation hashes, messages, settings or secrets.
        raise CloudError(error.code) from None


def collection(payload, name):
    rows = payload.get(name)
    require(isinstance(rows, list) and all(isinstance(row, dict) for row in rows), 'Malformed inventory')
    meta = payload.get('meta')
    require(isinstance(meta, dict) and type(meta.get('total')) is int and meta['total'] == len(rows), 'Incomplete inventory')
    return rows


def validate_server(server, target):
    expected = {'id': TARGET if target else SOURCE, 'name': 'analyst-ai-ru-stage-9326369' if target else 'analyst-ai-backend',
        'location': 'ru-3' if target else 'kz-1', 'availability_zone': 'msk-1' if target else 'ala-1',
        'preset_id': 6871 if target else 3795, 'cpu': 2, 'ram': 2048, 'status': 'on'}
    require(isinstance(server, dict) and all(server.get(k) == v for k, v in expected.items()), 'Server identity or resources changed')
    disks = server.get('disks')
    require(isinstance(disks, list) and len(disks) == 1, 'Unexpected server disks; preserve all data')
    disk = disks[0]
    require(isinstance(disk, dict) and disk.get('is_system') is True and disk.get('size') == 40960, 'Disk identity changed')
    if target:
        require(disk.get('id') == DISK and disk.get('status') == 'done', 'Moscow system disk not ready')
    return server


def validate_backup(value):
    require(isinstance(value, dict) and value.get('id') == BACKUP and value.get('status') == 'done'
        and value.get('comment') == 'Analyst AI final Moscow migration recovery 2026-10-13', 'Verified recovery backup is not available')


def selected_ip(rows, address, zone, resource):
    matches = [row for row in rows if row.get('ip') == address]
    require(len(matches) == 1, 'Expected unique known IP')
    row = matches[0]
    identifier = row.get('id')
    require(isinstance(identifier, str) and str(UUID(identifier)) == identifier, 'Invalid floating IP ID')
    require(row.get('availability_zone') == zone, 'Unexpected IP zone')
    require(str(ipaddress.ip_address(row['ip'])) == address, 'Unexpected IP address')
    if resource is None:
        require('resource_type' in row and 'resource_id' in row and row['resource_type'] is None
            and row['resource_id'] is None, 'Old IP is still attached; do not disconnect another service')
    else:
        require(row.get('resource_type') == 'server' and str(row.get('resource_id')) == str(resource), 'IP attached to unexpected resource')
    return row


def public_check():
    opener = urllib.request.build_opener(NoRedirect())
    with opener.open(HOST + '/health', timeout=15) as response:
        require(response.status == 200 and json.loads(response.read(2048)) == {'status': 'ok'}, 'Moscow HTTPS health failed')
    try:
        opener.open(HOST + '/me', timeout=15).close()
    except urllib.error.HTTPError as error:
        require(error.code == 401, 'Moscow authentication guard failed')
    else:
        raise RuntimeError('Anonymous user access unexpectedly allowed')
    try:
        opener.open(HOST + '/auth/telegram/start', timeout=15).close()
    except urllib.error.HTTPError as error:
        require(error.code == 302, 'Moscow OAuth start failed')
        redirect = urlparse(error.headers.get('Location', ''))
        fields = parse_qs(redirect.query)
        require(redirect.scheme == 'https' and redirect.netloc == 'oauth.telegram.org' and redirect.path == '/auth', 'Unexpected auth destination')
        require(fields.get('redirect_uri') == [HOST + '/auth/telegram/callback']
            and fields.get('code_challenge_method') == ['S256'] and bool(fields.get('state')), 'Wrong callback or missing PKCE')
    else:
        raise RuntimeError('OAuth redirect missing')


def inventory():
    servers = collection(cloud('GET', '/servers'), 'servers')
    target = cloud('GET', f'/servers/{TARGET}').get('server')
    validate_server(target, True)
    validate_backup(cloud('GET', BACKUP_PATH).get('backup'))
    ips = collection(cloud('GET', '/floating-ips'), 'ips')
    selected_ip(ips, NEW_IP, 'msk-1', TARGET)
    require(any(row.get('id') == TARGET for row in servers), 'Moscow missing from full server inventory')
    public_check()
    return servers, ips


def state_path():
    return Path(os.environ['RETIREMENT_STATE_WINDOWS'])


def save(record):
    state_path().write_text(json.dumps(record, sort_keys=True), encoding='utf-8')


def emit(name, record):
    print(name + '=' + json.dumps(record, sort_keys=True), flush=True)


def prepare():
    require(not state_path().exists(), 'Retirement attempt already has state; reconcile first')
    servers, ips = inventory()
    source = cloud('GET', f'/servers/{SOURCE}', allow_missing=True)
    require(source is not None, 'Source already absent; use a separate orphan-IP audit')
    validate_server(source.get('server'), False)
    old = selected_ip(ips, OLD_IP, 'ala-1', SOURCE)
    run = os.environ.get('GITHUB_RUN_ID', '')
    require(re.fullmatch('[0-9]{1,20}', run) is not None, 'Invalid run')
    public = Path(os.environ['RETIREMENT_PUBLIC_WINDOWS']).read_text().strip()
    require(re.fullmatch(r'ssh-ed25519 [A-Za-z0-9+/=]+ analyst-retire-[0-9]+', public) is not None, 'Invalid ephemeral public key')
    record = {'run': run, 'prepared_at': time.time(), 'old_ip_id': old['id'], 'attached': [], 'keys_cleaned': False}
    save(record)
    result = cloud('POST', '/ssh-keys', {'name': 'analyst-retire-' + run, 'body': public, 'is_default': False})
    key = result.get('ssh-key', result.get('ssh_key', {}))
    require(type(key.get('id')) is int and key['id'] > 0, 'Ambiguous key creation; no retry')
    record['key_id'] = key['id']
    save(record)
    for identifier in (SOURCE, TARGET):
        cloud('POST', f'/servers/{identifier}/ssh-keys', {'ssh_key_ids': [key['id']]})
        record['attached'].append(identifier)
        save(record)
    emit('RETIREMENT_PREFLIGHT', {'source_id': SOURCE, 'source_region': 'ala-1', 'retained_id': TARGET,
        'retained_region': 'msk-1', 'backup_id': BACKUP, 'backup_ready': True, 'other_servers':
        [{k: row.get(k) for k in ('id', 'name', 'location', 'availability_zone')} for row in servers if row.get('id') not in (SOURCE, TARGET)]})


def cleanup():
    if not state_path().exists():
        return
    record = json.loads(state_path().read_text())
    key = record.get('key_id')
    if key is None:
        return
    failures = []
    for path in [f'/servers/{n}/ssh-keys/{key}' for n in (SOURCE, TARGET)] + [f'/ssh-keys/{key}']:
        try:
            cloud('DELETE', path, key_id=key)
        except CloudError as error:
            if error.status != 404:
                failures.append(error.status)
    require(not failures, 'Temporary SSH-key cleanup failed; retirement blocked')
    record['keys_cleaned'] = True
    save(record)
    emit('RETIREMENT_KEY_CLEANUP', {'success': True})


def verify_evidence(record, source, target):
    require(record.get('keys_cleaned') is True, 'Temporary key cleanup required')
    age = time.time() - record.get('prepared_at', 0)
    require(0 <= age <= 900, 'Retirement evidence expired')
    require(source.get('role') == 'source' and source.get('source_frozen') is True, 'Source still requires final migration')
    fields = ('moscow_active', 'integrity', 'original_key_preserved', 'stored_tokens_decryptable')
    require(target.get('role') == 'target' and all(target.get(k) is True for k in fields), 'Moscow recovery probe failed')
    checksum = target.get('archive_sha256', '')
    require(re.fullmatch('[0-9a-f]{64}', checksum) is not None and source.get('archive_sha256') == checksum,
        'Source and target final archives differ')


def wait_absent(path, ip_id=None):
    for _ in range(30):
        if cloud('GET', path, ip_id=ip_id, allow_missing=True) is None:
            return True
        time.sleep(5)
    return False


def retire():
    record = json.loads(state_path().read_text())
    folder = state_path().parent
    source_probe = json.loads((folder / 'source.json').read_text(encoding='utf-8-sig'))
    target_probe = json.loads((folder / 'target.json').read_text(encoding='utf-8-sig'))
    verify_evidence(record, source_probe, target_probe)
    servers, ips = inventory()
    validate_server(cloud('GET', f'/servers/{SOURCE}').get('server'), False)
    old = selected_ip(ips, OLD_IP, 'ala-1', SOURCE)
    require(old['id'] == record['old_ip_id'], 'Old IP changed since preflight')
    try:
        cloud('DELETE', f'/servers/{SOURCE}')
    except CloudError as error:
        emit('RETIREMENT_NOT_COMPLETED', {'source_id': SOURCE, 'http_status': error.status,
            'provider_confirmation_or_lock': error.status == 423, 'ip_delete_attempted': False,
            'moscow_untouched': True})
        return 2
    require(wait_absent(f'/servers/{SOURCE}'), 'Source deletion accepted but not yet confirmed; IP retained')
    # Positive readback is required, not a successful DELETE response alone.
    servers, ips = inventory()
    require(not any(row.get('id') == SOURCE for row in servers), 'Source remains in inventory')
    existing = [row for row in ips if row.get('ip') == OLD_IP]
    if existing:
        old = selected_ip(ips, OLD_IP, 'ala-1', None)
        require(old['id'] == record['old_ip_id'], 'Orphan IP identity changed')
        path = '/floating-ips/' + old['id']
        current = cloud('GET', path, ip_id=old['id']).get('ip')
        selected_ip([current], OLD_IP, 'ala-1', None)
        cloud('DELETE', path, ip_id=old['id'])
        require(wait_absent(path, ip_id=old['id']), 'IP deletion is not yet confirmed')
    servers, ips = inventory()
    require(not any(row.get('ip') == OLD_IP for row in ips), 'Old IP remains billable')
    foreign = [row for row in servers if not str(row.get('location', '')).startswith('ru-')]
    emit('RETIREMENT_VERIFIED', {'old_server_deleted': True, 'old_ip_deleted': True,
        'retained_id': TARGET, 'region': 'msk-1', 'backup_ready': True, 'public_health': True,
        'servers': [{k: row.get(k) for k in ('id', 'name', 'location', 'availability_zone', 'cpu', 'ram')} for row in servers],
        'remaining_non_russian_server_count': len(foreign), 'new_resources_ordered': False})
    return 0


if __name__ == '__main__':
    try:
        action = sys.argv[1] if len(sys.argv) == 2 else ''
        if action == 'prepare':
            prepare()
        elif action == 'cleanup':
            cleanup()
        elif action == 'retire':
            sys.exit(retire())
        else:
            raise RuntimeError('Unknown retirement action')
    except Exception as error:
        print('RETIREMENT_STOPPED=' + type(error).__name__ + '; reconcile current state before any retry', flush=True)
        sys.exit(1)
