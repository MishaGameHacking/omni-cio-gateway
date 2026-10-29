"""Private Linux guest for the existing owner WSL; no credential is persisted."""
from __future__ import annotations
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import stat
import sys
import tempfile
import uuid

PRIVATE_ROOT = Path('/home/analyst-ci/.local/state/analyst-owner-ai')
DEPENDENCY_SHA = 'cd1866ee944ccea2259669f4293379241fd4ee02'
FILES = {'tools/launch_owner55_ai_wsl.py', 'tools/owner55_ai_guest.py', 'tools/inspect_owner55_ai.py', 'tools/provision_owner55_ai.py',
    'tools/owner_ai_private_transport.py', 'tools/owner_plan_transport_20261027.py',
    'deploy/stage_owner55_ai.py', 'tools/activate_owner55_ai.py', 'deploy/activate_owner55_ai.py',
    '.transport-admin/deploy/prepare_owner_vm.py',
    '.transport-admin/deploy/access_owner_vm.py', '.transport-admin/tools/timeweb_ci_capacity.py',
    '.transport-admin/tools/timeweb_actions_probe.py', '.transport-admin/tools/timeweb_ci_catalog.py'}
BOOLEAN_FIELDS = {'existing_key_replaced', 'service_restarted', 'inference_called',
    'provider_fallback_disabled', 'runtime_activation_performed', 'account_currency_rub_confirmed',
    'configuration_loaded', 'health_get_verified', 'auth_boundary_verified', 'inference_probe_called',
    'brokerage_request_sent', 'automatic_price_renewal_installed', 'public_feed_unchanged',
    'existing_key_absent', 'budget_sources_verified', 'configuration_changed',
    'read_only_preflight', 'ai_key_created', 'ai_limits_changed'}
CAP_FIELDS = {'daily_cap_rub', 'monthly_cap_rub', 'provider_daily_limit_rub', 'provider_30_day_limit_rub'}
FAILURE_CODES = {'new_key_metadata_mismatch', 'new_gateway_key_masked_or_invalid',
    'zero_limits_incomplete', 'zero_limits_wrong_periods', 'zero_limits_not_enforced_for_all_models',
    'new_key_not_visible_after_creation', 'remote_staging_receipt_mismatch',
    'cloud_request_failed', 'private_delivery_failed', 'unclassified_failure'}


def need(value, code):
    if not value:
        raise RuntimeError(code)


