"""Synthetic transport tests: no network, server, provider or credential writes."""
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location('private_transport',
    Path(__file__).parents[1] / 'owner_ai_private_transport.py')
transport = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transport)

KEY_ID = '2b8fa21b-4b04-4904-bd32-ef1181c5f811'
SECRET = 'synthetic-inference-secret-do-not-print'
CLOUD_SECRET = 'synthetic-cloud-secret-do-not-print'
RECEIPT = {'status': 'staged_disabled', 'server_id': 9417611, 'key_id': KEY_ID,
           'service_restarted': False, 'health_status': 200}
CONTRACT = {'status': {'staged_disabled'}, 'server_id': int, 'key_id': {KEY_ID},
            'service_restarted': bool, 'health_status': int}


class ReceiptTests(unittest.TestCase):
    def test_only_explicit_scalar_fields_escape(self):
        self.assertEqual(transport.validate_receipt(json.dumps(RECEIPT).encode(), CONTRACT), RECEIPT)

    def test_secret_cannot_escape_even_in_an_allowlisted_string(self):
        receipt = dict(RECEIPT, key_id=SECRET)
        contract = dict(CONTRACT, key_id={SECRET})
        with self.assertRaisesRegex(transport.PrivateTransportError, 'private_receipt_contains_credential'):
            transport.validate_receipt(json.dumps(receipt).encode(), contract, (SECRET,))
        escaped = 'synthetic-credential-with-"quote'
        with self.assertRaisesRegex(transport.PrivateTransportError, 'private_receipt_contains_credential'):
            transport.validate_receipt(json.dumps(dict(RECEIPT, key_id=escaped)).encode(),
                                       dict(CONTRACT, key_id={escaped}), (escaped,))

    def test_unknown_fields_types_values_and_wrong_server_are_rejected(self):
        for receipt in (dict(RECEIPT, unexpected='raw-output'), dict(RECEIPT, health_status=True),
                        dict(RECEIPT, status='arbitrary-provider-response'), dict(RECEIPT, server_id=1)):
            with self.subTest(receipt=receipt):
                with self.assertRaises(transport.PrivateTransportError):
                    transport.validate_receipt(json.dumps(receipt).encode(), CONTRACT)

    def test_duplicate_keys_and_oversized_output_are_rejected(self):
        with self.assertRaisesRegex(transport.PrivateTransportError, 'private_receipt_duplicate_key'):
            transport.validate_receipt(b'{"server_id":9417611,"server_id":9417611}', CONTRACT)
        with self.assertRaisesRegex(transport.PrivateTransportError, 'private_receipt_size_invalid'):
            transport.validate_receipt(b'x' * (transport.MAX_RECEIPT + 1), CONTRACT)
        # Rejection is required whether this interpreter rejects the nesting
        # during parsing or parses it and rejects the non-object receipt.
        with self.assertRaises(transport.PrivateTransportError):
            transport.validate_receipt(b'[' * 2000 + b'0' + b']' * 2000, CONTRACT)
        with mock.patch.object(transport.json, 'loads', side_effect=RecursionError('synthetic parser depth')):
            with self.assertRaisesRegex(transport.PrivateTransportError, 'private_receipt_invalid_json'):
                transport.validate_receipt(b'{"server_id":9417611}', CONTRACT)


