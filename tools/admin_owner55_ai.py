"""Narrow Ubuntu administrative adapter for the reviewed AI controller functions.

This does not invoke their WSL-only entry points or execute application tests.
Cloud credentials stay in this process; inference-key delivery remains confined
to the shared private SSH core. Only a validated finite receipt reaches stdout.
"""
from contextlib import redirect_stderr, redirect_stdout
import json
import os
from pathlib import Path
import re

import activate_owner55_ai as activation
import provision_owner55_ai as provision
from owner55_ai_guest import validate_outcome
from owner_ai_admin_transport import require_admin_guard, transport_admin
from owner_ai_private_transport import PrivateTransportError, SAFE_TRANSPORT_FAILURE_CODES

SOURCE_NAMES = {'ai_budget.py', 'ai_guarded_client.py', 'ai_broker_access.py'}
SAFE_REASONS = {
    'account_currency_not_rub', 'current_model_prices_not_verified',
    'model_context_does_not_fit_adapter_limits', 'adapter_generation_parameters_unverified',
    'key_inventory_incomplete', 'key_inventory_identity_invalid', 'invalid_new_key_name',
    'existing_dedicated_key_requires_inspection', 'key_inventory_changed_before_creation',
    'key_creation_requires_inspected_recovery', 'new_key_identity_unknown',
    'remote_preflight_failed', 'private_preflight_requires_inspection',
    'new_unused_key_cleanup_failed', 'new_unused_key_removed_after_failure',
    'private_delivery_requires_inspected_recovery', 'new_key_metadata_mismatch',
    'staged_key_identity_invalid', 'dedicated_key_identity_changed',
    'provider_limit_inventory_invalid', 'provider_limit_binding_invalid',
    'provider_limit_periods_invalid', 'provider_limit_identity_changed',
    'private_activation_preflight_failed', 'activation_requires_inspected_recovery',
    'activation_endpoint_not_allowlisted', 'limit_patch_http_status_invalid',
    'limit_patch_response_too_large', 'limit_patch_response_invalid',
    'limit_patch_outcome_requires_readback',
}
SAFE_FAILURES = {'new_key_metadata_mismatch', 'new_gateway_key_masked', 'new_gateway_key_invalid',
    'zero_limits_incomplete', 'zero_limits_wrong_periods', 'zero_limits_not_enforced_for_all_models',
    'new_key_not_visible_after_creation', 'remote_staging_receipt_mismatch',
    'cloud_request_failed', 'private_delivery_failed', 'unclassified_failure'}


class DiscardedOutput:
    def write(self, value):
        return len(value)
    def flush(self):
        pass


def need(condition):
    if not condition:
        raise RuntimeError('administrative_configuration_invalid')


def source_proof(environment):
    value = json.loads(environment.get('OWNER_AI_EXPECTED_BUDGET_SOURCES', ''))
    need(isinstance(value, dict) and set(value) == SOURCE_NAMES
         and all(isinstance(item, str) and re.fullmatch('[a-f0-9]{64}', item) for item in value.values()))
    return value


def safe_reason(value):
    if isinstance(value, str) and value in SAFE_REASONS:
        return value
    if isinstance(value, str) and re.fullmatch('cloud_http_[1-5][0-9]{2}', value):
        return 'cloud_request_failed'
    return 'unexpected_administrative_failure'


