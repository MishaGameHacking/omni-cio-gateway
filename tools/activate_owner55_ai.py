"""Activate only the identified zero-limit key after private GET readiness.

No key is created, regenerated or deleted. All writes are exact limit PATCHes
and the reviewed remote configuration operation. Prices expire after one day;
this tool does not pretend that price renewal has already been installed.
"""
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request

import provision_owner55_ai as provision
from owner_ai_private_transport import transport_secret, require_owner_wsl

LIMITS = {'day': '95', 'month': '2900'}
GATE = 'activate-existing-owner55-key-after-review'
KEYS = provision.KEYS
MODEL = provision.MODEL


class ActivationError(RuntimeError):
    def __init__(self, code, *, provider_blocked=None):
        super().__init__(code)
        self.code, self.provider_blocked = code, provider_blocked


def need(condition, code):
    if not condition:
        raise ActivationError(code)


def limit_patch_path(path):
    parts = path.removeprefix(KEYS + '/').split('/')
    return (path.startswith(KEYS + '/') and len(parts) == 3 and parts[1] == 'entity-limits'
            and provision.uuid_text(parts[0]) is not None and provision.uuid_text(parts[2]) is not None)


class ActivationAPI(provision.CloudAPI):
    def request(self, method, path, body=None):
        if method == 'GET':
            return super().request(method, path, body)
        need(method == 'PATCH' and limit_patch_path(path) and isinstance(body, dict)
             and set(body) == {'money_limit'} and type(body['money_limit']) is int
             and body['money_limit'] in {0, 95, 2900}, 'activation_endpoint_not_allowlisted')
        request = urllib.request.Request(provision.BASE + path, method='PATCH',
            data=json.dumps(body, allow_nan=False).encode(),
            headers={'Authorization': 'Bearer ' + self._token, 'Accept': 'application/json',
                     'Content-Type': 'application/json'})
        try:
            with self._opener.open(request, timeout=30) as response:
                need(response.status == 200, 'limit_patch_http_status_invalid')
                raw = response.read(provision.MAX_BYTES + 1)
            need(len(raw) <= provision.MAX_BYTES, 'limit_patch_response_too_large')
            value = json.loads(raw, parse_float=Decimal)
            need(isinstance(value, dict), 'limit_patch_response_invalid')
            return value
        except (urllib.error.URLError, OSError, ValueError, TypeError):
            raise ActivationError('limit_patch_outcome_requires_readback') from None


def owned_key(api, key_id, creation_run):
    if creation_run == 'owner-supplied':
        need(provision.uuid_text(key_id) == key_id, 'staged_key_identity_invalid')
        matches = [row for row in provision.keys(api) if row['id'] == key_id]
        need(len(matches) == 1, 'dedicated_key_identity_changed')
        # Identity is the pinned UUID and owner project, not a display name.
        provision.validate_created_metadata(matches[0], matches[0]['name'], key_id)
        return
    need(provision.uuid_text(key_id) == key_id and re.fullmatch('[0-9]{8,20}', creation_run),
         'staged_key_identity_invalid')
    rows = provision.keys(api)
    dedicated = [row for row in rows if row['name'].startswith(provision.DEDICATED_PREFIX)]
    need(len(dedicated) == 1 and dedicated[0]['id'] == key_id, 'dedicated_key_identity_changed')
    provision.validate_created_metadata(dedicated[0], provision.DEDICATED_PREFIX + creation_run, key_id)


def limit_ids(payload, key_id, expected):
    rows, complete = provision.complete_collection(payload, 'ai_key_entity_limits')
    need(complete and len(rows) == 2 and all(isinstance(row, dict) for row in rows),
         'provider_limit_inventory_invalid')
    result = {}
    for row in rows:
        period = row.get('limit_type')
        identity = provision.uuid_text(row.get('id'))
        amount = provision.decimal_text(row.get('money_limit'))
        need(period in expected and period not in result and identity is not None
             and identity not in result.values() and row.get('ai_key_id') == key_id
             and row.get('entity_id') == key_id and row.get('entity_type') == 'aikey'
             and 'model_id' in row and row['model_id'] is None and amount is not None
             and Decimal(amount) == Decimal(expected[period]), 'provider_limit_binding_invalid')
        result[period] = identity
    need(set(result) == {'day', 'month'}, 'provider_limit_periods_invalid')
    return result


def verify_limits(api, key_id, identities, expected):
    actual = limit_ids(api.request('GET', KEYS + '/' + key_id + '/entity-limits'), key_id, expected)
    need(actual == identities, 'provider_limit_identity_changed')


def block_provider(api, key_id, identities):
    # Attempt both periods even if one response is lost. Only exact zero readback
    # of both owned IDs constitutes a verified recovery result.
    for period in ('day', 'month'):
        try:
            api.request('PATCH', KEYS + '/' + key_id + '/entity-limits/' + identities[period],
                        {'money_limit': 0})
        except BaseException:
            pass
    try:
        verify_limits(api, key_id, identities, {'day': '0', 'month': '0'})
        return True
    except BaseException:
        return False


