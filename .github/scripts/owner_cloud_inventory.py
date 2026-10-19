"""Bounded GET-only Timeweb inventory. Never emit credentials or mutate resources."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE = 'https://api.timeweb.cloud/api/v1'
MAX_BYTES = 2 * 1024 * 1024
SERVER_FIELDS = ('id', 'name', 'status', 'location', 'cpu', 'ram', 'disk', 'preset_id', 'project_id')
AGENT_FIELDS = ('id', 'name', 'status', 'model_id', 'project_id')
SCALAR_TYPES = (str, int, float, bool)


class InventoryError(RuntimeError):
    """Fixed non-secret diagnostic, never an upstream response body."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise InventoryError('redirect_refused')


def read_api(token: str, path: str) -> dict:
    if not path.startswith(('/servers?', '/cloud-ai/agents')) or '..' in path:
        raise InventoryError('unapproved_inventory_endpoint')
    request = urllib.request.Request(BASE + path, headers={
        'Authorization': 'Bearer ' + token, 'Accept': 'application/json',
    }, method='GET')
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=30) as response:
            raw = response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as error:
        raise InventoryError('timeweb_http_' + str(error.code)) from None
    except OSError:
        raise InventoryError('timeweb_transport_error') from None
    if len(raw) > MAX_BYTES:
        raise InventoryError('inventory_response_too_large')
    try:
        value = json.loads(raw)
    except ValueError:
        raise InventoryError('inventory_invalid_json') from None
    if not isinstance(value, dict):
        raise InventoryError('inventory_invalid_shape')
    return value


def safe_fields(item: dict, fields: tuple[str, ...]) -> dict:
    result = {}
    for field in fields:
        value = item.get(field)
        if value is None or type(value) in SCALAR_TYPES:
            result[field] = value[:160] if isinstance(value, str) else value
    return result


def summarize_server(server: dict) -> dict:
    result = safe_fields(server, SERVER_FIELDS)
    config = server.get('configuration')
    if isinstance(config, dict):
        result['configuration'] = safe_fields(config, ('cpu', 'ram', 'disk'))
    disks = server.get('disks')
    if isinstance(disks, list):
        result['disks'] = [safe_fields(d, ('id', 'size', 'type', 'is_system'))
                           for d in disks if isinstance(d, dict)]
    return result


def inventory(token: str) -> dict:
    servers = []
    seen = set()
    for offset in range(0, 2000, 100):
        page = read_api(token, '/servers?limit=100&offset=' + str(offset))
        items = page.get('servers')
        if not isinstance(items, list) or any(not isinstance(i, dict) for i in items):
            raise InventoryError('invalid_servers_page')
        for item in items:
            identifier = item.get('id')
            if type(identifier) is not int or identifier in seen:
                raise InventoryError('ambiguous_server_inventory')
            seen.add(identifier)
            servers.append(summarize_server(item))
        if len(items) < 100:
            break
    else:
        raise InventoryError('inventory_pagination_limit')
    agents_response = read_api(token, '/cloud-ai/agents')
    agents = agents_response.get('agents')
    if not isinstance(agents, list) or any(not isinstance(a, dict) for a in agents):
        raise InventoryError('invalid_agents_inventory')
    return {
        'kind': 'read_only_owner_inventory',
        'servers': servers,
        'agents': [safe_fields(a, AGENT_FIELDS) for a in agents],
        'scope': 'Only resources visible to this token; not a claim of whole-account visibility.',
        'usage_measured': False,
        'resource_changes': False,
        'apk_or_backend_deployed': False,
    }


def main() -> int:
    token = os.environ.get('TIMEWEB_CLOUD_TOKEN', '').strip()
    if not token:
        raise InventoryError('timeweb_token_missing')
    print('OWNER_CLOUD_INVENTORY=' + json.dumps(inventory(token), ensure_ascii=True,
                                              allow_nan=False, sort_keys=True), flush=True)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except InventoryError as error:
        print('OWNER_CLOUD_INVENTORY_ERROR=' + str(error), file=sys.stderr, flush=True)
        raise SystemExit(1) from None
