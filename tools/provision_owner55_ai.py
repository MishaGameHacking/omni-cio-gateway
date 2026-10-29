"""Create one isolated Timeweb AI key, block it, and privately stage it.

This administrative operation never activates paid inference or touches existing
AI keys. Root review and an explicit workflow gate are required before calling
main. A creation timeout is not retried. An indeterminate SSH delivery retains
the new key at zero provider limits for inspected recovery.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request

from inspect_owner55_ai import (BASE, FINANCES, KEYS, MODELS, MODEL, DEDICATED_PREFIX,
    MAX_BYTES, MASKED, NoRedirect, complete_collection, model_summary, uuid_text, decimal_text)
from owner_ai_private_transport import (transport_secret, PrivateTransportError, require_owner_wsl,
                                       SAFE_TRANSPORT_FAILURE_CODES)

PROVISION_GATE = 'create-disabled-owner55-key-after-review'
PREFLIGHT_ONLY_GATE = 'inspect-owner55-configuration-after-review'
PREFLIGHT_REASONS = {'ready', 'root_transport_required', 'preflight_secret_not_allowed',
    'incomplete_budget_source_proof', 'invalid_source_proof', 'budget_source_not_the_reviewed_version',
    'unsafe_configuration_or_source_file', 'unsafe_environment_permissions', 'unsafe_configuration_file',
    'configuration_changed_while_reading', 'configuration_too_large', 'unsupported_environment_syntax',
    'duplicate_environment_variable', 'unsupported_environment_value',
    'existing_inference_key_must_not_be_replaced', 'custom_route_catalog_requires_separate_review',
    'required_file_missing', 'required_file_access_denied', 'deployment_lock_busy',
    'configuration_encoding_invalid', 'configuration_format_invalid', 'preflight_not_verified'}
PREFLIGHT_CONTRACT = {'status': {'ready', 'not_ready'}, 'reason': PREFLIGHT_REASONS,
    'server_id': int, 'existing_key_absent': bool,
    'budget_sources_verified': bool, 'configuration_changed': bool}


class ProvisionError(RuntimeError):
    def __init__(self, code, *, key_id=None, retained=False, failure_code=None,
                 transport_code=None, transport_operation_started=None, temporary_ssh_key_removed=None):
        super().__init__(code)
        self.code, self.key_id, self.retained = code, key_id, retained
        self.failure_code = failure_code
        self.transport_code = transport_code
        self.transport_operation_started = transport_operation_started
        self.temporary_ssh_key_removed = temporary_ssh_key_removed


def preflight_transport_error(error):
    candidate = error.code
    code = candidate if isinstance(candidate, str) and candidate in SAFE_TRANSPORT_FAILURE_CODES else 'private_preflight_failed'
    started = error.operation_started if type(error.operation_started) is bool else None
    removed = error.temporary_key_removed if type(error.temporary_key_removed) is bool else None
    return ProvisionError('private_preflight_requires_inspection', failure_code='private_delivery_failed',
                          transport_code=code, transport_operation_started=started,
                          temporary_ssh_key_removed=removed)


def safe_failure_code(error):
    permitted = {'new_key_metadata_mismatch', 'new_gateway_key_masked', 'new_gateway_key_invalid',
                 'zero_limits_incomplete', 'zero_limits_wrong_periods',
                 'zero_limits_not_enforced_for_all_models', 'new_key_not_visible_after_creation',
                 'remote_staging_receipt_mismatch'}
    if isinstance(error, ProvisionError):
        if error.code in permitted:
            return error.code
        if error.code.startswith('cloud_'):
            return 'cloud_request_failed'
    if isinstance(error, PrivateTransportError):
        return 'private_delivery_failed'
    return 'unclassified_failure'


def need(condition, code):
    if not condition:
        raise ProvisionError(code)


def require_gateway_key(secret):
    # Timeweb uses opaque HTTP-safe credentials, with no documented prefix,
    # minimum length or OAuth alphabet. Preserve the exact supplied bytes.
    need(secret != MASKED, 'new_gateway_key_masked')
    need(isinstance(secret, str) and 1 <= len(secret) <= 8192
         and all(33 <= ord(c) <= 126 for c in secret), 'new_gateway_key_invalid')


def permitted_write(method, path):
    if method == 'POST' and path == KEYS:
        return True
    suffix = path.removeprefix(KEYS + '/')
    if method == 'DELETE':
        return path.startswith(KEYS + '/') and uuid_text(suffix) is not None
    if method == 'POST' and suffix.endswith('/entity-limits'):
        return path.startswith(KEYS + '/') and uuid_text(suffix.removesuffix('/entity-limits')) is not None
    return False


class CloudAPI:
    def __init__(self, token):
        self._token = token
        self._opener = urllib.request.build_opener(NoRedirect())

    def request(self, method, path, body=None):
        from inspect_owner55_ai import permitted_path
        need((method == 'GET' and permitted_path(path)) or permitted_write(method, path), 'endpoint_not_allowlisted')
        request = urllib.request.Request(BASE + path, method=method,
            data=None if body is None else json.dumps(body, allow_nan=False).encode(),
            headers={'Authorization': 'Bearer ' + self._token, 'Accept': 'application/json',
                     'Content-Type': 'application/json'})
        try:
            with self._opener.open(request, timeout=30) as response:
                expected = {'GET': 200, 'POST': 201, 'DELETE': 204}[method]
                need(response.status == expected, 'unexpected_http_status')
                raw = response.read(MAX_BYTES + 1)
                need(len(raw) <= MAX_BYTES, 'response_too_large')
            value = json.loads(raw, parse_float=Decimal) if raw else {}
            need(isinstance(value, dict), 'invalid_response_shape')
            return value
        except urllib.error.HTTPError as error:
            raise ProvisionError('cloud_http_' + str(error.code)) from None
        except (urllib.error.URLError, OSError):
            # No automatic retry, especially for non-idempotent key creation.
            raise ProvisionError('cloud_outcome_unknown') from None
        except (ValueError, TypeError):
            raise ProvisionError('cloud_response_invalid') from None


def keys(api):
    rows, complete = complete_collection(api.request('GET', KEYS), 'ai_keys')
    need(complete and all(isinstance(row, dict) for row in rows), 'key_inventory_incomplete')
    normalized = []
    identities = set()
    for row in rows:
        identity = uuid_text(row.get('id'))
        need(identity is not None and identity not in identities
             and isinstance(row.get('name'), str) and bool(row['name']), 'key_inventory_identity_invalid')
        identities.add(identity)
        normalized.append({**row, 'id': identity})
    return normalized


def pricing(api, now):
    report = model_summary(api.request('GET', MODELS))
    need(report.get('availability_verified') is True and report.get('pricing_verified') is True,
         'current_model_prices_not_verified')
    need(type(report.get('context_window')) is int and report['context_window'] >= 118096
         and type(report.get('max_output_tokens')) is int and report['max_output_tokens'] >= 4000,
         'model_context_does_not_fit_adapter_limits')
    # params_info covers agent configuration, not every Gateway request field.
    # Gateway AiGatewayChatCompletionRequest explicitly supports response_format;
    # Alibaba documents JSON mode for Qwen3.5-Flash with thinking disabled.
    need({'max_tokens', 'enable_thinking'}.issubset(
         report.get('documented_generation_parameters', [])),
         'adapter_generation_parameters_unverified')
    return {'input_rub_per_million': report['maximum_input_rub_per_million'],
            'output_rub_per_million': report['maximum_output_rub_per_million'],
            'valid_until': (now + timedelta(days=1)).isoformat()}


def validate_created_metadata(row, name, key_id):
    need(isinstance(row, dict) and row.get('id') == key_id and row.get('name') == name
         and row.get('entity_type') == 'aikey' and row.get('is_readonly') is False
         and row.get('project_id') == 2941515 and row.get('fallback_models') == []
         and 'expires_at' in row and row['expires_at'] is None
         and 'entity_id' in row and row['entity_id'] is None,
         'new_key_metadata_mismatch')


def validate_limits(payload, key_id):
    rows, complete = complete_collection(payload, 'ai_key_entity_limits')
    need(complete and len(rows) == 2 and all(isinstance(row, dict) for row in rows), 'zero_limits_incomplete')
    need({row.get('limit_type') for row in rows} == {'day', 'month'}, 'zero_limits_wrong_periods')
    for row in rows:
        amount = decimal_text(row.get('money_limit'))
        need(uuid_text(row.get('id')) is not None and row.get('ai_key_id') == key_id
             and row.get('entity_id') == key_id and row.get('entity_type') == 'aikey'
             and 'model_id' in row and row['model_id'] is None
             and amount is not None and Decimal(amount) == 0, 'zero_limits_not_enforced_for_all_models')


def staged_contract(key_id):
    return {'status': {'staged_disabled'}, 'server_id': int, 'key_id': {key_id}, 'model': {MODEL},
        'daily_cap_rub': {'0'}, 'monthly_cap_rub': {'0'}, 'existing_key_replaced': bool,
        'service_restarted': bool, 'inference_called': bool}


def require_ready(receipt):
    need(receipt == {'status': 'ready', 'reason': 'ready', 'server_id': 9417611, 'existing_key_absent': True,
                    'budget_sources_verified': True, 'configuration_changed': False}, 'remote_preflight_failed')


def inspect_preflight(api, private_transfer, operation, source_sha256, *, now=None):
    finances = api.request('GET', FINANCES).get('finances')
    need(isinstance(finances, dict) and finances.get('currency') == 'RUB', 'account_currency_not_rub')
    pricing(api, datetime.now(timezone.utc) if now is None else now)
    inventory = keys(api)
    need(not any(row['name'].startswith(DEDICATED_PREFIX) for row in inventory),
         'existing_dedicated_key_requires_inspection')
    try:
        receipt = private_transfer(operation, {'action': 'preflight', 'source_sha256': source_sha256},
                                   None, PREFLIGHT_CONTRACT)
    except PrivateTransportError as error:
        raise preflight_transport_error(error) from None
    # The private transport enforces the finite reason/type contract. Recheck
    # meaning here so an inconsistent receipt cannot imply successful readiness.
    need(set(receipt) == set(PREFLIGHT_CONTRACT) and receipt.get('server_id') == 9417611
         and receipt.get('status') in {'ready', 'not_ready'} and receipt.get('reason') in PREFLIGHT_REASONS
         and receipt.get('configuration_changed') is False
         and type(receipt.get('existing_key_absent')) is bool
         and type(receipt.get('budget_sources_verified')) is bool, 'remote_preflight_failed')
    if receipt['status'] == 'ready':
        require_ready(receipt)
    else:
        need(receipt['reason'] != 'ready', 'remote_preflight_failed')
    return {**receipt, 'read_only_preflight': True, 'ai_key_created': False,
            'ai_limits_changed': False, 'inference_called': False}


def provision(api, private_transfer, operation, source_sha256, name, *, now=None):
    need(re.fullmatch(re.escape(DEDICATED_PREFIX) + r'[A-Za-z0-9_-]{1,64}', name), 'invalid_new_key_name')
    now = datetime.now(timezone.utc) if now is None else now
    finances = api.request('GET', FINANCES).get('finances')
    need(isinstance(finances, dict) and finances.get('currency') == 'RUB', 'account_currency_not_rub')
    verified_pricing = pricing(api, now)
    before = keys(api)
    need(not any(isinstance(row.get('name'), str) and row['name'].startswith(DEDICATED_PREFIX) for row in before),
         'existing_dedicated_key_requires_inspection')
    try:
        receipt = private_transfer(operation, {'action': 'preflight', 'source_sha256': source_sha256},
                                   None, PREFLIGHT_CONTRACT)
    except PrivateTransportError as error:
        # This is before POST /ai-keys. Preserve only fixed diagnostic codes and
        # cleanup booleans, never provider/SSH text, credentials or raw receipts.
        raise preflight_transport_error(error) from None
    require_ready(receipt)
    # Repeat the inventory immediately before creation. Workflow concurrency
    # must serialize this installer; no pre-existing key is ever regenerated.
    need(keys(api) == before, 'key_inventory_changed_before_creation')
    try:
        created = api.request('POST', KEYS, {'name': name, 'project_id': 2941515,
            'description': 'Analyst AI owner55; zero limits until reviewed activation',
            'expire': None, 'fallback_models': []})
    except BaseException:
        # A failed or unreadable response cannot establish whether creation
        # committed. Do not retry or claim that no new billable key exists.
        raise ProvisionError('key_creation_requires_inspected_recovery', retained=None) from None
    metadata = created.get('ai_key')
    key_id = uuid_text(metadata.get('id')) if isinstance(metadata, dict) else None
    if key_id is None or key_id in {row['id'] for row in before}:
        raise ProvisionError('new_key_identity_unknown', retained=None)
    remote_started = False
    try:
        validate_created_metadata(metadata, name, key_id)
        secret = created.get('key')
        require_gateway_key(secret)
        path = KEYS + '/' + key_id + '/entity-limits'
        for period in ('day', 'month'):
            api.request('POST', path, {'entity_type': 'aikey', 'limit_type': period, 'money_limit': 0})
        validate_limits(api.request('GET', path), key_id)
        after = [row for row in keys(api) if row.get('id') == key_id]
        need(len(after) == 1, 'new_key_not_visible_after_creation')
        validate_created_metadata(after[0], name, key_id)
        remote_started = True
        receipt = private_transfer(operation, {'action': 'stage_disabled', 'key_id': key_id,
            'model': MODEL, 'pricing': verified_pricing, 'source_sha256': source_sha256},
            secret, staged_contract(key_id))
        need(receipt == {'status': 'staged_disabled', 'server_id': 9417611, 'key_id': key_id,
                        'model': MODEL, 'daily_cap_rub': '0', 'monthly_cap_rub': '0',
                        'existing_key_replaced': False, 'service_restarted': False, 'inference_called': False},
             'remote_staging_receipt_mismatch')
        validate_limits(api.request('GET', path), key_id)
        return {**receipt, 'provider_daily_limit_rub': '0', 'provider_30_day_limit_rub': '0',
                'provider_fallback_disabled': True, 'runtime_activation_performed': False,
                'account_currency_rub_confirmed': True}
    except BaseException as error:
        failure_code = safe_failure_code(error)
        if isinstance(error, PrivateTransportError):
            remote_started = error.operation_started
        if not remote_started:
            # The secret has never reached any consumer: deleting exactly the
            # newly returned ID cannot rotate or break another application's key.
            try:
                api.request('DELETE', KEYS + '/' + key_id)
                need(not any(row.get('id') == key_id for row in keys(api)), 'unused_new_key_deletion_unverified')
            except BaseException:
                raise ProvisionError('new_unused_key_cleanup_failed', key_id=key_id, retained=True,
                                     failure_code=failure_code) from None
            raise ProvisionError('new_unused_key_removed_after_failure', key_id=key_id,
                                 failure_code=failure_code) from None
        raise ProvisionError('private_delivery_requires_inspected_recovery', key_id=key_id, retained=True,
                             failure_code=failure_code) from None


def main():
    require_owner_wsl()
    preflight_only = os.environ.get('OWNER_AI_ACTION') == 'preflight_only'
    gate = PREFLIGHT_ONLY_GATE if preflight_only else PROVISION_GATE
    need(os.environ.get('OWNER_AI_PROVISION_REVIEW') == gate, 'reviewed_provisioning_gate_required')
    token = os.environ.get('TIMEWEB_CLOUD_TOKEN', '').strip()
    need(token and len(token) <= 8192 and not any(c.isspace() for c in token), 'protected_cloud_credential_required')
    run_id = os.environ.get('GITHUB_RUN_ID', '')
    need(re.fullmatch('[0-9]{8,20}', run_id), 'invalid_run_identity')
    source_sha256 = json.loads(os.environ['OWNER_AI_EXPECTED_BUDGET_SOURCES'])
    if preflight_only:
        receipt = inspect_preflight(CloudAPI(token), transport_secret,
            Path('deploy/stage_owner55_ai.py').read_text(), source_sha256)
        print(json.dumps(receipt), flush=True)
        return
    receipt = provision(CloudAPI(token), transport_secret,
        Path('deploy/stage_owner55_ai.py').read_text(), source_sha256, DEDICATED_PREFIX + run_id)
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    try:
        main()
    except ProvisionError as error:
        print(json.dumps({'status': 'not_activated', 'reason': error.code,
                          'new_key_id': error.key_id, 'new_key_retained': error.retained,
                          'failure_code': error.failure_code, 'transport_code': error.transport_code,
                          'transport_operation_started': error.transport_operation_started,
                          'temporary_ssh_key_removed': error.temporary_ssh_key_removed}), flush=True)
        raise SystemExit(1) from None
    except BaseException:
        print(json.dumps({'status': 'not_activated', 'reason': 'unexpected_administrative_failure'}), flush=True)
        raise SystemExit(1) from None
