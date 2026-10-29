"""Bounded probe verification; no provider connection and no real secrets."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).parents[1]))
import probe_supplied_owner55_ai as probe
import test_activate_owner55_ai as fixtures


class FakeAPI(fixtures.FakeAPI):
    def __init__(self):
        super().__init__()
        self.values = {'day':'100', 'month':'2900'}
    def request(self, method, path, body=None):
        result = super().request(method, path, body)
        if path == probe.provision.KEYS:
            result['ai_keys'][0]['name'] = probe.KEY_NAME
        return result


def completion():
    return {'model':probe.provision.MODEL, 'choices':[{'finish_reason':'stop',
        'message':{'content':'{"ok":true,"answer":4}'}}],
        'usage':{'prompt_tokens':40, 'completion_tokens':10, 'total_tokens':50}}


class FakeGateway:
    def __init__(self):
        self.calls = []
        self.value = completion()
    def request(self, path, body=None):
        self.calls.append((path, body))
        if path == '/models':
            return {'data':[{'id':probe.provision.MODEL}]}
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.api, self.gateway, self.report = FakeAPI(), FakeGateway(), {'generation_request_sent':False}
        patch = mock.patch.object(probe.provision, 'model_summary', return_value=dict(fixtures.REPORT))
        patch.start()
        self.addCleanup(patch.stop)
    def invoke(self):
        return probe.probe(self.api, self.gateway, self.report, now=fixtures.NOW)
    def test_success_only_one_bounded_request_no_cloud_writes_or_raw_response(self):
        result = self.invoke()
        self.assertEqual(result['status'], 'verified')
        self.assertEqual(result['estimated_cost_rub'], '0.003')
        self.assertEqual(len(self.gateway.calls), 2)
        body = self.gateway.calls[1][1]
        self.assertEqual(body['max_tokens'], 128)
        self.assertFalse(body['enable_thinking'])
        self.assertEqual(body['response_format'], {'type':'json_object'})
        self.assertTrue(all(row[0] == 'GET' for row in self.api.calls))
        self.assertNotIn('content', json.dumps(result))
    def test_unknown_outcome_is_not_retried(self):
        self.gateway.value = probe.ProbeError('gateway_network_outcome_unknown')
        with self.assertRaises(probe.ProbeError): self.invoke()
        self.assertTrue(self.report['generation_request_sent'])
        self.assertEqual(len(self.gateway.calls), 2)
    def test_limit_zero_or_excessive_rejects_before_any_inference(self):
        for period, value in [('day','0'), ('day','101'), ('month','3001')]:
            with self.subTest(period=period, value=value):
                self.api.values = {'day':'100', 'month':'2900', period:value}
                with self.assertRaises(probe.ProbeError): self.invoke()
                self.assertEqual(self.gateway.calls, [])
    def test_untrusted_content_and_usage_never_become_success(self):
        mutations = [lambda v:v.update(model='expensive-model'),
            lambda v:v['choices'][0].update(finish_reason='length'),
            lambda v:v['choices'][0]['message'].update(content='PRIVATE-UNTRUSTED'),
            lambda v:v['choices'][0]['message'].update(content='{"ok":true,"answer":5}'),
            lambda v:v['usage'].update(completion_tokens=10000),
            lambda v:v['usage'].update(prompt_tokens=True),
            lambda v:v['usage'].update(total_tokens=0)]
        for mutation in mutations:
            value = completion(); mutation(value)
            with self.subTest(value=value), self.assertRaises(probe.ProbeError):
                probe.validate_completion(value, {'input_rub_per_million':'60', 'output_rub_per_million':'60'}, 5000)
    def test_secret_whitespace_and_masked_value_rejected_without_normalizing(self):
        for value in ['hidden-by-api-key-policy', fixtures.SECRET+'\n', ' '+fixtures.SECRET]:
            with self.assertRaises(probe.ProbeError): probe.Gateway(value)
    def test_opaque_short_or_punctuated_key_is_validated_by_provider_not_guessed_locally(self):
        for value in ['synthetic:key', 'synthetic!key', 'short']:
            self.assertEqual(probe.Gateway(value).secret, value)
    def test_unique_owner_designated_key_required(self):
        with mock.patch.object(probe.provision, 'keys', return_value=[]):
            with self.assertRaisesRegex(probe.ProbeError, 'designated_key_not_unique'): self.invoke()
        self.assertEqual(self.gateway.calls, [])
    def test_http_rejection_discards_private_error_body(self):
        gateway = probe.Gateway(fixtures.SECRET)
        error = probe.urllib.error.HTTPError(probe.GATEWAY+'/chat/completions', 401,
                                            'PRIVATE-UNTRUSTED', {}, None)
        with mock.patch.object(gateway.opener, 'open', side_effect=error):
            with self.assertRaisesRegex(probe.ProbeError, '^gateway_authentication_rejected$'):
                gateway.request('/chat/completions', {})
    def test_unexpected_endpoint_is_blocked(self):
        gateway = probe.Gateway(fixtures.SECRET)
        with mock.patch.object(gateway.opener, 'open') as opened:
            with self.assertRaises(probe.ProbeError): gateway.request('/untrusted')
            opened.assert_not_called()
