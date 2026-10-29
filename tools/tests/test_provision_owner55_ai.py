"""Fake-provider provisioning regressions; no external side effects."""
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

TOOLS = Path(__file__).parents[1]
sys.path.insert(0, str(TOOLS))
import provision_owner55_ai as provision

spec = importlib.util.spec_from_file_location('stage_owner55_ai', TOOLS.parent / 'deploy' / 'stage_owner55_ai.py')
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)

KEY_ID = '2b8fa21b-4b04-4904-bd32-ef1181c5f811'
SECRET = 'SYNTHETIC-ONLY-NOT-A-REAL-CREDENTIAL-1234567890._~+/=='
NAME = provision.DEDICATED_PREFIX + '40900000000'
NOW = datetime(2026, 10, 29, 12, tzinfo=timezone.utc)
PRICES = {'availability_verified': True, 'pricing_verified': True,
          'context_window': 1000000, 'max_output_tokens': 32000,
          'documented_generation_parameters': ['max_tokens', 'enable_thinking', 'response_format'],
          'maximum_input_rub_per_million': '20', 'maximum_output_rub_per_million': '40'}


class FakeAPI:
    def __init__(self):
        self.calls, self.rows, self.limits = [], [], []
        self.currency, self.secret = 'RUB', SECRET
        self.wrong_limit = False
        self.creation_unknown = False

    def request(self, method, path, body=None):
        self.calls.append((method, path, body))
        if method == 'GET' and path == provision.FINANCES:
            return {'finances': {'currency': self.currency, 'balance': 'must-not-escape'}}
        if method == 'GET' and path == provision.MODELS:
            return {}
        if method == 'GET' and path == provision.KEYS:
            return {'ai_keys': list(self.rows), 'meta': {'total': len(self.rows)}}
        if method == 'POST' and path == provision.KEYS:
            if self.creation_unknown:
                raise provision.ProvisionError('cloud_outcome_unknown')
            row = {'id': KEY_ID, 'name': body['name'], 'entity_type': 'aikey', 'entity_id': None,
                   'project_id': 2941515, 'is_readonly': False, 'fallback_models': [], 'expires_at': None}
            self.rows.append(row)
            return {'ai_key': row, 'key': self.secret}
        if path == provision.KEYS + '/' + KEY_ID + '/entity-limits':
            if method == 'POST':
                row = {'id': '0f6b7d8e-1c2a-4b3d-9e8f-7a6b5c4d3e2' + str(len(self.limits)),
                       'ai_key_id': KEY_ID, 'entity_id': KEY_ID, 'entity_type': 'aikey',
                       'model_id': None, 'limit_type': body['limit_type'],
                       'money_limit': '1' if self.wrong_limit else '0.00000000'}
                self.limits.append(row)
                return {'ai_key_entity_limit': row}
            if method == 'GET':
                return {'ai_key_entity_limits': list(self.limits), 'meta': {'total': len(self.limits)}}
        if method == 'DELETE' and path == provision.KEYS + '/' + KEY_ID:
            self.rows = []
            return {}
        raise AssertionError('Unexpected synthetic request')


