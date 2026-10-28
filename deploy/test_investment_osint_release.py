"""Temporary-file deployment regressions; no services, credentials or live data."""
import base64
import hashlib
import io
import importlib.util
from pathlib import Path
import tempfile
import sqlite3
import time
import unittest
import zipfile
from unittest import mock

spec = importlib.util.spec_from_file_location('release', Path(__file__).with_name('investment_osint_release.py'))
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseFilesTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / 'runtime'
        self.root.mkdir()
        self.backup = self.root.parent / 'backup'
        self.backup.mkdir()
        (self.root / 'app.py').write_bytes(b'previous-app')
        self.changes = {
            'app.py': {'before': release.digest(b'previous-app'), 'after': release.digest(b'new-app'), 'content': 'new-app'},
            'schema_migrations.py': {'before': None, 'after': release.digest(b'new-module'), 'content': 'new-module'}}

    def test_success_keeps_original_bytes_and_installs_exact_source(self):
        calls = []
        release.install(self.root, self.backup, self.changes, lambda: calls.append(True))
        self.assertEqual(calls, [True])
        self.assertEqual((self.root / 'app.py').read_bytes(), b'new-app')
        self.assertEqual((self.backup / 'app.py').read_bytes(), b'previous-app')
        self.assertEqual((self.root / 'schema_migrations.py').read_bytes(), b'new-module')

    def test_failed_activation_restores_old_code_and_removes_new_module(self):
        def reject():
            raise RuntimeError('synthetic health failure')
        with self.assertRaisesRegex(RuntimeError, 'synthetic health failure'):
            release.install(self.root, self.backup, self.changes, reject)
        self.assertEqual((self.root / 'app.py').read_bytes(), b'previous-app')
        self.assertFalse((self.root / 'schema_migrations.py').exists())
        self.assertFalse(list(self.root.glob('*.server-release-new')))

    def test_existing_new_module_is_never_overwritten(self):
        (self.root / 'schema_migrations.py').write_bytes(b'other-work')
        with self.assertRaisesRegex(RuntimeError, 'new_module_already_exists'):
            release.install(self.root, self.backup, self.changes, lambda: None)
        self.assertEqual((self.root / 'app.py').read_bytes(), b'previous-app')
        self.assertEqual((self.root / 'schema_migrations.py').read_bytes(), b'other-work')

    def test_changed_baseline_rejects_before_replacing_any_file(self):
        (self.root / 'app.py').write_bytes(b'concurrent-fix')
        with self.assertRaisesRegex(RuntimeError, 'runtime_changed_since_baseline'):
            release.verify_base(self.root, {'app.py': self.changes['app.py']['before']}, self.changes)
        self.assertEqual((self.root / 'app.py').read_bytes(), b'concurrent-fix')

    def test_unreviewed_module_set_is_rejected(self):
        bundle = {'schema': 1, 'base_commit': release.BASE, 'host': 'LAPTOP-NPSGA016',
                  'source_commit': 'a' * 40, 'apk_changed': False,
                  'files': {'../app.py': self.changes['app.py']}, 'expected': {}}
        with self.assertRaisesRegex(RuntimeError, 'unreviewed_module_set'):
            release.validate(bundle)

    def test_failed_second_replacement_restores_the_first_module(self):
        original = release.replace_file
        def interrupt(path, raw, template):
            if path.name == 'schema_migrations.py':
                raise OSError('synthetic replacement interruption')
            return original(path, raw, template)
        with mock.patch.object(release, 'replace_file', side_effect=interrupt):
            with self.assertRaisesRegex(OSError, 'synthetic replacement interruption'):
                release.install(self.root, self.backup, self.changes, lambda: None)
        self.assertEqual((self.root / 'app.py').read_bytes(), b'previous-app')
        self.assertFalse((self.root / 'schema_migrations.py').exists())

    def test_tampered_source_bytes_are_rejected(self):
        expected = {name: release.digest(b'synthetic old') for name in release.MODULES
                    if name != 'schema_migrations.py'}
        expected['requirements.txt'] = release.digest(b'synthetic requirements')
        expected['app.py'] = release.digest(b'synthetic app')
        expected.update({f'module_{index}.py': release.digest(b'synthetic baseline') for index in range(50)})
        files = {name: {'before': expected.get(name), 'after': release.digest(b'synthetic new'),
                        'content': 'synthetic new'} for name in release.MODULES}
        bundle = {'schema': 1, 'base_commit': release.BASE, 'host': 'LAPTOP-NPSGA016',
                  'source_commit': 'a' * 40, 'apk_changed': False, 'expected': expected, 'files': files}
        release.validate(bundle)
        files[sorted(release.MODULES)[0]]['content'] = 'unverified replacement'
        with self.assertRaisesRegex(RuntimeError, 'invalid_module_identity'):
            release.validate(bundle)


