"""N00 chat/history startup regressions; synthetic temporary databases only.

No lifespan, scheduler, broker, model or paid task is entered. These are written
scenarios, not executed acceptance until run on an authorized owner host.
"""
from contextlib import closing
import sqlite3
from types import SimpleNamespace

import pytest

from backend.tests.test_workspace_state_schema_atomic import (
    assert_closed, concurrent_startups, connect_file,
)

SCHEMA_SQL = "SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
THREAD_INSERT = 'INSERT INTO workspace_chat_threads VALUES (?,?,?,?)'
MESSAGE_INSERT = 'INSERT INTO workspace_chat_messages VALUES (?,?,?,?,?,?,?,?,?)'
HISTORY_INSERT = 'INSERT INTO portfolio_value_history VALUES (?,?,?,?,?,?,?)'
DROP_TIME_INDEX = 'DROP INDEX workspace_chat_thread_time'
DROP_RESPONSE_INDEX = 'DROP INDEX workspace_chat_one_response'
RESPONSE_INDEX = 'workspace_chat_one_response'
TIME_INDEX = 'workspace_chat_thread_time'
OBJECTS = {
    'n00_chat_retained', 'portfolio_value_history', 'workspace_chat_threads',
    'workspace_chat_messages', RESPONSE_INDEX, TIME_INDEX,
}
QUERIES = {
    'n00_chat_retained': 'SELECT * FROM n00_chat_retained ORDER BY key',
    'portfolio_value_history': 'SELECT rowid,* FROM portfolio_value_history ORDER BY rowid',
    'workspace_chat_threads': 'SELECT rowid,* FROM workspace_chat_threads ORDER BY rowid',
    'workspace_chat_messages': 'SELECT rowid,* FROM workspace_chat_messages ORDER BY rowid',
    'workspace_request_receipts': 'SELECT * FROM workspace_request_receipts ORDER BY user_id,request_id',
}
OLD_TIME = '2020-01-01T12:00:00+00:00'


def forbidden(*_args, **_kwargs):
    raise AssertionError('chat schema initialization attempted collection or model work')


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
    from backend import volume_chat as chat, volume_state as state, portfolio_details as details
    path = tmp_path / 'synthetic-chat.sqlite3'
    monkeypatch.setattr(backend, 'DATABASE_PATH', path)
    monkeypatch.setattr(backend, 'connect', lambda: connect_file(path))
    for name in ('GuardedAIClient', 'ready', 'model_messages', 'run_message'):
        monkeypatch.setattr(chat, name, forbidden)
    for name in ('enqueue', 'run_job'):
        monkeypatch.setattr(chat.jobs, name, forbidden)
    monkeypatch.setattr(details, 'BrokerReader', forbidden)
    return SimpleNamespace(backend=backend, chat=chat, state=state, path=path)


def snapshot(path):
    with closing(connect_file(path)) as db:
        schema = [tuple(row) for row in db.execute(SCHEMA_SQL)]
        tables = {name for kind, name, _ in schema if kind == 'table'}
        rows = {name: [tuple(row) for row in db.execute(query)]
                for name, query in QUERIES.items() if name in tables}
    return schema, rows


def seed_sentinel(path):
    with closing(connect_file(path)) as db, db:
        db.execute('CREATE TABLE n00_chat_retained (key TEXT PRIMARY KEY, value BLOB NOT NULL)')
        db.execute('INSERT INTO n00_chat_retained VALUES (?,?)',
                   ('unrelated-synthetic-binding', b'unchanged-not-a-token'))


def seed_chat(workspace):
    workspace.chat.initialize()
    with closing(connect_file(workspace.path)) as db, db:
        for user_id in (101, 202):
            thread_id = f'thread-{user_id}'
            db.execute(THREAD_INSERT, (thread_id, user_id, 'Синтетический диалог', OLD_TIME))
            for role in ('user', 'assistant'):
                db.execute(MESSAGE_INSERT, (
                    f'{user_id}-{role}', thread_id, user_id, role,
                    'Синтетический текст; не данные владельца', OLD_TIME,
                    'shared-local-request', f'job-{user_id}',
                    '{"evidence":[],"routing":{"cost_ceiling_micro_rub":17},"uncertainties":["unknown"]}',
                ))
            for currency in ('RUB', 'USD'):
                for resolution in ('intraday', 'hour', 'day'):
                    db.execute(HISTORY_INSERT, (
                        user_id, 'shared-local-account', currency, resolution, 1,
                        OLD_TIME, '12.340000001',
                    ))
        # Startup must not synthesize a reply or re-dispatch this saved question.
        db.execute(MESSAGE_INSERT, (
            'pending-question', 'thread-101', 101, 'user', 'Unanswered synthetic question',
            OLD_TIME, 'pending-request', 'pending-job', '{"routing":null}',
        ))


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


