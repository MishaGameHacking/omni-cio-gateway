"""Renew verified AI prices while the existing runtime is verifiably paused.

Reviewed STAGING and ACTIVATION helpers are supplied in memory. This operation
never obtains Cloud credentials, changes the inference key or calls inference.
"""
from datetime import datetime, timedelta, timezone
import json
import os

PRICE_SUFFIXES = ('INPUT_RUB_PER_MILLION', 'OUTPUT_RUB_PER_MILLION', 'PRICING_VALID_UNTIL')
REFRESH_MARKER = 'ANALYST_OWNER_AI_PRICE_REFRESHED_AT'
INTERVAL = timedelta(hours=6)
LIFETIME = timedelta(hours=24)


def need(condition, code):
    if not condition:
        raise RuntimeError(code)


def timestamp(value):
    need(isinstance(value, str) and len(value) <= 40, 'renewal_timestamp_invalid')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    need(parsed.tzinfo is not None, 'renewal_timestamp_invalid')
    return parsed.astimezone(timezone.utc)


def active_configuration(settings, payload, *, now=None):
    now = datetime.now(timezone.utc) if now is None else now
    need(settings.get('ANALYST_OWNER_AI_KEY_ID') == payload.get('key_id'), 'renewal_key_identity_changed')
    need(not settings.get('TIMEWEB_CLOUD_API_KEY', '').strip()
         and not settings.get('AI_ROUTE_CATALOG_JSON', '').strip()
         and all(not settings.get('TIMEWEB_AI_' + tier + '_TOKEN', '').strip()
                 for tier in ('FAST', 'STANDARD', 'PREMIUM')), 'renewal_route_not_reviewed')
    expected = STAGING['settings_for'](payload, settings.get('TIMEWEB_AI_TOKEN'))
    expected.update(ACTIVATION['ENABLED'])
    for key, value in expected.items():
        if not key.endswith(PRICE_SUFFIXES):
            need(settings.get(key) == value, 'renewal_active_configuration_changed')
    identities = payload.get('limit_ids')
    need(isinstance(identities, dict) and set(identities) == {'day', 'month'}, 'renewal_limit_identity_missing')
    import uuid
    for period, identity in identities.items():
        need(isinstance(identity, str) and str(uuid.UUID(identity)) == identity,
             'renewal_limit_identity_invalid')
        key = 'ANALYST_OWNER_AI_' + period.upper() + '_LIMIT_ID'
        need(settings.get(key) == identity, 'renewal_limit_identity_changed')
        expected[key] = identity
    need(identities['day'] != identities['month'], 'renewal_limit_identity_invalid')
    observed = timestamp(payload.get('observed_at'))
    expires = timestamp(payload['pricing']['valid_until'])
    need(expires - observed == LIFETIME and timedelta(seconds=-30) <= now - observed <= timedelta(minutes=15),
         'fresh_catalog_observation_required')
    expiries = [timestamp(settings.get('AI_' + tier + '_PRICING_VALID_UNTIL'))
                for tier in ('FAST', 'STANDARD', 'PREMIUM')]
    need(all(value == expiries[0] for value in expiries), 'renewal_existing_deadlines_disagree')
    previous = expiries[0] - LIFETIME
    if settings.get(REFRESH_MARKER):
        need(timestamp(settings[REFRESH_MARKER]) == previous, 'renewal_previous_observation_mismatch')
    need(previous <= now + timedelta(seconds=30), 'renewal_previous_observation_in_future')
    expected[REFRESH_MARKER] = payload['observed_at']
    changes = {key: value for key, value in expected.items()
               if key.endswith(PRICE_SUFFIXES) or key == REFRESH_MARKER}
    return expected, changes, now - previous >= INTERVAL


def current_process_expectation(settings, expected):
    # Compare the active process with the existing file, not the new quote yet.
    result = {key: settings[key] for key in expected if key != REFRESH_MARKER}
    if settings.get(REFRESH_MARKER):
        result[REFRESH_MARKER] = settings[REFRESH_MARKER]
    return result


