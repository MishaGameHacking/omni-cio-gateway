"""N00 core-auth startup regressions on temporary synthetic databases only.

The real init_db/device migration is exercised without entering ASGI lifespan.
Child initializers are observed separately; no all-startup atomicity is implied.
No Telegram, broker, production database or device installation is contacted.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import sqlite3
import threading
from types import SimpleNamespace

import pytest

CLOCK = 1_800_000_000
DEVICE_TABLE = 'workspace_session_devices'
USER_INSERT = '''INSERT INTO users
    (id,telegram_sub,telegram_id,name,username,picture,tinvest_token_encrypted,created_at,updated_at)
    VALUES (?,?,?,?,?,?,?,?,?)'''
SESSION_INSERT = 'INSERT INTO sessions VALUES (?,?,?)'
DEVICE_INSERT = 'INSERT INTO workspace_session_devices VALUES (?,?,?,?,?)'
SCHEMA_QUERY = "SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
ROW_QUERIES = {
    'n00_owner_sentinel': 'SELECT * FROM n00_owner_sentinel ORDER BY key',
    'users': 'SELECT * FROM users ORDER BY id',
    'login_transactions': 'SELECT * FROM login_transactions ORDER BY state',
    'login_codes': 'SELECT * FROM login_codes ORDER BY code_hash',
    'sessions': 'SELECT * FROM sessions ORDER BY token_hash',
    DEVICE_TABLE: 'SELECT * FROM workspace_session_devices ORDER BY token_hash',
    'broker_connection_versions': 'SELECT * FROM broker_connection_versions ORDER BY user_id',
}
CORE_OBJECTS = {'users', 'login_transactions', 'login_codes', 'sessions',
                'users_private_limit', DEVICE_TABLE}
CHILD_NAMES = ('client_updates', 'broker_connections', 'client_diagnostics')


def connect_file(path, *, timeout=3, factory=sqlite3.Connection):
    db = sqlite3.connect(path, timeout=timeout, factory=factory)
    db.row_factory = sqlite3.Row
    return db


def snapshot(path):
    with closing(connect_file(path)) as db:
        schema = [tuple(row) for row in db.execute(SCHEMA_QUERY)]
        names = {name for kind, name, _sql in schema if kind == 'table'}
        rows = {name: [tuple(row) for row in db.execute(query)]
                for name, query in ROW_QUERIES.items() if name in names}
    return schema, rows


@pytest.fixture
def context(tmp_path, monkeypatch):
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
    from backend import volume_devices
    path = tmp_path / 'synthetic-auth.sqlite3'
    monkeypatch.setattr(backend, 'DATABASE_PATH', path)
    monkeypatch.setattr(backend, 'connect', lambda: connect_file(path))
    monkeypatch.setattr(volume_devices, 'time', SimpleNamespace(time=lambda: CLOCK))
    calls, originals = [], {}

    def observer(name):
        def initialize(_connect):
            # Another connection must already see committed core tables.
            objects = {row[1] for row in snapshot(path)[0]}
            assert CORE_OBJECTS <= objects
            calls.append(name)
        return initialize

    for name in CHILD_NAMES:
        module = getattr(backend, name)
        originals[name] = module.initialize
        monkeypatch.setattr(module, 'initialize', observer(name))
    return SimpleNamespace(backend=backend, devices=volume_devices, path=path,
                           child_calls=calls, child_originals=originals)


def seed_sentinel(path):
    with closing(connect_file(path)) as db, db:
        db.execute('CREATE TABLE n00_owner_sentinel (key TEXT PRIMARY KEY,value BLOB NOT NULL)')
        db.executemany('INSERT INTO n00_owner_sentinel VALUES (?,?)', [
            ('synthetic-installation-binding', b'unchanged-owner-placeholder'),
            ('synthetic-strategy-version', b'unchanged-version-7'),
        ])


def seed_legacy(context):
    seed_sentinel(context.path)
    context.backend.init_db()
    context.child_calls.clear()
    with closing(connect_file(context.path)) as db, db:
        for user_id in (101, 202):
            db.execute(USER_INSERT, (user_id, f'synthetic-sub-{user_id}', f'synthetic-id-{user_id}',
                'Synthetic user', None, None, b'synthetic-ciphertext-not-a-credential', 1, 2))
        db.executemany(SESSION_INSERT, [
            ('retained-session', 101, CLOCK + 50),
            ('missing-device-a', 101, CLOCK + 100),
            ('missing-device-b', 202, 1),
        ])
        db.executemany(DEVICE_INSERT, [
            ('retained-session', 'retained-device-id', 'Saved label', 4, 5),
            ('orphan-session', 'orphan-device-id', 'Orphan label', 6, 7),
        ])
        db.execute('INSERT INTO login_transactions VALUES (?,?,?)', ('synthetic-state', 'synthetic-verifier', 1))
        db.executemany('INSERT INTO login_codes VALUES (?,?,?,?)', [
            ('synthetic-unused', 101, CLOCK + 100, 0), ('synthetic-used', 202, 1, 1),
        ])
        # Re-creation of this core trigger must roll back with a failed backfill.
        db.execute('DROP TRIGGER users_private_limit')


def rejecting_factory(path, predicate):
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


@pytest.mark.parametrize('action,name', [
    (sqlite3.SQLITE_CREATE_TRIGGER, 'users_private_limit'),
    (sqlite3.SQLITE_CREATE_TABLE, DEVICE_TABLE),
    (sqlite3.SQLITE_DELETE, DEVICE_TABLE),
    (sqlite3.SQLITE_TRANSACTION, 'COMMIT'),
])
def test_fresh_startup_refusal_rolls_back_core_and_device_schema(context, monkeypatch, action, name):
    seed_sentinel(context.path)
    before = snapshot(context.path)
    connect, opened, refused = rejecting_factory(
        context.path, lambda code, value: (code, value) == (action, name)
    )
    with monkeypatch.context() as patch:
        patch.setattr(context.backend, 'connect', connect)
        with pytest.raises(sqlite3.DatabaseError):
            context.backend.init_db()
    assert (action, name) in refused
    assert snapshot(context.path) == before
    assert context.child_calls == []
    assert_closed(opened)
    context.backend.init_db()
    assert context.child_calls == list(CHILD_NAMES)
    assert snapshot(context.path)[1]['n00_owner_sentinel'] == before[1]['n00_owner_sentinel']


@pytest.mark.parametrize('action,name', [
    (sqlite3.SQLITE_DELETE, DEVICE_TABLE), (sqlite3.SQLITE_TRANSACTION, 'COMMIT'),
])
def test_legacy_refusal_preserves_auth_rows_and_missing_trigger(context, monkeypatch, action, name):
    seed_legacy(context)
    before = snapshot(context.path)
    connect, opened, refused = rejecting_factory(
        context.path, lambda code, value: (code, value) == (action, name)
    )
    monkeypatch.setattr(context.backend, 'connect', connect)
    with pytest.raises(sqlite3.DatabaseError):
        context.backend.init_db()
    assert (action, name) in refused
    assert snapshot(context.path) == before
    assert not context.child_calls
    assert_closed(opened)


@pytest.mark.parametrize('error_type', (sqlite3.OperationalError, KeyboardInterrupt))
def test_failure_after_device_insert_restores_deleted_orphan_and_prior_inserts(context, monkeypatch, error_type):
    seed_legacy(context)
    before = snapshot(context.path)
    opened, writes = [], []

    class InterruptedConnection(sqlite3.Connection):
        def execute(self, statement, parameters=()):
            result = super().execute(statement, parameters)
            if statement.lstrip().startswith('INSERT INTO workspace_session_devices'):
                writes.append(parameters[0])
                if len(writes) == 2:
                    raise error_type('synthetic-failure-after-second-device-write')
            return result

    def connect():
        db = connect_file(context.path, factory=InterruptedConnection)
        opened.append(db)
        return db

    monkeypatch.setattr(context.backend, 'connect', connect)
    with pytest.raises(error_type, match='synthetic-failure-after-second-device-write'):
        context.backend.init_db()
    assert set(writes) == {'missing-device-a', 'missing-device-b'}
    assert snapshot(context.path) == before
    assert not context.child_calls
    assert_closed(opened)


def test_reinitialization_preserves_sessions_codes_credentials_and_device_ids(context):
    seed_legacy(context)
    before_rows = snapshot(context.path)[1]
    context.backend.init_db()
    first = snapshot(context.path)
    for table, rows in before_rows.items():
        if table != DEVICE_TABLE:
            assert first[1][table] == rows
    devices = {row[0]: row for row in first[1][DEVICE_TABLE]}
    assert devices['retained-session'] == ('retained-session', 'retained-device-id', 'Saved label', 4, 5)
    assert 'orphan-session' not in devices
    assert set(devices) == {row[0] for row in before_rows['sessions']}
    assert len({row[1] for row in devices.values()}) == len(devices)
    assert devices['missing-device-b'][3:] == (0, 0)
    assert devices['missing-device-a'][3:] == (
        CLOCK + 100 - context.backend.SESSION_TTL,
        CLOCK + 100 - context.backend.SESSION_TTL,
    )
    context.backend.init_db()
    assert snapshot(context.path) == first


def test_core_commit_precedes_child_initializers_and_occurs_once(context, monkeypatch):
    statements, opened = [], []

    def connect():
        db = connect_file(context.path)
        db.set_trace_callback(statements.append)
        opened.append(db)
        return db

    monkeypatch.setattr(context.backend, 'connect', connect)
    context.backend.init_db()
    normalized = [' '.join(value.upper().split()) for value in statements]
    assert normalized[0] == 'BEGIN IMMEDIATE'
    assert normalized[-1] == 'COMMIT'
    assert normalized.count('COMMIT') == normalized.count('BEGIN IMMEDIATE') == 1
    assert any(value.startswith('DELETE FROM WORKSPACE_SESSION_DEVICES') for value in normalized)
    assert context.child_calls == list(CHILD_NAMES)
    assert_closed(opened)


def test_two_core_initializers_do_not_duplicate_or_replace_device_mapping(context, monkeypatch):
    seed_legacy(context)
    original_rows = snapshot(context.path)[1]
    barrier = threading.Barrier(2, timeout=5)

    def connect():
        db = connect_file(context.path)
        try:
            barrier.wait()
        except BaseException:
            db.close()
            raise
        return db

    monkeypatch.setattr(context.backend, 'connect', connect)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(context.backend.init_db) for _ in range(2)]
        for future in futures:
            future.result(timeout=10)
    rows = snapshot(context.path)[1]
    assert rows['users'] == original_rows['users']
    assert rows['sessions'] == original_rows['sessions']
    devices = {row[0]: row for row in rows[DEVICE_TABLE]}
    assert len(devices) == len(rows['sessions']) == 3
    assert devices['retained-session'][1:] == ('retained-device-id', 'Saved label', 4, 5)
    assert sorted(context.child_calls) == sorted(list(CHILD_NAMES) * 2)


def test_busy_writer_prevents_partial_core_startup(context, monkeypatch):
    seed_sentinel(context.path)
    before = snapshot(context.path)
    opened = []

    def connect():
        db = connect_file(context.path, timeout=0)
        opened.append(db)
        return db

    monkeypatch.setattr(context.backend, 'connect', connect)
    with closing(connect_file(context.path)) as writer:
        writer.execute('BEGIN IMMEDIATE')
        try:
            with pytest.raises(sqlite3.OperationalError) as caught:
                context.backend.init_db()
            assert caught.value.sqlite_errorcode == sqlite3.SQLITE_BUSY
        finally:
            writer.rollback()
    assert snapshot(context.path) == before
    assert not context.child_calls
    assert_closed(opened)


def test_private_user_limit_trigger_is_preserved(context):
    context.backend.init_db()
    with closing(connect_file(context.path)) as db, db:
        for index in range(context.backend.MAX_PRIVATE_USERS):
            db.execute(USER_INSERT, (index + 1, f'synthetic-user-{index}', None, None, None, None, None, 1, 1))
        with pytest.raises(sqlite3.IntegrityError, match=context.backend.PRIVATE_USER_LIMIT_ERROR):
            db.execute(USER_INSERT, (100, 'synthetic-extra-user', None, None, None, None, None, 1, 1))
        assert db.execute('SELECT COUNT(*) FROM users').fetchone()[0] == context.backend.MAX_PRIVATE_USERS


def test_real_child_registries_remain_idempotent_without_network(context, monkeypatch):
    seed_legacy(context)
    for name, original in context.child_originals.items():
        monkeypatch.setattr(getattr(context.backend, name), 'initialize', original)

    def forbidden(*_args, **_kwargs):
        raise AssertionError('startup attempted a remote authentication or broker call')

    monkeypatch.setattr(context.backend.httpx, 'Client', forbidden)
    monkeypatch.setattr(context.backend, 'tinvest_ssl_context', forbidden)
    context.backend.init_db()
    before = snapshot(context.path)
    assert len(before[1]['broker_connection_versions']) == 2
    context.backend.init_db()
    assert snapshot(context.path) == before


def test_child_failure_is_not_misrepresented_as_whole_startup_rollback(context, monkeypatch):
    def fail(_connect):
        raise RuntimeError('synthetic-child-initializer-failed')

    monkeypatch.setattr(context.backend.client_updates, 'initialize', fail)
    with pytest.raises(RuntimeError, match='synthetic-child-initializer-failed'):
        context.backend.init_db()
    # Each child has its own transaction; the core was already committed.
    assert CORE_OBJECTS <= {row[1] for row in snapshot(context.path)[0]}
    assert not context.child_calls
