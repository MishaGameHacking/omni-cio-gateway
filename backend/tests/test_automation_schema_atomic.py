"""Synthetic controller startup regressions; no lifespan, network or real account.

Writing these scenarios is not evidence that they have passed on an owner host.
"""
from contextlib import closing
import sqlite3
from types import SimpleNamespace

import pytest

SCHEMA_QUERY = "SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
EVENT_INDEX = 'automation_events_user'
QUERIES = {
    'n00_retained': 'SELECT * FROM n00_retained ORDER BY rowid',
    'automation_preferences': 'SELECT * FROM automation_preferences ORDER BY user_id',
    'automation_observations': 'SELECT * FROM automation_observations ORDER BY user_id,broker_key',
    'automation_discovery': 'SELECT * FROM automation_discovery ORDER BY user_id',
    'automation_events': 'SELECT * FROM automation_events ORDER BY user_id,id',
}
OBSERVATION_INSERT = 'INSERT INTO automation_observations VALUES (?,?,?,?)'
DISCOVERY_INSERT = 'INSERT INTO automation_discovery VALUES (?,?,?,?,?,?,?,?,?,?,?)'
EVENT_INSERT = 'INSERT INTO automation_events VALUES (?,?,?,?,?,?)'


def connect_file(path, *, timeout=3, factory=sqlite3.Connection):
    db = sqlite3.connect(path, timeout=timeout, factory=factory)
    db.row_factory = sqlite3.Row
    return db


@pytest.fixture
def controller(tmp_path, monkeypatch):
    for key, value in {
        'DATABASE_PATH': str(tmp_path / 'unused-lifespan.sqlite3'),
        'TELEGRAM_CLIENT_ID': '123456', 'TELEGRAM_CLIENT_SECRET': 'test-only',
        'BACKEND_PUBLIC_URL': 'https://example.invalid',
        'FERNET_KEY': 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=',
        'ANALYSIS_SCHEDULER_ENABLED': 'false', 'AI_EXTERNAL_PROCESSING_APPROVED': 'false',
    }.items():
        monkeypatch.setenv(key, value)
    from backend import app as backend
    from backend import autonomous_controller as module
    path = tmp_path / 'synthetic-controller.sqlite3'
    monkeypatch.setattr(backend, 'DATABASE_PATH', path)
    monkeypatch.setattr(backend, 'connect', lambda: connect_file(path))

    def forbidden(*_args, **_kwargs):
        raise AssertionError('schema startup attempted collection or model work')

    for name in ('enqueue_collection', 'observe_and_discover', 'record_initial_observation',
                 '_claim_discovery', '_collect_discovery', 'configured_route'):
        monkeypatch.setattr(module, name, forbidden)
    monkeypatch.setattr(module.details, 'BrokerReader', forbidden)
    monkeypatch.setattr(module.catalogue, 'load_catalogue', forbidden)
    return SimpleNamespace(module=module, backend=backend, path=path)


def snapshot(path):
    with closing(connect_file(path)) as db:
        schema = [tuple(row) for row in db.execute(SCHEMA_QUERY)]
        tables = {name for kind, name, _ in schema if kind == 'table'}
        rows = {name: [tuple(row) for row in db.execute(query)]
                for name, query in QUERIES.items() if name in tables}
    return schema, rows


def seed(controller, *, populated=False):
    with closing(connect_file(controller.path)) as db, db:
        db.execute('CREATE TABLE n00_retained (value BLOB NOT NULL)')
        db.execute('INSERT INTO n00_retained VALUES (?)', (b'synthetic-unrelated-binding',))
    if not populated:
        return
    controller.module.initialize()
    with closing(connect_file(controller.path)) as db, db:
        db.executemany('INSERT INTO automation_preferences VALUES (?,?,?,?)', [
            (101, 0, 7, 11), (202, 1, 4, 12),
        ])
        db.executemany(OBSERVATION_INSERT, [
            (101, 'synthetic-old-connection', 1, 'first-old'),
            (101, 'synthetic-current-connection', 2, 'first-current'),
            (202, 'synthetic-current-connection', 3, 'first-other-user'),
        ])
        result = '{"state":"partial","candidates":[],"reasons":[],"as_of":"2020-01-01T00:00:00Z"}'
        db.executemany(DISCOVERY_INSERT, [
            (101, 'synthetic-current-connection', 'snapshot-old', 7, 'running', result,
             10, 9, 'expired-worker', 1, 1234),
            (202, 'synthetic-current-connection', 'snapshot-other', 4, 'paused', None,
             12, 11, None, None, 73),
        ])
        db.executemany(EVENT_INSERT, [
            (101, 'synthetic-old-connection', 'same-event', 'initial_observation', '{"old":true}', 1),
            (202, 'synthetic-current-connection', 'same-event', 'initial_observation', '{"other":true}', 2),
        ])


