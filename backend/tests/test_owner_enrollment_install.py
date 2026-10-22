"""Fresh installer enrollment ordering; filesystem is real, services are mocked."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import stat
import signal
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from deploy import install_owner_backend as installer

CHECK_TARGET = installer.check_target


def bootstrap():
    return {'TELEGRAM_CLIENT_ID': '123456', 'TELEGRAM_CLIENT_SECRET': 'synthetic-secret',
            'BACKEND_PUBLIC_URL': 'https://new.example.com', 'EXPECTED_PUBLIC_IPV4': '1.1.1.1',
            'TELEGRAM_ENROLLMENT_REDIRECT_URI': 'https://new.example.com' + installer.ENROLLMENT_CALLBACK}


def confirmed():
    return {name: value for name, value in bootstrap().items() if name != 'TELEGRAM_ENROLLMENT_REDIRECT_URI'} | {
        'ANALYST_OWNER_TELEGRAM_SUB': 'opaque:Owner-A_9'}


class OwnerEnrollmentInstallationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.folder.chmod(0o700)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for name, suffix in (('INSTALL', 'app'), ('CONFIG', 'config'), ('STATE', 'state'),
                             ('UNIT', 'owner.service'), ('CADDY_DROPIN', 'dropin/analyst-ai.conf'),
                             ('INPUT_CONFIG', 'owner.json'), ('ENROLLMENT_CONFIG', 'enrollment.json')):
            self.stack.enter_context(patch.object(installer, name, self.folder / suffix))
        self.stack.enter_context(patch.object(installer, 'check_target'))
        self.stack.enter_context(patch.object(installer, 'check_address'))
        self.stack.enter_context(patch.object(installer.shutil, 'chown'))
        self.stack.enter_context(patch.object(installer, 'wait_healthy'))
        self.stack.enter_context(patch.object(installer, 'enrollment_tls_ready', return_value=True))
        self.stack.enter_context(patch.object(installer.os, 'isatty', return_value=True))
        real_fstat = os.fstat
        def metadata(descriptor):
            if descriptor == 0:
                return os.stat_result((stat.S_IFCHR | 0o600, 1, 1, 1, 0, 0, 0, 0, 0, 0))
            values = list(real_fstat(descriptor))
            values[4] = 0
            return os.stat_result(values)
        self.stack.enter_context(patch.object(installer.os, 'fstat', side_effect=metadata))
        self.commands = []
        self.result = confirmed()
        self.cancel = False
        self.cleanup = self.stack.enter_context(patch.object(installer.subprocess, 'run'))
        self.cleanup.return_value = subprocess.CompletedProcess([], 0)
        self.stack.enter_context(patch.object(installer, 'run', side_effect=self.command))

    def command(self, command, **_kwargs):
        self.commands.append(command)
        if command[-1] == str(installer.ROOT / 'deploy/enroll_owner.py'):
            self.assertFalse((installer.CONFIG / 'backend.env').exists())
            self.assertFalse(installer.UNIT.exists())
            self.assertEqual(list(installer.STATE.iterdir()), [])
            self.assertNotIn(['systemctl', 'start', 'analyst-ai-owner'], self.commands)
            text = (installer.CONFIG / 'Caddyfile').read_text()
            self.assertIn('output discard', text)
            self.assertIn('reverse_proxy 127.0.0.1:8765', text)
            self.assertNotIn('127.0.0.1:8080', text)
            if self.cancel:
                raise installer.InstallError('synthetic_enrollment_cancelled')
            installer.write_new(installer.INPUT_CONFIG, json.dumps(self.result), 0o600)

    def test_fresh_flow_opens_application_only_after_confirmation_and_preserves_private_key(self):
        previous = os.umask(0o077)
        try:
            installer.install(bootstrap(), enroll_owner=True)
        finally:
            os.umask(previous)
        enrollment_index = next(index for index, command in enumerate(self.commands)
                                if command[-1] == str(installer.ROOT / 'deploy/enroll_owner.py'))
        self.assertGreater(self.commands.index(['systemctl', 'start', 'analyst-ai-owner']), enrollment_index)
        settings = dict(line.split('=', 1) for line in (installer.CONFIG / 'backend.env').read_text().splitlines())
        self.assertEqual(json.loads(settings['ANALYST_OWNER_TELEGRAM_SUB']), 'opaque:Owner-A_9')
        from cryptography.fernet import Fernet
        Fernet(json.loads(settings['FERNET_KEY']).encode())
        self.assertEqual(stat.S_IMODE((installer.CONFIG / 'backend.env').stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(installer.INPUT_CONFIG.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE((installer.CONFIG / 'Caddyfile').stat().st_mode), 0o644)
        text = (installer.CONFIG / 'Caddyfile').read_text()
        self.assertNotIn('output discard', text)
        self.assertNotIn('127.0.0.1:8765', text)
        self.assertIn('respond 410', text)
        self.assertIn('reverse_proxy 127.0.0.1:8080', text)
        self.assertEqual(list(installer.STATE.iterdir()), [])  # No actual app/service was started in this test.
        self.cleanup.assert_not_called()

    def test_cancellation_leaves_no_owner_environment_unit_or_database_and_stops_proxy(self):
        self.cancel = True
        with self.assertRaisesRegex(installer.InstallError, 'cancelled'):
            installer.install(bootstrap(), enroll_owner=True)
        self.assertFalse(installer.INPUT_CONFIG.exists())
        self.assertFalse((installer.CONFIG / 'backend.env').exists())
        self.assertFalse(installer.UNIT.exists())
        self.assertEqual(list(installer.STATE.iterdir()), [])
        self.assertNotIn(['systemctl', 'start', 'analyst-ai-owner'], self.commands)
        self.cleanup.assert_called_once()
        self.assertEqual(self.cleanup.call_args.args[0], ['systemctl', 'disable', '--now', 'caddy'])
        self.assertIn(['systemctl', 'disable', '--now', 'caddy'], self.commands)

    def test_returned_configuration_cannot_change_origin_client_secret_or_target(self):
        installer.STATE.mkdir()
        for name, value in (('TELEGRAM_CLIENT_ID', '654321'), ('TELEGRAM_CLIENT_SECRET', 'different-secret'),
                            ('BACKEND_PUBLIC_URL', 'https://different.example.com'), ('EXPECTED_PUBLIC_IPV4', '8.8.8.8')):
            # Each call exercises the post-enrollment barrier without mutating
            # the installation a second time.
            installer.CONFIG.mkdir(exist_ok=True)
            caddy = installer.CONFIG / 'Caddyfile'
            caddy.write_text(installer.caddy_text('new.example.com', enrollment=True))
            self.result = confirmed() | {name: value}
            with self.subTest(field=name), self.assertRaisesRegex(installer.InstallError, 'does_not_match'):
                installer.complete_enrollment(bootstrap(), 'new.example.com', caddy)
            self.assertFalse((installer.CONFIG / 'backend.env').exists())
            installer.INPUT_CONFIG.unlink()

    def test_ordinary_install_still_rejects_missing_owner_without_any_command(self):
        values = confirmed()
        del values['ANALYST_OWNER_TELEGRAM_SUB']
        with self.assertRaises(installer.InstallError):
            installer.install(values)
        self.assertEqual(self.commands, [])

    def test_exact_https_redirect_is_required_and_cannot_be_a_separate_destination(self):
        for uri in ('http://new.example.com' + installer.ENROLLMENT_CALLBACK,
                    'https://other.example.com' + installer.ENROLLMENT_CALLBACK,
                    'https://new.example.com/auth/telegram/callback',
                    'https://new.example.com' + installer.ENROLLMENT_CALLBACK + '?x=1'):
            with self.subTest(uri=uri), self.assertRaisesRegex(installer.InstallError, 'exact_enrollment'):
                installer.validated_enrollment_config(bootstrap() | {'TELEGRAM_ENROLLMENT_REDIRECT_URI': uri})
        with self.assertRaises(installer.InstallError):
            installer.validated_enrollment_config(bootstrap() | {'ANALYST_OWNER_TELEGRAM_SUB': 'first-visitor'})

    def test_preexisting_owner_or_nonprivate_terminal_prevents_installation_commands(self):
        installer.INPUT_CONFIG.write_text('existing owner')
        with self.assertRaisesRegex(installer.InstallError, 'existing_owner'):
            installer.install(bootstrap(), enroll_owner=True)
        self.assertEqual(self.commands, [])
        installer.INPUT_CONFIG.unlink()
        with patch.object(installer.os, 'isatty', return_value=False):
            with self.assertRaisesRegex(installer.InstallError, 'private_interactive'):
                installer.install(bootstrap(), enroll_owner=True)
        self.assertEqual(self.commands, [])

    def test_tls_failure_never_launches_enrollment_or_backend(self):
        with patch.object(installer, 'enrollment_tls_ready', return_value=False), patch.object(installer.time, 'sleep'):
            with self.assertRaisesRegex(installer.InstallError, 'enrollment_tls_probe_failed'):
                installer.install(bootstrap(), enroll_owner=True)
        self.assertFalse(any(command[-1] == str(installer.ROOT / 'deploy/enroll_owner.py') for command in self.commands))
        self.assertFalse((installer.CONFIG / 'backend.env').exists())
        self.cleanup.assert_called_once()

    def test_package_autostart_failure_and_interrupt_are_inside_cleanup_boundary(self):
        for failure in (installer.InstallError('synthetic_package_failed'), KeyboardInterrupt()):
            def failed_package(command, **_kwargs):
                if command[:2] == ['apt-get', 'install']:
                    raise failure
            with self.subTest(failure=type(failure).__name__), patch.object(installer, 'run', side_effect=failed_package):
                with self.assertRaises(type(failure)):
                    installer.install(bootstrap(), enroll_owner=True)
            self.cleanup.assert_called_with(['systemctl', 'disable', '--now', 'caddy'],
                                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                             timeout=30, check=False)
            self.assertFalse(installer.CONFIG.exists())
            self.cleanup.reset_mock()

    def test_failed_stop_does_not_hide_original_installation_error(self):
        self.cleanup.side_effect = subprocess.TimeoutExpired('systemctl', 30)
        with patch.object(installer, 'run', side_effect=installer.InstallError('original_failure')):
            with self.assertRaisesRegex(installer.InstallError, 'original_failure'):
                installer.install(bootstrap(), enroll_owner=True)

    def test_existing_or_symlink_dropin_directory_is_refused_before_package_changes(self):
        unrelated = self.folder / 'unrelated'
        unrelated.mkdir(mode=0o700)
        for symlink in (False, True):
            if symlink:
                installer.CADDY_DROPIN.parent.symlink_to(unrelated, target_is_directory=True)
            else:
                installer.CADDY_DROPIN.parent.mkdir(mode=0o700)
            with self.subTest(symlink=symlink), patch.object(installer, 'check_target', side_effect=CHECK_TARGET), patch.object(installer.os, 'geteuid', return_value=0), patch.object(Path, 'read_text', return_value='ID=ubuntu\nVERSION_ID="24.04"\n'):
                with self.assertRaisesRegex(installer.InstallError, 'existing_installation'):
                    installer.install(bootstrap(), enroll_owner=True)
            self.assertEqual(self.commands, [])
            self.assertEqual(stat.S_IMODE(unrelated.stat().st_mode), 0o700)
            self.assertEqual(list(unrelated.iterdir()), [])
            if symlink:
                installer.CADDY_DROPIN.parent.unlink()
            else:
                installer.CADDY_DROPIN.parent.rmdir()

    def test_proxy_helper_never_chmods_or_writes_through_dropin_symlink(self):
        installer.CONFIG.mkdir(mode=0o700)
        unrelated = self.folder / 'unrelated'
        unrelated.mkdir(mode=0o700)
        installer.CADDY_DROPIN.parent.symlink_to(unrelated, target_is_directory=True)
        with self.assertRaises(FileExistsError):
            installer.configure_caddy('new.example.com', enrollment=True)
        self.assertEqual(stat.S_IMODE(unrelated.stat().st_mode), 0o700)
        self.assertEqual(list(unrelated.iterdir()), [])

    def test_normal_termination_and_ssh_hangup_take_controlled_cancellation_path(self):
        for number in (signal.SIGTERM, signal.SIGHUP):
            previous = signal.getsignal(number)
            with self.subTest(signal=number), self.assertRaises(KeyboardInterrupt):
                with installer.cancel_on_signals():
                    signal.raise_signal(number)
            self.assertEqual(signal.getsignal(number), previous)


if __name__ == '__main__':
    unittest.main()
