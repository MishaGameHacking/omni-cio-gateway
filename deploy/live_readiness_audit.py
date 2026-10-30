"""Bounded reads of the existing broker connection and public model catalogue.

No application import, model inference, order submission, cancellation or change
to service configuration. Private broker responses remain on the existing host.
"""
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import sqlite3
import ssl
import sys
import time
import urllib.error
import urllib.request

SOURCE = 'af95e8de8cfd50970d712483b8c17e866f7239c9'
ROOT = Path('/opt/analyst-ai/backend')
DB = Path('/var/lib/analyst-ai/backend.db')
CONFIG = Path('/etc/analyst-ai/backend.env')
PRIVATE = Path('/var/lib/analyst-ai')
CA_SHA = 'd26d2d0231b7c39f92cc738512ba54103519e4405d68b5bd703e9788ca8ecf31'
INSTALLED = {
    'ai_guarded_client.py': 'd65872bcf5d90f34e852da3155f0b9e5852a713ecfb4e55403505143381a0243',
    'investment_chat_policy.py': '60d6a4f7ca5d8047eb5fa0b6963cf7ae79f31df624f3341f0c59b1d92a9604b8',
    'order_lifecycle.py': 'e5560f86c27179be3240e7f37615e9b3c0b90f0ef31d9a0adaabc2bffd0b07ca',
    'portfolio_details.py': '1dafbf959eb4ffe8fc23a304d3047fa4f95e6705459a733196a5e64b06d43ea1',
    'volume_chat.py': '8abeb8a8fba42e5319ec173f401f29bca778be61aad5d4428b97e34f3d4b167b',
    'volume_jobs.py': '1ba356d49a4a09f87402ecfb5d959bd9fc4785a4f6ddf5e3cba099f1462d7e6b',
}
BROKER = 'https://invest-public-api.tbank.ru/rest/tinkoff.public.invest.api.contract.v1.'
METHODS = {
    'accounts': 'UsersService/GetAccounts',
    'portfolio': 'OperationsService/GetPortfolio',
    'positions': 'OperationsService/GetPositions',
    'orders': 'OrdersService/GetOrders',
}
CATALOG = 'https://api.timeweb.cloud/api/v3/cloud-ai/models'
MODEL_IDS = frozenset({'gpt-6-luna', 'gpt-6.1-sol', 'gpt-6.1-terra', 'gpt-6-astra'})
MANDATE_FIELDS = frozenset({'asset_mode', 'base_currency', 'account_id', 'loss_capacity_percent',
    'bond_target_percent', 'share_target_percent', 'minimum_rating_level',
    'max_discretionary_turnover_percent', 'turnover_window_days', 'max_trade_cost_percent',
    'rebalance_cooldown_days', 'reinvest_coupons', 'reinvest_dividends', 'allowed_sessions'})


class AuditError(Exception):
    """Only a locally defined code is safe to print."""


def need(value, code):
    if not value:
        raise AuditError(code)


def regular(path, limit):
    need(path.is_file() and not path.is_symlink() and path.resolve(strict=True) == path
         and path.stat().st_nlink == 1 and path.stat().st_size <= limit, 'unsafe_file')
    return path.read_bytes()


def baseline():
    for name, expected in INSTALLED.items():
        need(hashlib.sha256(regular(ROOT / name, 1_000_000)).hexdigest() == expected, 'runtime_source_changed')
    app = regular(ROOT / 'app.py', 1_000_000)
    blob = hashlib.sha1(b'blob ' + str(len(app)).encode() + b'\0' + app).hexdigest()
    need(blob == 'a68eef110e6efbfb521316ec84244b46801c997a', 'runtime_source_changed')


