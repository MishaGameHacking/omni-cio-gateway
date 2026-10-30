from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

import httpx

from backend.ai_budget import MoneyLedger, BudgetDenied, micro_rub, token_cost
from backend.ai_jobs import AnalysisQueue, LeaseLost, CURRENT_JOB, drain
from backend.ai_guarded_client import GuardedAIClient, GuardError, validated_url
from backend.tests.ai_broker_fixtures import bind_synthetic_broker

FAST = SimpleNamespace(value='fast')
NOW = 1791882000


class DatabaseCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'test.sqlite'
        self.ledger = MoneyLedger(self.connect)
        self.ledger.initialize()
        self.queue = AnalysisQueue(self.connect)
        self.queue.initialize()

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def tearDown(self):
        self.temp.cleanup()

    def reserve(self, key='test', user=1, ceiling=1_000_000, cap=10_000_000, project=20_000_000, at=NOW, route=None):
        self.ledger.reserve(user_id=user, key=key, route=route or key, model='test-model',
                            ceiling=ceiling, user_cap=cap, project_cap=project, at=at)


class BudgetTests(DatabaseCase):
    def test_decimal_and_rounding(self):
        self.assertEqual(micro_rub('0.0000001'), 1)
        self.assertEqual(micro_rub('0.1'), 100000)
        self.assertEqual(token_cost(1, 1, 1000001, 2000001), 4)

    def test_invalid_money_rejected(self):
        for value in ('NaN','Infinity','-1','not-a-number','1000001'):
            with self.subTest(value=value), self.assertRaises(BudgetDenied):
                micro_rub(value)

    def test_zero_disables_paid_calls(self):
        with self.assertRaises(BudgetDenied):
            self.reserve(cap=0)

    def test_fractional_usage_rejected(self):
        with self.assertRaises(BudgetDenied):
            token_cost(0.1, 1, 1, 1)

    def test_user_limit_includes_reservations(self):
        self.reserve('a', cap=1000000)
        with self.assertRaisesRegex(BudgetDenied, 'user_budget'):
            self.reserve('b', cap=1000000)

    def test_global_limit_is_atomic_across_connections(self):
        def attempt(index):
            try:
                self.reserve(str(index), user=index+1, project=3_000_000)
                return True
            except BudgetDenied:
                return False
        with ThreadPoolExecutor(max_workers=8) as executor:
            result = list(executor.map(attempt, range(20)))
        self.assertEqual(sum(result), 3)

    def test_duplicate_not_charged_twice(self):
        self.reserve()
        with self.assertRaises(BudgetDenied):
            self.reserve()
        self.assertEqual(self.ledger.user_summary(1, at=NOW)['estimated_and_reserved_rub'], '1')

    def test_timeout_hold_survives_midnight(self):
        self.reserve()
        self.ledger.uncertain('test')
        summary = self.ledger.user_summary(1, at=NOW + 86400)
        self.assertEqual(summary['estimated_and_reserved_rub'], '1')
        self.assertEqual(summary['unresolved_attempts'], 1)

    def test_settle_releases_only_unused_reservation(self):
        self.reserve()
        self.assertTrue(self.ledger.settle('test', model='test-model', cost=125000, input_tokens=10, output_tokens=5))
        self.assertEqual(self.ledger.user_summary(1, at=NOW)['estimated_and_reserved_rub'], '0.125')
        self.assertEqual(self.ledger.user_summary(1, at=NOW+86400)['estimated_and_reserved_rub'], '0')

    def test_late_duplicate_cannot_modify_settled_cost(self):
        self.reserve()
        self.ledger.settle('test', model='test-model', cost=100, input_tokens=1, output_tokens=1)
        self.assertFalse(self.ledger.settle('test', model='test-model', cost=1, input_tokens=1, output_tokens=1))
        self.ledger.uncertain('test')
        self.assertEqual(self.ledger.user_summary(1, at=NOW)['estimated_and_reserved_rub'], '0.0001')

    def test_model_drift_pauses_paid_work(self):
        self.reserve()
        self.assertFalse(self.ledger.settle('test', model='different', cost=100, input_tokens=1, output_tokens=1))
        with self.assertRaisesRegex(BudgetDenied, 'reconciliation'):
            self.reserve('next')

    def test_overrun_is_recorded_not_hidden(self):
        self.reserve()
        self.assertFalse(self.ledger.settle('test', model='test-model', cost=2_000_000, input_tokens=1, output_tokens=1))
        summary = self.ledger.user_summary(1, at=NOW)
        self.assertEqual(summary['estimated_and_reserved_rub'], '2')
        self.assertTrue(summary['paid_calls_paused'])

    def test_status_does_not_include_other_users(self):
        self.reserve('one', user=1)
        self.reserve('two', user=2)
        self.assertEqual(self.ledger.user_summary(3, at=NOW)['estimated_and_reserved_rub'], '0')

    def test_route_serialization_and_cooldown(self):
        self.reserve('one', route='same')
        with self.assertRaisesRegex(BudgetDenied, 'in_flight'):
            self.reserve('two', user=2, route='same')
        self.ledger.uncertain('one')
        self.ledger.cool_down('same', at=NOW)
        with self.assertRaisesRegex(BudgetDenied, 'cooling_down'):
            self.reserve('three', route='same', at=NOW+299)
        self.reserve('four', route='same', at=NOW+301)