def operation_source():
    root = Path(__file__).resolve().parents[1]
    support = (root / 'deploy/stage_owner55_ai.py').read_text(encoding='utf-8')
    operation = (root / 'deploy/activate_owner55_ai.py').read_text(encoding='utf-8')
    return ('support={"__name__":"owner_ai_staging_support"}\n'
            'exec(compile(' + repr(support) + ',"owner-ai-staging-support","exec"),support)\n'
            'exec(compile(' + repr(operation) + ',"owner-ai-activation","exec"),'
            '{"STAGING":support,"ENVELOPE":ENVELOPE,"__name__":"__main__"})\n')


def activated_receipt(key_id, pricing):
    return {'status': 'activated', 'server_id': 9417611, 'key_id': key_id, 'model': MODEL,
            'daily_cap_rub': '95', 'monthly_cap_rub': '2900',
            'price_valid_until': pricing['valid_until'], 'service_restarted': True,
            'configuration_loaded': True, 'health_get_verified': True,
            'auth_boundary_verified': True, 'public_feed_unchanged': True, 'inference_probe_called': False,
            'brokerage_request_sent': False}


def receipt_contract(expected):
    return {key: bool if type(value) is bool else int if type(value) is int else {value}
            for key, value in expected.items()}


def activate(api, private_transfer, operation, sources, key_id, creation_run, *, now=None):
    now = datetime.now(timezone.utc) if now is None else now
    finances = api.request('GET', provision.FINANCES).get('finances')
    need(isinstance(finances, dict) and finances.get('currency') == 'RUB', 'account_currency_not_rub')
    pricing = provision.pricing(api, now)
    owned_key(api, key_id, creation_run)
    identities = limit_ids(api.request('GET', KEYS + '/' + key_id + '/entity-limits'),
                           key_id, {'day': '0', 'month': '0'})
    payload = {'key_id': key_id, 'model': MODEL, 'pricing': pricing,
               'source_sha256': sources, 'limit_ids': identities}
    expected_preflight = {'status': 'activation_ready', 'server_id': 9417611, 'key_id': key_id,
                          'inference_key_authenticated': True, 'model_present': True,
                          'configuration_changed': False, 'inference_probe_called': False}
    receipt = private_transfer(operation, {**payload, 'action': 'preflight_activation'},
                               None, receipt_contract(expected_preflight))
    need(receipt == expected_preflight, 'private_activation_preflight_failed')
    # Recheck the exact zero limits after the readiness GET and before any write.
    owned_key(api, key_id, creation_run)
    verify_limits(api, key_id, identities, {'day': '0', 'month': '0'})
    try:
        for period in ('day', 'month'):
            api.request('PATCH', KEYS + '/' + key_id + '/entity-limits/' + identities[period],
                        {'money_limit': int(LIMITS[period])})
        verify_limits(api, key_id, identities, LIMITS)
        expected = activated_receipt(key_id, pricing)
        receipt = private_transfer(operation, {**payload, 'action': 'activate'},
                                   None, receipt_contract(expected))
        need(receipt == expected, 'private_activation_receipt_invalid')
        verify_limits(api, key_id, identities, LIMITS)
        owned_key(api, key_id, creation_run)
        return {**receipt, 'provider_daily_limit_rub': '95', 'provider_30_day_limit_rub': '2900',
                'automatic_price_renewal_installed': False}
    except BaseException:
        # Runtime may already have started, even if SSH timed out. Blocking the
        # provider is always the first recovery action; never rotate/delete key.
        blocked = block_provider(api, key_id, identities)
        raise ActivationError('activation_requires_inspected_recovery', provider_blocked=blocked) from None


def main():
    require_owner_wsl()
    need(os.environ.get('OWNER_AI_ACTIVATION_REVIEW') == GATE, 'reviewed_activation_gate_required')
    token = os.environ.get('TIMEWEB_CLOUD_TOKEN', '').strip()
    need(token and len(token) <= 8192 and not any(c.isspace() for c in token), 'protected_cloud_credential_required')
    receipt = activate(ActivationAPI(token), transport_secret, operation_source(),
        json.loads(os.environ['OWNER_AI_EXPECTED_BUDGET_SOURCES']),
        os.environ.get('OWNER_AI_STAGED_KEY_ID', ''), os.environ.get('OWNER_AI_CREATION_RUN_ID', ''))
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    try:
        main()
    except ActivationError as error:
        print(json.dumps({'status': 'activation_unconfirmed', 'reason': error.code,
                          'provider_zero_limits_verified': error.provider_blocked}), flush=True)
        raise SystemExit(1) from None
    except BaseException:
        print(json.dumps({'status': 'activation_unconfirmed', 'reason': 'private_activation_failed'}), flush=True)
        raise SystemExit(1) from None
