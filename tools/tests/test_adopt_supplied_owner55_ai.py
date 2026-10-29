"""Existing-key adoption must preserve identity and existing usage periods."""
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).parents[1]))
import adopt_supplied_owner55_ai as adopt
import test_activate_owner55_ai as fixtures


class API(fixtures.FakeAPI):
    def __init__(self):
        super().__init__()
        self.values = {'day':'100', 'month':'2900'}
        self.month_exists = False
        self.lost_month = False
    def request(self, method, path, body=None):
        base = adopt.provision.KEYS+'/'+fixtures.KEY_ID+'/entity-limits'
        if method == 'POST' and path == base:
            self.calls.append((method,path,body))
            self.month_exists = True
            if self.lost_month: raise RuntimeError('synthetic unknown outcome')
            return {}
        result = super().request(method,path,body)
        if method == 'GET' and path == base and not self.month_exists:
            result['ai_key_entity_limits'] = result['ai_key_entity_limits'][:1]
            result['meta']['total'] = 1
        return result


class AdoptionTests(unittest.TestCase):
    def setUp(self):
        self.api, self.calls = API(), []
        self.fail_action = None
        patch = mock.patch.object(adopt.provision,'model_summary',return_value=dict(fixtures.REPORT))
        patch.start(); self.addCleanup(patch.stop)
    def transfer(self, operation, payload, secret, contract):
        action = payload['action']; self.calls.append((action,secret))
        if action == self.fail_action: raise RuntimeError('synthetic private failure')
        if action == 'preflight':
            return {'status':'ready','reason':'ready','server_id':9417611,'existing_key_absent':True,
                    'budget_sources_verified':True,'configuration_changed':False}
        if action == 'stage_disabled':
            self.assertEqual(secret, fixtures.SECRET)
            return {'status':'staged_disabled','server_id':9417611,'key_id':fixtures.KEY_ID,
                'model':adopt.provision.MODEL,'daily_cap_rub':'0','monthly_cap_rub':'0',
                'existing_key_replaced':False,'service_restarted':False,'inference_called':False}
        if action == 'preflight_activation':
            return {'status':'activation_ready','server_id':9417611,'key_id':fixtures.KEY_ID,
                'inference_key_authenticated':True,'model_present':True,'configuration_changed':False,
                'inference_probe_called':False}
        if action == 'activate':
            return adopt.activation.activated_receipt(fixtures.KEY_ID,payload['pricing'])
        raise AssertionError('Unexpected action')
    def invoke(self):
        return adopt.adopt(self.api,self.transfer,{},fixtures.SECRET,fixtures.KEY_ID)
    def test_adoption_adds_only_missing_month_never_changes_existing_day(self):
        receipt = self.invoke()
        self.assertEqual(receipt['status'],'activated')
        self.assertEqual(receipt['daily_cap_rub'],'95')
        self.assertEqual(receipt['provider_daily_limit_rub'],'100')
        self.assertFalse(receipt['existing_provider_limits_patched'])
        writes = [row for row in self.api.calls if row[0] != 'GET']
        self.assertEqual(len(writes),1)
        self.assertEqual(writes[0][0],'POST')
        self.assertTrue(writes[0][1].endswith('/entity-limits'))
        self.assertEqual([a for a,_ in self.calls],['preflight','stage_disabled','preflight_activation','activate'])
        self.assertEqual(sum(secret is not None for _,secret in self.calls),1)
    def test_existing_month_cap_is_not_reset(self):
        self.api.month_exists = True
        self.invoke()
        self.assertTrue(all(row[0]=='GET' for row in self.api.calls))
    def test_stricter_existing_budget_is_not_relaxed(self):
        self.api.values['day'] = '10'
        with self.assertRaisesRegex(adopt.AdoptionError,'individual_configuration'): self.invoke()
        self.assertEqual(self.calls,[])
        self.assertTrue(all(row[0]=='GET' for row in self.api.calls))
    def test_unknown_month_creation_does_not_retry_or_deliver_secret(self):
        self.api.lost_month = True
        with self.assertRaisesRegex(adopt.AdoptionError,'requires_readback'): self.invoke()
        self.assertEqual(sum(row[0]=='POST' for row in self.api.calls),1)
        self.assertEqual(self.calls,[('preflight',None)])
    def test_uncertain_activation_blocks_both_periods_without_deleting_key(self):
        self.fail_action = 'activate'
        with self.assertRaises(adopt.AdoptionError) as raised: self.invoke()
        self.assertTrue(raised.exception.blocked)
        self.assertEqual(self.api.values,{'day':'0','month':'0'})
        self.assertFalse(any(row[0]=='DELETE' for row in self.api.calls))
    def test_uuid_mismatch_stops_before_server_changes(self):
        with self.assertRaisesRegex(adopt.AdoptionError,'identity_changed'):
            adopt.adopt(self.api,self.transfer,{},fixtures.SECRET,fixtures.DAY)
        self.assertEqual(self.calls,[])
    def test_missing_uuid_stops_before_server_changes(self):
        with self.assertRaisesRegex(adopt.AdoptionError,'identity_required'):
            adopt.adopt(self.api,self.transfer,{},fixtures.SECRET,None)
        self.assertEqual(self.calls,[])
    def test_runtime_inspection_only_returns_fixed_booleans_and_no_secret(self):
        namespace={'__name__':'inspection_test'}
        exec(compile(adopt.RUNTIME_INSPECTION,'inspection','exec'),namespace)
        settings={**fixtures.stage.DISABLED,'TIMEWEB_AI_TOKEN':fixtures.SECRET,'ANALYST_OWNER_AI_KEY_ID':fixtures.KEY_ID}
        support={'verify_sources':mock.Mock(),'parse_environment':lambda raw:settings,
                 'configuration_snapshot':lambda:(b'',None),'DISABLED':fixtures.stage.DISABLED}
        active={'ENABLED':fixtures.remote.ENABLED,'PUBLIC':'https://unit.invalid',
                'systemctl':lambda *args:'active','verify_environment_file':mock.Mock(),
                'verify_running_configuration':mock.Mock(side_effect=RuntimeError('PRIVATE ERROR')),
                'read_get':lambda *args,**kwargs:{'status':'ok'},'verify_inference_key':mock.Mock()}
        namespace.update(STAGING=support,ACTIVATION=active)
        with mock.patch.object(namespace['os'],'getuid',return_value=0):
            result=namespace['run']({'payload':{'source_sha256':{},'key_id':fixtures.KEY_ID},'secret':fixtures.SECRET})
        self.assertEqual(result['configuration_state'],'staged_disabled')
        self.assertTrue(result['key_matches_supplied'])
        self.assertFalse(result['process_configuration_loaded'])
        self.assertEqual(result['last_failed_check'],'process_configuration_loaded')
        self.assertNotIn(fixtures.SECRET,str(result))
        self.assertNotIn('PRIVATE ERROR',str(result))
    def test_supplied_identity_does_not_depend_on_display_name(self):
        adopt.activation.owned_key(self.api,fixtures.KEY_ID,'owner-supplied')
        with self.assertRaises(adopt.activation.ActivationError):
            adopt.activation.owned_key(self.api,fixtures.DAY,'owner-supplied')
    def test_api_rejects_key_creation_regeneration_deletion(self):
        api = adopt.API(fixtures.SECRET)
        for method,path,body in [('POST',adopt.provision.KEYS,{}),
            ('DELETE',adopt.provision.KEYS+'/'+fixtures.KEY_ID,None),
            ('PUT',adopt.provision.KEYS+'/'+fixtures.KEY_ID+'/regenerate',{})]:
            with self.subTest(method=method), self.assertRaises((adopt.AdoptionError,adopt.activation.ActivationError)):
                api.request(method,path,body)
