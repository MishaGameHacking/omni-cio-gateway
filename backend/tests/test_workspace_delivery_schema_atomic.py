"""N00 startup regressions for workspace jobs and the notification outbox.

Only temporary synthetic databases are used. Importing the app does not enter
its lifespan; these tests never start the scheduler, a model or a broker client.
Written scenarios are not execution evidence until run on an authorized host.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import json
import sqlite3
import threading
from types import SimpleNamespace

import pytest

SENTINEL_TABLE = 'n00_retained'
JOB_INSERT = '''INSERT INTO workspace_jobs
    (id,user_id,request_id,kind,payload_json,payload_hash,state,stage,checkpoint_json,
     result_json,error_code,cancel_requested,paid_started,owner,expires_at,created_at,updated_at)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)'''
REQUEST_INSERT = 'INSERT INTO workspace_job_requests VALUES (?,?,?,?)'
PREFERENCES_INSERT = 'INSERT INTO workspace_notification_preferences VALUES (?,?,?,?)'
OUTBOX_INSERT = 'INSERT INTO workspace_notification_outbox VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)'
SCHEMA_QUERY = "SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
QUERIES = {
    SENTINEL_TABLE: 'SELECT * FROM n00_retained ORDER BY key',
    'workspace_jobs': 'SELECT * FROM workspace_jobs ORDER BY id',
    'workspace_job_requests': 'SELECT * FROM workspace_job_requests ORDER BY user_id,request_id',
    'workspace_notification_preferences': 'SELECT * FROM workspace_notification_preferences ORDER BY user_id',
    'workspace_notification_outbox': 'SELECT * FROM workspace_notification_outbox ORDER BY id',
}
INDEXES = {
    'jobs': ('workspace_jobs_due', 'workspace_jobs_user'),
    'notifications': ('workspace_outbox_due',),
}
DROP_INDEXES = {
    'jobs': ('DROP INDEX workspace_jobs_due', 'DROP INDEX workspace_jobs_user'),
    'notifications': ('DROP INDEX workspace_outbox_due',),
}
TABLES = {
    'jobs': {'workspace_jobs', 'workspace_job_requests'},
    'notifications': {'workspace_notification_preferences', 'workspace_notification_outbox'},
}
JOB_STATES = ('queued', 'running', 'uncertain', 'cancelled', 'failed', 'completed')
NOTICE_STATES = ('pending', 'claimed', 'presented', 'read', 'suppressed')


def connect_file(path, *, timeout=3, factory=sqlite3.Connection):
    db = sqlite3.connect(path, timeout=timeout, factory=factory)
    db.row_factory = sqlite3.Row
    return db


@pytest.fixture
def modules(tmp_path, monkeypatch):
    # Set only isolated fixture values before the first possible app import.
    settings = {
        'DATABASE_PATH': str(tmp_path / 'unused-lifespan.sqlite3'),
        'TELEGRAM_CLIENT_ID': '123456', 'TELEGRAM_CLIENT_SECRET': 'test-only',
        'BACKEND_PUBLIC_URL': 'https://example.invalid',
        'FERNET_KEY': 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=',
        'ANALYSIS_SCHEDULER_ENABLED': 'false', 'AI_EXTERNAL_PROCESSING_APPROVED': 'false',
    }
    for key, value in settings.items():
        monkeypatch.setenv(key, value)
    from backend import app as backend
    from backend import volume_jobs, volume_notifications
    path = tmp_path / 'synthetic-workspace.sqlite3'
    monkeypatch.setattr(backend, 'DATABASE_PATH', path)
    monkeypatch.setattr(backend, 'connect', lambda: connect_file(path))
    return SimpleNamespace(backend=backend, jobs=volume_jobs,
                           notifications=volume_notifications, path=path)


@pytest.fixture(params=('jobs', 'notifications'))
def registry(modules, request):
    return SimpleNamespace(kind=request.param, module=getattr(modules, request.param),
                           backend=modules.backend, path=modules.path)


def snapshot(path):
    with closing(connect_file(path)) as db:
        schema = [tuple(row) for row in db.execute(SCHEMA_QUERY)]
        tables = {name for kind, name, _ in schema if kind == 'table'}
        rows = {name: [tuple(row) for row in db.execute(query)]
                for name, query in QUERIES.items() if name in tables}
    return schema, rows


def seed_sentinel(path):
    with closing(connect_file(path)) as db, db:
        db.execute('CREATE TABLE n00_retained (key TEXT PRIMARY KEY, value BLOB NOT NULL)')
        db.executemany('INSERT INTO n00_retained VALUES (?,?)', [
            ('synthetic-owner-binding', b'unchanged-owner'),
            ('synthetic-session', b'unchanged-session'),
            ('synthetic-broker-binding', b'unchanged-placeholder-not-a-token'),
            ('synthetic-strategy', b'unchanged-version-7'),
        ])


def seed_jobs(db):
    for index, state in enumerate(JOB_STATES):
        identifier, user_id = f'synthetic-job-{index}', 101 + index % 2
        request_id = f'synthetic-request-{index // 2}'
        db.execute(JOB_INSERT, (
            identifier, user_id, request_id, 'refresh', '{"currency":"RUB"}', f'hash-{index}',
            state, 'synthetic-checkpoint', '{"cursor":"retained","_progress":{"completed":2,"total":5}}',
            '{"synthetic_result":"retained"}', 'retained-diagnostic',
            int(state in {'running', 'cancelled'}), int(state in {'running', 'uncertain'}),
            'synthetic-lease-owner', 1, 1, 2,
        ))
        db.execute(REQUEST_INSERT, (user_id, request_id, identifier, f'hash-{index}'))


def seed_notifications(db, module):
    for user_id in (101, 102):
        preferences = {**module.DEFAULTS, 'enabled': False, 'morning': '10:15'}
        db.execute(PREFERENCES_INSERT, (user_id, 7, json.dumps(preferences), 123))
    for index, state in enumerate(NOTICE_STATES):
        db.execute(OUTBOX_INSERT, (
            f'synthetic-notice-{index}', 101 + index % 2, 'risk', 'Synthetic title',
            'Synthetic body, not an owner event', f'card-{index // 2}', f'event-{index // 2}',
            1, state, 2, 'synthetic-claim', 1, 3 if state in {'presented', 'read'} else None,
        ))


def prepare(registry, populated):
    seed_sentinel(registry.path)
    if not populated:
        return
    registry.module.initialize()
    with closing(connect_file(registry.path)) as db, db:
        if registry.kind == 'jobs':
            seed_jobs(db)
        else:
            seed_notifications(db, registry.module)
        for command in DROP_INDEXES[registry.kind]:
            db.execute(command)


def denying_factory(path, predicate):
    opened, refused = [], []

    def connect():
        db = connect_file(path)
        opened.append(db)

        def authorize(action, first, _second, _database, _trigger):
            if predicate(action, first):
                refused.append((action, first))
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        db.set_authorizer(authorize)
        return db

    return connect, opened, refused


def assert_closed(opened):
    assert opened
    for db in opened:
        with pytest.raises(sqlite3.ProgrammingError):
            db.execute('SELECT 1')


@pytest.mark.parametrize('populated', (False, True))
@pytest.mark.parametrize('failure', ('late-index', 'commit'))
def test_failure_restores_entire_schema_and_saved_rows(registry, monkeypatch, populated, failure):
    prepare(registry, populated)
    before = snapshot(registry.path)
    action, name = ((sqlite3.SQLITE_CREATE_INDEX, INDEXES[registry.kind][-1])
                    if failure == 'late-index' else (sqlite3.SQLITE_TRANSACTION, 'COMMIT'))
    connect, opened, refused = denying_factory(
        registry.path, lambda current_action, current_name: (current_action, current_name) == (action, name)
    )
    with monkeypatch.context() as patch:
        patch.setattr(registry.backend, 'connect', connect)
        with pytest.raises(sqlite3.DatabaseError):
            registry.module.initialize()
    assert (action, name) in refused
    assert snapshot(registry.path) == before
    assert_closed(opened)
    registry.module.initialize()
    after_schema, after_rows = snapshot(registry.path)
    for table, rows in before[1].items():
        assert after_rows[table] == rows
    assert {name for _, name, _ in after_schema} == TABLES[registry.kind] | set(INDEXES[registry.kind]) | {SENTINEL_TABLE}


@pytest.mark.parametrize('populated', (False, True))
def test_interrupt_after_late_write_rolls_back(registry, monkeypatch, populated):
    prepare(registry, populated)
    before = snapshot(registry.path)
    opened, written = [], []
    marker = 'CREATE INDEX IF NOT EXISTS ' + INDEXES[registry.kind][-1]

    class InterruptedConnection(sqlite3.Connection):
        def execute(self, statement, parameters=()):
            result = super().execute(statement, parameters)
            if marker in statement:
                written.append(marker)
                raise KeyboardInterrupt('synthetic-interruption-after-index')
            return result

    def connect():
        db = connect_file(registry.path, factory=InterruptedConnection)
        opened.append(db)
        return db

    monkeypatch.setattr(registry.backend, 'connect', connect)
    with pytest.raises(KeyboardInterrupt, match='synthetic-interruption-after-index'):
        registry.module.initialize()
    assert written == [marker]
    assert snapshot(registry.path) == before
    assert_closed(opened)


def test_reinitialization_preserves_every_lease_receipt_preference_and_ack(registry):
    prepare(registry, True)
    registry.module.initialize()
    before = snapshot(registry.path)
    registry.module.initialize()
    registry.module.initialize()
    assert snapshot(registry.path) == before
    if registry.kind == 'jobs':
        rows = before[1]['workspace_jobs']
        assert {row[6] for row in rows} == set(JOB_STATES)
        assert all(row[8] and row[13] and row[14] == 1 for row in rows)
    else:
        assert {row[8] for row in before[1]['workspace_notification_outbox']} == set(NOTICE_STATES)
        assert all(row[1] == 7 for row in before[1]['workspace_notification_preferences'])


def test_transaction_begins_before_ddl_and_has_one_commit(registry, monkeypatch):
    statements, opened = [], []

    def connect():
        db = connect_file(registry.path)
        db.set_trace_callback(statements.append)
        opened.append(db)
        return db

    monkeypatch.setattr(registry.backend, 'connect', connect)
    registry.module.initialize()
    normalized = [' '.join(value.upper().split()) for value in statements]
    assert normalized[0] == 'BEGIN IMMEDIATE'
    assert normalized[-1] == 'COMMIT'
    assert normalized.count('BEGIN IMMEDIATE') == normalized.count('COMMIT') == 1
    assert all(value.startswith('CREATE ') for value in normalized[1:-1])
    assert_closed(opened)


@pytest.mark.parametrize('populated', (False, True))
def test_concurrent_startups_preserve_the_existing_payloads(registry, monkeypatch, populated):
    prepare(registry, populated)
    before_rows = snapshot(registry.path)[1]
    barrier = threading.Barrier(2, timeout=5)

    def connect():
        db = connect_file(registry.path)
        try:
            barrier.wait()
        except BaseException:
            db.close()
            raise
        return db

    monkeypatch.setattr(registry.backend, 'connect', connect)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(registry.module.initialize) for _ in range(2)]
        for future in futures:
            future.result(timeout=10)
    schema, rows = snapshot(registry.path)
    assert {name for _, name, _ in schema} == TABLES[registry.kind] | set(INDEXES[registry.kind]) | {SENTINEL_TABLE}
    for table, expected in before_rows.items():
        assert rows[table] == expected


def test_busy_write_lock_leaves_no_partial_tables(registry, monkeypatch):
    prepare(registry, False)
    before = snapshot(registry.path)
    opened = []

    def connect():
        db = connect_file(registry.path, timeout=0)
        opened.append(db)
        return db

    monkeypatch.setattr(registry.backend, 'connect', connect)
    with closing(connect_file(registry.path)) as writer:
        writer.execute('BEGIN IMMEDIATE')
        try:
            with pytest.raises(sqlite3.OperationalError) as caught:
                registry.module.initialize()
            assert caught.value.sqlite_errorcode == sqlite3.SQLITE_BUSY
        finally:
            writer.rollback()
    assert snapshot(registry.path) == before
    assert_closed(opened)


def test_startup_does_not_dispatch_work_or_report_delivery(modules, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError('schema initialization attempted an operational action')

    for name in ('run_job', 'drain', '_expire', 'before_model_send'):
        monkeypatch.setattr(modules.jobs, name, forbidden)
    for name in ('enqueue_in', 'claim', 'acknowledge', 'due_flags'):
        monkeypatch.setattr(modules.notifications, name, forbidden)
    modules.jobs.initialize()
    modules.notifications.initialize()
    _, rows = snapshot(modules.path)
    assert rows
    assert all(not value for value in rows.values())


def test_request_id_deduplication_and_user_scope_survive_restart(modules):
    from fastapi import HTTPException
    jobs = modules.jobs
    jobs.initialize()
    request, payload = 'synthetic-same-request', {'currency': 'RUB'}
    first = jobs.enqueue(101, request, 'refresh', payload)
    other = jobs.enqueue(102, request, 'refresh', payload)
    assert first['job_id'] != other['job_id']
    before = snapshot(modules.path)
    jobs.initialize()
    assert jobs.enqueue(101, request, 'refresh', payload)['job_id'] == first['job_id']
    assert jobs.enqueue(102, request, 'refresh', payload)['job_id'] == other['job_id']
    with pytest.raises(HTTPException) as caught:
        jobs.enqueue(101, request, 'refresh', {'currency': 'USD'})
    assert caught.value.status_code == 409
    assert snapshot(modules.path) == before


def test_notification_deduplication_does_not_resend_or_cross_users(modules):
    notes = modules.notifications
    notes.initialize()
    with closing(connect_file(modules.path)) as db, db:
        preferences = {**notes.DEFAULTS, 'quiet_start': '00:00', 'quiet_end': '00:00'}
        for user_id in (101, 102):
            db.execute(PREFERENCES_INSERT, (user_id, 4, json.dumps(preferences), 1))
            notes.enqueue_in(db, user_id, kind='risk', title='Synthetic title', body='Synthetic body',
                             source_card_id='same-card', event_id='same-event', at=1700000000)
    before = snapshot(modules.path)
    notes.initialize()
    with closing(connect_file(modules.path)) as db, db:
        for user_id in (101, 102):
            notes.enqueue_in(db, user_id, kind='risk', title='Must not replace original', body='Not delivered',
                             source_card_id='same-card', event_id='same-event', at=1700000001)
    assert snapshot(modules.path) == before
    notices = before[1]['workspace_notification_outbox']
    assert len(notices) == 2
    assert {row[1] for row in notices} == {101, 102}
    assert all(row[8] == 'pending' and row[12] is None for row in notices)
