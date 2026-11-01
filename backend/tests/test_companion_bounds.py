"""Unicode, exact byte budgets and cancellation races; no real model or account."""
from contextlib import closing
from cryptography.fernet import Fernet
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import json
import sqlite3
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from backend import companion_chat as chat
from backend.ai_guarded_client import GuardedAIClient


def reply(answer='Ответ 👋'):
    return json.dumps({'model': chat.local.MODEL_ID,
        'usage': {'prompt_tokens': 10, 'completion_tokens': 4, 'total_tokens': 14},
        'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps({'answer': answer})}}]}).encode()


@pytest.fixture
def companion(tmp_path, monkeypatch):
    path = tmp_path / 'synthetic-bounds.sqlite3'
    def connect():
        db = sqlite3.connect(path)
        db.row_factory = sqlite3.Row
        return db
    auth = 'Bearer synthetic-bound-session'
    env = {'COMPANION_CHAT_ENABLED': 'true', 'LOCAL_AI_ENABLED': 'true'}
    cipher = Fernet(Fernet.generate_key())
    service = chat.CompanionService(connect, cipher, lambda: env)
    with closing(connect()) as db, db:
        db.execute('CREATE TABLE users(id INTEGER PRIMARY KEY,tinvest_token_encrypted BLOB)')
        db.execute('INSERT INTO users VALUES(1,NULL)')
        db.execute('CREATE TABLE sessions(token_hash TEXT PRIMARY KEY,user_id INTEGER,expires_at INTEGER)')
        db.execute('INSERT INTO sessions VALUES(?,?,?)', (chat.session_hash(auth), 1, int(time.time()) + 3600))
    service.initialize()
    ready = Mock(return_value=None)
    generate = Mock(return_value=reply())
    cloud = Mock(side_effect=AssertionError('no external model'))
    monkeypatch.setattr(chat.local, 'ensure_ready', ready)
    monkeypatch.setattr(chat.local, 'complete', generate)
    monkeypatch.setattr(GuardedAIClient, '_send', cloud)
    def ask(text='Привет', request_id='bounded-0001'):
        return service.chat(1, auth, request_id, text)
    return SimpleNamespace(service=service, connect=connect, auth=auth, env=env,
                           cipher=cipher, ready=ready, generate=generate, cloud=cloud, ask=ask)


def error(code, call, status=None):
    with pytest.raises(HTTPException) as caught:
        call()
    assert caught.value.detail == code
    if status is not None:
        assert caught.value.status_code == status


@pytest.mark.parametrize('text', ['\ud800', 'текст\udfff', '\ud83d\ude00', '\x00hello', 'a\x1b[31m', 'a\x01b'])
def test_invalid_text_fails_before_db_or_model(companion, text):
    error('companion_input_invalid', lambda: companion.ask(text), 422)
    companion.generate.assert_not_called()
    companion.ready.assert_not_called()
    with closing(companion.connect()) as db:
        assert db.execute('SELECT COUNT(*) FROM companion_turns').fetchone()[0] == 0
        assert db.execute('SELECT COUNT(*) FROM companion_slots').fetchone()[0] == 0


@pytest.mark.parametrize('text', ['Привет, Михаил!', '👨‍👩‍👧‍👦 👍🏽', 'е\u0308 и ё', 'строка\nстрока\tтаб', '𐍈🙂' * 1000])
def test_valid_unicode_is_preserved_not_lossily_repaired(companion, text):
    result = companion.ask(text)
    assert result['text'] == text and result['state'] == 'completed'
    assert companion.service.history(1, companion.auth)['turns'][0]['text'] == text
    sent = json.loads(companion.generate.call_args.args[0][1]['content'])
    assert sent['message'] == text


@pytest.mark.parametrize('answer', ['\ud800', 'ok\udfff', 'ok\x00', 'ok\x1b'])
def test_invalid_model_unicode_does_not_poison_history(companion, answer):
    companion.generate.return_value = reply(answer)
    error('companion_invalid_response', companion.ask, 502)
    with closing(companion.connect()) as db:
        row = db.execute('SELECT state,answer_cipher FROM companion_turns').fetchone()
        assert tuple(row) == ('failed', None)
    assert companion.service.history(1, companion.auth)['turns'][0]['answer'] is None
    companion.cloud.assert_not_called()


def test_invalid_encrypted_legacy_text_is_closed_and_can_be_cleared(companion):
    companion.ask()
    with closing(companion.connect()) as db, db:
        row = db.execute('SELECT * FROM companion_turns').fetchone()
        value = [1, row['epoch'], row['id'], 'answer', '\ud800']
        encrypted = companion.cipher.encrypt(json.dumps(value, ensure_ascii=True).encode())
        db.execute('UPDATE companion_turns SET answer_cipher=?', (encrypted,))
    error('companion_history_unreadable', lambda: companion.service.history(1, companion.auth), 503)
    error('companion_history_unreadable', lambda: companion.ask(request_id='bounded-0002'), 503)
    companion.generate.assert_called_once()
    companion.service.clear(1, companion.auth)
    assert companion.ask(request_id='bounded-0003')['state'] == 'completed'


@pytest.mark.parametrize('fragment', ['🙂', '\\', '"', '\n'])
def test_exact_double_encoded_context_is_bounded(fragment):
    history = [{'user': str(i) + fragment * 1999, 'assistant': fragment * 4000} for i in range(6)]
    original = list(history)
    current = fragment * 2000
    messages = chat._messages(history, current)
    wire = json.dumps({'messages': messages, 'max_output_tokens': chat.MAX_TOKENS}, ensure_ascii=False).encode()
    assert len(wire) <= chat.MAX_REQUEST_BYTES
    selected = json.loads(messages[1]['content'])
    assert selected['message'] == current
    assert 0 < len(selected['history']) < len(history)
    assert selected['history'] == history[-len(selected['history']):]
    assert history == original


def test_context_that_cannot_fit_is_not_silently_truncated(monkeypatch):
    monkeypatch.setattr(chat, 'MAX_REQUEST_BYTES', 100)
    error('companion_context_too_large', lambda: chat._messages([], 'Полный вопрос'), 422)


@pytest.mark.parametrize('token', ['\ud800', 'тест', '🙂', 'a' * 4097])
def test_bad_session_encoding_is_a_fixed_401(token):
    error('invalid_session', lambda: chat.session_hash('Bearer ' + token), 401)


@pytest.mark.parametrize('action', ['cancel', 'clear', 'logout', 'disable', 'expire'])
def test_revoked_during_readiness_is_never_sent_to_model(companion, action):
    def ready():
        if action == 'clear':
            companion.service.clear(1, companion.auth)
        elif action == 'disable':
            companion.env['COMPANION_CHAT_ENABLED'] = 'false'
        elif action == 'cancel':
            with closing(companion.connect()) as db:
                turn_id = db.execute('SELECT id FROM companion_turns').fetchone()[0]
            companion.service.cancel(1, companion.auth, turn_id)
        else:
            with closing(companion.connect()) as db, db:
                db.execute('DELETE FROM sessions' if action == 'logout' else 'UPDATE companion_slots SET deadline=0')
    companion.ready.side_effect = ready
    with pytest.raises(HTTPException):
        companion.ask()
    companion.generate.assert_not_called()
    companion.cloud.assert_not_called()
    with closing(companion.connect()) as db:
        assert db.execute('SELECT COUNT(*) FROM companion_slots').fetchone()[0] == 0


def test_timeout_keeps_cooldown_and_does_not_replay(companion):
    companion.generate.side_effect = chat.local.LocalAIError('local_ai_timeout')
    error('companion_local_timeout', companion.ask, 504)
    result = companion.ask()
    assert result['state'] == 'failed' and result['error_code'] == 'companion_local_timeout'
    error('companion_busy', lambda: companion.ask(request_id='bounded-0002'), 429)
    restarted = chat.CompanionService(companion.connect, companion.cipher, lambda: companion.env)
    restarted.clear(1, companion.auth)
    error('companion_busy', lambda: restarted.chat(1, companion.auth, 'bounded-0003', 'Привет'), 429)
    companion.generate.assert_called_once()
    with closing(companion.connect()) as db, db:
        db.execute('UPDATE companion_slots SET deadline=0')
    companion.generate.side_effect = None
    assert companion.ask(request_id='bounded-0004')['state'] == 'completed'
    companion.cloud.assert_not_called()


def test_wait_limit_is_shorter_than_persisted_cooldown():
    assert chat.local.TIMEOUT_SECONDS < chat.LEASE_SECONDS


@pytest.mark.parametrize('turn_id', ['\ud800', 'a' * 10000, '..', 'not-a-turn', None])
def test_bad_cancel_identifier_never_reaches_sqlite(companion, turn_id):
    error('companion_turn_not_found', lambda: companion.service.cancel(1, companion.auth, turn_id), 404)


@pytest.mark.parametrize('text', ['\ud800', 'a\x00', 'Привет 👋'])
def test_http_unicode_status_is_serializable(companion, text):
    app = FastAPI()
    # Synthetic identity only. CompanionService still checks the actual test session.
    chat.install_routes(app, companion.connect, companion.cipher, lambda: {'id': 1}, lambda: companion.env)
    with TestClient(app) as client:
        response = client.post('/assistant/chat', headers={'Authorization': companion.auth,
            'Content-Type': 'application/json'},
            content=json.dumps({'request_id': 'http-bound-001', 'text': text}, ensure_ascii=True).encode())
    assert response.status_code == (200 if chat._valid_text(text, chat.MAX_TEXT) else 422)
    response.json()
