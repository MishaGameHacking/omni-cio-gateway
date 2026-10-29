"""One bounded synthetic Gateway request; never emits credentials or model text.

Cloud metadata is read-only. No portfolio, personal data, key creation, retries,
fallbacks or runtime changes. Executable checks run on the owner's laptop.
"""
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
import re
import sys
import urllib.error
import urllib.request

import provision_owner55_ai as provision

KEY_NAME = 'AI-Analyst-Full-Access'
GATEWAY = 'https://api.timeweb.ai/v1'
MESSAGES = [{'role': 'system', 'content': 'Return only a JSON object.'},
            {'role': 'user', 'content': 'Connectivity check: calculate 2+2. Return {"ok":true,"answer":4}.'}]
MAX_TOKENS = 128


class ProbeError(RuntimeError):
    pass


def need(value, code):
    if not value:
        raise ProbeError(code)


def selected_key(api):
    rows = provision.keys(api)
    matches = [row for row in rows if row.get('name') == KEY_NAME]
    need(len(matches) == 1, 'designated_key_not_unique')
    row = matches[0]
    provision.validate_created_metadata(row, KEY_NAME, row['id'])
    return row['id']


def limits(api, key_id):
    rows, complete = provision.complete_collection(
        api.request('GET', provision.KEYS + '/' + key_id + '/entity-limits'), 'ai_key_entity_limits')
    need(complete and all(isinstance(row, dict) for row in rows), 'limits_inventory_incomplete')
    result, identities = {}, set()
    for row in rows:
        identity = provision.uuid_text(row.get('id'))
        amount = provision.decimal_text(row.get('money_limit'))
        need(identity and identity not in identities and row.get('ai_key_id') == key_id
             and row.get('entity_id') == key_id and row.get('entity_type') == 'aikey'
             and row.get('model_id') is None and 'model_id' in row
             and row.get('limit_type') in {'day', 'month'} and amount is not None,
             'limits_binding_invalid')
        period = row['limit_type']
        need(period not in result, 'limits_period_duplicate')
        identities.add(identity)
        result[period] = {'id': identity, 'amount': amount}
    need('day' in result and Decimal('0') < Decimal(result['day']['amount']) <= Decimal('100'),
         'bounded_daily_limit_required')
    if 'month' in result:
        need(Decimal('0') < Decimal(result['month']['amount']) <= Decimal('3000'),
             'monthly_limit_outside_owner_budget')
    return result


class Gateway:
    def __init__(self, secret):
        provision.require_gateway_key(secret)
        self.secret = secret
        self.opener = urllib.request.build_opener(provision.NoRedirect())

    def request(self, path, body=None):
        need((path == '/models' and body is None) or (path == '/chat/completions' and body is not None),
             'gateway_endpoint_not_allowed')
        request = urllib.request.Request(GATEWAY + path, method='GET' if body is None else 'POST',
            data=None if body is None else json.dumps(body, allow_nan=False).encode(),
            headers={'Authorization': 'Bearer ' + self.secret, 'Accept': 'application/json',
                     'Content-Type': 'application/json'})
        try:
            with self.opener.open(request, timeout=45) as response:
                need(response.status == 200, 'gateway_status_invalid')
                raw = response.read(2 * 1024**2 + 1)
                need(len(raw) <= 2 * 1024**2, 'gateway_response_too_large')
                need(response.headers.get('x-timeweb-attempted-fallbacks', '0') == '0',
                     'unexpected_model_fallback')
            payload = json.loads(raw)
            need(isinstance(payload, dict), 'gateway_response_invalid')
            return payload
        except urllib.error.HTTPError as error:
            raise ProbeError({401:'gateway_authentication_rejected', 403:'gateway_access_denied',
                402:'gateway_balance_required', 422:'gateway_request_or_limit_rejected',
                429:'gateway_rate_limited'}.get(error.code, 'gateway_http_failure')) from None
        except (urllib.error.URLError, OSError):
            raise ProbeError('gateway_network_outcome_unknown') from None
        except (ValueError, TypeError):
            raise ProbeError('gateway_response_invalid') from None


