"""GET-only reconstruction diagnostics with no live API, token or user data."""
from contextlib import contextmanager
import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import patch
import urllib.error

ROOT = Path(__file__).resolve().parents[2]
SENSITIVE = 'not-for-output'


def load_script(name):
    path = ROOT / '.github' / 'scripts' / (name + '.py')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rebuild = load_script('owner_rebuild_inventory')
cloud = load_script('owner_cloud_inventory')


class InventorySafetyTests(unittest.TestCase):
    def test_catalogue_selects_only_small_presets(self):
        rows = [{'id': 1, 'cpu': 1, 'ram': 1024, 'password': SENSITIVE},
                {'id': 2, 'cpu': 8, 'ram': 1024}, {'id': 3, 'cpu': 1, 'ram': 4096},
                {'id': 4, 'cpu': True, 'ram': 1024}, {'id': 5, 'cpu': 0, 'ram': 1024}]
        value = rebuild._catalogue_section('presets', {'server_presets': rows})
        self.assertEqual(value, {'server_presets': [{'id': 1, 'cpu': 1, 'ram': 1024}]})

    def test_unexpected_payload_is_not_echoed(self):
        for value in ([{'token': SENSITIVE}], {'token': SENSITIVE}, {'unavailable': SENSITIVE}, None):
            with self.subTest(kind=type(value).__name__):
                self.assertNotIn(SENSITIVE, str(rebuild._catalogue_section('os', value)))

    def test_fixed_unavailable_codes_remain_diagnostic(self):
        self.assertEqual(rebuild._catalogue_section('os', {'unavailable': 'http_403'}),
                         {'unavailable': 'http_403'})

    def test_malformed_metadata_cannot_claim_restored_data(self):
        with patch.object(rebuild, 'safe_get', side_effect=[{'tree': [None, {'path': 2}]}, {}, []]):
            result = rebuild.backup_metadata('synthetic', 'a' * 40)
        self.assertEqual(result['source_tree_candidates'], [])
        self.assertFalse(result['database_restored'])
        self.assertFalse(result['decryption_verified'])
        self.assertTrue(result['release_scan_complete'])

    def test_recovery_output_never_contains_contents(self):
        tree = {'tree': [{'path': 'backup.sqlite', 'type': 'blob', 'sha': 'b' * 40,
                          'size': 5, 'content': SENSITIVE}]}
        releases = [{'assets': [{'id': 1, 'name': 'old-backup.tgz', 'size': 5, 'content': SENSITIVE}]}]
        with patch.object(rebuild, 'safe_get', side_effect=[tree, tree, releases]):
            result = rebuild.backup_metadata('synthetic', 'a' * 40)
        self.assertEqual(len(result['source_tree_candidates']), 2)
        self.assertEqual(len(result['release_candidates']), 1)
        self.assertNotIn(SENSITIVE, str(result))

    def test_pagination_failure_remains_incomplete(self):
        with patch.object(rebuild, 'safe_get', side_effect=[{}, {}, {'unavailable': 'http_403'}]):
            result = rebuild.backup_metadata('synthetic', 'a' * 40)
        self.assertFalse(result['release_scan_complete'])

    def test_http_transport_errors_do_not_expose_upstream_body(self):
        for module, function, args in (
            (rebuild, rebuild.read_json, (rebuild.CLOUD + '/os/servers', 'synthetic')),
            (cloud, cloud.read_api, ('synthetic', '/cloud-ai/agents')),
        ):
            error = urllib.error.HTTPError('https://unused.invalid', 403, SENSITIVE, {}, None)
            with self.subTest(module=module.__name__), patch.object(module.urllib.request, 'build_opener') as opener:
                opener.return_value.open.side_effect = error
                with self.assertRaises(RuntimeError) as caught:
                    function(*args)
                self.assertNotIn(SENSITIVE, str(caught.exception))

    def test_transport_failures_are_fixed_codes(self):
        for error in (urllib.error.URLError(SENSITIVE), TimeoutError(SENSITIVE), OSError(SENSITIVE)):
            with self.subTest(kind=type(error).__name__), patch.object(rebuild.urllib.request, 'build_opener') as opener:
                opener.return_value.open.side_effect = error
                with self.assertRaisesRegex(rebuild.ProbeError, 'transport_failed'):
                    rebuild.read_json(rebuild.CLOUD + '/os/servers', 'synthetic')

    def test_invalid_utf8_is_rejected_and_requests_are_get_only(self):
        @contextmanager
        def response(request, timeout):
            self.assertEqual(request.get_method(), 'GET')
            yield io.BytesIO(b'\xff\x80')
        for module, function, args in (
            (rebuild, rebuild.read_json, (rebuild.CLOUD + '/os/servers', 'synthetic')),
            (cloud, cloud.read_api, ('synthetic', '/cloud-ai/agents')),
        ):
            with self.subTest(module=module.__name__), patch.object(module.urllib.request, 'build_opener') as opener:
                opener.return_value.open.side_effect = response
                with self.assertRaises(RuntimeError):
                    function(*args)

    def test_redirect_never_sends_token_to_another_host(self):
        handler = rebuild.NoRedirect()
        with self.assertRaisesRegex(rebuild.ProbeError, 'redirect_refused'):
            handler.redirect_request(None, None, 302, '', {}, 'https://other.invalid')


if __name__ == '__main__':
    unittest.main()
