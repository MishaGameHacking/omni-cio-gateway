"""Prepare initial owner entry without setting a password or changing accounts.

Only the bootstrap value supplied through the private envelope can be written.
The existing application makes it unusable after the first password is created.
No credential, credential hash, database content or session is returned.
"""
import fcntl
import hashlib
import hmac
import json
import os
import re

BOOTSTRAP = 'ANALYST_OWNER_BOOTSTRAP_SECRET'
AUTH_SOURCES = {'owner_password.py', 'owner_password_routes.py', 'owner_access.py'}
STATUSES = {'waiting_for_secret', 'bootstrap_ready', 'already_configured', 'blocked'}
PHASES = {'source_verification', 'service_metadata', 'owner_status',
          'bootstrap_validation', 'configuration_write', 'restart', 'runtime_verification', 'complete'}
BOOLEAN_FIELDS = ('password_configured', 'bootstrap_configured', 'configuration_changed',
    'service_restarted', 'bootstrap_loaded', 'key_matches_supplied',
    'preserved_configuration', 'health_verified', 'auth_boundary_verified', 'public_feed_unchanged')


def need(condition, reason):
    if not condition:
        raise RuntimeError(reason)


def valid_bootstrap(secret):
    return isinstance(secret, str) and re.fullmatch('[A-Za-z0-9_-]{32,128}', secret) is not None


def verify_auth_sources(expected):
    need(isinstance(expected, dict) and set(expected) == AUTH_SOURCES, 'incomplete_auth_source_proof')
    for name, digest in expected.items():
        need(isinstance(digest, str) and re.fullmatch('[a-f0-9]{64}', digest), 'invalid_auth_source_proof')
        actual = hashlib.sha256(STAGING['read_regular'](STAGING['SOURCES'] / name)).hexdigest()
        need(actual == digest, 'auth_source_changed')


def password_configured():
    status = ACTIVATION['read_get'](ACTIVATION['PUBLIC'] + '/auth/owner/status')
    need(isinstance(status, dict) and type(status.get('configured')) is bool
         and status.get('method') == 'password'
         and status.get('setup_requires') == 'existing_owner_session_or_bootstrap'
         and status.get('min_password_length') == 10
         and status.get('max_password_bytes') == 128, 'owner_status_not_verified')
    return status['configured']


def run(envelope):
    receipt = {name: False for name in BOOLEAN_FIELDS}
    receipt.update(status='blocked', server_id=9417611, phase='source_verification',
                   minimum_bootstrap_length=32, minimum_password_length=10)
    try:
        need(os.getuid() == 0, 'private_root_required')
        payload = envelope['payload']
        need(set(payload) == {'source_sha256'}, 'invalid_bootstrap_payload')
        secret = envelope.get('secret')
        with STAGING['LOCK'].open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            verify_auth_sources(payload['source_sha256'])
            snapshot = STAGING['configuration_snapshot']()
            settings = STAGING['parse_environment'](snapshot[0])
            receipt['bootstrap_configured'] = bool(settings.get(BOOTSTRAP))
            receipt['phase'] = 'service_metadata'
            ACTIVATION['verify_environment_file']()
            need(settings.get('ANALYST_OWNER_TELEGRAM_SUB'), 'owner_binding_missing')
            need(ACTIVATION['systemctl']('is-active', 'analyst-ai-owner.service') == 'active', 'owner_service_inactive')
            feed_pid = ACTIVATION['public_feed_pid']()
            need(ACTIVATION['read_get'](ACTIVATION['PUBLIC'] + '/health') == {'status': 'ok'}, 'health_unverified')
            receipt['health_verified'] = True
            ACTIVATION['read_get'](ACTIVATION['PUBLIC'] + '/workspace/live?wait=0', allowed_status=401)
            receipt['auth_boundary_verified'] = True
            receipt['phase'] = 'owner_status'
            receipt['password_configured'] = password_configured()
            if receipt['password_configured']:
                receipt.update(status='already_configured', phase='complete', preserved_configuration=True,
                               public_feed_unchanged=ACTIVATION['public_feed_pid']() == feed_pid)
                return receipt
            if secret is None:
                receipt.update(status='waiting_for_secret', phase='complete', preserved_configuration=True,
                               public_feed_unchanged=ACTIVATION['public_feed_pid']() == feed_pid)
                return receipt
            receipt['phase'] = 'bootstrap_validation'
            need(valid_bootstrap(secret), 'bootstrap_format_invalid')
            unset = ACTIVATION['systemctl']('show', 'analyst-ai-owner.service', '--property=UnsetEnvironment', '--value')
            unset_names = {word.partition('=')[0] for word in unset.split()}
            need(BOOTSTRAP not in unset_names, 'bootstrap_unset_by_service')
            # This operation cannot replace a configured password or alter users,
            # sessions, brokerage tokens, AI budgets or any other environment key.
            need(not password_configured(), 'password_configured_during_preparation')
            receipt['phase'] = 'configuration_write'
            desired = STAGING['replacement_environment'](snapshot[0], {BOOTSTRAP: secret})
            parsed = STAGING['parse_environment'](desired)
            need({k: v for k, v in parsed.items() if k != BOOTSTRAP}
                 == {k: v for k, v in settings.items() if k != BOOTSTRAP}, 'unrelated_configuration_changed')
            STAGING['atomic_configuration'](desired, snapshot)
            receipt['configuration_changed'] = True
            need(STAGING['configuration_snapshot']()[0] == desired, 'bootstrap_write_not_verified')
            receipt['phase'] = 'restart'
            ACTIVATION['systemctl']('restart', 'analyst-ai-owner.service')
            receipt['service_restarted'] = True
            receipt['phase'] = 'runtime_verification'
            # Preserve deliberate systemd exclusions while proving the supplied
            # key and the retained configuration loaded. No value is returned.
            ACTIVATION['readiness_after_restart']({k: v for k, v in parsed.items() if k not in unset_names})
            receipt.update(bootstrap_loaded=True, preserved_configuration=True)
            actual = STAGING['parse_environment'](STAGING['configuration_snapshot']()[0])
            receipt['key_matches_supplied'] = hmac.compare_digest(actual.get(BOOTSTRAP, ''), secret)
            need(receipt['key_matches_supplied'], 'bootstrap_changed_after_restart')
            receipt['bootstrap_configured'] = True
            receipt['password_configured'] = password_configured()
            receipt['public_feed_unchanged'] = ACTIVATION['public_feed_pid']() == feed_pid
            need(receipt['public_feed_unchanged'], 'public_feed_changed')
            receipt.update(status='already_configured' if receipt['password_configured'] else 'bootstrap_ready',
                           phase='complete')
    except BaseException:
        # Failure after a write is indeterminate. Never restore stale snapshots,
        # reveal private diagnostics, or claim that a password has been created.
        pass
    return receipt


if __name__ == '__main__':
    print(json.dumps(run(ENVELOPE)), flush=True)