def validate_completion(payload, pricing, bound):
    # Timeweb may return the provider-native name, rather than its routing prefix.
    need(payload.get('model') in {provision.MODEL, 'qwen3.5-flash'}, 'unexpected_response_model')
    choices = payload.get('choices')
    need(isinstance(choices, list) and len(choices) == 1 and isinstance(choices[0], dict)
         and choices[0].get('finish_reason') == 'stop', 'probe_completion_incomplete')
    message = choices[0].get('message')
    need(isinstance(message, dict) and isinstance(message.get('content'), str), 'probe_content_missing')
    try:
        parsed = json.loads(message['content'])
    except (ValueError, TypeError):
        raise ProbeError('probe_json_invalid') from None
    need(isinstance(parsed, dict) and set(parsed) == {'ok', 'answer'}
         and parsed['ok'] is True and type(parsed['answer']) is int and parsed['answer'] == 4,
         'probe_answer_invalid')
    usage = payload.get('usage')
    need(isinstance(usage, dict), 'probe_usage_missing')
    incoming, outgoing = usage.get('prompt_tokens'), usage.get('completion_tokens')
    need(type(incoming) is int and type(outgoing) is int and 0 <= incoming <= bound
         and 0 < outgoing <= MAX_TOKENS and usage.get('total_tokens') == incoming + outgoing,
         'probe_usage_invalid')
    cost = (Decimal(incoming) * Decimal(pricing['input_rub_per_million'])
            + Decimal(outgoing) * Decimal(pricing['output_rub_per_million'])) / 1000000
    return {'response_json_verified': True, 'arithmetic_verified': True,
            'prompt_tokens': incoming, 'completion_tokens': outgoing,
            'estimated_cost_rub': format(cost, 'f')}


def probe(api, gateway, report, *, now=None):
    finances = api.request('GET', provision.FINANCES).get('finances')
    need(isinstance(finances, dict) and finances.get('currency') == 'RUB', 'account_currency_not_rub')
    pricing = provision.pricing(api, datetime.now(timezone.utc) if now is None else now)
    key_id = selected_key(api)
    observed_limits = limits(api, key_id)
    report.update(key_id=key_id, provider_daily_cap_rub=observed_limits['day']['amount'],
                  provider_monthly_cap_rub=observed_limits.get('month', {}).get('amount'),
                  provider_fallback_disabled=True, pricing_verified=True)
    models = gateway.request('/models').get('data')
    need(isinstance(models, list) and any(isinstance(row, dict) and row.get('id') == provision.MODEL
         for row in models), 'required_model_unavailable')
    report['model_available'] = True
    bound = len(json.dumps(MESSAGES, ensure_ascii=False).encode()) + 4096
    ceiling = (Decimal(bound) * Decimal(pricing['input_rub_per_million'])
               + MAX_TOKENS * Decimal(pricing['output_rub_per_million'])) / 1000000
    need(ceiling <= 1, 'probe_cost_ceiling_above_one_ruble')
    report['estimated_request_ceiling_rub'] = format(ceiling, 'f')
    # Set before dispatch: timeouts must not be described as free or retried.
    report['generation_request_sent'] = True
    response = gateway.request('/chat/completions', {'model': provision.MODEL, 'messages': MESSAGES,
        'max_tokens': MAX_TOKENS, 'enable_thinking': False,
        'response_format': {'type': 'json_object'}, 'stream': False})
    report.update(validate_completion(response, pricing, bound))
    report.update(status='verified', authentication_verified=True)
    return report


def main():
    report = {'status':'not_verified', 'generation_request_sent':False,
              'configuration_changed':False, 'key_created':False,
              'brokerage_request_sent':False, 'automatic_retry':False}
    try:
        need(sys.platform == 'win32' and os.environ.get('COMPUTERNAME') == 'LAPTOP-NPSGA016',
             'owner_laptop_required')
        cloud = os.environ.get('TIMEWEB_CLOUD_TOKEN', '')
        secret = os.environ.get('TIMEWEB_AI_TOKEN', '')
        need(16 <= len(cloud) <= 8192 and not any(c.isspace() for c in cloud), 'cloud_credential_required')
        report = probe(provision.CloudAPI(cloud), Gateway(secret), report)
        code = 0
    except ProbeError as error:
        # ProbeError codes are fixed literals in this source, never provider text.
        report['reason'] = str(error)
        code = 1
    except BaseException:
        report['reason'] = 'probe_precondition_or_execution_failed'
        code = 1
    finally:
        os.environ.pop('TIMEWEB_AI_TOKEN', None)
        os.environ.pop('TIMEWEB_CLOUD_TOKEN', None)
    print('OWNER_AI_SUPPLIED_PROBE=' + json.dumps(report, sort_keys=True), flush=True)
    raise SystemExit(code)


if __name__ == '__main__':
    main()
