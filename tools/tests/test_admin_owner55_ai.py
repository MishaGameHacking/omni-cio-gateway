"""Administrative dispatch only: all API/SSH access is synthetic or mocked."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

TOOLS = Path(__file__).parents[1]
sys.path.insert(0, str(TOOLS))
import admin_owner55_ai as admin

TOKEN = 'SYNTHETIC-CLOUD-CREDENTIAL-NOT-A-REAL-TOKEN'
KEY_ID = '2b8fa21b-4b04-4904-bd32-ef1181c5f811'
SOURCES = {name: 'a' * 64 for name in admin.SOURCE_NAMES}


def environment(action='preflight_only'):
    return {'TIMEWEB_CLOUD_TOKEN': TOKEN, 'GITHUB_RUN_ID': '40900000000',
        'OWNER_AI_ACTION': action,
        'OWNER_AI_PROVISION_REVIEW': (admin.provision.PREFLIGHT_ONLY_GATE
            if action == 'preflight_only' else admin.provision.PROVISION_GATE),
        'OWNER_AI_ACTIVATION_REVIEW': admin.activation.GATE,
        'OWNER_AI_EXPECTED_BUDGET_SOURCES': json.dumps(SOURCES),
        'OWNER_AI_STAGED_KEY_ID': KEY_ID, 'OWNER_AI_CREATION_RUN_ID': '40800000000'}


def ready_receipt():
    return {'status': 'ready', 'reason': 'ready', 'server_id': 9417611,
        'existing_key_absent': True, 'budget_sources_verified': True,
        'configuration_changed': False, 'read_only_preflight': True,
        'ai_key_created': False, 'ai_limits_changed': False, 'inference_called': False}


def staged_receipt():
    return {'status': 'staged_disabled', 'server_id': 9417611, 'key_id': KEY_ID,
        'model': 'dashscope/qwen3.5-flash', 'daily_cap_rub': '0', 'monthly_cap_rub': '0',
        'existing_key_replaced': False, 'service_restarted': False, 'inference_called': False,
        'provider_daily_limit_rub': '0', 'provider_30_day_limit_rub': '0',
        'provider_fallback_disabled': True, 'runtime_activation_performed': False,
        'account_currency_rub_confirmed': True}


def active_receipt():
    return {**admin.activation.activated_receipt(KEY_ID,
                {'valid_until': '2026-10-30T12:00:00+00:00'}),
        'provider_daily_limit_rub': '95', 'provider_30_day_limit_rub': '2900',
        'automatic_price_renewal_installed': False}


class ReadOnlyAPI:
    def __init__(self):
        self.calls = []

    def request(self, method, path, body=None):
        self.calls.append((method, path, body))
        if method == 'GET' and path == admin.provision.FINANCES:
            return {'finances': {'currency': 'RUB'}}
        if method == 'GET' and path == admin.provision.KEYS:
            return {'ai_keys': [], 'meta': {'total': 0}}
        raise AssertionError('Only expected read-only synthetic requests are permitted')


class AdminControllerTests(unittest.TestCase):
    def setUp(self):
        guard = mock.patch.object(admin, 'require_admin_guard')
        self.guard = guard.start()
        self.addCleanup(guard.stop)

    def test_host_guard_fails_before_api_or_transport(self):
        self.guard.side_effect = RuntimeError(TOKEN)
        with mock.patch.object(admin.provision, 'CloudAPI') as cloud, \
             mock.patch.object(admin.activation, 'ActivationAPI') as activation_api, \
             mock.patch.object(admin, 'transport_admin') as transfer:
            receipt, code = admin.run_administration(environment())
        self.assertEqual(code, 1)
        self.assertEqual(receipt['reason'], 'unexpected_administrative_failure')
        cloud.assert_not_called()
        activation_api.assert_not_called()
        transfer.assert_not_called()

    def test_read_only_mode_runs_inspection_without_provider_writes(self):
        api = ReadOnlyAPI()
        remote = {key: value for key, value in ready_receipt().items()
                  if key in admin.provision.PREFLIGHT_CONTRACT}
        with mock.patch.object(admin.provision, 'CloudAPI', return_value=api) as factory, \
             mock.patch.object(admin.provision, 'pricing', return_value={}), \
             mock.patch.object(admin, 'transport_admin', return_value=remote) as transfer, \
             mock.patch.object(admin.provision, 'provision') as create, \
             mock.patch.object(admin.activation, 'activate') as activate:
            receipt, code = admin.run_administration(environment())
        self.assertEqual((receipt, code), (ready_receipt(), 0))
        factory.assert_called_once_with(TOKEN)
        self.assertEqual([row[0] for row in api.calls], ['GET', 'GET'])
        self.assertEqual(transfer.call_args.args[1], {'action': 'preflight', 'source_sha256': SOURCES})
        self.assertIsNone(transfer.call_args.args[2])
        create.assert_not_called()
        activate.assert_not_called()

    def test_provision_dispatches_reviewed_function_and_private_transport(self):
        api = object()
        with mock.patch.object(admin.provision, 'CloudAPI', return_value=api) as factory, \
             mock.patch.object(admin.provision, 'provision', return_value=staged_receipt()) as create, \
             mock.patch.object(admin.provision, 'main') as wsl_main, \
             mock.patch.object(admin.activation, 'activate') as activate:
            receipt, code = admin.run_administration(environment('provision_disabled'))
        self.assertEqual((receipt, code), (staged_receipt(), 0))
        factory.assert_called_once_with(TOKEN)
        args = create.call_args.args
        self.assertIs(args[0], api)
        self.assertIs(args[1], admin.transport_admin)
        self.assertEqual(args[3:], (SOURCES, admin.provision.DEDICATED_PREFIX + '40900000000'))
        self.assertNotIn(TOKEN, args[2])
        wsl_main.assert_not_called()
        activate.assert_not_called()

    def test_activate_dispatches_existing_identity_without_wsl_entrypoint(self):
        api = object()
        with mock.patch.object(admin.activation, 'ActivationAPI', return_value=api) as factory, \
             mock.patch.object(admin.activation, 'operation_source', return_value='reviewed-activation'), \
             mock.patch.object(admin.activation, 'activate', return_value=active_receipt()) as activate, \
             mock.patch.object(admin.activation, 'main') as wsl_main, \
             mock.patch.object(admin.provision, 'provision') as create:
            receipt, code = admin.run_administration(environment('activate'))
        self.assertEqual((receipt, code), (active_receipt(), 0))
        factory.assert_called_once_with(TOKEN)
        activate.assert_called_once_with(api, admin.transport_admin, 'reviewed-activation',
                                        SOURCES, KEY_ID, '40800000000')
        create.assert_not_called()
        wsl_main.assert_not_called()

    def test_invalid_gate_source_or_whitespace_credential_never_reaches_api(self):
        cases = [('OWNER_AI_PROVISION_REVIEW', 'unreviewed'),
                 ('OWNER_AI_EXPECTED_BUDGET_SOURCES', '{}'),
                 ('TIMEWEB_CLOUD_TOKEN', ' ' + TOKEN + '\n')]
        for key, value in cases:
            with self.subTest(field=key):
                config = {**environment(), key: value}
                with mock.patch.object(admin.provision, 'CloudAPI') as factory:
                    receipt, code = admin.run_administration(config)
                self.assertEqual(code, 1)
                self.assertNotIn(TOKEN, json.dumps(receipt))
                factory.assert_not_called()

    def test_dependency_stdout_stderr_and_exception_text_are_discarded(self):
        def noisy_failure(_environment):
            print(TOKEN)
            print('private-provider-detail:' + TOKEN, file=sys.stderr)
            raise RuntimeError(TOKEN)
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(admin, 'execute', side_effect=noisy_failure), \
             redirect_stdout(stdout), redirect_stderr(stderr):
            receipt, code = admin.run_administration(environment())
        self.assertEqual(code, 1)
        self.assertEqual(stdout.getvalue() + stderr.getvalue(), '')
        self.assertEqual(receipt, {'status': 'not_activated', 'reason': 'unexpected_administrative_failure'})

    def test_uncertain_creation_and_private_cleanup_flags_are_preserved(self):
        failures = [
            admin.provision.ProvisionError('key_creation_requires_inspected_recovery', retained=None),
            admin.provision.ProvisionError('private_delivery_requires_inspected_recovery',
                key_id=KEY_ID, retained=True, failure_code='private_delivery_failed',
                transport_code='private_operation_timeout', transport_operation_started=True,
                temporary_ssh_key_removed=False),
        ]
        for error in failures:
            with self.subTest(reason=error.code), mock.patch.object(admin, 'execute', side_effect=error):
                receipt, code = admin.run_administration(environment('provision_disabled'))
            self.assertEqual(code, 1)
            self.assertEqual(receipt['reason'], error.code)
            self.assertIs(receipt['new_key_retained'], error.retained)
            self.assertEqual(receipt['new_key_id'], error.key_id)
            self.assertIs(receipt['transport_operation_started'], error.transport_operation_started)
            self.assertIs(receipt['temporary_ssh_key_removed'], error.temporary_ssh_key_removed)

    def test_transport_and_activation_failure_keep_safe_recovery_evidence(self):
        error = admin.PrivateTransportError('private_operation_timeout',
            operation_started=True, temporary_key_removed=False)
        with mock.patch.object(admin, 'execute', side_effect=error):
            receipt, code = admin.run_administration(environment())
        self.assertEqual(code, 1)
        self.assertEqual(receipt['transport_code'], 'private_operation_timeout')
        self.assertTrue(receipt['transport_operation_started'])
        self.assertFalse(receipt['temporary_ssh_key_removed'])
        failure = admin.activation.ActivationError('activation_requires_inspected_recovery', provider_blocked=False)
        with mock.patch.object(admin, 'execute', side_effect=failure):
            receipt, code = admin.run_administration(environment('activate'))
        self.assertEqual(code, 1)
        self.assertEqual(receipt['status'], 'activation_unconfirmed')
        self.assertIs(receipt['provider_zero_limits_verified'], False)

    def test_masked_and_invalid_gateway_failures_remain_distinct_finite_codes(self):
        for failure in ('new_gateway_key_masked', 'new_gateway_key_invalid'):
            error = admin.provision.ProvisionError('new_unused_key_removed_after_failure',
                key_id=KEY_ID, retained=False, failure_code=failure)
            with self.subTest(failure=failure), mock.patch.object(admin, 'execute', side_effect=error):
                receipt, code = admin.run_administration(environment('provision_disabled'))
            self.assertEqual(code, 1)
            self.assertEqual(receipt['failure_code'], failure)
            self.assertFalse(receipt['new_key_retained'])
            self.assertNotIn(TOKEN, json.dumps(receipt))

    def test_invalid_or_wrong_action_receipt_is_never_reported_as_success(self):
        invalid = [{**ready_receipt(), 'raw_detail': TOKEN},
                   {**ready_receipt(), 'reason': TOKEN},
                   {**ready_receipt(), 'ai_key_created': True}, staged_receipt()]
        for candidate in invalid:
            with self.subTest(fields=sorted(candidate)), \
                 mock.patch.object(admin, 'execute', return_value=candidate):
                receipt, code = admin.run_administration(environment())
            self.assertEqual(code, 1)
            self.assertEqual(receipt, {'status': 'not_activated',
                'reason': 'administrative_receipt_requires_inspection'})

    def test_main_prints_only_validated_receipt_and_removes_cloud_secret(self):
        stdout = io.StringIO()
        expected = ready_receipt()
        with mock.patch.dict(admin.os.environ, environment(), clear=True), \
             mock.patch.object(admin, 'run_administration', return_value=(expected, 0)), \
             redirect_stdout(stdout):
            with self.assertRaises(SystemExit) as stopped:
                admin.main()
            self.assertNotIn('TIMEWEB_CLOUD_TOKEN', admin.os.environ)
        self.assertEqual(stopped.exception.code, 0)
        self.assertEqual(json.loads(stdout.getvalue()), expected)
        self.assertNotIn(TOKEN, stdout.getvalue())


if __name__ == '__main__':
    unittest.main()
