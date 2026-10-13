"""Create at most ONE provider backup of the existing verified Moscow disk.

Uses documented server-disk-backup API only. Does not restore a backup, stop a
server, resize/create/delete a VM, alter credentials or touch the old server.
A provider backup is NOT a guarantee against every disaster or server deletion.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request

SERVER_ID = 9334503
SERVER_NAME = 'analyst-ai-ru-stage-9326369'
COMMENT = 'Analyst AI final Moscow migration recovery 2026-10-13'
BASE = 'https://api.timeweb.cloud/api/v1'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def cloud(method, path, body=None):
    server_path = '/servers/' + str(SERVER_ID)
    disk_backup = re.fullmatch(re.escape(server_path) + r'/disks/([1-9][0-9]*)/backups(?:/([1-9][0-9]*))?', path)
    allowed = method == 'GET' and (path == server_path or disk_backup is not None)
    allowed = allowed or (method == 'POST' and disk_backup is not None and disk_backup.group(2) is None and body == {'comment': COMMENT})
    require(allowed, 'Operation outside one-backup scope')
    token = os.environ.get('TIMEWEB_CLOUD_TOKEN', '').strip()
    require(bool(token), 'Cloud credential is missing')
    request = urllib.request.Request(BASE + path, method=method,
        data=None if body is None else json.dumps(body).encode(),
        headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/json', 'Content-Type': 'application/json'})
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=35) as response:
            raw = response.read(2000001)
        require(len(raw) <= 2000000, 'Oversized response; stop and reconcile')
        result = json.loads(raw)
        require(isinstance(result, dict), 'Unexpected cloud response')
        return result
    except urllib.error.HTTPError as error:
        # No uncertain POST retries and no provider response body or secrets in logs.
        raise RuntimeError('Backup API HTTP ' + str(error.code) + '; inspect inventory before retry') from None


def selected_disk(server):
    expected = {'id': SERVER_ID, 'name': SERVER_NAME, 'location': 'ru-3', 'availability_zone': 'msk-1',
                'preset_id': 6871, 'cpu': 2, 'ram': 2048, 'status': 'on'}
    require(isinstance(server, dict) and all(server.get(key) == value for key, value in expected.items()),
            'Moscow server identity/configuration changed')
    disks = server.get('disks')
    require(isinstance(disks, list) and len(disks) == 1 and isinstance(disks[0], dict), 'Expected one existing disk')
    disk = disks[0]
    require(disk.get('is_system') is True and disk.get('size') == 40960 and disk.get('type') == 'nvme', 'Moscow disk changed')
    require(type(disk.get('id')) is int and disk['id'] > 0 and disk.get('status') == 'done', 'Invalid or unavailable disk')
    return disk['id']


def list_backups(path):
    payload = cloud('GET', path)
    rows = payload.get('backups')
    require(isinstance(rows, list) and all(isinstance(row, dict) for row in rows), 'Malformed backup inventory')
    total = payload.get('meta', {}).get('total')
    require(type(total) is int and total == len(rows), 'Incomplete backup inventory; no purchase')
    return rows


def main():
    disk_id = selected_disk(cloud('GET', '/servers/' + str(SERVER_ID)).get('server'))
    path = '/servers/' + str(SERVER_ID) + '/disks/' + str(disk_id) + '/backups'
    existing = list_backups(path)
    owned = [row for row in existing if row.get('comment') == COMMENT]
    require(len(owned) <= 1, 'Duplicate migration backups; no additional purchase')
    if existing and not owned:
        print('MOSCOW_BACKUP=existing_backups_preserved_no_additional_order', flush=True)
        return
    if owned:
        backup = owned[0]
    else:
        backup = cloud('POST', path, {'comment': COMMENT}).get('backup')
    require(isinstance(backup, dict) and type(backup.get('id')) is int and backup['id'] > 0,
            'Uncertain backup creation response; no retry')
    identifier = backup['id']
    print('MOSCOW_BACKUP_TRACKING=' + json.dumps({'server_id': SERVER_ID, 'disk_id': disk_id,
          'backup_id': identifier, 'created_new': not bool(owned), 'server_deleted': False,
          'recurring_backup_schedule_configured': False}), flush=True)
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        value = cloud('GET', path + '/' + str(identifier)).get('backup')
        require(isinstance(value, dict) and value.get('id') == identifier and value.get('comment') == COMMENT,
                'Backup identity changed')
        status = value.get('status')
        if status == 'done':
            selected_disk(cloud('GET', '/servers/' + str(SERVER_ID)).get('server'))
            print('MOSCOW_PROVIDER_BACKUP_READY=' + json.dumps({'server_id': SERVER_ID,
                'disk_id': disk_id, 'backup_id': identifier, 'status': status,
                'restore_test': 'not_performed_on_live_server', 'old_server_deleted': False}), flush=True)
            return
        require(status in ('precreate', 'create'), 'Backup not ready; unexpected status ' + str(status))
        time.sleep(10)
    raise RuntimeError('Backup creation still pending; do not order another')


if __name__ == '__main__':
    main()
