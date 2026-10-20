"""Real application wiring tests; isolated SQLite and synthetic non-installable APK."""
from contextlib import closing
from datetime import UTC, datetime
import hashlib
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

os.environ.setdefault('TELEGRAM_CLIENT_ID', '123456')
os.environ.setdefault('TELEGRAM_CLIENT_SECRET', 'test-only')
os.environ.setdefault('BACKEND_PUBLIC_URL', 'https://example.invalid')
os.environ.setdefault('FERNET_KEY', 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=')
os.environ['ANALYSIS_SCHEDULER_ENABLED'] = 'false'

from fastapi import HTTPException
from fastapi.testclient import TestClient
from backend import app as backend
from backend import autonomous_ai as ai
from backend import client_updates as updates
from backend.release_publication import publish
from backend.monitoring_access import monitoring_connection
from backend.portfolio_details import record_history
from backend.tests.test_autonomous_ai import sample_snapshot
from backend.tests.android_runtime_fixtures import publication_report


class ApplicationUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.path_patch = patch.object(backend, 'DATABASE_PATH', self.root/'test.db')
        self.path_patch.start()
        self.env = patch.dict(os.environ, {'ANDROID_RELEASE_DIR':str(self.root/'releases'), 'ANDROID_UPDATES_ENABLED':'true'})
        self.env.start()
        backend.init_db()
        ai.init_autonomous_db()
        with closing(backend.connect()) as db:
            db.execute("INSERT INTO users(telegram_sub,telegram_id,tinvest_token_encrypted,created_at,updated_at) VALUES('test','1',?,1,1)", (b'fake-only',))
            self.uid = int(db.execute('SELECT id FROM users').fetchone()[0])
            db.execute('INSERT INTO sessions VALUES(?,?,?)', (backend.hash_token('test'), self.uid, int(time.time())+3600))
            db.commit()
        self.client = TestClient(backend.app)
        self.release = self.publish(23)

    def tearDown(self):
        self.client.close()
        self.env.stop()
        self.path_patch.stop()
        self.temp.cleanup()

    def publish(self, version):
        apk = self.root/'source.apk'
        apk.write_bytes(f'not an APK, synthetic version {version}'.encode())
        sha = hashlib.sha256(apk.read_bytes()).hexdigest()
        checks = {
            'clean_install': True,
            'upgrade': True,
            'upgrade_launch': True,
            'launch': True,
        }
        evidence = {'sha256':sha,'bytes':apk.stat().st_size,'certificate_sha256':'c'*64,
            'signature_v2':True,'zipalign_16kb':True,'debuggable':False,'test_only':False,
            'package':'ru.omnicio.app.debug','version_code':version,'version_name':str(version),'min_sdk':36,
            'installation_evidence':{'apk_sha256':sha,'36':checks}}
        evidence = publication_report(evidence)
        return publish(self.root/'releases',apk,evidence,expected_certificate='c'*64)

    def headers(self, version=23):
        return {'Authorization':'Bearer test',updates.CODE_HEADER:str(version), updates.PACKAGE_HEADER:'ru.omnicio.app.debug'}

    def test_real_auth_rejects_missing_session_before_version(self):
        self.assertEqual(self.client.get('/me', headers={updates.CODE_HEADER:'22'}).status_code,401)

    def test_old_build_rejected_without_deleting_session_or_token(self):
        self.assertEqual(self.client.get('/me',headers=self.headers(22)).status_code,426)
        with closing(backend.connect()) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT tinvest_token_encrypted FROM users').fetchone()[0],b'fake-only')

    def test_current_authenticated_build_reports_client_readiness(self):
        self.assertFalse(updates.user_can_run(backend.connect,self.uid))
        self.assertEqual(self.client.post('/client/ready',headers=self.headers()).status_code,200)
        self.assertEqual(self.client.get('/me',headers=self.headers()).status_code,200)
        self.assertTrue(updates.user_can_run(backend.connect,self.uid))

    def test_public_download_does_not_require_old_session(self):
        response = self.client.get('/client/update-policy')
        self.assertEqual(response.status_code,200)
        download = self.client.get(response.json()['apk_path'])
        self.assertEqual(download.status_code,200)
        self.assertFalse(updates.user_can_run(backend.connect,self.uid))

    def run_without_paid_ai(self, *, collect=None):
        with patch.object(ai, 'get_tinvest_portfolio',
                          side_effect=collect, return_value=sample_snapshot(stock_share=90)) as broker, \
                patch.object(ai.GuardedAIClient, 'check_ready', side_effect=ai.GuardError('test_ai_disabled')), \
                patch.object(ai, 'analyze_if_needed') as model:
            result = ai.run_user_analysis(self.uid)
        model.assert_not_called()
        broker.assert_called_once()
        return result

    def count_rows(self, table):
        queries = {
            'portfolio_snapshots': 'SELECT COUNT(*) FROM portfolio_snapshots',
            'insight_cards': 'SELECT COUNT(*) FROM insight_cards',
            'analysis_runs': 'SELECT COUNT(*) FROM analysis_runs',
            'portfolio_value_history': 'SELECT COUNT(*) FROM portfolio_value_history',
        }
        with closing(backend.connect()) as db:
            return db.execute(queries[table]).fetchone()[0]

    def change_connection(self, value):
        with closing(backend.connect()) as db:
            db.execute('UPDATE users SET tinvest_token_encrypted=? WHERE id=?', (value, self.uid))
            db.commit()

    def test_background_risk_check_runs_without_current_apk(self):
        self.assertFalse(updates.user_can_run(backend.connect, self.uid))
        result = self.run_without_paid_ai()
        self.assertEqual(result['state'], 'fallback')
        self.assertEqual(result['reason'], 'risk_event')
        self.assertEqual(self.count_rows('portfolio_snapshots'), 1)
        self.assertEqual(self.count_rows('insight_cards'), 1)
        self.assertGreater(self.count_rows('portfolio_value_history'), 0)
        self.assertEqual(self.client.get('/me', headers=self.headers(22)).status_code, 426)

    def test_scheduler_enqueues_connected_users_without_client_readiness(self):
        with patch.object(ai.AnalysisQueue, 'enqueue') as enqueue, \
                patch.object(ai, 'drain', return_value={}) as drain:
            ai.run_scheduler_cycle()
        enqueue.assert_called_once_with(self.uid)
        drain.assert_called_once()

    def test_expired_or_missing_android_session_does_not_stop_monitoring(self):
        for expires in (0, None):
            with self.subTest(expires=expires):
                with closing(backend.connect()) as db:
                    if expires is None:
                        db.execute('DELETE FROM sessions')
                    else:
                        db.execute('UPDATE sessions SET expires_at=?', (expires,))
                    db.commit()
                result = self.run_without_paid_ai()
                self.assertNotEqual(result['state'], 'paused')
        self.assertEqual(self.count_rows('portfolio_snapshots'), 2)
        self.assertEqual(self.client.get('/me', headers=self.headers()).status_code, 401)

    def test_release_change_during_collection_keeps_monitoring_but_gates_client(self):
        self.client.post('/client/ready', headers=self.headers())
        def collected(**_):
            self.publish(24)
            return sample_snapshot(stock_share=90)
        result = self.run_without_paid_ai(collect=collected)
        self.assertEqual(result['reason'], 'risk_event')
        self.assertEqual(self.count_rows('portfolio_snapshots'), 1)
        self.assertEqual(self.count_rows('insight_cards'), 1)
        self.assertEqual(self.client.get('/me', headers=self.headers(23)).status_code, 426)

    def test_unavailable_apk_channel_does_not_stop_server_collection(self):
        updates.channel().verified_file(self.release).unlink()
        self.run_without_paid_ai()
        self.assertEqual(self.count_rows('portfolio_snapshots'), 1)
        self.assertEqual(self.client.get('/me', headers=self.headers()).status_code, 503)

    def test_disconnected_user_is_not_collected_or_enqueued(self):
        self.change_connection(None)
        with patch.object(ai, 'get_tinvest_portfolio') as broker, \
                patch.object(ai, 'analyze_if_needed') as model, \
                self.assertRaises(HTTPException) as raised:
            ai.run_user_analysis(self.uid)
        self.assertEqual(raised.exception.detail, 'tinvest_not_connected')
        broker.assert_not_called()
        model.assert_not_called()
        with patch.object(ai.AnalysisQueue, 'enqueue') as enqueue, \
                patch.object(ai, 'drain', return_value={}):
            ai.run_scheduler_cycle()
        enqueue.assert_not_called()

    def test_revoked_or_replaced_connection_discards_inflight_collection(self):
        for replacement in (None, b'replacement-test-token'):
            with self.subTest(replacement=replacement):
                self.change_connection(b'fake-only')
                def collected(**_):
                    self.change_connection(replacement)
                    return sample_snapshot(stock_share=90)
                with patch.object(ai, 'get_tinvest_portfolio', side_effect=collected), \
                        patch.object(ai, 'analyze_if_needed') as model, \
                        self.assertRaises(HTTPException) as raised:
                    ai.run_user_analysis(self.uid)
                self.assertEqual(raised.exception.detail, 'monitoring_connection_changed')
                model.assert_not_called()
                self.assertEqual(self.count_rows('portfolio_snapshots'), 0)
                self.assertEqual(self.count_rows('insight_cards'), 0)

    def test_connection_revoked_during_ai_is_not_published(self):
        def revoked(**_):
            self.change_connection(None)
            raise ai.GuardError('test_model_response')
        with patch.object(ai, 'get_tinvest_portfolio', return_value=sample_snapshot(stock_share=90)), \
                patch.object(ai.GuardedAIClient, 'check_ready'), \
                patch.object(ai, 'analyze_if_needed', side_effect=revoked), \
                self.assertRaises(HTTPException) as raised:
            ai.run_user_analysis(self.uid)
        self.assertEqual(raised.exception.detail, 'monitoring_connection_changed')
        self.assertEqual(self.count_rows('analysis_runs'), 0)
        self.assertEqual(self.count_rows('insight_cards'), 0)

    def test_writes_recheck_connection_and_scope_is_always_reset(self):
        snapshot = sample_snapshot()
        observed_at = datetime.now(UTC).isoformat()
        with monitoring_connection(self.uid, b'fake-only'):
            self.change_connection(None)
            with self.assertRaises(HTTPException):
                ai._save_snapshot(self.uid, snapshot)
            with self.assertRaises(HTTPException):
                record_history(self.uid, snapshot['accounts'], observed_at)
        self.assertEqual(self.count_rows('portfolio_snapshots'), 0)
        # A completed scope must not contaminate subsequent work after reconnect.
        self.change_connection(b'new-test-token')
        self.run_without_paid_ai()
        self.assertEqual(self.count_rows('portfolio_snapshots'), 1)

    def test_five_users_without_sessions_are_monitored_independently(self):
        with closing(backend.connect()) as db:
            for identifier in range(2, 6):
                db.execute(
                    "INSERT INTO users(telegram_sub,telegram_id,tinvest_token_encrypted,created_at,updated_at) "
                    "VALUES(?,?,?,1,1)", (str(identifier), str(identifier), b'fake-only')
                )
            db.execute('DELETE FROM sessions')
            db.commit()
        with patch.object(ai, 'get_tinvest_portfolio', return_value=sample_snapshot(stock_share=90)), \
                patch.object(ai.GuardedAIClient, 'check_ready', side_effect=ai.GuardError('test_ai_disabled')):
            result = ai.run_scheduler_cycle()
        self.assertEqual(result, {'processed': 5, 'failed': 0})
        with closing(backend.connect()) as db:
            self.assertEqual(len(db.execute('SELECT DISTINCT user_id FROM portfolio_snapshots').fetchall()), 5)
            self.assertEqual(len(db.execute('SELECT DISTINCT user_id FROM insight_cards').fetchall()), 5)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM ai_work_jobs WHERE status='completed'").fetchone()[0], 5)

    def test_monitoring_status_uses_observed_snapshots_not_ai_configuration(self):
        def user():
            with closing(backend.connect()) as db:
                return db.execute('SELECT * FROM users WHERE id=?', (self.uid,)).fetchone()
        with patch.object(ai, 'SCHEDULER_ENABLED', True):
            first = ai.monitoring_status(user(), {'state': 'not_scheduled'})
            self.assertEqual(first['state'], 'waiting')
            self.assertIsNone(first['last_snapshot_at'])
            self.run_without_paid_ai()
            current = ai.monitoring_status(user(), {'state': 'completed'})
            self.assertEqual(current['state'], 'current')
            self.assertIsNotNone(current['last_snapshot_at'])
            failed = ai.monitoring_status(user(), {'state': 'failed'})
            self.assertEqual(failed['state'], 'check_failed')
            with closing(backend.connect()) as db:
                db.execute('UPDATE portfolio_snapshots SET created_at=1')
                db.commit()
            self.assertEqual(ai.monitoring_status(user(), {})['state'], 'delayed')
            self.change_connection(None)
            self.assertEqual(ai.monitoring_status(user(), {})['state'], 'not_connected')
        with patch.object(ai, 'SCHEDULER_ENABLED', False):
            self.change_connection(b'fake-only')
            self.assertEqual(ai.monitoring_status(user(), {})['state'], 'disabled')

    def test_disabled_gate_preserves_existing_clients(self):
        with patch.dict(os.environ,{'ANDROID_UPDATES_ENABLED':'false'}):
            self.assertEqual(self.client.get('/me',headers={'Authorization':'Bearer test'}).status_code,200)


if __name__=='__main__': unittest.main()