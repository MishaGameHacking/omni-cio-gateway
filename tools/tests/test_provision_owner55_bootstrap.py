"""Owner-entry preparation uses synthetic values and cannot create a session."""
from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).parents[1]))
import provision_owner55_bootstrap as controller
import test_activate_owner55_ai as fixtures

remote = fixtures.load_script('owner_bootstrap_remote_test', 'deploy/provision_owner55_bootstrap.py')
SECRET = 'SYNTHETIC_OWNER_SETUP_ONLY_' + 'a' * 32
SOURCES = {name: '0' * 64 for name in controller.AUTH_SOURCES}


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.env = {'OWNER_BOOTSTRAP_EXPECTED_SOURCES': json.dumps(SOURCES)}

    def test_missing_key_is_read_only_private_inspection(self):
        transfer = mock.Mock(return_value={'status':'waiting_for_secret'})
        self.assertEqual(controller.execute(self.env, transfer)['status'], 'waiting_for_secret')
        self.assertIsNone(transfer.call_args.args[2])
        self.assertEqual(transfer.call_args.args[1], {'source_sha256':SOURCES})

    def test_protected_key_is_only_an_envelope_argument(self):
        transfer = mock.Mock(return_value={'status':'bootstrap_ready'})
        self.env[controller.BOOTSTRAP] = SECRET
        result = controller.execute(self.env, transfer)
        operation, payload, key, contract = transfer.call_args.args
        self.assertEqual(key, SECRET)
        self.assertNotIn(SECRET, operation)
        self.assertNotIn(SECRET, str(payload))
        self.assertNotIn(SECRET, str(result))
        self.assertEqual(contract['key_matches_supplied'], bool)

    def test_invalid_key_never_reaches_private_transport(self):
        for value in ('a' * 31, 'a' * 129, SECRET + '\n', SECRET + ' ', 'пароль' * 10):
            transfer = mock.Mock()
            self.env[controller.BOOTSTRAP] = value
            with self.subTest(length=len(value)):
                result = controller.execute(self.env, transfer)
                self.assertEqual(result['status'], 'blocked')
                self.assertNotIn(value, str(result))
                transfer.assert_not_called()

    def test_incomplete_auth_source_proof_is_rejected_before_transport(self):
        self.env['OWNER_BOOTSTRAP_EXPECTED_SOURCES'] = '{}'
        transfer = mock.Mock()
        with self.assertRaisesRegex(RuntimeError, 'bootstrap_source_proof_invalid'):
            controller.execute(self.env, transfer)
        transfer.assert_not_called()

    def test_private_error_text_does_not_escape_controller(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(controller, 'require_admin_guard'), \
             mock.patch.object(controller, 'execute', side_effect=RuntimeError(SECRET)), \
             redirect_stdout(stdout), redirect_stderr(stderr):
            with self.assertRaises(SystemExit): controller.main()
        self.assertNotIn(SECRET, stdout.getvalue() + stderr.getvalue())
        self.assertIn('private_bootstrap_preparation_failed', stdout.getvalue())

    def test_summary_distinguishes_waiting_from_ready_without_echoing_values(self):
        for status in controller.STATUSES:
            result=controller.summary({'status':status,'private':SECRET})
            self.assertNotIn(SECRET,result)
        self.assertIn('ключ пока не установлен',controller.summary({'status':'waiting_for_secret'}))
        self.assertIn('Ключ готов',controller.summary({'status':'bootstrap_ready'}))
        self.assertIn('пароль уже создан',controller.summary({'status':'already_configured'}))


class RemoteBootstrapTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.original = (b'ANALYST_OWNER_TELEGRAM_SUB=synthetic-owner\n'
            b'TIMEWEB_AI_TOKEN=synthetic-ai\nAI_USER_DAILY_RUB=95\n'
            b'BROKER_TOKEN=synthetic-broker\nUNRELATED_SECRET=synthetic-other\n')
        self.raw = self.original
        self.configured = False
        self.unset = ''
        self.settings = {'LOCK':Path(folder.name)/'lock',
            'configuration_snapshot':lambda:(self.raw,None),
            'parse_environment':fixtures.stage.parse_environment,
            'replacement_environment':fixtures.stage.replacement_environment,
            'atomic_configuration':mock.Mock(side_effect=self.write)}
        self.active = {'PUBLIC':'https://unit.invalid','verify_environment_file':mock.Mock(),
            'public_feed_pid':mock.Mock(return_value='1234'),
            'systemctl':mock.Mock(side_effect=self.systemctl),
            'read_get':mock.Mock(side_effect=self.read_get),
            'readiness_after_restart':mock.Mock()}
        for target, value in (('STAGING',self.settings),('ACTIVATION',self.active)):
            patch = mock.patch.object(remote,target,value,create=True)
            patch.start(); self.addCleanup(patch.stop)
        for target, kwargs in ((remote.os,{'attribute':'getuid','return_value':0}),
                               (remote,{'attribute':'verify_auth_sources','return_value':None})):
            attribute = kwargs.pop('attribute')
            patch = mock.patch.object(target,attribute,**kwargs)
            patch.start(); self.addCleanup(patch.stop)

    def systemctl(self, *arguments):
        if arguments[0] == 'is-active': return 'active'
        if arguments[0] == 'show': return self.unset
        return ''

    def read_get(self, url, **kwargs):
        if url.endswith('/health'): return {'status':'ok'}
        if '/workspace/' in url:
            self.assertEqual(kwargs,{'allowed_status':401})
            return {}
        self.assertTrue(url.endswith('/auth/owner/status'))
        return {'configured':self.configured,'method':'password',
            'setup_requires':'existing_owner_session_or_bootstrap',
            'min_password_length':10,'max_password_bytes':128}

    def write(self, raw, snapshot):
        self.assertEqual(snapshot[0], self.raw)
        self.raw = raw

    def invoke(self, secret=SECRET):
        return remote.run({'payload':{'source_sha256':SOURCES},'secret':secret})

    def test_absent_secret_only_reports_readiness_without_writes_or_restart(self):
        receipt = self.invoke(None)
        self.assertEqual(receipt['status'],'waiting_for_secret')
        self.assertFalse(receipt['bootstrap_configured'])
        self.assertTrue(receipt['health_verified'])
        self.settings['atomic_configuration'].assert_not_called()
        self.assertFalse(any(call.args[0]=='restart' for call in self.active['systemctl'].call_args_list))

    def test_existing_password_is_never_overwritten_or_reset(self):
        self.configured = True
        receipt = self.invoke()
        self.assertEqual(receipt['status'],'already_configured')
        self.settings['atomic_configuration'].assert_not_called()
        self.assertEqual(self.raw,self.original)

    def test_preparation_preserves_broker_ai_and_other_configuration(self):
        receipt = self.invoke()
        self.assertEqual(receipt['status'],'bootstrap_ready')
        parsed = fixtures.stage.parse_environment(self.raw)
        self.assertEqual(parsed.pop(remote.BOOTSTRAP),SECRET)
        self.assertEqual(parsed,fixtures.stage.parse_environment(self.original))
        self.assertTrue(receipt['bootstrap_loaded'])
        self.assertTrue(receipt['key_matches_supplied'])
        self.assertTrue(receipt['auth_boundary_verified'])
        self.assertNotIn(SECRET,str(receipt))
        self.assertTrue(all(call.args[0].startswith('https://unit.invalid/')
                            for call in self.active['read_get'].call_args_list))

    def test_existing_unused_bootstrap_can_be_replaced_before_password_creation(self):
        self.raw = fixtures.stage.replacement_environment(self.raw,{remote.BOOTSTRAP:'b'*40})
        receipt = self.invoke()
        self.assertEqual(receipt['status'],'bootstrap_ready')
        self.assertEqual(fixtures.stage.parse_environment(self.raw)[remote.BOOTSTRAP],SECRET)

    def test_invalid_bootstrap_is_not_written(self):
        receipt = self.invoke('a'*31)
        self.assertEqual(receipt['status'],'blocked')
        self.assertEqual(receipt['phase'],'bootstrap_validation')
        self.settings['atomic_configuration'].assert_not_called()

    def test_service_exclusion_of_bootstrap_blocks_before_write(self):
        self.unset = remote.BOOTSTRAP
        receipt = self.invoke()
        self.assertEqual(receipt['status'],'blocked')
        self.settings['atomic_configuration'].assert_not_called()

    def test_unrelated_service_exclusion_is_preserved(self):
        self.unset = 'UNRELATED_SECRET'
        receipt = self.invoke()
        self.assertEqual(receipt['status'],'bootstrap_ready')
        expected = self.active['readiness_after_restart'].call_args.args[0]
        self.assertNotIn('UNRELATED_SECRET',expected)
        self.assertEqual(expected[remote.BOOTSTRAP],SECRET)
        self.assertIn(b'UNRELATED_SECRET=synthetic-other\n',self.raw)

    def test_configuration_race_is_not_overwritten(self):
        self.settings['atomic_configuration'].side_effect = RuntimeError('configuration_changed_before_write')
        receipt = self.invoke()
        self.assertEqual(receipt['status'],'blocked')
        self.assertEqual(receipt['phase'],'configuration_write')
        self.assertFalse(receipt['service_restarted'])
        self.assertEqual(self.raw,self.original)

    def test_failed_process_verification_is_not_claimed_ready(self):
        self.active['readiness_after_restart'].side_effect = RuntimeError(SECRET)
        receipt = self.invoke()
        self.assertEqual(receipt['status'],'blocked')
        self.assertEqual(receipt['phase'],'runtime_verification')
        self.assertTrue(receipt['configuration_changed'])
        self.assertFalse(receipt['bootstrap_loaded'])
        self.assertNotIn(SECRET,str(receipt))

    def test_password_created_during_preparation_prevents_write(self):
        with mock.patch.object(remote,'password_configured',side_effect=[False,True]):
            receipt = self.invoke()
        self.assertEqual(receipt['status'],'blocked')
        self.settings['atomic_configuration'].assert_not_called()

    def test_source_failure_prevents_configuration_access(self):
        with mock.patch.object(remote,'verify_auth_sources',side_effect=RuntimeError('source_changed')):
            receipt = self.invoke()
        self.assertEqual(receipt['status'],'blocked')
        self.assertEqual(receipt['phase'],'source_verification')
        self.settings['atomic_configuration'].assert_not_called()

    def test_unknown_status_schema_prevents_preparation(self):
        self.active['read_get'].side_effect = lambda url,**kwargs: {'status':'ok'} if url.endswith('/health') else {}
        receipt = self.invoke()
        self.assertEqual(receipt['status'],'blocked')
        self.assertEqual(receipt['phase'],'owner_status')
        self.settings['atomic_configuration'].assert_not_called()
