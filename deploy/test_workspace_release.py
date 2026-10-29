"""Temporary-file deployment regressions; no services, credentials or live data."""
import base64
from contextlib import closing
import hashlib
import io
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
import zipfile
from unittest import mock

spec = importlib.util.spec_from_file_location('release', Path(__file__).with_name('workspace_release.py'))
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


class ServiceRollbackTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        folder = Path(temporary.name).resolve()
        self.root, self.backup = folder / 'runtime', folder / 'backup'
        self.root.mkdir(); self.backup.mkdir()
        (self.root / 'app.py').write_bytes(b'old-code')
        self.database = folder / 'owner.sqlite3'
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute('CREATE TABLE owner_password_credentials (singleton INTEGER)')
        self.changes = {'app.py': {'before': release.digest(b'old-code'),
                                  'after': release.digest(b'candidate-code'),
                                  'content': 'candidate-code'}}
        self.events = []
        self.active = False
        self.start_fails = True
        self.stop_fails = False
        self.lingering_pid = False

    def control(self, operation, *arguments):
        self.events.append((operation, *arguments))
        if operation == 'start':
            self.active = True  # Owner started before the second service failed.
            if self.start_fails:
                raise RuntimeError('partial_start_failed')
            return ''
        if operation == 'stop':
            if self.stop_fails:
                raise RuntimeError('stop_failed')
            self.active = False
            return ''
        if operation == 'show':
            if '--property=ActiveState' in arguments:
                return 'active' if self.active else 'inactive'
            if '--property=MainPID' in arguments:
                return '123' if self.active or self.lingering_pid else '0'
            if '--property=ControlPID' in arguments:
                return '0'
        raise AssertionError('unexpected synthetic service operation')

    def activate(self):
        with release.activated_services():
            pass

    def test_partial_start_stops_both_services_before_reading_auth_and_restoring_code(self):
        before = self.database.read_bytes()
        original = release.protect_auth_rollback
        def auth_guard(database):
            self.assertFalse(self.active)
            self.assertIn(('stop', *release.SERVICES), self.events)
            self.events.append(('auth_check',))
            original(database)
        with mock.patch.object(release, 'systemctl', side_effect=self.control):
            with mock.patch.object(release, 'protect_auth_rollback', side_effect=auth_guard):
                with self.assertRaisesRegex(RuntimeError, 'partial_start_failed'):
                    release.install(self.root, self.backup, self.changes, self.activate,
                                    before_rollback=lambda: release.protect_rollback(self.database))
        self.assertEqual((self.root / 'app.py').read_bytes(), b'old-code')
        self.assertEqual(self.database.read_bytes(), before)
        self.assertEqual(self.events[-1], ('auth_check',))

    def test_failed_stop_blocks_rollback_even_with_empty_credentials(self):
        self.stop_fails = True
        with mock.patch.object(release, 'systemctl', side_effect=self.control):
            with mock.patch.object(release, 'protect_auth_rollback') as auth_guard:
                with self.assertRaisesRegex(release.ServiceRollbackBlocked, 'rollback_requires_service_quiescence'):
                    release.install(self.root, self.backup, self.changes, self.activate,
                                    before_rollback=lambda: release.protect_rollback(self.database))
                auth_guard.assert_not_called()
        self.assertTrue(self.active)
        self.assertEqual((self.root / 'app.py').read_bytes(), b'candidate-code')
        self.assertEqual((self.backup / 'app.py').read_bytes(), b'old-code')

    def test_successful_stop_command_with_lingering_process_also_blocks_rollback(self):
        self.lingering_pid = True
        with mock.patch.object(release, 'systemctl', side_effect=self.control):
            with mock.patch.object(release, 'protect_auth_rollback') as auth_guard:
                with self.assertRaisesRegex(release.ServiceRollbackBlocked, 'rollback_requires_service_quiescence'):
                    release.install(self.root, self.backup, self.changes, self.activate,
                                    before_rollback=lambda: release.protect_rollback(self.database))
                auth_guard.assert_not_called()
        self.assertEqual((self.root / 'app.py').read_bytes(), b'candidate-code')

    def test_healthy_activation_does_not_stop_services_or_check_rollback(self):
        self.start_fails = False
        with mock.patch.object(release, 'systemctl', side_effect=self.control):
            with mock.patch.object(release, 'protect_rollback') as guard:
                release.install(self.root, self.backup, self.changes, self.activate,
                                before_rollback=lambda: release.protect_rollback(self.database))
                guard.assert_not_called()
        self.assertEqual(self.events, [('start', *release.SERVICES)])
        self.assertTrue(self.active)
        self.assertEqual((self.root / 'app.py').read_bytes(), b'candidate-code')