class ProvisionTests(unittest.TestCase):
    def setUp(self):
        self.api, self.deliveries = FakeAPI(), []
        self.stage_error = None
        patch = mock.patch.object(provision, 'model_summary', return_value=dict(PRICES))
        self.model = patch.start()
        self.addCleanup(patch.stop)

    def transfer(self, operation, payload, secret, contract):
        self.deliveries.append((payload['action'], secret))
        if payload['action'] == 'preflight':
            return {'status': 'ready', 'reason': 'ready', 'server_id': 9417611, 'existing_key_absent': True,
                    'budget_sources_verified': True, 'configuration_changed': False}
        if self.stage_error:
            raise self.stage_error
        self.assertEqual(secret, SECRET)
        self.assertEqual(payload['pricing']['input_rub_per_million'], '20')
        return {'status': 'staged_disabled', 'server_id': 9417611, 'key_id': KEY_ID,
                'model': provision.MODEL, 'daily_cap_rub': '0', 'monthly_cap_rub': '0',
                'existing_key_replaced': False, 'service_restarted': False, 'inference_called': False}

    def invoke(self):
        return provision.provision(self.api, self.transfer, 'reviewed-op', {}, NAME, now=NOW)

    def writes(self):
        return [call for call in self.api.calls if call[0] != 'GET']

    def test_success_blocks_before_private_delivery_and_emits_no_secrets(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            receipt = self.invoke()
        self.assertFalse(receipt['runtime_activation_performed'])
        self.assertEqual(receipt['provider_daily_limit_rub'], '0')
        self.assertEqual(receipt['provider_30_day_limit_rub'], '0')
        self.assertNotIn(SECRET, str(receipt) + stdout.getvalue() + stderr.getvalue())
        self.assertEqual([call[0] for call in self.writes()], ['POST', 'POST', 'POST'])
        self.assertEqual(self.writes()[0][2]['fallback_models'], [])
        self.assertEqual([call[2]['money_limit'] for call in self.writes()[1:]], [0, 0])
        self.assertEqual(self.deliveries, [('preflight', None), ('stage_disabled', SECRET)])

    def test_non_rub_account_never_creates_key(self):
        self.api.currency = 'EUR'
        with self.assertRaisesRegex(provision.ProvisionError, 'account_currency_not_rub'):
            self.invoke()
        self.assertEqual(self.writes(), [])

    def test_ambiguous_model_prices_never_create_key(self):
        self.model.return_value = {'availability_verified': False, 'pricing_verified': False}
        with self.assertRaisesRegex(provision.ProvisionError, 'current_model_prices_not_verified'):
            self.invoke()
        self.assertEqual(self.writes(), [])

    def test_existing_dedicated_key_is_not_rotated(self):
        self.api.rows = [{'id': KEY_ID, 'name': NAME}]
        with self.assertRaisesRegex(provision.ProvisionError, 'existing_dedicated_key_requires_inspection'):
            self.invoke()
        self.assertEqual(self.writes(), [])

    def test_preflight_transport_failure_never_creates_ai_key_and_preserves_safe_metadata(self):
        failure = provision.PrivateTransportError('private_remote_operation_failed',
                    operation_started=True, temporary_key_removed=False)
        transfer = mock.Mock(side_effect=failure)
        with self.assertRaisesRegex(provision.ProvisionError, '^private_preflight_requires_inspection$') as raised:
            provision.provision(self.api, transfer, 'reviewed-op', {}, NAME, now=NOW)
        result = raised.exception
        self.assertEqual(result.transport_code, 'private_remote_operation_failed')
        self.assertTrue(result.transport_operation_started)
        self.assertFalse(result.temporary_ssh_key_removed)
        self.assertIsNone(result.key_id)
        self.assertFalse(result.retained)
        self.assertEqual(self.writes(), [])

    def test_preflight_diagnostics_do_not_copy_unknown_exception_text(self):
        failure = provision.PrivateTransportError(SECRET, operation_started=False)
        result = provision.preflight_transport_error(failure)
        self.assertEqual(result.transport_code, 'private_preflight_failed')
        self.assertNotIn(SECRET, repr(result.__dict__))

    def test_readonly_preflight_cannot_create_or_change_ai_key(self):
        receipt = provision.inspect_preflight(self.api, self.transfer, 'reviewed-op', {}, now=NOW)
        self.assertEqual(receipt['status'], 'ready')
        self.assertTrue(receipt['read_only_preflight'])
        self.assertFalse(receipt['ai_key_created'])
        self.assertFalse(receipt['ai_limits_changed'])
        self.assertEqual(self.writes(), [])

    def test_readonly_preflight_preserves_fixed_remote_blocker_without_writes(self):
        transfer = mock.Mock(return_value={'status': 'not_ready', 'reason': 'incomplete_budget_source_proof',
            'server_id': 9417611, 'existing_key_absent': False, 'budget_sources_verified': False,
            'configuration_changed': False})
        receipt = provision.inspect_preflight(self.api, transfer, 'reviewed-op', {}, now=NOW)
        self.assertEqual(receipt['status'], 'not_ready')
        self.assertEqual(receipt['reason'], 'incomplete_budget_source_proof')
        self.assertEqual(self.writes(), [])

    def test_masked_creation_removes_only_just_created_unused_key(self):
        self.api.secret = provision.MASKED
        with self.assertRaisesRegex(provision.ProvisionError, 'new_unused_key_removed_after_failure') as raised:
            self.invoke()
        self.assertEqual(raised.exception.failure_code, 'new_gateway_key_masked')
        self.assertEqual([call[0] for call in self.writes()], ['POST', 'DELETE'])
        self.assertEqual(self.deliveries, [('preflight', None)])

    def test_invalid_creation_removes_only_new_unused_key_without_secret_diagnostics(self):
        invalid = 'SYNTHETIC-ONLY-NOT-A-REAL-CREDENTIAL\r\nInjected: value'
        self.api.secret = invalid
        with self.assertRaisesRegex(provision.ProvisionError, 'new_unused_key_removed_after_failure') as raised:
            self.invoke()
        self.assertEqual(raised.exception.failure_code, 'new_gateway_key_invalid')
        self.assertFalse(raised.exception.retained)
        self.assertEqual([call[0] for call in self.writes()], ['POST', 'DELETE'])
        self.assertEqual(self.deliveries, [('preflight', None)])
        self.assertNotIn(invalid, str(raised.exception))

    def test_diagnostics_only_return_fixed_codes_never_arbitrary_provider_text(self):
        arbitrary = provision.ProvisionError(SECRET)
        self.assertEqual(provision.safe_failure_code(arbitrary), 'unclassified_failure')
        self.assertEqual(provision.safe_failure_code(RuntimeError(SECRET)), 'unclassified_failure')

    def test_zero_limit_readback_failure_deletes_unused_key(self):
        self.api.wrong_limit = True
        with self.assertRaisesRegex(provision.ProvisionError, 'new_unused_key_removed_after_failure'):
            self.invoke()
        self.assertEqual(self.writes()[-1][0], 'DELETE')
        self.assertEqual(self.deliveries, [('preflight', None)])

    def test_pre_dispatch_transport_failure_deletes_unused_key(self):
        self.stage_error = provision.PrivateTransportError('private_ssh_unavailable', operation_started=False)
        with self.assertRaisesRegex(provision.ProvisionError, 'new_unused_key_removed_after_failure'):
            self.invoke()
        self.assertEqual(self.writes()[-1][0], 'DELETE')

    def test_indeterminate_delivery_retains_key_at_verified_zero_limits(self):
        self.stage_error = provision.PrivateTransportError('timeout', operation_started=True)
        with self.assertRaisesRegex(provision.ProvisionError, 'private_delivery_requires_inspected_recovery') as raised:
            self.invoke()
        self.assertTrue(raised.exception.retained)
        self.assertEqual(raised.exception.key_id, KEY_ID)
        self.assertNotIn('DELETE', [call[0] for call in self.writes()])
        self.assertEqual(len(self.api.limits), 2)

    def test_creation_timeout_is_not_retried_or_deleted_by_guess(self):
        self.api.creation_unknown = True
        with self.assertRaisesRegex(provision.ProvisionError, 'key_creation_requires_inspected_recovery') as raised:
            self.invoke()
        self.assertIsNone(raised.exception.retained)
        self.assertEqual([call[0] for call in self.writes()], ['POST'])

    def test_existing_id_case_variant_never_becomes_cleanup_target(self):
        self.api.rows = [{'id': KEY_ID.upper(), 'name': 'some-other-application'}]
        with self.assertRaisesRegex(provision.ProvisionError, 'new_key_identity_unknown'):
            self.invoke()
        self.assertEqual([call[0] for call in self.writes()], ['POST'])

    def test_duplicate_inventory_identity_blocks_before_creation(self):
        self.api.rows = [{'id': KEY_ID, 'name': 'one'}, {'id': KEY_ID.upper(), 'name': 'two'}]
        with self.assertRaisesRegex(provision.ProvisionError, 'key_inventory_identity_invalid'):
            self.invoke()
        self.assertEqual(self.writes(), [])


class StagingFormatTests(unittest.TestCase):
    def test_remote_preflight_does_not_return_unknown_exception_text(self):
        with mock.patch.object(stage.os, 'getuid', return_value=0, create=True), \
             mock.patch.object(stage, 'LOCK') as lock:
            lock.open.side_effect = RuntimeError(SECRET)
            receipt = stage.preflight({'payload': {'action': 'preflight'}, 'secret': None})
        self.assertEqual(receipt['reason'], 'preflight_not_verified')
        self.assertFalse(receipt['configuration_changed'])
        self.assertNotIn(SECRET, str(receipt))

    def test_concurrent_configuration_edit_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            configuration = Path(directory) / 'backend.env'
            configuration.write_bytes(b'OTHER_SECRET=synthetic-existing\n')
            expected = (configuration.read_bytes(), stage.file_identity(configuration.stat()))
            changed = (b'OTHER_SECRET=synthetic-newer\n', expected[1])
            with mock.patch.object(stage, 'CONFIGURATION', configuration), \
                 mock.patch.object(stage, 'configuration_snapshot', return_value=changed), \
                 mock.patch.object(stage.os, 'chown', create=True), \
                 mock.patch.object(stage.os, 'replace') as replace:
                with self.assertRaisesRegex(RuntimeError, 'configuration_changed_before_write'):
                    stage.atomic_configuration(b'TIMEWEB_AI_TOKEN=synthetic\n', expected)
            replace.assert_not_called()
            self.assertEqual(configuration.read_bytes(), expected[0])

    def test_duplicate_variables_are_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'duplicate_environment_variable'):
            stage.parse_environment(b'TIMEWEB_AI_TOKEN=one\nTIMEWEB_AI_TOKEN=two\n')

    def test_existing_or_hidden_credential_is_never_overwritten(self):
        for value in (SECRET, provision.MASKED):
            with self.subTest(value=value):
                with self.assertRaisesRegex(RuntimeError, 'existing_inference_key_must_not_be_replaced'):
                    stage.no_existing_key({'TIMEWEB_AI_TOKEN': value})

    def test_legacy_gateway_credential_is_never_shadowed(self):
        with self.assertRaisesRegex(RuntimeError, 'existing_inference_key_must_not_be_replaced'):
            stage.no_existing_key({'TIMEWEB_CLOUD_API_KEY': SECRET})

    def test_disabled_configuration_preserves_unrelated_secret_bytes(self):
        original = b'# original\nOTHER_SECRET=synthetic-existing\nAI_USER_DAILY_RUB=90\n'
        changes = {**stage.DISABLED, 'TIMEWEB_AI_TOKEN': SECRET}
        replaced = stage.replacement_environment(original, changes)
        self.assertIn(b'OTHER_SECRET=synthetic-existing\n', replaced)
        parsed = stage.parse_environment(replaced)
        for key, value in stage.DISABLED.items():
            self.assertEqual(parsed[key], value)
        self.assertEqual(parsed['TIMEWEB_AI_TOKEN'], SECRET)


