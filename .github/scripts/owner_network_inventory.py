"""Bounded GET-only network metadata for the explicitly selected Timeweb project.

API contracts checked against the official Timeweb SDKs on 2026-10-22:
https://github.com/timeweb-cloud/sdk-python/blob/main/docs/FloatingIPApi.md
https://github.com/timeweb-cloud/sdk-python/blob/main/docs/DomainsApi.md
https://github.com/timeweb-cloud/sdk-python/blob/main/docs/ProjectsApi.md
https://github.com/timeweb-cloud/sdk-go/blob/main/model_floating_ip.go
https://github.com/timeweb-cloud/sdk-go/blob/main/model_domain.go

Floating IPs and project resources have no documented pagination parameters.
Domains use limit/offset and meta.total. Domain has no project_id: only a
verified linked_ip association permits a name to appear in this report.
"""
from __future__ import annotations

from datetime import datetime, timezone
import ipaddress
import json
import os
import re
import sys
import urllib.error
import urllib.request
import uuid

BASE = 'https://api.timeweb.cloud/api/v1'
PROJECT_ID = 2941515
MAX_BYTES = 2 * 1024 * 1024
MAX_ENTRIES = 2000
PAGE_SIZE = 100
PROJECT_PATH = f'/projects/{PROJECT_ID}/resources'
DOMAIN_PATHS = tuple(
    f'/domains?limit={PAGE_SIZE}&offset={offset}&order=asc&sort=idn_name'
    for offset in range(0, MAX_ENTRIES, PAGE_SIZE)
)
ALLOWED_PATHS = frozenset(('/floating-ips', PROJECT_PATH, *DOMAIN_PATHS))
PROJECT_COLLECTIONS = ('servers', 'balancers', 'buckets', 'clusters',
                       'databases', 'dedicated_servers')
RESOURCE_COLLECTIONS = {'server': 'servers', 'balancer': 'balancers',
                        'dbaas': 'databases'}
RESOURCE_TYPES = frozenset((*RESOURCE_COLLECTIONS, 'network'))


