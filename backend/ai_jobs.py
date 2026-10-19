"""Persistent, coalescing analysis queue for the existing SQLite deployment.

Claim is atomic across processes; each user has at most one outstanding job.
An expired worker is marked uncertain, not blindly replayed: a paid request may
already have left the process. New deterministic checks may proceed, but paid
calls for that user are suspended until the uncertain work is reconciled. Read-only collection failures retry with a bound.
"""
from __future__ import annotations

from contextlib import closing
from contextvars import ContextVar
import json
import sqlite3
import time
import uuid
from typing import Callable

try:
    from .ai_budget import Connect, transaction
except ImportError:
    from ai_budget import Connect, transaction

CURRENT_JOB: ContextVar[tuple[str, str] | None] = ContextVar('analyst_current_job', default=None)
MAX_ATTEMPTS = 3
LEASE_SECONDS = 900


class LeaseLost(RuntimeError):
    pass


class AnalysisQueue:
    def __init__(self, connect: Connect):
        self.connect = connect

    def initialize(self) -> None:
        with closing(self.connect()) as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS ai_work_jobs (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    bucket INTEGER NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('queued','running','completed','failed','uncertain')),
                    attempts INTEGER NOT NULL DEFAULT 0,
                    due_at INTEGER NOT NULL,
                    owner TEXT,
                    expires_at INTEGER,
                    result_json TEXT,
                    error_code TEXT,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    cancel_requested_at INTEGER,
                    UNIQUE(user_id,bucket)
                );
                CREATE UNIQUE INDEX IF NOT EXISTS ai_work_one_outstanding_user
                    ON ai_work_jobs(user_id) WHERE status IN ('queued','running');
                CREATE INDEX IF NOT EXISTS ai_work_due ON ai_work_jobs(status,due_at);
            ''')
            # executescript commits independently. Acquire the write reservation
            # AFTER it, before reading the legacy schema, so two starting
            # workers cannot both attempt the same ADD COLUMN migration.
            db.execute('BEGIN IMMEDIATE')
            columns = {row[1] for row in db.execute('PRAGMA table_info(ai_work_jobs)')}
            if 'cancel_requested_at' not in columns:
                db.execute('ALTER TABLE ai_work_jobs ADD COLUMN cancel_requested_at INTEGER')
            db.commit()

    @staticmethod
    def _expire(db: sqlite3.Connection, now: int) -> None:
        db.execute("UPDATE ai_work_jobs SET status='uncertain',error_code='worker_lease_expired',updated_at=? "
                   "WHERE status='running' AND expires_at<=?", (now, now))

    def enqueue(self, user_id: int, *, at: int | None = None) -> dict:
        if type(user_id) is not int or user_id <= 0:
            raise ValueError('invalid_job_user')
        now = int(time.time()) if at is None else at
        with transaction(self.connect) as db:
            return self.enqueue_in(db, user_id, now=now)

    def enqueue_in(self, db, user_id: int, *, now: int | None = None) -> dict:
        """Bind a client request and an analysis job in the same transaction."""
        now = int(time.time()) if now is None else now
        self._expire(db, now)
        row = db.execute("SELECT id,status FROM ai_work_jobs WHERE user_id=? AND "
                         "(status IN ('queued','running') OR bucket=?) ORDER BY created_at DESC LIMIT 1",
                         (user_id, now // 300)).fetchone()
        if row:
            return {'job_id': row[0], 'state': row[1], 'coalesced': True}
        identifier = uuid.uuid4().hex
        db.execute("INSERT INTO ai_work_jobs(id,user_id,bucket,status,due_at,created_at,updated_at) VALUES (?,?,?,'queued',?,?,?)",
                   (identifier, user_id, now // 300, now, now, now))
        return {'job_id': identifier, 'state': 'queued', 'coalesced': False}

    def cancel(self, user_id: int, identifier: str) -> None:
        now = int(time.time())
        with transaction(self.connect) as db:
            db.execute("UPDATE ai_work_jobs SET status='failed',error_code='analysis_cancelled',cancel_requested_at=?,updated_at=? WHERE id=? AND user_id=? AND status='queued'",
                       (now, now, identifier, user_id))
            db.execute("UPDATE ai_work_jobs SET cancel_requested_at=?,updated_at=? WHERE id=? AND user_id=? AND status='running'", (now, now, identifier, user_id))

    def acknowledge_cancel(self, job: dict) -> None:
        with transaction(self.connect) as db:
            row = db.execute("SELECT user_id,created_at FROM ai_work_jobs WHERE id=? AND owner=? AND status='running' AND cancel_requested_at IS NOT NULL", (job['id'], job['owner'])).fetchone()
            if row is None:
                return
            unresolved = db.execute("SELECT 1 FROM ai_money_reservations WHERE user_id=? AND created_at>=? AND state IN ('reserved','uncertain')", (row['user_id'], row['created_at'])).fetchone()
            db.execute("UPDATE ai_work_jobs SET status=?,error_code=?,updated_at=? WHERE id=? AND owner=?",
                       ('uncertain' if unresolved else 'failed', 'analysis_paid_outcome_unknown' if unresolved else 'analysis_cancelled', int(time.time()), job['id'], job['owner']))

    def claim(self, *, at: int | None = None) -> dict | None:
        now = int(time.time()) if at is None else at
        with transaction(self.connect) as db:
            self._expire(db, now)
            row = db.execute("SELECT id,user_id,attempts FROM ai_work_jobs WHERE status='queued' AND due_at<=? ORDER BY due_at,id LIMIT 1", (now,)).fetchone()
            if row is None:
                return None
            owner = uuid.uuid4().hex
            db.execute("UPDATE ai_work_jobs SET status='running',attempts=attempts+1,owner=?,expires_at=?,updated_at=? WHERE id=? AND status='queued'",
                       (owner, now + LEASE_SECONDS, now, row[0]))
            return {'id': row[0], 'user_id': row[1], 'attempts': row[2] + 1, 'owner': owner}

    def assert_owner(self, identifier: str, owner: str, *, at: int | None = None) -> None:
        now = int(time.time()) if at is None else at
        with closing(self.connect()) as db:
            row = db.execute("SELECT 1 FROM ai_work_jobs WHERE id=? AND owner=? AND status='running' AND cancel_requested_at IS NULL AND expires_at>?",
                             (identifier, owner, now)).fetchone()
        if row is None:
            raise LeaseLost('analysis_worker_lease_lost')

    def finish(self, job: dict, result: dict, *, at: int | None = None) -> None:
        now = int(time.time()) if at is None else at
        # No response bodies, tokens or portfolio data are stored in job diagnostics.
        safe = {key: result.get(key) for key in ('state','reason','tier','card_id','error_code')}
        with transaction(self.connect) as db:
            cursor = db.execute("UPDATE ai_work_jobs SET status='completed',result_json=?,updated_at=? "
                                "WHERE id=? AND owner=? AND status='running' AND cancel_requested_at IS NULL AND expires_at>?",
                                (json.dumps(safe), now, job['id'], job['owner'], now))
            if cursor.rowcount != 1:
                raise LeaseLost('analysis_worker_lease_lost')

    def fail(self, job: dict, *, retryable: bool, at: int | None = None) -> None:
        now = int(time.time()) if at is None else at
        retry = retryable and job['attempts'] < MAX_ATTEMPTS
        delay = min(60 * 2 ** (job['attempts'] - 1), 600)
        with transaction(self.connect) as db:
            cursor = db.execute("UPDATE ai_work_jobs SET status=?,due_at=?,error_code=?,updated_at=? "
                                "WHERE id=? AND owner=? AND status='running' AND cancel_requested_at IS NULL AND expires_at>?",
                                ('queued' if retry else 'failed', now + delay,
                                 'collection_temporary_failure' if retryable else 'analysis_failed', now,
                                 job['id'], job['owner'], now))
            if cursor.rowcount != 1:
                raise LeaseLost('analysis_worker_lease_lost')

    def has_uncertain(self, user_id: int) -> bool:
        with closing(self.connect()) as db:
            return bool(db.execute("SELECT 1 FROM ai_work_jobs WHERE user_id=? AND status='uncertain' LIMIT 1", (user_id,)).fetchone())

    def user_status(self, user_id: int, *, at: int | None = None) -> dict:
        now = int(time.time()) if at is None else at
        with transaction(self.connect) as db:
            self._expire(db, now)
            row = db.execute("SELECT id,status,attempts,due_at,error_code,updated_at FROM ai_work_jobs WHERE user_id=? ORDER BY created_at DESC,id DESC LIMIT 1", (user_id,)).fetchone()
        if row is None:
            return {'state': 'not_scheduled'}
        return dict(zip(('job_id','state','attempts','due_at','error_code','updated_at'), row))


def drain(queue: AnalysisQueue, run: Callable[[int], dict], *, limit: int = 20) -> dict[str, int]:
    """No hidden retry of a model call: only upstream collection errors are retried."""
    counts = {'processed': 0, 'failed': 0}
    for _ in range(max(0, min(limit, 100))):
        job = queue.claim()
        if job is None:
            break
        token = CURRENT_JOB.set((job['id'], job['owner']))
        try:
            result = run(job['user_id'])
            queue.finish(job, result)
            counts['processed'] += 1
        except LeaseLost:
            queue.acknowledge_cancel(job)
            counts['failed'] += 1
        except Exception as error:
            # run_user_analysis contains/categorizes paid failures. Escaping HTTP
            # 502/503/504 here is read-only collection, before the model attempt.
            retryable = getattr(error, 'status_code', None) in (502, 503, 504)
            try:
                queue.fail(job, retryable=retryable)
            except LeaseLost:
                queue.acknowledge_cancel(job)
            counts['failed'] += 1
        finally:
            CURRENT_JOB.reset(token)
    return counts



def assert_current_owner_in(db: sqlite3.Connection) -> None:
    """Call under the caller's write transaction, before persisting its result."""
    job = CURRENT_JOB.get()
    if job is None:
        return
    row = db.execute("SELECT 1 FROM ai_work_jobs WHERE id=? AND owner=? AND status='running' AND cancel_requested_at IS NULL AND expires_at>?",
                     (*job, int(time.time()))).fetchone()
    if row is None:
        raise LeaseLost('analysis_worker_lease_lost')
