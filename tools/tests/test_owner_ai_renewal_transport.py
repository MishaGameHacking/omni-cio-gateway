"""Synthetic tests for scheduled metadata-only transport; no external calls."""
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
from contextlib import redirect_stdout, redirect_stderr

sys.path.insert(0, str(Path(__file__).parents[1]))
import owner_ai_renewal_transport as renewal

KEY = '2b8fa21b-4b04-4904-bd32-ef1181c5f811'
CLOUD = 'synthetic-cloud-credential-never-forward'
RECEIPT = {'status': 'not_due', 'server_id': 9417611, 'key_id': KEY,
           'configuration_changed': False, 'inference_probe_called': False}
CONTRACT = {'status': {'not_due'}, 'server_id': int, 'key_id': {KEY},
            'configuration_changed': bool, 'inference_probe_called': bool}


class RenewalHostTests(unittest.TestCase):
    def test_only_reviewed_github_ubuntu_admin_environment_is_allowed(self):
        env = {'GITHUB_ACTIONS': 'true', 'RUNNER_ENVIRONMENT': 'github-hosted', 'RUNNER_OS': 'Linux',
               'OWNER_AI_RENEWAL_ADMIN_HOST': 'reviewed-ubuntu24-metadata-only'}
        release = {'ID': 'ubuntu', 'VERSION_ID': '24.04'}
        renewal._verify_environment(env, release, 'generic-azure', 1001)
        for changed_env, changed_release, kernel, uid in (
            ({**env, 'RUNNER_ENVIRONMENT': 'self-hosted'}, release, 'generic-azure', 1001),
            (env, release, 'microsoft-standard-wsl2', 1001),
            (env, {'ID': 'ubuntu', 'VERSION_ID': '22.04'}, 'generic-azure', 1001),
            (env, release, 'generic-azure', 0),
            ({**env, 'OWNER_AI_RENEWAL_ADMIN_HOST': 'unknown'}, release, 'generic-azure', 1001)):
            with self.subTest(environment=changed_env, kernel=kernel, uid=uid):
                with self.assertRaises(renewal.PrivateTransportError):
                    renewal._verify_environment(changed_env, changed_release, kernel, uid)

    def test_provenance_failure_prevents_all_cloud_access(self):
        with mock.patch.object(renewal, 'require_renewal_admin',
            side_effect=renewal.PrivateTransportError('reviewed_renewal_admin_host_required')):
            with mock.patch.object(renewal, '_load_transport') as backend:
                with self.assertRaises(renewal.PrivateTransportError):
                    renewal.transport_renewal('reviewed code', {}, CONTRACT)
                backend.assert_not_called()


class RenewalTransferTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.calls = []
        def generate_key(path):
            path.write_text('synthetic temporary SSH key')
            path.chmod(0o600)
            path.with_suffix('.pub').write_text('ssh-ed25519 synthetic-public-key')
        def request(token, method, path, body=None):
            self.assertEqual(token, CLOUD)
            self.calls.append((method, path))
            if method == 'POST' and path == '/ssh-keys':
                return {'ssh_key': {'id': 77, 'body': body['body']}}
            return {}
        backend = SimpleNamespace(TOKEN=CLOUD, SERVER_ID=9417611, IP='83.217.195.29',
            HOST_KEY='pinned-host-key', access=SimpleNamespace(request=request),
            api=mock.Mock(return_value=(200, {'server': {'name': 'Analyst AI runtime 20261025',
                'project_id': 2941515, 'availability_zone': 'ams-1', 'ip': '83.217.195.29'}})),
            p=SimpleNamespace(ProbeError=RuntimeError, remote=mock.Mock(),
                ssh_command=lambda folder, ip, key: ['ssh', '-i', str(folder / 'client'), ip],
                cloud=SimpleNamespace(generate_key=generate_key, public_ipv4=lambda server: server['ip'])))
        self.backend = backend
        for patcher in (mock.patch.object(renewal, 'require_renewal_admin'),
                        mock.patch.object(renewal, '_load_transport', return_value=backend),
                        mock.patch.dict(os.environ, RUNNER_TEMP=str(self.folder), GITHUB_RUN_ID='40900000000')):
            patcher.start(); self.addCleanup(patcher.stop)

    def invoke(self):
        return renewal.transport_renewal('print("reviewed renewal")',
            {'action': 'preflight_renewal', 'key_id': KEY}, CONTRACT)

    def test_cloud_and_inference_credentials_never_cross_ssh(self):
        captured = io.StringIO()
        with mock.patch.object(renewal.subprocess, 'run',
            return_value=SimpleNamespace(returncode=0, stdout=json.dumps(RECEIPT).encode())) as run:
            with redirect_stdout(captured), redirect_stderr(captured):
                self.assertEqual(self.invoke(), RECEIPT)
        envelope = json.loads(run.call_args.kwargs['input'])
        self.assertIsNone(envelope['secret'])
        self.assertNotIn(CLOUD, run.call_args.kwargs['input'].decode())
        self.assertNotIn(CLOUD, ' '.join(run.call_args.args[0]))
        self.assertEqual(captured.getvalue(), '')
        self.assertEqual(list(self.folder.iterdir()), [])
        self.assertEqual(self.calls[-2:], [('DELETE', '/servers/9417611/ssh-keys/77'),
                                          ('DELETE', '/ssh-keys/77')])

    def test_unexpected_response_cannot_become_a_secret_receipt(self):
        raw = json.dumps({**RECEIPT, 'key_id': 'sk-unexpected-inference-credential'}).encode()
        with mock.patch.object(renewal.subprocess, 'run',
            return_value=SimpleNamespace(returncode=0, stdout=raw)):
            with self.assertRaises(renewal.PrivateTransportError) as caught:
                self.invoke()
        self.assertTrue(caught.exception.operation_started)
        self.assertTrue(caught.exception.temporary_key_removed)
        self.assertIsNone(caught.exception.validated_receipt)
        self.assertNotIn('sk-unexpected', str(caught.exception))
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_dependency_diagnostics_are_discarded_before_scheduled_logs(self):
        def fail(*args, **kwargs):
            print(CLOUD)
            print('sk-unexpected-inference-credential', file=sys.stderr)
            raise RuntimeError(CLOUD)
        self.backend.access.request = fail
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            with self.assertRaises(renewal.PrivateTransportError):
                self.invoke()
        self.assertEqual(output.getvalue(), '')


if __name__ == '__main__':
    unittest.main()
