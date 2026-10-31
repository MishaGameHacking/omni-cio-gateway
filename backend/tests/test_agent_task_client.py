"""Real SQLite/jobs/ledger, synthetic local and HTTP transports; no live services."""
from contextlib import closing
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

import httpx

from backend.agent_runtime_policy import Availability, TaskKind, TaskRequest
from backend.agent_task_client import AgentTaskClient, TaskContext
from backend.ai_budget import MoneyLedger, SCALE
from backend.ai_guarded_client import GuardError, IncompleteModelResponse
from backend.ai_jobs import AnalysisQueue, CURRENT_JOB, LeaseLost, drain
from backend.ai_policy import AnalysisTier
from backend import local_ai_transport as local
from backend.tests.ai_broker_fixtures import bind_synthetic_broker


class AgentTaskClientTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.database = Path(temp.name) / 'synthetic-agent.db'
        self.ledger = MoneyLedger(self.connect)
        self.ledger.initialize()
        bind_synthetic_broker(self.connect)
        self.queue = AnalysisQueue(self.connect)
        self.queue.initialize()
        self.queue.enqueue(1)
        self.job = self.queue.claim()
        token = CURRENT_JOB.set((self.job['id'], self.job['owner']))
        self.addCleanup(CURRENT_JOB.reset, token)
        expires = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        self.env = {
            'AGENT_CLOUD_ENABLED': 'true', 'AI_TRANSPORT': 'local',
            'LOCAL_AI_ENABLED': 'true', 'AI_EXTERNAL_PROCESSING_APPROVED': 'true',
            'AI_FAST_PROCESSING_REGION': 'RU', 'TIMEWEB_AI_TOKEN': 'synthetic-test-token',
            'AI_MODEL_FAST': 'synthetic-agent-model', 'AI_FAST_PRICING_MODEL': 'synthetic-agent-model',
            'AI_FAST_PRICING_VALID_UNTIL': expires, 'AI_FAST_INPUT_RUB_PER_MILLION': '100',
            'AI_FAST_OUTPUT_RUB_PER_MILLION': '200', 'AI_FAST_INPUT_TOKEN_ALLOWANCE': '0',
            'AI_FAST_TOKEN_PARAMETER': 'max_tokens', 'AI_USER_DAILY_RUB': '95',
            'AI_PROJECT_DAILY_RUB': '95', 'AI_USER_MONTHLY_RUB': '2900',
            'AI_PROJECT_MONTHLY_RUB': '2900',
        }
        self.context = TaskContext(TaskRequest(TaskKind.CONVERSATION), Availability(True, False, True, True))
        self.messages = [{'role': 'user', 'content': 'Synthetic greeting.'}]
        self.requests = []
        self.local_calls = []
        for patcher in (
            patch.object(local, 'ensure_ready', return_value=None),
            patch.object(local, 'complete', side_effect=self.respond_local),
            patch('socket.create_connection', side_effect=AssertionError('Network forbidden in this suite')),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def connect(self):
        db = sqlite3.connect(self.database, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def response(self, model):
        return {'model': model, 'usage': {'prompt_tokens': 8, 'completion_tokens': 2, 'total_tokens': 10},
                'choices': [{'finish_reason': 'stop', 'message': {'content': '{"answer":"synthetic"}'}}]}

    def respond_local(self, messages, max_output_tokens):
        self.local_calls.append(messages)
        return json.dumps(self.response(local.MODEL_ID)).encode()

    def respond_cloud(self, request):
        self.requests.append(request)
        return httpx.Response(200, json=self.response('synthetic-agent-model'))

    def client(self, **kwargs):
        kwargs.setdefault('transport', httpx.MockTransport(self.respond_cloud))
        return AgentTaskClient(1, self.connect, context_provider=lambda: self.context,
                               environment_provider=lambda: self.env, **kwargs)

    def invoke(self, client=None):
        return (client or self.client()).complete_json(tier=AnalysisTier.FAST,
                                                     messages=self.messages, max_output_tokens=50)

    def cloud(self):
        self.context = replace(self.context, request=replace(self.context.request,
                               requires_cloud=True, cloud_data_approved=True))

    def rows(self):
        with closing(self.connect()) as db:
            return [dict(row) for row in db.execute('SELECT * FROM ai_money_reservations')]

    def prepare_next_job(self):
        CURRENT_JOB.set(None)
        self.queue.finish(self.job, {'state': 'synthetic-done'})
        with closing(self.connect()) as db, db:
            db.execute('UPDATE ai_work_jobs SET bucket=bucket-1 WHERE id=?', (self.job['id'],))
        self.queue.enqueue(1)

    def test_local_uses_existing_adapter_without_paid_reservation(self):
        result = self.invoke()
        self.assertEqual(result.model, local.MODEL_ID)
        self.assertEqual(len(self.local_calls), 1)
        self.assertEqual((self.requests, self.rows()), ([], []))

    def test_local_does_not_need_cloud_key_or_cloud_budget(self):
        self.env = {'AI_TRANSPORT': 'local', 'LOCAL_AI_ENABLED': 'true'}
        self.assertEqual(self.invoke().data, {'answer': 'synthetic'})
        self.assertFalse(self.requests)

    def test_cloud_from_local_default_settles_existing_ledger(self):
        self.cloud()
        before, process_before = dict(self.env), dict(os.environ)
        result = self.invoke()
        self.assertEqual(result.model, 'synthetic-agent-model')
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(str(self.requests[0].url), 'https://api.timeweb.ai/v1/chat/completions')
        self.assertFalse(self.local_calls)
        self.assertEqual(self.env, before)
        self.assertEqual(dict(os.environ), process_before)
        self.assertEqual((self.rows()[0]['state'], self.rows()[0]['charge']), ('settled', 1200))

    def test_cloud_reservation_exists_before_transport(self):
        self.cloud()
        def respond(request):
            self.assertEqual(self.rows()[0]['state'], 'reserved')
            return self.respond_cloud(request)
        self.invoke(self.client(transport=httpx.MockTransport(respond)))

    def test_envelope_is_passed_to_atomic_ledger(self):
        self.cloud()
        original = MoneyLedger.reserve
        calls = []
        def reserve(ledger, **kwargs):
            calls.append(kwargs)
            return original(ledger, **kwargs)
        with patch.object(MoneyLedger, 'reserve', reserve):
            self.invoke()
        self.assertEqual(len(calls), 1)
        self.assertEqual((calls[0]['user_cap'], calls[0]['project_cap']), (95*SCALE, 95*SCALE))
        self.assertEqual((calls[0]['user_month_cap'], calls[0]['project_month_cap']), (2000*SCALE, 2000*SCALE))
        self.assertEqual(calls[0]['job'], (self.job['id'], self.job['owner']))

    def test_local_failure_does_not_call_cloud(self):
        with patch.object(local, 'complete', side_effect=local.LocalAIError('local_ai_unavailable')):
            with self.assertRaisesRegex(GuardError, 'local_ai_unavailable'):
                self.invoke()
        self.assertEqual((self.requests, self.rows()), ([], []))

    def test_local_busy_defers_without_switching(self):
        self.context = replace(self.context, availability=replace(self.context.availability, local_model_busy=True))
        with self.assertRaisesRegex(GuardError, 'agent_local_model_busy'):
            self.invoke()
        self.assertFalse(self.requests or self.local_calls)

    def test_no_job_context_is_rejected(self):
        token = CURRENT_JOB.set(None)
        try:
            with self.assertRaisesRegex(GuardError, 'agent_claimed_job_required'):
                self.invoke()
        finally:
            CURRENT_JOB.reset(token)
        self.assertFalse(self.local_calls)

    def test_job_from_another_user_is_rejected_even_locally(self):
        client = AgentTaskClient(2, self.connect, context_provider=lambda: self.context,
                                environment_provider=lambda: self.env)
        with self.assertRaises(LeaseLost):
            self.invoke(client)
        self.assertFalse(self.local_calls)

    def test_expired_job_is_rejected(self):
        with closing(self.connect()) as db, db:
            db.execute('UPDATE ai_work_jobs SET expires_at=?', (int(time.time()) - 1,))
        with self.assertRaises(LeaseLost):
            self.invoke()
        self.assertFalse(self.local_calls)

    def test_cancelled_job_never_sends(self):
        self.queue.cancel(1, self.job['id'])
        with self.assertRaises(LeaseLost):
            self.invoke()
        self.assertFalse(self.local_calls or self.requests)

    def test_cancel_before_cloud_dispatch_refunds_unused_reservation(self):
        self.cloud()
        with self.assertRaises(LeaseLost):
            self.invoke(self.client(before_send=lambda: self.queue.cancel(1, self.job['id'])))
        self.assertFalse(self.requests)
        self.assertEqual((self.rows()[0]['state'], self.rows()[0]['charge']), ('settled', 0))

    def test_cancel_after_response_keeps_charge_and_hides_result(self):
        self.cloud()
        def respond(request):
            result = self.respond_cloud(request)
            self.queue.cancel(1, self.job['id'])
            return result
        with self.assertRaises(LeaseLost):
            self.invoke(self.client(transport=httpx.MockTransport(respond)))
        self.assertEqual(len(self.requests), 1)
        self.assertEqual((self.rows()[0]['state'], self.rows()[0]['charge']), ('settled', 1200))

    def test_revoked_cloud_permission_before_send_blocks_dispatch(self):
        self.cloud()
        client = self.client(before_send=lambda: self.env.update(AGENT_CLOUD_ENABLED='false'))
        with self.assertRaisesRegex(GuardError, 'agent_configuration_changed'):
            self.invoke(client)
        self.assertFalse(self.requests)
        self.assertEqual(self.rows()[0]['charge'], 0)

    def test_changed_context_before_send_blocks_dispatch(self):
        self.cloud()
        def revoke():
            self.context = replace(self.context, request=replace(self.context.request, cloud_data_approved=False))
        with self.assertRaisesRegex(GuardError, 'agent_task_context_changed'):
            self.invoke(self.client(before_send=revoke))
        self.assertFalse(self.requests)
        self.assertEqual(self.rows()[0]['charge'], 0)

    def test_revocation_after_response_does_not_refund_paid_work(self):
        self.cloud()
        client = self.client(after_response=lambda: self.env.update(AGENT_CLOUD_ENABLED='false'))
        with self.assertRaisesRegex(GuardError, 'agent_configuration_changed'):
            self.invoke(client)
        self.assertEqual((self.rows()[0]['state'], self.rows()[0]['charge']), ('settled', 1200))

    def test_secrets_never_enter_either_transport(self):
        for cloud in (False, True):
            self.context = replace(self.context, request=TaskRequest(TaskKind.CONVERSATION,
                requires_cloud=cloud, cloud_data_approved=True, contains_secrets=True))
            with self.subTest(cloud=cloud), self.assertRaisesRegex(GuardError, 'agent_secret_input_blocked'):
                self.invoke()
        self.assertFalse(self.requests or self.local_calls or self.rows())

    def test_stale_portfolio_is_blocked(self):
        self.context = replace(self.context, request=TaskRequest(TaskKind.PORTFOLIO_REVIEW))
        with self.assertRaisesRegex(GuardError, 'agent_fresh_sources_required'):
            self.invoke()
        self.assertFalse(self.requests or self.local_calls)

    def test_cloud_without_data_approval_is_blocked(self):
        self.cloud()
        self.context = replace(self.context, request=replace(self.context.request, cloud_data_approved=False))
        with self.assertRaisesRegex(GuardError, 'agent_cloud_data_not_approved'):
            self.invoke()
        self.assertFalse(self.requests or self.rows())

    def test_cloud_unavailable_does_not_downgrade_review(self):
        self.cloud()
        self.context = replace(self.context, availability=replace(self.context.availability, cloud_route_ready=False))
        with self.assertRaisesRegex(GuardError, 'agent_cloud_route_unavailable'):
            self.invoke()
        self.assertFalse(self.local_calls or self.requests)

    def test_required_global_external_approval_is_preserved(self):
        self.cloud()
        self.env.pop('AI_EXTERNAL_PROCESSING_APPROVED')
        with self.assertRaisesRegex(GuardError, 'ai_processing_approval_required'):
            self.invoke()
        self.assertFalse(self.requests or self.rows())

    def test_existing_local_enablement_is_not_overridden(self):
        self.env['LOCAL_AI_ENABLED'] = 'false'
        with self.assertRaisesRegex(GuardError, 'local_ai_not_enabled'):
            self.invoke()
        self.assertFalse(self.local_calls or self.requests)

    def test_existing_broker_binding_is_not_bypassed(self):
        with closing(self.connect()) as db, db:
            db.execute('UPDATE users SET tinvest_token_encrypted=NULL')
        with self.assertRaisesRegex(GuardError, 'ai_broker_connection_required'):
            self.invoke()
        self.assertFalse(self.local_calls or self.requests)

    def test_untrusted_provider_url_is_rejected(self):
        self.cloud()
        self.env['TIMEWEB_AI_BASE_URL'] = 'https://invalid.example/v1'
        with self.assertRaisesRegex(GuardError, 'ai_route_url_not_allowed'):
            self.invoke()
        self.assertFalse(self.requests)

    def test_expired_prices_are_rejected(self):
        self.cloud()
        self.env['AI_FAST_PRICING_VALID_UNTIL'] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        with self.assertRaisesRegex(GuardError, 'ai_prices_missing_stale_or_invalid'):
            self.invoke()
        self.assertFalse(self.requests)

    def test_paid_timeout_retains_uncertain_reservation_without_retry(self):
        self.cloud()
        def fail(request):
            self.requests.append(request)
            raise httpx.ReadTimeout('synthetic timeout')
        with self.assertRaisesRegex(GuardError, 'ai_transport_outcome_unknown'):
            self.invoke(self.client(transport=httpx.MockTransport(fail)))
        row = self.rows()[0]
        self.assertEqual((len(self.requests), row['state']), (1, 'uncertain'))
        self.assertEqual(row['charge'], row['ceiling'])
        self.assertFalse(self.local_calls)

    def test_same_job_paid_attempt_cannot_be_replayed(self):
        self.cloud()
        client = self.client()
        self.invoke(client)
        with self.assertRaisesRegex(GuardError, 'ai_budget_duplicate_attempt'):
            self.invoke(client)
        self.assertEqual(len(self.requests), 1)

    def test_incomplete_paid_response_is_accounted_not_retried(self):
        self.cloud()
        def incomplete(request):
            self.requests.append(request)
            result = self.response('synthetic-agent-model')
            result['choices'][0]['finish_reason'] = 'length'
            return httpx.Response(200, json=result)
        with self.assertRaises(IncompleteModelResponse):
            self.invoke(self.client(transport=httpx.MockTransport(incomplete)))
        self.assertEqual((len(self.requests), self.rows()[0]['state']), (1, 'settled'))
        self.assertFalse(self.local_calls)

    def test_changed_local_model_rejected(self):
        with patch.object(local, 'complete', return_value=json.dumps(self.response('wrong-model')).encode()):
            with self.assertRaisesRegex(GuardError, 'local_ai_model_changed'):
                self.invoke()
        self.assertFalse(self.requests)

    def test_speech_is_not_misrouted_to_language_model(self):
        self.context = replace(self.context, request=TaskRequest(TaskKind.SPEECH_SYNTHESIS))
        with self.assertRaisesRegex(GuardError, 'agent_local_service_handler_required'):
            self.invoke()
        self.assertFalse(self.local_calls or self.requests)

    def test_messages_are_snapshotted_before_mutation(self):
        self.cloud()
        self.invoke(self.client(before_send=lambda: self.messages[0].update(content='Changed after quote')))
        self.assertEqual(json.loads(self.requests[0].content)['messages'][0]['content'], 'Synthetic greeting.')

    def test_existing_application_guard_is_composed(self):
        self.cloud()
        def denied(db):
            raise GuardError('synthetic_owner_pause')
        with self.assertRaisesRegex(GuardError, 'synthetic_owner_pause'):
            self.invoke(self.client(budget_guard=denied))
        self.assertFalse(self.requests or self.rows())

    def test_lower_monthly_envelope_is_applied_to_existing_ledger(self):
        self.cloud()
        self.env['AGENT_CLOUD_MONTHLY_RUB'] = '0.02'
        self.ledger.reserve(user_id=1, key='prior-monthly', route='other', model='synthetic',
                            ceiling=19_000, user_cap=SCALE, project_cap=SCALE)
        self.ledger.settle('prior-monthly', model='synthetic', cost=19_000, input_tokens=1, output_tokens=1)
        with self.assertRaisesRegex(GuardError, 'agent_monthly_budget_exhausted'):
            self.invoke()
        self.assertFalse(self.requests)
        self.assertEqual(len(self.rows()), 1)

    def test_spending_between_quote_and_reservation_is_rechecked(self):
        self.cloud()
        self.env['AI_USER_DAILY_RUB'] = '0.02'
        self.env['AI_PROJECT_DAILY_RUB'] = '0.02'
        def spend(route, ceiling):
            self.ledger.reserve(user_id=1, key='concurrent', route='synthetic-other-route',
                                model='synthetic-other-model', ceiling=20_000,
                                user_cap=20_000, project_cap=20_000,
                                user_month_cap=100_000, project_month_cap=100_000)
        with self.assertRaisesRegex(GuardError, 'agent_daily_budget_exhausted'):
            self.invoke(self.client(route_guard=spend))
        self.assertFalse(self.requests)
        self.assertEqual(len(self.rows()), 1)
        self.assertEqual(self.rows()[0]['request_key'], 'concurrent')

    def test_invalid_context_provider_is_closed(self):
        client = AgentTaskClient(1, self.connect, context_provider=lambda: {'requires_cloud': True},
                                environment_provider=lambda: self.env)
        with self.assertRaisesRegex(GuardError, 'agent_context_unavailable'):
            self.invoke(client)
        self.assertFalse(self.requests or self.local_calls)

    def test_queue_drain_uses_adapter_without_second_queue(self):
        self.prepare_next_job()
        def work(user_id):
            result = self.invoke()
            return {'state': 'completed', 'reason': result.data['answer']}
        self.assertEqual(drain(self.queue, work, limit=1), {'processed': 1, 'failed': 0})
        self.assertEqual(self.queue.user_status(1)['state'], 'completed')
        self.assertIsNone(CURRENT_JOB.get())

    def test_queue_drain_does_not_retry_unknown_paid_outcome(self):
        self.cloud()
        self.prepare_next_job()
        def fail(request):
            self.requests.append(request)
            raise httpx.ReadTimeout('synthetic timeout')
        client = self.client(transport=httpx.MockTransport(fail))
        self.assertEqual(drain(self.queue, lambda user_id: self.invoke(client), limit=3),
                         {'processed': 0, 'failed': 1})
        self.assertEqual(self.queue.user_status(1)['state'], 'failed')
        self.assertEqual(self.rows()[0]['state'], 'uncertain')
        self.assertEqual(len(self.requests), 1)
        self.assertFalse(self.local_calls)
        self.assertIsNone(CURRENT_JOB.get())


if __name__ == '__main__':
    unittest.main()
