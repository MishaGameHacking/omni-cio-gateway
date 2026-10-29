"""Refresh exact-owner pricing with a verified runtime pause during the update.

Only a fresh catalog GET supplies a new 24-hour validity window. The server
enforces a six-hour minimum interval. A key left blocked by an incident or an
owner action is never automatically unblocked by a scheduled renewal.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path

import activate_owner55_ai as activation
from owner_ai_renewal_transport import transport_renewal, require_renewal_admin

GATE = 'renew-existing-owner55-prices-after-review'
LIMITS = activation.LIMITS


class RenewalError(RuntimeError):
    def __init__(self, code, *, provider_blocked=None):
        super().__init__(code)
        self.code, self.provider_blocked = code, provider_blocked


def need(condition, code):
    if not condition:
        raise RenewalError(code)


def preflight_receipt(key_id, due):
    return {'status': 'renewal_due' if due else 'not_due', 'server_id': 9417611,
            'key_id': key_id, 'configuration_changed': False, 'inference_probe_called': False}


def expected_receipt(key_id, pricing):
    return {'status': 'renewed', 'server_id': 9417611, 'key_id': key_id,
            'model': activation.MODEL, 'daily_cap_rub': '95', 'monthly_cap_rub': '2900',
            'price_valid_until': pricing['valid_until'], 'service_restarted': True,
            'configuration_loaded': True, 'health_get_verified': True, 'auth_boundary_verified': True,
            'public_feed_unchanged': True, 'app_pause_verified': True, 'inference_probe_called': False,
            'brokerage_request_sent': False}


def operation_source():
    root = Path(__file__).resolve().parents[1]
    support = (root / 'deploy/stage_owner55_ai.py').read_text(encoding='utf-8')
    activate = (root / 'deploy/activate_owner55_ai.py').read_text(encoding='utf-8')
    renew = (root / 'deploy/renew_owner55_ai.py').read_text(encoding='utf-8')
    return ('support={"__name__":"owner_ai_staging_support"}\n'
        'exec(compile(' + repr(support) + ',"owner-ai-staging-support","exec"),support)\n'
        'activate={"__name__":"owner_ai_activation_support","STAGING":support}\n'
        'exec(compile(' + repr(activate) + ',"owner-ai-activation-support","exec"),activate)\n'
        'exec(compile(' + repr(renew) + ',"owner-ai-price-renewal","exec"),'
        '{"STAGING":support,"ACTIVATION":activate,"ENVELOPE":ENVELOPE,"__name__":"__main__"})\n')


def renew(api, private_transfer, operation, sources, key_id, creation_run, *, now=None):
    provider_limits = {'day':'100', 'month':'2900'} if creation_run == 'owner-supplied' else LIMITS
    finances = api.request('GET', activation.provision.FINANCES).get('finances')
    need(isinstance(finances, dict) and finances.get('currency') == 'RUB', 'renewal_currency_not_rub')
    activation.owned_key(api, key_id, creation_run)
    # Require the normal active limits. Never undo a manual or incident block.
    identities = activation.limit_ids(api.request('GET', activation.KEYS + '/' + key_id + '/entity-limits'),
                                      key_id, provider_limits)
    try:
        observed = datetime.now(timezone.utc) if now is None else now
        pricing = activation.provision.pricing(api, observed)
        payload = {'key_id': key_id, 'model': activation.MODEL, 'pricing': pricing,
                   'observed_at': observed.isoformat(), 'source_sha256': sources, 'limit_ids': identities}
        due_receipt = preflight_receipt(key_id, True)
        contract = activation.receipt_contract(due_receipt)
        contract['status'] = {'renewal_due', 'not_due'}
        receipt = private_transfer(operation, {**payload, 'action': 'renewal_preflight'}, contract)
        activation.owned_key(api, key_id, creation_run)
        activation.verify_limits(api, key_id, identities, provider_limits)
        if receipt == preflight_receipt(key_id, False):
            return {**receipt, 'provider_daily_limit_rub': provider_limits['day'], 'provider_30_day_limit_rub': '2900',
                    'automatic_retry_permitted': False}
        need(receipt == due_receipt, 'renewal_preflight_receipt_invalid')
        expected = expected_receipt(key_id, pricing)
        receipt = private_transfer(operation, {**payload, 'action': 'renew_prices'},
                                   activation.receipt_contract(expected))
        need(receipt == expected, 'renewal_private_receipt_invalid')
        activation.verify_limits(api, key_id, identities, provider_limits)
        activation.owned_key(api, key_id, creation_run)
        return {**receipt, 'provider_daily_limit_rub': provider_limits['day'], 'provider_30_day_limit_rub': '2900',
                'provider_limits_changed': False, 'automatic_retry_permitted': False}
    except BaseException:
        # Once exact ownership and limit IDs are established, uncertainty in
        # pricing, preflight, update or restoration always blocks the provider.
        blocked = activation.block_provider(api, key_id, identities)
        raise RenewalError('renewal_requires_inspected_recovery', provider_blocked=blocked) from None


def main():
    require_renewal_admin()
    need(os.environ.get('OWNER_AI_RENEWAL_REVIEW') == GATE, 'reviewed_renewal_gate_required')
    token = os.environ.get('TIMEWEB_CLOUD_TOKEN', '').strip()
    need(token and len(token) <= 8192 and not any(c.isspace() for c in token), 'protected_cloud_credential_required')
    receipt = renew(activation.ActivationAPI(token), transport_renewal, operation_source(),
        json.loads(os.environ['OWNER_AI_EXPECTED_BUDGET_SOURCES']),
        os.environ.get('OWNER_AI_STAGED_KEY_ID', ''), os.environ.get('OWNER_AI_CREATION_RUN_ID', ''))
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    try:
        main()
    except RenewalError as error:
        print(json.dumps({'status': 'renewal_unconfirmed', 'reason': error.code,
                          'provider_zero_limits_verified': error.provider_blocked,
                          'automatic_retry_permitted': False}), flush=True)
        raise SystemExit(1) from None
    except BaseException:
        print(json.dumps({'status': 'renewal_unconfirmed', 'reason': 'private_renewal_failed',
                          'automatic_retry_permitted': False}), flush=True)
        raise SystemExit(1) from None
