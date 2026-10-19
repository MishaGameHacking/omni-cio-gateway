"""Read-only reconstruction preflight; output metadata, never backup contents."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

CLOUD = 'https://api.timeweb.cloud/api/v1'
REPO = 'https://api.github.com/repos/MishaGameHacking/omni-cio-gateway'
LIMIT = 4 * 1024 * 1024


class ProbeError(RuntimeError):
    """Non-secret diagnostic code."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ProbeError('redirect_refused')


def read_json(url: str, token: str):
    if not any(url.startswith(base + '/') for base in (CLOUD, REPO)):
        raise ProbeError('unapproved_api')
    request = urllib.request.Request(url, headers={
        'Authorization': 'Bearer ' + token, 'Accept': 'application/json',
        'User-Agent': 'AnalystAI-owner-rebuild',
    }, method='GET')
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=30) as response:
            raw = response.read(LIMIT + 1)
    except urllib.error.HTTPError as error:
        raise ProbeError('http_' + str(error.code)) from None
    except (OSError, urllib.error.URLError):
        raise ProbeError('transport_failed') from None
    if len(raw) > LIMIT:
        raise ProbeError('response_limit')
    try:
        return json.loads(raw)
    except (ValueError, UnicodeError):
        raise ProbeError('invalid_json') from None


def safe_get(url: str, token: str):
    try:
        return read_json(url, token)
    except ProbeError as error:
        return {'unavailable': str(error)}


def select_fields(item: dict, fields: tuple[str, ...]) -> dict:
    return {key: item[key] for key in fields if key in item}


def catalogue(token: str) -> dict:
    result = {}
    fields = ('id', 'name', 'location', 'availability_zone', 'cpu', 'ram',
              'disk', 'price', 'prices', 'requirements', 'type', 'is_available',
              'available', 'network', 'bandwidth', 'disk_type', 'cpu_frequency')
    endpoints = (('presets', '/presets/servers'),
                 ('configurators', '/configurator/servers'),
                 ('os', '/os/servers'))
    for label, path in endpoints:
        payload = safe_get(CLOUD + path, token)
        result[label] = payload
        if not isinstance(payload, dict):
            continue
        for key, entries in payload.items():
            if not isinstance(entries, list):
                continue
            selected = []
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                if label == 'presets':
                    cpu, ram = entry.get('cpu'), entry.get('ram')
                    if type(cpu) not in (int, float) or type(ram) not in (int, float):
                        continue
                    if cpu > 2 or ram > 2048:
                        continue
                selected.append(select_fields(entry, fields + ('family', 'version', 'version_codename')))
            result[label] = {key: selected}
            break
    return result


def backup_metadata(token: str, sha: str) -> dict:
    candidates = []
    for ref in ('main', sha):
        tree = safe_get(REPO + '/git/trees/' + ref + '?recursive=1', token)
        entries = tree.get('tree', []) if isinstance(tree, dict) else []
        for entry in entries:
            path = entry.get('path', '')
            lower = path.lower()
            if entry.get('type') == 'blob' and any(term in lower for term in ('backup', '.db', '.sqlite', '.enc', '.age')):
                candidates.append(select_fields(entry, ('path', 'size', 'sha')) | {'ref': ref})
    assets = []
    release_scan_complete = False
    for page in range(1, 6):
        releases = safe_get(REPO + '/releases?per_page=100&page=' + str(page), token)
        if not isinstance(releases, list):
            break
        for release in releases:
            for asset in release.get('assets', []):
                name = asset.get('name', '').lower()
                if any(term in name for term in ('backup', '.db', '.sqlite', '.enc', '.age', '.tar', '.tgz')):
                    assets.append(select_fields(asset, ('id', 'name', 'size', 'created_at')))
        if len(releases) < 100:
            release_scan_complete = True
            break
    return {'source_tree_candidates': candidates, 'release_candidates': assets,
            'release_scan_complete': release_scan_complete,
            'database_restored': False, 'decryption_verified': False}


def main() -> int:
    token = os.environ.get('TIMEWEB_CLOUD_TOKEN', '').strip()
    github = os.environ.get('GH_READ_TOKEN', '').strip()
    sha = os.environ.get('GITHUB_SHA', '')
    if not token or not github or len(sha) != 40:
        raise ProbeError('required_job_inputs_missing')
    for label, data in (
        ('CATALOGUE', catalogue(token)),
        ('RECOVERY', backup_metadata(github, sha)),
        ('CONFIG_PRESENT', {name: bool(os.environ.get(name, '').strip()) for name in
                            ('TELEGRAM_CLIENT_ID', 'TELEGRAM_CLIENT_SECRET', 'FERNET_KEY', 'OWNER_TELEGRAM_SUB')}),
    ):
        print('OWNER_REBUILD_' + label + '=' + json.dumps(data, ensure_ascii=True, allow_nan=False), flush=True)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except ProbeError as error:
        print('OWNER_REBUILD_ERROR=' + str(error), flush=True)
        raise SystemExit(1) from None
