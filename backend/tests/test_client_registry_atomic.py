"""Client-registry startup regressions; temporary synthetic SQLite files only.

No app import, session creation, APK publication, broker request or live DB.
These tests are source candidates until executed on an authorized owner host.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import sqlite3
import threading
from types import SimpleNamespace

import pytest

from backend import client_diagnostics as diagnostics
from backend import client_updates as updates

CLOCK = 1_800_000_000
DIAGNOSTIC_TABLE = 'client_diagnostic_events'
VERSION_TABLE = 'client_versions'
DIAGNOSTIC_INSERT = 'INSERT INTO client_diagnostic_events VALUES (?,?,?,?,?,?,?,?)'
VERSION_INSERT = 'INSERT INTO client_versions VALUES (?,?,?,?,?,?)'
MODULES = {'diagnostics': diagnostics, 'versions': updates}
LATE_INDEX = {
    'diagnostics': 'client_diagnostic_user_received',
    'versions': 'client_versions_identity',
}
OBJECTS = {
    'diagnostics': {DIAGNOSTIC_TABLE, 'client_diagnostic_received', LATE_INDEX['diagnostics']},
    'versions': {VERSION_TABLE, 'client_versions_user', LATE_INDEX['versions']},
}
DROP_INDEXES = {
    'diagnostics': (
        'DROP INDEX client_diagnostic_received',
        'DROP INDEX client_diagnostic_user_received',
    ),
    'versions': (
        'DROP INDEX client_versions_user',
        'DROP INDEX client_versions_identity',
    ),
}
ROW_QUERIES = {
    'synthetic_retained': 'SELECT * FROM synthetic_retained ORDER BY rowid',
    DIAGNOSTIC_TABLE: 'SELECT * FROM client_diagnostic_events ORDER BY user_id,event_id',
    VERSION_TABLE: 'SELECT * FROM client_versions ORDER BY session_hash',
}


@pytest.fixture(params=('diagnostics', 'versions'))
def registry(request):
    return request.param


@pytest.fixture(autouse=True)
def fixed_diagnostic_clock(monkeypatch):
    # Replace the module reference, not the shared time.time used by threads.
    monkeypatch.setattr(diagnostics, 'time', SimpleNamespace(time=lambda: CLOCK))


def connect_file(path):
    return sqlite3.connect(path, timeout=3)


def snapshot(path):
    with closing(connect_file(path)) as db:
        schema = db.execute(
            "SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
        ).fetchall()
        tables = {name for kind, name, _ in schema if kind == 'table'}
        rows = {name: db.execute(query).fetchall()
                for name, query in ROW_QUERIES.items() if name in tables}
    return schema, rows


def seed_sentinel(path):
    with closing(connect_file(path)) as db, db:
        db.execute('CREATE TABLE synthetic_retained (value TEXT NOT NULL)')
        db.execute('INSERT INTO synthetic_retained VALUES (?)', ('synthetic-sentinel',))


def seed_registry(path, registry, *, missing_indexes=False):
    MODULES[registry].initialize(lambda: connect_file(path))
    cutoff = CLOCK - diagnostics.RETENTION_SECONDS
    with closing(connect_file(path)) as db, db:
        if registry == 'diagnostics':
            db.executemany(DIAGNOSTIC_INSERT, [
                (101, 'a' * 64, cutoff - 1, 123, 'historical_exit', 49, None, '{"fixture":"expired"}'),
                (101, 'b' * 64, cutoff, 124, 'historical_exit', 49, None, '{"fixture":"boundary"}'),
                (101, 'c' * 64, cutoff + 1, 125, 'uncaught_exception', 49, 49, '{"fixture":"current"}'),
                (202, 'b' * 64, CLOCK, 126, 'historical_exit', 48, 47, '{"fixture":"other-user"}'),
            ])
        else:
            db.executemany(VERSION_INSERT, [
                ('a' * 64, 101, updates.PREVIEW_PACKAGE, 49, '1' * 64, CLOCK),
                ('b' * 64, 101, updates.PREVIEW_PACKAGE, 48, None, CLOCK - 1),
                ('c' * 64, 202, 'ru.omnicio.app', 3, '2' * 64, 1),
            ])
        if missing_indexes:
            for command in DROP_INDEXES[registry]:
                db.execute(command)


def denying_connection(path, predicate):
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


def assert_closed(connections):
    assert connections
    for db in connections:
        with pytest.raises(sqlite3.ProgrammingError):
            db.execute('SELECT 1')


def test_late_index_failure_restores_schema_and_all_existing_rows(tmp_path, registry):
    path = tmp_path / 'synthetic.sqlite3'
    seed_sentinel(path)
    before = snapshot(path)
    factory, opened, refused = denying_connection(
        path, lambda action, name: action == sqlite3.SQLITE_CREATE_INDEX and name == LATE_INDEX[registry]
    )
    with pytest.raises(sqlite3.DatabaseError):
        MODULES[registry].initialize(factory)
    assert refused == [(sqlite3.SQLITE_CREATE_INDEX, LATE_INDEX[registry])]
    assert snapshot(path) == before
    assert_closed(opened)
    # A failed startup must allow a clean retry without losing the sentinel.
    MODULES[registry].initialize(lambda: connect_file(path))
    after_schema, after_rows = snapshot(path)
    assert {row[1] for row in after_schema} == OBJECTS[registry] | {'synthetic_retained'}
    assert after_rows['synthetic_retained'] == before[1]['synthetic_retained']


@pytest.mark.parametrize('seed_existing', (False, True))
def test_refused_commit_rolls_back_new_indexes_and_retention(tmp_path, registry, seed_existing):
    path = tmp_path / 'synthetic.sqlite3'
    seed_sentinel(path)
    if seed_existing:
        seed_registry(path, registry, missing_indexes=True)
    before = snapshot(path)
    factory, opened, refused = denying_connection(
        path, lambda action, name: action == sqlite3.SQLITE_TRANSACTION and name == 'COMMIT'
    )
    with pytest.raises(sqlite3.DatabaseError):
        MODULES[registry].initialize(factory)
    assert (sqlite3.SQLITE_TRANSACTION, 'COMMIT') in refused
    assert snapshot(path) == before
    assert_closed(opened)


@pytest.mark.parametrize('seed_existing', (False, True))
def test_diagnostic_cleanup_refusal_does_not_commit_schema(tmp_path, seed_existing):
    path = tmp_path / 'synthetic.sqlite3'
    seed_sentinel(path)
    if seed_existing:
        seed_registry(path, 'diagnostics', missing_indexes=True)
    before = snapshot(path)
    factory, opened, refused = denying_connection(
        path, lambda action, name: action == sqlite3.SQLITE_DELETE and name == DIAGNOSTIC_TABLE
    )
    with pytest.raises(sqlite3.DatabaseError):
        diagnostics.initialize(factory)
    assert (sqlite3.SQLITE_DELETE, DIAGNOSTIC_TABLE) in refused
    assert snapshot(path) == before
    assert_closed(opened)


def test_interruption_after_a_write_rolls_back_and_closes(tmp_path, registry):
    path = tmp_path / 'synthetic.sqlite3'
    seed_registry(path, registry, missing_indexes=True)
    before = snapshot(path)
    opened = []
    marker = ('DELETE FROM client_diagnostic_events' if registry == 'diagnostics'
              else 'CREATE INDEX IF NOT EXISTS client_versions_identity')

    class InterruptedConnection(sqlite3.Connection):
        def execute(self, statement, parameters=()):
            result = super().execute(statement, parameters)
            if marker in statement:
                raise KeyboardInterrupt('synthetic-interruption-after-write')
            return result

    def connect():
        db = sqlite3.connect(path, timeout=3, factory=InterruptedConnection)
        opened.append(db)
        return db

    with pytest.raises(KeyboardInterrupt, match='synthetic-interruption-after-write'):
        MODULES[registry].initialize(connect)
    assert snapshot(path) == before
    assert_closed(opened)


def test_diagnostics_keep_exact_retention_boundary_and_user_partition(tmp_path):
    path = tmp_path / 'synthetic.sqlite3'
    seed_registry(path, 'diagnostics')
    before_schema, before_rows = snapshot(path)
    diagnostics.initialize(lambda: connect_file(path))
    after_schema, after_rows = snapshot(path)
    cutoff = CLOCK - diagnostics.RETENTION_SECONDS
    expected = [row for row in before_rows[DIAGNOSTIC_TABLE] if row[2] >= cutoff]
    assert after_schema == before_schema
    assert after_rows[DIAGNOSTIC_TABLE] == expected
    assert len(expected) == 3
    assert expected[0][6] is None  # Unknown exited-process version stays unknown.
    assert {row[0] for row in expected} == {101, 202}
    diagnostics.initialize(lambda: connect_file(path))
    assert snapshot(path) == (after_schema, after_rows)


def test_version_reinitialization_preserves_old_unverified_and_other_user_claims(tmp_path):
    path = tmp_path / 'synthetic.sqlite3'
    seed_registry(path, 'versions')
    before = snapshot(path)
    updates.initialize(lambda: connect_file(path))
    updates.initialize(lambda: connect_file(path))
    assert snapshot(path) == before
    rows = before[1][VERSION_TABLE]
    assert rows[1][4] is None  # No new attestation is fabricated by startup.
    assert rows[2][1] == 202
    assert rows[2][5] == 1


def test_one_transaction_starts_before_first_schema_write(tmp_path, registry):
    statements, opened = [], []

    def connect():
        db = connect_file(tmp_path / 'synthetic.sqlite3')
        db.set_trace_callback(statements.append)
        opened.append(db)
        return db

    MODULES[registry].initialize(connect)
    normalized = [' '.join(statement.upper().split()) for statement in statements]
    assert normalized[0] == 'BEGIN IMMEDIATE'
    assert normalized[-1] == 'COMMIT'
    assert normalized.count('COMMIT') == 1
    assert normalized.count('BEGIN IMMEDIATE') == 1
    assert normalized.count('ROLLBACK') == 0
    assert any(statement.startswith('CREATE TABLE') for statement in normalized[1:-1])
    if registry == 'diagnostics':
        assert normalized[-2].startswith('DELETE FROM CLIENT_DIAGNOSTIC_EVENTS')
    assert_closed(opened)


@pytest.mark.parametrize('seed_existing', (False, True))
def test_two_startups_serialize_without_resetting_registry(tmp_path, registry, seed_existing):
    path = tmp_path / 'synthetic.sqlite3'
    seed_sentinel(path)
    if seed_existing:
        seed_registry(path, registry, missing_indexes=True)
    before_rows = snapshot(path)[1]
    barrier = threading.Barrier(2, timeout=5)

    def initialize():
        def connect():
            db = connect_file(path)
            try:
                barrier.wait()
            except BaseException:
                db.close()
                raise
            return db
        MODULES[registry].initialize(connect)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(initialize) for _ in range(2)]
        for future in futures:
            future.result(timeout=12)
    after_schema, after_rows = snapshot(path)
    assert {row[1] for row in after_schema} == OBJECTS[registry] | {'synthetic_retained'}
    assert after_rows['synthetic_retained'] == before_rows['synthetic_retained']
    if seed_existing:
        table = DIAGNOSTIC_TABLE if registry == 'diagnostics' else VERSION_TABLE
        expected = before_rows[table]
        if registry == 'diagnostics':
            expected = [row for row in expected if row[2] >= CLOCK - diagnostics.RETENTION_SECONDS]
        assert after_rows[table] == expected


def test_busy_database_releases_failed_connection_without_writes(tmp_path, registry):
    path = tmp_path / 'synthetic.sqlite3'
    seed_registry(path, registry, missing_indexes=True)
    before = snapshot(path)
    opened = []

    def connect():
        db = sqlite3.connect(path, timeout=0)
        opened.append(db)
        return db

    with closing(connect_file(path)) as blocker:
        blocker.execute('BEGIN IMMEDIATE')
        try:
            with pytest.raises(sqlite3.OperationalError, match='locked'):
                MODULES[registry].initialize(connect)
            assert_closed(opened)
        finally:
            blocker.rollback()
    assert snapshot(path) == before


def test_schema_startup_does_not_read_or_publish_a_release(tmp_path, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError('registry startup touched the release channel')

    monkeypatch.setenv('ANDROID_UPDATES_ENABLED', 'false')
    monkeypatch.setattr(updates, 'channel', forbidden)
    monkeypatch.setattr(updates.ReleaseChannel, 'verified_file', forbidden)
    path = tmp_path / 'synthetic.sqlite3'
    updates.initialize(lambda: connect_file(path))
    diagnostics.initialize(lambda: connect_file(path))
    assert updates.enabled() is False
    _, rows = snapshot(path)
    assert rows[VERSION_TABLE] == []
    assert rows[DIAGNOSTIC_TABLE] == []
