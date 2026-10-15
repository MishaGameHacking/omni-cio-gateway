"""Real application wiring tests; isolated SQLite and synthetic non-installable APK."""
from contextlib import closing
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
from backend.tests.test_autonomous_ai import sample_snapshot


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
        evidence = {'sha256':sha,'bytes':apk.stat().st_size,'certificate_sha256':'c'*64,
            'signature_v2':True,'zipalign_16kb':True,'debuggable':False,'test_only':False,
            'package':'ru.omnicio.app.debug','version_code':version,'version_name':str(version),'min_sdk':36,
            'installation_evidence':{'apk_sha256':sha,'36':{'clean_install':True,'upgrade':True,'launch':True}}}
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

    def test_current_authenticated_build_resumes_account(self):
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

    def test_paused_analysis_makes_no_broker_or_model_call(self):
        with patch.object(ai,'get_tinvest_portfolio') as broker, patch.object(ai,'analyze_if_needed') as model:
            result=ai.run_user_analysis(self.uid)
        self.assertEqual(result['state'],'paused')
        broker.assert_not_called()
        model.assert_not_called()

    def test_scheduler_does_not_enqueue_outdated_users(self):
        with patch.object(ai.AnalysisQueue,'enqueue') as enqueue, patch.object(ai,'drain',return_value={}) as drain:
            ai.run_scheduler_cycle()
        enqueue.assert_not_called()
        drain.assert_called_once()

    def test_release_change_during_collection_blocks_further_analysis(self):
        self.client.post('/client/ready',headers=self.headers())
        def collected(**_):
            self.publish(24)
            return sample_snapshot()
        with patch.object(ai,'get_tinvest_portfolio',side_effect=collected), patch.object(ai,'analyze_if_needed') as model:
            with self.assertRaises(HTTPException) as raised:
                ai.run_user_analysis(self.uid)
        self.assertEqual(raised.exception.status_code,426)
        model.assert_not_called()
        with closing(backend.connect()) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM insight_cards').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM portfolio_snapshots').fetchone()[0],0)

    def test_disabled_gate_preserves_existing_clients(self):
        with patch.dict(os.environ,{'ANDROID_UPDATES_ENABLED':'false'}):
            self.assertEqual(self.client.get('/me',headers={'Authorization':'Bearer test'}).status_code,200)


if __name__=='__main__': unittest.main()
