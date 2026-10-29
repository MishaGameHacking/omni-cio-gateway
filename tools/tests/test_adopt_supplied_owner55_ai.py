"""Existing-key adoption must preserve identity and existing usage periods."""
from pathlib import Path
import tempfile
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


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.api = fixtures.FakeAPI()
        self.calls = []
        self.fail_resume = False
        self.current = {'configuration_state':'paused','key_matches_supplied':True,
            'key_identity_matches':True,'process_configuration_loaded':True,
            'health_verified':True,'auth_boundary_verified':True,'gateway_metadata_verified':True}
        patch = mock.patch.object(adopt,'inspect_runtime',side_effect=lambda *args:dict(self.current))
        patch.start(); self.addCleanup(patch.stop)

    def transfer(self, operation, payload, secret, contract):
        self.assertEqual(secret, fixtures.SECRET)
        self.calls.append(payload['action'])
        if payload['action'] == 'repair':
            self.assertEqual(self.api.values, {'day':'0','month':'0'})
            return {'status':'repaired','inference_called':False}
        self.assertEqual(payload['action'],'resume')
        self.assertEqual(self.api.values, {'day':'100','month':'2900'})
        if self.fail_resume: raise RuntimeError('synthetic private timeout')
        return {'status':'activated','inference_called':False}

    def invoke(self, resume=False):
        return adopt.recover(self.api,self.transfer,{},fixtures.KEY_ID,fixtures.SECRET,resume=resume)

    def test_repair_keeps_provider_blocked_and_never_resets_usage_limits(self):
        result = self.invoke()
        self.assertEqual(result['status'],'repaired')
        self.assertTrue(result['provider_zero_limits_verified'])
        self.assertTrue(all(row[0]=='GET' for row in self.api.calls))

    def test_unverified_paused_process_cannot_restore_provider_limits(self):
        self.current['process_configuration_loaded'] = False
        with self.assertRaisesRegex(adopt.AdoptionError,'paused_runtime_not_verified'):
            self.invoke(resume=True)
        self.assertEqual(self.calls,[])
        self.assertTrue(all(row[0]=='GET' for row in self.api.calls))

    def test_resume_restores_only_reviewed_caps_after_paused_proof(self):
        result = self.invoke(resume=True)
        writes = [row for row in self.api.calls if row[0]!='GET']
        self.assertEqual([row[2] for row in writes],[{'money_limit':100},{'money_limit':2900}])
        self.assertEqual(result['daily_cap_rub'],'95')
        self.assertEqual(result['monthly_cap_rub'],'2900')
        self.assertFalse(result['key_created'])
        self.assertEqual(self.calls,['resume'])

    def test_unknown_resume_outcome_blocks_both_periods_with_readback(self):
        self.fail_resume = True
        with self.assertRaises(adopt.AdoptionError) as raised: self.invoke(resume=True)
        self.assertTrue(raised.exception.blocked)
        self.assertEqual(self.api.values,{'day':'0','month':'0'})
        self.assertFalse(any(row[0] in {'POST','PUT','DELETE'} for row in self.api.calls))

    def test_partial_limit_restore_is_blocked_without_runtime_resume(self):
        self.api.fail_nonzero = 'month'
        with self.assertRaises(adopt.AdoptionError) as raised: self.invoke(resume=True)
        self.assertTrue(raised.exception.blocked)
        self.assertEqual(self.api.values,{'day':'0','month':'0'})
        self.assertEqual(self.calls,[])

    def test_identity_mismatch_prevents_any_write(self):
        self.api.key_id = fixtures.DAY
        with self.assertRaises(adopt.activation.ActivationError): self.invoke()
        self.assertTrue(all(row[0]=='GET' for row in self.api.calls))
        self.assertEqual(self.calls,[])


class RemoteRecoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.settings = {**fixtures.remote.ENABLED,'TIMEWEB_AI_TOKEN':fixtures.SECRET,
            'ANALYST_OWNER_AI_KEY_ID':fixtures.KEY_ID}
        self.raw = fixtures.stage.replacement_environment(b'UNRELATED_SECRET=synthetic-existing\n',self.settings)
        self.unset = ''
        self.namespace = {'__name__':'recovery_test'}
        exec(compile(adopt.RUNTIME_REPAIR,'recovery','exec'),self.namespace)
        self.support = {'LOCK':Path(temporary.name)/'test.lock','verify_sources':mock.Mock(),
            'configuration_snapshot':lambda:(self.raw,None),'parse_environment':fixtures.stage.parse_environment,
            'replacement_environment':fixtures.stage.replacement_environment,
            'atomic_configuration':mock.Mock(side_effect=self.write)}
        self.active = {'ENABLED':fixtures.remote.ENABLED,'verify_environment_file':mock.Mock(),
            'systemctl':mock.Mock(side_effect=lambda *args:self.unset if args[0]=='show' else ''),
            'public_feed_pid':mock.Mock(return_value='1234'),
            'verify_running_configuration':mock.Mock(),'readiness_after_restart':mock.Mock()}
        self.namespace.update(STAGING=self.support,ACTIVATION=self.active)

    def write(self, raw, expected):
        self.assertEqual(expected[0],self.raw)
        self.raw = raw

    def invoke(self, action='repair'):
        with mock.patch.object(self.namespace['os'],'getuid',return_value=0):
            return self.namespace['run']({'payload':{'action':action,'source_sha256':{},'key_id':fixtures.KEY_ID},
                'secret':fixtures.SECRET})

    def test_repair_pauses_paid_work_preserves_key_and_verifies_restarted_process(self):
        result = self.invoke()
        self.assertEqual(result['status'],'repaired')
        actual = fixtures.stage.parse_environment(self.raw)
        self.assertEqual(actual['AI_EXTERNAL_PROCESSING_APPROVED'],'false')
        self.assertEqual(actual['TIMEWEB_AI_TOKEN'],fixtures.SECRET)
        self.assertEqual(actual['UNRELATED_SECRET'],'synthetic-existing')
        self.assertTrue(result['process_configuration_loaded'])
        self.assertFalse(result['inference_called'])
        expected = self.active['readiness_after_restart'].call_args.args[0]
        self.assertEqual(expected['TIMEWEB_AI_TOKEN'],fixtures.SECRET)
        self.assertEqual(expected['AI_EXTERNAL_PROCESSING_APPROVED'],'false')
        self.assertNotIn(fixtures.SECRET,str(result))

    def test_unknown_unit_metadata_blocks_without_configuration_write(self):
        self.unset = 'UNRELATED TIMEWEB_AI_TOKEN'
        result = self.invoke()
        self.assertEqual(result['phase'],'unit_inspection')
        self.assertEqual(result['status'],'blocked')
        self.support['atomic_configuration'].assert_not_called()

    def test_resume_requires_existing_paused_state_before_write(self):
        result = self.invoke('resume')
        self.assertEqual(result['status'],'blocked')
        self.assertEqual(result['phase'],'paused_process')
        self.support['atomic_configuration'].assert_not_called()

    def test_successful_resume_verifies_paused_process_before_enabling(self):
        self.raw = fixtures.stage.replacement_environment(self.raw,{'AI_EXTERNAL_PROCESSING_APPROVED':'false'})
        result = self.invoke('resume')
        self.assertEqual(result['status'],'activated')
        self.active['verify_running_configuration'].assert_called_once()
        self.assertEqual(fixtures.stage.parse_environment(self.raw)['AI_EXTERNAL_PROCESSING_APPROVED'],'true')

    def test_failed_readiness_returns_sanitized_stage_and_no_success(self):
        self.active['readiness_after_restart'].side_effect=RuntimeError('PRIVATE '+fixtures.SECRET)
        result=self.invoke()
        self.assertEqual(result['status'],'blocked')
        self.assertEqual(result['phase'],'runtime_verification')
        self.assertTrue(result['configuration_changed'])
        self.assertFalse(result['process_configuration_loaded'])
        self.assertNotIn('PRIVATE',str(result))
        self.assertNotIn(fixtures.SECRET,str(result))

    def test_unit_patch_only_removes_target_and_preserves_other_restrictions(self):
        original=(b'[Service]\nNoNewPrivileges=true\nUnsetEnvironment=UNRELATED TIMEWEB_AI_TOKEN TIMEWEB_CLOUD_TOKEN\n'
                  b'Environment=UNCHANGED=value\n[Other]\nUnsetEnvironment=TIMEWEB_AI_TOKEN\n')
        desired,count=self.namespace['patch_unit'](original)
        self.assertEqual(count,1)
        self.assertEqual(desired,original.replace(b'UNRELATED TIMEWEB_AI_TOKEN TIMEWEB_CLOUD_TOKEN',
                                                  b'UNRELATED TIMEWEB_CLOUD_TOKEN'))

    def test_sole_key_directive_is_removed_without_resetting_earlier_restrictions(self):
        raw=b'[Service]\nUnsetEnvironment=UNRELATED\nUnsetEnvironment=TIMEWEB_AI_TOKEN\n'
        desired,count=self.namespace['patch_unit'](raw)
        self.assertEqual(desired,b'[Service]\nUnsetEnvironment=UNRELATED\n')
        self.assertEqual(count,1)

    def test_complex_unit_syntax_requires_separate_review(self):
        for raw in (b'[Service]\nUnsetEnvironment="TIMEWEB_AI_TOKEN"\n',
                    b'[Service]\nUnsetEnvironment=TIMEWEB_AI_TOKEN=bound-value\n'):
            with self.subTest(raw=raw), self.assertRaisesRegex(RuntimeError,'unsupported_unit_unset_syntax'):
                self.namespace['patch_unit'](raw)

    def test_unit_plan_refuses_concurrent_metadata_change_before_writes(self):
        self.namespace['unset_names']=mock.Mock(return_value={'UNRELATED'})
        self.namespace['write_unit']=mock.Mock()
        with self.assertRaisesRegex(RuntimeError,'unit_changed_before_write'):
            self.namespace['apply_unit_plan']([],{'TIMEWEB_AI_TOKEN','UNRELATED'})
        self.namespace['write_unit'].assert_not_called()

    def test_unit_apply_requires_exact_remaining_restrictions_after_reload(self):
        self.namespace['unset_names']=mock.Mock(side_effect=[{'TIMEWEB_AI_TOKEN','UNRELATED'},set()])
        self.namespace['unit_snapshot']=mock.Mock(return_value=(b'original','identity'))
        self.namespace['write_unit']=mock.Mock()
        with self.assertRaisesRegex(RuntimeError,'unit_unset_change_not_verified'):
            self.namespace['apply_unit_plan']([(Path('/unit'),(b'original','identity'),b'desired')],
                                             {'TIMEWEB_AI_TOKEN','UNRELATED'})
        self.active['systemctl'].assert_called_once_with('daemon-reload')