def validate_outcome(raw, secret):
    need(isinstance(raw, bytes) and 0 < len(raw) <= 32768 and (not secret or secret.encode() not in raw),
         'guest_outcome_invalid')
    result = json.loads(raw)
    allowed = {'status', 'server_id', 'key_id', 'model', 'reason', 'new_key_id', 'new_key_retained',
               'price_valid_until', 'provider_zero_limits_verified', 'failure_code', 'transport_code',
               'transport_operation_started', 'temporary_ssh_key_removed'} | BOOLEAN_FIELDS | CAP_FIELDS
    need(isinstance(result, dict) and set(result) <= allowed
         and result.get('status') in {'staged_disabled', 'not_activated', 'activated', 'activation_unconfirmed',
                                     'ready', 'not_ready'},
         'guest_outcome_invalid')
    for name, value in result.items():
        need(not isinstance(value, str) or not secret or secret not in value, 'guest_outcome_invalid')
        if name in BOOLEAN_FIELDS:
            need(type(value) is bool, 'guest_outcome_invalid')
        elif name in CAP_FIELDS:
            need(value in {'0', '95', '2900', '100', '3000'}, 'guest_outcome_invalid')
        elif name == 'server_id':
            need(type(value) is int and value == 9417611, 'guest_outcome_invalid')
        elif name in {'key_id', 'new_key_id'}:
            need(value is None or (isinstance(value, str) and str(uuid.UUID(value)) == value), 'guest_outcome_invalid')
        elif name in {'new_key_retained', 'provider_zero_limits_verified',
                      'transport_operation_started', 'temporary_ssh_key_removed'}:
            need(value is None or type(value) is bool, 'guest_outcome_invalid')
        elif name == 'failure_code':
            need(value is None or isinstance(value, str) and value in FAILURE_CODES, 'guest_outcome_invalid')
        elif name == 'transport_code':
            from owner_ai_private_transport import SAFE_TRANSPORT_FAILURE_CODES
            need(value is None or isinstance(value, str)
                 and value in SAFE_TRANSPORT_FAILURE_CODES | {'private_preflight_failed'},
                 'guest_outcome_invalid')
        elif name == 'reason':
            need(isinstance(value, str) and re.fullmatch('[a-z][a-z0-9_]{0,95}', value), 'guest_outcome_invalid')
        elif name == 'model':
            need(value == 'dashscope/qwen3.5-flash', 'guest_outcome_invalid')
        elif name == 'price_valid_until':
            need(isinstance(value, str) and len(value) <= 40
                 and datetime.fromisoformat(value).tzinfo is not None, 'guest_outcome_invalid')
    if result['status'] in {'ready', 'not_ready'}:
        from provision_owner55_ai import PREFLIGHT_REASONS
        expected = {'status': result['status'], 'reason': result.get('reason'), 'server_id': 9417611,
            'existing_key_absent': result.get('existing_key_absent'),
            'budget_sources_verified': result.get('budget_sources_verified'),
            'configuration_changed': False, 'read_only_preflight': True,
            'ai_key_created': False, 'ai_limits_changed': False, 'inference_called': False}
        need(result == expected and result.get('reason') in PREFLIGHT_REASONS
             and type(result.get('existing_key_absent')) is bool
             and type(result.get('budget_sources_verified')) is bool,
             'guest_success_receipt_incomplete')
        need((result['status'] == 'ready' and result['reason'] == 'ready'
              and result['existing_key_absent'] and result['budget_sources_verified'])
             or (result['status'] == 'not_ready' and result['reason'] != 'ready'),
             'guest_success_receipt_incomplete')
    elif result['status'] == 'staged_disabled':
        expected = {'status': 'staged_disabled', 'server_id': 9417611, 'key_id': result.get('key_id'),
            'model': 'dashscope/qwen3.5-flash', 'daily_cap_rub': '0', 'monthly_cap_rub': '0',
            'existing_key_replaced': False, 'service_restarted': False, 'inference_called': False,
            'provider_daily_limit_rub': '0', 'provider_30_day_limit_rub': '0',
            'provider_fallback_disabled': True, 'runtime_activation_performed': False,
            'account_currency_rub_confirmed': True}
        need(result == expected and isinstance(result['key_id'], str), 'guest_success_receipt_incomplete')
    elif result['status'] == 'activated':
        expected = {'status': 'activated', 'server_id': 9417611, 'key_id': result.get('key_id'),
            'model': 'dashscope/qwen3.5-flash', 'daily_cap_rub': '95', 'monthly_cap_rub': '2900',
            'price_valid_until': result.get('price_valid_until'), 'service_restarted': True,
            'configuration_loaded': True, 'health_get_verified': True, 'auth_boundary_verified': True,
            'public_feed_unchanged': True,
            'inference_probe_called': False, 'brokerage_request_sent': False,
            'provider_daily_limit_rub': '95', 'provider_30_day_limit_rub': '2900',
            'automatic_price_renewal_installed': False}
        need(result == expected and isinstance(result['key_id'], str)
             and isinstance(result['price_valid_until'], str), 'guest_success_receipt_incomplete')
    return result


def validate_report(raw, secret):
    need(isinstance(raw, bytes) and 0 < len(raw) <= 65536 and (not secret or secret.encode() not in raw),
         'guest_report_invalid')
    report = json.loads(raw)
    need(isinstance(report, dict) and set(report) == {'status', 'action', 'exit_code', 'outcome',
         'local_cleanup_succeeded', 'automatic_retry_permitted'}, 'guest_report_invalid')
    need(report['status'] in {'completed', 'requires_inspection'}
         and report['action'] in {'provision_disabled', 'activate', 'preflight_only'}
         and type(report['exit_code']) is int and 0 <= report['exit_code'] <= 255
         and type(report['local_cleanup_succeeded']) is bool
         and report['automatic_retry_permitted'] is False and isinstance(report['outcome'], dict),
         'guest_report_invalid')
    if report['outcome']:
        validate_outcome(json.dumps(report['outcome']).encode(), secret)
    if report['status'] == 'completed':
        expected_status = {'activate': {'activated'}, 'provision_disabled': {'staged_disabled'},
                           'preflight_only': {'ready', 'not_ready'}}[report['action']]
        need(report['exit_code'] == 0 and report['local_cleanup_succeeded']
             and report['outcome'].get('status') in expected_status,
             'guest_success_receipt_incomplete')
    return report


