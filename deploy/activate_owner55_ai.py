"""Activate the already staged key; never issue inference or brokerage requests.

The controller supplies reviewed staging helpers in STAGING. Provider limits must
already have been verified before the activation action. A failed operation is
indeterminate: the controller blocks the provider first and retains the key.
"""
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.request

MODEL = 'dashscope/qwen3.5-flash'
SERVICES = ('analyst-ai-owner.service',)
PUBLIC_FEED = 'analyst-ai-updates.service'
ENABLED = {'AI_USER_DAILY_RUB': '95', 'AI_PROJECT_DAILY_RUB': '95',
           'AI_USER_MONTHLY_RUB': '2900', 'AI_PROJECT_MONTHLY_RUB': '2900',
           'AI_EXTERNAL_PROCESSING_APPROVED': 'true'}
PUBLIC = 'https://analyst-ai-2941515.twc1.net'


def need(condition, code):
    if not condition:
        raise RuntimeError(code)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def read_get(url, *, credential=None, allowed_status=200):
    headers = {'Accept': 'application/json', 'Cache-Control': 'no-cache'}
    if credential is not None:
        headers['Authorization'] = 'Bearer ' + credential
    request = urllib.request.Request(url, headers=headers, method='GET')
    opener = urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(request, timeout=20) as response:
            need(response.status == allowed_status, 'read_only_readiness_status_invalid')
            raw = response.read(1024 * 1024 + 1)
        need(len(raw) <= 1024 * 1024, 'read_only_readiness_response_too_large')
        value = json.loads(raw)
        need(isinstance(value, dict), 'read_only_readiness_response_invalid')
        return value
    except urllib.error.HTTPError as error:
        if error.code == allowed_status == 401:
            return {}
        raise RuntimeError('read_only_readiness_failed') from None
    except (urllib.error.URLError, OSError, ValueError, TypeError):
        raise RuntimeError('read_only_readiness_failed') from None


def verify_inference_key(secret):
    # This is a metadata GET, made while provider spending limits are zero.
    # Its response never leaves this process. No /chat/completions is called.
    value = read_get('https://api.timeweb.ai/v1/models', credential=secret)
    rows = value.get('data')
    need(isinstance(rows, list) and len(rows) <= 10000
         and all(isinstance(row, dict) for row in rows), 'inference_model_catalog_invalid')
    need(sum(row.get('id') == MODEL for row in rows) == 1, 'exact_inference_model_unavailable')


def activation_settings(settings, payload):
    support = STAGING
    need(settings.get('ANALYST_OWNER_AI_KEY_ID') == payload.get('key_id'), 'staged_key_identity_mismatch')
    need(not settings.get('TIMEWEB_CLOUD_API_KEY', '').strip()
         and not settings.get('AI_ROUTE_CATALOG_JSON', '').strip(), 'unreviewed_existing_ai_route')
    need(all(not settings.get('TIMEWEB_AI_' + tier + '_TOKEN', '').strip()
             for tier in ('FAST', 'STANDARD', 'PREMIUM')), 'unreviewed_tier_credential')
    need(all(settings.get(key) == value for key, value in support['DISABLED'].items()),
         'staged_ai_is_not_disabled')
    changes = support['settings_for'](payload, settings.get('TIMEWEB_AI_TOKEN'))
    # All non-pricing routing fields must still match the staged, bounded route.
    pricing_suffixes = ('INPUT_RUB_PER_MILLION', 'OUTPUT_RUB_PER_MILLION', 'PRICING_VALID_UNTIL')
    for key, value in changes.items():
        if not key.endswith(pricing_suffixes):
            need(settings.get(key) == value, 'staged_ai_configuration_changed')
    changes.update(ENABLED)
    limits = payload.get('limit_ids')
    need(isinstance(limits, dict) and set(limits) == {'day', 'month'}, 'provider_limit_identity_missing')
    import uuid
    for period, value in limits.items():
        need(isinstance(value, str) and str(uuid.UUID(value)) == value, 'provider_limit_identity_invalid')
        key = 'ANALYST_OWNER_AI_' + period.upper() + '_LIMIT_ID'
        need(not settings.get(key, '').strip(), 'activation_already_recorded')
        changes[key] = value
    need(limits['day'] != limits['month'], 'provider_limit_identity_invalid')
    return changes


