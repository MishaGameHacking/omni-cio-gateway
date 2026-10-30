"""Synthetic release regressions, executed only in the owner's project WSL."""
from contextlib import closing
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest import mock
import zipfile


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


ROOT = Path(__file__).resolve().parents[1]
release = module('decision_release', ROOT / 'deploy/decision_engine_release.py')
prepare = module('decision_prepare', ROOT / 'tools/prepare_decision_engine_transport.py')


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.parent = Path(temp.name).resolve()
        self.root = self.parent / 'backend'; self.root.mkdir()
        self.backup = self.parent / 'old'; self.backup.mkdir()
        self.expected = {}; blobs = {}
        for name in release.BASELINE_BLOBS:
            raw = ('synthetic baseline ' + name).encode()
            (self.root / name).write_bytes(raw)
            self.expected[name] = release.digest(raw); blobs[name] = release.git_blob(raw)
        patcher = mock.patch.object(release, 'BASELINE_BLOBS', blobs)
        patcher.start(); self.addCleanup(patcher.stop)
        self.files = {name: {'before': self.expected.get(name), 'content': 'synthetic candidate ' + name,
            'after': release.digest(('synthetic candidate ' + name).encode())} for name in release.MODULES}
        self.bundle = {'schema': 1, 'base_commit': release.BASE, 'source_commit': 'a' * 40,
            'host': 'LAPTOP-NPSGA016', 'apk_changed': False, 'run_id': '41000000000',
            'run_attempt': '1', 'expected': self.expected, 'files': self.files}
        self.database = self.parent / 'test.sqlite3'
        with closing(sqlite3.connect(self.database)) as db:
            db.executescript("""CREATE TABLE installation_owner(singleton,telegram_sub,policy_version);
                INSERT INTO installation_owner VALUES(1,'fixture-owner','fixture-policy');
                CREATE TABLE users(id,telegram_sub); INSERT INTO users VALUES(1,'fixture-owner');
                CREATE TABLE owner_password_credentials(user_id,password_hash);
                INSERT INTO owner_password_credentials VALUES(1,'synthetic-hash');
                CREATE TABLE preserved(value);INSERT INTO preserved VALUES('original');""")
            db.execute('PRAGMA journal_mode=WAL')
        self.config = self.parent / 'backend.env'; self.config.write_text('SYNTHETIC=true\n')
        patcher = mock.patch.object(release, 'CONFIGURATION', self.config)
        patcher.start(); self.addCleanup(patcher.stop)
        self.config_hash = release.digest(self.config.read_bytes())
        self.binding = release.owner_binding(self.database)

    def guard(self):
        release.protect_compatible_rollback(self.root, self.database, self.expected,
                                            self.config_hash, self.binding)

    def test_exact_manifest_and_file_baseline_accepted(self):
        release.validate(self.bundle)
        release.verify_base(self.root, self.expected, self.files)

    def test_manifest_rejects_old_base_extra_module_apk_or_rerun(self):
        cases = [('base_commit', 'b' * 40), ('apk_changed', True), ('run_attempt', '2'),
                 ('files', {**self.files, 'owner_password.py': self.files['volume_live.py']})]
        for key, value in cases:
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                release.validate({**self.bundle, key: value})

    def test_baseline_names_and_payload_bytes_cannot_be_substituted(self):
        with self.assertRaisesRegex(RuntimeError, 'incomplete_runtime_baseline'):
            release.validate({**self.bundle, 'expected': {'app.py': self.expected['app.py']}})
        self.files['volume_live.py']['content'] += 'changed'
        with self.assertRaisesRegex(RuntimeError, 'invalid_module_identity'):
            release.validate(self.bundle)

    def test_payload_hash_cannot_authorize_different_runtime_baseline(self):
        raw = b'unauthorized app'
        (self.root / 'app.py').write_bytes(raw)
        self.expected['app.py'] = release.digest(raw)
        with self.assertRaisesRegex(RuntimeError, 'runtime_changed_since_baseline'):
            release.verify_base(self.root, self.expected, self.files)

    def test_new_module_must_not_already_exist(self):
        (self.root / 'decision_cycle.py').write_text('other work')
        with self.assertRaisesRegex(RuntimeError, 'new_module_already_exists'):
            release.verify_base(self.root, self.expected, self.files)

    def test_symlink_baseline_rejected(self):
        app = self.root / 'app.py'; app.unlink(); app.symlink_to(self.config)
        with self.assertRaisesRegex(RuntimeError, 'unsafe_runtime_file'):
            release.verify_base(self.root, self.expected, self.files)

    def test_success_keeps_old_source_backup(self):
        release.install(self.root, self.backup, self.files, lambda: None)
        self.assertEqual((self.root / 'decision_cycle.py').read_text(), self.files['decision_cycle.py']['content'])
        self.assertEqual(release.digest((self.backup / 'volume_live.py').read_bytes()), self.expected['volume_live.py'])

    def test_configured_password_allows_verified_compatible_source_rollback(self):
        def failed_activation():
            with sqlite3.connect(self.database) as db:
                db.execute("INSERT INTO preserved VALUES('new committed fact')")
            raise RuntimeError('synthetic activation failure')
        with mock.patch.object(release, 'require_stopped_services') as stopped:
            with self.assertRaisesRegex(RuntimeError, 'synthetic activation failure'):
                release.install(self.root, self.backup, self.files, failed_activation, self.guard)
            stopped.assert_called_once()
        self.assertFalse((self.root / 'decision_cycle.py').exists())
        self.assertEqual(release.digest((self.root / 'volume_live.py').read_bytes()), self.expected['volume_live.py'])
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute('SELECT value FROM preserved').fetchall(), [('original',), ('new committed fact',)])
            self.assertEqual(db.execute('SELECT password_hash FROM owner_password_credentials').fetchone()[0], 'synthetic-hash')
            self.assertEqual(db.execute('PRAGMA journal_mode').fetchone()[0], 'wal')

    def test_changed_auth_code_blocks_rollback(self):
        def failed_activation():
            (self.root / 'owner_password.py').write_text('unexpected auth change')
            raise RuntimeError('failure')
        with mock.patch.object(release, 'require_stopped_services'):
            with self.assertRaises(release.CompatibleRollbackBlocked):
                release.install(self.root, self.backup, self.files, failed_activation, self.guard)
        self.assertTrue((self.root / 'decision_cycle.py').exists())

    def test_changed_owner_or_configuration_blocks_rollback(self):
        with mock.patch.object(release, 'require_stopped_services'):
            self.config.write_text('changed')
            with self.assertRaises(release.CompatibleRollbackBlocked): self.guard()
            self.config.write_text('SYNTHETIC=true\n')
            with sqlite3.connect(self.database) as db:
                db.execute("UPDATE installation_owner SET telegram_sub='different'")
            with self.assertRaises(release.CompatibleRollbackBlocked): self.guard()

    def test_live_process_blocks_rollback(self):
        with mock.patch.object(release, 'require_stopped_services', side_effect=release.ServiceRollbackBlocked):
            with self.assertRaises(release.ServiceRollbackBlocked): self.guard()

    def test_wal_backup_includes_committed_uncheckpointed_rows(self):
        target = self.parent / 'saved.sqlite3'
        with closing(sqlite3.connect(self.database)) as writer:
            writer.execute('PRAGMA wal_autocheckpoint=0')
            writer.execute("INSERT INTO preserved VALUES('WAL committed')"); writer.commit()
            self.assertGreater(Path(str(self.database) + '-wal').stat().st_size, 0)
            release.backup_database(self.database, target)
        with closing(sqlite3.connect(target)) as saved:
            self.assertIn(('WAL committed',), saved.execute('SELECT value FROM preserved').fetchall())
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)

    def test_backup_never_overwrites_existing_file(self):
        target = self.parent / 'saved.sqlite3'; target.write_bytes(b'keep')
        with self.assertRaisesRegex(RuntimeError, 'backup_already_exists'):
            release.backup_database(self.database, target)
        self.assertEqual(target.read_bytes(), b'keep')

    def test_lingering_service_pid_rejected(self):
        with mock.patch.object(release, 'systemctl', side_effect=['inactive', '9', '0']):
            with self.assertRaises(release.ServiceRollbackBlocked): release.require_stopped_services()

    def test_decision_schema_status_rejects_absent_table_without_creating_it(self):
        with self.assertRaisesRegex(RuntimeError, 'decision_journal_schema_missing'):
            release.decision_schema_status(self.database)
        with closing(sqlite3.connect(self.database)) as db:
            self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='portfolio_decision_cycles'").fetchone())

    def test_decision_schema_status_requires_index_on_exact_table(self):
        with sqlite3.connect(self.database) as db:
            db.execute('CREATE TABLE portfolio_decision_cycles(user_id,broker_key,evaluated_at,payload_json)')
            db.execute('CREATE INDEX portfolio_decision_cycles_latest ON preserved(value)')
        with self.assertRaisesRegex(RuntimeError, 'decision_journal_schema_missing'):
            release.decision_schema_status(self.database)

    def test_decision_schema_status_returns_only_readiness_and_row_count(self):
        with sqlite3.connect(self.database) as db:
            db.execute('CREATE TABLE portfolio_decision_cycles(user_id,broker_key,evaluated_at,payload_json)')
            db.execute('CREATE INDEX portfolio_decision_cycles_latest ON portfolio_decision_cycles(user_id,broker_key,evaluated_at DESC)')
            db.executemany('INSERT INTO portfolio_decision_cycles VALUES(?,?,?,?)',
                           [(1, 'synthetic-private-key', 1, 'private-payload'),
                            (1, 'synthetic-private-key', 2, 'private-payload')])
        self.assertEqual(release.decision_schema_status(self.database),
                         {'decision_journal_ready': True, 'decision_journal_rows': 2})
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM portfolio_decision_cycles').fetchone()[0], 2)