def config_values(raw):
    allowed = {'FERNET_KEY', 'DATABASE_PATH', 'AI_MODEL_FAST', 'AI_MODEL_STANDARD', 'AI_MODEL_PREMIUM'}
    result = {}
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        key, separator, value = line.partition('=')
        key = key.strip()
        if key not in allowed:
            continue
        need(separator and key not in result, 'runtime_configuration_invalid')
        words = shlex.split(value, comments=False, posix=True)
        need(len(words) == 1, 'runtime_configuration_invalid')
        result[key] = words[0]
    need(result.get('DATABASE_PATH', str(DB)) == str(DB) and result.get('FERNET_KEY'), 'runtime_configuration_invalid')
    return result


def owner_state():
    need(DB.is_file() and not DB.is_symlink() and DB.resolve(strict=True) == DB, 'database_path_invalid')
    with closing(sqlite3.connect(DB.as_uri() + '?mode=ro', uri=True, timeout=3)) as db:
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        rows = db.execute('''SELECT u.id,u.tinvest_token_encrypted FROM users u
            JOIN installation_owner o ON o.telegram_sub=u.telegram_sub WHERE o.singleton=1''').fetchall()
        need(len(rows) == 1 and isinstance(rows[0][1], bytes) and rows[0][1], 'broker_binding_unavailable')
        user, cipher = rows[0]
        strategy = db.execute('SELECT config_json FROM workspace_strategy_versions WHERE user_id=? ORDER BY version DESC LIMIT 1', (user,)).fetchone()
        stamp = db.execute('SELECT MAX(created_at) FROM workspace_snapshots WHERE user_id=?', (user,)).fetchone()[0]
        body = json.loads(strategy[0]) if strategy else {}
        need(isinstance(body, dict), 'strategy_shape_invalid')
        db.rollback()
    return user, cipher, body, stamp


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_json(opener, request, timeout):
    try:
        with opener.open(request, timeout=timeout) as response:
            need(response.status == 200, 'unexpected_http_status')
            raw = response.read(4 * 1024 * 1024 + 1)
            need(len(raw) <= 4 * 1024 * 1024, 'response_size_exceeded')
        result = json.loads(raw, parse_float=Decimal)
        need(isinstance(result, dict), 'response_shape_invalid')
        return result
    except urllib.error.HTTPError as error:
        raise AuditError({401: 'authentication_rejected', 403: 'permission_denied',
                          429: 'rate_limited'}.get(error.code, 'broker_or_catalog_http_error')) from None
    except (urllib.error.URLError, OSError):
        raise AuditError('network_unavailable') from None
    except (ValueError, TypeError):
        raise AuditError('response_json_invalid') from None


class BrokerReader:
    def __init__(self, token, context, *, opener=None):
        self._token = token
        self.opener = opener or urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=context))
        self.deadline = time.monotonic() + 150

    def read(self, method, body):
        need(method in METHODS, 'broker_method_not_readonly')
        if method == 'accounts':
            need(body == {'status': 'ACCOUNT_STATUS_OPEN'}, 'broker_request_invalid')
        else:
            need(isinstance(body, dict) and set(body) == {'accountId'}
                 and isinstance(body['accountId'], str)
                 and re.fullmatch('[A-Za-z0-9_-]{1,128}', body['accountId']), 'broker_request_invalid')
        remaining = self.deadline - time.monotonic()
        need(remaining > 0, 'broker_deadline_exceeded')
        request = urllib.request.Request(BROKER + METHODS[method], method='POST',
            data=json.dumps(body).encode(), headers={'Authorization': 'Bearer ' + self._token,
            'Content-Type': 'application/json', 'Accept': 'application/json'})
        return request_json(self.opener, request, min(8, remaining))


