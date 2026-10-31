"""Local companion with synthetic sessions, temporary DB and fixture model only."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from cryptography.fernet import Fernet
from fastapi import HTTPException
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from backend import companion_chat as chat
from backend.ai_guarded_client import GuardedAIClient


def response(answer='Привет! Это синтетический ответ.', **changes):
    value = {'model': chat.local.MODEL_ID,
             'usage': {'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 120},
             'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps({'answer': answer})}}]}
    value.update(changes)
    return json.dumps(value).encode()


class CompanionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / 'synthetic.db'
        self.env = {'COMPANION_CHAT_ENABLED': 'true', 'LOCAL_AI_ENABLED': 'true'}
        self.cipher = Fernet(Fernet.generate_key())
        self.service = chat.CompanionService(self.connect, self.cipher, lambda: self.env)
        self.auth = 'Bearer synthetic-chat-session'
        self.other = 'Bearer synthetic-other-session'
        with closing(self.connect()) as db, db:
            db.execute('CREATE TABLE users(id INTEGER PRIMARY KEY,tinvest_token_encrypted BLOB)')
            db.execute('INSERT INTO users VALUES(1,NULL),(2,NULL)')
            db.execute('CREATE TABLE sessions(token_hash TEXT PRIMARY KEY,user_id INTEGER,expires_at INTEGER)')
            db.executemany('INSERT INTO sessions VALUES(?,?,?)', [(chat.session_hash(self.auth), 1, int(time.time()) + 3600),
                           (chat.session_hash(self.other), 2, int(time.time()) + 3600)])
        self.service.initialize()
        self.ready = self.enterContext(patch.object(chat.local, 'ensure_ready', return_value=None))
        self.generate = self.enterContext(patch.object(chat.local, 'complete', return_value=response()))
        self.cloud = self.enterContext(patch.object(GuardedAIClient, '_send', side_effect=AssertionError('no cloud')))

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def ask(self, request_id='request-0001', text='Привет', *, user=1, authorization=None):
        return self.service.chat(user, authorization or self.auth, request_id, text)

    def rows(self):
        with closing(self.connect()) as db:
            return db.execute('SELECT * FROM companion_turns ORDER BY rowid').fetchall()

    def assert_error(self, code, call, status=None):
        with self.assertRaises(HTTPException) as caught:
            call()
        self.assertEqual(caught.exception.detail, code)
        if status is not None:
            self.assertEqual(caught.exception.status_code, status)

    def test_no_broker_token_needed_for_authenticated_local_conversation(self):
        result = self.ask()
        self.assertEqual(result['state'], 'completed')
        self.assertEqual(result['answer'], 'Привет! Это синтетический ответ.')
        self.assertEqual(result['actions_performed'], [])
        self.assertFalse(result['external_processing'])
        with closing(self.connect()) as db:
            self.assertIsNone(db.execute('SELECT tinvest_token_encrypted FROM users WHERE id=1').fetchone()[0])
            self.assertFalse(db.execute("SELECT 1 FROM sqlite_master WHERE name='ai_money_reservations'").fetchone())
        self.cloud.assert_not_called()

    def test_disabled_by_default(self):
        self.env.pop('COMPANION_CHAT_ENABLED')
        self.assert_error('companion_disabled', self.ask, 503)
        self.generate.assert_not_called()

    def test_never_enables_local_model_or_cloud_as_fallback(self):
        self.env.update(LOCAL_AI_ENABLED='false', TIMEWEB_AI_TOKEN='synthetic-not-used', AI_TRANSPORT='gateway')
        self.assert_error('companion_local_disabled', self.ask, 503)
        self.generate.assert_not_called()
        self.cloud.assert_not_called()

    def test_truthy_unknown_flags_fail_closed(self):
        for value in ('yes', '1', 'TRUE', True):
            self.env['COMPANION_CHAT_ENABLED'] = value
            self.assert_error('companion_disabled', self.ask)

    def test_invalid_and_other_users_sessions_rejected(self):
        for auth in ('', 'Basic abc', 'Bearer unknown', self.other):
            self.assert_error('invalid_session', lambda: self.service.chat(1, auth, 'request-0001', 'Привет'), 401)
        self.generate.assert_not_called()

    def test_expired_session_rejected(self):
        with closing(self.connect()) as db, db:
            db.execute('UPDATE sessions SET expires_at=0 WHERE user_id=1')
        self.assert_error('invalid_session', self.ask, 401)
        self.generate.assert_not_called()

    def test_input_bounds(self):
        for text in ('', ' ', 'x' * 2001, None):
            self.assert_error('companion_input_invalid', lambda: self.ask(text=text), 422)
        self.assert_error('companion_input_invalid', lambda: self.ask(request_id='bad'), 422)
        self.generate.assert_not_called()

    def test_completed_idempotency_does_not_generate_twice(self):
        first = self.ask()
        second = self.ask()
        self.assertEqual(first, second)
        self.generate.assert_called_once()

    def test_request_id_conflict(self):
        self.ask()
        self.assert_error('companion_request_conflict', lambda: self.ask(text='Другая фраза'), 409)
        self.generate.assert_called_once()

    def test_running_duplicate_returns_saved_state_without_reentry(self):
        observed = []
        def complete(*_):
            observed.append(self.ask())
            return response()
        self.generate.side_effect = complete
        self.ask()
        self.assertEqual(observed[0]['state'], 'running')
        self.generate.assert_called_once()

    def test_context_contains_previous_completed_exchange(self):
        self.ask(text='Мой любимый цвет — синий.')
        self.ask('request-0002', 'Какой цвет я назвал?')
        payload = json.loads(self.generate.call_args.args[0][1]['content'])
        self.assertEqual(payload['history'][0]['user'], 'Мой любимый цвет — синий.')
        self.assertEqual(payload['message'], 'Какой цвет я назвал?')
        self.assertEqual(len(self.generate.call_args.args[0]), 2)

    def test_storage_is_encrypted_and_field_bound(self):
        self.ask(text='private-test-conversation-phrase')
        row = self.rows()[0]
        self.assertNotIn(b'private-test-conversation-phrase', row['input_cipher'])
        self.assertNotIn('Привет'.encode(), row['answer_cipher'])
        with closing(self.connect()) as db, db:
            db.execute('UPDATE companion_turns SET answer_cipher=input_cipher')
        self.assert_error('companion_history_unreadable', lambda: self.service.history(1, self.auth), 503)

    def test_another_user_cannot_read_or_cancel_conversation(self):
        first = self.ask()
        self.assertEqual(self.service.history(2, self.other)['turns'], [])
        self.assert_error('companion_turn_not_found', lambda: self.service.cancel(2, self.other, first['id']), 404)
        self.service.clear(2, self.other)
        self.assertEqual(len(self.service.history(1, self.auth)['turns']), 1)

    def test_history_survives_new_service_instance(self):
        first = self.ask()
        restarted = chat.CompanionService(self.connect, self.cipher, lambda: self.env)
        self.assertEqual(restarted.history(1, self.auth)['turns'][0]['id'], first['id'])
        self.assertEqual(restarted.chat(1, self.auth, 'request-0001', 'Привет'), first)
        self.generate.assert_called_once()

    def test_clear_removes_context_for_next_generation(self):
        self.ask()
        self.service.clear(1, self.auth)
        self.assertEqual(self.service.history(1, self.auth)['turns'], [])
        self.ask('request-0002')
        payload = json.loads(self.generate.call_args.args[0][1]['content'])
        self.assertEqual(payload['history'], [])

    def test_clear_during_generation_discards_late_answer(self):
        def complete(*_):
            self.service.clear(1, self.auth)
            self.assert_error('companion_busy', lambda: self.ask('request-0002'), 429)
            return response()
        self.generate.side_effect = complete
        self.assert_error('companion_turn_revoked', self.ask, 409)
        self.assertEqual(self.service.history(1, self.auth)['turns'], [])

    def test_cancel_during_generation_keeps_slot_until_completion(self):
        def complete(*_):
            turn_id = self.rows()[0]['id']
            result = self.service.cancel(1, self.auth, turn_id)
            self.assertFalse(result['generation_interrupt_confirmed'])
            self.assert_error('companion_busy', lambda: self.ask('request-0002'), 429)
            return response()
        self.generate.side_effect = complete
        self.assert_error('companion_turn_revoked', self.ask, 409)
        row = self.service.history(1, self.auth)['turns'][0]
        self.assertEqual(row['state'], 'cancelled')
        self.assertIsNone(row['answer'])

    def test_logout_during_generation_suppresses_answer(self):
        def complete(*_):
            with closing(self.connect()) as db, db:
                db.execute('DELETE FROM sessions WHERE user_id=1')
            return response()
        self.generate.side_effect = complete
        self.assert_error('invalid_session', self.ask, 401)
        self.assertEqual(self.rows()[0]['state'], 'cancelled')
        self.assertIsNone(self.rows()[0]['answer_cipher'])

    def test_disable_during_generation_suppresses_answer(self):
        def complete(*_):
            self.env['COMPANION_CHAT_ENABLED'] = 'false'
            return response()
        self.generate.side_effect = complete
        self.assert_error('companion_disabled', self.ask, 503)
        self.assertIsNone(self.rows()[0]['answer_cipher'])

    def test_model_call_holds_no_sqlite_write_lock(self):
        def complete(*_):
            with closing(self.connect()) as db:
                db.execute('BEGIN IMMEDIATE')
                db.rollback()
            return response()
        self.generate.side_effect = complete
        self.assertEqual(self.ask()['state'], 'completed')

    def test_parallel_calls_are_bounded_by_persisted_slot(self):
        started, release = threading.Event(), threading.Event()
        def complete(*_):
            started.set()
            if not release.wait(5):
                raise RuntimeError('synthetic-timeout')
            return response()
        self.generate.side_effect = complete
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.ask)
            try:
                self.assertTrue(started.wait(5))
                self.assert_error('companion_busy', lambda: self.ask('request-0002'), 429)
            finally:
                release.set()
            self.assertEqual(future.result(timeout=5)['state'], 'completed')
        self.generate.assert_called_once()

    def test_interrupted_saved_attempt_is_not_automatically_replayed(self):
        self.ask()
        with closing(self.connect()) as db, db:
            db.execute("UPDATE companion_turns SET state='running',deadline=0,answer_cipher=NULL,model=NULL")
            db.execute('INSERT INTO companion_slots VALUES(1,?,0)', (self.rows()[0]['id'],))
        result = self.ask()
        self.assertEqual(result['state'], 'interrupted')
        self.assertIsNone(result['answer'])
        self.generate.assert_called_once()

    def test_failed_attempt_is_not_replayed(self):
        self.generate.side_effect = chat.local.LocalAIError('local_ai_unavailable')
        self.assert_error('companion_local_unavailable', self.ask, 503)
        self.assertEqual(self.ask()['state'], 'failed')
        self.generate.assert_called_once()
        self.cloud.assert_not_called()

    def test_history_limit_does_not_drop_idempotency_receipts(self):
        self.ask()
        with patch.object(chat, 'MAX_TURNS', 1):
            self.assert_error('companion_history_full', lambda: self.ask('request-0002'), 429)
            self.assertEqual(self.ask()['state'], 'completed')
        self.generate.assert_called_once()

    def test_invalid_json_model_or_usage_cannot_become_answer(self):
        cases = [b'not-json', b'[]', response(model='wrong-model'),
                 response(usage={'prompt_tokens': True, 'completion_tokens': 1, 'total_tokens': 2}),
                 response(usage={'prompt_tokens': 1, 'completion_tokens': 999, 'total_tokens': 1000}),
                 response(usage={'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 7}),
                 response(answer=''), response(answer='x' * 4001),
                 b'{"model":"a","model":"b"}']
        for index, value in enumerate(cases):
            with self.subTest(index=index):
                self.generate.side_effect = None
                self.generate.return_value = value
                with self.assertRaises(HTTPException):
                    self.ask(f'request-bad-{index}')
                self.assertIsNone(self.rows()[-1]['answer_cipher'])

    def test_incomplete_or_tool_outputs_are_rejected(self):
        for index, choice in enumerate([
            {'finish_reason': 'length', 'message': {'content': '{"answer":"partial"}'}},
            {'finish_reason': 'tool_calls', 'message': {'tool_calls': [{'name': 'buy'}]}},
            {'finish_reason': 'stop', 'message': {'content': '{"answer":"bad"}', 'tool_calls': [{'name': 'buy'}]}},
            {'finish_reason': 'stop', 'message': {'content': '{"answer":"bad","command":"buy"}'}}]):
            self.generate.return_value = response(choices=[choice])
            with self.subTest(index=index), self.assertRaises(HTTPException):
                self.ask(f'request-tool-{index}')
        self.cloud.assert_not_called()


class CompanionHTTPTests(unittest.TestCase):
    def setUp(self):
        # Existing test module establishes only synthetic startup configuration.
        from backend.tests import test_autonomous_ai
        from backend import app as backend
        from fastapi.testclient import TestClient
        self.backend = backend
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.enterContext(patch.object(backend, 'DATABASE_PATH', Path(directory.name) / 'http-test.sqlite3'))
        self.enterContext(patch.dict('os.environ', {'COMPANION_CHAT_ENABLED': 'true', 'LOCAL_AI_ENABLED': 'true'}))
        backend.init_db()
        with closing(backend.connect()) as db, db:
            db.execute("INSERT INTO users(telegram_sub,created_at,updated_at) VALUES('synthetic-no-broker',1,1)")
            self.user_id = db.execute('SELECT id FROM users').fetchone()[0]
            db.execute('INSERT INTO sessions VALUES(?,?,?)', (backend.hash_token('synthetic-http-session'), self.user_id, int(time.time()) + 600))
        # Only device attestation is bypassed in this test, not session validation.
        self.enterContext(patch.dict(backend.app.dependency_overrides, {backend.current_user: backend.session_user}))
        self.client = TestClient(backend.app)
        self.addCleanup(self.client.close)
        self.generate = self.enterContext(patch.object(chat.local, 'complete', return_value=response()))
        self.enterContext(patch.object(chat.local, 'ensure_ready', return_value=None))
        self.headers = {'Authorization': 'Bearer synthetic-http-session'}

    def test_unauthenticated_endpoints_reject(self):
        self.assertEqual(self.client.get('/assistant/chat/history').status_code, 401)
        self.assertEqual(self.client.post('/assistant/chat', json={'request_id': 'http-0001', 'text': 'Привет'}).status_code, 401)
        self.assertEqual(self.client.delete('/assistant/chat/history').status_code, 401)
        self.generate.assert_not_called()

    def test_real_session_and_no_broker_chat_history_and_clear(self):
        r = self.client.post('/assistant/chat', headers=self.headers, json={'request_id': 'http-0001', 'text': 'Привет'})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()['state'], 'completed')
        self.assertEqual(r.headers['Cache-Control'], 'no-store, private')
        history = self.client.get('/assistant/chat/history', headers=self.headers)
        self.assertEqual(len(history.json()['turns']), 1)
        self.assertEqual(self.client.delete('/assistant/chat/history', headers=self.headers).status_code, 200)
        self.assertEqual(self.client.get('/assistant/chat/history', headers=self.headers).json()['turns'], [])

    def test_extra_tool_or_cloud_mode_fields_are_forbidden(self):
        for key in ('tools', 'route', 'broker_token'):
            r = self.client.post('/assistant/chat', headers=self.headers,
                json={'request_id': 'http-0001', 'text': 'Привет', key: 'not-allowed'})
            self.assertEqual(r.status_code, 422)
        self.generate.assert_not_called()

    def test_disabled_feature_is_not_a_successful_response(self):
        with patch.dict('os.environ', {'COMPANION_CHAT_ENABLED': 'false'}):
            r = self.client.post('/assistant/chat', headers=self.headers, json={'request_id': 'http-0001', 'text': 'Привет'})
        self.assertEqual(r.status_code, 503)
        self.generate.assert_not_called()


if __name__ == '__main__':
    unittest.main()