class OwnerPasswordReleaseTests(unittest.TestCase):
    def test_release_is_bound_to_deployed_baseline_and_reviewed_modules(self):
        self.assertEqual(release.BASE, 'b69169abb4e750985ba79bf4c08f8f0f1a2ef596')
        self.assertEqual(release.MODULES, {
            'investment_chat_policy.py', 'osint_api.py', 'osint_read.py',
            'osint_retention.py', 'osint_store.py', 'osint_worker.py',
            'volume_chat.py', 'volume_explanations.py',
        })

    def status(self, **changes):
        value = {'configured': False, 'method': 'password',
                 'setup_requires': 'existing_owner_session_or_bootstrap',
                 'min_password_length': 10, 'max_password_bytes': 128}
        value.update(changes)
        return 200, json.dumps(value).encode(), {'Cache-Control': 'no-store, private',
                                                'X-Content-Type-Options': 'nosniff'}

    def test_health_reads_status_and_method_contract_without_login_or_enrollment(self):
        responses = [self.status(), (405, b''), (405, b''), (405, b'')]
        with mock.patch.object(release, 'request', side_effect=responses) as request:
            self.assertFalse(release.owner_password_health())
        self.assertEqual(request.call_args_list, [
            mock.call('/auth/owner/status', include_headers=True),
            mock.call('/auth/owner/setup'), mock.call('/auth/owner/login'),
            mock.call('/auth/owner/password')])

    def test_status_does_not_accept_unsafe_or_malformed_auth_contract(self):
        for changes in ({'configured': 'false'}, {'min_password_length': 4},
                        {'setup_requires': 'first_visitor'}, {'method': 'telegram'}):
            with self.subTest(changes=changes):
                with mock.patch.object(release, 'request', return_value=self.status(**changes)):
                    with self.assertRaisesRegex(RuntimeError, 'owner_password_contract_changed'):
                        release.owner_password_health()

    def test_status_requires_private_headers_and_existing_write_routes(self):
        status, raw, _ = self.status()
        with mock.patch.object(release, 'request', return_value=(status, raw, {})):
            with self.assertRaisesRegex(RuntimeError, 'owner_password_privacy_headers_missing'):
                release.owner_password_health()
        with mock.patch.object(release, 'request', side_effect=[self.status(), (404, b'')]):
            with self.assertRaisesRegex(RuntimeError, 'owner_password_write_route_missing'):
                release.owner_password_health()

    def test_owner_binding_compares_identity_without_modifying_data(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory).resolve() / 'owner.sqlite3'
            with closing(sqlite3.connect(database)) as db, db:
                db.execute('CREATE TABLE installation_owner (singleton INTEGER, telegram_sub TEXT, policy_version TEXT)')
                db.execute('CREATE TABLE users (id INTEGER, telegram_sub TEXT)')
                db.execute("INSERT INTO installation_owner VALUES (1,'synthetic-owner','policy')")
                db.execute("INSERT INTO users VALUES (7,'synthetic-owner')")
            before = database.read_bytes()
            identity = release.owner_binding(database)
            self.assertEqual(database.read_bytes(), before)
            self.assertRegex(identity, '^[a-f0-9]{64}$')
            with closing(sqlite3.connect(database)) as db, db:
                db.execute("UPDATE users SET telegram_sub='changed-owner'")
            self.assertNotEqual(release.owner_binding(database), identity)

    def test_no_credentials_allows_code_rollback_without_schema_removal(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory).resolve() / 'owner.sqlite3'
            with closing(sqlite3.connect(database)) as db, db:
                db.execute('CREATE TABLE unrelated (id INTEGER)')
            release.protect_auth_rollback(database)
            with closing(sqlite3.connect(database)) as db, db:
                db.execute('CREATE TABLE owner_password_credentials (singleton INTEGER)')
            before = database.read_bytes()
            release.protect_auth_rollback(database)
            self.assertEqual(database.read_bytes(), before)

    def test_unknown_database_state_blocks_downgrade(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory).resolve() / 'missing.sqlite3'
            with self.assertRaisesRegex(release.AuthRollbackBlocked, 'rollback_requires_auth_compatible_recovery'):
                release.protect_auth_rollback(database)
            self.assertFalse(database.exists())

    def test_empty_password_registry_allows_source_only_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory).resolve()
            root, backup = folder / 'runtime', folder / 'backup'
            root.mkdir(); backup.mkdir()
            (root / 'app.py').write_bytes(b'old-login-code')
            database = folder / 'owner.sqlite3'
            with closing(sqlite3.connect(database)) as db, db:
                db.execute('CREATE TABLE owner_password_credentials (singleton INTEGER)')
            before = database.read_bytes()
            changes = {'app.py': {'before': release.digest(b'old-login-code'),
                                  'after': release.digest(b'password-login-code'),
                                  'content': 'password-login-code'}}
            def reject():
                raise RuntimeError('synthetic activation failure')
            with self.assertRaisesRegex(RuntimeError, 'synthetic activation failure'):
                release.install(root, backup, changes, reject,
                                before_rollback=lambda: release.protect_auth_rollback(database))
            self.assertEqual((root / 'app.py').read_bytes(), b'old-login-code')
            self.assertEqual(database.read_bytes(), before)

    def test_concurrent_enrollment_preserves_new_code_and_credentials_on_activation_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory).resolve()
            root, backup = folder / 'runtime', folder / 'backup'
            root.mkdir(); backup.mkdir()
            (root / 'app.py').write_bytes(b'old-login-code')
            database = folder / 'owner.sqlite3'
            with closing(sqlite3.connect(database)) as db, db:
                db.execute('CREATE TABLE owner_password_credentials (singleton INTEGER)')
            changes = {'app.py': {'before': release.digest(b'old-login-code'),
                                  'after': release.digest(b'password-login-code'),
                                  'content': 'password-login-code'}}
            def fail_after_enrollment():
                with closing(sqlite3.connect(database)) as db, db:
                    db.execute('INSERT INTO owner_password_credentials VALUES (1)')
                raise RuntimeError('synthetic activation failure')
            with mock.patch.object(release, 'systemctl') as service:
                with self.assertRaisesRegex(release.AuthRollbackBlocked, 'rollback_requires_auth_compatible_recovery'):
                    release.install(root, backup, changes, fail_after_enrollment,
                                    before_rollback=lambda: release.protect_auth_rollback(database))
                service.assert_not_called()
            self.assertEqual((root / 'app.py').read_bytes(), b'password-login-code')
            self.assertEqual((backup / 'app.py').read_bytes(), b'old-login-code')
            with closing(sqlite3.connect(database)) as db, db:
                self.assertEqual(db.execute('SELECT singleton FROM owner_password_credentials').fetchall(), [(1,)])



if __name__ == '__main__':
    unittest.main()

