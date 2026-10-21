"""First-install boundary tests; no cloud order or server mutation."""
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from unittest.mock import MagicMock

SOURCE = Path(__file__).resolve().parents[2] / 'deploy/install_owner_backend.py'
SPEC = importlib.util.spec_from_file_location('owner_installer', SOURCE)
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


def configuration():
    return {'TELEGRAM_CLIENT_ID': '123456', 'TELEGRAM_CLIENT_SECRET': 'synthetic-secret',
            'ANALYST_OWNER_TELEGRAM_SUB': '987654', 'BACKEND_PUBLIC_URL': 'https://new.example.com',
            'EXPECTED_PUBLIC_IPV4': '1.1.1.1'}


class OwnerInstallationTests(unittest.TestCase):
    def test_missing_owner_never_selects_first_visitor(self):
        config = configuration()
        del config['ANALYST_OWNER_TELEGRAM_SUB']
        with self.assertRaisesRegex(installer.InstallError, 'exact_configuration'):
            installer.validated_config(config)

    def test_retired_host_cleartext_and_config_injection_are_rejected(self):
        cases = [('BACKEND_PUBLIC_URL', value) for value in (
            'http://new.example.com', 'https://176.98.178.81.sslip.io',
            'https://new.example.com/other', 'https://user@new.example.com',
            'https://new.example.com:443', 'https://new.example.com\nadmin off',
            'https://new..example.com', 'https://1.1.1.1')]
        cases += [('ANALYST_OWNER_TELEGRAM_SUB', 'x' * 257), ('ANALYST_OWNER_TELEGRAM_SUB', 'subject with whitespace'),
                  ('EXPECTED_PUBLIC_IPV4', '127.0.0.1')]
        for name, value in cases:
            candidate = configuration() | {name: value}
            with self.subTest(name=name, value=value), self.assertRaises(installer.InstallError):
                installer.validated_config(candidate)

    def test_oidc_subject_is_preserved_and_never_derived_from_numeric_profile_id(self):
        for subject in ('1234123412341234123', 'opaque:Owner-A_9', 'x' * 256):
            with self.subTest(subject=subject):
                values = configuration() | {'ANALYST_OWNER_TELEGRAM_SUB': subject}
                self.assertEqual(installer.validated_config(values)['ANALYST_OWNER_TELEGRAM_SUB'], subject)
        profile_only = configuration() | {'TELEGRAM_PROFILE_ID': '987654321'}
        with self.assertRaises(installer.InstallError):
            installer.validated_config(profile_only)

    def test_environment_is_data_and_never_copies_install_target(self):
        config = configuration() | {'TELEGRAM_CLIENT_SECRET': 'synthetic"$value\\tail'}
        document = installer.environment_text(config, 'synthetic-fernet')
        values = {name: json.loads(value) for name, value in (line.split('=', 1) for line in document.splitlines())}
        self.assertEqual(values['TELEGRAM_CLIENT_SECRET'], config['TELEGRAM_CLIENT_SECRET'])
        self.assertNotIn('EXPECTED_PUBLIC_IPV4', values)
        self.assertEqual(values['DATABASE_PATH'], '/var/lib/analyst-ai/backend.db')

    def test_secret_file_and_existing_destination_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'env'
            installer.write_new(path, 'first', 0o600)
            with self.assertRaises(FileExistsError):
                installer.write_new(path, 'second', 0o600)
            self.assertEqual(path.read_text(), 'first')

    @patch.object(installer.socket, 'getaddrinfo')
    @patch.object(installer.subprocess, 'run')
    def test_dns_and_actual_interface_must_match_same_new_vm(self, run, dns):
        values = configuration()
        dns.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('1.1.1.1', 443))]
        run.return_value = subprocess.CompletedProcess([], 0, b'[{"addr_info":[{"local":"1.1.1.1"}]}]')
        installer.check_address(values)
        run.return_value = subprocess.CompletedProcess([], 0, b'[{"addr_info":[{"local":"8.8.8.8"}]}]')
        with self.assertRaisesRegex(installer.InstallError, 'not_assigned'):
            installer.check_address(values)
        dns.return_value.append((socket.AF_INET6, socket.SOCK_STREAM, 6, '', ('2606:4700::1111', 443, 0, 0)))
        with self.assertRaisesRegex(installer.InstallError, 'dns_does_not_identify'):
            installer.check_address(values)

    def test_source_package_contains_real_owner_factory(self):
        names = {path.name for path in installer.source_files()}
        self.assertIn('owner_app.py', names)
        self.assertIn('telegram_jwks.json', names)
        self.assertNotIn('backend.db', names)

    @patch.object(installer, 'check_target', side_effect=installer.InstallError('existing_installation_refused_no_data_replaced'))
    @patch.object(installer, 'run')
    def test_existing_installation_blocks_every_command(self, run, _check):
        values = configuration()
        with self.assertRaises(installer.InstallError):
            installer.install(values)
        run.assert_not_called()

    @patch.object(installer, 'HTTPConnection')
    def test_health_success_never_accepts_anonymous_workspace_access_or_redirects(self, factory):
        health = MagicMock()
        health.__enter__.return_value.status = 200
        health.__enter__.return_value.read.return_value = b'{"status":"ok"}'
        workspace = MagicMock()
        for status in (200, 301, 401, 403, 404, 503):
            workspace.__enter__.return_value.status = status
            factory.return_value.getresponse.side_effect = [health, workspace]
            with self.subTest(status=status):
                self.assertEqual(installer.probe(), status == 401)
            factory.assert_called_with('127.0.0.1', 8080, timeout=5)
            factory.return_value.close.assert_called()

    @patch.object(installer.ssl, 'create_default_context')
    @patch.object(installer.socket, 'create_connection')
    def test_tls_probe_pins_loopback_and_checks_certificate_for_configured_hostname(self, connect, tls):
        connection = installer.LocalTLSConnection('new.example.com')
        connection.connect()
        connect.assert_called_once_with(('127.0.0.1', 443), timeout=5)
        tls.return_value.wrap_socket.assert_called_once_with(connect.return_value, server_hostname='new.example.com')
        tls.return_value.wrap_socket.side_effect = installer.ssl.SSLError('synthetic invalid certificate')
        with self.assertRaises(installer.ssl.SSLError):
            connection.connect()
        connect.return_value.close.assert_called_once()

    def test_fixed_config_file_rejects_symlinks_and_unsafe_permissions(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'private.json'
            source.write_text(json.dumps(configuration()))
            source.chmod(0o600)
            with patch.object(installer, 'INPUT_CONFIG', source):
                self.assertEqual(installer.load_config(), configuration())
                source.chmod(0o644)
                with self.assertRaises(installer.InstallError):
                    installer.load_config()
            link = Path(folder) / 'link.json'
            link.symlink_to(source)
            with patch.object(installer, 'INPUT_CONFIG', link), self.assertRaises(OSError):
                installer.load_config()


if __name__ == '__main__':
    unittest.main()