@pytest.mark.parametrize('action,name', [
    (sqlite3.SQLITE_CREATE_TABLE, 'workspace_chat_threads'),
    (sqlite3.SQLITE_CREATE_TABLE, 'workspace_chat_messages'),
    (sqlite3.SQLITE_CREATE_INDEX, RESPONSE_INDEX),
    (sqlite3.SQLITE_CREATE_INDEX, TIME_INDEX),
    (sqlite3.SQLITE_TRANSACTION, 'COMMIT'),
])
def test_late_failure_also_rolls_back_new_history_table(workspace, monkeypatch, action, name):
    seed_sentinel(workspace.path)
    before = snapshot(workspace.path)
    factory, opened, refused = denying_factory(workspace.path, action, name)
    with monkeypatch.context() as patch:
        patch.setattr(workspace.backend, 'connect', factory)
        with pytest.raises(sqlite3.DatabaseError):
            workspace.chat.initialize()
    assert (action, name) in refused
    assert snapshot(workspace.path) == before
    assert_closed(opened)
    workspace.chat.initialize()
    schema, rows = snapshot(workspace.path)
    assert {name for _, name, _ in schema} == OBJECTS
    assert rows['n00_chat_retained'] == before[1]['n00_chat_retained']
    assert not rows['portfolio_value_history']
    assert not rows['workspace_chat_messages']


@pytest.mark.parametrize('action,name', [
    (sqlite3.SQLITE_CREATE_INDEX, TIME_INDEX), (sqlite3.SQLITE_TRANSACTION, 'COMMIT'),
])
def test_refused_index_repair_preserves_history_message_rowids_and_payloads(workspace, monkeypatch, action, name):
    seed_sentinel(workspace.path)
    seed_chat(workspace)
    healthy = snapshot(workspace.path)
    assert TIME_INDEX in {name for _, name, _ in healthy[0]}
    with closing(connect_file(workspace.path)) as db, db:
        db.execute(DROP_TIME_INDEX)
    before = snapshot(workspace.path)
    assert TIME_INDEX not in {name for _, name, _ in before[0]}
    factory, opened, refused = denying_factory(workspace.path, action, name)
    with monkeypatch.context() as patch:
        patch.setattr(workspace.backend, 'connect', factory)
        with pytest.raises(sqlite3.DatabaseError):
            workspace.chat.initialize()
    assert (action, name) in refused
    assert snapshot(workspace.path) == before
    assert_closed(opened)
    workspace.chat.initialize()
    # Reopen independently: compare the complete persisted schema, not just rows.
    assert snapshot(workspace.path) == healthy


def test_interrupt_after_final_index_rolls_back_history_and_chat(workspace, monkeypatch):
    seed_sentinel(workspace.path)
    before = snapshot(workspace.path)
    opened, written = [], []

    class InterruptedConnection(sqlite3.Connection):
        def execute(self, statement, parameters=()):
            result = super().execute(statement, parameters)
            if 'CREATE INDEX IF NOT EXISTS workspace_chat_thread_time' in statement:
                written.append(True)
                raise KeyboardInterrupt('synthetic-after-chat-index')
            return result

    def connect():
        db = connect_file(workspace.path, factory=InterruptedConnection)
        opened.append(db)
        return db

    monkeypatch.setattr(workspace.backend, 'connect', connect)
    with pytest.raises(KeyboardInterrupt, match='synthetic-after-chat-index'):
        workspace.chat.initialize()
    assert written == [True]
    assert snapshot(workspace.path) == before
    assert_closed(opened)


def test_one_transaction_includes_ensure_history_before_chat_ddl(workspace, monkeypatch):
    traced, opened = [], []

    def connect():
        db = connect_file(workspace.path)
        opened.append(db)
        db.set_trace_callback(traced.append)
        return db

    monkeypatch.setattr(workspace.backend, 'connect', connect)
    workspace.chat.initialize()
    statements = [' '.join(sql.upper().split()) for sql in traced]
    assert statements[0] == 'BEGIN IMMEDIATE'
    assert statements[1].startswith('CREATE TABLE IF NOT EXISTS PORTFOLIO_VALUE_HISTORY')
    assert statements[-1] == 'COMMIT'
    assert statements.count('BEGIN IMMEDIATE') == statements.count('COMMIT') == 1
    assert len(statements[1:-1]) == 5
    assert all(sql.startswith('CREATE ') for sql in statements[1:-1])
    assert_closed(opened)


