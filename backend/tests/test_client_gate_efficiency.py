"""Real gate and SHA-256 reader; synthetic bytes are explicitly not an APK."""
from contextlib import closing
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

from backend import client_updates as updates


class ClientGateEfficiencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.database = self.root / 'sessions.sqlite'
        self.package = updates.PREVIEW_PACKAGE
        self.directory = self.root / 'releases' / self.package
        self.directory.mkdir(parents=True)
        self.data = b'Synthetic data for hashing, not an Android application.'
        digest = hashlib.sha256(self.data).hexdigest()
        self.release = updates.AndroidRelease(self.package, 23, 'test-23', digest, len(self.data), 'c' * 64, 33, int(time.time()) - 10)
        self.apk = self.directory / self.release.filename
        self.apk.write_bytes(self.data)
        (self.directory / 'current.json').write_text(json.dumps({'schema_version': 1, **asdict(self.release)}))
        with closing(self.connect()) as db:
            db.execute('CREATE TABLE sessions(token_hash TEXT PRIMARY KEY,user_id INTEGER,expires_at INTEGER)')
            db.commit()
        updates.initialize(self.connect)
        self.env = patch.dict('os.environ', ANDROID_UPDATES_ENABLED='true', ANDROID_RELEASE_DIR=str(self.root / 'releases'))
        self.env.start()
        self.addCleanup(self.env.stop)

    def connect(self):
        return sqlite3.connect(self.database)

    def add(self, count=1, version=23):
        with closing(self.connect()) as db:
            for index in range(count):
                key = f'test-session-{version}-{index}'
                db.execute('INSERT INTO sessions VALUES(?,?,?)', (key, 1, int(time.time()) + 3600))
                db.execute('INSERT INTO client_versions VALUES(?,?,?,?,?,?)', (key, 1, self.package, version, self.release.apk_sha256, int(time.time())))
            db.commit()

    def test_120_outdated_sessions_perform_one_full_artifact_hash(self):
        self.add(120, version=22)
        with patch.object(updates, '_file_digest', wraps=updates._file_digest) as reader:
            self.assertFalse(updates.user_can_run(self.connect, 1))
        self.assertEqual(reader.call_count, 1)

    def test_current_session_survives_many_stale_devices(self):
        self.add(120, version=22)
        self.add()
        with patch.object(updates, '_file_digest', wraps=updates._file_digest) as reader:
            self.assertTrue(updates.user_can_run(self.connect, 1))
        self.assertEqual(reader.call_count, 1)

    def test_next_permission_check_detects_same_size_modified_bytes(self):
        self.add()
        self.assertTrue(updates.user_can_run(self.connect, 1))
        self.apk.write_bytes(b'X' * len(self.data))
        self.assertFalse(updates.user_can_run(self.connect, 1))

    def test_revocation_on_another_connection_while_hashing_is_not_ignored(self):
        self.add()
        original = updates._file_digest
        def revoke(path, expected_size):
            digest = original(path, expected_size)
            with closing(self.connect()) as db:
                db.execute('DELETE FROM sessions')
                db.commit()
            return digest
        with patch.object(updates, '_file_digest', side_effect=revoke):
            self.assertFalse(updates.user_can_run(self.connect, 1))

    def test_disabled_gate_still_preserves_bootstrap_clients(self):
        with patch.dict('os.environ', ANDROID_UPDATES_ENABLED='false'), patch.object(updates, '_file_digest') as reader:
            self.assertTrue(updates.user_can_run(self.connect, 1))
        reader.assert_not_called()

    def test_index_migration_is_idempotent_and_keeps_sessions(self):
        self.add()
        updates.initialize(self.connect)
        updates.initialize(self.connect)
        self.assertTrue(updates.user_can_run(self.connect, 1))
        with closing(self.connect()) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0], 1)
            self.assertIn('client_versions_identity', [row[1] for row in db.execute('PRAGMA index_list(client_versions)')])


if __name__ == '__main__':
    unittest.main()
