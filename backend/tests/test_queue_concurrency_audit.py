"""Real SQLite concurrency checks; never call a provider or broker."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest

from backend.ai_budget import BudgetDenied, MoneyLedger
from backend.ai_jobs import AnalysisQueue, LeaseLost

SCHEMA_QUERY = 'PRAGMA table_info(ai_work_jobs)'
LEGACY_SCHEMA = '''
CREATE TABLE ai_work_jobs (
    id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, bucket INTEGER NOT NULL,
    status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
    due_at INTEGER NOT NULL, owner TEXT, expires_at INTEGER, result_json TEXT,
    error_code TEXT, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL,
    UNIQUE(user_id, bucket)
);
'''


class QueueConcurrencyAuditTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / 'audit.sqlite'

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def legacy_database(self):
        with closing(self.connect()) as db:
            db.executescript(LEGACY_SCHEMA)
            db.execute("INSERT INTO ai_work_jobs "
                       "(id,user_id,bucket,status,due_at,created_at,updated_at) "
                       "VALUES ('kept',1,1,'queued',300,300,300)")
            db.commit()

    def test_simultaneous_legacy_migration_is_serialized(self):
        self.legacy_database()
        barrier = threading.Barrier(2)

        class CoordinatedConnection(sqlite3.Connection):
            def execute(connection, sql, parameters=(), /):
                cursor = super().execute(sql, parameters)
                if sql == SCHEMA_QUERY and not connection.in_transaction:
                    # Materialize actual pre-migration rows, then force both
                    # unprotected readers to observe the same legacy schema.
                    rows = cursor.fetchall()
                    barrier.wait(timeout=5)
                    return iter(rows)
                return cursor

        def connect():
            return sqlite3.connect(self.path, timeout=10, factory=CoordinatedConnection)

        with ThreadPoolExecutor(max_workers=2) as pool:
            tasks = [pool.submit(AnalysisQueue(connect).initialize) for _ in range(2)]
            for task in tasks:
                task.result(timeout=15)
        with closing(self.connect()) as db:
            columns = [row[1] for row in db.execute(SCHEMA_QUERY)]
            self.assertEqual(columns.count('cancel_requested_at'), 1)
            self.assertEqual(db.execute('SELECT id FROM ai_work_jobs').fetchone()[0], 'kept')

    def test_migration_failure_rolls_back_and_can_be_retried(self):
        self.legacy_database()

        class FailingConnection(sqlite3.Connection):
            def execute(connection, sql, parameters=(), /):
                if sql.startswith('ALTER TABLE'):
                    raise sqlite3.OperationalError('injected migration failure')
                return super().execute(sql, parameters)

        queue = AnalysisQueue(lambda: sqlite3.connect(self.path, factory=FailingConnection))
        with self.assertRaisesRegex(sqlite3.OperationalError, 'injected'):
            queue.initialize()
        AnalysisQueue(self.connect).initialize()
        with closing(self.connect()) as db:
            row = db.execute("SELECT cancel_requested_at FROM ai_work_jobs WHERE id='kept'").fetchone()
            self.assertIsNone(row[0])

    def test_concurrent_enqueue_coalesces_and_claim_has_one_owner(self):
        queue = AnalysisQueue(self.connect)
        queue.initialize()
        with ThreadPoolExecutor(max_workers=8) as pool:
            responses = list(pool.map(lambda _: queue.enqueue(1, at=600), range(16)))
            claims = list(pool.map(lambda _: queue.claim(at=601), range(16)))
        self.assertEqual(len({row['job_id'] for row in responses}), 1)
        self.assertEqual(sum(not row['coalesced'] for row in responses), 1)
        self.assertEqual(sum(row is not None for row in claims), 1)

    def test_expired_owner_cannot_finish_new_work(self):
        queue = AnalysisQueue(self.connect)
        queue.initialize()
        queue.enqueue(1, at=600)
        old = queue.claim(at=600)
        queue.enqueue(1, at=1600)
        current = queue.claim(at=1600)
        self.assertNotEqual(old['id'], current['id'])
        with self.assertRaises(LeaseLost):
            queue.finish(old, {'state': 'done'}, at=1600)
        self.assertTrue(queue.has_uncertain(1))
        queue.assert_owner(current['id'], current['owner'], at=1600)

    def test_concurrent_reservations_cannot_overrun_project_cap(self):
        ledger = MoneyLedger(self.connect)
        ledger.initialize()

        def reserve(index):
            try:
                ledger.reserve(user_id=index + 1, key=str(index), route='route-' + str(index),
                               model='synthetic', ceiling=100, user_cap=500, project_cap=500, at=600)
                return True
            except BudgetDenied as error:
                if str(error) != 'ai_project_budget_exhausted':
                    raise
                return False

        with ThreadPoolExecutor(max_workers=8) as pool:
            accepted = list(pool.map(reserve, range(16)))
        self.assertEqual(sum(accepted), 5)
        with closing(self.connect()) as db:
            self.assertEqual(db.execute('SELECT SUM(charge) FROM ai_money_reservations').fetchone()[0], 500)

    def test_user_budget_counts_unresolved_calls_across_midnight(self):
        ledger = MoneyLedger(self.connect)
        ledger.initialize()
        ledger.reserve(user_id=1, key='first', route='one', model='synthetic', ceiling=100,
                       user_cap=100, project_cap=1000, at=600)
        ledger.uncertain('first')
        with self.assertRaisesRegex(BudgetDenied, 'ai_user_budget_exhausted'):
            ledger.reserve(user_id=1, key='next-day', route='two', model='synthetic', ceiling=1,
                           user_cap=100, project_cap=1000, at=87000)


if __name__ == '__main__':
    unittest.main()