@pytest.mark.parametrize('populated', (False, True))
def test_concurrent_startup_preserves_history_and_closes_both_handles(workspace, monkeypatch, populated):
    seed_sentinel(workspace.path)
    if populated:
        seed_chat(workspace)
    before_rows = snapshot(workspace.path)[1]
    # The shared probe retains strong references and checks closure on the
    # owning thread before cleanup; it keeps SQLite's thread check enabled.
    concurrent_startups(workspace, monkeypatch, workspace.chat.initialize)
    schema, rows = snapshot(workspace.path)
    assert {name for _, name, _ in schema} == OBJECTS
    for name, expected in before_rows.items():
        assert rows[name] == expected


def test_busy_writer_does_not_leave_history_schema_behind(workspace, monkeypatch):
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
                workspace.chat.initialize()
            assert caught.value.sqlite_errorcode == sqlite3.SQLITE_BUSY
        finally:
            writer.rollback()
    assert snapshot(workspace.path) == before
    assert_closed(opened)


def test_restart_preserves_messages_dates_roles_user_scope_and_history(workspace):
    from fastapi import HTTPException
    seed_sentinel(workspace.path)
    seed_chat(workspace)
    before = snapshot(workspace.path)
    workspace.chat.initialize()
    workspace.chat.initialize()
    assert snapshot(workspace.path) == before
    first = workspace.chat.messages('thread-101', user={'id': 101})
    other = workspace.chat.messages('thread-202', user={'id': 202})
    assert {row['id'] for row in first['items']} == {'101-user', '101-assistant', 'pending-question'}
    assert {row['id'] for row in other['items']} == {'202-user', '202-assistant'}
    assert all(row['created_at'] == OLD_TIME for row in first['items'])
    assert sum(row['role'] == 'assistant' for row in first['items']) == 1
    with pytest.raises(HTTPException) as caught:
        workspace.chat.messages('thread-101', user={'id': 202})
    assert caught.value.status_code == 404
    assert snapshot(workspace.path) == before


def test_thread_creation_replays_saved_receipt_after_restart(workspace):
    from fastapi import HTTPException
    workspace.state.initialize()
    workspace.chat.initialize()
    request = workspace.chat.ThreadCreate(request_id='synthetic-thread-request', title='Synthetic thread')
    first = workspace.chat.create_thread(request, {'id': 101})
    other = workspace.chat.create_thread(request, {'id': 202})
    before = snapshot(workspace.path)
    workspace.chat.initialize()
    assert workspace.chat.create_thread(request, {'id': 101}) == first
    assert workspace.chat.create_thread(request, {'id': 202}) == other
    assert first['thread_id'] != other['thread_id']
    with pytest.raises(HTTPException) as caught:
        workspace.chat.create_thread(request.model_copy(update={'title': 'Changed content'}), {'id': 101})
    assert caught.value.status_code == 409
    assert snapshot(workspace.path) == before


@pytest.mark.parametrize('request_id,job_id', [
    ('another-request', 'job-101'), ('shared-local-request', 'another-job'),
])
def test_restart_retains_both_response_uniqueness_constraints(workspace, request_id, job_id):
    seed_chat(workspace)
    workspace.chat.initialize()
    before = snapshot(workspace.path)
    with closing(connect_file(workspace.path)) as db:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(MESSAGE_INSERT, (
                'duplicate-answer', 'thread-101', 101, 'assistant', 'Synthetic duplicate',
                OLD_TIME, request_id, job_id, '{}',
            ))
        db.rollback()
    assert snapshot(workspace.path) == before


def test_existing_duplicate_responses_fail_without_deleting_either_record(workspace):
    seed_chat(workspace)
    with closing(connect_file(workspace.path)) as db, db:
        db.execute(DROP_RESPONSE_INDEX)
        db.execute(DROP_TIME_INDEX)
        db.execute(MESSAGE_INSERT, (
            'preexisting-duplicate', 'thread-101', 101, 'assistant', 'Synthetic conflict',
            OLD_TIME, 'different-request', 'job-101', '{}',
        ))
    before = snapshot(workspace.path)
    with pytest.raises(sqlite3.IntegrityError):
        workspace.chat.initialize()
    assert snapshot(workspace.path) == before