def preflight_receipt(key_id, due):
    return {'status': 'renewal_due' if due else 'not_due', 'server_id': 9417611,
            'key_id': key_id, 'configuration_changed': False, 'inference_probe_called': False}


def renewal_receipt(payload):
    return {'status': 'renewed', 'server_id': 9417611, 'key_id': payload['key_id'],
            'model': ACTIVATION['MODEL'], 'daily_cap_rub': '95', 'monthly_cap_rub': '2900',
            'price_valid_until': payload['pricing']['valid_until'], 'service_restarted': True,
            'configuration_loaded': True, 'health_get_verified': True, 'auth_boundary_verified': True,
            'public_feed_unchanged': True, 'app_pause_verified': True, 'inference_probe_called': False,
            'brokerage_request_sent': False}


def run(envelope):
    import fcntl
    need(os.getuid() == 0 and envelope.get('secret') is None, 'private_root_renewal_required')
    payload = envelope.get('payload')
    need(isinstance(payload, dict) and payload.get('action') in {'renewal_preflight', 'renew_prices'},
         'renewal_action_invalid')
    with STAGING['LOCK'].open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        STAGING['verify_sources'](payload.get('source_sha256'))
        snapshot = STAGING['configuration_snapshot']()
        settings = STAGING['parse_environment'](snapshot[0])
        expected, changes, due = active_configuration(settings, payload)
        ACTIVATION['verify_environment_file']()
        need(ACTIVATION['systemctl']('show', 'analyst-ai-owner.service', '--property=KillMode', '--value')
             == 'control-group', 'renewal_requires_service_group_termination')
        feed_pid = ACTIVATION['public_feed_pid']()
        ACTIVATION['verify_running_configuration'](current_process_expectation(settings, expected))
        if payload['action'] == 'renewal_preflight':
            return preflight_receipt(payload['key_id'], due)
        need(due, 'renewal_interval_not_elapsed')
        # Normal renewal never patches provider limits, whose usage-counter
        # preservation is undocumented. Stop the old service process group with
        # approval disabled, then prove the replacement process is paused.
        paused = STAGING['replacement_environment'](snapshot[0], {'AI_EXTERNAL_PROCESSING_APPROVED': 'false'})
        STAGING['atomic_configuration'](paused, snapshot)
        paused_snapshot = STAGING['configuration_snapshot']()
        need(paused_snapshot[0] == paused, 'renewal_pause_write_not_verified')
        ACTIVATION['systemctl']('restart', 'analyst-ai-owner.service')
        paused_expected = current_process_expectation(settings, expected)
        paused_expected['AI_EXTERNAL_PROCESSING_APPROVED'] = 'false'
        ACTIVATION['readiness_after_restart'](paused_expected)
        need(ACTIVATION['public_feed_pid']() == feed_pid, 'public_feed_changed_during_renewal')
        # Mutate prices only after pause verification. Approval remains disabled
        # throughout the price write; interruption here leaves a paused runtime.
        priced = STAGING['replacement_environment'](paused, changes)
        STAGING['atomic_configuration'](priced, paused_snapshot)
        priced_snapshot = STAGING['configuration_snapshot']()
        need(priced_snapshot[0] == priced, 'renewal_price_write_not_verified')
        resumed = STAGING['replacement_environment'](priced, {'AI_EXTERNAL_PROCESSING_APPROVED': 'true'})
        STAGING['atomic_configuration'](resumed, priced_snapshot)
        need(STAGING['configuration_snapshot']()[0] == resumed, 'renewal_resume_write_not_verified')
        ACTIVATION['systemctl']('restart', 'analyst-ai-owner.service')
        ACTIVATION['readiness_after_restart'](expected)
        need(ACTIVATION['public_feed_pid']() == feed_pid, 'public_feed_changed_during_renewal')
        return renewal_receipt(payload)


if __name__ == '__main__':
    try:
        print(json.dumps(run(ENVELOPE)), flush=True)
    except BaseException:
        raise SystemExit(1) from None