def denying_factory(path, expected_action, expected_name):
    opened, refused = [], []

    def connect():
        db = connect_file(path)
        opened.append(db)

        def authorizer(action, first, _second, _database, _trigger):
            if (action, first) == (expected_action, expected_name):
                refused.append((action, first))
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        db.set_authorizer(authorizer)
        return db

    return connect, opened, refused


def assert_closed(opened):
    assert opened
    for db in opened:
        with pytest.raises(sqlite3.ProgrammingError, match='closed database'):
            db.execute('SELECT 1')


@pytest.mark.parametrize('action,name', [
    (sqlite3.SQLITE_CREATE_TABLE, 'automation_events'),
    (sqlite3.SQLITE_CREATE_INDEX, EVENT_INDEX),
    (sqlite3.SQLITE_TRANSACTION, 'COMMIT'),
])
def test_late_refusal_rolls_back_all_controller_objects(controller, monkeypatch, action, name):
    seed(controller)
    before = snapshot(controller.path)
    connect, opened, refused = denying_factory(controller.path, action, name)
    with monkeypatch.context() as patch:
        patch.setattr(controller.backend, 'connect', connect)
        with pytest.raises(sqlite3.DatabaseError):
            controller.module.initialize()
    assert (action, name) in refused
    assert snapshot(controller.path) == before
    assert_closed(opened)
    controller.module.initialize()
    schema, rows = snapshot(controller.path)
    assert {name for _, name, _ in schema} == set(QUERIES) | {EVENT_INDEX}
    assert rows['n00_retained'] == before[1]['n00_retained']


@pytest.mark.parametrize('action,name', [
    (sqlite3.SQLITE_CREATE_INDEX, EVENT_INDEX), (sqlite3.SQLITE_TRANSACTION, 'COMMIT'),
])
def test_index_repair_preserves_rows_and_really_restores_schema(controller, monkeypatch, action, name):
    seed(controller, populated=True)
    healthy = snapshot(controller.path)
    assert any(kind == 'index' and identifier == EVENT_INDEX for kind, identifier, _ in healthy[0])
    with closing(connect_file(controller.path)) as db, db:
        db.execute('DROP INDEX automation_events_user')
    broken = snapshot(controller.path)
    assert not any(identifier == EVENT_INDEX for _, identifier, _ in broken[0])
    connect, opened, refused = denying_factory(controller.path, action, name)
    with monkeypatch.context() as patch:
        patch.setattr(controller.backend, 'connect', connect)
        with pytest.raises(sqlite3.DatabaseError):
            controller.module.initialize()
    assert (action, name) in refused
    assert snapshot(controller.path) == broken
    assert_closed(opened)
    controller.module.initialize()
    assert snapshot(controller.path) == healthy


def test_interrupt_after_index_creation_does_not_commit_partial_startup(controller, monkeypatch):
    seed(controller)
    before = snapshot(controller.path)
    opened, written = [], []

    class InterruptedConnection(sqlite3.Connection):
        def execute(self, statement, parameters=()):
            cursor = super().execute(statement, parameters)
            if 'CREATE INDEX IF NOT EXISTS automation_events_user' in statement:
                written.append(True)
                raise KeyboardInterrupt('synthetic-after-controller-index')
            return cursor

    def connect():
        db = connect_file(controller.path, factory=InterruptedConnection)
        opened.append(db)
        return db

    monkeypatch.setattr(controller.backend, 'connect', connect)
    with pytest.raises(KeyboardInterrupt, match='synthetic-after-controller-index'):
        controller.module.initialize()
    assert written == [True]
    assert snapshot(controller.path) == before
    assert_closed(opened)


