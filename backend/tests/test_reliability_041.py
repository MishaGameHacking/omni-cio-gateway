from __future__ import annotations

import asyncio
import copy
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('TELEGRAM_CLIENT_ID', '123456')
os.environ.setdefault('TELEGRAM_CLIENT_SECRET', 'test-only')
os.environ.setdefault('BACKEND_PUBLIC_URL', 'https://example.invalid')
os.environ.setdefault('FERNET_KEY', 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=')
os.environ['ANALYSIS_SCHEDULER_ENABLED'] = 'false'

from backend import app as backend
from backend import autonomous_ai as ai
from backend.ai_policy import AnalysisBudget, AnalysisTier
from backend.tests.test_autonomous_ai import sample_snapshot
from backend.timeweb_ai import DEFAULT_BASE_URL, TimewebAIConfig, TimewebAIUpstreamError


class SchedulerShutdownTests(unittest.IsolatedAsyncioTestCase):
    async def test_stops_child_without_cancelling_caller(self):
        started = asyncio.Event()
        async def worker():
            started.set()
            await asyncio.Event().wait()
        task = asyncio.create_task(worker())
        await started.wait()
        with patch.object(ai, '_scheduler_task', task):
            await ai.stop_scheduler()
            self.assertTrue(task.cancelled())
            self.assertIsNone(ai._scheduler_task)
            self.assertEqual(asyncio.current_task().cancelling(), 0)

    async def test_caller_cancellation_during_cleanup_propagates(self):
        started = asyncio.Event()
        cleaning = asyncio.Event()
        release = asyncio.Event()
        async def worker():
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleaning.set()
                await release.wait()
        task = asyncio.create_task(worker())
        await started.wait()
        with patch.object(ai, '_scheduler_task', task):
            stopper = asyncio.create_task(ai.stop_scheduler())
            await cleaning.wait()
            stopper.cancel()
            try:
                with self.assertRaises(asyncio.CancelledError):
                    await stopper
            finally:
                release.set()
                await asyncio.wait({task})
            self.assertTrue(task.cancelled())

    async def test_worker_failure_is_not_hidden(self):
        async def worker():
            raise RuntimeError('test failure')
        task = asyncio.create_task(worker())
        await asyncio.wait({task})
        with patch.object(ai, '_scheduler_task', task):
            with self.assertRaisesRegex(RuntimeError, 'test failure'):
                await ai.stop_scheduler()
            self.assertIsNone(ai._scheduler_task)


class AnalysisReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.path_patch = patch.object(backend, 'DATABASE_PATH', Path(self.temp.name) / 'test.db')
        self.path_patch.start()
        backend.init_db()
        ai.init_autonomous_db()
        with closing(backend.connect()) as db:
            db.execute("INSERT INTO users(telegram_sub, telegram_id, tinvest_token_encrypted, created_at, updated_at) VALUES ('test', '1', ?, 1, 1)", (b'test-encrypted-placeholder',))
            db.commit()
            self.user = db.execute("SELECT * FROM users WHERE telegram_sub='test'").fetchone()
        self.user_id = int(self.user['id'])
        self.now = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)

    def tearDown(self):
        self.path_patch.stop()
        self.temp.cleanup()

    def test_cash_only_is_not_a_concentrated_security(self):
        snapshot = sample_snapshot(cash_share=100, stock_share=0)
        snapshot['accounts'][0]['positions'] = [snapshot['accounts'][0]['positions'][1]]
        self.assertEqual(ai._critical_risk(snapshot, ai.get_profile(self.user_id)), (False, None))

    def test_diversified_class_is_not_one_position(self):
        snapshot = sample_snapshot(cash_share=10, stock_share=90)
        template = snapshot['accounts'][0]['positions'][0]
        positions = []
        for index in range(9):
            position = copy.deepcopy(template)
            position['id'] = f'asset-{index}'
            position['currentValue']['value']['units'] = 10_000
            positions.append(position)
        snapshot['accounts'][0]['positions'] = positions
        self.assertFalse(ai._critical_risk(snapshot, ai.get_profile(self.user_id))[0])

    def test_position_is_aggregated_across_accounts(self):
        snapshot = sample_snapshot(cash_share=10, stock_share=30)
        account = copy.deepcopy(snapshot['accounts'][0])
        account['id'] = 'account-2'
        snapshot['accounts'].append(account)
        self.assertTrue(ai._critical_risk(snapshot, ai.get_profile(self.user_id))[0])

    def test_refresh_does_not_force_model_invocation(self):
        with patch.object(ai, 'run_user_analysis', return_value={'state': 'skipped'}) as run:
            ai.refresh(ai.RefreshRequest(), user=self.user)
        run.assert_called_once_with(self.user_id, force=False)
        with patch.object(ai, 'get_tinvest_portfolio', return_value=sample_snapshot()), patch.object(ai, 'analyze_if_needed') as analyze:
            ai.run_user_analysis(self.user_id, force=True, now=self.now)
            result = ai.run_user_analysis(self.user_id, force=True, now=self.now)
        self.assertEqual(result['state'], 'skipped')
        analyze.assert_not_called()

    def test_attempt_budget_is_atomic(self):
        with patch.object(ai, 'STANDARD_DAILY_LIMIT', 3):
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(lambda _: ai._reserve_budget(self.user_id, self.now, AnalysisTier.STANDARD), range(20)))
        self.assertEqual(sum(results), 3)

    def test_failed_paid_attempt_still_consumes_budget(self):
        environment = {'TIMEWEB_AI_TOKEN':'synthetic-test-only', 'AI_MODEL_PREMIUM':'test/model'}
        with patch.dict(os.environ, environment), patch.object(ai, 'get_tinvest_portfolio', return_value=sample_snapshot(stock_share=90, cash_share=5)), patch.object(ai, 'analyze_if_needed', side_effect=TimewebAIUpstreamError('timeweb_ai_timeout', retryable=True)):
            result = ai.run_user_analysis(self.user_id, now=self.now)
        self.assertEqual(result['state'], 'fallback')
        self.assertEqual(ai._budget(self.user_id, self.now).premium_calls_left, max(0, ai.PREMIUM_DAILY_LIMIT - 1))

    def test_critical_fallback_survives_exhausted_budget(self):
        with patch.object(ai, '_budget', return_value=AnalysisBudget(0, 0, 0)), patch.object(ai, 'get_tinvest_portfolio', return_value=sample_snapshot(stock_share=90, cash_share=5)), patch.object(ai, 'analyze_if_needed') as analyze:
            result = ai.run_user_analysis(self.user_id, now=self.now)
        self.assertEqual(result['state'], 'fallback')
        self.assertIsNotNone(result['card_id'])
        analyze.assert_not_called()
        self.assertEqual(ai.feed(limit=10, user=self.user)['cards'][0]['severity'], 'critical')

    def test_sum_of_ideas_does_not_exceed_available_cash(self):
        ai.update_profile(ai.ProfileUpdate(risk_level='moderate', horizon='medium', min_cash_percent=5), user=self.user)
        ai._save_snapshot(self.user_id, sample_snapshot(cash_share=20, stock_share=20))
        payload = ai.ideas(user=self.user)
        self.assertLessEqual(sum(idea['suggested_max_percent'] for idea in payload['ideas']), 15.0)

    def test_empty_base_url_uses_documented_default(self):
        with patch.dict(os.environ, {'TIMEWEB_AI_BASE_URL':'   '}):
            self.assertEqual(TimewebAIConfig.from_env().base_url, DEFAULT_BASE_URL)
