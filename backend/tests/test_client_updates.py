"""Synthetic update-channel tests; no actual APK install or production access."""
from contextlib import closing
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient
from backend import client_updates as updates
from backend.client_updates import ReleaseUnavailable
from backend.release_publication import publish
from backend.tests.android_runtime_fixtures import publication_report

CERT = 'c' * 64


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.path = self.root / 'test.db'
        self.env = patch.dict(os.environ, {'ANDROID_RELEASE_DIR': str(self.root), 'ANDROID_UPDATES_ENABLED': 'true'})
        self.env.start()
        with closing(self.connect()) as db:
            db.execute('CREATE TABLE sessions(token_hash TEXT PRIMARY KEY, user_id INTEGER, expires_at INTEGER)')
            for raw, uid in [('test', 1), ('other', 2), ('second-device', 1)]:
                db.execute('INSERT INTO sessions VALUES(?,?,?)', (hashlib.sha256(raw.encode()).hexdigest(), uid, int(time.time())+10000))
            db.commit()
        updates.initialize(self.connect)
        self.apk = self.root / 'synthetic-input.apk'
        self.apk.write_bytes(b'synthetic archive test bytes; NOT an installable APK')
        self.report = self.evidence()
        self.release = publish(self.root, self.apk, self.report, expected_certificate=CERT)

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    def evidence(self, version=23):
        sha = hashlib.sha256(self.apk.read_bytes()).hexdigest()
        checks = {
            'clean_install': True,
            'upgrade': True,
            'upgrade_launch': True,
            'launch': True,
        }
        return publication_report({'sha256': sha, 'bytes': self.apk.stat().st_size, 'certificate_sha256': CERT,
                'signature_v2': True, 'zipalign_16kb': True, 'test_only': False, 'debuggable': False,
                'package': 'ru.omnicio.app.debug', 'version_code': version, 'version_name': '0.6.0-preview',
                'min_sdk': 36, 'installation_evidence': {'apk_sha256': sha, '36': checks}})

    def test_current_release_requires_exact_os_and_complete_runtime_transcripts(self):
        evidence = self.evidence(24)
        incomplete = dict(evidence)
        incomplete.pop('installation_tests')
        with self.assertRaises(ReleaseUnavailable):
            publish(self.root, self.apk, incomplete, expected_certificate=CERT)
        for minimum in (34, 35, 36, 38, '37', True):
            invalid = dict(evidence, min_sdk=minimum)
            with self.subTest(minimum=minimum), self.assertRaises(ReleaseUnavailable):
                publish(self.root, self.apk, invalid, expected_certificate=CERT)
        incomplete = dict(evidence, installation_tests=evidence['installation_tests'][:1])
        with self.assertRaises(ReleaseUnavailable):
            publish(self.root, self.apk, incomplete, expected_certificate=CERT)
        result = publish(self.root, self.apk, evidence, expected_certificate=CERT)
        self.assertEqual(result.min_sdk, 37)

    def enforce(self, version='23', token='test', uid=1, package='ru.omnicio.app.debug'):
        return updates.enforce(self.connect, user_id=uid, authorization='Bearer '+token,
            headers={updates.CODE_HEADER: version, updates.PACKAGE_HEADER: package})

    def test_current_client_allows_work(self):
        self.assertFalse(updates.user_can_run(self.connect, 1))
        self.enforce()
        self.assertTrue(updates.user_can_run(self.connect, 1))

    def test_old_missing_invalid_future_versions_denied(self):
        for value in ('22', '', '23.0', '024', '9999999999', '24', '-1'):
            with self.subTest(version=value), self.assertRaises(HTTPException) as error:
                self.enforce(value)
            self.assertEqual(error.exception.status_code, 426)

    def test_other_user_not_resumed(self):
        self.enforce()
        self.assertFalse(updates.user_can_run(self.connect, 2))

    def test_old_device_cannot_suspend_current_other_device(self):
        self.enforce(token='second-device')
        with self.assertRaises(HTTPException):
            self.enforce('22')
        self.assertTrue(updates.user_can_run(self.connect, 1))

    def test_new_release_pauses_until_authenticated_current_call(self):
        self.enforce()
        self.apk.write_bytes(b'new synthetic archive bytes')
        publish(self.root, self.apk, self.evidence(24), expected_certificate=CERT)
        self.assertFalse(updates.user_can_run(self.connect, 1))
        self.enforce('24')
        self.assertTrue(updates.user_can_run(self.connect, 1))

    def test_wrong_package_cannot_resume(self):
        with self.assertRaises(HTTPException): self.enforce(package='wrong.package')
        self.assertFalse(updates.user_can_run(self.connect, 1))

    def test_expired_session_does_not_resume_jobs(self):
        self.enforce()
        with closing(self.connect()) as db:
            db.execute('UPDATE sessions SET expires_at=0')
            db.commit()
        self.assertFalse(updates.user_can_run(self.connect, 1))

    def test_channel_read_checks_checksum_not_only_length(self):
        channel = updates.channel()
        path = channel.verified_file(self.release)
        path.write_bytes(b'x'*self.release.apk_bytes)
        with self.assertRaises(updates.ReleaseUnavailable):
            channel.current(self.release.package_name)

    def test_missing_artifact_is_not_ready(self):
        updates.channel().verified_file(self.release).unlink()
        with self.assertRaises(HTTPException) as error: self.enforce()
        self.assertEqual(error.exception.status_code, 503)

    def test_enforcement_is_opt_in_and_does_not_break_bootstrap(self):
        with patch.dict(os.environ, {'ANDROID_UPDATES_ENABLED': 'false'}):
            self.enforce('22')
            self.assertTrue(updates.user_can_run(self.connect, 1))

    def test_downgrade_and_version_reuse_rejected(self):
        self.apk.write_bytes(b'changed package')
        for version in (22, 23):
            report = self.evidence(version)
            with self.assertRaises(updates.ReleaseUnavailable):
                publish(self.root, self.apk, report, expected_certificate=CERT)
        self.assertEqual(updates.channel().current(self.release.package_name), self.release)

    def test_repeat_publish_idempotent(self):
        self.assertEqual(publish(self.root, self.apk, self.report, expected_certificate=CERT), self.release)

    def test_missing_failed_or_unbound_install_tests_prevent_activation(self):
        for kind in ('missing', 'failed', 'missing_upgrade_launch', 'unbound'):
            report = self.evidence(24)
            if kind == 'missing':
                del report['installation_evidence']
            elif kind == 'failed':
                report['installation_evidence']['runtimes']['api37-4096']['launch'] = False
            elif kind == 'missing_upgrade_launch':
                del report['installation_evidence']['runtimes']['api37-4096']['upgrade_launch']
            else:
                report['installation_evidence']['apk_sha256'] = 'f'*64
            with self.assertRaises(updates.ReleaseUnavailable):
                publish(self.root, self.apk, report, expected_certificate=CERT)

    def test_invalid_manifest_values_rejected(self):
        for field, value in [('version_code', True), ('apk_bytes', 0), ('apk_sha256', '../x'),
                             ('min_sdk', 1), ('version_name', '\ninvalid'), ('schema_version', True)]:
            raw = {'schema_version': 1, **asdict(self.release), field: value}
            with self.subTest(field=field), self.assertRaises(updates.ReleaseUnavailable):
                updates.AndroidRelease.parse(raw)

    def test_symlink_apk_is_not_served(self):
        channel = updates.channel()
        with patch.object(Path, 'is_symlink', return_value=True):
            with self.assertRaises(updates.ReleaseUnavailable):
                channel.verified_file(self.release)

    def test_http_bootstrap_download_and_authenticated_resume(self):
        app = FastAPI()
        def authenticate(authorization: str | None = Header(default=None)):
            if authorization != 'Bearer test': raise HTTPException(401, 'invalid_session')
            return {'id': 1}
        updates.install_routes(app, self.connect, authenticate)
        with TestClient(app) as client:
            policy = client.get('/client/update-policy')
            self.assertEqual(policy.status_code, 200)
            self.assertEqual(policy.headers['cache-control'], 'no-store')
            apk = client.get(policy.json()['apk_path'])
            self.assertEqual(apk.content, self.apk.read_bytes())
            self.assertEqual(client.post('/client/ready').status_code, 401)
            self.assertEqual(client.post('/client/ready', headers={'Authorization':'Bearer test'}).status_code, 426)
            self.assertFalse(updates.user_can_run(self.connect, 1))
            response = client.post('/client/ready', headers={'Authorization':'Bearer test',
                updates.CODE_HEADER:'23', updates.PACKAGE_HEADER:'ru.omnicio.app.debug'})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(updates.user_can_run(self.connect, 1))
            self.assertEqual(client.get('/client/apk/other.apk').status_code, 404)


if __name__ == '__main__': unittest.main()