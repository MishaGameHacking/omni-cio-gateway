"""N00 workspace-state regressions using isolated synthetic SQLite databases.

The application lifespan, scheduler, broker and paid model routes are not run.
These scenarios remain unverified until executed on an authorized owner host.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import sqlite3
import threading
from types import SimpleNamespace

import pytest

SCHEMA_SQL = "SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
QUERIES = {
    'n00_retained': 'SELECT * FROM n00_retained ORDER BY key',
    'workspace_snapshots': 'SELECT * FROM workspace_snapshots ORDER BY user_id,currency',
    'workspace_records': 'SELECT * FROM workspace_records ORDER BY user_id,kind,id',
    'workspace_strategy_versions': 'SELECT * FROM workspace_strategy_versions ORDER BY user_id,version',
    'workspace_strategy_previews': 'SELECT * FROM workspace_strategy_previews ORDER BY id',
    'workspace_events': 'SELECT * FROM workspace_events ORDER BY id',
    'workspace_request_receipts': 'SELECT * FROM workspace_request_receipts ORDER BY user_id,request_id',
}
SNAPSHOT_INSERT = 'INSERT INTO workspace_snapshots VALUES (?,?,?,?,?,?)'
VERSION_INSERT = 'INSERT INTO workspace_strategy_versions VALUES (?,?,?,?,?,?,?,?)'
PREVIEW_INSERT = 'INSERT INTO workspace_strategy_previews VALUES (?,?,?,?,?,?,?,?,?)'
RECEIPT_INSERT = 'INSERT INTO workspace_request_receipts VALUES (?,?,?,?,?,?)'
EVENT_INDEX = 'workspace_events_user'


def connect_file(path, *, timeout=3, factory=sqlite3.Connection):
    db = sqlite3.connect(path, timeout=timeout, factory=factory)
    db.row_factory = sqlite3.Row
    return db


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    for key, value in {
        'DATABASE_PATH': str(tmp_path / 'unused-lifespan.sqlite3'),
        'TELEGRAM_CLIENT_ID': '123456', 'TELEGRAM_CLIENT_SECRET': 'test-only',
        'BACKEND_PUBLIC_URL': 'https://example.invalid',
        'FERNET_KEY': 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=',
        'ANALYSIS_SCHEDULER_ENABLED': 'false', 'AI_EXTERNAL_PROCESSING_APPROVED': 'false',
    }.items():
        monkeypatch.setenv(key, value)
    from backend import app as backend
    from backend import volume_state as state
    path = tmp_path / 'synthetic-state.sqlite3'
    monkeypatch.setattr(backend, 'DATABASE_PATH', path)
    monkeypatch.setattr(backend, 'connect', lambda: connect_file(path))
    return SimpleNamespace(state=state, backend=backend, path=path)


def snapshot(path):
    with closing(connect_file(path)) as db:
        schema = [tuple(row) for row in db.execute(SCHEMA_SQL)]
        tables = {name for kind, name, _ in schema if kind == 'table'}
        rows = {name: [tuple(row) for row in db.execute(query)]
                for name, query in QUERIES.items() if name in tables}
    return schema, rows


def seed_sentinel(path):
    with closing(connect_file(path)) as db, db:
        db.execute('CREATE TABLE n00_retained (key TEXT PRIMARY KEY, value BLOB NOT NULL)')
        db.execute('INSERT INTO n00_retained VALUES (?,?)', ('synthetic-unrelated', b'unchanged'))


def synthetic_user(identifier):
    return {'id': identifier, 'tinvest_token_encrypted': f'synthetic-placeholder-{identifier}'.encode()}


def seed_state(workspace):
    state = workspace.state
    state.initialize()
    with closing(connect_file(workspace.path)) as db, db:
        for user_id in (101, 202):
            for currency in ('RUB', 'USD'):
                db.execute(SNAPSHOT_INSERT, (
                    user_id, currency, f'snapshot-{user_id}-{currency}', state.broker_key(synthetic_user(user_id)),
                    state.encode({'as_of': '2020-01-01T00:00:00+00:00', 'currency': currency,
                                  'positions': [], 'synthetic_owner': user_id}), 1,
                ))
            db.execute('INSERT INTO workspace_records VALUES (?,?,?,?,?,?,?)', (
                user_id, 'risk_check', 'shared-local-id', '{"state":"to_review"}', 7, 1, 2,
            ))
            for version in (1, 2):
                db.execute(VERSION_INSERT, (
                    user_id, version, state.encode({'synthetic_version': version, 'owner': user_id}),
                    f'snapshot-{user_id}-RUB', version - 1, 'synthetic-reason', f'request-{version}', version,
                ))
            for label, expires, consumed in (('expired', 1, None), ('consumed', 2, 3), ('pending', 32503680000, None)):
                db.execute(PREVIEW_INSERT, (
                    f'{user_id}-{label}', user_id, 2, f'snapshot-{user_id}-RUB', '{"draft":"retained"}',
                    '{"coverage":"unknown"}', expires, 'synthetic-preview', consumed,
                ))
            db.execute('INSERT INTO workspace_events VALUES (?,?,?,?,?,?)', (
                f'event-{user_id}', user_id, 'risk_synthetic', f'snapshot-{user_id}-RUB',
                '{"synthetic":true,"occurred_at":"2020-01-01T00:00:00+00:00"}', 1,
            ))
            db.execute(RECEIPT_INSERT, (user_id, 'shared-request-id', 'synthetic', 'retained-hash', '{"ok":true}', 1))


def denying_factory(path, expected_action, expected_name):
    opened, refused = [], []

    def connect():
        db = connect_file(path)
        opened.append(db)

        def authorize(action, first, _second, _database, _trigger):
            if (action, first) == (expected_action, expected_name):
                refused.append((action, first))
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        db.set_authorizer(authorize)
        return db

    return connect, opened, refused


def assert_closed(opened):
    assert opened
    for db in opened:
        # A wrong-thread ProgrammingError is not evidence that close() ran.
        with pytest.raises(sqlite3.ProgrammingError, match='closed database'):
            db.execute('SELECT 1')


@pytest.mark.parametrize('action,name', [
    (sqlite3.SQLITE_CREATE_TABLE, 'workspace_request_receipts'),
    (sqlite3.SQLITE_CREATE_INDEX, EVENT_INDEX),
    (sqlite3.SQLITE_TRANSACTION, 'COMMIT'),
])
def test_late_failure_rolls_back_every_new_state_object(workspace, monkeypatch, action, name):
    seed_sentinel(workspace.path)
    before = snapshot(workspace.path)
    factory, opened, refused = denying_factory(workspace.path, action, name)
    with monkeypatch.context() as patch:
        patch.setattr(workspace.backend, 'connect', factory)
        with pytest.raises(sqlite3.DatabaseError):
            workspace.state.initialize()
    assert (action, name) in refused
    assert snapshot(workspace.path) == before
    assert_closed(opened)
    workspace.state.initialize()
    schema, rows = snapshot(workspace.path)
    assert {name for _, name, _ in schema} == set(QUERIES) | {EVENT_INDEX}
    assert rows['n00_retained'] == before[1]['n00_retained']


@pytest.mark.parametrize('action,name', [
    (sqlite3.SQLITE_CREATE_INDEX, EVENT_INDEX), (sqlite3.SQLITE_TRANSACTION, 'COMMIT'),
])
def test_failed_index_repair_retains_every_saved_value(workspace, monkeypatch, action, name):
    seed_state(workspace)
    healthy = snapshot(workspace.path)
    assert any(kind == 'index' and identifier == EVENT_INDEX for kind, identifier, _ in healthy[0])
    with closing(connect_file(workspace.path)) as db, db:
        db.execute('DROP INDEX workspace_events_user')
    before = snapshot(workspace.path)
    assert not any(identifier == EVENT_INDEX for _, identifier, _ in before[0])
    factory, opened, refused = denying_factory(workspace.path, action, name)
    with monkeypatch.context() as patch:
        patch.setattr(workspace.backend, 'connect', factory)
        with pytest.raises(sqlite3.DatabaseError):
            workspace.state.initialize()
    assert (action, name) in refused
    assert snapshot(workspace.path) == before
    assert_closed(opened)
    workspace.state.initialize()
    # Reopen independently: rows alone cannot establish that the index persisted.
    repaired = snapshot(workspace.path)
    assert repaired == healthy
    assert repaired[1] == before[1]


def test_interrupt_after_final_table_does_not_leave_partial_schema(workspace, monkeypatch):
    seed_sentinel(workspace.path)
    before = snapshot(workspace.path)
    opened, completed = [], []

    class InterruptedConnection(sqlite3.Connection):
        def execute(self, statement, parameters=()):
            cursor = super().execute(statement, parameters)
            if 'CREATE TABLE IF NOT EXISTS workspace_request_receipts' in statement:
                completed.append(True)
                raise KeyboardInterrupt('synthetic-after-receipts')
            return cursor

    def connect():
        db = connect_file(workspace.path, factory=InterruptedConnection)
        opened.append(db)
        return db

    monkeypatch.setattr(workspace.backend, 'connect', connect)
    with pytest.raises(KeyboardInterrupt, match='synthetic-after-receipts'):
        workspace.state.initialize()
    assert completed == [True]
    assert snapshot(workspace.path) == before
    assert_closed(opened)


def test_reinitialization_never_confirms_expires_or_refreshes_saved_state(workspace):
    seed_state(workspace)
    before = snapshot(workspace.path)
    active = workspace.state.strategy_data(101)
    workspace.state.initialize()
    workspace.state.initialize()
    assert snapshot(workspace.path) == before
    assert workspace.state.strategy_data(101) == active
    assert active['active']['version'] == 2
    assert len(active['history']) == 2
    assert workspace.state.saved_snapshot(synthetic_user(101))['as_of'].startswith('2020-01-01')


def test_broker_and_user_snapshot_isolation_survives_restart(workspace):
    seed_state(workspace)
    workspace.state.initialize()
    state = workspace.state
    assert state.saved_snapshot(synthetic_user(101))['snapshot_id'] == 'snapshot-101-RUB'
    assert state.saved_snapshot(synthetic_user(202), 'USD')['snapshot_id'] == 'snapshot-202-USD'
    assert state.saved_snapshot(synthetic_user(303)) is None
    assert state.saved_snapshot({**synthetic_user(101), 'tinvest_token_encrypted': b'changed-placeholder'}) is None
    assert state.saved_snapshot({**synthetic_user(101), 'tinvest_token_encrypted': None}) is None


def test_single_write_transaction_starts_before_first_create(workspace, monkeypatch):
    traced, opened = [], []

    def connect():
        db = connect_file(workspace.path)
        db.set_trace_callback(traced.append)
        opened.append(db)
        return db

    monkeypatch.setattr(workspace.backend, 'connect', connect)
    workspace.state.initialize()
    statements = [' '.join(sql.upper().split()) for sql in traced]
    assert statements[0] == 'BEGIN IMMEDIATE' and statements[-1] == 'COMMIT'
    assert statements.count('BEGIN IMMEDIATE') == statements.count('COMMIT') == 1
    assert len(statements[1:-1]) == 7
    assert all(sql.startswith('CREATE ') for sql in statements[1:-1])
    assert_closed(opened)


def concurrent_startups(workspace, monkeypatch, initialize):
    """Retain handles and prove closure on each handle's owning thread."""
    barrier = threading.Barrier(2, timeout=5)
    lock = threading.Lock()
    opened, verified = [], []

    def connect():
        db = connect_file(workspace.path)
        with lock:
            opened.append((threading.get_ident(), db))
        try:
            barrier.wait()
        except BaseException:
            db.close()
            raise
        return db

    def worker():
        thread_id = threading.get_ident()
        try:
            initialize()
        finally:
            with lock:
                owned = [db for creator, db in opened if creator == thread_id]
            try:
                assert len(owned) == 1
                assert_closed(owned)
                with lock:
                    verified.append(thread_id)
            finally:
                # Cleanup follows the assertion, so it cannot hide a leaked handle.
                # This also runs on the owning thread; check_same_thread stays on.
                for db in owned:
                    db.close()

    with monkeypatch.context() as patch:
        patch.setattr(workspace.backend, 'connect', connect)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker) for _ in range(2)]
            for future in futures:
                future.result(timeout=10)
    assert len(opened) == len(verified) == 2
    assert {creator for creator, _ in opened} == set(verified)
    assert len(set(verified)) == 2


