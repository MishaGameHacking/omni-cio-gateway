"""Temporary-file deployment regressions; no services, credentials or live data."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location('release', Path(__file__).with_name('server_runtime_release.py'))
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
        files['volume_live.py']['content'] = 'unverified replacement'
        with self.assertRaisesRegex(RuntimeError, 'invalid_module_identity'):
            release.validate(bundle)


if __name__ == '__main__':
    unittest.main()