def test_restart_preserves_pause_expired_lease_cursor_and_connection_history(controller):
    from fastapi import HTTPException
    seed(controller, populated=True)
    before = snapshot(controller.path)
    controller.module.initialize()
    controller.module.initialize()
    assert snapshot(controller.path) == before
    assert controller.module.preferences(101)['enabled'] is False
    assert controller.module.preferences(101)['version'] == 7
    assert controller.module.preferences(202)['enabled'] is True
    with pytest.raises(HTTPException) as caught:
        controller.module.assert_enabled(101)
    assert caught.value.status_code == 409 and caught.value.detail == 'automation_paused'
    assert snapshot(controller.path) == before


def test_schema_starts_with_write_reservation_and_commits_once(controller, monkeypatch):
    traced, opened = [], []

    def connect():
        db = connect_file(controller.path)
        db.set_trace_callback(traced.append)
        opened.append(db)
        return db

    monkeypatch.setattr(controller.backend, 'connect', connect)
    controller.module.initialize()
    statements = [' '.join(statement.upper().split()) for statement in traced]
    assert statements[0] == 'BEGIN IMMEDIATE'
    assert statements[-1] == 'COMMIT'
    assert statements.count('BEGIN IMMEDIATE') == statements.count('COMMIT') == 1
    assert len(statements[1:-1]) == 5
    assert all(statement.startswith('CREATE ') for statement in statements[1:-1])
    assert_closed(opened)


@pytest.mark.parametrize('populated', (False, True))
def test_concurrent_startups_preserve_state_and_close_handles(controller, monkeypatch, populated):
    # Shared probe keeps strong references and checks on the creating threads;
    # the probe itself has a deliberately leaking-initializer regression.
    from backend.tests.test_workspace_state_schema_atomic import concurrent_startups
    seed(controller, populated=populated)
    before = snapshot(controller.path)[1]
    concurrent_startups(controller, monkeypatch, controller.module.initialize)
    schema, rows = snapshot(controller.path)
    assert {name for _, name, _ in schema} == set(QUERIES) | {EVENT_INDEX}
    assert all(rows[name] == values for name, values in before.items())


def test_occupied_write_lock_does_not_create_controller_tables(controller, monkeypatch):
    seed(controller)
    before = snapshot(controller.path)
    opened = []

    def connect():
        db = connect_file(controller.path, timeout=0)
        opened.append(db)
        return db

    monkeypatch.setattr(controller.backend, 'connect', connect)
    with closing(connect_file(controller.path)) as writer:
        writer.execute('BEGIN IMMEDIATE')
        try:
            with pytest.raises(sqlite3.OperationalError) as caught:
                controller.module.initialize()
            assert caught.value.sqlite_errorcode == sqlite3.SQLITE_BUSY
        finally:
            writer.rollback()
    assert snapshot(controller.path) == before
    assert_closed(opened)


def test_event_deduplication_and_user_partition_survive_startup(controller):
    seed(controller, populated=True)
    with closing(connect_file(controller.path)) as db, db:
        for user_id in (101, 202):
            controller.module._event_in(db, user_id, 'synthetic-key', 'synthetic-kind',
                                        'same-identity', 'Synthetic title', 'Not a real event', 100)
    before = snapshot(controller.path)
    controller.module.initialize()
    with closing(connect_file(controller.path)) as db, db:
        for user_id in (101, 202):
            controller.module._event_in(db, user_id, 'synthetic-key', 'synthetic-kind',
                                        'same-identity', 'Changed title', 'Not a new observation', 200)
    assert snapshot(controller.path) == before
    added = [row for row in before[1]['automation_events'] if row[3] == 'synthetic-kind']
    assert len(added) == 2 and {row[0] for row in added} == {101, 202}
    assert all(row[5] == 100 for row in added)