def systemctl(*arguments):
    result = subprocess.run(['systemctl', *arguments], stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, timeout=60)
    need(result.returncode == 0, 'ai_service_operation_failed')
    need(len(result.stdout) <= 4096, 'ai_service_metadata_too_large')
    return result.stdout.decode('ascii').strip()


def verify_environment_file():
    # Inspect only EnvironmentFiles metadata, never systemctl Environment values.
    value = systemctl('show', SERVICES[0], '--property=EnvironmentFiles', '--value')
    need(value == '/etc/analyst-ai/backend.env (ignore_errors=no)',
         'owner_service_environment_file_unverified')


def public_feed_pid():
    need(systemctl('is-active', PUBLIC_FEED) == 'active', 'public_feed_not_active')
    pid = systemctl('show', PUBLIC_FEED, '--property=MainPID', '--value')
    need(pid.isdigit() and int(pid) > 1, 'public_feed_pid_invalid')
    return pid


def verify_running_configuration(expected):
    # Inspect only the two existing service processes, never return their env.
    for service in SERVICES:
        need(systemctl('is-active', service) == 'active', 'ai_service_inactive')
        pid = systemctl('show', service, '--property=MainPID', '--value')
        need(pid.isdigit() and int(pid) > 1, 'ai_service_pid_invalid')
        with Path('/proc/' + pid + '/environ').open('rb') as source:
            raw = source.read(512 * 1024 + 1)
        need(len(raw) <= 512 * 1024, 'ai_process_environment_invalid')
        entries = [entry.split(b'=', 1) for entry in raw.split(b'\0') if entry]
        need(all(len(entry) == 2 for entry in entries), 'ai_process_environment_invalid')
        actual = dict(entries)
        need(all(actual.get(key.encode()) == value.encode() for key, value in expected.items()),
             'ai_process_configuration_not_loaded')


def readiness_after_restart(expected):
    for attempt in range(10):
        try:
            # Type=simple may report started before the child has completed exec.
            verify_running_configuration(expected)
            need(read_get(PUBLIC + '/health') == {'status': 'ok'}, 'ai_runtime_health_invalid')
            read_get(PUBLIC + '/workspace/live?wait=0', allowed_status=401)
            return
        except RuntimeError:
            if attempt == 9:
                raise
            time.sleep(1)


def run(envelope):
    import fcntl
    need(os.getuid() == 0 and envelope.get('secret') is None, 'private_root_activation_required')
    payload = envelope.get('payload')
    need(isinstance(payload, dict) and payload.get('action') in {'preflight_activation', 'activate'},
         'invalid_activation_action')
    support = STAGING
    with support['LOCK'].open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        support['verify_sources'](payload.get('source_sha256'))
        original = support['configuration_snapshot']()
        settings = support['parse_environment'](original[0])
        changes = activation_settings(settings, payload)
        verify_environment_file()
        feed_pid = public_feed_pid()
        if payload['action'] == 'preflight_activation':
            verify_inference_key(settings['TIMEWEB_AI_TOKEN'])
            return {'status': 'activation_ready', 'server_id': 9417611, 'key_id': payload['key_id'],
                    'inference_key_authenticated': True, 'model_present': True,
                    'configuration_changed': False, 'inference_probe_called': False}
        desired = support['replacement_environment'](original[0], changes)
        support['atomic_configuration'](desired, original)
        need(support['configuration_snapshot']()[0] == desired, 'ai_activation_write_not_verified')
        systemctl('restart', *SERVICES)
        readiness_after_restart(changes)
        need(public_feed_pid() == feed_pid, 'public_feed_changed_during_ai_activation')
        # An uncertain result is not rolled back over concurrent configuration.
        # The controller's first recovery action blocks both provider limits.
        return {'status': 'activated', 'server_id': 9417611, 'key_id': payload['key_id'],
                'model': MODEL, 'daily_cap_rub': '95', 'monthly_cap_rub': '2900',
                'price_valid_until': payload['pricing']['valid_until'],
                'service_restarted': True, 'configuration_loaded': True,
                'health_get_verified': True, 'auth_boundary_verified': True,
                'public_feed_unchanged': True,
                'inference_probe_called': False, 'brokerage_request_sent': False}


if __name__ == '__main__':
    try:
        print(json.dumps(run(ENVELOPE)), flush=True)
    except BaseException:
        raise SystemExit(1) from None
