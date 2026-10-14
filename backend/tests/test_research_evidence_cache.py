"""Real route and database; synthetic evidence only, broker reads mocked."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from backend import portfolio_research as research, portfolio_details as details, research_store, autonomous_ai
from backend.evidence_revision import EvidenceRevision
from backend.tests import test_portfolio_research_integration as fixtures


class EvidenceCacheIntegrationTests(unittest.TestCase):
    def setUp(self):
        fixtures.ResearchIntegrationTests.setUp(self)
        autonomous_ai.init_autonomous_db()

    tearDown = fixtures.ResearchIntegrationTests.tearDown

    def import_identity(self, issuer='synthetic-company'):
        now = datetime.now(timezone.utc)
        return research_store.import_record(research.backend.connect, kind='issuer_identity', subject='synthetic-uid',
            payload={'instrument_uid': 'synthetic-uid', 'issuer_id': issuer, 'source': {
                'id': 'synthetic-source', 'url': 'https://example.invalid/evidence',
                'published_at': (now - timedelta(days=1)).isoformat(),
                'checked_at': (now - timedelta(minutes=1)).isoformat(),
                'expires_at': (now + timedelta(days=1)).isoformat(), 'review_id': 'synthetic-review'}})

    def test_import_changes_stamp(self):
        before = research_store.revision(research.backend.connect)
        self.import_identity()
        self.assertNotEqual(research_store.revision(research.backend.connect), before)

    def test_same_import_does_not_invalidate_again(self):
        self.import_identity()
        with closing(research.backend.connect()) as db:
            record = db.execute('SELECT * FROM research_evidence_v1').fetchone()
        import json
        before = research_store.revision(research.backend.connect)
        research_store.import_record(research.backend.connect, kind=record['kind'], subject=record['subject'],
                                     payload=json.loads(record['payload']))
        self.assertEqual(research_store.revision(research.backend.connect), before)

    def test_import_during_collection_discards_result(self):
        def load(*args, **kwargs):
            self.import_identity()
            return {'state': 'old-synthetic-evidence'}
        with patch.object(details, 'cached', side_effect=lambda key, ttl, build: build()), \
             patch.object(research, 'collect_research', side_effect=load):
            with self.assertRaises(HTTPException) as error:
                research.research(self.user)
        self.assertEqual(error.exception.status_code, 503)
        self.assertEqual(error.exception.detail, 'research_evidence_changed')

    def test_import_between_requests_cannot_reuse_previous_cache(self):
        cache = {}
        def cached(key, ttl, build):
            if key not in cache:
                cache[key] = build()
            return cache[key]
        with patch.object(details, 'cached', side_effect=cached), \
             patch.object(research, 'collect_research', side_effect=[{'state': 'before'}, {'state': 'after'}]) as collect:
            self.assertEqual(research.research(self.user)['state'], 'before')
            self.assertEqual(research.research(self.user)['state'], 'before')
            self.import_identity()
            self.assertEqual(research.research(self.user)['state'], 'after')
        self.assertEqual(collect.call_count, 2)

    def test_cache_hit_still_checks_current_evidence(self):
        before = EvidenceRevision('a'*32, 1)
        after = EvidenceRevision('a'*32, 2)
        with patch.object(research_store, 'revision', side_effect=[before, after]), \
             patch.object(details, 'cached', return_value={'state': 'cached'}), \
             patch.object(research, 'collect_research') as collect:
            with self.assertRaises(HTTPException) as error:
                research.research(self.user)
        collect.assert_not_called()
        self.assertEqual(error.exception.detail, 'research_evidence_changed')

    def test_revision_failure_does_not_serve_cached_success(self):
        failure = research.EvidenceError('synthetic failure')
        with patch.object(research_store, 'revision', side_effect=failure), \
             patch.object(details, 'cached') as cached:
            with self.assertRaises(HTTPException) as error:
                research.research(self.user)
        cached.assert_not_called()
        self.assertEqual(error.exception.detail, 'research_evidence_unavailable')

    def test_no_broker_token_still_precedes_revision_access(self):
        with patch.object(research_store, 'revision') as revision:
            with self.assertRaises(HTTPException):
                research.research({'id': 3, 'tinvest_token_encrypted': None})
        revision.assert_not_called()


if __name__ == '__main__':
    unittest.main()