class QueueTests(DatabaseCase):
    def test_enqueue_coalesces_manual_and_scheduled(self):
        first = self.queue.enqueue(1, at=NOW)
        second = self.queue.enqueue(1, at=NOW+600)
        self.assertEqual(first['job_id'], second['job_id'])
        self.assertTrue(second['coalesced'])

    def test_atomic_claim_has_one_owner(self):
        self.queue.enqueue(1, at=NOW)
        with ThreadPoolExecutor(max_workers=8) as executor:
            jobs = list(executor.map(lambda _: self.queue.claim(at=NOW), range(12)))
        self.assertEqual(sum(job is not None for job in jobs), 1)

    def test_restart_keeps_queued_work(self):
        expected = self.queue.enqueue(1, at=NOW)['job_id']
        fresh = AnalysisQueue(self.connect)
        fresh.initialize()
        self.assertEqual(fresh.claim(at=NOW)['id'], expected)

    def test_stale_owner_cannot_commit(self):
        self.queue.enqueue(1, at=NOW)
        job = self.queue.claim(at=NOW)
        with self.assertRaises(LeaseLost):
            self.queue.finish(job, {'state':'completed'}, at=NOW+901)
        status = self.queue.user_status(1, at=NOW+901)
        self.assertEqual(status['state'], 'uncertain')

    def test_uncertain_does_not_stop_deterministic_collection(self):
        self.queue.enqueue(1, at=NOW)
        self.queue.claim(at=NOW)
        newer = self.queue.enqueue(1, at=NOW+1000)
        self.assertEqual(newer['state'], 'queued')
        self.assertTrue(self.queue.has_uncertain(1))

    def test_read_only_failure_retries_at_bounded_delays(self):
        self.queue.enqueue(1, at=NOW)
        for attempt, delay in ((1,60),(2,120),(3,240)):
            job = self.queue.claim(at=NOW + (0 if attempt==1 else 600*(attempt-1)))
            self.assertEqual(job['attempts'], attempt)
            now = NOW+600*(attempt-1)
            self.queue.fail(job, retryable=True, at=now)
            status = self.queue.user_status(1, at=now)
            self.assertEqual(status['due_at'], now+delay)
        self.assertEqual(status['state'], 'failed')

    def test_completion_is_not_replayed_in_same_bucket(self):
        self.queue.enqueue(1, at=NOW)
        job = self.queue.claim(at=NOW)
        self.queue.finish(job, {'state':'completed','token':'DO-NOT-STORE'}, at=NOW+1)
        self.assertTrue(self.queue.enqueue(1, at=NOW+1)['coalesced'])
        with closing(self.connect()) as db:
            payload = db.execute('SELECT result_json FROM ai_work_jobs').fetchone()[0]
        self.assertNotIn('DO-NOT-STORE', payload)

    def test_drain_establishes_and_clears_context(self):
        self.queue.enqueue(1)
        def run(user):
            self.assertEqual(user, 1)
            self.assertIsNotNone(CURRENT_JOB.get())
            return {'state':'skipped'}
        self.assertEqual(drain(self.queue, run)['processed'], 1)
        self.assertIsNone(CURRENT_JOB.get())

    def test_terminal_error_is_not_retried(self):
        self.queue.enqueue(1)
        run = Mock(side_effect=ValueError('must-not-be-logged'))
        self.assertEqual(drain(self.queue, run)['failed'], 1)
        self.assertEqual(self.queue.user_status(1)['state'], 'failed')
        self.assertNotIn('must-not-be-logged', str(self.queue.user_status(1)))


