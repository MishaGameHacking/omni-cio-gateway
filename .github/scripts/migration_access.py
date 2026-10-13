"""Temporary SSH access and one IPv4 for two exact owner-authorized VMs.

No VM deletion, resize, reset, new-server order, secret output, or source stop.
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

BASE = 'https://api.timeweb.cloud/api/v1'
SOURCE = 9326369
TARGET = 9334503
TARGET_NAME = 'analyst-ai-ru-stage-9326369'
COMMENT = 'Owner-authorized RU migration 2026-10-13; source 9326369; staging only'

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

class ApiError(RuntimeError):
    def __init__(self, status):
        super().__init__('Cloud API HTTP ' + str(status))
        self.status = status

def api(method, path, payload=None, key_id=None):
    permitted = {('GET', f'/servers/{n}') for n in (SOURCE, TARGET)}
    permitted |= {('GET', f'/servers/{n}/ips') for n in (SOURCE, TARGET)}
    permitted |= {('POST', f'/servers/{TARGET}/ips'), ('POST', '/ssh-keys')}
    permitted |= {('POST', f'/servers/{n}/ssh-keys') for n in (SOURCE, TARGET)}
    if type(key_id) is int and key_id > 0:
        permitted |= {('DELETE', f'/servers/{n}/ssh-keys/{key_id}') for n in (SOURCE, TARGET)}
        permitted.add(('DELETE', f'/ssh-keys/{key_id}'))
    if (method, path) not in permitted:
        raise RuntimeError('Operation outside migration access scope')
    token = os.environ.get('TIMEWEB_CLOUD_TOKEN', '').strip()
    if not token:
        raise RuntimeError('Missing cloud credential')
    req = urllib.request.Request(BASE + path, method=method,
        data=None if payload is None else json.dumps(payload).encode(),
        headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json', 'Accept': 'application/json'})
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=40) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise RuntimeError('Oversized cloud response; reconcile before retry')
        return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raise ApiError(exc.code) from None

def validate_pair():
    for identifier, name, location, zone, preset in ((SOURCE, 'analyst-ai-backend', 'kz-1', 'ala-1', 3795),
            (TARGET, TARGET_NAME, 'ru-3', 'msk-1', 6871)):
        actual = api('GET', f'/servers/{identifier}').get('server', {})
        expected = {'id': identifier, 'name': name, 'location': location, 'availability_zone': zone,
                    'preset_id': preset, 'cpu': 2, 'ram': 2048, 'status': 'on'}
        if any(actual.get(k) != v for k, v in expected.items()):
            raise RuntimeError('Server identity/resources/status changed')
        if identifier == TARGET and actual.get('comment') != COMMENT:
            raise RuntimeError('Target ownership marker changed')

def ipv4(identifier):
    payload = api('GET', f'/servers/{identifier}/ips')
    entries = payload.get('server_ips')
    if not isinstance(entries, list):
        raise RuntimeError('Unexpected IP inventory')
    ips = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise RuntimeError('Malformed IP record')
        if entry.get('type') != 'ipv4':
            continue
        value = ipaddress.ip_address(entry.get('ip', ''))
        if value.version != 4 or not value.is_global:
            raise RuntimeError('Expected global IPv4')
        ips.append(str(value))
    if len(ips) > 1:
        raise RuntimeError('Ambiguous public IPv4; no automatic change')
    return ips[0] if ips else None

def state_path():
    return Path(os.environ['MIGRATION_STATE_WINDOWS'])

def prepare():
    validate_pair()
    source_ip = ipv4(SOURCE)
    if source_ip != '94.198.220.228':
        raise RuntimeError('Source public address changed')
    target_ip = ipv4(TARGET)
    if target_ip is None:
        api('POST', f'/servers/{TARGET}/ips', {'type': 'ipv4'})
        print('MIGRATION_IP_ORDERED=one_ipv4_for_moscow_staging', flush=True)
        for _ in range(36):
            target_ip = ipv4(TARGET)
            if target_ip:
                break
            time.sleep(5)
    if not target_ip:
        raise RuntimeError('Target IPv4 is not ready; do not order another')
    run = os.environ.get('GITHUB_RUN_ID', '')
    if not re.fullmatch(r'[0-9]{1,20}', run):
        raise RuntimeError('Unexpected run identifier')
    public = Path(os.environ['MIGRATION_PUBLIC_WINDOWS']).read_text().strip()
    if not re.fullmatch(r'ssh-ed25519 [A-Za-z0-9+/=]+ analyst-migrate-[0-9]+', public):
        raise RuntimeError('Unexpected generated SSH key')
    key = api('POST', '/ssh-keys', {'name': 'analyst-migrate-' + run, 'body': public, 'is_default': False})
    record = key.get('ssh-key', key.get('ssh_key', {}))
    key_id = record.get('id')
    if type(key_id) is not int or key_id <= 0:
        raise RuntimeError('Uncertain SSH-key creation; inspect before retry')
    state = {'key_id': key_id, 'source_ip': source_ip, 'target_ip': target_ip, 'attached': []}
    state_path().write_text(json.dumps(state), encoding='utf-8')
    for identifier in (SOURCE, TARGET):
        api('POST', f'/servers/{identifier}/ssh-keys', {'ssh_key_ids': [key_id]})
        state['attached'].append(identifier)
        state_path().write_text(json.dumps(state), encoding='utf-8')
    print('MIGRATION_ACCESS_READY=' + json.dumps({'source_id': SOURCE, 'target_id': TARGET,
        'target_zone': 'msk-1', 'target_ipv4': target_ip, 'temporary_key_id': key_id}), flush=True)

def cleanup():
    path = state_path()
    if not path.exists():
        return
    state = json.loads(path.read_text(encoding='utf-8'))
    key_id = state.get('key_id')
    if type(key_id) is not int or key_id <= 0:
        raise RuntimeError('Invalid cleanup key ID')
    failed = []
    for uri in (f'/servers/{SOURCE}/ssh-keys/{key_id}', f'/servers/{TARGET}/ssh-keys/{key_id}', f'/ssh-keys/{key_id}'):
        try:
            api('DELETE', uri, key_id=key_id)
        except ApiError as exc:
            if exc.status != 404:
                failed.append({'endpoint': uri, 'http_status': exc.status})
        except (OSError, ValueError):
            failed.append({'endpoint': uri, 'error': 'network_or_response'})
    if failed:
        print('MIGRATION_KEY_CLEANUP_INCOMPLETE=' + json.dumps(failed), flush=True)
        raise RuntimeError('Temporary key cleanup incomplete')
    print('MIGRATION_KEY_CLEANUP=success', flush=True)

if __name__ == '__main__':
    action = sys.argv[1] if len(sys.argv) == 2 else ''
    if action == 'prepare':
        prepare()
    elif action == 'cleanup':
        cleanup()
    else:
        raise SystemExit('Expected prepare or cleanup')