def error_receipt(action, error):
    is_activation = action == 'activate'
    result = {'status': 'activation_unconfirmed' if is_activation else 'not_activated',
              'reason': 'unexpected_administrative_failure'}
    if isinstance(error, provision.ProvisionError):
        result['reason'] = safe_reason(error.code)
        if not is_activation:
            result.update(new_key_id=provision.uuid_text(error.key_id),
                          new_key_retained=error.retained if error.retained is None or type(error.retained) is bool else None)
        result['failure_code'] = error.failure_code if error.failure_code in SAFE_FAILURES else None
        code = error.transport_code
        if code in SAFE_TRANSPORT_FAILURE_CODES or code == 'private_preflight_failed':
            result['transport_code'] = code
        for field in ('transport_operation_started', 'temporary_ssh_key_removed'):
            value = getattr(error, field)
            result[field] = value if type(value) is bool else None
    elif isinstance(error, activation.ActivationError):
        result['reason'] = safe_reason(error.code)
        value = error.provider_blocked
        result['provider_zero_limits_verified'] = value if type(value) is bool else None
    elif isinstance(error, PrivateTransportError):
        result['reason'] = 'private_preflight_requires_inspection'
        result['transport_code'] = error.code if error.code in SAFE_TRANSPORT_FAILURE_CODES else 'private_preflight_failed'
        result['transport_operation_started'] = error.operation_started if type(error.operation_started) is bool else None
        result['temporary_ssh_key_removed'] = error.temporary_key_removed if type(error.temporary_key_removed) is bool else None
    return result


def execute(environment):
    require_admin_guard()
    action = environment.get('OWNER_AI_ACTION')
    gates = {'preflight_only': ('OWNER_AI_PROVISION_REVIEW', provision.PREFLIGHT_ONLY_GATE),
             'provision_disabled': ('OWNER_AI_PROVISION_REVIEW', provision.PROVISION_GATE),
             'activate': ('OWNER_AI_ACTIVATION_REVIEW', activation.GATE)}
    need(action in gates)
    gate_name, gate_value = gates[action]
    need(environment.get(gate_name) == gate_value)
    token = environment.get('TIMEWEB_CLOUD_TOKEN', '')
    need(16 <= len(token) <= 8192 and not any(character.isspace() for character in token))
    run_id = environment.get('GITHUB_RUN_ID', '')
    need(re.fullmatch('[0-9]{8,20}', run_id))
    sources = source_proof(environment)
    root = Path(__file__).resolve().parents[1]
    if action == 'activate':
        return activation.activate(activation.ActivationAPI(token), transport_admin,
            activation.operation_source(), sources, environment.get('OWNER_AI_STAGED_KEY_ID', ''),
            environment.get('OWNER_AI_CREATION_RUN_ID', ''))
    operation = (root / 'deploy/stage_owner55_ai.py').read_text(encoding='utf-8')
    api = provision.CloudAPI(token)
    if action == 'preflight_only':
        return provision.inspect_preflight(api, transport_admin, operation, sources)
    return provision.provision(api, transport_admin, operation, sources,
                               provision.DEDICATED_PREFIX + run_id)


def run_administration(environment):
    action = environment.get('OWNER_AI_ACTION')
    token = environment.get('TIMEWEB_CLOUD_TOKEN', '')
    try:
        # Includes provenance checks and all dependencies, even their failures.
        # No raw provider/SSH stderr or traceback can become a user receipt.
        with redirect_stdout(DiscardedOutput()), redirect_stderr(DiscardedOutput()):
            try:
                receipt = execute(environment)
                exit_code = 0
            except BaseException as error:
                receipt, exit_code = error_receipt(action, error), 1
        receipt = validate_outcome(json.dumps(receipt, allow_nan=False).encode(), token)
        success = {'preflight_only': {'ready', 'not_ready'},
                   'provision_disabled': {'staged_disabled'}, 'activate': {'activated'}}
        if exit_code == 0:
            need(action in success and receipt.get('status') in success[action])
        return receipt, exit_code
    except BaseException:
        return {'status': 'activation_unconfirmed' if action == 'activate' else 'not_activated',
                'reason': 'administrative_receipt_requires_inspection'}, 1


def main():
    try:
        receipt, exit_code = run_administration(os.environ)
    finally:
        os.environ.pop('TIMEWEB_CLOUD_TOKEN', None)
    print(json.dumps(receipt), flush=True)
    raise SystemExit(exit_code)


if __name__ == '__main__':
    main()
