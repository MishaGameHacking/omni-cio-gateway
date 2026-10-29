"""Synthetic renewal checks: no credentials, provider writes or paid requests."""
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

TOOLS = Path(__file__).parents[1]
sys.path.insert(0, str(TOOLS))
import renew_owner55_ai as renewal


def script(name, relative):
    spec = importlib.util.spec_from_file_location(name, TOOLS.parent / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


stage = script('renewal_stage_helpers', 'deploy/stage_owner55_ai.py')
active = script('renewal_activation_helpers', 'deploy/activate_owner55_ai.py')
remote = script('renewal_remote', 'deploy/renew_owner55_ai.py')
active.STAGING = stage.__dict__
remote.STAGING, remote.ACTIVATION = stage.__dict__, active.__dict__
KEY = '2b8fa21b-4b04-4904-bd32-ef1181c5f811'
DAY = '4abc649e-8f69-4a11-87fa-e24f3574d385'
MONTH = '6b434639-2e0b-4817-83b4-614ca2839a67'
CREATION = '40900000000'
SECRET = 'SYNTHETIC-ONLY-NOT-A-REAL-CREDENTIAL-1234567890._~+/=='
NOW = datetime(2026, 10, 29, 12, tzinfo=timezone.utc)
REPORT = {'availability_verified': True, 'pricing_verified': True, 'context_window': 1000000,
          'max_output_tokens': 262144, 'documented_generation_parameters': ['max_tokens', 'enable_thinking'],
          'maximum_input_rub_per_million': '60', 'maximum_output_rub_per_million': '60'}


class FakeAPI:
    def __init__(self):
        self.calls, self.values = [], {'day': '95', 'month': '2900'}
        self.block_fails = False

    def request(self, method, path, body=None):
        self.calls.append((method, path, body))
        base = renewal.activation.KEYS
        if method == 'GET' and path == renewal.activation.provision.FINANCES:
            return {'finances': {'currency': 'RUB'}}
        if method == 'GET' and path == renewal.activation.provision.MODELS:
            return {}
        if method == 'GET' and path == base:
            return {'ai_keys': [{'id': KEY, 'name': renewal.activation.provision.DEDICATED_PREFIX + CREATION,
                    'entity_type': 'aikey', 'entity_id': None, 'project_id': 2941515,
                    'is_readonly': False, 'fallback_models': [], 'expires_at': None}], 'meta': {'total': 1}}
        limits_path = base + '/' + KEY + '/entity-limits'
        if method == 'GET' and path == limits_path:
            return {'ai_key_entity_limits': [{'id': identity, 'ai_key_id': KEY, 'entity_id': KEY,
                'entity_type': 'aikey', 'model_id': None, 'limit_type': period,
                'money_limit': self.values[period]} for period, identity in (('day', DAY), ('month', MONTH))],
                'meta': {'total': 2}}
        if method == 'PATCH' and path in (limits_path + '/' + DAY, limits_path + '/' + MONTH):
            period = 'day' if path.endswith(DAY) else 'month'
            if body['money_limit'] == 0 and self.block_fails:
                raise RuntimeError('synthetic blocking failure')
            self.values[period] = str(body['money_limit'])
            return {}
        raise AssertionError('Unexpected synthetic API request')


class RenewalControllerTests(unittest.TestCase):
    def setUp(self):
        self.api, self.actions = FakeAPI(), []
        self.due, self.fail_remote, self.limit_drift = True, False, False
        self.price_patch = mock.patch.object(renewal.activation.provision, 'model_summary', return_value=dict(REPORT))
        self.prices = self.price_patch.start()
        self.addCleanup(self.price_patch.stop)

    def transfer(self, operation, payload, contract):
        self.actions.append(payload['action'])
        self.assertNotIn(SECRET, str(payload))
        if payload['action'] == 'renewal_preflight':
            self.assertEqual(self.api.values, renewal.LIMITS)
            return renewal.preflight_receipt(KEY, self.due)
        self.assertEqual(self.api.values, renewal.LIMITS)
        if self.fail_remote:
            raise RuntimeError('synthetic unknown remote outcome')
        if self.limit_drift:
            self.api.values['day'] = '100'
        return renewal.expected_receipt(KEY, payload['pricing'])

    def invoke(self):
        return renewal.renew(self.api, self.transfer, 'reviewed-operation', {}, KEY, CREATION, now=NOW)

    def patches(self):
        return [call for call in self.api.calls if call[0] == 'PATCH']

    def test_successful_update_never_patches_provider_limits_or_usage_counters(self):
        receipt = self.invoke()
        self.assertEqual(self.actions, ['renewal_preflight', 'renew_prices'])
        self.assertEqual(self.patches(), [])
        self.assertEqual(receipt['status'], 'renewed')
        self.assertEqual(receipt['price_valid_until'], (NOW + timedelta(days=1)).isoformat())
        self.assertFalse(receipt['inference_probe_called'])
        self.assertFalse(receipt['brokerage_request_sent'])
        self.assertFalse(receipt['provider_limits_changed'])
        self.assertTrue(receipt['app_pause_verified'])
        self.assertEqual(sum(path == renewal.activation.provision.MODELS for _, path, _ in self.api.calls), 1)

    def test_before_six_hours_does_not_modify_or_extend_prices(self):
        self.due = False
        receipt = self.invoke()
        self.assertEqual(receipt['status'], 'not_due')
        self.assertNotIn('price_valid_until', receipt)
        self.assertEqual(self.patches(), [])

    def test_missing_fresh_catalog_price_does_not_extend_expiry(self):
        self.prices.return_value = {'availability_verified': True, 'pricing_verified': False}
        with self.assertRaises(renewal.RenewalError) as raised:
            self.invoke()
        self.assertTrue(raised.exception.provider_blocked)
        self.assertEqual(self.api.values, {'day': '0', 'month': '0'})
        self.assertEqual([call[2] for call in self.patches()], [{'money_limit': 0}, {'money_limit': 0}])
        self.assertEqual(self.actions, [])

    def test_manual_or_incident_block_is_never_automatically_removed(self):
        self.api.values = {'day': '0', 'month': '0'}
        with self.assertRaisesRegex(renewal.activation.ActivationError, 'provider_limit_binding_invalid'):
            self.invoke()
        self.assertEqual(self.patches(), [])
        self.assertEqual(self.actions, [])

    def test_unknown_remote_result_keeps_both_provider_limits_zero(self):
        self.fail_remote = True
        with self.assertRaises(renewal.RenewalError) as raised:
            self.invoke()
        self.assertTrue(raised.exception.provider_blocked)
        self.assertEqual(self.api.values, {'day': '0', 'month': '0'})
        self.assertTrue(all(call[2] == {'money_limit': 0} for call in self.patches()))

    def test_external_limit_drift_is_followed_by_blocking_both_periods(self):
        self.limit_drift = True
        with self.assertRaises(renewal.RenewalError) as raised:
            self.invoke()
        self.assertTrue(raised.exception.provider_blocked)
        self.assertEqual(self.api.values, {'day': '0', 'month': '0'})
        self.assertEqual([call[2] for call in self.patches()][-2:], [{'money_limit': 0}, {'money_limit': 0}])

    def test_unverified_emergency_block_is_not_reported_as_confirmed(self):
        self.api.block_fails = self.fail_remote = True
        with self.assertRaises(renewal.RenewalError) as raised:
            self.invoke()
        self.assertFalse(raised.exception.provider_blocked)
        self.assertEqual(self.actions, ['renewal_preflight', 'renew_prices'])


class RemoteRenewalTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.previous = self.now - timedelta(hours=7)
        self.payload = {'key_id': KEY, 'model': renewal.activation.MODEL,
            'limit_ids': {'day': DAY, 'month': MONTH}, 'observed_at': self.now.isoformat(),
            'pricing': {'input_rub_per_million': '60', 'output_rub_per_million': '60',
                        'valid_until': (self.now + timedelta(hours=24)).isoformat()}}
        old = {**self.payload, 'pricing': {**self.payload['pricing'], 'input_rub_per_million': '55',
               'valid_until': (self.previous + timedelta(hours=24)).isoformat()}}
        self.settings = {**stage.settings_for(old, SECRET), **active.ENABLED,
            'ANALYST_OWNER_AI_DAY_LIMIT_ID': DAY, 'ANALYST_OWNER_AI_MONTH_LIMIT_ID': MONTH,
            'UNRELATED_SETTING': 'keep-this', 'BROKER_TOKEN_SETTING': 'synthetic-existing-broker'}

    def test_only_price_fields_and_observation_marker_change(self):
        expected, changes, due = remote.active_configuration(self.settings, self.payload, now=self.now)
        self.assertTrue(due)
        self.assertTrue(all(key.endswith(remote.PRICE_SUFFIXES) or key == remote.REFRESH_MARKER for key in changes))
        after = stage.parse_environment(stage.replacement_environment(stage.replacement_environment(b'', self.settings), changes))
        self.assertEqual(after['TIMEWEB_AI_TOKEN'], SECRET)
        self.assertEqual(after['BROKER_TOKEN_SETTING'], 'synthetic-existing-broker')
        self.assertEqual(after['UNRELATED_SETTING'], 'keep-this')
        self.assertEqual(after['AI_USER_DAILY_RUB'], '95')
        self.assertEqual(after['AI_PROJECT_MONTHLY_RUB'], '2900')
        self.assertEqual(after['AI_FAST_INPUT_RUB_PER_MILLION'], '60')
        self.assertEqual(expected[remote.REFRESH_MARKER], self.now.isoformat())

    def test_server_enforces_six_hour_interval_at_boundary(self):
        for age, due in ((timedelta(hours=6) - timedelta(microseconds=1), False), (timedelta(hours=6), True)):
            with self.subTest(age=age):
                settings = dict(self.settings)
                for tier in ('FAST', 'STANDARD', 'PREMIUM'):
                    settings['AI_' + tier + '_PRICING_VALID_UNTIL'] = (self.now - age + timedelta(hours=24)).isoformat()
                self.assertEqual(remote.active_configuration(settings, self.payload, now=self.now)[2], due)

    def test_fresh_observation_cannot_extend_price_validity_beyond_one_day(self):
        payload = {**self.payload, 'pricing': {**self.payload['pricing'],
                   'valid_until': (self.now + timedelta(days=2)).isoformat()}}
        with self.assertRaisesRegex(RuntimeError, 'fresh_catalog_observation_required'):
            remote.active_configuration(self.settings, payload, now=self.now)

    def test_stale_observation_is_not_relabelled_as_fresh(self):
        observed = self.now - timedelta(minutes=16)
        payload = {**self.payload, 'observed_at': observed.isoformat(),
                   'pricing': {**self.payload['pricing'], 'valid_until': (observed + timedelta(hours=24)).isoformat()}}
        with self.assertRaisesRegex(RuntimeError, 'fresh_catalog_observation_required'):
            remote.active_configuration(self.settings, payload, now=self.now)

    def test_changed_limit_identity_blocks_renewal(self):
        self.settings['ANALYST_OWNER_AI_DAY_LIMIT_ID'] = MONTH
        with self.assertRaisesRegex(RuntimeError, 'renewal_limit_identity_changed'):
            remote.active_configuration(self.settings, self.payload, now=self.now)

    def test_previous_observation_must_match_current_price_expiry(self):
        self.settings[remote.REFRESH_MARKER] = (self.previous - timedelta(minutes=1)).isoformat()
        with self.assertRaisesRegex(RuntimeError, 'renewal_previous_observation_mismatch'):
            remote.active_configuration(self.settings, self.payload, now=self.now)

    def runtime_fakes(self, directory):
        current = [stage.replacement_environment(b'', self.settings)]
        support = dict(stage.__dict__)
        support['LOCK'] = Path(directory) / 'lock'
        support['verify_sources'] = mock.Mock()
        support['configuration_snapshot'] = lambda: (current[0], ('synthetic-identity',))
        support['atomic_configuration'] = lambda raw, expected: current.__setitem__(0, raw)
        helpers = dict(active.__dict__)
        for name in ('verify_environment_file', 'verify_running_configuration', 'readiness_after_restart'):
            helpers[name] = mock.Mock()
        helpers['systemctl'] = mock.Mock(side_effect=lambda *args: 'control-group' if args[0] == 'show' else '')
        helpers['public_feed_pid'] = mock.Mock(return_value='2222')
        helpers['verify_inference_key'] = mock.Mock(side_effect=AssertionError('inference probe forbidden'))
        return current, support, helpers

    def test_restart_only_owner_after_price_write_without_inference_probe(self):
        with tempfile.TemporaryDirectory() as directory:
            current, support, helpers = self.runtime_fakes(directory)
            with mock.patch.object(remote, 'STAGING', support), mock.patch.object(remote, 'ACTIVATION', helpers), \
                 mock.patch.object(remote.os, 'getuid', return_value=0):
                receipt = remote.run({'payload': {**self.payload, 'action': 'renew_prices'}, 'secret': None})
            self.assertEqual(receipt['status'], 'renewed')
            self.assertEqual(helpers['systemctl'].call_args_list,
                [mock.call('show', 'analyst-ai-owner.service', '--property=KillMode', '--value'),
                 mock.call('restart', 'analyst-ai-owner.service'), mock.call('restart', 'analyst-ai-owner.service')])
            helpers['verify_inference_key'].assert_not_called()
            self.assertEqual(helpers['readiness_after_restart'].call_count, 2)
            self.assertEqual(helpers['readiness_after_restart'].call_args_list[0].args[0]['AI_EXTERNAL_PROCESSING_APPROVED'], 'false')
            self.assertEqual(helpers['readiness_after_restart'].call_args_list[1].args[0]['AI_EXTERNAL_PROCESSING_APPROVED'], 'true')
            self.assertEqual(stage.parse_environment(current[0])['TIMEWEB_AI_TOKEN'], SECRET)

    def test_failed_pause_verification_cannot_replace_prices_or_resume_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            current, support, helpers = self.runtime_fakes(directory)
            helpers['readiness_after_restart'].side_effect = RuntimeError('synthetic pause verification failure')
            with mock.patch.object(remote, 'STAGING', support), mock.patch.object(remote, 'ACTIVATION', helpers), \
                 mock.patch.object(remote.os, 'getuid', return_value=0):
                with self.assertRaisesRegex(RuntimeError, 'synthetic pause verification failure'):
                    remote.run({'payload': {**self.payload, 'action': 'renew_prices'}, 'secret': None})
            actual = stage.parse_environment(current[0])
            self.assertEqual(actual['AI_FAST_INPUT_RUB_PER_MILLION'], '55')
            self.assertEqual(actual['AI_EXTERNAL_PROCESSING_APPROVED'], 'false')
            self.assertNotIn(remote.REFRESH_MARKER, actual)


if __name__ == '__main__':
    unittest.main()
