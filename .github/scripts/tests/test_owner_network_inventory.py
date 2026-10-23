"""Safety and completeness checks using synthetic Timeweb responses only."""
from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import urllib.error
import uuid

MODULE = Path(__file__).resolve().parents[1] / 'owner_network_inventory.py'
spec = importlib.util.spec_from_file_location('owner_network_inventory', MODULE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def collection(key, rows, total=None):
    return {key: rows, 'meta': {'total': len(rows) if total is None else total}}


def project(**collections):
    result = {key: [] for key in module.PROJECT_COLLECTIONS}
    result.update(collections)
    result['meta'] = {'total': sum(len(result[key]) for key in module.PROJECT_COLLECTIONS)}
    return result


def floating(number=1, **fields):
    return {'id': str(uuid.UUID(int=number)), 'ip': '198.51.100.' + str(number),
            'resource_type': None, 'resource_id': None, **fields}


def domain(number=1, **fields):
    return {'id': number, 'fqdn': f'private-{number}.example', 'is_technical': False,
            'linked_ip': None, 'subdomains': [], **fields}


def api_response(data):
    response = io.BytesIO(json.dumps(data).encode())
    return response


class OwnerNetworkInventoryTests(unittest.TestCase):
    def inventory(self, resources=None, ips=None, domains=None):
        responses = {module.PROJECT_PATH: resources if resources is not None else project(),
                     '/floating-ips': collection('ips', ips or []),
                     module.DOMAIN_PATHS[0]: collection('domains', domains or [])}
        with patch.object(module, 'read_api', side_effect=lambda token, path: responses[path]):
            return module.inventory('synthetic-token')

    def test_unattached_ipv4_is_visible_even_when_project_has_no_servers(self):
        report = self.inventory(ips=[floating(), floating(2, ip='2001:db8::2'),
                                     floating(3, ip=None)])
        self.assertEqual(report['unattached_ipv4_count'], 1)
        self.assertEqual(report['unknown_ip_version_count'], 1)
        self.assertEqual([ip['assignment'] for ip in report['floating_ips']], ['unattached'] * 3)
        self.assertFalse(report['billing_verified'])
        self.assertFalse(report['resource_changes'])

    def test_complete_empty_inventory_requires_explicit_arrays_and_zero_totals(self):
        report = self.inventory()
        self.assertTrue(report['complete_within_token_visibility'])
        self.assertEqual(report['floating_ips'], [])
        self.assertEqual(report['domains']['domains_total'], 0)

    def test_only_proven_project_binding_discloses_name_and_allowlisted_metadata(self):
        resources = project(servers=[{'id': 42, 'networks': [],
                                      'root_pass': 'root-password', 'ssh_keys': 'private-ssh-key'}])
        ips = [floating(resource_type='server', resource_id=42, comment='private-comment'),
               floating(2, resource_type='server', resource_id=100), floating(3)]
        domains = [domain(linked_ip='198.51.100.1', fqdn='analyst.example',
                          is_technical=True, person_id='private-person'),
                   domain(2, linked_ip='198.51.100.2'),
                   domain(3, linked_ip='198.51.100.3'), domain(4)]
        report = self.inventory(resources, ips, domains)
        encoded = json.dumps(report)
        for private in ('root-password', 'private-ssh-key', 'private-comment',
                        'private-person', 'private-2.example', 'private-3.example',
                        'private-4.example', '198.51.100.', 'synthetic-token'):
            self.assertNotIn(private, encoded)
        names = report['domains']['project_linked_names']
        self.assertEqual(names, [{'id': 1, 'type': 'domain', 'fqdn': 'analyst.example',
                                 'is_technical': True, 'project_id': module.PROJECT_ID,
                                 'resource_type': 'server', 'resource_id': 42,
                                 'https_verified': False}])
        self.assertEqual(report['domains']['outside_or_unknown_project_names_count'], 1)
        self.assertEqual(report['domains']['linked_to_unattached_ip_count'], 1)
        self.assertEqual(report['domains']['unlinked_names_count'], 1)
        self.assertFalse(report['https_verified'])
        self.assertFalse(report['domain_ownership_verified'])

    def test_public_vm_network_and_subdomain_can_prove_binding(self):
        resources = project(servers=[{'id': 42, 'networks': [
            {'type': 'private', 'ips': [{'ip': '10.0.0.1'}]},
            {'type': 'public', 'ips': [{'ip': '203.0.113.10', 'ptr': 'private-ptr'}]},
        ]}])
        domains = [domain(subdomains=[{'id': 5, 'fqdn': 'api.analyst.example',
                                      'linked_ip': '203.0.113.10'}]),
                   domain(2, linked_ip='10.0.0.1')]
        report = self.inventory(resources, domains=domains)['domains']
        self.assertEqual(report['subdomains_total'], 1)
        self.assertEqual(report['project_linked_names'][0]['type'], 'subdomain')
        self.assertEqual(report['project_linked_names'][0]['fqdn'], 'api.analyst.example')
        self.assertEqual(report['outside_or_unknown_project_names_count'], 1)

    def test_public_network_missing_and_duplicate_address_guards_remain_strict(self):
        cases = [
            ([{'id': 42}], 'invalid_inventory_collection'),
            ([{'id': 42, 'networks': [{'type': 'public'}]}], 'invalid_inventory_collection'),
            ([{'id': 42, 'networks': [{'type': 'public', 'ips': [{}]}]}], 'missing_ip_address'),
            ([{'id': 42, 'networks': [{'type': 'public', 'ips': [{'ip': None}]}]}],
             'missing_public_server_ip'),
            ([{'id': 42, 'networks': [{'type': 'public', 'ips': [{'ip': '2001:db8::1'}]}]},
              {'id': 43, 'networks': [{'type': 'public', 'ips': [{'ip': '2001:0db8::1'}]}]}],
             'duplicate_project_public_ip'),
        ]
        for servers, error in cases:
            resources = project(servers=servers)
            with self.subTest(error=error), self.assertRaisesRegex(module.InventoryError, '^' + error + '$'):
                self.inventory(resources)

    def test_missing_or_half_null_assignment_is_not_unattached(self):
        variants = [dict(resource_type=None), dict(resource_id=None),
                    dict(resource_type=None, resource_id=42),
                    dict(resource_type='server', resource_id=None),
                    dict(resource_type=[], resource_id=42),
                    dict(resource_type='secret-value', resource_id=42)]
        for assignment in variants:
            row = floating()
            del row['resource_id'], row['resource_type']
            row.update(assignment)
            with self.subTest(assignment=assignment), self.assertRaises(module.InventoryError):
                self.inventory(ips=[row])

    def test_project_membership_is_typed_and_other_projects_are_not_claimed(self):
        resources = project(balancers=[{'id': 42}])
        report = self.inventory(resources, ips=[floating(resource_type='server', resource_id=42),
                                                floating(2, resource_type='balancer', resource_id=42)])
        self.assertIsNone(report['floating_ips'][0]['project_id'])
        self.assertEqual(report['floating_ips'][1]['project_id'], module.PROJECT_ID)

    def test_two_complete_domain_pages_are_collected(self):
        pages = [collection('domains', [domain(i) for i in range(1, 101)], 101),
                 collection('domains', [domain(101)], 101)]
        with patch.object(module, 'read_api', side_effect=pages) as read:
            self.assertEqual(len(module.all_domains('token')), 101)
        self.assertEqual([call.args[1] for call in read.call_args_list], list(module.DOMAIN_PATHS[:2]))

    def test_exact_page_multiple_uses_verified_total_without_unbounded_extra_request(self):
        with patch.object(module, 'read_api', return_value=collection(
                'domains', [domain(i) for i in range(1, 101)])) as read:
            self.assertEqual(len(module.all_domains('token')), 100)
            self.assertEqual(read.call_count, 1)

    def test_partial_duplicate_and_changed_total_pages_fail(self):
        first = collection('domains', [domain(i) for i in range(1, 101)], 101)
        endings = [collection('domains', [], 101), collection('domains', [domain(1)], 101),
                   collection('domains', [domain(101)], 102)]
        for ending in endings:
            with self.subTest(ending=ending['meta']), patch.object(
                    module, 'read_api', side_effect=[first, ending]), self.assertRaises(module.InventoryError):
                module.all_domains('token')

    def test_domain_total_and_collection_are_mandatory(self):
        for response in ({'domains': []}, {'meta': {'total': 0}},
                         collection('domains', [], 1), collection('domains', [None], 1),
                         collection('domains', [], True), collection('domains', [], -1),
                         collection('domains', [], module.MAX_ENTRIES + 1)):
            with self.subTest(response=response), patch.object(
                    module, 'read_api', return_value=response), self.assertRaises(module.InventoryError):
                module.all_domains('token')

    def test_missing_arrays_and_incomplete_nonpaginated_responses_fail(self):
        cases = [(module.PROJECT_PATH, {'meta': {'total': 0}}),
                 (module.PROJECT_PATH, project() | {'meta': {'total': 1}}),
                 ('/floating-ips', {'meta': {'total': 0}}),
                 ('/floating-ips', collection('ips', [], 1))]
        for path, invalid in cases:
            payloads = {module.PROJECT_PATH: project(), '/floating-ips': collection('ips', []),
                        module.DOMAIN_PATHS[0]: collection('domains', [])}
            payloads[path] = invalid
            with self.subTest(path=path, invalid=invalid), patch.object(
                    module, 'read_api', side_effect=lambda token, endpoint: payloads[endpoint]), \
                    self.assertRaises(module.InventoryError):
                module.inventory('token')

    def test_duplicate_ip_ids_addresses_and_project_ids_fail(self):
        cases = [dict(ips=[floating(), floating()]),
                 dict(ips=[floating(), floating(2, ip='198.51.100.1')]),
                 dict(resources=project(servers=[{'id': 42, 'networks': []}] * 2))]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(module.InventoryError):
                self.inventory(**case)

    def test_conflicting_live_assignment_does_not_disclose_name(self):
        resources = project(servers=[{'id': 42, 'networks': [
            {'type': 'public', 'ips': [{'ip': '198.51.100.1'}]}]}])
        ips = [floating()]
        domains = [domain(linked_ip='198.51.100.1')]
        with self.assertRaisesRegex(module.InventoryError, '^conflicting_ip_assignment$'):
            self.inventory(resources, ips=ips, domains=domains)

    def test_project_floating_binding_must_match_public_resource_type_and_id(self):
        resources = project(servers=[{'id': 42, 'networks': [
            {'type': 'public', 'ips': [{'ip': '198.51.100.1'}]}]},
            {'id': 43, 'networks': []}], balancers=[{'id': 42}])
        domains = [domain(linked_ip='198.51.100.1', fqdn='analyst.example')]
        matching_ips = [floating(resource_type='server', resource_id=42)]
        report = self.inventory(resources, ips=matching_ips, domains=domains)
        self.assertEqual(report['domains']['project_linked_names'][0]['fqdn'], 'analyst.example')
        for kind, identifier in [('server', 43), ('balancer', 42)]:
            ips = [floating(resource_type=kind, resource_id=identifier)]
            with self.subTest(kind=kind), self.assertRaisesRegex(
                    module.InventoryError, '^conflicting_ip_assignment$'):
                self.inventory(resources, ips=ips, domains=domains)

    def test_domain_type_and_subdomain_identifier_validation_are_preserved(self):
        cases = [([domain(is_technical=0)], 'invalid_domain_type'),
                 ([domain(is_technical='true')], 'invalid_domain_type'),
                 ([domain(subdomains=[{'id': True, 'linked_ip': None}])], 'invalid_resource_id')]
        for domains, error in cases:
            with self.subTest(error=error), self.assertRaisesRegex(module.InventoryError, '^' + error + '$'):
                self.inventory(domains=domains)

    def test_missing_subdomain_array_is_not_an_empty_list(self):
        row = domain()
        del row['subdomains']
        with self.assertRaises(module.InventoryError):
            self.inventory(domains=[row])

    def test_nested_subdomains_are_bounded_and_duplicates_fail(self):
        sub = {'id': 9, 'fqdn': 'secret.example', 'linked_ip': None}
        for rows in ([domain(subdomains=[sub, sub])],
                     [domain(subdomains=[dict(sub, id=i + 1) for i in range(module.MAX_ENTRIES)])]):
            with self.subTest(count=len(rows[0]['subdomains'])), self.assertRaises(module.InventoryError):
                self.inventory(domains=rows)

    def test_ip_and_id_types_are_strict_and_never_echo_input(self):
        for field, value in [('id', 'private-secret'), ('ip', 'private-secret'),
                             ('ip', 'fe80::1%private-secret'), ('resource_id', True)]:
            row = floating(resource_type='server', resource_id=42)
            row[field] = value
            with self.subTest(field=field), self.assertRaises(module.InventoryError) as caught:
                self.inventory(ips=[row])
            self.assertNotIn(str(value), str(caught.exception))

    def test_fqdn_rejects_log_injection_and_canonicalizes_idn(self):
        self.assertEqual(module.safe_fqdn('Пример.РФ'), 'xn--e1afmkfd.xn--p1ai')
        for value in ('https://secret.example', 'valid.example\nsecret', 'a..example', '-bad.example'):
            with self.subTest(value=value), self.assertRaises(module.InventoryError):
                module.safe_fqdn(value)


class InventoryTransportTests(unittest.TestCase):
    def test_get_uses_fixed_origin_and_has_no_request_body(self):
        with patch.object(module.urllib.request, 'build_opener') as factory:
            factory.return_value.open.return_value = api_response({'meta': {'total': 0}, 'ips': []})
            self.assertEqual(module.read_api('synthetic-token', '/floating-ips')['ips'], [])
            request = factory.return_value.open.call_args.args[0]
            self.assertEqual(request.full_url, module.BASE + '/floating-ips')
            self.assertEqual(request.method, 'GET')
            self.assertIsNone(request.data)
            self.assertEqual(factory.call_args.args, (module.NoRedirect,))
            self.assertEqual(factory.return_value.open.call_args.kwargs['timeout'], 30)

    def test_endpoint_allowlist_rejects_suffix_query_traversal_and_other_project(self):
        paths = ('/floating-ips/uuid', '/floating-ips?limit=100', '/domains',
                 module.DOMAIN_PATHS[0] + '&token=secret', '/projects/1/resources',
                 '/servers?limit=100', '//evil.example/', '/floating-ips/../servers',
                 module.DOMAIN_PATHS[0] + '#fragment')
        with patch.object(module.urllib.request, 'build_opener') as factory:
            for path in paths:
                with self.subTest(path=path), self.assertRaisesRegex(
                        module.InventoryError, '^unapproved_inventory_endpoint$'):
                    module.read_api('token', path)
            factory.assert_not_called()

    def test_redirect_never_follows_or_echoes_destination(self):
        handler = module.NoRedirect()
        with self.assertRaisesRegex(module.InventoryError, '^redirect_refused$'):
            handler.redirect_request(None, None, 302, 'secret', {}, 'https://evil.example/token')

    def test_response_size_json_and_top_level_shape_are_bounded(self):
        for raw, error in [(b' ' * (module.MAX_BYTES + 1), 'response_size_limit'),
                           (b'private-secret', 'invalid_json'), (b'[]', 'invalid_response_shape')]:
            with self.subTest(error=error), patch.object(module.urllib.request, 'build_opener') as factory:
                factory.return_value.open.return_value = io.BytesIO(raw)
                with self.assertRaisesRegex(module.InventoryError, '^' + error + '$'):
                    module.read_api('token', '/floating-ips')

    def test_http_and_transport_failures_have_fixed_nonsensitive_codes(self):
        failures = [(urllib.error.HTTPError('secret-url', 403, 'private-secret', {}, None),
                     'timeweb_http_403'), (OSError('private-secret'), 'timeweb_transport_error')]
        for error, code in failures:
            with self.subTest(code=code), patch.object(module.urllib.request, 'build_opener') as factory:
                factory.return_value.open.side_effect = error
                with self.assertRaisesRegex(module.InventoryError, '^' + code + '$'):
                    module.read_api('token', '/floating-ips')

    def test_main_never_prints_partial_success_when_later_read_fails(self):
        with patch.dict(module.os.environ, {'TIMEWEB_CLOUD_TOKEN': 'synthetic-token'}), \
                patch.object(module, 'read_api', side_effect=[project(),
                             collection('ips', [floating()]), module.InventoryError('timeweb_http_403')]), \
                patch('sys.stdout', new_callable=io.StringIO) as output, \
                self.assertRaises(module.InventoryError):
            module.main()
        self.assertEqual(output.getvalue(), '')

    def test_missing_token_does_not_call_api(self):
        with patch.dict(module.os.environ, {'TIMEWEB_CLOUD_TOKEN': ''}), \
                patch.object(module, 'read_api') as read, self.assertRaisesRegex(
                    module.InventoryError, '^timeweb_token_missing$'):
            module.main()
        read.assert_not_called()


if __name__ == '__main__':
    unittest.main()