class PdfDependencyTests(unittest.TestCase):
    def dependency(self, names=None):
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w') as archive:
            for name in names or ['pypdf/__init__.py', 'pypdf-6.21.3.dist-info/METADATA']:
                archive.writestr(name, 'synthetic dependency')
        raw = output.getvalue()
        digest = hashlib.sha256(raw).hexdigest()
        return {'name': 'pypdf-6.21.3-py3-none-any.whl', 'version': '6.21.3',
                'sha256': digest, 'content_base64': base64.b64encode(raw).decode()}, digest

    def test_reviewed_wheel_path_and_byte_inventory(self):
        dependency, digest = self.dependency()
        with mock.patch.object(release, 'WHEEL_SHA', digest):
            entries = release.dependency_entries(dependency)
        self.assertEqual(set(entries), {'pypdf/__init__.py', 'pypdf-6.21.3.dist-info/METADATA'})

    def test_tampered_dependency_rejected(self):
        dependency, digest = self.dependency()
        dependency['content_base64'] = base64.b64encode(b'changed').decode()
        with mock.patch.object(release, 'WHEEL_SHA', digest):
            with self.assertRaisesRegex(RuntimeError, 'pdf_dependency_digest_changed'):
                release.dependency_entries(dependency)

    def test_parent_path_cannot_escape_vendor_directory(self):
        dependency, digest = self.dependency(['pypdf/../../outside.py'])
        with mock.patch.object(release, 'WHEEL_SHA', digest):
            with self.assertRaisesRegex(RuntimeError, 'pdf_dependency_path_invalid'):
                release.dependency_entries(dependency)

    def test_install_preserves_existing_vendor_and_installs_only_reviewed_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / 'app.py').write_text('synthetic runtime')
            vendor = release.install_dependency(root, {'pypdf/__init__.py': b'verified bytes'})
            self.assertEqual((vendor / 'pypdf/__init__.py').read_bytes(), b'verified bytes')
            with self.assertRaisesRegex(RuntimeError, 'pdf_dependency_already_present'):
                release.install_dependency(root, {'pypdf/__init__.py': b'other bytes'})
            self.assertEqual((vendor / 'pypdf/__init__.py').read_bytes(), b'verified bytes')


class DeployedDependencyAndRetryTests(unittest.TestCase):
    def test_existing_dependency_is_verified_without_replacing_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / 'app.py').write_text('synthetic runtime')
            entries = {'pypdf/__init__.py': b'reviewed dependency'}
            vendor = release.install_dependency(root, entries)
            release.verify_dependency(root, entries)
            (vendor / 'pypdf/__init__.py').write_bytes(b'unreviewed change')
            with self.assertRaisesRegex(RuntimeError, 'pdf_dependency_installed_bytes_changed'):
                release.verify_dependency(root, entries)

    def test_retry_preserves_provider_backoff_and_active_worker_leases(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'fixture.db'
            now = int(time.time())
            with sqlite3.connect(database) as db:
                db.execute('CREATE TABLE osint_targets_v1(id INTEGER PRIMARY KEY,next_at INTEGER,lease_until INTEGER,error TEXT)')
                db.executemany('INSERT INTO osint_targets_v1 VALUES(?,?,?,?)', [
                    (1, now + 3600, 0, 'osint_response_too_large'),
                    (2, now + 3600, 0, 'osint_http_429'),
                    (3, now + 3600, now + 600, 'osint_source_unavailable')])
            self.assertEqual(release.retry_collection_failures(database), 1)
            with sqlite3.connect(database) as db:
                rows = db.execute('SELECT next_at FROM osint_targets_v1 ORDER BY id').fetchall()
            self.assertLess(rows[0][0], now + 3600)
            self.assertEqual(rows[1][0], now + 3600)
            self.assertEqual(rows[2][0], now + 3600)


if __name__ == '__main__':
    unittest.main()
