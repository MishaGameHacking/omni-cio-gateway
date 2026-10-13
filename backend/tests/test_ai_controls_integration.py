"""Integration regressions on the real application modules with synthetic DB only."""
from __future__ import annotations

from contextlib import closing
from datetime import UTC, datetime
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

os.environ.setdefault('TELEGRAM_CLIENT_ID', '123456')
os.environ.setdefault('TELEGRAM_CLIENT_SECRET', 'test-only')
os.environ.setdefault('BACKEND_PUBLIC_URL', 'https://example.invalid')
os.environ.setdefault('FERNET_KEY', 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=')
os.environ['ANALYSIS_SCHEDULER_ENABLED'] = 'false'

from fastapi import HTTPException
from fastapi.testclient import TestClient
from backend import app as backend
from backend import autonomous_ai as ai
from backend.ai_jobs import AnalysisQueue, CURRENT_JOB, LeaseLost
from backend.ai_budget import MoneyLedger, BudgetDenied
from backend.ai_policy import AnalysisBudget, AnalysisSignals
from backend.analysis_engine import analyze_if_needed, AnalysisValidationError
from backend.tests.test_autonomous_ai import sample_snapshot


class ControlsIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(backend, 'DATABASE_PATH', Path(self.temp.name)/'test.db')
        self.db_patch.start()
        backend.init_db()
        ai.init_autonomous_db()
        with closing(backend.connect()) as db:
            cursor = db.execute("INSERT INTO users(telegram_sub,telegram_id,tinvest_token_encrypted,created_at,updated_at) VALUES ('control-test','1',?,1,1)", (b'synthetic-placeholder',))
            self.user_id = int(cursor.lastrowid)
            db.commit()
            self.user = db.execute('SELECT * FROM users WHERE id=?', (self.user_id,)).fetchone()
        self.queue = AnalysisQueue(backend.connect)
        self.client = TestClient(backend.app)

    def tearDown(self):
        self.client.close()
        self.db_patch.stop()
        self.temp.cleanup()

    def test_existing_db_initialized_repeatedly_without_resetting_users(self):
        ai.init_autonomous_db()
        with closing(backend.connect()) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM users').fetchone()[0], 1)
            self.assertIsNotNone(db.execute("SELECT name FROM sqlite_master WHERE name='ai_work_jobs'").fetchone())
            self.assertIsNotNone(db.execute("SELECT name FROM sqlite_master WHERE name='ai_money_reservations'").fetchone())

    def test_refresh_queues_without_network_or_inline_analysis(self):
        with patch.object(ai, 'SCHEDULER_ENABLED', True), patch.object(ai, 'run_user_analysis') as run:
            first = ai.refresh(ai.RefreshRequest(), user=self.user)
            second = ai.refresh(ai.RefreshRequest(), user=self.user)
        run.assert_not_called()
        self.assertEqual(first['state'], 'queued')
        self.assertEqual(first['job_id'], second['job_id'])
        self.assertTrue(second['coalesced'])

    def test_http_queue_contract_remains_compatible_and_authenticated(self):
        self.assertEqual(self.client.post('/analysis/refresh', json={'reason':'manual'}).status_code, 401)
        backend.app.dependency_overrides[backend.current_user] = lambda: self.user
        try:
            with patch.object(ai, 'SCHEDULER_ENABLED', True), patch.object(ai, 'run_user_analysis') as run:
                response = self.client.post('/analysis/refresh', json={'reason':'manual'})
            self.assertEqual(response.status_code, 202, response.text)
            self.assertEqual(response.json()['tier'], 'none')
            self.assertIsNone(response.json()['card_id'])
            run.assert_not_called()
        finally:
            backend.app.dependency_overrides.pop(backend.current_user, None)

    def test_disabled_scheduler_is_not_a_false_queued_success(self):
        with patch.object(ai, 'SCHEDULER_ENABLED', False), self.assertRaises(HTTPException) as error:
            ai.refresh(ai.RefreshRequest(), user=self.user)
        self.assertEqual(error.exception.status_code, 503)

    def test_scheduler_drains_through_real_analysis_without_live_model(self):
        now = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)
        def synthetic_run(user_id):
            return original(user_id, now=now)
        original = ai.run_user_analysis
        with patch.dict(os.environ, {'AI_EXTERNAL_PROCESSING_APPROVED':'false'}), patch.object(ai, 'get_tinvest_portfolio', return_value=sample_snapshot(stock_share=90, cash_share=5)), patch.object(ai, 'run_user_analysis', side_effect=synthetic_run), patch.object(ai, 'analyze_if_needed') as model:
            result = ai.run_scheduler_cycle()
        self.assertEqual(result, {'processed':1, 'failed':0})
        model.assert_not_called()
        self.assertEqual(self.queue.user_status(self.user_id)['state'], 'completed')
        cards = ai.feed(limit=10, user=self.user)['cards']
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]['severity'], 'critical')
        self.assertIsNone(CURRENT_JOB.get())

    def test_scheduler_retry_keeps_collection_job_after_temporary_error(self):
        with patch.object(ai, 'get_tinvest_portfolio', side_effect=HTTPException(status_code=503, detail='tinvest_timeout')):
            result = ai.run_scheduler_cycle()
        self.assertEqual(result['failed'], 1)
        status = self.queue.user_status(self.user_id)
        self.assertEqual(status['state'], 'queued')
        self.assertEqual(status['attempts'], 1)

    def test_stale_worker_cannot_write_snapshot(self):
        now = int(time.time())
        self.queue.enqueue(self.user_id, at=now-1000)
        job = self.queue.claim(at=now-1000)
        context = CURRENT_JOB.set((job['id'], job['owner']))
        try:
            with self.assertRaises(LeaseLost):
                ai._save_snapshot(self.user_id, sample_snapshot())
        finally:
            CURRENT_JOB.reset(context)
        with closing(backend.connect()) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM portfolio_snapshots').fetchone()[0], 0)

    def test_money_fence_runs_under_transaction(self):
        now = int(time.time())
        self.queue.enqueue(self.user_id, at=now-1000)
        job = self.queue.claim(at=now-1000)
        with self.assertRaisesRegex(BudgetDenied, 'lease'):
            MoneyLedger(backend.connect).reserve(user_id=self.user_id, key='stale', route='synthetic', model='test', ceiling=1, user_cap=10, project_cap=10,
                                                job=(job['id'],job['owner']))
        self.assertEqual(MoneyLedger(backend.connect).user_summary(self.user_id)['unresolved_attempts'], 0)

    def test_status_does_not_claim_configuration_is_live_proof(self):
        with patch.dict(os.environ, {'AI_EXTERNAL_PROCESSING_APPROVED':'false', 'TIMEWEB_CLOUD_TOKEN':'DO-NOT-EXPOSE'}):
            result = ai.status(user=self.user)
        self.assertFalse(result['ai_configured'])
        self.assertEqual(len(result['route_readiness']), 3)
        self.assertTrue(result['configuration_is_not_live_inference_proof'])
        self.assertNotIn('DO-NOT-EXPOSE', str(result))
        self.assertFalse(result['spending']['provider_invoice_reconciled'])

    def test_engine_requires_explicit_guarded_transport_for_paid_work(self):
        with self.assertRaisesRegex(AnalysisValidationError, 'explicit_client'):
            analyze_if_needed(signals=AnalysisSignals(morning_due=True,digest_changed=True), budget=AnalysisBudget(1,1,1),
                              context={'sources':[{'id':'synthetic','as_of':'2026-10-13T00:00:00Z'}]})
        result = analyze_if_needed(signals=AnalysisSignals(), budget=AnalysisBudget(1,1,1), context={})
        self.assertIsNone(result.report)


if __name__ == '__main__':
    unittest.main()
