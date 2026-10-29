"""Synthetic admin-host provenance tests; no SSH, provider or application calls."""
from contextlib import redirect_stdout, redirect_stderr
import io
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).parents[1]))
import owner_ai_admin_transport as admin


class AdminTransportTests(unittest.TestCase):
    def test_only_reviewed_github_ubuntu_administrative_host_is_allowed(self):
        env = {'GITHUB_ACTIONS': 'true', 'RUNNER_ENVIRONMENT': 'github-hosted', 'RUNNER_OS': 'Linux',
               'OWNER_AI_ADMIN_HOST': 'reviewed-ubuntu24-administration-only'}
        release = {'ID': 'ubuntu', 'VERSION_ID': '24.04'}
        admin._verify_environment(env, release, 'generic-azure', 1001)
        for updated_env, updated_release, kernel, uid in (
            ({**env, 'RUNNER_ENVIRONMENT': 'self-hosted'}, release, 'generic-azure', 1001),
            (env, release, 'microsoft-standard-wsl2', 1001),
            (env, {'ID': 'ubuntu', 'VERSION_ID': '22.04'}, 'generic-azure', 1001),
            (env, release, 'generic-azure', 0),
            ({**env, 'OWNER_AI_ADMIN_HOST': 'unknown'}, release, 'generic-azure', 1001)):
            with self.subTest(kernel=kernel, uid=uid, environment=updated_env):
                with self.assertRaises(admin.PrivateTransportError):
                    admin._verify_environment(updated_env, updated_release, kernel, uid)

    def test_host_proof_failure_prevents_private_delivery(self):
        with mock.patch.object(admin, 'require_admin_guard',
            side_effect=admin.PrivateTransportError('reviewed_ai_admin_host_required')):
            with mock.patch.object(admin, '_transport_secret') as transfer:
                with self.assertRaises(admin.PrivateTransportError):
                    admin.transport_admin('reviewed operation', {}, None, {})
                transfer.assert_not_called()

    def test_guard_precedes_shared_transport_and_secret_remains_an_in_memory_argument(self):
        secret = 'synthetic-inference-credential'
        calls = []
        receipt = {'status': 'staged_disabled', 'server_id': 9417611}
        def guarded():
            calls.append('verified')
        def deliver(operation, payload, credential, contract):
            self.assertEqual(calls, ['verified'])
            self.assertEqual(credential, secret)
            self.assertNotIn(secret, operation)
            return receipt
        output = io.StringIO()
        with mock.patch.object(admin, 'require_admin_guard', side_effect=guarded):
            with mock.patch.object(admin, '_transport_secret', side_effect=deliver):
                with redirect_stdout(output), redirect_stderr(output):
                    result = admin.transport_admin('reviewed operation', {'action': 'stage'}, secret, {})
        self.assertIs(result, receipt)
        self.assertEqual(output.getvalue(), '')

    def test_private_diagnostics_are_discarded_and_indeterminate_outcome_is_preserved(self):
        error = admin.PrivateTransportError('private_operation_timeout', operation_started=True,
                                            temporary_key_removed=False)
        def deliver(*args):
            print('synthetic-secret-never-in-receipt')
            print('synthetic-provider-diagnostic', file=sys.stderr)
            raise error
        output = io.StringIO()
        with mock.patch.object(admin, 'require_admin_guard'):
            with mock.patch.object(admin, '_transport_secret', side_effect=deliver):
                with redirect_stdout(output), redirect_stderr(output):
                    with self.assertRaises(admin.PrivateTransportError) as caught:
                        admin.transport_admin('reviewed operation', {}, None, {})
        self.assertIs(caught.exception, error)
        self.assertTrue(caught.exception.operation_started)
        self.assertFalse(caught.exception.temporary_key_removed)
        self.assertEqual(output.getvalue(), '')


if __name__ == '__main__':
    unittest.main()