class GatewayCredentialGrammarTests(unittest.TestCase):
    def test_controller_and_remote_accept_opaque_bearer_grammar_at_bounds(self):
        values = ['a', 'a' * 8192, 'synthetic:opaque:key', SECRET,
                  'eyJhbGciOiJIUzI1NiJ9.synthetic_signature-1234567890',
                  'sk-SYNTHETIC-ONLY-NOT-A-REAL-CREDENTIAL-1234567890',
                  'a' * 30 + '==']
        for index, value in enumerate(values):
            with self.subTest(case=index):
                provision.require_gateway_key(value)
                stage.require_gateway_key(value)

    def test_controller_and_remote_reject_invalid_or_masked_credentials_consistently(self):
        values = [None, {}, '', 'a' * 8193,
                  'a' * 31 + '\n', 'a' * 31 + '\r', 'a' * 31 + ' ',
                  'a' * 31 + '\u00e9', 'a' * 31 + '\x7f',
                  'a' * 31 + '\x00', provision.MASKED]
        for index, value in enumerate(values):
            code = 'new_gateway_key_masked' if value == provision.MASKED else 'new_gateway_key_invalid'
            with self.subTest(case=index):
                with self.assertRaisesRegex(provision.ProvisionError, '^' + code + '$'):
                    provision.require_gateway_key(value)
                with self.assertRaisesRegex(RuntimeError, '^' + code + '$'):
                    stage.require_gateway_key(value)

    def test_settings_and_environment_preserve_opaque_token_without_normalization(self):
        payload = {'key_id': KEY_ID, 'model': stage.MODEL, 'pricing': {
            'input_rub_per_million': '60', 'output_rub_per_million': '60',
            'valid_until': '2026-10-30T12:00:00+00:00'}}
        with mock.patch.object(stage, 'validate_prices'):
            settings = stage.settings_for(payload, SECRET)
        serialized = stage.replacement_environment(b'OTHER_SECRET=synthetic-existing\n', settings)
        self.assertEqual(stage.parse_environment(serialized)['TIMEWEB_AI_TOKEN'], SECRET)
        self.assertEqual(settings['AI_EXTERNAL_PROCESSING_APPROVED'], 'false')
        self.assertEqual(settings['AI_USER_DAILY_RUB'], '0')
        self.assertEqual(settings['AI_USER_MONTHLY_RUB'], '0')


if __name__ == '__main__':
    unittest.main()
