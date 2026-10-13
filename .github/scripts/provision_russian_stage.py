"""Provision at most one owner-authorized Russian staging VM; preserve source."""
from __future__ import annotations
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

SOURCE_ID = 9326369
SOURCE_NAME = 'analyst-ai-backend'
TARGET_NAME = 'analyst-ai-ru-stage-9326369'
TARGET_COMMENT = 'Owner-authorized RU migration 2026-10-13; source 9326369; staging only'
PRESETS = ((4799, 'ru-3'), (2451, 'ru-1'), (4241, 'ru-2'))
ZONES = {'ru-3': 'msk-1', 'ru-1': 'spb-3', 'ru-2': 'nsk-1'}
BASE = 'https://api.timeweb.cloud/api/v1'
MAX_PRICE = 2600

class CloudError(RuntimeError):
    def __init__(self, status, code):
        super().__init__(f'Timeweb HTTP {status}, code={code}')
        self.status, self.code = status, code

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def call(method, path, body=None):
    if method == 'POST' and path != '/servers':
        raise RuntimeError('Mutation outside provisioning scope')
    if method not in ('GET', 'POST') or not path.startswith('/') or '..' in path:
        raise RuntimeError('Invalid request')
    token = os.environ.get('TIMEWEB_CLOUD_TOKEN', '').strip()
    if not token:
        raise RuntimeError('TIMEWEB_CLOUD_TOKEN unavailable')
    request = urllib.request.Request(BASE + path, method=method,
        data=None if body is None else json.dumps(body).encode(),
        headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/json', 'Content-Type': 'application/json'})
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=45) as response:
            raw = response.read(4_000_001)
        if len(raw) > 4_000_000:
            raise RuntimeError('Oversized response; reconcile resource state')
        return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        code = 'unknown'
        try:
            detail = json.loads(exc.read(65536))
            candidate = detail.get('error_code', '')
            if isinstance(candidate, str) and re.fullmatch(r'[a-zA-Z0-9_-]{1,120}', candidate):
                code = candidate
        except (ValueError, AttributeError):
            pass
        raise CloudError(exc.code, code) from None

def select_presets(payload):
    rows = payload.get('server_presets')
    if not isinstance(rows, list) or payload.get('meta', {}).get('total') != len(rows):
        raise RuntimeError('Incomplete preset catalog')
    selected = []
    for identifier, location in PRESETS:
        matches = [p for p in rows if isinstance(p, dict) and p.get('id') == identifier]
        if len(matches) != 1:
            raise RuntimeError('Preset identity absent or ambiguous')
        p = matches[0]
        required = {'location': location, 'cpu': 2, 'ram': 2048, 'disk': 40960, 'disk_type': 'nvme', 'cpu_frequency': '3.3'}
        if any(p.get(k) != v for k, v in required.items()):
            raise RuntimeError('Preset resources/location changed')
        price = p.get('price')
        if type(price) not in (int, float) or not 0 < price <= MAX_PRICE:
            raise RuntimeError('Preset exceeds the server price ceiling')
        selected.append(p)
    return selected

def inventory():
    payload = call('GET', '/servers')
    rows = payload.get('servers')
    if not isinstance(rows, list) or any(not isinstance(p, dict) for p in rows):
        raise RuntimeError('Invalid inventory')
    if type(payload.get('meta', {}).get('total')) is not int or payload['meta']['total'] != len(rows):
        raise RuntimeError('Incomplete inventory; no creation')
    return rows

def target_from(rows):
    matches = [p for p in rows if p.get('name') == TARGET_NAME]
    if len(matches) > 1:
        raise RuntimeError('Duplicate staging VM; reconcile before continuing')
    if not matches:
        return None
    result = matches[0]
    approved = dict(PRESETS)
    if (type(result.get('id')) is not int or result['id'] <= 0 or result['id'] == SOURCE_ID
        or result.get('comment') != TARGET_COMMENT
        or approved.get(result.get('preset_id')) != result.get('location')
        or result.get('cpu') != 2 or result.get('ram') != 2048
        or ZONES.get(result.get('location')) != result.get('availability_zone')):
        raise RuntimeError('Unexpected staging VM identity/resources/zone')
    return result

def report(target, state):
    safe = {k: target.get(k) for k in ('id', 'name', 'status', 'location', 'availability_zone', 'cpu', 'ram', 'preset_id')}
    print('RUSSIA_STAGE=' + json.dumps({'at': datetime.now(timezone.utc).isoformat(), 'stage': state,
        'source_id': SOURCE_ID, 'source_untouched': True, 'data_copied': False, 'old_server_deleted': False,
        'target': safe}, ensure_ascii=True), flush=True)

def main():
    source = call('GET', f'/servers/{SOURCE_ID}').get('server', {})
    if source.get('id') != SOURCE_ID or source.get('name') != SOURCE_NAME or source.get('location') != 'kz-1':
        raise RuntimeError('Source identity/location changed; stop')
    presets = select_presets(call('GET', '/presets/servers'))
    target = target_from(inventory())
    if target is None:
        for preset in presets:
            try:
                payload = call('POST', '/servers', {'name': TARGET_NAME, 'comment': TARGET_COMMENT,
                    'os_id': 99, 'preset_id': preset['id'], 'availability_zone': ZONES[preset['location']],
                    'bandwidth': 1000, 'is_ddos_guard': False, 'is_local_network': False, 'ssh_keys_ids': []})
            except CloudError as exc:
                print('CAPACITY_ATTEMPT=' + json.dumps({'preset_id': preset['id'], 'location': preset['location'],
                    'zone': ZONES[preset['location']], 'http_status': exc.status, 'error_code': exc.code}), flush=True)
                rejected = ((exc.status in (400, 409, 422) and exc.code in ('no_free_node', 'location_not_available'))
                            or (exc.status == 404 and exc.code == 'preset_not_found'))
                if rejected:
                    if target_from(inventory()) is not None:
                        raise RuntimeError('Resource appeared despite rejection; stop')
                    continue
                raise
            created = payload.get('server')
            if not isinstance(created, dict) or type(created.get('id')) is not int:
                raise RuntimeError('Uncertain creation response; reconcile before another POST')
            target = call('GET', f"/servers/{created['id']}").get('server', {})
            target = target_from([target])
            if target is None or target.get('preset_id') != preset['id']:
                raise RuntimeError('Created VM identity mismatch; no further order')
            report(target, 'created_not_yet_ready')
            break
    if target is None:
        print('RUSSIA_CAPACITY=none_created_in_three_verified_presets; no preorders', flush=True)
        raise RuntimeError('Russian provisioning rejected; source remains unchanged')
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        current = call('GET', f"/servers/{target['id']}").get('server', {})
        checked = target_from([current])
        if checked is None:
            raise RuntimeError('Staging VM disappeared')
        if checked.get('status') == 'on':
            report(checked, 'vm_on_waiting_for_secure_data_copy')
            return
        if checked.get('status') not in ('installing', 'turning_on', 'rebooting', 'off'):
            report(checked, 'unexpected_state_no_cutover')
            raise RuntimeError('VM not ready; no automatic second order')
        time.sleep(10)
    report(target, 'startup_timeout_no_cutover')
    raise RuntimeError('Staging startup timeout; no automatic second order')

if __name__ == '__main__':
    main()
