import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('prepare_ai54',Path(__file__).resolve().parents[1]/'prepare_ai54.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class ActivationTests(unittest.TestCase):
    def fake(self, bad_limit=False, stopped=False):
        calls=[]
        def api(method,path,body=None):
            calls.append((method,path,body))
            if path.endswith('/models'): return {'models':[{'id':99,'model_name':m.MODEL,'is_stopped':stopped,'parameter_values':{'cost_in':'0.000014','cost_out':'0.000052'}}]}
            if method=='GET' and path.endswith('/ai-keys'): return {'ai_keys':[]}
            if method=='POST' and path.endswith('/ai-keys'): return {'ai_key':{'id':123},'key':'sk-synthetic-not-a-real-key'}
            if method=='GET': return {'ai_key_entity_limits':[{'limit_type':p,'money_limit':a,'model_id':None} for p,a in [('day','200' if bad_limit else '2'),('month','30')]]}
            return {}
        return calls,api
    def test_both_provider_budgets_before_any_inference(self):
        calls,api=self.fake();p=m.setup(api)
        self.assertEqual(p['daily_rub'],'2');self.assertEqual(p['monthly_rub'],'30')
        self.assertEqual(calls[2][2]['fallback_models'],[])
        self.assertEqual(len([c for c in calls if c[0]=='POST' and c[1].endswith('/entity-limits')]),2)
    def test_invalid_provider_limit_revokes_new_key(self):
        calls,api=self.fake(bad_limit=True)
        with self.assertRaises(ValueError):m.setup(api)
        self.assertEqual(calls[-1][:2],('DELETE','/api/v1/cloud-ai/ai-keys/123'))
    def test_stopped_model_creates_nothing(self):
        calls,api=self.fake(stopped=True)
        with self.assertRaises(ValueError):m.setup(api)
        self.assertTrue(all(c[0]=='GET' for c in calls))
    def test_key_cannot_inject_environment_lines(self):
        with self.assertRaises(ValueError):m.validate_key('synthetic\nAI_PROJECT_DAILY_RUB=100')
    def test_withheld_key_is_revoked_before_any_gateway_request(self):
        calls,api=self.fake()
        def withheld(method,path,body=None):
            result=api(method,path,body)
            if method=='POST' and path.endswith('/ai-keys'):
                result['key']='hidden-by-provider-policy'
            return result
        with self.assertRaises(ValueError):m.setup(withheld)
        self.assertEqual(calls[-1][:2],('DELETE','/api/v1/cloud-ai/ai-keys/123'))
        self.assertFalse(any(path.endswith('/entity-limits') for _,path,_ in calls))

    def test_price_increase_aborts(self):
        with self.assertRaises(ValueError):m.prices({'models':[{'model_name':m.MODEL,'parameter_values':{'cost_in':1,'cost_out':1}}]})


class ReadinessTests(unittest.TestCase):
    def test_waits_for_key_propagation_without_paid_requests(self):
        calls=[]
        def call(method,url,token):
            calls.append((method,url))
            if len(calls)<3: raise RuntimeError('ai_http_401:unspecified')
            return {'data':[{'id':m.MODEL}]}
        m.await_key_ready({'token':'synthetic-key'},call,lambda seconds:None)
        self.assertEqual(len(calls),3)
        self.assertTrue(all(method=='GET' for method,url in calls))
    def test_stops_on_non_authentication_failure(self):
        def call(*args): raise RuntimeError('ai_http_429:rate_limited')
        with self.assertRaisesRegex(RuntimeError,'429'):
            m.await_key_ready({'token':'synthetic-key'},call,lambda seconds:None)
    def test_never_substitutes_another_model(self):
        def call(*args):return {'data':[{'id':'expensive-other-model'}]}
        with self.assertRaisesRegex(ValueError,'model_not_accessible'):
            m.await_key_ready({'token':'synthetic-key'},call,lambda seconds:None)

if __name__=='__main__':unittest.main()
