"""Synthetic bounded service-recovery tests; run only in the owner's WSL."""
from contextlib import closing, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location('runtime_recovery', Path(__file__).with_name('runtime_recovery.py'))
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.parent = Path(temp.name).resolve()
        self.root = self.parent / 'backend'; self.root.mkdir()
        self.units = self.parent / 'units'; self.units.mkdir()
        self.database = self.parent / 'backend.db'
        self.config = self.parent / 'backend.env'
        self.config.write_text('SYNTHETIC_SECRET=private-canary\n')
        blobs = {}
        for name in recovery.BASELINE_BLOBS:
            raw = ('baseline ' + name).encode()
            (self.root / name).write_bytes(raw)
            blobs[name] = recovery.git_blob(raw)
        for service in recovery.SERVICES:
            (self.units / service).write_text('synthetic existing service')
        with closing(sqlite3.connect(self.database)) as db:
            db.executescript("""CREATE TABLE installation_owner(singleton,telegram_sub,policy_version);
                INSERT INTO installation_owner VALUES(1,'private-owner','policy');
                CREATE TABLE users(id,telegram_sub,tinvest_token_encrypted);
                INSERT INTO users VALUES(1,'private-owner',X'112233');
                CREATE TABLE owner_password_credentials(user_id,salt,password_hash);
                INSERT INTO owner_password_credentials VALUES(1,X'4455',X'6677');
                CREATE TABLE facts(value);INSERT INTO facts VALUES('preserved');""")
            db.execute('PRAGMA journal_mode=WAL')
        for name, value in {'ROOT': self.root, 'UNIT_ROOT': self.units, 'DATABASE': self.database,
                            'CONFIGURATION': self.config, 'ARCHIVES': self.parent,
                            'LOCK': self.parent / 'recovery.lock', 'BASELINE_BLOBS': blobs}.items():
            patcher = mock.patch.object(recovery, name, value)
            patcher.start(); self.addCleanup(patcher.stop)
        self.patch('os.getuid', return_value=0)
        self.patch('validate_archive_parent')
        self.state = 'active'; self.generation = 0; self.calls = []
        self.patch('ctl', side_effect=self.ctl)
        self.patch('probe', side_effect=lambda name: {'endpoint': name, 'ok': self.generation > 0})
        self.envelope = {'payload': {'source_commit': recovery.BASE}, 'run_id': '41000000001'}
        self.output = io.StringIO()

    def patch(self, name, **arguments):
        target, _, attribute = name.rpartition('.')
        owner = getattr(recovery, target) if target else recovery
        patcher = mock.patch.object(owner, attribute or name, **arguments)
        value = patcher.start(); self.addCleanup(patcher.stop)
        return value

    def ctl(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if args[0] == 'stop':
            self.state = 'inactive'; return ''
        if args[0] == 'start':
            self.state = 'active'; self.generation += 1; return ''
        service = args[1]
        if '--property=TimeoutStopUSec' in args: return '45s'
        if '--property=FragmentPath' in args: return str(self.units / service)
        if '--property=ActiveState' in args: return self.state
        if '--property=ControlPID' in args: return '0'
        if '--property=MainPID' in args:
            return str((100 + self.generation * 10 + recovery.SERVICES.index(service)) if self.state == 'active' else 0)
        raise AssertionError(args)

    def run_recovery(self):
        with redirect_stdout(self.output):
            return recovery.recover(self.envelope)

    def test_restart_preserves_source_config_inode_credentials_and_wal(self):
        before = recovery.database_identity()
        result = self.run_recovery()
        self.assertEqual(result['status'], 'recovered')
        self.assertEqual(recovery.database_identity(), before)
        recovery.baseline()
        self.assertEqual(self.config.read_text(), 'SYNTHETIC_SECRET=private-canary\n')
        backup = self.parent / 'analyst-ai-runtime-recovery-41000000001/before.sqlite3'
        with closing(sqlite3.connect(backup)) as db:
            self.assertEqual(db.execute('SELECT value FROM facts').fetchone()[0], 'preserved')
        self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
        mutations = [call for call in self.calls if call[0][0] in {'start', 'stop'}]
        self.assertEqual(mutations, [(('stop', *recovery.SERVICES), {'timeout': 180}),
                                    (('start', *recovery.SERVICES), {'timeout': 60})])
        self.assertNotIn('private-', self.output.getvalue())
        self.assertNotIn(before[-1], self.output.getvalue())

    def test_changed_source_prevents_any_service_mutation(self):
        (self.root / 'portfolio_details.py').write_text('changed')
        with self.assertRaisesRegex(RuntimeError, 'recovery_source_baseline_changed'):
            self.run_recovery()
        self.assertFalse(any(call[0][0] in {'start', 'stop'} for call in self.calls))

    def test_candidate_module_prevents_restarting_wrong_release(self):
        (self.root / 'order_lifecycle.py').write_text('candidate')
        with self.assertRaisesRegex(RuntimeError, 'recovery_candidate_already_installed'):
            self.run_recovery()
        self.assertEqual(self.calls, [])

    def test_stop_failure_never_restores_database_and_requests_start_under_lock(self):
        original = self.ctl
        def failing(*args, **kwargs):
            if args[0] == 'stop':
                self.calls.append((args, kwargs))
                raise subprocess.TimeoutExpired('synthetic private-command', 180)
            if args[0] == 'start':
                import fcntl
                with recovery.LOCK.open('a') as competing:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(competing, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return original(*args, **kwargs)
        self.patch('ctl', side_effect=failing)
        before = recovery.database_identity()
        with self.assertRaises(subprocess.TimeoutExpired): self.run_recovery()
        self.assertEqual(recovery.database_identity(), before)
        self.assertIn('"recovery_start_requested": true', self.output.getvalue())
        self.assertNotIn('private-command', self.output.getvalue())
        self.assertFalse((self.parent / 'analyst-ai-runtime-recovery-41000000001/before.sqlite3').exists())

    def test_start_failure_retries_existing_services_without_code_or_db_restore(self):
        original = self.ctl
        starts = []
        def failing(*args, **kwargs):
            if args[0] == 'start':
                starts.append(args)
                if len(starts) == 1: raise RuntimeError('private failure')
            return original(*args, **kwargs)
        self.patch('ctl', side_effect=failing)
        before = recovery.database_identity()
        with self.assertRaises(RuntimeError): self.run_recovery()
        self.assertEqual(len(starts), 2)
        self.assertEqual(self.state, 'active')
        self.assertEqual(recovery.database_identity(), before)
        recovery.baseline()

    def test_binding_change_blocks_compensating_start(self):
        original = self.ctl
        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            if args[0] == 'stop': self.config.write_text('changed configuration')
            return result
        self.patch('ctl', side_effect=changed)
        with self.assertRaisesRegex(RuntimeError, 'recovery_configuration_changed'): self.run_recovery()
        self.assertFalse(any(call[0][0] == 'start' for call in self.calls))
        self.assertIn('"recovery_start_requested": false', self.output.getvalue())

    def test_existing_archive_not_overwritten(self):
        archive = self.parent / 'analyst-ai-runtime-recovery-41000000001'
        archive.mkdir(); (archive / 'failure.json').write_text('preserve prior evidence')
        with self.assertRaises(FileExistsError): self.run_recovery()
        self.assertEqual((archive / 'failure.json').read_text(), 'preserve prior evidence')
        self.assertFalse(any(call[0][0] in {'start', 'stop'} for call in self.calls))

    def test_local_healthy_does_not_restart_for_public_network_failure(self):
        self.patch('probe', side_effect=lambda name: {'endpoint': name, 'ok': name == 'local_health'})
        result = self.run_recovery()
        self.assertEqual(result['status'], 'restart_not_needed')
        self.assertFalse(any(call[0][0] in {'start', 'stop'} for call in self.calls))

    def test_public_healthy_cannot_mask_local_failure_after_restart(self):
        self.patch('probe', side_effect=lambda name: {'endpoint': name, 'ok': name != 'local_health'})
        sleep = self.patch('time.sleep')
        with self.assertRaisesRegex(RuntimeError, 'recovery_health_not_restored'): self.run_recovery()
        self.assertEqual(sleep.call_count, 3)
        self.assertIn('"phase": "health"', self.output.getvalue())

    def test_unbounded_stop_timeout_rejected_before_mutation(self):
        original = self.ctl
        def show(*args, **kwargs):
            return 'infinity' if '--property=TimeoutStopUSec' in args else original(*args, **kwargs)
        self.patch('ctl', side_effect=show)
        with self.assertRaisesRegex(RuntimeError, 'recovery_service_stop_timeout_unbounded'): self.run_recovery()
        self.assertFalse(any(call[0][0] in {'start', 'stop'} for call in self.calls))

    def test_still_running_service_blocks_backup(self):
        self.patch('stopped', side_effect=RuntimeError('recovery_services_not_stopped'))
        backup = self.patch('backup')
        with self.assertRaisesRegex(RuntimeError, 'recovery_services_not_stopped'): self.run_recovery()
        backup.assert_not_called()

    def test_password_or_broker_binding_change_detected(self):
        before = recovery.database_identity()
        with sqlite3.connect(self.database) as db:
            db.execute("UPDATE owner_password_credentials SET password_hash=X'9999'")
        self.assertNotEqual(recovery.database_identity(), before)

    def test_existing_backup_never_replaced(self):
        target = self.parent / 'keep.sqlite3'; target.write_bytes(b'original')
        with self.assertRaisesRegex(RuntimeError, 'recovery_backup_already_exists'): recovery.backup(target)
        self.assertEqual(target.read_bytes(), b'original')

    def test_failure_projection_has_no_exception_message_source_locals_or_path(self):
        namespace = {}
        exec(compile("def fail():\n    secret='private-token'\n    raise RuntimeError(secret)\n", 'owner-plan-operation', 'exec'), namespace)
        try:
            namespace['fail']()
        except RuntimeError as error:
            value = recovery.error_receipt(error, 'start')
        encoded = json.dumps(value)
        self.assertNotIn('private-token', encoded)
        self.assertEqual(value['frames'], [{'function': 'fail', 'line': 3}])
        self.assertEqual(value['phase'], 'start')


class ContractTests(unittest.TestCase):
    def test_exact_cc22_runtime_and_two_existing_services_only(self):
        self.assertEqual(recovery.BASE, 'cc22cb7ee3fe82eca28e4162e13c4463cab5ddc4')
        self.assertEqual(len(recovery.BASELINE_BLOBS), 107)
        self.assertEqual(recovery.BASELINE_BLOBS['portfolio_details.py'], '78e1c2123f7921795c02bcb14ef615eed9476c81')
        self.assertEqual(recovery.SERVICES, ('analyst-ai-owner.service', 'analyst-ai-updates.service'))
        self.assertNotIn('order_lifecycle.py', recovery.BASELINE_BLOBS)


if __name__ == '__main__':
    unittest.main()
