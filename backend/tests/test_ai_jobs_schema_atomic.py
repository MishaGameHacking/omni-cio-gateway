"""N00 queue migrations: synthetic temporary databases, never a live account.

These scenarios exercise the real initializer, not a replacement SQL routine.
Source-only candidate: execution on the owner host is still required.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import sqlite3
import threading

import pytest

from backend.ai_jobs import AnalysisQueue
from backend.schema_migrations import SchemaMigrationError, schema_statements

TABLE = 'ai_work_jobs'
OUTSTANDING_INDEX = 'ai_work_one_outstanding_user'
DUE_INDEX = 'ai_work_due'
CANCEL_COLUMN = 'cancel_requested_at'
SENTINEL = b'synthetic-preserved-not-a-real-secret'
LEGACY_SCHEMA = '''CREATE TABLE ai_work_jobs (
    id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, bucket INTEGER NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('queued','running','completed','failed','uncertain')),
    attempts INTEGER NOT NULL DEFAULT 0, due_at INTEGER NOT NULL, owner TEXT,
    expires_at INTEGER, result_json TEXT, error_code TEXT,
    created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL,
    UNIQUE(user_id,bucket))'''
JOB_INSERT = '''INSERT INTO ai_work_jobs
    (id,user_id,bucket,status,attempts,due_at,owner,expires_at,result_json,error_code,created_at,updated_at)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)'''


def connect(path):
    return sqlite3.connect(path, timeout=5)


def seed(path, legacy=False):
    with closing(connect(path)) as db, db:
        db.execute('CREATE TABLE synthetic_preserved (value BLOB NOT NULL)')
        db.execute('INSERT INTO synthetic_preserved VALUES (?)', (SENTINEL,))
        if legacy:
            db.execute(LEGACY_SCHEMA)
            for index, status in enumerate(('queued', 'running', 'uncertain', 'completed', 'failed'), 1):
                db.execute(JOB_INSERT, (f'synthetic-{status}', index, index, status, 2,
                    1700000000, 'synthetic-worker', 1700000900, '{"synthetic":true}',
                    'synthetic-retained', 1700000000, 1700000001))


def materialized(path):
    with closing(connect(path)) as db:
        objects = db.execute('SELECT type,name,sql FROM sqlite_master ORDER BY type,name').fetchall()
        names = {row[1] for row in objects}
        jobs = db.execute('SELECT * FROM ai_work_jobs ORDER BY id').fetchall() if TABLE in names else []
        preserved = db.execute('SELECT value FROM synthetic_preserved').fetchall()
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        return objects, jobs, preserved


def denying_factory(path, predicate, opened, refusals):
    def factory():
        db = connect(path)
        opened.append(db)
        def authorize(action, first, second, _database, _trigger):
            if predicate(action, first, second):
                refusals.append((action, first, second))
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        db.set_authorizer(authorize)
        return db
    return factory


def assert_closed(db):
    with pytest.raises(sqlite3.ProgrammingError):
        db.execute('SELECT 1')


@pytest.mark.parametrize('denied_name', [OUTSTANDING_INDEX, DUE_INDEX])
def test_late_index_failure_rolls_back_new_queue(tmp_path, denied_name):
    path = tmp_path / 'synthetic.sqlite3'
    seed(path)
    before = materialized(path)
    opened, refusals = [], []
    factory = denying_factory(path,
        lambda action, first, _second: action == sqlite3.SQLITE_CREATE_INDEX and first == denied_name,
        opened, refusals)
    queue = AnalysisQueue(factory)
    with pytest.raises(sqlite3.DatabaseError):
        queue.initialize()
    assert len(refusals) == 1
    assert materialized(path) == before
    assert_closed(opened[0])


def test_failed_legacy_alter_also_rolls_back_new_indexes(tmp_path):
    path = tmp_path / 'legacy.sqlite3'
    seed(path, legacy=True)
    before = materialized(path)
    opened, refusals = [], []
    factory = denying_factory(path,
        lambda action, _first, second: action == sqlite3.SQLITE_ALTER_TABLE and second == TABLE,
        opened, refusals)
    queue = AnalysisQueue(factory)
    with pytest.raises(sqlite3.DatabaseError):
        queue.initialize()
    assert len(refusals) == 1
    assert materialized(path) == before
    assert_closed(opened[0])
    # A retry without the injected refusal upgrades rather than deleting jobs.
    AnalysisQueue(lambda: connect(path)).initialize()
    _, upgraded, preserved = materialized(path)
    assert [row[:-1] for row in upgraded] == before[1]
    assert all(row[-1] is None for row in upgraded)
    assert preserved == [(SENTINEL,)]


@pytest.mark.parametrize('legacy', [False, True])
def test_denied_commit_rolls_back_and_closes_the_initializer(tmp_path, legacy):
    path = tmp_path / 'commit-refusal.sqlite3'
    seed(path, legacy=legacy)
    before = materialized(path)
    opened, refusals = [], []
    factory = denying_factory(path,
        lambda action, first, _second: action == sqlite3.SQLITE_TRANSACTION and first == 'COMMIT',
        opened, refusals)
    queue = AnalysisQueue(factory)
    with pytest.raises(sqlite3.DatabaseError):
        queue.initialize()
    assert len(refusals) == 1
    assert materialized(path) == before
    assert_closed(opened[0])


def test_initializer_keeps_cancellation_lease_and_uncertain_job_fields(tmp_path):
    path = tmp_path / 'preservation.sqlite3'
    seed(path, legacy=True)
    queue = AnalysisQueue(lambda: connect(path))
    queue.initialize()
    with closing(connect(path)) as db, db:
        db.execute("UPDATE ai_work_jobs SET cancel_requested_at=? WHERE status='running'", (1700000002,))
    before = materialized(path)
    for _ in range(3):
        queue.initialize()
        assert materialized(path) == before
    assert queue.has_uncertain(3)


@pytest.mark.parametrize('legacy', [False, True])
def test_parallel_initializers_share_one_serialized_migration(tmp_path, legacy):
    path = tmp_path / 'parallel.sqlite3'
    seed(path, legacy=legacy)
    before = materialized(path)
    barrier = threading.Barrier(2, timeout=10)
    def initialize():
        def factory():
            db = connect(path)
            try:
                barrier.wait()
            except BaseException:
                db.close()
                raise
            return db
        AnalysisQueue(factory).initialize()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(initialize) for _ in range(2)]
        for future in futures:
            future.result(timeout=15)
    with closing(connect(path)) as db:
        columns = [row[1] for row in db.execute('PRAGMA table_info(ai_work_jobs)')]
        indexes = {row[1] for row in db.execute('PRAGMA index_list(ai_work_jobs)')}
    assert columns.count(CANCEL_COLUMN) == 1
    assert {OUTSTANDING_INDEX, DUE_INDEX} <= indexes
    _, jobs, preserved = materialized(path)
    assert [row[:-1] for row in jobs] == before[1]
    assert preserved == [(SENTINEL,)]


def test_interrupted_legacy_migration_leaves_all_old_bytes_logically_intact(tmp_path):
    path = tmp_path / 'interrupt.sqlite3'
    seed(path, legacy=True)
    before = materialized(path)
    opened = []
    class InterruptedConnection(sqlite3.Connection):
        def execute(self, statement, parameters=()):
            if statement.startswith('ALTER TABLE ai_work_jobs'):
                raise KeyboardInterrupt('synthetic-interruption')
            return super().execute(statement, parameters)
    def factory():
        db = sqlite3.connect(path, factory=InterruptedConnection)
        opened.append(db)
        return db
    queue = AnalysisQueue(factory)
    with pytest.raises(KeyboardInterrupt):
        queue.initialize()
    assert materialized(path) == before
    assert_closed(opened[0])


def test_schema_and_column_upgrade_have_one_commit_boundary(tmp_path):
    path = tmp_path / 'trace.sqlite3'
    seed(path, legacy=True)
    trace = []
    def factory():
        db = connect(path)
        db.set_trace_callback(trace.append)
        return db
    AnalysisQueue(factory).initialize()
    normalized = [item.strip().upper() for item in trace]
    assert normalized[0] == 'BEGIN IMMEDIATE'
    assert normalized[-1] == 'COMMIT'
    assert normalized.count('COMMIT') == 1
    assert normalized.count('BEGIN IMMEDIATE') == 1
    assert any(item.startswith('ALTER TABLE AI_WORK_JOBS') for item in normalized[1:-1])


def test_outstanding_job_uniqueness_survives_legacy_upgrade(tmp_path):
    path = tmp_path / 'uniqueness.sqlite3'
    seed(path, legacy=True)
    AnalysisQueue(lambda: connect(path)).initialize()
    with closing(connect(path)) as db, db:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(JOB_INSERT, ('synthetic-duplicate', 1, 99, 'running', 0,
                1700000000, None, None, None, None, 1700000000, 1700000000))
        assert db.execute("SELECT COUNT(*) FROM ai_work_jobs WHERE user_id=1").fetchone()[0] == 1


@pytest.mark.parametrize('prefix', [
    ' ' * 10000, '/* synthetic prefix */' * 1000,
    '-- first; comment\r\n /* second; comment */ \t',
])
def test_comment_prefixes_preserve_statement_boundaries(prefix):
    statement = prefix + 'CREATE TABLE synthetic_one (value TEXT);'
    assert schema_statements(statement) == (statement,)


@pytest.mark.parametrize('script', [
    'CREATE TABLE synthetic_one (id); /* unfinished',
    '-- comment only\n /* finished */',
    '/* first */ -- next\n COMMIT;',
])
def test_comment_handling_does_not_hide_invalid_schema(script):
    with pytest.raises(SchemaMigrationError):
        schema_statements(script)