@pytest.mark.parametrize('populated', (False, True))
def test_concurrent_initializers_preserve_existing_versions(workspace, monkeypatch, populated):
    seed_sentinel(workspace.path)
    if populated:
        seed_state(workspace)
    before = snapshot(workspace.path)[1]
    concurrent_startups(workspace, monkeypatch, workspace.state.initialize)
    schema, rows = snapshot(workspace.path)
    assert {name for _, name, _ in schema} == set(QUERIES) | {EVENT_INDEX}
    assert all(rows[name] == values for name, values in before.items())


def test_concurrent_closure_probe_detects_a_retained_open_handle(workspace, monkeypatch):
    # Deliberately faulty synthetic initializer: the probe must fail BEFORE its
    # own cleanup. Retained references prevent GC from closing the leaked handle.
    def leaking_initializer():
        db = workspace.backend.connect()
        db.execute('SELECT 1')

    with pytest.raises(pytest.fail.Exception, match='DID NOT RAISE'):
        concurrent_startups(workspace, monkeypatch, leaking_initializer)


def test_busy_writer_leaves_no_partial_schema(workspace, monkeypatch):
    seed_sentinel(workspace.path)
    before = snapshot(workspace.path)
    opened = []

    def connect():
        db = connect_file(workspace.path, timeout=0)
        opened.append(db)
        return db

    monkeypatch.setattr(workspace.backend, 'connect', connect)
    with closing(connect_file(workspace.path)) as writer:
        writer.execute('BEGIN IMMEDIATE')
        try:
            with pytest.raises(sqlite3.OperationalError) as caught:
                workspace.state.initialize()
            assert caught.value.sqlite_errorcode == sqlite3.SQLITE_BUSY
        finally:
            writer.rollback()
    assert snapshot(workspace.path) == before
    assert_closed(opened)


