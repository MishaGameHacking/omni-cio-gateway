"""N00 schema regressions using temporary synthetic databases only."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import sqlite3
import threading

import pytest

from backend.ai_budget import MoneyLedger, transaction
from backend.schema_migrations import SchemaMigrationError, execute_schema, schema_statements


def connection(path):
    return sqlite3.connect(path, timeout=3)


def schema(path):
    with closing(connection(path)) as db:
        return db.execute("SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name").fetchall()


def test_failed_initializer_rolls_back_all_new_objects(tmp_path):
    path = tmp_path / 'synthetic.sqlite3'
    with closing(connection(path)) as db, db:
        db.execute('CREATE TABLE retained (value TEXT NOT NULL)')
        db.execute('INSERT INTO retained VALUES (?)', ('synthetic-sentinel',))
    before = schema(path)
    opened = []
    def rejecting_connection():
        db = connection(path)
        opened.append(db)
        def authorizer(action, first, second, database, trigger):
            if action == sqlite3.SQLITE_CREATE_TABLE and first == 'ai_money_control':
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        db.set_authorizer(authorizer)
        return db
    with pytest.raises(sqlite3.DatabaseError):
        MoneyLedger(rejecting_connection).initialize()
    assert schema(path) == before
    with closing(connection(path)) as db:
        assert db.execute('SELECT value FROM retained').fetchall() == [('synthetic-sentinel',)]
    with pytest.raises(sqlite3.ProgrammingError):
        opened[0].execute('SELECT 1')


def test_initializer_is_idempotent_and_preserves_unresolved_reservations(tmp_path):
    path = tmp_path / 'synthetic.sqlite3'
    ledger = MoneyLedger(lambda: connection(path))
    ledger.initialize()
    ledger.reserve(user_id=1, key='synthetic-request', route='synthetic-route', model='synthetic-model',
                   ceiling=100, user_cap=200, project_cap=300, at=1700000000)
    ledger.uncertain('synthetic-request', pause_reason='model_mismatch')
    with closing(connection(path)) as db:
        before_rows = db.execute('SELECT * FROM ai_money_reservations').fetchall()
        before_control = db.execute('SELECT * FROM ai_money_control').fetchall()
    before_schema = schema(path)
    ledger.initialize()
    assert schema(path) == before_schema
    with closing(connection(path)) as db:
        assert db.execute('SELECT * FROM ai_money_reservations').fetchall() == before_rows
        assert db.execute('SELECT * FROM ai_money_control').fetchall() == before_control


def test_two_initializers_serialize_without_partial_schema(tmp_path):
    path = tmp_path / 'synthetic.sqlite3'
    barrier = threading.Barrier(2, timeout=5)
    def create():
        def connect():
            db = connection(path)
            barrier.wait()
            return db
        MoneyLedger(connect).initialize()
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(create) for _ in range(2)]
        for future in futures:
            future.result(timeout=10)
    names = {row[1] for row in schema(path)}
    assert names == {'ai_money_reservations', 'ai_money_user_day', 'ai_money_unresolved',
                     'ai_route_cooldown', 'ai_money_control'}


def test_initializer_retains_transaction_until_last_statement(tmp_path):
    statements = []
    def connect():
        db = connection(tmp_path / 'synthetic.sqlite3')
        db.set_trace_callback(statements.append)
        return db
    MoneyLedger(connect).initialize()
    normalized = [statement.strip().upper() for statement in statements]
    assert normalized[0] == 'BEGIN IMMEDIATE'
    assert normalized[-1] == 'COMMIT'
    assert normalized.count('COMMIT') == 1
    assert any('AI_MONEY_CONTROL' in statement for statement in normalized[1:-1])


def test_schema_helper_does_not_commit_callers_previous_writes(tmp_path):
    path = tmp_path / 'synthetic.sqlite3'
    with closing(connection(path)) as db, db:
        db.execute('CREATE TABLE retained (value TEXT)')
    with pytest.raises(RuntimeError, match='synthetic-interruption'):
        with transaction(lambda: connection(path)) as db:
            db.execute('INSERT INTO retained VALUES (?)', ('synthetic-uncommitted',))
            execute_schema(db, 'CREATE TABLE candidate (value TEXT);')
            assert db.in_transaction
            raise RuntimeError('synthetic-interruption')
    with closing(connection(path)) as db:
        assert db.execute('SELECT * FROM retained').fetchall() == []
        assert db.execute("SELECT name FROM sqlite_master WHERE name='candidate'").fetchall() == []


def test_schema_helper_requires_existing_transaction():
    with closing(sqlite3.connect(':memory:')) as db:
        with pytest.raises(SchemaMigrationError, match='schema_write_transaction_required'):
            execute_schema(db, 'CREATE TABLE candidate (id INTEGER);')
        assert not db.in_transaction


@pytest.mark.parametrize('tail', ['COMMIT;', 'ROLLBACK;', 'BEGIN;', 'PRAGMA journal_mode=WAL;',
                                  'INSERT INTO candidate VALUES (1);', 'CREATE TABLE unfinished ('])
def test_whole_batch_is_validated_before_any_execution(tail):
    with closing(sqlite3.connect(':memory:')) as db, db:
        db.execute('BEGIN IMMEDIATE')
        with pytest.raises(SchemaMigrationError):
            execute_schema(db, 'CREATE TABLE candidate (id INTEGER); ' + tail)
        assert db.in_transaction
        assert db.execute("SELECT name FROM sqlite_master WHERE name='candidate'").fetchall() == []


def test_trigger_and_quoted_semicolons_use_sqlite_statement_boundaries():
    script = '''-- synthetic migration; comments are not statements
        CREATE TABLE synthetic_input (value TEXT DEFAULT 'one;two');
        CREATE TABLE synthetic_audit (value TEXT);
        CREATE TRIGGER synthetic_trigger AFTER INSERT ON synthetic_input BEGIN
          INSERT INTO synthetic_audit VALUES ('first;part');
          INSERT INTO synthetic_audit VALUES (new.value);
        END;
        /* retained trailing comment; */
    '''
    assert len(schema_statements(script)) == 3
    with closing(sqlite3.connect(':memory:')) as db, db:
        db.execute('BEGIN IMMEDIATE')
        assert execute_schema(db, script) == 3
        db.execute('INSERT INTO synthetic_input DEFAULT VALUES')
        assert db.execute('SELECT value FROM synthetic_audit').fetchall() == [('first;part',), ('one;two',)]
        assert db.in_transaction


@pytest.mark.parametrize('script', ['', '   ', '-- only a comment', '/* only a comment */',
                                    'CREATE TABLE candidate(id);\x00', None, 1])
def test_invalid_schema_contract_is_rejected(script):
    with pytest.raises(SchemaMigrationError):
        schema_statements(script)


def test_size_and_statement_bounds(monkeypatch):
    from backend import schema_migrations as module
    monkeypatch.setattr(module, 'MAX_SCHEMA_STATEMENTS', 1)
    with pytest.raises(SchemaMigrationError, match='schema_statement_limit'):
        schema_statements('CREATE TABLE a(id); CREATE TABLE b(id);')
    monkeypatch.setattr(module, 'MAX_SCHEMA_CHARACTERS', 5)
    with pytest.raises(SchemaMigrationError, match='schema_script_invalid_or_oversized'):
        schema_statements('CREATE TABLE a(id);')


def test_baseexception_rolls_back_and_closes_connection(tmp_path):
    path = tmp_path / 'synthetic.sqlite3'
    opened = []
    class InterruptedConnection(sqlite3.Connection):
        def execute(self, statement, parameters=()):
            if 'CREATE TABLE IF NOT EXISTS ai_route_cooldown' in statement:
                raise KeyboardInterrupt('synthetic-interruption')
            return super().execute(statement, parameters)
    def connect():
        db = sqlite3.connect(path, factory=InterruptedConnection)
        opened.append(db)
        return db
    with pytest.raises(KeyboardInterrupt):
        MoneyLedger(connect).initialize()
    assert schema(path) == []
    with pytest.raises(sqlite3.ProgrammingError):
        opened[0].execute('SELECT 1')