def inspect_broker(reader):
    payload = reader.read('accounts', {'status': 'ACCOUNT_STATUS_OPEN'})
    rows = payload.get('accounts')
    need(isinstance(rows, list) and 0 < len(rows) <= 5, 'account_collection_invalid')
    identifiers = set()
    private, checks, full = [], [], 0
    for row in rows:
        need(isinstance(row, dict) and row.get('status') == 'ACCOUNT_STATUS_OPEN', 'account_status_unverified')
        account = row.get('id')
        need(isinstance(account, str) and re.fullmatch('[A-Za-z0-9_-]{1,128}', account)
             and account not in identifiers, 'account_identity_invalid')
        identifiers.add(account)
        access = row.get('accessLevel')
        need(access in {'ACCOUNT_ACCESS_LEVEL_FULL_ACCESS', 'ACCOUNT_ACCESS_LEVEL_READ_ONLY'}, 'account_access_unverified')
        full += access == 'ACCOUNT_ACCESS_LEVEL_FULL_ACCESS'
        response = {}
        for method in ('portfolio', 'positions', 'orders'):
            value = reader.read(method, {'accountId': account})
            need('accountId' not in value or value['accountId'] == account, 'broker_response_account_mismatch')
            field = 'orders' if method == 'orders' else 'positions' if method == 'portfolio' else 'money'
            # Protobuf JSON omits empty repeated fields. An absent field is not
            # a synthetic position or quote; retain the original private response.
            need(isinstance(value.get(field, []), list), 'broker_response_collection_invalid')
            response[method] = value
        private.append({'account': row, 'responses': response})
        checks.append({'portfolio_read': True, 'positions_read': True, 'orders_read': True})
    return {'account_count': len(rows), 'full_access_accounts': full, 'checks': checks,
            'endpoint': 'production', 'read_methods_only': True, 'orders_sent': 0,
            'execution_eligibility_verified': False}, private


def safe_routes(config):
    result = {}
    for tier in ('FAST', 'STANDARD', 'PREMIUM'):
        value = config.get('AI_MODEL_' + tier, '')
        result[tier.lower()] = value if re.fullmatch(r'(?:openai/)?gpt-6(?:\.1)?-(?:luna|sol|terra|astra)|dashscope/qwen3\.5-flash', value) else 'other_or_unconfigured'
    return result


def broker_context():
    raw = regular(ROOT / 'certs/russian_trusted_root_ca.pem', 100_000).decode('ascii')
    der = ssl.PEM_cert_to_DER_cert(raw)
    need(hashlib.sha256(der).hexdigest() == CA_SHA, 'broker_ca_identity_changed')
    context = ssl.create_default_context()
    context.load_verify_locations(cadata=raw)
    return context


def save_private(run, data):
    need(re.fullmatch('[1-9][0-9]{7,19}', run), 'audit_run_invalid')
    need(PRIVATE.resolve(strict=True) == PRIVATE and not PRIVATE.stat().st_mode & 0o022, 'private_directory_invalid')
    path = PRIVATE / ('live-readiness-audit-' + run + '.json')
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'w') as output:
        json.dump(data, output, ensure_ascii=False, default=str)
        output.flush()
        os.fsync(output.fileno())


def audit_runtime(run):
    from cryptography.fernet import Fernet, InvalidToken
    need(os.getuid() == 0, 'runtime_identity_invalid')
    need(re.fullmatch('[1-9][0-9]{7,19}', run), 'audit_run_invalid')
    baseline()
    config = config_values(regular(CONFIG, 256_000).decode())
    user, cipher, strategy, stamp = owner_state()
    try:
        token = Fernet(config['FERNET_KEY'].encode()).decrypt(cipher).decode()
    except (ValueError, UnicodeError, InvalidToken):
        raise AuditError('stored_broker_token_unreadable') from None
    need(20 <= len(token) <= 2048 and all(32 < ord(char) < 127 for char in token), 'stored_broker_token_invalid')
    report, private = inspect_broker(BrokerReader(token, broker_context()))
    current = owner_state()
    need(current[0] == user and current[1] == cipher, 'broker_binding_changed')
    baseline()
    mandate = strategy.get('mandate')
    missing = sorted(MANDATE_FIELDS - set(mandate)) if isinstance(mandate, dict) else sorted(MANDATE_FIELDS)
    report.update(schema=1, server_id=9417611, status='observed', source_commit=SOURCE,
        observed_at=datetime.now(timezone.utc).isoformat(), strategy_present=bool(strategy),
        mandate_missing_fields=missing, configured_models=safe_routes(config),
        stored_snapshot_at=(datetime.fromtimestamp(stamp, timezone.utc).isoformat() if type(stamp) is int else None),
        private_report_saved=True, application_database_written=False, model_inference_called=False,
        trading_configuration_changed=False, financial_values_published=False)
    save_private(run, {'report': report, 'broker': private})
    return report