class PrivateTransferTests(unittest.TestCase):
    def setUp(self):
        guard = mock.patch.object(transport, 'require_owner_wsl')
        guard.start(); self.addCleanup(guard.stop)
        executables = mock.patch.object(transport.shutil, 'which', side_effect=lambda name: '/usr/bin/' + name)
        executables.start(); self.addCleanup(executables.stop)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.calls = []
        self.cleanup_fails = False
        self.attach_fails = False
        self.created = None

        def generate_key(path):
            path.write_text('synthetic SSH key, not inference credential')
            path.chmod(0o600)
            path.with_suffix('.pub').write_text('ssh-ed25519 synthetic-public-key')

        def request(token, method, path, body=None):
            self.assertEqual(token, CLOUD_SECRET)
            self.calls.append((method, path))
            if method == 'POST' and path == '/ssh-keys':
                self.created = body
                return {'ssh_key': {'id': 77, 'body': body['body']}}
            if method == 'POST' and path == '/servers/9417611/ssh-keys' and self.attach_fails:
                raise RuntimeError(SECRET)
            if method == 'DELETE' and '/servers/' in path and self.cleanup_fails:
                raise RuntimeError(SECRET)
            return {}

        cloud = SimpleNamespace(generate_key=generate_key, public_ipv4=lambda server: server['ip'])
        p = SimpleNamespace(cloud=cloud, ProbeError=RuntimeError,
            ssh_command=lambda folder, ip, key: ['ssh', '-i', str(folder / 'client'), ip],
            remote=mock.Mock())
        self.backend = SimpleNamespace(SERVER_ID=9417611, IP='83.217.195.29',
            HOST_KEY='pinned-public-host-key', TOKEN=CLOUD_SECRET, p=p,
            access=SimpleNamespace(request=request),
            api=mock.Mock(return_value=(200, {'server': {'name': 'Analyst AI runtime 20261025',
                'project_id': 2941515, 'availability_zone': 'ams-1', 'ip': '83.217.195.29'}})))
        self.load = mock.patch.object(transport, '_load_transport', return_value=self.backend)
        self.load.start(); self.addCleanup(self.load.stop)
        self.environment = mock.patch.dict(os.environ, RUNNER_TEMP=str(self.folder), GITHUB_RUN_ID='40900000000')
        self.environment.start(); self.addCleanup(self.environment.stop)

    def invoke(self):
        return transport.transport_secret('print("reviewed operation")',
            {'configuration': {'provider_enabled': 'false'}}, SECRET, CONTRACT)

    def test_secret_is_only_ssh_stdin_and_no_receipt_or_secret_artifact_is_written(self):
        output = io.StringIO()
        result = SimpleNamespace(returncode=0, stdout=json.dumps(RECEIPT).encode())
        with mock.patch.object(transport.subprocess, 'run', return_value=result) as run:
            with redirect_stdout(output), redirect_stderr(output):
                self.assertEqual(self.invoke(), RECEIPT)
        command = run.call_args.args[0]
        self.assertNotIn(SECRET, ' '.join(command))
        self.assertNotIn(CLOUD_SECRET, ' '.join(command))
        envelope = json.loads(run.call_args.kwargs['input'])
        self.assertEqual(envelope['secret'], SECRET)
        self.assertEqual(run.call_args.kwargs['stderr'], subprocess.DEVNULL)
        self.assertEqual(output.getvalue(), '')
        self.assertEqual(list(self.folder.iterdir()), [])
        self.assertEqual(self.calls[-2:], [('DELETE', '/servers/9417611/ssh-keys/77'),
                                          ('DELETE', '/ssh-keys/77')])

    def test_timeout_is_indeterminate_and_cleanup_never_exposes_exception_output(self):
        with mock.patch.object(transport.subprocess, 'run',
            side_effect=subprocess.TimeoutExpired('synthetic-command', 240, output=SECRET.encode())):
            with self.assertRaises(transport.PrivateTransportError) as caught:
                self.invoke()
        self.assertTrue(caught.exception.operation_started)
        self.assertTrue(caught.exception.temporary_key_removed)
        self.assertIsNone(caught.exception.validated_receipt)
        self.assertNotIn(SECRET, str(caught.exception))


        self.assertEqual(list(self.folder.iterdir()), [])

    def test_failed_temporary_key_cleanup_retains_validated_staging_outcome(self):
        self.cleanup_fails = True
        with mock.patch.object(transport.subprocess, 'run',
            return_value=SimpleNamespace(returncode=0, stdout=json.dumps(RECEIPT).encode())):
            with self.assertRaisesRegex(transport.PrivateTransportError, 'private_temporary_key_cleanup_failed') as caught:
                self.invoke()
        self.assertTrue(caught.exception.operation_started)
        self.assertFalse(caught.exception.temporary_key_removed)
        self.assertEqual(caught.exception.validated_receipt, RECEIPT)
        self.assertEqual(self.calls[-1], ('DELETE', '/ssh-keys/77'))

    def test_attach_failure_cleans_only_own_key_and_marks_operation_not_started(self):
        self.attach_fails = True
        with mock.patch.object(transport.subprocess, 'run') as run:
            with self.assertRaises(transport.PrivateTransportError) as caught:
                self.invoke()
            run.assert_not_called()
        self.assertFalse(caught.exception.operation_started)
        self.assertTrue(caught.exception.temporary_key_removed)
        self.assertEqual(self.calls[-2:], [('DELETE', '/servers/9417611/ssh-keys/77'),
                                          ('DELETE', '/ssh-keys/77')])

    def test_wrong_server_is_rejected_before_creating_temporary_access(self):
        self.backend.api.return_value[1]['server']['project_id'] = 1
        with self.assertRaises(transport.PrivateTransportError) as caught:
            self.invoke()
        self.assertFalse(caught.exception.operation_started)
        self.assertEqual(self.calls, [])

    def test_lost_key_creation_response_does_not_claim_cleanup_or_delete_unknown_key(self):
        self.backend.access.request = mock.Mock(side_effect=RuntimeError(CLOUD_SECRET))
        with self.assertRaises(transport.PrivateTransportError) as caught:
            self.invoke()
        self.assertFalse(caught.exception.operation_started)
        self.assertFalse(caught.exception.temporary_key_removed)
        self.backend.access.request.assert_called_once()
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_missing_ssh_tools_are_reported_before_any_cloud_access(self):
        for missing, code in (('ssh', 'private_ssh_client_missing'), ('ssh-keygen', 'private_ssh_keygen_missing')):
            with self.subTest(missing=missing):
                with mock.patch.object(transport.shutil, 'which', side_effect=lambda name: None if name == missing else '/usr/bin/' + name):
                    with mock.patch.object(transport, '_load_transport') as load:
                        with self.assertRaisesRegex(transport.PrivateTransportError, code) as caught:
                            self.invoke()
                        load.assert_not_called()
                        self.assertFalse(caught.exception.operation_started)

    def test_dependency_prints_and_raw_creation_exception_are_never_replayed(self):
        def fail(*args, **kwargs):
            print(SECRET)
            print(CLOUD_SECRET, file=__import__('sys').stderr)
            raise RuntimeError(SECRET)
        self.backend.access.request = fail
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            with self.assertRaisesRegex(transport.PrivateTransportError, 'private_ssh_key_create_failed') as caught:
                self.invoke()
        self.assertEqual(output.getvalue(), '')
        self.assertFalse(caught.exception.operation_started)
        self.assertFalse(caught.exception.temporary_key_removed)
        self.assertIn(caught.exception.code, transport.SAFE_TRANSPORT_FAILURE_CODES)

    def test_dependency_import_and_metadata_failures_have_distinct_fixed_codes(self):
        for target, code in (('_load_transport', 'private_transport_dependency_failed'),
                             ('metadata', 'private_server_metadata_failed')):
            with self.subTest(target=target):
                patch = (mock.patch.object(transport, '_load_transport', side_effect=RuntimeError(SECRET))
                         if target == '_load_transport' else mock.patch.object(self.backend, 'api', side_effect=RuntimeError(SECRET)))
                with patch:
                    with self.assertRaisesRegex(transport.PrivateTransportError, code) as caught:
                        self.invoke()
                    self.assertFalse(caught.exception.operation_started)
        self.assertEqual(self.calls, [])

    def test_local_cleanup_failure_preserves_committed_remote_outcome(self):
        original = tempfile.TemporaryDirectory
        class FailingCleanup:
            def __init__(self, *args, **kwargs):
                self.directory = original(*args, **kwargs)
            def __enter__(self):
                return self.directory.__enter__()
            def __exit__(self, *args):
                self.directory.__exit__(*args)
                raise OSError(SECRET)
        with mock.patch.object(transport.tempfile, 'TemporaryDirectory', FailingCleanup):
            with mock.patch.object(transport.subprocess, 'run',
                return_value=SimpleNamespace(returncode=0, stdout=json.dumps(RECEIPT).encode())):
                with self.assertRaisesRegex(transport.PrivateTransportError, 'private_local_workspace_failed') as caught:
                    self.invoke()
        self.assertTrue(caught.exception.operation_started)
        self.assertTrue(caught.exception.temporary_key_removed)
        self.assertEqual(caught.exception.validated_receipt, RECEIPT)
        self.assertNotIn(SECRET, str(caught.exception))


