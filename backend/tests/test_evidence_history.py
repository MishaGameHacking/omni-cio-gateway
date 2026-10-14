"""Real SQLite snapshots; these records are synthetic, not market evidence."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import sqlite3
import unittest
from unittest.mock import patch

from backend.evidence_history import HistoryUnavailable, read_history

NOW = datetime(2026, 10, 13, 12, tzinfo=timezone.utc)


class EvidenceHistoryTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.db.execute('''CREATE TABLE research_evidence_v1(
            digest TEXT PRIMARY KEY,kind TEXT,subject TEXT,payload TEXT,imported_at TEXT)''')

    def insert(self, value, *, kind='issuer_identity', subject='A', imported=NOW, text=None, digest=None):
        text = json.dumps({'source': {}, 'value': value}) if text is None else text
        digest = hashlib.sha256((kind + ':' + subject + ':' + text).encode()).hexdigest() if digest is None else digest
        instant = imported.isoformat() if isinstance(imported, datetime) else imported
        self.db.execute('INSERT INTO research_evidence_v1 VALUES(?,?,?,?,?)', (digest, kind, subject, text, instant))
        return digest

    def read(self, **kwargs):
        return read_history(self.db, 'issuer_identity', 'A', **kwargs)

    def test_more_than_100_records_are_not_silently_truncated(self):
        for i in range(150):
            self.insert(i, imported=NOW + timedelta(seconds=i))
        self.assertEqual({r['value'] for r in self.read()}, set(range(150)))

    def test_old_import_not_lost_after_many_later_imports(self):
        self.insert('material_change', imported=NOW - timedelta(days=1))
        for i in range(120):
            self.insert(i)
        self.assertIn('material_change', [r['value'] for r in self.read()])

    def test_import_after_assessment_is_not_available_in_backtest(self):
        self.insert('known')
        self.insert('late', imported=NOW + timedelta(seconds=1))
        self.assertEqual([r['value'] for r in self.read(at=NOW)], ['known'])

    def test_equal_instant_with_different_offset_is_available(self):
        self.insert('known', imported='2026-10-13T15:00:00+03:00')
        self.assertEqual([r['value'] for r in self.read(at=NOW)], ['known'])

    def test_foreign_subject_and_kind_never_leak(self):
        self.insert('a')
        self.insert('b', subject='B')
        self.insert('c', kind='rating')
        self.assertEqual([r['value'] for r in self.read()], ['a'])

    def test_corrupt_digest_is_failure_not_an_older_fallback(self):
        self.insert('old')
        self.insert('changed', digest='0' * 64)
        with self.assertRaisesRegex(HistoryUnavailable, 'digest_mismatch'):
            self.read()

    def test_row_limit_is_failure_not_partial_success(self):
        for i in range(3):
            self.insert(i)
        with patch('backend.evidence_history.MAX_HISTORY_ROWS', 2):
            with self.assertRaisesRegex(HistoryUnavailable, 'row_limit'):
                self.read()

    def test_history_byte_budget_is_failure(self):
        self.insert('x' * 50)
        self.insert('y' * 50)
        with patch('backend.evidence_history.MAX_HISTORY_BYTES', 100):
            with self.assertRaisesRegex(HistoryUnavailable, 'byte_limit'):
                self.read()

    def test_single_record_size_is_bounded(self):
        self.insert('x' * 50)
        with patch('backend.evidence_history.MAX_RECORD_BYTES', 20):
            with self.assertRaisesRegex(HistoryUnavailable, 'byte_limit'):
                self.read()

    def test_bad_import_time_is_not_ignored(self):
        for moment in ('bad', '2026-10-13T12:00:00', None):
            with self.subTest(moment=moment):
                self.db.execute('DELETE FROM research_evidence_v1')
                self.insert('x', imported=moment)
                with self.assertRaisesRegex(HistoryUnavailable, 'import_time'):
                    self.read(at=NOW)

    def test_naive_assessment_rejected(self):
        moment = NOW.replace(tzinfo=None)
        with self.assertRaisesRegex(HistoryUnavailable, 'timezone_required'):
            self.read(at=moment)

    def test_duplicate_json_key_is_rejected(self):
        self.insert('x', text='{"source":{},"value":1,"value":2}')
        with self.assertRaisesRegex(HistoryUnavailable, 'invalid_evidence_json'):
            self.read()

    def test_nonfinite_json_is_rejected(self):
        self.insert('x', text='{"source":{},"value":NaN}')
        with self.assertRaises(HistoryUnavailable):
            self.read()

    def test_wrong_shape_is_rejected(self):
        for text in ('[]', '{"source": []}', '{"value":1}'):
            with self.subTest(text=text):
                self.db.execute('DELETE FROM research_evidence_v1')
                self.insert('x', text=text)
                with self.assertRaisesRegex(HistoryUnavailable, 'shape'):
                    self.read()

    def test_order_is_deterministic_for_same_records(self):
        self.insert('z')
        self.insert('a')
        first = self.read()
        self.db.execute('PRAGMA reverse_unordered_selects=ON')
        self.assertEqual(self.read(), first)

    def test_empty_history(self):
        self.assertEqual(self.read(at=NOW), [])


if __name__ == '__main__':
    unittest.main()
