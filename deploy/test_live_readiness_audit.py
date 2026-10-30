"""Synthetic safety and protocol checks; never access a live account."""
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
import urllib.error

SPEC = importlib.util.spec_from_file_location('audit', Path(__file__).with_name('live_readiness_audit.py'))
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


class Reply:
    status = 200
    def __init__(self, raw):
        self.raw = raw
    def __enter__(self):
        return self
    def __exit__(self, *_):
        pass
    def read(self, size):
        return self.raw[:size]


class Broker:
    def __init__(self, access='ACCOUNT_ACCESS_LEVEL_FULL_ACCESS'):
        self.calls = []
        self.access = access
    def read(self, method, body):
        self.calls.append((method, body))
        if method == 'accounts':
            return {'accounts': [{'id': 'PRIVATE_ACCOUNT', 'name': 'PRIVATE_NAME',
                'status': 'ACCOUNT_STATUS_OPEN', 'accessLevel': self.access}]}
        if method == 'portfolio':
            return {'accountId': 'PRIVATE_ACCOUNT', 'positions': [],
                    'totalAmountPortfolio': {'units': '12345', 'nano': 0, 'currency': 'rub'}}
        return {'orders': []} if method == 'orders' else {'money': []}


def catalog_row(**changes):
    return {'id': 123, 'model_name': 'openai/gpt-6-luna', 'is_stopped': False,
        'is_deprecated': False, 'parameter_values': {'cost_in': '0.00001', 'cost_out': '0.00002',
        'context_window': 1000000, 'max_output_tokens': 128000}, 'price_tiers': [], **changes}


def catalog(rows):
    return {'models': rows, 'meta': {'total': len(rows)}}


