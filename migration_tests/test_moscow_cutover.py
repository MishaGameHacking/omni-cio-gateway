"""Offline safety regressions. No cloud API/SSH or real application paths are used."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.parse import urlencode

SPEC = importlib.util.spec_from_file_location('cutover', Path(__file__).parents[1] / '.github/scripts/moscow_cutover.py')
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def oauth(**changes):
    values = {'redirect_uri': 'https://' + m.TARGET_HOST + '/auth/telegram/callback',
              'code_challenge_method': 'S256', 'code_challenge': 'abc', 'response_type': 'code', 'state': 'test-state'}
    values.update(changes)
    return 'https://oauth.telegram.org/auth?' + urlencode(values)


class CutoverTests(unittest.TestCase):
    def test_expected_redirect_with_pkce(self):
        self.assertEqual(m.assert_oauth(oauth()), 'test-state')

    def test_old_callback_rejected(self):
        with self.assertRaises(RuntimeError):
            m.assert_oauth(oauth(redirect_uri='https://' + m.SOURCE_HOST + '/auth/telegram/callback'))

    def test_lookalike_telegram_host_rejected(self):
        with self.assertRaises(RuntimeError):
            m.assert_oauth(oauth().replace('oauth.telegram.org', 'oauth.telegram.org.example.com'))

    def test_plaintext_telegram_rejected(self):
        with self.assertRaises(RuntimeError):
            m.assert_oauth(oauth().replace('https://oauth', 'http://oauth'))

    def test_missing_state_rejected(self):
        with self.assertRaises(RuntimeError):
            m.assert_oauth(oauth(state=''))

    def test_weak_pkce_rejected(self):
        with self.assertRaises(RuntimeError):
            m.assert_oauth(oauth(code_challenge_method='plain'))

    def test_duplicate_redirect_rejected(self):
        with self.assertRaises(RuntimeError):
            m.assert_oauth(oauth() + '&redirect_uri=https://example.com')

    def test_atomic_private_write(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'record.json'
            m.write_private(target, 'old')
            m.write_private(target, 'new')
            self.assertEqual(target.read_text(), 'new')
            # POSIX permissions are checked on the Linux VMs, not emulated on Windows.
            if __import__('os').name != 'nt':
                self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            self.assertFalse(target.with_name('record.json.new').exists())

    def test_symlink_write_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            actual = Path(directory) / 'actual'
            actual.write_text('untouched')
            link = Path(directory) / 'link'
            # Windows workers may not grant the symlink privilege; mock the path guard there.
            if __import__('os').name == 'nt':
                with patch.object(Path, 'is_symlink', return_value=True), self.assertRaises(RuntimeError):
                    m.write_private(link, 'changed')
            else:
                link.symlink_to(actual)
                with self.assertRaises(RuntimeError):
                    m.write_private(link, 'changed')
            self.assertEqual(actual.read_text(), 'untouched')

    def test_incomplete_write_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'state'
            target.with_name('state.new').write_text('unknown')
            with self.assertRaises(RuntimeError):
                m.write_private(target, 'retry')

    def test_active_source_cannot_be_copied(self):
        with patch.object(m, 'run_command', return_value='active'), self.assertRaises(RuntimeError):
            m.service_stopped()

    def test_stopped_source_can_be_copied(self):
        with patch.object(m, 'run_command', return_value='inactive'):
            m.service_stopped()

    def test_command_error_does_not_expose_output(self):
        with patch.object(m.subprocess, 'run', return_value=Mock(returncode=1, stdout='private', stderr='secret')):
            with self.assertRaises(RuntimeError) as error:
                m.run_command('systemctl', 'stop', 'unit')
            self.assertNotIn('private', str(error.exception))
            self.assertNotIn('secret', str(error.exception))

    def test_active_marker_prevents_second_activation(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / 'active'
            marker.write_text('{}')
            with patch.object(m, 'ACTIVE', marker), patch.object(m, 'run_command') as command:
                with self.assertRaises(RuntimeError):
                    m.activate(Path(directory))
                command.assert_not_called()

    def test_unvalidated_target_cannot_activate(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            (state / 'target-state.json').write_text(json.dumps({'phase': 'restored_closed'}))
            with patch.object(m, 'ACTIVE', state / 'active'), patch.object(m, 'run_command') as command:
                with self.assertRaises(RuntimeError):
                    m.activate(state)
                command.assert_not_called()

    def test_remote_tool_has_no_cloud_delete_or_provision(self):
        source = Path(SPEC.origin).read_text()
        self.assertNotIn('TIMEWEB_CLOUD_TOKEN', source)
        self.assertNotIn('api.timeweb.cloud', source)
        self.assertNotIn('rmtree(', source)


if __name__ == '__main__':
    unittest.main()