class InventoryError(RuntimeError):
    """Only fixed, nonsensitive error codes may leave the inventory."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise InventoryError('redirect_refused')


def read_api(token: str, path: str) -> dict:
    if path not in ALLOWED_PATHS:
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
        raise InventoryError('response_size_limit')
    try:
        value = json.loads(raw)
    except ValueError:
        raise InventoryError('invalid_json') from None
    if not isinstance(value, dict):
        raise InventoryError('invalid_response_shape')
    return value


def total_count(payload: dict) -> int:
    meta = payload.get('meta')
    total = meta.get('total') if isinstance(meta, dict) else None
    if type(total) is not int or total < 0:
        raise InventoryError('invalid_inventory_total')
    if total > MAX_ENTRIES:
        raise InventoryError('inventory_entry_limit')
    return total


def entries(payload: dict, key: str) -> list[dict]:
    rows = payload.get(key)
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise InventoryError('invalid_inventory_collection')
    if len(rows) > MAX_ENTRIES:
        raise InventoryError('inventory_entry_limit')
    return rows


def resource_id(value) -> int:
    if type(value) is not int or not 0 < value < 2**53:
        raise InventoryError('invalid_resource_id')
    return value


def floating_id(value) -> str:
    if not isinstance(value, str) or len(value) != 36:
        raise InventoryError('invalid_floating_ip_id')
    try:
        result = str(uuid.UUID(value))
    except ValueError:
        raise InventoryError('invalid_floating_ip_id') from None
    if result != value.lower():
        raise InventoryError('invalid_floating_ip_id')
    return result


def nullable_address(row: dict, field: str):
    if field not in row:
        raise InventoryError('missing_ip_address')
    value = row[field]
    if value is None:
        return None
    if not isinstance(value, str) or '%' in value:
        raise InventoryError('invalid_ip_address')
    try:
        return ipaddress.ip_address(value)
    except ValueError:
        raise InventoryError('invalid_ip_address') from None


def project_resources(token: str) -> tuple[dict, dict]:
    payload = read_api(token, PROJECT_PATH)
    collections = {key: entries(payload, key) for key in PROJECT_COLLECTIONS}
    if sum(map(len, collections.values())) != total_count(payload):
        raise InventoryError('incomplete_project_resources')
    ids = {}
    for kind, key in RESOURCE_COLLECTIONS.items():
        values = [resource_id(row.get('id')) for row in collections[key]]
        if len(set(values)) != len(values):
            raise InventoryError('duplicate_project_resource')
        ids[kind] = set(values)
    public_addresses = {}
    for server in collections['servers']:
        for network in entries(server, 'networks'):
            if network.get('type') != 'public':
                continue
            for address in entries(network, 'ips'):
                ip = nullable_address(address, 'ip')
                if ip is None:
                    raise InventoryError('missing_public_server_ip')
                if str(ip) in public_addresses:
                    raise InventoryError('duplicate_project_public_ip')
                public_addresses[str(ip)] = {'resource_type': 'server',
                                             'resource_id': server['id']}
    return ids, public_addresses


def floating_ips(token: str, project_ids: dict) -> tuple[list[dict], dict]:
    payload = read_api(token, '/floating-ips')
    rows = entries(payload, 'ips')
    if len(rows) != total_count(payload):
        raise InventoryError('incomplete_floating_ips')
    result, address_index, seen = [], {}, set()
    for row in rows:
        identifier = floating_id(row.get('id'))
        if identifier in seen:
            raise InventoryError('duplicate_floating_ip')
        seen.add(identifier)
        ip = nullable_address(row, 'ip')
        if 'resource_type' not in row or 'resource_id' not in row:
            raise InventoryError('missing_ip_assignment')
        kind, assigned_id = row['resource_type'], row['resource_id']
        if kind is None and assigned_id is None:
            assignment = 'unattached'
        elif isinstance(kind, str) and kind in RESOURCE_TYPES and assigned_id is not None:
            assigned_id = resource_id(assigned_id)
            assignment = ('attached_to_project' if assigned_id in project_ids.get(kind, set())
                          else 'attached_outside_or_unknown_project')
        else:
            raise InventoryError('invalid_ip_assignment')
        summary = {'id': identifier, 'type': 'floating',
                   'ip_version': ip.version if ip is not None else None,
                   'assignment': assignment, 'resource_type': kind,
                   'resource_id': assigned_id,
                   'project_id': PROJECT_ID if assignment == 'attached_to_project' else None}
        result.append(summary)
        if ip is not None:
            if str(ip) in address_index:
                raise InventoryError('duplicate_floating_ip_address')
            address_index[str(ip)] = summary
    return result, address_index


def all_domains(token: str) -> list[dict]:
    result, seen, expected = [], set(), None
    for path in DOMAIN_PATHS:
        payload = read_api(token, path)
        total = total_count(payload)
        if expected is not None and total != expected:
            raise InventoryError('domain_total_changed')
        expected = total
        page = entries(payload, 'domains')
        if len(page) != min(PAGE_SIZE, expected - len(result)):
            raise InventoryError('incomplete_domain_page')
        for row in page:
            identifier = resource_id(row.get('id'))
            if identifier in seen:
                raise InventoryError('duplicate_domain')
            seen.add(identifier)
            result.append(row)
        if len(result) == expected:
            return result
    raise InventoryError('domain_pagination_limit')


def safe_fqdn(value) -> str:
    if not isinstance(value, str) or not 1 < len(value) <= 253:
        raise InventoryError('invalid_project_fqdn')
    try:
        ascii_name = value.rstrip('.').encode('idna').decode('ascii').lower()
    except UnicodeError:
        raise InventoryError('invalid_project_fqdn') from None
    labels = ascii_name.split('.')
    if len(ascii_name) > 253 or len(labels) < 2 or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label)
                              for label in labels):
        raise InventoryError('invalid_project_fqdn')
    return ascii_name


def domain_summary(rows: list[dict], ip_index: dict, public_addresses: dict) -> dict:
    report = {'domains_total': len(rows), 'subdomains_total': 0,
              'unlinked_names_count': 0, 'linked_to_unattached_ip_count': 0,
              'outside_or_unknown_project_names_count': 0,
              'project_linked_names': [], 'https_verified': False}
    seen_subdomains = set()
    for domain in rows:
        if type(domain.get('is_technical')) is not bool:
            raise InventoryError('invalid_domain_type')
        subdomains = entries(domain, 'subdomains')
        report['subdomains_total'] += len(subdomains)
        if report['subdomains_total'] + len(rows) > MAX_ENTRIES:
            raise InventoryError('inventory_entry_limit')
        names = [('domain', domain), *(('subdomain', sub) for sub in subdomains)]
        for kind, name in names:
            identifier = resource_id(name.get('id'))
            if kind == 'subdomain':
                if identifier in seen_subdomains:
                    raise InventoryError('duplicate_subdomain')
                seen_subdomains.add(identifier)
            ip = nullable_address(name, 'linked_ip')
            if ip is None:
                report['unlinked_names_count'] += 1
                continue
            floating = ip_index.get(str(ip), {})
            binding = public_addresses.get(str(ip))
            if binding and floating and (floating.get('project_id') != PROJECT_ID or
                                         floating['resource_type'] != binding['resource_type'] or
                                         floating['resource_id'] != binding['resource_id']):
                raise InventoryError('conflicting_ip_assignment')
            if floating.get('project_id') == PROJECT_ID:
                binding = floating
            if binding:
                report['project_linked_names'].append({
                    'id': identifier, 'type': kind, 'fqdn': safe_fqdn(name.get('fqdn')),
                    'is_technical': domain['is_technical'], 'project_id': PROJECT_ID,
                    'resource_type': binding['resource_type'],
                    'resource_id': binding['resource_id'], 'https_verified': False,
                })
            elif floating.get('assignment') == 'unattached':
                report['linked_to_unattached_ip_count'] += 1
            else:
                report['outside_or_unknown_project_names_count'] += 1
    return report


def inventory(token: str) -> dict:
    project_ids, public_addresses = project_resources(token)
    ips, ip_index = floating_ips(token, project_ids)
    domains = domain_summary(all_domains(token), ip_index, public_addresses)
    return {
        'kind': 'read_only_owner_network_inventory', 'project_id': PROJECT_ID,
        'observed_at_utc': datetime.now(timezone.utc).isoformat(),
        'complete_within_token_visibility': True, 'floating_ips': ips,
        'unattached_ipv4_count': sum(ip['assignment'] == 'unattached' and ip['ip_version'] == 4
                                    for ip in ips),
        'unknown_ip_version_count': sum(ip['ip_version'] is None for ip in ips),
        'domains': domains, 'billing_verified': False, 'resource_changes': False,
        'scope': 'Only resources visible to this token; not whole-account visibility.',
        'domain_project_basis': 'linked_ip matches a floating IP attached to a project resource '
                                'or a public IP of a project VM; other associations are unknown.',
        'domain_ownership_verified': False, 'dns_verified': False, 'https_verified': False,
    }


def main() -> int:
    token = os.environ.get('TIMEWEB_CLOUD_TOKEN', '').strip()
    if not token:
        raise InventoryError('timeweb_token_missing')
    report = inventory(token)
    print('OWNER_NETWORK_INVENTORY=' + json.dumps(report, ensure_ascii=True,
                                                 allow_nan=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except InventoryError as error:
        print('OWNER_NETWORK_INVENTORY_ERROR=' + str(error), file=sys.stderr)
        raise SystemExit(1) from None