class AuditTests(unittest.TestCase):
    def test_profile_presence_never_substitutes_for_confirmation(self):
        result = audit.profile_checks({'mandate': {'loss_capacity_percent': '20'},
            'construction': {'loss_capacity_confirmed': 1, 'income_stability': 'PRIVATE_TEXT'}})
        self.assertEqual(result, {'loss_capacity_confirmed': False, 'income_stability_known': False,
            'loss_capacity_valid': True, 'loss_capacity_state': 'positive'})
        self.assertNotIn('20', json.dumps(result))
        self.assertNotIn('PRIVATE_TEXT', json.dumps(result))

    def test_profile_handles_missing_and_invalid_values_without_disclosure(self):
        for raw in (True, 'NaN', '-1', '101', None, {}, [], 'PRIVATE_VALUE'):
            with self.subTest(raw=raw):
                result = audit.profile_checks({'mandate': {'loss_capacity_percent': raw}})
                self.assertFalse(result['loss_capacity_valid'])
        self.assertFalse(audit.profile_checks({})['loss_capacity_confirmed'])

    def test_zero_and_positive_capacity_are_distinct(self):
        for value, state in [('0', 'zero'), ('100', 'positive')]:
            result = audit.profile_checks({'mandate': {'loss_capacity_percent': value},
                'construction': {'loss_capacity_confirmed': True, 'income_stability': 'variable'}})
            self.assertTrue(result['loss_capacity_confirmed'])
            self.assertTrue(result['income_stability_known'])
            self.assertEqual(result['loss_capacity_state'], state)

    def test_gateway_access_uses_only_a_metadata_get_and_exact_identifiers(self):
        opener = Mock()
        opener.open.return_value = Reply(json.dumps({'data': [
            {'id': 'openai/gpt-6-luna'}, {'id': 'gpt-6-astra'}, {'id': 'PRIVATE_OTHER_MODEL'}]}).encode())
        with patch.object(audit.urllib.request, 'build_opener', return_value=opener):
            result = audit.gateway_model_access({'TIMEWEB_AI_TOKEN': 'PRIVATE_KEY'})
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, 'https://api.timeweb.ai/v1/models')
        self.assertEqual(request.get_method(), 'GET')
        self.assertIsNone(request.data)
        self.assertTrue(result['available']['gpt-6-luna'])
        self.assertFalse(result['available']['gpt-6-astra'])
        self.assertFalse(result['inference_verified'])
        self.assertNotIn('PRIVATE', json.dumps(result))

    def test_gateway_does_not_infer_access_from_cloud_admin_token(self):
        with patch.object(audit.urllib.request, 'build_opener') as opener:
            with self.assertRaisesRegex(audit.AuditError, 'gateway_key_unavailable'):
                audit.gateway_model_access({'TIMEWEB_CLOUD_TOKEN': 'PRIVATE_CLOUD'})
            opener.assert_not_called()

    def test_read_protocol_and_private_data_projection(self):
        broker = Broker()
        report, private = audit.inspect_broker(broker)
        self.assertEqual([x[0] for x in broker.calls], ['accounts', 'portfolio', 'positions', 'orders'])
        self.assertEqual(report['orders_sent'], 0)
        self.assertEqual(report['full_access_accounts'], 1)
        self.assertFalse(report['execution_eligibility_verified'])
        self.assertIn('PRIVATE_NAME', json.dumps(private))
        for secret in ('PRIVATE_NAME', 'PRIVATE_ACCOUNT', '12345', 'totalAmountPortfolio'):
            self.assertNotIn(secret, json.dumps(report))

    def test_readonly_account_is_not_misreported_as_full_access(self):
        report, _ = audit.inspect_broker(Broker('ACCOUNT_ACCESS_LEVEL_READ_ONLY'))
        self.assertEqual(report['full_access_accounts'], 0)

    def test_unknown_access_blocks(self):
        with self.assertRaisesRegex(audit.AuditError, 'account_access_unverified'):
            audit.inspect_broker(Broker('PRIVATE_PROVIDER_TEXT'))

    def test_empty_accounts_are_not_invented(self):
        reader = Mock()
        reader.read.return_value = {'accounts': []}
        with self.assertRaisesRegex(audit.AuditError, 'account_collection_invalid'):
            audit.inspect_broker(reader)

    def test_duplicate_account_blocks_before_second_read(self):
        broker = Broker()
        source = broker.read
        def read(method, body):
            result = source(method, body)
            if method == 'accounts':
                result['accounts'] *= 2
            return result
        broker.read = read
        with self.assertRaisesRegex(audit.AuditError, 'account_identity_invalid'):
            audit.inspect_broker(broker)

    def test_mismatched_response_account_blocks(self):
        reader = Mock()
        reader.read.side_effect = [Broker().read('accounts', {}), {'accountId': 'ANOTHER_PRIVATE_ACCOUNT'}]
        with self.assertRaisesRegex(audit.AuditError, 'broker_response_account_mismatch'):
            audit.inspect_broker(reader)

    def test_write_methods_are_impossible(self):
        opener = Mock()
        reader = audit.BrokerReader('PRIVATE_TOKEN', None, opener=opener)
        for method in ('PostOrder', 'cancel', 'OrdersService/PostOrder', 'stop', 'withdraw', 'payin'):
            with self.subTest(method=method), self.assertRaises(audit.AuditError):
                reader.read(method, {'accountId': 'test'})
        opener.open.assert_not_called()

    def test_request_body_cannot_inject_order_fields(self):
        opener = Mock()
        reader = audit.BrokerReader('PRIVATE_TOKEN', None, opener=opener)
        with self.assertRaises(audit.AuditError):
            reader.read('orders', {'accountId': 'test', 'quantity': 10})
        opener.open.assert_not_called()

    def test_request_uses_exact_production_url_and_no_secret_in_url(self):
        opener = Mock()
        opener.open.return_value = Reply(b'{"orders":[]}')
        reader = audit.BrokerReader('PRIVATE_TOKEN', None, opener=opener)
        reader.read('orders', {'accountId': 'PRIVATE_ACCOUNT'})
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, audit.BROKER + 'OrdersService/GetOrders')
        self.assertNotIn('PRIVATE_', request.full_url)
        self.assertEqual(request.get_method(), 'POST')
        self.assertLessEqual(opener.open.call_args.kwargs['timeout'], 8)

    def test_expired_deadline_makes_no_network_call(self):
        opener = Mock()
        reader = audit.BrokerReader('x', None, opener=opener)
        reader.deadline = -1
        with self.assertRaisesRegex(audit.AuditError, 'broker_deadline_exceeded'):
            reader.read('accounts', {'status': 'ACCOUNT_STATUS_OPEN'})
        opener.open.assert_not_called()

    def test_no_redirect(self):
        self.assertIsNone(audit.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.test'))

    def test_http_error_does_not_expose_body_url_or_token(self):
        opener = Mock()
        opener.open.side_effect = urllib.error.HTTPError('PRIVATE_URL', 403, 'PRIVATE_TOKEN', {}, io.BytesIO(b'PRIVATE_BODY'))
        with self.assertRaises(audit.AuditError) as caught:
            audit.request_json(opener, Mock(), 1)
        self.assertEqual(str(caught.exception), 'permission_denied')

    def test_oversized_response_rejected(self):
        opener = Mock()
        opener.open.return_value = Reply(b' ' * (4 * 1024 * 1024 + 1))
        with self.assertRaisesRegex(audit.AuditError, 'response_size_exceeded'):
            audit.request_json(opener, Mock(), 1)

    def test_configuration_is_parsed_without_evaluating_shell(self):
        result = audit.config_values("FERNET_KEY='literal$(PRIVATE_COMMAND)'\nUNRELATED=PRIVATE_OTHER\nAI_MODEL_FAST=openai/gpt-6-luna")
        self.assertEqual(result['FERNET_KEY'], 'literal$(PRIVATE_COMMAND)')
        self.assertNotIn('UNRELATED', result)

    def test_duplicate_configuration_rejected(self):
        with self.assertRaisesRegex(audit.AuditError, 'runtime_configuration_invalid'):
            audit.config_values('FERNET_KEY=x\nFERNET_KEY=y')

    def test_unapproved_database_rejected(self):
        with self.assertRaises(audit.AuditError):
            audit.config_values('FERNET_KEY=x\nDATABASE_PATH=/tmp/other.db')

    def test_private_file_is_exclusive_and_owner_only(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(audit, 'PRIVATE', Path(directory).resolve()):
            audit.save_private('41000000000', {'private': 'PRIVATE_DATA'})
            target = Path(directory) / 'live-readiness-audit-41000000000.json'
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                audit.save_private('41000000000', {'private': 'changed'})
            self.assertEqual(json.loads(target.read_text())['private'], 'PRIVATE_DATA')

    def test_safe_routes_never_print_arbitrary_configuration(self):
        result = audit.safe_routes({'AI_MODEL_FAST': 'PRIVATE_SECRET', 'AI_MODEL_STANDARD': 'openai/gpt-6.1-sol'})
        self.assertNotIn('PRIVATE_SECRET', json.dumps(result))
        self.assertEqual(result['standard'], 'openai/gpt-6.1-sol')

    def test_catalog_price_and_generation_filter(self):
        result = audit.model_catalogue(catalog([catalog_row(), catalog_row(model_name='openai/gpt-5.5'),
            catalog_row(model_name='PRIVATE_CATALOG_TEXT')]))
        self.assertEqual(len(result['models']), 1)
        self.assertEqual(result['models'][0]['input_rub_per_million'], '10.00000')
        self.assertNotIn('PRIVATE_', json.dumps(result))
        self.assertFalse(result['inference_verified'])

    def test_incomplete_catalog_never_selects_models(self):
        with self.assertRaisesRegex(audit.AuditError, 'catalog_incomplete'):
            audit.model_catalogue({'models': [], 'meta': {'total': 100}})

    def test_unknown_model_state_and_deprecation(self):
        rows = [catalog_row(is_stopped='false'), catalog_row(is_deprecated=True)]
        result = audit.model_catalogue(catalog(rows))['models']
        self.assertFalse(result[0]['state_known'])
        self.assertFalse(result[0]['active'])
        self.assertFalse(result[1]['active'])

    def test_invalid_prices_never_become_zero_price_routes(self):
        for price in ('NaN', 'Infinity', '-1', True, 'PRIVATE_PRICE', '0'):
            with self.subTest(price=price):
                row = catalog_row(parameter_values={'cost_in': price, 'cost_out': '1'})
                result = audit.model_catalogue(catalog([row]))['models'][0]
                self.assertFalse(result['price_verified'])
                self.assertNotIn('input_rub_per_million', result)

    def test_context_price_tiers_use_largest_declared_rate(self):
        row = catalog_row(price_tiers=[{'above_context_tokens': 1000, 'cost_in': '0.001', 'cost_out': '0.002'}])
        result = audit.model_catalogue(catalog([row]))['models'][0]
        self.assertEqual(result['input_rub_per_million'], '1000.000')

    def test_cache_write_cost_is_included_in_conservative_price(self):
        row = catalog_row(parameter_values={'cost_in': '0.001', 'cost_out': '0.002',
                                            'cost_cache_read': '0', 'cost_cache_write': '0.003'})
        result = audit.model_catalogue(catalog([row]))['models'][0]
        self.assertEqual(result['input_rub_per_million'], '3000.000')

    def test_boolean_cache_cost_is_not_a_zero_price(self):
        row = catalog_row(parameter_values={'cost_in': '1', 'cost_out': '1', 'cost_cache_read': False})
        self.assertFalse(audit.model_catalogue(catalog([row]))['models'][0]['price_verified'])

    def test_transport_uses_fixed_venv_and_bounded_child(self):
        path = Path(__file__).resolve().parents[1] / 'tools/prepare_live_readiness_transport.py'
        spec = importlib.util.spec_from_file_location('prepare', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        previous = Path.cwd()
        try:
            with tempfile.TemporaryDirectory() as directory:
                os.chdir(directory)
                Path('deploy/plan-20261027').mkdir(parents=True)
                Path('deploy/live_readiness_audit.py').write_text('value = "synthetic"\n')
                module.main()
                operation = Path('deploy/plan-20261027/operation.py').read_text()
                response = subprocess.CompletedProcess([], 0, stdout=b'{"status":"observed"}', stderr=b'')
                with patch.object(subprocess, 'run', return_value=response) as call, patch('sys.stdout', new_callable=io.StringIO):
                    exec(compile(operation, '<synthetic-operation>', 'exec'), {'ENVELOPE': {'run_id': '41000000000'}})
                self.assertEqual(call.call_args.args[0][:3], ['/opt/analyst-ai/venv/bin/python', '-I', '-c'])
                self.assertEqual(call.call_args.kwargs['timeout'], 200)
                self.assertEqual(call.call_args.kwargs['input'], b'41000000000')
        finally:
            os.chdir(previous)


if __name__ == '__main__':
    unittest.main()
