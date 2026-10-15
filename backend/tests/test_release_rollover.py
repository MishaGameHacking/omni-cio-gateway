"""Synthetic channel tests: do not claim these bytes are an installable APK."""
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.client_updates import AndroidRelease, ReleaseChannel, ReleaseUnavailable, install_routes
from backend.release_publication import publish, publication_lock
from backend.release_lock import PublicationBusy

CERT = 'c' * 64
PACKAGE = 'ru.omnicio.app.debug'


class ReleaseRolloverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'releases'
        self.apk = Path(self.temp.name) / 'synthetic.apk'
        self.apk.write_bytes(b'synthetic test input, not an APK')
        self.channel = ReleaseChannel(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def report(self, version=23, certificate=CERT):
        sha = hashlib.sha256(self.apk.read_bytes()).hexdigest()
        checks = {'clean_install': True, 'upgrade': True, 'launch': True}
        return dict(sha256=sha, bytes=self.apk.stat().st_size, certificate_sha256=certificate,
                    signature_v2=True, zipalign_16kb=True, debuggable=False, test_only=False,
                    package=PACKAGE, version_code=version, version_name=f'test-{version}', min_sdk=36,
                    installation_evidence={'apk_sha256': sha, '36': checks})

    def publish(self, version=23):
        return publish(self.root, self.apk, self.report(version), expected_certificate=CERT)

    def test_previous_download_survives_rollout(self):
        old = self.publish()
        previous = self.apk.read_bytes()
        self.apk.write_bytes(b'new synthetic test bytes')
        current = self.publish(24)
        self.assertEqual(self.channel.current(PACKAGE), current)
        self.assertEqual(self.channel.published(PACKAGE, old.filename), old)
        self.assertEqual(self.channel.verified_file(old).read_bytes(), previous)

    def test_old_download_http_remains_available(self):
        old = self.publish()
        previous = self.apk.read_bytes()
        self.apk.write_bytes(b'new synthetic test bytes')
        self.publish(24)
        app = FastAPI()
        install_routes(app, lambda: None, lambda: {'id': 1})
        with patch.dict(os.environ, ANDROID_RELEASE_DIR=str(self.root)), TestClient(app) as client:
            response = client.get('/client/apk/' + old.filename)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content, previous)
            self.assertIn('immutable', response.headers['cache-control'])

    def test_legacy_metadata_is_backfilled(self):
        old = self.publish()
        archived = self.root / PACKAGE / (old.filename[:-4] + '.json')
        archived.unlink()
        self.apk.write_bytes(b'new synthetic test bytes')
        self.publish(24)
        self.assertTrue(archived.exists())
        self.assertEqual(self.channel.published(PACKAGE, old.filename), old)

    def test_legacy_current_download_without_archive(self):
        release = self.publish()
        (self.root / PACKAGE / (release.filename[:-4] + '.json')).unlink()
        self.assertEqual(self.channel.published(PACKAGE, release.filename), release)

    def test_future_publication_does_not_activate(self):
        report = self.report()
        future = int(time.time()) + 3600
        with self.assertRaises(ReleaseUnavailable):
            publish(self.root, self.apk, report, expected_certificate=CERT, now=future)
        self.assertFalse((self.root / PACKAGE / 'current.json').exists())

    def test_future_tampered_manifest_not_current(self):
        release = self.publish()
        path = self.root / PACKAGE / 'current.json'
        data = json.loads(path.read_text())
        data['published_at'] = int(time.time()) + 3600
        path.write_text(json.dumps(data))
        with self.assertRaises(ReleaseUnavailable):
            self.channel.current(PACKAGE)
        self.assertEqual(self.channel.published(PACKAGE, release.filename), release)

    def test_directory_symlink_rejected(self):
        release = self.publish()
        original = Path.is_symlink
        directory = self.root / PACKAGE
        with patch.object(Path, 'is_symlink', lambda p: p == directory or original(p)):
            with self.assertRaises(ReleaseUnavailable):
                self.channel.current(PACKAGE)
            with self.assertRaises(ReleaseUnavailable):
                self.channel.verified_file(release)

    def test_publication_does_not_follow_directory_symlink(self):
        original = Path.is_symlink
        directory = self.root / PACKAGE
        with patch.object(Path, 'is_symlink', lambda p: p == directory or original(p)):
            with self.assertRaises(ReleaseUnavailable):
                self.publish()

    def test_changed_certificate_not_hidden_by_idempotence(self):
        old = self.publish()
        changed_certificate = 'd' * 64
        report = self.report(certificate=changed_certificate)
        with self.assertRaisesRegex(ReleaseUnavailable, 'certificate_changed'):
            publish(self.root, self.apk, report, expected_certificate=changed_certificate)
        self.assertEqual(self.channel.current(PACKAGE), old)

    def test_changed_metadata_not_hidden_by_idempotence(self):
        old = self.publish()
        report = self.report()
        report['min_sdk'] = 34
        with self.assertRaisesRegex(ReleaseUnavailable, 'identity_changed'):
            publish(self.root, self.apk, report, expected_certificate=CERT)
        self.assertEqual(self.channel.current(PACKAGE), old)

    def test_unchanged_publication_is_idempotent(self):
        old = self.publish()
        self.assertEqual(self.publish(), old)

    def test_corrupt_archived_bytes_not_served(self):
        old = self.publish()
        self.apk.write_bytes(b'new synthetic test bytes')
        self.publish(24)
        (self.root / PACKAGE / old.filename).write_bytes(b'x' * old.apk_bytes)
        with self.assertRaises(ReleaseUnavailable):
            self.channel.published(PACKAGE, old.filename)

    def test_path_traversal_rejected(self):
        for name in ('../current.json', '/etc/passwd', 'other.apk', 'Analyst-AI-01-' + 'a' * 64 + '.apk'):
            with self.subTest(name=name), self.assertRaises(ReleaseUnavailable):
                self.channel.published(PACKAGE, name)

    def test_unknown_package_is_domain_error(self):
        raw = {'schema_version': 1, **asdict(self.publish())}
        raw['package_name'] = []
        with self.assertRaises(ReleaseUnavailable):
            AndroidRelease.parse(raw)

    def test_existing_publication_lock_not_removed(self):
        self.publish()
        directory = self.root / PACKAGE
        with publication_lock(directory):
            with self.assertRaises(PublicationBusy):
                self.publish(24)
            self.assertTrue((directory / '.publishing').exists())

    def test_manifest_too_large_is_rejected(self):
        self.publish()
        (self.root / PACKAGE / 'current.json').write_bytes(b' ' * 16_385)
        with self.assertRaises(ReleaseUnavailable):
            self.channel.current(PACKAGE)

    def test_failed_metadata_retention_keeps_current(self):
        old = self.publish()
        archived = self.root / PACKAGE / (old.filename[:-4] + '.json')
        archived.write_text('{}')
        self.apk.write_bytes(b'new synthetic test bytes')
        with self.assertRaises(ReleaseUnavailable):
            self.publish(24)
        self.assertEqual(self.channel.current(PACKAGE), old)
        # The stable lock file remains, but no process owns it after failure.
        with publication_lock(self.root / PACKAGE):
            self.assertTrue((self.root / PACKAGE / '.publishing').is_file())

    def test_directory_is_not_an_apk(self):
        directory = Path(self.temp.name)
        report = self.report()
        with self.assertRaises(ReleaseUnavailable):
            publish(self.root, directory, report, expected_certificate=CERT)

if __name__ == '__main__':
    unittest.main()
