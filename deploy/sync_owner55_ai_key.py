"""Synchronize the rotated secret for the same reviewed AI key.

Only TIMEWEB_AI_TOKEN may change. No provider mutation, inference, brokerage
request, owner password, session, budget, price or model change is permitted.
"""
import fcntl
import hmac
import json
import os
import uuid

FIELDS = ('configuration_changed', 'service_restarted', 'key_matches_supplied',
          'gateway_verified', 'configuration_loaded', 'health_verified',
          'auth_boundary_verified', 'public_feed_unchanged', 'other_settings_preserved')
PHASES = {'identity', 'configuration', 'gateway', 'write', 'restart', 'verification', 'complete'}


def need(value):
    if not value:
        raise RuntimeError('key_sync_precondition_failed')


def run(envelope):
    result = {name:False for name in FIELDS}
    result.update(status='blocked', phase='identity', server_id=9417611)
    try:
        need(os.getuid() == 0)
        payload, secret = envelope['payload'], envelope['secret']
        need(set(payload) == {'source_sha256', 'key_id', 'limit_ids'})
        key_id = payload['key_id']
        need(isinstance(key_id, str) and str(uuid.UUID(key_id)) == key_id)
        ids = payload['limit_ids']
        need(isinstance(ids, dict) and set(ids) == {'day', 'month'})
        need(all(isinstance(v, str) and str(uuid.UUID(v)) == v for v in ids.values()))
        need(ids['day'] != ids['month'])
        STAGING['require_gateway_key'](secret)
        with STAGING['LOCK'].open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            STAGING['verify_sources'](payload['source_sha256'])
            snapshot = STAGING['configuration_snapshot']()
            settings = STAGING['parse_environment'](snapshot[0])
            need(settings.get('ANALYST_OWNER_AI_KEY_ID') == key_id)
            for period, identity in ids.items():
                need(settings.get('ANALYST_OWNER_AI_' + period.upper() + '_LIMIT_ID') == identity)
            need(all(settings.get(k) == v for k,v in ACTIVATION['ENABLED'].items()))
            need(not settings.get('TIMEWEB_CLOUD_API_KEY') and not settings.get('AI_ROUTE_CATALOG_JSON'))
            need(all(not settings.get('TIMEWEB_AI_' + t + '_TOKEN') for t in ('FAST','STANDARD','PREMIUM')))
            # Confirm the existing, unexpired bounded route; do not extend prices.
            pricing = {
                'input_rub_per_million':settings.get('AI_FAST_INPUT_RUB_PER_MILLION'),
                'output_rub_per_million':settings.get('AI_FAST_OUTPUT_RUB_PER_MILLION'),
                'valid_until':settings.get('AI_FAST_PRICING_VALID_UNTIL')}
            expected_route = STAGING['settings_for'](
                {'key_id':key_id,'model':STAGING['MODEL'],'pricing':pricing}, secret)
            need(all(settings.get(k) == v for k,v in expected_route.items()
                     if k != 'TIMEWEB_AI_TOKEN' and k not in STAGING['DISABLED']))
            result['phase'] = 'configuration'
            ACTIVATION['verify_environment_file']()
            need(ACTIVATION['systemctl']('is-active','analyst-ai-owner.service') == 'active')
            unset = ACTIVATION['systemctl']('show','analyst-ai-owner.service','--property=UnsetEnvironment','--value')
            excluded = {word.partition('=')[0] for word in unset.split()}
            need('TIMEWEB_AI_TOKEN' not in excluded)
            expected = {k:v for k,v in settings.items() if k not in excluded}
            ACTIVATION['verify_running_configuration'](expected)
            feed = ACTIVATION['public_feed_pid']()
            need(ACTIVATION['read_get'](ACTIVATION['PUBLIC']+'/health') == {'status':'ok'})
            ACTIVATION['read_get'](ACTIVATION['PUBLIC']+'/workspace/live?wait=0',allowed_status=401)
            result['phase'] = 'gateway'
            ACTIVATION['verify_inference_key'](secret)
            result['gateway_verified'] = True
            same = hmac.compare_digest(settings.get('TIMEWEB_AI_TOKEN',''),secret)
            if not same:
                result['phase'] = 'write'
                desired = STAGING['replacement_environment'](snapshot[0],{'TIMEWEB_AI_TOKEN':secret})
                parsed = STAGING['parse_environment'](desired)
                need({k:v for k,v in parsed.items() if k != 'TIMEWEB_AI_TOKEN'} ==
                     {k:v for k,v in settings.items() if k != 'TIMEWEB_AI_TOKEN'})
                STAGING['atomic_configuration'](desired,snapshot)
                result['configuration_changed'] = True
                need(STAGING['configuration_snapshot']()[0] == desired)
                result['phase'] = 'restart'
                ACTIVATION['systemctl']('restart','analyst-ai-owner.service')
                result['service_restarted'] = True
                expected['TIMEWEB_AI_TOKEN'] = secret
                ACTIVATION['readiness_after_restart'](expected)
            result['phase'] = 'verification'
            ACTIVATION['verify_running_configuration'](expected)
            actual = STAGING['parse_environment'](STAGING['configuration_snapshot']()[0])
            result['key_matches_supplied'] = hmac.compare_digest(actual.get('TIMEWEB_AI_TOKEN',''),secret)
            result['other_settings_preserved'] = (
                {k:v for k,v in actual.items() if k != 'TIMEWEB_AI_TOKEN'} ==
                {k:v for k,v in settings.items() if k != 'TIMEWEB_AI_TOKEN'})
            result['public_feed_unchanged'] = ACTIVATION['public_feed_pid']() == feed
            need(result['key_matches_supplied'] and result['other_settings_preserved'] and result['public_feed_unchanged'])
            need(ACTIVATION['read_get'](ACTIVATION['PUBLIC']+'/health') == {'status':'ok'})
            ACTIVATION['read_get'](ACTIVATION['PUBLIC']+'/workspace/live?wait=0',allowed_status=401)
            result.update(status='already_current' if same else 'synchronized', phase='complete',
                          configuration_loaded=True,health_verified=True,auth_boundary_verified=True)
    except BaseException:
        pass
    return result


if __name__ == '__main__':
    print(json.dumps(run(ENVELOPE)),flush=True)