def private_root():
    need(os.name == 'posix', 'owner_wsl_required')
    import pwd
    need(os.getuid() > 0 and pwd.getpwuid(os.getuid()).pw_name == 'analyst-ci'
         and 'microsoft' in Path('/proc/sys/kernel/osrelease').read_text().lower()
         and os.environ.get('WSL_DISTRO_NAME') == 'Ubuntu-24.04'
         and os.environ.get('OWNER_AI_HOST_VERIFIED') == 'LAPTOP-NPSGA016:Ubuntu-24.04',
         'owner_wsl_required')
    PRIVATE_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = PRIVATE_ROOT.lstat()
    need(PRIVATE_ROOT.resolve(strict=True) == PRIVATE_ROOT and stat.S_ISDIR(info.st_mode)
         and info.st_uid == os.getuid() and not info.st_mode & 0o077, 'private_guest_directory_required')


def unpack_sources(raw, destination):
    need(len(raw) <= 2 * 1024**2, 'guest_source_bundle_too_large')
    bundle = json.loads(raw)
    need(bundle['schema'] == 1 and bundle['dependency_commit'] == DEPENDENCY_SHA
         and re.fullmatch('[a-f0-9]{40}', bundle['tools_commit'])
         and set(bundle['files']) == FILES, 'guest_source_identity_invalid')
    for name, row in bundle['files'].items():
        content = row['content'].encode('utf-8')
        need(0 < len(content) <= 2 * 1024**2
             and hashlib.sha256(content).hexdigest() == row['sha256'], 'guest_source_bytes_changed')
        path = destination / name
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with path.open('xb') as output:
            output.write(content)
        path.chmod(0o600)


def main():
    action = os.environ.get('OWNER_AI_ACTION')
    controllers = {'provision_disabled': 'tools/provision_owner55_ai.py',
                   'preflight_only': 'tools/provision_owner55_ai.py', 'activate': 'tools/activate_owner55_ai.py'}
    need(action in controllers, 'guest_operation_not_reviewed')
    private_root()
    token = os.environ.get('TIMEWEB_CLOUD_TOKEN', '')
    need(16 <= len(token) <= 8192 and not any(c.isspace() for c in token), 'protected_cloud_credential_required')
    raw = sys.stdin.buffer.read(2 * 1024**2 + 1)
    need(token.encode() not in raw, 'credential_must_not_be_in_source_bundle')
    folder = Path(tempfile.mkdtemp(prefix='operation-', dir=PRIVATE_ROOT))
    folder.chmod(0o700)
    original_cwd, outcome, exit_code, cleanup = Path.cwd(), {}, 1, False
    try:
        unpack_sources(raw, folder)
        temporary = folder / 'private-temp'
        temporary.mkdir(mode=0o700)
        os.environ['RUNNER_TEMP'] = str(temporary)
        os.chdir(folder)
        sys.path.insert(0, str(folder / 'tools'))
        from owner_ai_private_transport import require_owner_wsl
        require_owner_wsl()
        stdout, stderr = io.StringIO(), io.StringIO()
        try:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                runpy.run_path(str(folder / controllers[action]), run_name='__main__')
            exit_code = 0
        except SystemExit as error:
            exit_code = error.code if type(error.code) is int and 0 <= error.code <= 255 else 1
        except BaseException:
            exit_code = 1
        outcome = validate_outcome(stdout.getvalue().encode(), token)
    finally:
        os.chdir(original_cwd)
        os.environ.pop('TIMEWEB_CLOUD_TOKEN', None)
        try:
            # Only this newly created, owned private tree is removed.
            need(folder.parent == PRIVATE_ROOT and folder.resolve(strict=True) == folder
                 and folder.stat().st_uid == os.getuid(), 'private_cleanup_target_changed')
            shutil.rmtree(folder)
            cleanup = not folder.exists()
        except BaseException:
            cleanup = False
    report = {'status': 'completed' if exit_code == 0 and cleanup else 'requires_inspection',
              'action': action, 'exit_code': exit_code, 'outcome': outcome,
              'local_cleanup_succeeded': cleanup, 'automatic_retry_permitted': False}
    print(json.dumps(report), flush=True)
    raise SystemExit(0 if exit_code == 0 and cleanup else 1)


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except BaseException:
        print(json.dumps({'status': 'requires_inspection',
            'action': os.environ.get('OWNER_AI_ACTION') if os.environ.get('OWNER_AI_ACTION') in
                {'activate', 'preflight_only'} else 'provision_disabled', 'exit_code': 1,
            'outcome': {}, 'local_cleanup_succeeded': False, 'automatic_retry_permitted': False}), flush=True)
        raise SystemExit(1) from None
