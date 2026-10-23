"""Read-only reconstruction preflight; output metadata, never backup contents."""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

CLOUD = 'https://api.timeweb.cloud/api/v1'
REPO = 'https://api.github.com/repos/MishaGameHacking/omni-cio-gateway'
LIMIT = 4 * 1024 * 1024
CATALOGUE_FIELDS = ('id', 'name', 'location', 'availability_zone', 'cpu', 'ram',
                    'disk', 'price', 'prices', 'requirements', 'type', 'is_available',
                    'available', 'network', 'bandwidth', 'disk_type', 'cpu_frequency',
                    'family', 'version', 'version_codename')
RECOVERY_TERMS = ('backup', '.db', '.sqlite', '.enc', '.age')


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
    except OSError:
        raise ProbeError('transport_failed') from None
    if len(raw) > LIMIT:
        raise ProbeError('response_limit')
    try:
        return json.loads(raw)
    except ValueError:
        raise ProbeError('invalid_json') from None


def safe_get(url: str, token: str):
    try:
        return read_json(url, token)
    except ProbeError as error:
        return {'unavailable': str(error)}


def select_fields(item: dict, fields: tuple[str, ...]) -> dict:
    return {key: item[key] for key in fields if key in item}


def _small_preset(entry: dict) -> bool:
    cpu, ram = entry.get('cpu'), entry.get('ram')
    return (type(cpu) in (int, float) and type(ram) in (int, float)
            and 0 < cpu <= 2 and 0 < ram <= 2048)


def _safe_unavailable(code) -> dict:
    known = {'unapproved_api', 'redirect_refused', 'transport_failed', 'response_limit', 'invalid_json'}
    if isinstance(code, str) and (code in known or re.fullmatch(r'http_[1-5]\d{2}', code, re.ASCII)):
        return {'unavailable': code}
    return {'unavailable': 'catalogue_unavailable'}


def _catalogue_section(label: str, payload) -> dict:
    if not isinstance(payload, dict):
        return {'unavailable': 'invalid_catalogue_shape'}
    if set(payload) == {'unavailable'}:
        return _safe_unavailable(payload['unavailable'])
    for key, entries in payload.items():
        if isinstance(entries, list):
            selected = [select_fields(entry, CATALOGUE_FIELDS) for entry in entries
                        if isinstance(entry, dict) and (label != 'presets' or _small_preset(entry))]
            return {key: selected}
    # Never echo an unexpected raw response (which can contain sensitive fields).
    return {'unavailable': 'catalogue_entries_missing'}


def catalogue(token: str) -> dict:
    endpoints = (('presets', '/presets/servers'),
                 ('configurators', '/configurator/servers'),
                 ('os', '/os/servers'))
    return {label: _catalogue_section(label, safe_get(CLOUD + path, token))
            for label, path in endpoints}


def _named_match(entry, field: str, terms: tuple[str, ...]) -> bool:
    if not isinstance(entry, dict):
        return False
    name = entry.get(field)
    return isinstance(name, str) and any(term in name.lower() for term in terms)


def _tree_candidates(tree, ref: str) -> list:
    entries = tree.get('tree', []) if isinstance(tree, dict) else []
    if not isinstance(entries, list):
        return []
    return [select_fields(entry, ('path', 'size', 'sha')) | {'ref': ref} for entry in entries
            if _named_match(entry, 'path', RECOVERY_TERMS) and entry.get('type') == 'blob']


def _release_candidates(releases: list) -> list:
    selected = []
    for release in releases:
        if not isinstance(release, dict) or not isinstance(release.get('assets'), list):
            continue
        selected.extend(select_fields(asset, ('id', 'name', 'size', 'created_at'))
                        for asset in release['assets']
                        if _named_match(asset, 'name', RECOVERY_TERMS + ('.tar', '.tgz')))
    return selected


def backup_metadata(token: str, sha: str) -> dict:
    candidates = []
    for ref in ('main', sha):
        tree = safe_get(REPO + '/git/trees/' + ref + '?recursive=1', token)
        candidates.extend(_tree_candidates(tree, ref))
    assets = []
    release_scan_complete = False
    for page in range(1, 6):
        releases = safe_get(REPO + '/releases?per_page=100&page=' + str(page), token)
        if not isinstance(releases, list):
            break
        assets.extend(_release_candidates(releases))
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
