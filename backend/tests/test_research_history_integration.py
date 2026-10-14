"""Store/selector regression using real SQLite and synthetic reviewed records."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from backend import research_store as store
from backend.credit_evidence import EvidenceError

NOW = datetime(2026, 10, 13, 12, tzinfo=timezone.utc)


def identity(issuer='issuer', audit='review', published_days=2):
    return {'instrument_uid': 'A', 'issuer_id': issuer, 'source': {
        'id': 'official-test', 'url': 'https://example.invalid/reviewed-record',
        'published_at': (NOW - timedelta(days=published_days)).isoformat(),
        'checked_at': (NOW - timedelta(days=1)).isoformat(),
        'expires_at': (NOW + timedelta(days=10)).isoformat(), 'review_id': audit}}


class ResearchHistoryIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'test.sqlite'

    def connect(self):
        return sqlite3.connect(self.path)

    def insert(self, payload, at=NOW):
        return store.import_record(self.connect, kind='issuer_identity', subject='A', payload=payload, at=at)

    def test_backfill_cannot_evict_latest_published_fact(self):
        self.insert(identity('latest'), at=NOW - timedelta(hours=1))
        for i in range(120):
            self.insert(identity('old', audit=str(i), published_days=3))
        result = store.latest_verified(self.connect, 'issuer_identity', 'A', NOW)
        self.assertEqual(result['issuer_id'], 'latest')

    def test_more_than_100_duplicate_observations_cannot_hide_conflict(self):
        self.insert(identity('conflicting'), at=NOW - timedelta(hours=1))
        for i in range(120):
            self.insert(identity('other', audit=str(i)))
        self.assertIsNone(store.latest_verified(self.connect, 'issuer_identity', 'A', NOW))

    def test_late_import_cannot_appear_in_earlier_assessment(self):
        self.insert(identity())
        moment = NOW - timedelta(minutes=1)
        self.assertIsNone(store.latest_verified(self.connect, 'issuer_identity', 'A', moment))

    def test_repeated_import_preserves_first_availability(self):
        first = self.insert(identity(), at=NOW - timedelta(hours=1))
        self.assertEqual(self.insert(identity()), first)
        moment = NOW - timedelta(minutes=30)
        self.assertIsNotNone(store.latest_verified(self.connect, 'issuer_identity', 'A', moment))

    def test_changed_database_payload_is_not_accepted(self):
        self.insert(identity())
        with closing(self.connect()) as db:
            db.execute('UPDATE research_evidence_v1 SET payload=?', (json.dumps(identity('changed')),))
            db.commit()
        with self.assertRaises(EvidenceError):
            store.latest_verified(self.connect, 'issuer_identity', 'A', NOW)

    def test_invalid_record_shape_has_domain_error(self):
        for payload in ([], None, {}, {'source': []}, {'source': {'id': 'partial'}}):
            with self.subTest(payload=payload), self.assertRaises(EvidenceError):
                self.insert(payload)

    def test_invalid_key_has_domain_error(self):
        payload = identity()
        for kind, subject in (([], 'A'), ('unknown', 'A'), ('issuer_identity', []), ('issuer_identity', ' ')):
            with self.subTest(kind=kind, subject=subject), self.assertRaises(EvidenceError):
                store.import_record(self.connect, kind=kind, subject=subject, payload=payload, at=NOW)

    def test_invalid_import_timezone_has_domain_error(self):
        naive = NOW.replace(tzinfo=None)
        payload = identity()
        with self.assertRaises(EvidenceError):
            self.insert(payload, at=naive)

    def test_history_bound_never_becomes_partial_success(self):
        for i in range(3):
            self.insert(identity(audit=str(i)))
        with patch('backend.evidence_history.MAX_HISTORY_ROWS', 2):
            with self.assertRaises(EvidenceError):
                store.latest_verified(self.connect, 'issuer_identity', 'A', NOW)

    def test_import_timestamp_is_normalized(self):
        offset = timezone(timedelta(hours=3))
        self.insert(identity(), at=NOW.astimezone(offset))
        with closing(self.connect()) as db:
            timestamp = db.execute('SELECT imported_at FROM research_evidence_v1').fetchone()[0]
        self.assertEqual(timestamp, NOW.isoformat())


if __name__ == '__main__':
    unittest.main()
