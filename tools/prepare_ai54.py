"""Owner-authorized, bounded AI setup. No broker credentials or trading requests.

Only the owner laptop may perform the synthetic paid model check. The temporary
transport payload contains a dedicated inference key, never a cloud-admin key.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import re
import sys
import urllib.request
import urllib.error

MODEL = 'dashscope/qwen3.5-flash'
NAME = 'analyst-ai-facts-54'
BASE = 'https://api.timeweb.cloud'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(method, url, token, body=None):
    if not (url.startswith(BASE + '/api/') or url == 'https://api.timeweb.ai/v1/chat/completions' or url == 'https://api.timeweb.ai/v1/models'):
        raise ValueError('unapproved_ai_endpoint')
    headers = {'Accept':'application/json','Content-Type':'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(url, method=method, headers=headers,
                                 data=None if body is None else json.dumps(body).encode())
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=60) as response:
            raw = response.read(2097153)
            if len(raw) > 2097152:
                raise ValueError('response_too_large')
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        # Response bodies may contain sensitive provider metadata; do not log.
        raise RuntimeError('ai_http_' + str(error.code)) from None


def prices(data):
    rows = [row for row in data.get('models', []) if row.get('model_name') == MODEL]
    if len(rows) != 1 or rows[0].get('is_stopped') or rows[0].get('is_deprecated'):
        raise ValueError('selected_model_unavailable')
    row = rows[0]
    values = row.get('parameter_values') or {}
    inp, out = Decimal(str(values['cost_in'])) * 1000000, Decimal(str(values['cost_out'])) * 1000000
    if not inp.is_finite() or not out.is_finite() or not 0 < inp <= 14 or not 0 < out <= 52:
        raise ValueError('price_exceeds_approved_ceiling')
    return {'model':MODEL,'model_id':row['id'],'input':str(inp),'output':str(out)}


def validate_key(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_./+:-]{16,512}', value):
        raise ValueError('invalid_inference_key')
    return value


def setup(api):
    catalog = prices(api('GET', '/api/v3/cloud-ai/models'))
    existing = api('GET', '/api/v1/cloud-ai/ai-keys').get('ai_keys', [])
    if any(key.get('name') == NAME for key in existing):
        raise ValueError('dedicated_key_exists_use_staged_runtime_copy')
    created = api('POST', '/api/v1/cloud-ai/ai-keys', {'name':NAME,'project_id':2941515,
                  'description':'Portfolio fact explanations; 2 RUB/day, 30 RUB/30 days; no fallback',
                  'expire':None,'fallback_models':[]})
    key_id = created['ai_key']['id']
    try:
        token = validate_key(created['key'])
        for period, amount in [('day', '2'), ('month', '30')]:
            api('POST', '/api/v1/cloud-ai/ai-keys/' + str(key_id) + '/entity-limits',
                {'entity_type':'aikey','limit_type':period,'money_limit':amount})
        limits = api('GET', '/api/v1/cloud-ai/ai-keys/' + str(key_id) + '/entity-limits')['ai_key_entity_limits']
        for period, amount in [('day', '2'), ('month', '30')]:
            matching = [row for row in limits if row.get('limit_type') == period and row.get('model_id') is None]
            if len(matching) != 1 or Decimal(str(matching[0].get('money_limit'))) != Decimal(amount):
                raise ValueError('provider_limit_not_verified')
    except BaseException:
        api('DELETE', '/api/v1/cloud-ai/ai-keys/' + str(key_id))
        raise
    return {**catalog,'key_id':key_id,'token':token,'checked_at':datetime.now(timezone.utc).isoformat(),
            'daily_rub':'2','monthly_rub':'30','fallback_models':[]}


def smoke(payload):
    request_body = {'model':MODEL,'stream':False,'max_tokens':512,'enable_thinking':False,
        'response_format':{'type':'json_object'},'messages':[
            {'role':'system','content':'Use only supplied facts. Return one JSON object with currency, age, trade_executed, income, summary. Unknown values must be null. No investment promises. Explain in one plain Russian sentence.'},
            {'role':'user','content':'Synthetic test: current balance 1000 RUB, deposited 1000 RUB. No earlier valuation. Age not supplied. No order sent. Report currency RUB, age null, trade_executed false, income null.'}]}
    result = request('POST','https://api.timeweb.ai/v1/chat/completions',payload['token'],request_body)
    choice = result['choices'][0]
    content = json.loads(choice['message']['content'])
    if (choice['finish_reason'] != 'stop' or content.get('currency') != 'RUB' or content.get('age') is not None
            or content.get('trade_executed') is not False or content.get('income') is not None
            or not isinstance(content.get('summary'),str) or not 1 <= len(content['summary']) <= 1000):
        raise ValueError('synthetic_fact_check_failed')
    usage = result['usage']
    if any(type(usage.get(k)) is not int or usage[k] < 0 for k in ('prompt_tokens','completion_tokens','total_tokens')):
        raise ValueError('usage_not_verified')
    estimated = (Decimal(usage['prompt_tokens']) * Decimal(payload['input']) + Decimal(usage['completion_tokens']) * Decimal(payload['output'])) / 1000000
    return {'model':result.get('model'),'usage':usage,'estimated_rub':str(estimated),'synthetic_facts_passed':True}


def main():
    if os.environ.get('COMPUTERNAME') != 'LAPTOP-NPSGA016':
        raise RuntimeError('owner_laptop_required')
    admin = os.environ['TIMEWEB_CLOUD_TOKEN']
    payload = setup(lambda method,path,body=None:request(method,BASE+path,admin,body))
    # A failed model check must not become an active runtime route.
    try:
        receipt = smoke(payload)
        if receipt['model'] != MODEL:
            raise ValueError('model_identity_differs_from_catalogue')
    except BaseException:
        request('DELETE',BASE+'/api/v1/cloud-ai/ai-keys/'+str(payload['key_id']),admin)
        raise
    payload['smoke'] = receipt
    stage = Path('deploy/plan-20261027');stage.mkdir(parents=True, exist_ok=True)
    (stage/'payload.json').write_text(json.dumps(payload), encoding='utf-8')
    (stage/'operation.py').write_bytes(Path('deploy/stage_ai54.py').read_bytes())
    Path('plan-reports').mkdir(exist_ok=True)
    Path('plan-reports/ai54-smoke.json').write_text(json.dumps(receipt), encoding='utf-8')
    print('AI54_SMOKE='+json.dumps(receipt),flush=True)


if __name__ == '__main__':
    main()
