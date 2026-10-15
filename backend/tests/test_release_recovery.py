"""Synthetic publication failure tests; these bytes are NOT installable APKs."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend import release_publication as publication
from backend.client_updates import AndroidRelease, ReleaseChannel, ReleaseUnavailable

PACKAGE = 'ru.omnicio.app.debug'
CERTIFICATE = 'c' * 64


class PublicationRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'releases'
        self.apk = Path(self.temp.name) / 'synthetic.apk'
        self.apk.write_bytes(b'publication regression input, not a real apk')
        self.channel = ReleaseChannel(self.root)

    def report(self, code=23):
        digest = hashlib.sha256(self.apk.read_bytes()).hexdigest()
        checks = dict(clean_install=True, upgrade=True, launch=True)
        return dict(package=PACKAGE, version_code=code, version_name=f'test-{code}',
                    min_sdk=36, sha256=digest, bytes=self.apk.stat().st_size,
                    certificate_sha256=CERTIFICATE, signature_v2=True, zipalign_16kb=True,
                    debuggable=False, test_only=False,
                    installation_evidence={'apk_sha256': digest, '36': checks})

    def publish(self, code=23, now=200, notes=''):
        return publication.publish(self.root, self.apk, self.report(code),
                                   expected_certificate=CERTIFICATE, now=now, notes=notes)

    def interrupt_before_activation(self):
        original = publication._manifest

        def fail_current(directory, destination, release, *, immutable):
            if destination.name == 'current.json':
                raise OSError('injected interruption before activation')
            return original(directory, destination, release, immutable=immutable)

        with patch.object(publication, '_manifest', side_effect=fail_current):
            with self.assertRaisesRegex(OSError, 'injected interruption'):
                self.publish(now=100)
        report = self.report()
        name = f"Analyst-AI-23-{report['sha256']}.json"
        return AndroidRelease.parse(json.loads((self.root / PACKAGE / name).read_text(encoding='utf-8')))

    def test_first_publication_resumes_without_rewriting_timestamp(self):
        retained = self.interrupt_before_activation()
        self.assertFalse((self.root / PACKAGE / 'current.json').exists())
        recovered = self.publish(now=200)
        self.assertEqual(recovered, retained)
        self.assertEqual(recovered.published_at, 100)
        self.assertEqual(self.channel.current(PACKAGE), recovered)

    def test_previous_current_remains_until_recovery(self):
        old = self.publish(code=22, now=50)
        self.apk.write_bytes(b'new synthetic publication bytes')
        retained = self.interrupt_before_activation()
        self.assertEqual(self.channel.current(PACKAGE), old)
        self.assertEqual(self.publish(now=200), retained)
        self.assertEqual(self.channel.published(PACKAGE, old.filename), old)

    def test_retry_cannot_change_prepared_minimum_android(self):
        self.interrupt_before_activation()
        report = self.report()
        report['min_sdk'] = 34
        with self.assertRaisesRegex(ReleaseUnavailable, 'identity_changed'):
            publication.publish(self.root, self.apk, report,
                                expected_certificate=CERTIFICATE, now=200)
        self.assertFalse((self.root / PACKAGE / 'current.json').exists())

    def test_retry_cannot_change_prepared_notes(self):
        self.interrupt_before_activation()
        with self.assertRaisesRegex(ReleaseUnavailable, 'identity_changed'):
            self.publish(now=200, notes='different release')
        self.assertFalse((self.root / PACKAGE / 'current.json').exists())

    def test_corrupt_prepared_bytes_never_activate(self):
        retained = self.interrupt_before_activation()
        (self.root / PACKAGE / retained.filename).write_bytes(b'x' * retained.apk_bytes)
        with self.assertRaises(ReleaseUnavailable):
            self.publish(now=200)
        self.assertFalse((self.root / PACKAGE / 'current.json').exists())

    def test_verified_file_rejects_directory_symlink(self):
        release = self.publish()
        directory = self.root / PACKAGE
        original = Path.is_symlink
        with patch.object(Path, 'is_symlink', lambda p: p == directory or original(p)):
            with self.assertRaises(ReleaseUnavailable):
                self.channel.verified_file(release)

    def test_idempotent_current_cannot_silently_change_notes(self):
        current = self.publish()
        with self.assertRaisesRegex(ReleaseUnavailable, 'identity_changed'):
            self.publish(notes='changed')
        self.assertEqual(self.channel.current(PACKAGE), current)


if __name__ == '__main__':
    unittest.main()
