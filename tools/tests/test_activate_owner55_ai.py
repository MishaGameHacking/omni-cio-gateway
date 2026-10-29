"""Activation regressions use synthetic keys, mocked providers and no network."""
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

TOOLS = Path(__file__).parents[1]
sys.path.insert(0, str(TOOLS))
import activate_owner55_ai as activation


def load_script(name, relative):
    spec = importlib.util.spec_from_file_location(name, TOOLS.parent / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


stage = load_script('stage_for_activation_test', 'deploy/stage_owner55_ai.py')
remote = load_script('remote_activation_test', 'deploy/activate_owner55_ai.py')
remote.STAGING = stage.__dict__
KEY_ID = '2b8fa21b-4b04-4904-bd32-ef1181c5f811'
DAY = '4abc649e-8f69-4a11-87fa-e24f3574d385'
MONTH = '6b434639-2e0b-4817-83b4-614ca2839a67'
RUN = '40900000000'
SECRET = 'SYNTHETIC-ONLY-NOT-A-REAL-CREDENTIAL-1234567890._~+/=='
NOW = datetime(2026, 10, 29, 12, tzinfo=timezone.utc)
REPORT = {'availability_verified': True, 'pricing_verified': True, 'context_window': 1000000,
          'max_output_tokens': 262144, 'documented_generation_parameters': ['max_tokens', 'enable_thinking'],
          'maximum_input_rub_per_million': '60', 'maximum_output_rub_per_million': '60'}


class FakeAPI:
    def __init__(self):
        self.calls = []
        self.key_id = KEY_ID
        self.values = {'day': '0', 'month': '0'}
        self.fail_nonzero = None
        self.fail_zero = False

    def request(self, method, path, body=None):
        self.calls.append((method, path, body))
        if method == 'GET' and path == activation.provision.FINANCES:
            return {'finances': {'currency': 'RUB'}}
        if method == 'GET' and path == activation.provision.MODELS:
            return {}
        if method == 'GET' and path == activation.KEYS:
            row = {'id': self.key_id, 'name': activation.provision.DEDICATED_PREFIX + RUN,
                   'entity_type': 'aikey', 'entity_id': None, 'project_id': 2941515,
                   'is_readonly': False, 'fallback_models': [], 'expires_at': None}
            return {'ai_keys': [row], 'meta': {'total': 1}}
        base = activation.KEYS + '/' + KEY_ID + '/entity-limits'
        if method == 'GET' and path == base:
            rows = [{'id': identity, 'ai_key_id': KEY_ID, 'entity_id': KEY_ID,
                     'entity_type': 'aikey', 'model_id': None, 'limit_type': period,
                     'money_limit': self.values[period]} for period, identity in (('day', DAY), ('month', MONTH))]
            return {'ai_key_entity_limits': rows, 'meta': {'total': 2}}
        if method == 'PATCH' and path in (base + '/' + DAY, base + '/' + MONTH):
            period = 'day' if path.endswith(DAY) else 'month'
            if body['money_limit'] == 0 and self.fail_zero:
                raise RuntimeError('synthetic lost blocking response')
            self.values[period] = str(body['money_limit'])
            if body['money_limit'] and period == self.fail_nonzero:
                raise RuntimeError('synthetic lost PATCH response after commit')
            return {'ai_key_entity_limit': {}}
        raise AssertionError('Unexpected synthetic provider request')


class ActivationTests(unittest.TestCase):
    def setUp(self):
        self.api, self.actions = FakeAPI(), []
        self.preflight_error = self.activation_error = False
        patch = mock.patch.object(activation.provision, 'model_summary', return_value=dict(REPORT))
        patch.start()
        self.addCleanup(patch.stop)

    def transfer(self, operation, payload, secret, contract):
        self.assertIsNone(secret)
        self.actions.append(payload['action'])
        if payload['action'] == 'preflight_activation':
            self.assertEqual(self.api.values, {'day': '0', 'month': '0'})
            if self.preflight_error:
                raise RuntimeError('synthetic GET authentication failure')
            return {'status': 'activation_ready', 'server_id': 9417611, 'key_id': KEY_ID,
                    'inference_key_authenticated': True, 'model_present': True,
                    'configuration_changed': False, 'inference_probe_called': False}
        self.assertEqual(self.api.values, activation.LIMITS)
        if self.activation_error:
            raise RuntimeError('synthetic SSH timeout after possible activation')
        return activation.activated_receipt(KEY_ID, payload['pricing'])

    def invoke(self):
        return activation.activate(self.api, self.transfer, 'reviewed-script', {}, KEY_ID, RUN, now=NOW)

    def writes(self):
        return [call for call in self.api.calls if call[0] != 'GET']

    def test_success_enables_matching_bounded_caps_after_zero_limit_authentication(self):
        receipt = self.invoke()
        self.assertEqual(self.actions, ['preflight_activation', 'activate'])
        self.assertEqual([call[2] for call in self.writes()], [{'money_limit': 95}, {'money_limit': 2900}])
        self.assertEqual(receipt['daily_cap_rub'], '95')
        self.assertEqual(receipt['monthly_cap_rub'], '2900')
        self.assertFalse(receipt['automatic_price_renewal_installed'])
        self.assertFalse(receipt['inference_probe_called'])
        self.assertFalse(receipt['brokerage_request_sent'])

    def test_authentication_failure_does_not_raise_provider_limits(self):
        self.preflight_error = True
        with self.assertRaisesRegex(RuntimeError, 'synthetic GET authentication failure'):
            self.invoke()
        self.assertEqual(self.writes(), [])

    def test_foreign_key_is_never_modified(self):
        self.api.key_id = '0198ef63-c5e8-4a60-8877-071d7bd67e40'
        with self.assertRaisesRegex(activation.ActivationError, 'dedicated_key_identity_changed'):
            self.invoke()
        self.assertEqual(self.writes(), [])

    def test_existing_nonzero_limits_are_not_treated_as_staged(self):
        self.api.values['day'] = '1'
        with self.assertRaisesRegex(activation.ActivationError, 'provider_limit_binding_invalid'):
            self.invoke()
        self.assertEqual(self.writes(), [])

    def test_partial_patch_unknown_outcome_blocks_both_periods(self):
        self.api.fail_nonzero = 'month'
        with self.assertRaisesRegex(activation.ActivationError, 'activation_requires_inspected_recovery') as raised:
            self.invoke()
        self.assertTrue(raised.exception.provider_blocked)
        self.assertEqual(self.api.values, {'day': '0', 'month': '0'})
        self.assertEqual(self.actions, ['preflight_activation'])
        self.assertEqual([call[2] for call in self.writes()][-2:], [{'money_limit': 0}, {'money_limit': 0}])

    def test_timeout_after_possible_activation_blocks_provider_without_deleting_key(self):
        self.activation_error = True
        with self.assertRaisesRegex(activation.ActivationError, 'activation_requires_inspected_recovery') as raised:
            self.invoke()
        self.assertTrue(raised.exception.provider_blocked)
        self.assertEqual(self.actions, ['preflight_activation', 'activate'])
        self.assertEqual([call[0] for call in self.writes()], ['PATCH'] * 4)
        self.assertEqual(self.api.values, {'day': '0', 'month': '0'})

    def test_unverified_emergency_block_is_not_reported_as_success(self):
        self.activation_error = self.api.fail_zero = True
        with self.assertRaises(activation.ActivationError) as raised:
            self.invoke()
        self.assertFalse(raised.exception.provider_blocked)
        self.assertEqual([call[2] for call in self.writes()][-2:], [{'money_limit': 0}, {'money_limit': 0}])

    def test_patch_adapter_rejects_key_rotation_and_unreviewed_caps(self):
        api = activation.ActivationAPI('synthetic-cloud-secret')
        api._opener = mock.Mock()
        for method, path, body in [('POST', activation.KEYS, {}), ('DELETE', activation.KEYS + '/' + KEY_ID, {}),
                ('PATCH', activation.KEYS + '/' + KEY_ID + '/entity-limits/' + DAY, {'money_limit': 100})]:
            with self.subTest(method=method, path=path):
                with self.assertRaisesRegex(activation.ActivationError, 'activation_endpoint_not_allowlisted'):
                    api.request(method, path, body)
        api._opener.open.assert_not_called()


class RemoteActivationTests(unittest.TestCase):
    def test_readiness_retries_service_exec_race_before_claiming_loaded(self):
        with mock.patch.object(remote, 'verify_running_configuration',
                side_effect=[RuntimeError('ai_process_configuration_not_loaded'), None]) as verify, \
             mock.patch.object(remote, 'read_get', return_value={'status':'ok'}) as get, \
             mock.patch.object(remote.time, 'sleep') as sleep:
            remote.readiness_after_restart({'AI_EXTERNAL_PROCESSING_APPROVED':'false'})
        self.assertEqual(verify.call_count, 2)
        self.assertEqual(get.call_count, 2)
        sleep.assert_called_once_with(1)

    def test_readiness_does_not_hide_persistent_missing_configuration(self):
        with mock.patch.object(remote, 'verify_running_configuration',
                side_effect=RuntimeError('ai_process_configuration_not_loaded')) as verify, \
             mock.patch.object(remote, 'read_get') as get, \
             mock.patch.object(remote.time, 'sleep'):
            with self.assertRaisesRegex(RuntimeError, 'ai_process_configuration_not_loaded'):
                remote.readiness_after_restart({'TIMEWEB_AI_TOKEN':SECRET})
        self.assertEqual(verify.call_count, 10)
        get.assert_not_called()

    def setUp(self):
        self.payload = {'key_id': KEY_ID, 'model': activation.MODEL,
                        'limit_ids': {'day': DAY, 'month': MONTH},
                        'pricing': {'input_rub_per_million': '60', 'output_rub_per_million': '60',
                                    'valid_until': (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()}}
        self.settings = stage.settings_for(self.payload, SECRET)

    def test_environment_source_is_verified_without_reading_service_environment(self):
        with mock.patch.object(remote, 'systemctl', return_value='/etc/analyst-ai/backend.env (ignore_errors=no)') as service:
            remote.verify_environment_file()
            service.assert_called_once_with('show', 'analyst-ai-owner.service', '--property=EnvironmentFiles', '--value')
        with mock.patch.object(remote, 'systemctl', return_value='/some/other/config.env (ignore_errors=no)'):
            with self.assertRaisesRegex(RuntimeError, 'owner_service_environment_file_unverified'):
                remote.verify_environment_file()
        self.assertEqual(remote.SERVICES, ('analyst-ai-owner.service',))

    def test_only_reviewed_ai_configuration_changes_and_key_remains_identical(self):
        self.settings['BROKER_TRADE_MODE'] = 'unchanged-synthetic'
        self.settings['UNRELATED_SECRET'] = 'existing-synthetic'
        changes = remote.activation_settings(self.settings, self.payload)
        original = stage.replacement_environment(b'', self.settings)
        after = stage.parse_environment(stage.replacement_environment(original, changes))
        self.assertEqual(after['TIMEWEB_AI_TOKEN'], SECRET)
        self.assertEqual(after['BROKER_TRADE_MODE'], 'unchanged-synthetic')
        self.assertEqual(after['UNRELATED_SECRET'], 'existing-synthetic')
        for key, value in remote.ENABLED.items():
            self.assertEqual(after[key], value)
        self.assertEqual(after['ANALYST_OWNER_AI_DAY_LIMIT_ID'], DAY)

    def test_already_active_configuration_requires_recovery_not_reactivation(self):
        self.settings.update(remote.ENABLED)
        with self.assertRaisesRegex(RuntimeError, 'staged_ai_is_not_disabled'):
            remote.activation_settings(self.settings, self.payload)

    def test_changed_staged_key_cannot_be_activated(self):
        self.settings['ANALYST_OWNER_AI_KEY_ID'] = DAY
        with self.assertRaisesRegex(RuntimeError, 'staged_key_identity_mismatch'):
            remote.activation_settings(self.settings, self.payload)

    def test_metadata_readiness_is_get_only_and_has_no_secret_output(self):
        response = mock.MagicMock()
        response.status = 200
        response.read.return_value = json.dumps({'data': [{'id': activation.MODEL}]}).encode()
        response.__enter__.return_value = response
        opener = mock.Mock()
        opener.open.return_value = response
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(remote.urllib.request, 'build_opener', return_value=opener), \
             redirect_stdout(stdout), redirect_stderr(stderr):
            remote.verify_inference_key(SECRET)
        request = opener.open.call_args.args[0]
        self.assertEqual(request.method, 'GET')
        self.assertEqual(request.full_url, 'https://api.timeweb.ai/v1/models')
        self.assertEqual(request.get_header('Authorization'), 'Bearer ' + SECRET)
        self.assertEqual(stdout.getvalue() + stderr.getvalue(), '')
        self.assertIsNone(remote.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://elsewhere.invalid'))

    def test_exact_model_must_be_present_once(self):
        for rows in ([], [{'id': activation.MODEL}, {'id': activation.MODEL}], [{'id': 'other-model'}]):
            with self.subTest(rows=rows):
                with mock.patch.object(remote, 'read_get', return_value={'data': rows}):
                    with self.assertRaisesRegex(RuntimeError, 'exact_inference_model_unavailable'):
                        remote.verify_inference_key(SECRET)

    def test_provider_error_message_cannot_escape_readiness(self):
        error = remote.urllib.error.URLError('synthetic remote body containing ' + SECRET)
        with mock.patch.object(remote.urllib.request, 'build_opener') as build:
            build.return_value.open.side_effect = error
            with self.assertRaisesRegex(RuntimeError, '^read_only_readiness_failed$') as raised:
                remote.verify_inference_key(SECRET)
        self.assertNotIn(SECRET, str(raised.exception))

    def test_process_environment_requires_actual_enforced_values(self):
        expected = {'TIMEWEB_AI_TOKEN': SECRET, **remote.ENABLED}
        raw = b'\0'.join(key.encode() + b'=' + value.encode() for key, value in expected.items()) + b'\0'
        process_file = mock.Mock()
        process_file.open.side_effect = lambda *args, **kwargs: io.BytesIO(raw)
        status = lambda *args: 'active' if args[0] == 'is-active' else '2345'
        with mock.patch.object(remote, 'systemctl', side_effect=status), \
             mock.patch.object(remote, 'Path', return_value=process_file):
            remote.verify_running_configuration(expected)
            changed = dict(expected, AI_USER_DAILY_RUB='100')
            with self.assertRaisesRegex(RuntimeError, 'ai_process_configuration_not_loaded'):
                remote.verify_running_configuration(changed)


if __name__ == '__main__':
    unittest.main()
