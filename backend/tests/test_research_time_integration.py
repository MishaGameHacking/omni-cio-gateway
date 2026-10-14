"""Actual route, evidence selectors and cache with controlled time/broker data."""
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from backend import autonomous_ai, portfolio_research as research, research_clock, research_store
from backend.tests import test_portfolio_research_integration as fixtures


class ResearchTimeIntegrationTests(unittest.TestCase):
    snapshot = fixtures.ResearchIntegrationTests.snapshot
    tearDown = fixtures.ResearchIntegrationTests.tearDown

    def setUp(self):
        fixtures.ResearchIntegrationTests.setUp(self)
        autonomous_ai.init_autonomous_db()
        self.clock = datetime.now(timezone.utc)
        self.expires = self.clock + timedelta(seconds=30)
        self.uid = self.snapshot()['accounts'][0]['positions'][0]['id']

    def import_identity(self, *, available=None):
        now = self.clock if available is None else available
        return research_store.import_record(research.backend.connect, kind='issuer_identity',
            subject=self.uid, payload={'instrument_uid': self.uid, 'issuer_id': 'synthetic-issuer',
            'source': {'id': 'synthetic', 'url': 'https://example.invalid/review',
                       'published_at': (now - timedelta(days=1)).isoformat(),
                       'checked_at': now.isoformat(), 'expires_at': self.expires.isoformat(),
                       'review_id': 'synthetic-review'}}, at=now)

    def environment(self):
        stack = ExitStack()
        stack.enter_context(patch.object(research_clock, 'utc_now', side_effect=lambda: self.clock))
        dates = stack.enter_context(patch.object(research, 'datetime', wraps=datetime))
        dates.now.side_effect = lambda tz: self.clock.astimezone(tz)
        stack.enter_context(patch.object(research.details, 'load_dashboard', return_value=self.snapshot()))
        stack.enter_context(patch.object(research, '_optional_inputs', return_value=({}, [], [])))
        return stack

    def test_expiry_without_import_recomputes_cached_assessment(self):
        self.import_identity()
        original_revision = research_store.revision(research.backend.connect)
        with self.environment(), patch.object(research, 'collect_research', wraps=research.collect_research) as collect:
            first = research.research(self.user)
            again = research.research(self.user)
            self.assertEqual(first['cards'][0]['issuer_id'], 'synthetic-issuer')
            self.assertEqual(again['cards'][0]['issuer_id'], 'synthetic-issuer')
            self.assertEqual(collect.call_count, 1)
            self.clock = self.expires
            expired = research.research(self.user)
            self.assertIsNone(expired['cards'][0]['issuer_id'])
            self.assertEqual(collect.call_count, 2)
        self.assertEqual(research_store.revision(research.backend.connect), original_revision)

    def test_expiry_during_collection_is_not_published(self):
        self.import_identity()
        actual = research.collect_research
        def expires_during_read(*args, **kwargs):
            value = actual(*args, **kwargs)
            self.clock = self.expires
            return value
        with self.environment(), patch.object(research, 'collect_research', side_effect=expires_during_read):
            with self.assertRaises(HTTPException) as failure:
                research.research(self.user)
        self.assertEqual(failure.exception.status_code, 503)
        self.assertEqual(failure.exception.detail, 'research_time_boundary_crossed')
        # No need to wait out a 300-second cache after crossing the boundary.
        with self.environment():
            fresh = research.research(self.user)
        self.assertIsNone(fresh['cards'][0]['issuer_id'])

    def test_future_import_becomes_visible_without_new_database_write(self):
        available = self.clock + timedelta(seconds=10)
        self.import_identity(available=available)
        revision = research_store.revision(research.backend.connect)
        with self.environment():
            before = research.research(self.user)
            self.assertIsNone(before['cards'][0]['issuer_id'])
            self.clock = available
            after = research.research(self.user)
        self.assertEqual(after['cards'][0]['issuer_id'], 'synthetic-issuer')
        self.assertEqual(research_store.revision(research.backend.connect), revision)

    def test_news_expiry_is_not_hidden_by_unchanged_database(self):
        expires = self.clock + timedelta(seconds=10)
        item = {'id': 'synthetic-news', 'title': 'Test', 'source': 'Test',
                'ts': (expires - timedelta(days=7)).isoformat(),
                'instrumentId': [{'instrument': {'instrumentUid': self.uid}}]}
        with self.environment(), patch.object(research, '_optional_inputs', return_value=({}, [item], [])):
            before = research.research(self.user)
            self.assertEqual(len(before['cards'][0]['news']), 1)
            self.clock = expires
            after = research.research(self.user)
        self.assertEqual(after['cards'][0]['news'], [])


if __name__ == '__main__':
    unittest.main()