def test_saved_request_is_replayed_without_creating_a_second_goal(workspace):
    from fastapi import HTTPException
    state = workspace.state
    state.initialize()
    request = state.GoalWrite(request_id='synthetic-goal-request', title='Synthetic goal',
                             target=state.MoneyInput(amount='1000.25', currency='RUB'),
                             reserve=state.MoneyInput(amount='100', currency='RUB'))
    first = state.save_goal(request, synthetic_user(101))
    other = state.save_goal(request, synthetic_user(202))
    before = snapshot(workspace.path)
    state.initialize()
    assert state.save_goal(request, synthetic_user(101)) == first
    assert state.save_goal(request, synthetic_user(202)) == other
    assert first['id'] != other['id']
    with pytest.raises(HTTPException) as caught:
        state.save_goal(request.model_copy(update={'title': 'Different synthetic goal'}), synthetic_user(101))
    assert caught.value.status_code == 409
    assert snapshot(workspace.path) == before


def test_startup_preserves_uniqueness_constraints(workspace):
    seed_state(workspace)
    workspace.state.initialize()
    before = snapshot(workspace.path)
    with closing(connect_file(workspace.path)) as db:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(VERSION_INSERT, (101, 3, '{}', 'snapshot', 2, 'duplicate', 'request-1', 3))
        db.rollback()
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(RECEIPT_INSERT, (101, 'shared-request-id', 'different', 'different-hash', '{}', 2))
        db.rollback()
    assert snapshot(workspace.path) == before


def test_scenario_comparison_still_requires_two_variants(workspace):
    from pydantic import ValidationError
    state = workspace.state
    variant = state.ScenarioVariant(id='synthetic', title='Synthetic scenario',
                                    shocks=[state.Shock(axis='all', id='all', percent='-10')])
    with pytest.raises(ValidationError):
        state.ScenarioComparison(scenarios=[variant])
    assert len(state.ScenarioComparison(scenarios=[variant, variant.model_copy(update={'id': 'second'})]).scenarios) == 2