def decimal_rate(value, *, allow_zero=False):
    need(type(value) in (str, int, Decimal) and len(str(value)) <= 64, 'catalog_price_invalid')
    try:
        number = Decimal(value)
        need(number.is_finite() and (number >= 0 if allow_zero else number > 0)
             and number <= Decimal('1000000'), 'catalog_price_invalid')
    except InvalidOperation:
        raise AuditError('catalog_price_invalid') from None
    return number


def model_catalogue(payload):
    rows, meta = payload.get('models'), payload.get('meta')
    need(isinstance(rows, list) and len(rows) <= 10000 and isinstance(meta, dict)
         and type(meta.get('total')) is int and meta['total'] == len(rows), 'catalog_incomplete')
    result = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        identifier = row.get('model_name')
        if not isinstance(identifier, str) or identifier.removeprefix('openai/') not in MODEL_IDS:
            continue
        values = row.get('parameter_values')
        item = {'model': identifier, 'catalog_id': row.get('id') if type(row.get('id')) is int else None,
                'active': row.get('is_stopped') is False and row.get('is_deprecated') is False,
                'state_known': type(row.get('is_stopped')) is bool and type(row.get('is_deprecated')) is bool,
                'price_verified': False}
        try:
            need(isinstance(values, dict) and values.get('pricing_unit', 'token') == 'token', 'catalog_price_invalid')
            inputs, outputs = [decimal_rate(values.get('cost_in'))], [decimal_rate(values.get('cost_out'))]
            for name in ('cost_cache_read', 'cost_cache_write'):
                if name in values:
                    inputs.append(decimal_rate(values[name], allow_zero=True))
            tiers = row.get('price_tiers')
            need(isinstance(tiers, list) and len(tiers) <= 32, 'catalog_price_invalid')
            previous = -1
            for tier in tiers:
                need(isinstance(tier, dict) and type(tier.get('above_context_tokens')) is int
                     and tier['above_context_tokens'] > previous, 'catalog_price_invalid')
                previous = tier['above_context_tokens']
                inputs.append(decimal_rate(tier.get('cost_in')))
                outputs.append(decimal_rate(tier.get('cost_out')))
            item.update(price_verified=True, input_rub_per_million=str(max(inputs) * 1_000_000),
                        output_rub_per_million=str(max(outputs) * 1_000_000))
        except AuditError:
            pass
        if isinstance(values, dict):
            for key in ('context_window', 'max_output_tokens'):
                value = values.get(key)
                item[key] = value if type(value) is int and 0 < value <= 10_000_000 else None
        result.append(item)
    return {'schema': 1, 'catalog_complete': True, 'models': result,
            'inference_verified': False, 'configuration_changed': False,
            'observed_at': datetime.now(timezone.utc).isoformat()}


def read_catalogue(token):
    request = urllib.request.Request(CATALOG, method='GET',
        headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/json'})
    return model_catalogue(request_json(urllib.request.build_opener(NoRedirect()), request, 20))


if __name__ == '__main__':
    try:
        print(json.dumps(audit_runtime(sys.stdin.read(64).strip())), flush=True)
    except AuditError as error:
        print(json.dumps({'status': 'failed', 'code': str(error), 'orders_sent': 0}), flush=True)
        sys.exit(1)
    except Exception:
        print(json.dumps({'status': 'failed', 'code': 'audit_failed', 'orders_sent': 0}), flush=True)
        sys.exit(1)