def environment():
    return {'AI_TRANSPORT':'gateway','TIMEWEB_AI_TOKEN':'SYNTHETIC-KEY','AI_MODEL_FAST':'test-model',
            'AI_EXTERNAL_PROCESSING_APPROVED':'true','AI_ALLOWED_PROCESSING_REGIONS':'RU',
            'AI_FAST_PROCESSING_REGION':'RU','AI_FAST_PRICING_MODEL':'test-model',
            'AI_FAST_PRICING_VALID_UNTIL':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat(),
            'AI_FAST_INPUT_RUB_PER_MILLION':'20','AI_FAST_OUTPUT_RUB_PER_MILLION':'40',
            'AI_FAST_TOKEN_PARAMETER':'max_tokens','AI_USER_DAILY_RUB':'5','AI_PROJECT_DAILY_RUB':'10'}


def model_response(**changes):
    value = {'model':'test-model', 'usage':{'prompt_tokens':10,'completion_tokens':10,'total_tokens':20},
             'choices':[{'finish_reason':'stop','message':{'content':'{"ok":true}'}}]}
    value.update(changes)
    return value


class GuardedClientTests(DatabaseCase):
    def setUp(self):
        super().setUp()
        bind_synthetic_broker(self.connect)
        self.env = environment()
        self.requests = []

    def client(self, response=None, status=200):
        def handle(request):
            self.requests.append(request)
            return httpx.Response(status, json=model_response() if response is None else response,
                                  headers={'Location':'https://example.invalid/steal'})
        return GuardedAIClient(1, self.connect, transport=httpx.MockTransport(handle), env=self.env)

    def run_call(self, client):
        return client.complete_json(tier=FAST, messages=[{'role':'user','content':'synthetic'}], max_output_tokens=100)

    def test_qwen_flash_disables_reasoning_and_accounts_json_response(self):
        self.env.update(AI_MODEL_FAST='dashscope/qwen3.5-flash', AI_FAST_PRICING_MODEL='dashscope/qwen3.5-flash',
                        AI_FAST_PROCESSING_REGION='EXTERNAL', AI_ALLOWED_PROCESSING_REGIONS='EXTERNAL')
        self.run_call(self.client(model_response(model='dashscope/qwen3.5-flash')))
        body = json.loads(self.requests[0].content)
        self.assertIs(body['enable_thinking'], False)
        self.assertEqual(body['response_format'], {'type':'json_object'})
        self.assertEqual(body['max_tokens'], 100)
        self.assertEqual(self.ledger.user_summary(1)['unresolved_attempts'], 0)

    def test_external_processing_requires_explicit_region_approval(self):
        self.env['AI_FAST_PROCESSING_REGION'] = 'EXTERNAL'
        client = self.client()
        with self.assertRaisesRegex(GuardError, 'ai_processing_region_not_approved'):
            self.run_call(client)
        self.assertEqual(len(self.requests), 0)

    def test_gateway_request_is_accounted(self):
        result = self.run_call(self.client())
        self.assertEqual(result.data, {'ok':True})
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(self.requests[0].headers['Authorization'], 'Bearer SYNTHETIC-KEY')
        summary = self.ledger.user_summary(1)
        self.assertEqual(summary['unresolved_attempts'], 0)
        self.assertEqual(summary['estimated_and_reserved_rub'], '0.0006')

    def test_agents_have_per_tier_credentials_and_no_ignored_model_switch(self):
        self.env.update({'AI_TRANSPORT':'agents','TIMEWEB_AI_FAST_BASE_URL':'https://agent.timeweb.cloud/api/v1/cloud-ai/agents/abc-123/v1',
                         'TIMEWEB_AI_FAST_TOKEN':'SYNTHETIC-FAST'})
        self.run_call(self.client())
        request = self.requests[0]
        self.assertEqual(request.headers['Authorization'], 'Bearer SYNTHETIC-FAST')
        self.assertNotIn('model', json.loads(request.content))

    def test_missing_agent_key_does_not_fall_back_to_global_key(self):
        self.env.update({'AI_TRANSPORT':'agents','TIMEWEB_AI_FAST_BASE_URL':'https://agent.timeweb.cloud/api/v1/cloud-ai/agents/abc/v1'})
        client = self.client()
        with self.assertRaises(GuardError):
            self.run_call(client)
        self.assertEqual(self.requests, [])

    def test_admin_token_is_never_used_for_inference(self):
        self.env.pop('TIMEWEB_AI_TOKEN')
        self.env['TIMEWEB_CLOUD_TOKEN']='MUST-NOT-LEAVE'
        self.env['TIMEWEB_CLOUD_API_KEY']='MUST-NOT-LEAVE'
        client = self.client()
        with self.assertRaises(GuardError):
            self.run_call(client)
        self.assertEqual(self.requests, [])

    def test_approval_required_before_any_spend(self):
        self.env.pop('AI_EXTERNAL_PROCESSING_APPROVED')
        client = self.client()
        with self.assertRaises(GuardError):
            self.run_call(client)
        self.assertEqual(self.requests, [])
        self.assertEqual(self.ledger.user_summary(1)['unresolved_attempts'], 0)

    def test_region_mismatch_is_rejected(self):
        self.env['AI_FAST_PROCESSING_REGION']='US'
        client = self.client()
        with self.assertRaises(GuardError):
            self.run_call(client)
        self.assertEqual(self.requests, [])

    def test_prices_bound_to_model(self):
        self.env['AI_MODEL_FAST']='new-model'
        client = self.client()
        with self.assertRaises(GuardError):
            self.run_call(client)
        self.assertEqual(self.requests, [])

    def test_expired_prices_do_not_allow_a_free_estimate(self):
        self.env['AI_FAST_PRICING_VALID_UNTIL']='2020-01-01T00:00:00Z'
        client = self.client()
        with self.assertRaises(GuardError):
            self.run_call(client)
        self.assertEqual(self.requests, [])

    def test_zero_ruble_budget_is_not_unlimited(self):
        self.env['AI_USER_DAILY_RUB']='0'
        client = self.client()
        with self.assertRaises(GuardError):
            self.run_call(client)
        self.assertEqual(self.requests, [])

    def test_missing_usage_keeps_full_reservation(self):
        client = self.client(model_response(usage=None))
        with self.assertRaises(GuardError):
            self.run_call(client)
        self.assertEqual(self.ledger.user_summary(1)['unresolved_attempts'], 1)
        self.assertEqual(len(self.requests), 1)

    def test_bad_output_is_still_charged(self):
        bad = model_response(choices=[{'finish_reason':'stop','message':{'content':'not JSON'}}])
        client = self.client(bad)
        with self.assertRaises(GuardError):
            self.run_call(client)
        self.assertEqual(self.ledger.user_summary(1)['estimated_and_reserved_rub'], '0.0006')

    def test_model_mismatch_halts_further_paid_attempts(self):
        client = self.client(model_response(model='unexpected'))
        with self.assertRaises(GuardError):
            self.run_call(client)
        self.assertTrue(self.ledger.user_summary(1)['paid_calls_paused'])

    def test_redirect_is_not_followed(self):
        client = self.client(status=302)
        with self.assertRaises(GuardError):
            self.run_call(client)
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(self.ledger.user_summary(1)['unresolved_attempts'], 1)

    def test_timeout_has_no_free_retry(self):
        client = GuardedAIClient(1, self.connect, env=self.env,
            transport=httpx.MockTransport(lambda r: (_ for _ in ()).throw(httpx.ReadTimeout('test'))))
        with self.assertRaises(GuardError): self.run_call(client)
        self.assertEqual(self.ledger.user_summary(1)['unresolved_attempts'], 1)

    def test_incomplete_output_not_delivered(self):
        bad = model_response(choices=[{'finish_reason':'length','message':{'content':'{"ok":true}'}}])
        client = self.client(bad)
        with self.assertRaises(GuardError):
            self.run_call(client)
        self.assertEqual(self.ledger.user_summary(1)['estimated_and_reserved_rub'], '0.0006')

    def test_endpoint_allowlist_rejects_insecure_variants(self):
        for url in ('http://api.timeweb.ai/v1','https://api.timeweb.ai.evil/v1','https://api.timeweb.ai:443/v1',
                    'https://key@api.timeweb.ai/v1','https://api.timeweb.ai/v1?secret=yes',
                    'https://localhost/v1','https://agent.timeweb.cloud/api/v1/cloud-ai/agents/../v1'):
            with self.subTest(url=url), self.assertRaises(GuardError): validated_url(url, 'gateway')

    def test_uncertain_worker_stops_paid_calls_but_not_new_collection(self):
        now = int(time.time())
        self.queue.enqueue(1, at=now-1000)
        self.queue.claim(at=now-1000)
        self.queue.enqueue(1, at=now)
        job = self.queue.claim(at=now)
        context = CURRENT_JOB.set((job['id'],job['owner']))
        try:
            client = self.client()
            with self.assertRaisesRegex(GuardError, 'reconciliation'):
                self.run_call(client)
        finally:
            CURRENT_JOB.reset(context)
        self.assertEqual(self.requests, [])


if __name__ == '__main__':
    unittest.main()