class ProvenanceTests(unittest.TestCase):
    def test_native_windows_is_rejected_before_any_external_call(self):
        with mock.patch.object(transport.os, 'name', 'nt'):
            with self.assertRaisesRegex(transport.PrivateTransportError, 'owner_wsl_runtime_required'):
                transport.require_owner_wsl()

    def test_only_verified_owner_wsl_and_private_linux_directory_are_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            root.chmod(0o700)
            temporary = root / 'run-private'
            temporary.mkdir(mode=0o700)
            import pwd
            with mock.patch.object(transport, 'PRIVATE_ROOT', root), \
                 mock.patch.object(transport, '_kernel_release', return_value='microsoft-standard-wsl2'), \
                 mock.patch.object(pwd, 'getpwnam', return_value=SimpleNamespace(pw_uid=os.getuid())), \
                 mock.patch.dict(os.environ, RUNNER_TEMP=str(temporary), WSL_DISTRO_NAME='Ubuntu-24.04',
                                 OWNER_AI_HOST_VERIFIED=transport.WSL_HOST_MARKER):
                transport.require_owner_wsl()
                with mock.patch.dict(os.environ, OWNER_AI_HOST_VERIFIED='unverified'):
                    with self.assertRaises(transport.PrivateTransportError):
                        transport.require_owner_wsl()
                temporary.chmod(0o755)
                with self.assertRaisesRegex(transport.PrivateTransportError, 'owner_private_temporary_directory_required'):
                    transport.require_owner_wsl()


if __name__ == '__main__':
    unittest.main()
