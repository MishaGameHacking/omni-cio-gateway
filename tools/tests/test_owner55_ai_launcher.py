"""Synthetic launcher contracts; never invokes WSL, SSH or a provider."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parents[1]))


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parents[1] / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


launcher = load('ai_windows_launcher', 'launch_owner55_ai_wsl.py')
guest = load('ai_linux_guest', 'owner55_ai_guest.py')
TOKEN = 'synthetic-cloud-token-never-persist'


class LauncherContracts(unittest.TestCase):
    def test_only_named_variables_cross_to_wsl_and_host_marker_is_not_caller_controlled(self):
        source = {name: 'synthetic-value' for name in launcher.FORWARDED}
        source.update(TIMEWEB_CLOUD_TOKEN=TOKEN, OWNER_AI_HOST_VERIFIED='wrong-host',
                      TINVEST_TOKEN='must-not-forward', SIGNING_PASSWORD='must-not-forward',
                      GITHUB_TOKEN='must-not-forward', PYTHONPATH='must-not-forward')
        result = launcher.guest_environment(source)
        self.assertEqual(result['TIMEWEB_CLOUD_TOKEN'], TOKEN)
        self.assertEqual(result['OWNER_AI_HOST_VERIFIED'], launcher.HOST + ':' + launcher.DISTRO)
        self.assertEqual(set(result['WSLENV'].split(':')), {name + '/u' for name in launcher.FORWARDED})
        for name in ('TINVEST_TOKEN', 'SIGNING_PASSWORD', 'GITHUB_TOKEN', 'PYTHONPATH'):
            self.assertNotIn(name, result)
        self.assertNotIn(TOKEN, result['WSLENV'])

    def test_windows_and_linux_source_allowlists_are_identical(self):
        expected = set(launcher.SOURCE_FILES) | {'.transport-admin/' + name for name in launcher.DEPENDENCY_FILES}
        self.assertEqual(guest.FILES, expected)
        self.assertEqual(guest.DEPENDENCY_SHA, launcher.DEPENDENCY_SHA)

    def bundle(self):
        return {'schema': 1, 'tools_commit': 'a' * 40, 'dependency_commit': guest.DEPENDENCY_SHA,
                'files': {name: {'content': 'synthetic reviewed source',
                    'sha256': hashlib.sha256(b'synthetic reviewed source').hexdigest()}
                    for name in sorted(guest.FILES)}}

    def test_source_copy_preserves_identity_and_private_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            guest.unpack_sources(json.dumps(self.bundle()).encode(), destination)
            for name in guest.FILES:
                path = destination / name
                self.assertEqual(path.read_bytes(), b'synthetic reviewed source')
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_unlisted_paths_and_changed_source_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            bundle = self.bundle()
            bundle['files']['../outside'] = {'content': 'x', 'sha256': '0' * 64}
            with self.assertRaisesRegex(RuntimeError, 'guest_source_identity_invalid'):
                guest.unpack_sources(json.dumps(bundle).encode(), destination)
            self.assertEqual(list(destination.iterdir()), [])
            bundle = self.bundle()
            bundle['files'][next(iter(bundle['files']))]['content'] = 'changed bytes'
            with self.assertRaisesRegex(RuntimeError, 'guest_source_bytes_changed'):
                guest.unpack_sources(json.dumps(bundle).encode(), destination)

    def test_unknown_activation_recovery_state_is_preserved_without_claiming_success(self):
        outcome = {'status': 'activation_unconfirmed', 'reason': 'activation_requires_inspected_recovery',
                   'provider_zero_limits_verified': None}
        report = {'status': 'requires_inspection', 'action': 'activate', 'exit_code': 1,
            'outcome': outcome, 'local_cleanup_succeeded': True, 'automatic_retry_permitted': False}
        self.assertEqual(guest.validate_report(json.dumps(report).encode(), TOKEN), report)
        report['status'] = 'completed'
        with self.assertRaisesRegex(RuntimeError, 'guest_success_receipt_incomplete'):
            guest.validate_report(json.dumps(report).encode(), TOKEN)

    def test_incomplete_success_and_raw_credentials_are_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'guest_success_receipt_incomplete'):
            guest.validate_outcome(b'{"status":"activated"}', TOKEN)
        with self.assertRaisesRegex(RuntimeError, 'guest_outcome_invalid'):
            guest.validate_outcome(json.dumps({'status': 'not_activated', 'reason': TOKEN}).encode(), TOKEN)
        with self.assertRaisesRegex(RuntimeError, 'guest_outcome_invalid'):
            guest.validate_outcome(b'{"status":"not_activated","raw_provider_body":"untrusted"}', TOKEN)

    def test_provisioning_failure_details_are_finite_codes_only(self):
        outcome = {'status': 'not_activated', 'reason': 'new_unused_key_removed_after_failure',
                   'failure_code': 'new_gateway_key_masked', 'new_key_retained': False,
                   'new_key_id': '2b8fa21b-4b04-4904-bd32-ef1181c5f811'}
        self.assertEqual(guest.validate_outcome(json.dumps(outcome).encode(), TOKEN), outcome)
        outcome['failure_code'] = 'new_gateway_key_invalid'
        self.assertEqual(guest.validate_outcome(json.dumps(outcome).encode(), TOKEN), outcome)
        outcome['failure_code'] = 'arbitrary_provider_reply'
        with self.assertRaisesRegex(RuntimeError, 'guest_outcome_invalid'):
            guest.validate_outcome(json.dumps(outcome).encode(), TOKEN)

    def test_readonly_transport_diagnostics_preserve_only_fixed_codes_and_booleans(self):
        outcome = {'status': 'not_activated', 'reason': 'private_preflight_requires_inspection',
            'failure_code': 'private_delivery_failed', 'transport_code': 'private_ssh_client_missing',
            'transport_operation_started': False, 'temporary_ssh_key_removed': True,
            'new_key_id': None, 'new_key_retained': False}
        self.assertEqual(guest.validate_outcome(json.dumps(outcome).encode(), TOKEN), outcome)
        for change in ({'transport_code': 'provider_raw_error'}, {'transport_operation_started': 'false'}):
            with self.subTest(change=change):
                with self.assertRaisesRegex(RuntimeError, 'guest_outcome_invalid'):
                    guest.validate_outcome(json.dumps({**outcome, **change}).encode(), TOKEN)

    def test_preflight_completion_preserves_readiness_and_forbids_mutation(self):
        ready = {'status': 'ready', 'reason': 'ready', 'server_id': 9417611,
            'existing_key_absent': True, 'budget_sources_verified': True,
            'configuration_changed': False, 'read_only_preflight': True,
            'ai_key_created': False, 'ai_limits_changed': False, 'inference_called': False}
        blocked = {**ready, 'status': 'not_ready', 'reason': 'existing_inference_key_must_not_be_replaced',
                   'existing_key_absent': False}
        for outcome in (ready, blocked):
            report = {'status': 'completed', 'action': 'preflight_only', 'exit_code': 0,
                'outcome': outcome, 'local_cleanup_succeeded': True, 'automatic_retry_permitted': False}
            with self.subTest(status=outcome['status']):
                self.assertEqual(guest.validate_report(json.dumps(report).encode(), TOKEN), report)
                for field in ('configuration_changed', 'ai_key_created', 'ai_limits_changed', 'inference_called'):
                    changed = {**outcome, field: True}
                    with self.assertRaisesRegex(RuntimeError, 'guest_success_receipt_incomplete'):
                        guest.validate_outcome(json.dumps(changed).encode(), TOKEN)
        for change in ({'reason': 'arbitrary_provider_reply'}, {'existing_key_absent': False},
                       {'budget_sources_verified': False}, {'status': 'not_ready'}):
            with self.subTest(change=change):
                with self.assertRaisesRegex(RuntimeError, 'guest_success_receipt_incomplete'):
                    guest.validate_outcome(json.dumps({**ready, **change}).encode(), TOKEN)
        wrong_action = {'status': 'completed', 'action': 'provision_disabled', 'exit_code': 0,
            'outcome': ready, 'local_cleanup_succeeded': True, 'automatic_retry_permitted': False}
        with self.assertRaisesRegex(RuntimeError, 'guest_success_receipt_incomplete'):
            guest.validate_report(json.dumps(wrong_action).encode(), TOKEN)

    def test_activation_receipt_requires_caps_no_trade_and_unchanged_public_feed(self):
        outcome = {'status': 'activated', 'server_id': 9417611,
            'key_id': '2b8fa21b-4b04-4904-bd32-ef1181c5f811', 'model': 'dashscope/qwen3.5-flash',
            'daily_cap_rub': '95', 'monthly_cap_rub': '2900',
            'price_valid_until': '2026-10-30T12:00:00+00:00', 'service_restarted': True,
            'configuration_loaded': True, 'health_get_verified': True, 'auth_boundary_verified': True,
            'public_feed_unchanged': True, 'inference_probe_called': False, 'brokerage_request_sent': False,
            'provider_daily_limit_rub': '95', 'provider_30_day_limit_rub': '2900',
            'automatic_price_renewal_installed': False}
        self.assertEqual(guest.validate_outcome(json.dumps(outcome).encode(), TOKEN), outcome)
        for change in ({'public_feed_unchanged': False}, {'brokerage_request_sent': True},
                       {'daily_cap_rub': '100'}):
            with self.subTest(change=change):
                with self.assertRaisesRegex(RuntimeError, 'guest_success_receipt_incomplete'):
                    guest.validate_outcome(json.dumps({**outcome, **change}).encode(), TOKEN)


if __name__ == '__main__':
    unittest.main()
