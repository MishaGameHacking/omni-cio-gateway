"""Real worker/queue/SQLite, synthetic portfolio and model replies only."""
from contextlib import closing
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault('BACKEND_PUBLIC_URL', 'https://example.invalid')
os.environ.setdefault('FERNET_KEY', 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=')
os.environ.setdefault('TELEGRAM_CLIENT_ID', '123456')
os.environ.setdefault('TELEGRAM_CLIENT_SECRET', 'test-only')
os.environ['ANALYSIS_SCHEDULER_ENABLED'] = 'false'

from backend import app as backend, autonomous_ai as ai, agent_analysis_runtime as runtime
from backend import local_ai_transport as local
from backend.ai_guarded_client import GuardedAIClient, GuardError
from backend.ai_jobs import AnalysisQueue, CURRENT_JOB, LeaseLost, drain
from backend.ai_policy import AnalysisDecision, AnalysisReason, AnalysisTier
from backend.tests.test_autonomous_ai import sample_snapshot


class AgentAnalysisRuntimeTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        old_path = backend.DATABASE_PATH
        self.addCleanup(setattr, backend, 'DATABASE_PATH', old_path)
        backend.DATABASE_PATH = Path(directory.name) / 'synthetic.db'
        self.env = {'AGENT_ROUTING_ENABLED': 'true', 'AGENT_PORTFOLIO_ROUTE': 'local',
            'AGENT_CLOUD_ENABLED': 'true', 'AI_TRANSPORT': 'local', 'LOCAL_AI_ENABLED': 'true',
            'AI_EXTERNAL_PROCESSING_APPROVED': 'true', 'AI_USER_DAILY_RUB': '95',
            'AI_PROJECT_DAILY_RUB': '95', 'AI_USER_MONTHLY_RUB': '2900',
            'AI_PROJECT_MONTHLY_RUB': '2900', 'TIMEWEB_AI_TOKEN': 'synthetic-test-token'}
        expires = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        for tier in ('FAST', 'STANDARD', 'PREMIUM'):
            self.env.update({f'AI_MODEL_{tier}': 'synthetic-model', f'AI_{tier}_PROCESSING_REGION': 'RU',
                f'AI_{tier}_PRICING_MODEL': 'synthetic-model', f'AI_{tier}_PRICING_VALID_UNTIL': expires,
                f'AI_{tier}_INPUT_RUB_PER_MILLION': '100', f'AI_{tier}_OUTPUT_RUB_PER_MILLION': '200',
                f'AI_{tier}_INPUT_TOKEN_ALLOWANCE': '0', f'AI_{tier}_TOKEN_PARAMETER': 'max_tokens'})
        self.environment_patch = patch.dict(os.environ, self.env)
        self.environment_patch.start()
        self.addCleanup(self.environment_patch.stop)
        backend.init_db()
        ai.init_autonomous_db()
        with closing(backend.connect()) as db, db:
            db.execute("INSERT INTO users(telegram_sub,tinvest_token_encrypted,created_at,updated_at) "
                       "VALUES('synthetic-owner',?,1,1)", (b'synthetic-encrypted-placeholder',))
            self.user_id = db.execute('SELECT id FROM users').fetchone()[0]
        self.queue = AnalysisQueue(backend.connect)
        self.queue.enqueue(self.user_id)
        self.context = ai._context(sample_snapshot(stock_share=90, cash_share=5),
                                  ai.get_profile(self.user_id), datetime.now(timezone.utc), None)
        self.context['portfolio']['accounts'][0]['id'] = 'private-account-xyz'
        self.context['portfolio']['accounts'][0]['name'] = 'private-owner-label'
        self.decision = AnalysisDecision(AnalysisTier.PREMIUM, AnalysisReason.RISK_EVENT, True, 1200)
        self.addCleanup(CURRENT_JOB.reset, CURRENT_JOB.set(None))
        self.local_mock = self.enterContext(patch.object(local, 'complete', side_effect=self.respond_local))
        self.enterContext(patch.object(local, 'ensure_ready', return_value=None))
        self.cloud_mock = self.enterContext(patch.object(GuardedAIClient, '_send', side_effect=self.respond_cloud))

    def claim(self):
        job = self.queue.claim()
        CURRENT_JOB.set((job['id'], job['owner']))
        return job

    def build(self, **kwargs):
        return runtime.build_analysis_client(self.user_id, backend.connect,
            context=kwargs.pop('context', self.context), decision=self.decision,
            environment_provider=lambda: os.environ, **kwargs)

    def invoke(self, client):
        return client.complete_json(tier=self.decision.tier, messages=client.messages,
                                    max_output_tokens=self.decision.max_output_tokens)

    def response(self, messages, model):
        source = json.loads(messages[1]['content'])['context']['sources'][0]
        report = {'severity': 'warning', 'headline': 'Synthetic risk check', 'summary': 'Synthetic analysis only',
            'actions': [], 'uncertainties': ['Synthetic test, not advice'], 'valid_until': None,
            'evidence': [{'fact': 'Synthetic observation', 'source_id': source['id'], 'as_of': source['as_of']}]}
        return {'model': model, 'usage': {'prompt_tokens': 100, 'completion_tokens': 30, 'total_tokens': 130},
                'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(report)}}]}

    def respond_local(self, messages, max_output_tokens):
        return json.dumps(self.response(messages, local.MODEL_ID)).encode()

    def respond_cloud(self, route, payload):
        return self.response(payload['messages'], route.model)

    def records(self):
        with closing(backend.connect()) as db:
            return list(db.execute('SELECT payload_json,version FROM workspace_records WHERE kind=?',
                                   (runtime.RECEIPT_KIND,)))

    def test_actual_queue_worker_uses_local_adapter_and_publishes_validated_card(self):
        with patch.object(ai, 'get_tinvest_portfolio', return_value=sample_snapshot(stock_share=90, cash_share=5)):
            result = drain(self.queue, ai.run_user_analysis, limit=1)
        self.assertEqual(result, {'processed': 1, 'failed': 0})
        self.local_mock.assert_called_once()
        self.cloud_mock.assert_not_called()
        self.assertEqual(len(self.records()), 1)
        with closing(backend.connect()) as db:
            self.assertEqual(db.execute('SELECT state,model FROM analysis_runs').fetchone()[:], ('completed', local.MODEL_ID))
            self.assertEqual(db.execute('SELECT COUNT(*) FROM insight_cards').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM ai_money_reservations').fetchone()[0], 0)

    def test_actual_worker_cloud_route_reserves_and_settles_without_local_call(self):
        os.environ['AGENT_PORTFOLIO_ROUTE'] = 'timeweb'
        with patch.object(ai, 'get_tinvest_portfolio', return_value=sample_snapshot(stock_share=90, cash_share=5)):
            result = drain(self.queue, ai.run_user_analysis, limit=1)
        self.assertEqual(result, {'processed': 1, 'failed': 0})
        self.cloud_mock.assert_called_once()
        self.local_mock.assert_not_called()
        with closing(backend.connect()) as db:
            row = db.execute('SELECT state,charge FROM ai_money_reservations').fetchone()
            self.assertEqual(row['state'], 'settled')
            self.assertGreater(row['charge'], 0)
            self.assertEqual(db.execute('SELECT state FROM analysis_runs').fetchone()[0], 'completed')
        self.assertEqual(os.environ['AI_TRANSPORT'], 'local')

    def test_actual_worker_local_failure_does_not_call_cloud(self):
        self.local_mock.side_effect = local.LocalAIError('local_ai_unavailable')
        with patch.object(ai, 'get_tinvest_portfolio', return_value=sample_snapshot(stock_share=90, cash_share=5)):
            drain(self.queue, ai.run_user_analysis, limit=1)
        self.cloud_mock.assert_not_called()
        with closing(backend.connect()) as db:
            row = db.execute('SELECT state,error_code FROM analysis_runs').fetchone()
            self.assertEqual(row[:], ('fallback', 'local_ai_unavailable'))

    def test_feature_off_preserves_unbound_legacy_factory(self):
        self.claim()
        os.environ['AGENT_ROUTING_ENABLED'] = 'false'
        sentinel = object()
        factory = Mock(return_value=sentinel)
        client, context = self.build(legacy_factory=factory)
        self.assertIs(client, sentinel)
        self.assertIs(context, self.context)
        self.assertEqual(self.records(), [])

    def test_invalid_flags_do_not_fall_through_to_legacy_cloud(self):
        for flag in ('yes', '1', ''):
            with self.subTest(flag=flag), patch.dict(os.environ, {'AGENT_ROUTING_ENABLED': flag}):
                with self.assertRaisesRegex(GuardError, 'agent_routing_flag_invalid'):
                    self.build()
        self.cloud_mock.assert_not_called()

    def test_claimed_job_required(self):
        with self.assertRaisesRegex(GuardError, 'agent_claimed_job_required'):
            self.build()
        self.assertEqual(self.records(), [])

    def test_cancelled_claim_cannot_create_receipt(self):
        job = self.claim()
        self.queue.cancel(self.user_id, job['id'])
        with self.assertRaises(LeaseLost):
            self.build()
        self.assertEqual(self.records(), [])

    def test_receipt_persists_metadata_but_not_private_payload(self):
        self.claim()
        original = deepcopy(self.context)
        first, safe = self.build()
        second, _ = self.build()
        self.assertEqual(first.receipt, second.receipt)
        rows = self.records()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['version'], 1)
        self.assertNotIn('private-account-xyz', rows[0]['payload_json'])
        self.assertNotIn('private-owner-label', rows[0]['payload_json'])
        self.assertNotIn('positions', rows[0]['payload_json'])
        self.assertNotIn('private-account-xyz', json.dumps(safe))
        self.assertNotIn('private-owner-label', json.dumps(safe))
        self.assertEqual(safe['portfolio']['accounts'][0]['account_ref'], 'account-1')
        self.assertEqual(self.context, original)

    def test_route_cannot_change_when_recreating_bound_job(self):
        self.claim()
        self.build()
        os.environ['AGENT_PORTFOLIO_ROUTE'] = 'timeweb'
        with self.assertRaisesRegex(GuardError, 'agent_analysis_receipt_changed'):
            self.build()

    def test_disabling_feature_cannot_escape_bound_receipt(self):
        self.claim()
        self.build()
        os.environ['AGENT_ROUTING_ENABLED'] = 'false'
        with self.assertRaisesRegex(GuardError, 'agent_routing_changed'):
            self.build()

    def test_context_change_cannot_overwrite_receipt(self):
        self.claim()
        client, _ = self.build()
        self.context['computed']['new_value'] = 42
        with self.assertRaisesRegex(GuardError, 'agent_analysis_receipt_changed'):
            self.build()
        self.assertEqual(self.records()[0]['payload_json'], client.receipt)

    def test_payload_cannot_be_swapped_after_admission(self):
        self.claim()
        client, _ = self.build()
        changed = deepcopy(client.messages)
        changed[1]['content'] = '{}'
        with self.assertRaisesRegex(GuardError, 'agent_analysis_payload_changed'):
            client.complete_json(tier=self.decision.tier, messages=changed, max_output_tokens=1200)
        self.local_mock.assert_not_called()

    def test_secret_shaped_fields_fail_before_any_receipt_or_inference(self):
        self.claim()
        self.context['portfolio']['api_key'] = 'synthetic-do-not-publish'
        with self.assertRaisesRegex(GuardError, '^agent_secret_input_blocked$'):
            self.build()
        self.assertEqual(self.records(), [])
        self.local_mock.assert_not_called()

    def test_stale_and_future_sources_fail_closed(self):
        self.claim()
        for delta, code in ((-301, 'agent_fresh_sources_required'), (30, 'agent_source_from_future')):
            value = deepcopy(self.context)
            value['sources'][0]['as_of'] = (datetime.now(timezone.utc) + timedelta(seconds=delta)).isoformat()
            with self.subTest(delta=delta), self.assertRaisesRegex(GuardError, code):
                self.build(context=value)
        self.assertEqual(self.records(), [])

    def test_false_or_missing_freshness_not_treated_as_true(self):
        self.claim()
        for value in (False, 'true', None):
            context = deepcopy(self.context)
            context['sources'][0]['fresh'] = value
            with self.subTest(value=value), self.assertRaisesRegex(GuardError, 'agent_fresh_sources_required'):
                self.build(context=context)

    def test_expired_third_party_source_blocks_request(self):
        self.claim()
        self.context['sources'].append({'id': 'synthetic-credit', 'fresh': True,
            'as_of': datetime.now(timezone.utc).isoformat(),
            'expires_at': (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()})
        with self.assertRaisesRegex(GuardError, 'agent_fresh_sources_required'):
            self.build()

    def test_receipt_tampering_blocks_dispatch(self):
        self.claim()
        client, _ = self.build()
        with closing(backend.connect()) as db, db:
            db.execute('UPDATE workspace_records SET version=2 WHERE kind=?', (runtime.RECEIPT_KIND,))
        with self.assertRaisesRegex(GuardError, 'agent_analysis_receipt_changed'):
            self.invoke(client)
        self.local_mock.assert_not_called()

    def test_expiry_before_dispatch_blocks_model(self):
        self.claim()
        client, _ = self.build()
        with patch.object(runtime, 'time', SimpleNamespace(time=lambda: client.deadline + 1)):
            with self.assertRaisesRegex(GuardError, 'agent_fresh_sources_required'):
                self.invoke(client)
        self.local_mock.assert_not_called()

    def test_receipt_changed_during_cloud_call_does_not_erase_charge(self):
        self.claim()
        os.environ['AGENT_PORTFOLIO_ROUTE'] = 'timeweb'
        client, _ = self.build()
        def respond(route, payload):
            with closing(backend.connect()) as db, db:
                db.execute('UPDATE workspace_records SET version=2 WHERE kind=?', (runtime.RECEIPT_KIND,))
            return self.respond_cloud(route, payload)
        self.cloud_mock.side_effect = respond
        with self.assertRaisesRegex(GuardError, 'agent_analysis_receipt_changed'):
            self.invoke(client)
        with closing(backend.connect()) as db:
            row = db.execute('SELECT state,charge FROM ai_money_reservations').fetchone()
            self.assertEqual(row['state'], 'settled')
            self.assertGreater(row['charge'], 0)
        self.assertEqual(self.cloud_mock.call_count, 1)

    def test_cloud_requires_both_explicit_approvals(self):
        self.claim()
        os.environ['AGENT_PORTFOLIO_ROUTE'] = 'timeweb'
        for flag in ('AGENT_CLOUD_ENABLED', 'AI_EXTERNAL_PROCESSING_APPROVED'):
            with self.subTest(flag=flag), patch.dict(os.environ, {flag: 'false'}):
                with self.assertRaisesRegex(GuardError, 'agent_cloud_not_approved'):
                    self.build()
        self.assertEqual(self.records(), [])

    def test_mutating_returned_messages_does_not_mutate_admission(self):
        self.claim()
        client, _ = self.build()
        observed = client.messages
        observed[1]['content'] = '{}'
        self.assertNotEqual(observed, client.messages)
        with self.assertRaisesRegex(GuardError, 'agent_analysis_payload_changed'):
            client.complete_json(tier=self.decision.tier, messages=observed, max_output_tokens=1200)
        self.local_mock.assert_not_called()
        self.invoke(client)
        self.local_mock.assert_called_once()

    def test_changed_notification_intent_cannot_reuse_receipt(self):
        self.claim()
        self.build()
        self.decision = replace(self.decision, notify_user=False)
        with self.assertRaisesRegex(GuardError, 'agent_analysis_receipt_changed'):
            self.build()

    def test_reconnected_broker_before_readiness_blocks_old_context(self):
        self.claim()
        client, _ = self.build()
        with closing(backend.connect()) as db, db:
            db.execute('UPDATE broker_connection_versions SET stamp=? WHERE user_id=?',
                       ('f' * 64 if client.binding != 'f' * 64 else 'e' * 64, self.user_id))
        with self.assertRaisesRegex(GuardError, 'agent_analysis_broker_changed'):
            client.check_ready(self.decision.tier)
        self.local_mock.assert_not_called()
        self.cloud_mock.assert_not_called()

    def test_top_level_runtime_import_has_no_process_or_model_side_effects(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, '-I', '-c',
            'import sys; sys.path.insert(0,sys.argv[1]); import agent_analysis_runtime; print("IMPORT_OK")', str(root)],
            env={key: value for key, value in os.environ.items() if key.upper() in
                 {'PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'HOME'}},
            capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'IMPORT_OK')


if __name__ == '__main__':
    unittest.main()
