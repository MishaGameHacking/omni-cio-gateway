"""Synthetic instants and real SQLite reads; no portfolio or network access."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import json
import sqlite3
import unittest
from unittest.mock import patch

from backend import research_clock as clock
from backend.evidence_history import HistoryUnavailable, read_history

NOW = datetime(2026, 10, 14, 8, tzinfo=timezone.utc)
SOON = NOW + timedelta(seconds=30)


class ResearchClockTests(unittest.TestCase):
    def setUp(self):
        # Each test owns a distinct identity; production has no registry reset.
        self.key = ('synthetic', self.id())
        self.window = clock.window_for(self.key, at=NOW)

    def test_before_expiry_reuses_same_window(self):
        self.assertIs(clock.window_for(self.key, at=SOON), self.window)

    def test_default_lifetime_is_bounded(self):
        self.assertTrue(self.window.current(NOW + timedelta(seconds=299)))
        self.assertFalse(self.window.current(NOW + timedelta(seconds=300)))

    def test_boundary_equality_requires_new_window(self):
        self.window.note(SOON)
        self.assertFalse(self.window.current(SOON))
        self.assertNotEqual(clock.window_for(self.key, at=SOON).serial, self.window.serial)

    def test_earliest_boundary_wins(self):
        for value in (SOON, NOW + timedelta(seconds=20), NOW + timedelta(seconds=40)):
            self.window.note(value)
        self.assertEqual(self.window.deadline, NOW + timedelta(seconds=20))

    def test_past_boundaries_do_not_create_a_refresh_loop(self):
        self.window.note(NOW - timedelta(seconds=1))
        self.window.note(NOW)
        self.assertEqual(self.window.deadline, NOW + timedelta(seconds=300))

    def test_far_boundary_never_extends_ttl(self):
        self.window.note(NOW + timedelta(days=1))
        self.assertEqual(self.window.deadline, NOW + timedelta(seconds=300))

    def test_backward_clock_cannot_reuse_a_future_assessment(self):
        before = NOW - timedelta(microseconds=1)
        self.assertFalse(self.window.current(before))
        self.assertNotEqual(clock.window_for(self.key, at=before).serial, self.window.serial)

    def test_naive_registry_time_rejected(self):
        naive = NOW.replace(tzinfo=None)
        with self.assertRaises(ValueError):
            clock.window_for(self.key, at=naive)

    def test_naive_expiry_rejected(self):
        naive = SOON.replace(tzinfo=None)
        with self.assertRaises(ValueError):
            self.window.note(naive)

    def test_observation_is_scoped(self):
        clock.note_time(SOON)
        self.assertEqual(self.window.deadline, NOW + timedelta(seconds=300))
        with self.window.observing():
            clock.note_time(SOON)
        self.assertEqual(self.window.deadline, SOON)

    def test_nested_observers_restore_parent(self):
        other = clock.window_for((*self.key, 'nested'), at=NOW)
        with self.window.observing():
            with other.observing():
                clock.note_time(SOON)
            clock.note_time(NOW + timedelta(seconds=50))
        self.assertEqual(other.deadline, SOON)
        self.assertEqual(self.window.deadline, NOW + timedelta(seconds=50))

    def test_failure_does_not_leak_context(self):
        failure = RuntimeError('synthetic')
        observation = self.window.observing()
        with self.assertRaisesRegex(RuntimeError, 'synthetic') as raised:
            with observation:
                raise failure
        self.assertIs(raised.exception, failure)
        clock.note_time(SOON)
        self.assertEqual(self.window.deadline, NOW + timedelta(seconds=300))

    def test_source_checked_and_publication_boundaries_observed(self):
        with self.window.observing():
            clock.note_source({'published_at': SOON.isoformat(),
                               'checked_at': (SOON + timedelta(seconds=1)).isoformat(),
                               'expires_at': (NOW + timedelta(days=1)).isoformat()})
        self.assertEqual(self.window.deadline, SOON)

    def test_different_timezone_has_same_boundary(self):
        with self.window.observing():
            clock.note_time(SOON.astimezone(timezone(timedelta(hours=3))).isoformat())
        self.assertEqual(self.window.deadline, SOON)

    def test_malformed_observation_does_not_validate_evidence(self):
        with self.window.observing():
            for invalid in (None, [], 1, 'invalid', 'x' * 1000, '2026-10-14T08:00:30'):
                clock.note_time(invalid)
        self.assertEqual(self.window.deadline, NOW + timedelta(seconds=300))

    def test_registry_is_bounded_and_eviction_never_reuses_token(self):
        with patch.object(clock, 'MAX_WINDOWS', 2):
            first = clock.window_for((*self.key, 'first'), at=NOW)
            clock.window_for((*self.key, 'second'), at=NOW)
            clock.window_for((*self.key, 'third'), at=NOW)
            self.assertLessEqual(len(clock._WINDOWS), 2)
            again = clock.window_for((*self.key, 'first'), at=NOW)
        self.assertNotEqual(first.serial, again.serial)

    def test_concurrent_callers_share_one_generation(self):
        def obtain(_):
            return clock.window_for(self.key, at=SOON).serial
        with ThreadPoolExecutor(max_workers=8) as executor:
            serials = list(executor.map(obtain, range(100)))
        self.assertEqual(set(serials), {self.window.serial})

    def test_thread_contexts_do_not_share_observations(self):
        with self.window.observing(), ThreadPoolExecutor(max_workers=1) as executor:
            executor.submit(clock.note_time, SOON).result(timeout=5)
        self.assertEqual(self.window.deadline, NOW + timedelta(seconds=300))


class HistoryClockTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.db.execute('CREATE TABLE research_evidence_v1(digest TEXT,kind TEXT,subject TEXT,payload TEXT,imported_at TEXT)')
        self.window = clock.window_for(('history-clock', self.id()), at=NOW)

    def insert(self, *, available=NOW, expires=SOON, checked=NOW, digest_override=None):
        value = {'source': {'published_at': NOW.isoformat(),
                            'checked_at': checked.isoformat(), 'expires_at': expires.isoformat()}}
        text = json.dumps(value)
        digest = hashlib.sha256(('rating:A:' + text).encode()).hexdigest()
        self.db.execute('INSERT INTO research_evidence_v1 VALUES(?,?,?,?,?)',
                        (digest_override or digest, 'rating', 'A', text, available.isoformat()))
        self.db.commit()

    def test_real_read_observes_expiry(self):
        self.insert()
        with self.window.observing():
            result = read_history(self.db, 'rating', 'A', at=NOW)
        self.assertEqual(len(result), 1)
        self.assertEqual(self.window.deadline, SOON)

    def test_future_import_is_hidden_but_changes_next_cache_boundary(self):
        self.insert(available=SOON, expires=NOW + timedelta(days=1))
        with self.window.observing():
            result = read_history(self.db, 'rating', 'A', at=NOW)
        self.assertEqual(result, [])
        self.assertEqual(self.window.deadline, SOON)
        self.assertEqual(len(read_history(self.db, 'rating', 'A', at=SOON)), 1)

    def test_future_review_is_a_boundary(self):
        self.insert(checked=SOON, expires=NOW + timedelta(days=1))
        with self.window.observing():
            read_history(self.db, 'rating', 'A', at=NOW)
        self.assertEqual(self.window.deadline, SOON)

    def test_unrelated_subject_does_not_shorten_window(self):
        self.insert()
        with self.window.observing():
            self.assertEqual(read_history(self.db, 'rating', 'B', at=NOW), [])
        self.assertEqual(self.window.deadline, NOW + timedelta(seconds=300))

    def test_integrity_failure_is_not_swallowed_by_observer(self):
        self.insert(digest_override='0' * 64)
        with self.window.observing(), self.assertRaises(HistoryUnavailable):
            read_history(self.db, 'rating', 'A', at=NOW)


if __name__ == '__main__':
    unittest.main()