class ContractTests(unittest.TestCase):
    def test_pinned_baseline_and_module_allowlist(self):
        self.assertEqual(release.BASE, 'a9574656fcac4507660c872ebcc22641154a3c8a')
        self.assertEqual(release.MODULES, {'autonomous_controller.py', 'decision_cycle.py',
            'decision_views.py', 'strategy_actions.py', 'purchase_policy.py', 'volume_live.py',
            'margin_policy.py', 'volume_chat.py'})
        self.assertEqual(release.MODULES, prepare.MODULES)
        self.assertEqual(len(release.BASELINE_BLOBS), 105)
        self.assertNotIn('decision_cycle.py', release.BASELINE_BLOBS)
        self.assertNotIn('margin_policy.py', release.BASELINE_BLOBS)
        for name in ('app.py', 'owner_password.py', 'requirements.txt', 'schema_migrations.py'):
            self.assertIn(name, release.BASELINE_BLOBS); self.assertNotIn(name, release.MODULES)


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'artifact.zip'
        self.report = {'host': 'LAPTOP-NPSGA016', 'status': 'passed', 'tested_merge_sha': 'a' * 40,
            'linux': {'status': 'passed', 'changed_sources': []}, 'complete_source_sha256': 'c' * 64}

    def archive(self, *, duplicate=False, **overrides):
        report = json.dumps(self.report).encode()
        bundle = {'schema': 1, 'base_commit': prepare.BASE, 'apk_changed': False,
            'files': {name: {} for name in prepare.MODULES}, 'host': 'LAPTOP-NPSGA016',
            'source_commit': 'a' * 40, 'run_id': '41000000000', 'run_attempt': '1',
            'source_sha256': 'c' * 64, 'verification_sha256': prepare.sha(report), **overrides}
        raw = json.dumps(bundle).encode()
        with zipfile.ZipFile(self.path, 'w') as output:
            output.writestr('server-runtime.json', raw)
            output.writestr('windows-backend-report.json', report)
            if duplicate: output.writestr('nested/server-runtime.json', raw)
        return dict(archive_sha=prepare.sha(self.path.read_bytes()), bundle_sha=prepare.sha(raw),
                    source_sha='a' * 40, run_id='41000000000')

    def test_exact_artifact_is_bound_to_verified_source(self):
        self.assertTrue(prepare.verify_artifact(self.path, **self.archive()))

    def test_unset_identity_rejected_before_artifact_use(self):
        options = self.archive(); options['source_sha'] = 'UNSET_SOURCE_SHA'
        with self.assertRaisesRegex(RuntimeError, 'source_identity_unset'):
            prepare.verify_artifact(self.path, **options)

    def test_duplicate_bundle_rejected(self):
        options = self.archive(duplicate=True)
        with self.assertRaisesRegex(RuntimeError, 'ambiguous_artifact'):
            prepare.verify_artifact(self.path, **options)

    def test_artifact_tampering_rejected(self):
        options = self.archive(); self.path.write_bytes(self.path.read_bytes() + b'changed')
        with self.assertRaisesRegex(RuntimeError, 'artifact_digest_changed'):
            prepare.verify_artifact(self.path, **options)

    def test_different_tested_source_or_changed_guest_source_rejected(self):
        for field, value in [('tested_merge_sha', 'b' * 40), ('linux', {'status': 'passed', 'changed_sources': ['app.py']})]:
            with self.subTest(field=field):
                previous = self.report[field]; self.report[field] = value
                options = self.archive()
                with self.assertRaisesRegex(RuntimeError, 'exact_laptop_verification_required'):
                    prepare.verify_artifact(self.path, **options)
                self.report[field] = previous


if __name__ == '__main__':
    unittest.main()
