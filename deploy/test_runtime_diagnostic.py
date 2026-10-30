"""Synthetic-only read-only observer checks; execute exclusively in owner WSL."""
from pathlib import Path
import importlib.util
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('runtime_diagnostic', Path(__file__).with_name('runtime_diagnostic.py'))
observer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(observer)
PREPARE_SPEC = importlib.util.spec_from_file_location('prepare_runtime_diagnostic_transport',
    Path(__file__).resolve().parents[1] / 'tools/prepare_runtime_diagnostic_transport.py')
preparer = importlib.util.module_from_spec(PREPARE_SPEC)
PREPARE_SPEC.loader.exec_module(preparer)
NOW = 1793361600
SECRET = 'private_account_token_prompt_never_publish'


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.path = self.root / 'test.db'
        self.db = sqlite3.connect(self.path)
        self.addCleanup(self.db.close)
        self.db.executescript('''
            CREATE TABLE portfolio_decision_cycles(evaluated_at INTEGER,payload_json TEXT);
            CREATE TABLE automation_discovery(state TEXT,updated_at INTEGER,attempted_at INTEGER,lease_until INTEGER,result_json TEXT);
            CREATE TABLE automation_preferences(enabled INTEGER);
            CREATE TABLE workspace_jobs(id TEXT,user_id INTEGER,kind TEXT,state TEXT,stage TEXT,error_code TEXT,paid_started INTEGER,created_at INTEGER,updated_at INTEGER,expires_at INTEGER);
            CREATE TABLE workspace_chat_messages(job_id TEXT,user_id INTEGER,role TEXT,payload_json TEXT);
            CREATE TABLE ai_money_reservations(model TEXT,state TEXT,input_tokens INTEGER,output_tokens INTEGER,created_at INTEGER,updated_at INTEGER);
            CREATE TABLE ai_work_jobs(status TEXT,updated_at INTEGER,error_code TEXT);
            CREATE TABLE scheduler_leases(expires_at INTEGER);
            CREATE TABLE workspace_snapshots(created_at INTEGER);
            CREATE TABLE users(secret TEXT);
        ''')
        self.db.commit()

    def observe(self):
        return observer.observe_database(self.path, NOW)

    def test_empty_journal_does_not_claim_live_cycle_or_trade(self):
        result = self.observe()
        self.assertEqual([], result['missing_tables'])
        self.assertTrue(result['query_only'])
        self.assertEqual(0, result['decision_cycles']['rows'])
        self.assertFalse(result['decision_cycles']['live_trade_execution_verified'])
        self.assertIsNone(result['decision_cycles']['last_at'])

    def test_cycle_projection_redacts_ids_cash_sources_and_unknown_codes(self):
        payload = {'state': 'blocked', 'lineage': {'account_id': SECRET}, 'cash': SECRET,
            'blockers': [{'code': 'investment_profile_incomplete', 'message': SECRET}, {'code': SECRET}],
            'candidates': [{'instrument_uid': SECRET}], 'proposed_action': {'secret': SECRET},
            'execution': {'real_orders_enabled': False}}
        self.db.execute('INSERT INTO portfolio_decision_cycles VALUES (?,?)', (NOW - 10, json.dumps(payload)))
        self.db.commit()
        result = self.observe()
        row = result['decision_cycles']['recent'][0]
        self.assertEqual(['investment_profile_incomplete', 'unknown'], row['blockers'])
        self.assertEqual(1, row['candidate_count'])
        self.assertEqual(10, row['age_seconds'])
        self.assertNotIn(SECRET, json.dumps(result))

    def test_bounded_malformed_cycle_payload_does_not_get_published(self):
        for raw in ('{"broken":', '[' + '[' * 1200, 'x' * 524289, '[]'):
            self.db.execute('INSERT INTO portfolio_decision_cycles VALUES (?,?)', (NOW, raw))
        self.db.commit()
        self.assertEqual([False] * 4, [row['payload_valid'] for row in self.observe()['decision_cycles']['recent']])

    def test_future_observation_is_not_silently_labelled_fresh(self):
        self.db.execute('INSERT INTO portfolio_decision_cycles VALUES (?,?)', (NOW + 90, '{}'))
        self.db.commit()
        self.assertEqual(-90, self.observe()['decision_cycles']['recent'][0]['age_seconds'])

    def test_discovery_projection_redacts_nonfinite_and_nested_values(self):
        payload = {'reasons': [{'code': 'research_incomplete'}, {'code': SECRET}],
            'coverage': {'scanned': 500, 'eligible': True, 'reviewed': {'secret': SECRET}, 'constraint_checks_passed': -1}}
        self.db.execute('INSERT INTO automation_discovery VALUES (?,?,?,?,?)', ('partial', NOW, NOW, NOW + 20, json.dumps(payload)))
        self.db.commit()
        result = self.observe()['discovery'][0]
        self.assertEqual({'scanned': 500, 'eligible': None, 'reviewed': None, 'constraint_checks_passed': None}, result['coverage'])
        self.assertEqual(['research_incomplete', 'unknown'], result['reasons'])

    def test_chat_route_and_usage_projection_without_question_or_ids(self):
        self.db.execute('INSERT INTO workspace_jobs VALUES (?,?,?,?,?,?,?,?,?,?)',
            (SECRET, 123, 'chat', 'failed', 'model_running', 'ai_incomplete_response', 1, NOW, NOW + 3, None))
        route = {'model': 'dashscope/qwen3.5-flash', 'selected_tier': 'standard', 'required_tier': 'fast',
                 'max_output_tokens': 1200, 'route_id': SECRET, 'pricing_expires_at': SECRET}
        self.db.execute('INSERT INTO workspace_chat_messages VALUES (?,?,?,?)',
            (SECRET, 123, 'user', json.dumps({'routing': route, 'text': SECRET})))
        self.db.execute('INSERT INTO ai_money_reservations VALUES (?,?,?,?,?,?)',
            ('dashscope/qwen3.5-flash', 'settled', 1234, 1200, NOW, NOW + 2))
        self.db.commit()
        result = self.observe()
        row = result['workspace_jobs']['recent_chat'][0]
        self.assertEqual('ai_incomplete_response', row['error_code'])
        self.assertEqual(1200, row['saved_route']['max_output_tokens'])
        self.assertEqual(1200, result['model_usage']['recent'][0]['output_tokens'])
        self.assertFalse(result['model_usage']['job_link_verified'])
        self.assertNotIn(SECRET, json.dumps(result))

    def test_no_cross_user_route_inheritance(self):
        self.db.execute('INSERT INTO workspace_jobs VALUES (?,?,?,?,?,?,?,?,?,?)',
            ('one', 123, 'chat', 'failed', 'model_running', None, 0, NOW, NOW, None))
        self.db.execute('INSERT INTO workspace_chat_messages VALUES (?,?,?,?)',
            ('one', 124, 'user', json.dumps({'routing': {'max_output_tokens': 4000}})))
        self.db.commit()
        self.assertIsNone(self.observe()['workspace_jobs']['recent_chat'][0]['saved_route'])

    def test_unknown_model_and_arbitrary_errors_are_redacted(self):
        self.db.execute('INSERT INTO workspace_jobs VALUES (?,?,?,?,?,?,?,?,?,?)',
            (SECRET, 1, 'chat', SECRET, SECRET, SECRET, 0, NOW, NOW, None))
        self.db.execute('INSERT INTO ai_money_reservations VALUES (?,?,?,?,?,?)', (SECRET, SECRET, None, None, NOW, NOW))
        self.db.commit()
        result = self.observe()
        self.assertNotIn(SECRET, json.dumps(result))
        self.assertEqual('unknown', result['model_usage']['recent'][0]['model'])

    def test_expired_paid_jobs_are_observed_without_requeue_or_refund(self):
        self.db.execute('INSERT INTO workspace_jobs VALUES (?,?,?,?,?,?,?,?,?,?)',
            ('one', 1, 'chat', 'running', 'model_running', None, 1, NOW - 999, NOW - 999, NOW - 1))
        self.db.execute('INSERT INTO ai_money_reservations VALUES (?,?,?,?,?,?)',
            ('dashscope/qwen3.5-flash', 'reserved', None, None, NOW, NOW))
        self.db.commit()
        before = self.path.read_bytes()
        result = self.observe()
        self.assertEqual(1, result['workspace_jobs']['running_expired'])
        self.assertTrue(result['workspace_jobs']['recent_chat'][0]['running_lease_expired'])
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual('running', self.db.execute('SELECT state FROM workspace_jobs').fetchone()[0])
        self.assertEqual('reserved', self.db.execute('SELECT state FROM ai_money_reservations').fetchone()[0])

    def test_wal_sees_committed_rows_and_keeps_one_snapshot_while_writer_progresses(self):
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('INSERT INTO portfolio_decision_cycles VALUES (?,?)', (NOW, '{}'))
        self.db.commit()
        original = observer.observe_cycles
        def concurrent_commit(db, now):
            value = original(db, now)
            self.db.execute('INSERT INTO workspace_snapshots VALUES (?)', (NOW,))
            self.db.commit()
            return value
        with patch.object(observer, 'observe_cycles', side_effect=concurrent_commit):
            result = self.observe()
        self.assertEqual('wal', result['journal_mode'])
        self.assertEqual(1, result['decision_cycles']['rows'])
        self.assertEqual(0, result['snapshot_metadata']['rows'])
        self.assertEqual(1, self.db.execute('SELECT COUNT(*) FROM workspace_snapshots').fetchone()[0])

    def test_authorizer_rejects_writes_and_secret_table_reads(self):
        with sqlite3.connect(self.path) as db:
            db.set_authorizer(observer.authorize)
            with self.assertRaises(sqlite3.DatabaseError):
                db.execute('SELECT secret FROM users').fetchall()
            with self.assertRaises(sqlite3.DatabaseError):
                db.execute('DELETE FROM workspace_jobs')
            with self.assertRaises(sqlite3.DatabaseError):
                db.execute('ATTACH DATABASE ? AS extra', (str(self.root / 'extra.db'),))
        self.assertFalse((self.root / 'extra.db').exists())

    def test_missing_tables_are_reported_without_creation(self):
        self.db.execute('DROP TABLE portfolio_decision_cycles')
        self.db.commit()
        result = self.observe()
        self.assertEqual(['portfolio_decision_cycles'], result['missing_tables'])
        self.assertNotIn('decision_cycles', result)

    def test_missing_database_not_created_and_symlink_rejected(self):
        missing = self.root / 'missing.db'
        with self.assertRaises(RuntimeError):
            observer.observe_database(missing, NOW)
        self.assertFalse(missing.exists())
        linked = self.root / 'linked.db'
        linked.symlink_to(self.path)
        with self.assertRaises(RuntimeError):
            observer.observe_database(linked, NOW)

    def test_service_read_allowlist_redacts_unexpected_properties(self):
        class Result:
            stdout = ('ActiveState=active\nSubState=running\nNRestarts=2\nEnvironment=' + SECRET).encode()
        with patch.object(observer.subprocess, 'run', return_value=Result()) as command:
            result = observer.services()
        self.assertEqual(2, command.call_count)
        self.assertTrue(all(call.args[0][1] == 'show' for call in command.call_args_list))
        self.assertNotIn(SECRET, json.dumps(result))

    def test_module_change_rejects_observation_of_wrong_runtime(self):
        with self.assertRaises(RuntimeError):
            observer.verify_source(self.root)
        for name in observer.INSTALLED:
            (self.root / name).write_text('different bytes')
        with self.assertRaisesRegex(RuntimeError, 'runtime_source_changed'):
            observer.verify_source(self.root)

    def test_recent_rows_are_bounded(self):
        self.db.executemany('INSERT INTO portfolio_decision_cycles VALUES (?,?)', [(NOW + i, '{}') for i in range(20)])
        self.db.commit()
        result = self.observe()['decision_cycles']
        self.assertEqual(20, result['rows'])
        self.assertEqual(12, len(result['recent']))

    def test_transport_preparation_binds_exact_runtime_without_application_import(self):
        destination = self.root / 'deploy/plan-20261027'
        destination.mkdir(parents=True)
        source = self.root / 'deploy/runtime_diagnostic.py'
        source.write_bytes(b'reviewed diagnostic bytes')
        with patch.object(preparer, 'Path', side_effect=lambda relative: self.root / relative):
            preparer.main()
        self.assertEqual(source.read_bytes(), (destination / 'operation.py').read_bytes())
        self.assertEqual({'source_commit': observer.SOURCE}, json.loads((destination / 'payload.json').read_text()))

    def test_transport_refuses_missing_or_redirected_destination(self):
        with patch.object(preparer, 'Path', side_effect=lambda relative: self.root / relative):
            with self.assertRaises(RuntimeError):
                preparer.main()
        (self.root / 'deploy').mkdir()
        (self.root / 'deploy/plan-20261027').symlink_to(self.root, target_is_directory=True)
        with patch.object(preparer, 'Path', side_effect=lambda relative: self.root / relative):
            with self.assertRaises(RuntimeError):
                preparer.main()


if __name__ == '__main__':
    unittest.main()
