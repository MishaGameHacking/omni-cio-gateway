"""Rotated-key synchronization with synthetic secrets and no network."""
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timedelta, timezone
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).parents[1]))
import sync_owner55_ai_key as sync
import test_activate_owner55_ai as fixtures
import test_adopt_supplied_owner55_ai as adoption

remote=fixtures.load_script('sync_key_remote_tests','deploy/sync_owner55_ai_key.py')
NEW='SYNTHETIC_NEW_GATEWAY_KEY_ONLY-1234567890'
OLD='SYNTHETIC_OLD_GATEWAY_KEY_ONLY-1234567890'
IDS={'day':fixtures.DAY,'month':fixtures.MONTH}
PRICING={'input_rub_per_million':'60','output_rub_per_million':'60',
         'valid_until':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()}


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.api=adoption.API()
        self.api.month_exists=True
        self.transfer=mock.Mock(return_value={'status':'synchronized'})

    def invoke(self,key_id=fixtures.KEY_ID):
        return sync.synchronize(self.api,self.transfer,{},NEW,key_id)

    def test_only_existing_identity_and_limits_are_read_before_private_delivery(self):
        result=self.invoke()
        self.assertTrue(result['provider_limits_unchanged'])
        self.assertTrue(all(call[0]=='GET' for call in self.api.calls))
        operation,payload,secret,contract=self.transfer.call_args.args
        self.assertEqual(secret,NEW)
        self.assertNotIn(NEW,operation)
        self.assertNotIn(NEW,str(payload)+str(result))
        self.assertEqual(payload['limit_ids'],IDS)
        self.assertEqual(contract['key_matches_supplied'],bool)

    def test_missing_monthly_limit_never_delivers_key_or_adds_limit(self):
        self.api.month_exists=False
        with self.assertRaisesRegex(RuntimeError,'both_existing_limits'): self.invoke()
        self.transfer.assert_not_called()
        self.assertTrue(all(call[0]=='GET' for call in self.api.calls))

    def test_unexpected_identity_and_stricter_budget_are_preserved(self):
        with self.assertRaises(RuntimeError): self.invoke(fixtures.DAY)
        self.transfer.assert_not_called()
        self.api.values['day']='10'
        with self.assertRaises(RuntimeError): self.invoke()
        self.transfer.assert_not_called()
        self.assertTrue(all(call[0]=='GET' for call in self.api.calls))

    def test_provider_change_after_delivery_is_not_reported_as_success(self):
        def delivered(*args):
            self.api.values['month']='10'
            return {'status':'synchronized'}
        self.transfer.side_effect=delivered
        with self.assertRaises(RuntimeError): self.invoke()
        self.assertEqual(self.transfer.call_count,1)

    def test_private_exceptions_and_credentials_never_reach_logs(self):
        out,err=io.StringIO(),io.StringIO()
        with mock.patch.object(sync,'require_admin_guard',side_effect=RuntimeError(NEW)), \
             redirect_stdout(out),redirect_stderr(err):
            with self.assertRaises(SystemExit): sync.main()
        self.assertNotIn(NEW,out.getvalue()+err.getvalue())
        self.assertIn('"status": "blocked"',out.getvalue())


class RemoteTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.original_settings=fixtures.stage.settings_for(
            {'key_id':fixtures.KEY_ID,'model':fixtures.stage.MODEL,'pricing':PRICING},OLD)
        self.original_settings.update(fixtures.remote.ENABLED)
        self.original_settings.update({
            'ANALYST_OWNER_AI_DAY_LIMIT_ID':fixtures.DAY,
            'ANALYST_OWNER_AI_MONTH_LIMIT_ID':fixtures.MONTH,
            'ANALYST_OWNER_BOOTSTRAP_SECRET':'SYNTHETIC_BOOTSTRAP_UNCHANGED',
            'BROKER_TOKEN':'SYNTHETIC_BROKER_UNCHANGED',
            'UNRELATED_SECRET':'SYNTHETIC_OTHER_UNCHANGED'})
        self.raw=fixtures.stage.replacement_environment(b'',self.original_settings)
        self.original=self.raw
        self.unset=''
        self.support={**fixtures.stage.__dict__,'LOCK':Path(folder.name)/'lock',
            'configuration_snapshot':lambda:(self.raw,None),
            'atomic_configuration':mock.Mock(side_effect=self.write),
            'verify_sources':mock.Mock()}
        self.active={'ENABLED':fixtures.remote.ENABLED,'PUBLIC':'https://unit.invalid',
            'verify_environment_file':mock.Mock(),'systemctl':mock.Mock(side_effect=self.systemctl),
            'verify_running_configuration':mock.Mock(),'readiness_after_restart':mock.Mock(),
            'public_feed_pid':mock.Mock(return_value='1234'),'read_get':mock.Mock(side_effect=self.read_get),
            'verify_inference_key':mock.Mock()}
        for target,value in [('STAGING',self.support),('ACTIVATION',self.active)]:
            patch=mock.patch.object(remote,target,value,create=True)
            patch.start();self.addCleanup(patch.stop)
        patch=mock.patch.object(remote.os,'getuid',return_value=0)
        patch.start();self.addCleanup(patch.stop)

    def write(self,raw,snapshot):
        self.assertEqual(snapshot[0],self.raw)
        self.raw=raw

    def systemctl(self,*args):
        if args[0]=='is-active': return 'active'
        if args[0]=='show': return self.unset
        return ''

    def read_get(self,url,**kwargs):
        if url.endswith('/health'): return {'status':'ok'}
        self.assertEqual(url,'https://unit.invalid/workspace/live?wait=0')
        self.assertEqual(kwargs,{'allowed_status':401})
        return {}

    def change(self,**settings):
        self.raw=fixtures.stage.replacement_environment(self.raw,settings)

    def invoke(self,secret=NEW,**payload):
        return remote.run({'payload':{'source_sha256':{},'key_id':fixtures.KEY_ID,
                                      'limit_ids':IDS,**payload},'secret':secret})

    def assert_no_write(self,receipt):
        self.assertEqual(receipt['status'],'blocked')
        self.support['atomic_configuration'].assert_not_called()
        self.assertFalse(any(call.args[0]=='restart' for call in self.active['systemctl'].call_args_list))

    def test_replaces_only_gateway_secret_and_checks_actual_process(self):
        receipt=self.invoke()
        self.assertEqual(receipt['status'],'synchronized')
        actual=fixtures.stage.parse_environment(self.raw)
        self.assertEqual(actual.pop('TIMEWEB_AI_TOKEN'),NEW)
        expected={k:v for k,v in self.original_settings.items() if k!='TIMEWEB_AI_TOKEN'}
        self.assertEqual(actual,expected)
        self.assertTrue(all(receipt[k] for k in remote.FIELDS))
        self.assertNotIn(NEW,str(receipt))
        self.active['verify_inference_key'].assert_called_once_with(NEW)
        self.active['readiness_after_restart'].assert_called_once()
        self.assertEqual(self.active['readiness_after_restart'].call_args.args[0]['TIMEWEB_AI_TOKEN'],NEW)

    def test_same_secret_is_read_only_without_restart(self):
        self.change(TIMEWEB_AI_TOKEN=NEW)
        receipt=self.invoke()
        self.assertEqual(receipt['status'],'already_current')
        self.assertFalse(receipt['configuration_changed'])
        self.support['atomic_configuration'].assert_not_called()
        self.active['readiness_after_restart'].assert_not_called()

    def test_invalid_secret_never_reaches_gateway(self):
        self.assert_no_write(self.invoke('wrong\nsecret'))
        self.active['verify_inference_key'].assert_not_called()

    def test_other_key_or_limit_identity_is_rejected(self):
        self.assert_no_write(self.invoke(key_id=fixtures.DAY))
        self.assert_no_write(self.invoke(limit_ids={'day':fixtures.MONTH,'month':fixtures.DAY}))

    def test_paused_or_custom_route_is_never_automatically_enabled(self):
        self.change(AI_EXTERNAL_PROCESSING_APPROVED='false')
        self.assert_no_write(self.invoke())
        self.change(AI_EXTERNAL_PROCESSING_APPROVED='true',AI_MODEL_STANDARD='other-model')
        self.assert_no_write(self.invoke())

    def test_expired_prices_require_separate_renewal(self):
        self.change(AI_FAST_PRICING_VALID_UNTIL='2000-01-01T00:00:00+00:00')
        self.assert_no_write(self.invoke())

    def test_gateway_rejection_preserves_current_secret(self):
        self.active['verify_inference_key'].side_effect=RuntimeError(NEW)
        self.assert_no_write(self.invoke())
        self.assertEqual(self.raw,self.original)

    def test_unset_gateway_variable_is_not_silently_overridden(self):
        self.unset='TIMEWEB_AI_TOKEN'
        self.assert_no_write(self.invoke())

    def test_deliberate_unrelated_exclusions_are_preserved(self):
        self.unset='UNRELATED_SECRET'
        receipt=self.invoke()
        self.assertEqual(receipt['status'],'synchronized')
        self.assertNotIn('UNRELATED_SECRET',self.active['readiness_after_restart'].call_args.args[0])
        self.assertIn('UNRELATED_SECRET',fixtures.stage.parse_environment(self.raw))

    def test_snapshot_race_blocks_write_and_restart(self):
        self.support['atomic_configuration'].side_effect=RuntimeError('concurrent_change')
        receipt=self.invoke()
        self.assertEqual(receipt['status'],'blocked')
        self.assertEqual(receipt['phase'],'write')
        self.assertFalse(receipt['service_restarted'])
        self.assertEqual(self.raw,self.original)

    def test_failed_process_readback_is_not_claimed_successful(self):
        self.active['readiness_after_restart'].side_effect=RuntimeError(NEW)
        receipt=self.invoke()
        self.assertEqual(receipt['status'],'blocked')
        self.assertTrue(receipt['configuration_changed'])
        self.assertFalse(receipt['configuration_loaded'])
        self.assertNotIn(NEW,str(receipt))

    def test_unrelated_config_change_after_restart_is_detected(self):
        self.active['readiness_after_restart'].side_effect=lambda *a:self.change(BROKER_TOKEN='changed')
        receipt=self.invoke()
        self.assertEqual(receipt['status'],'blocked')
        self.assertFalse(receipt['other_settings_preserved'])

    def test_source_mismatch_never_changes_config(self):
        self.support['verify_sources'].side_effect=RuntimeError('source_changed')
        self.assert_no_write(self.invoke())
        self.active['verify_inference_key'].assert_not_called()

    def test_public_feed_change_is_not_claimed_successful(self):
        self.active['public_feed_pid'].side_effect=['1234','5678']
        receipt=self.invoke()
        self.assertEqual(receipt['status'],'blocked')
        self.assertFalse(receipt['public_feed_unchanged'])
