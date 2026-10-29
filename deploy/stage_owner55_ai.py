"""Stage one newly provisioned gateway key with all paid work disabled.

Executed only through the private pinned SSH transport. No key, environment
contents or credential-derived hash is printed, archived or returned. Activation
is deliberately a separate reviewed operation; this file never calls inference.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import stat
import uuid

CONFIGURATION = Path('/etc/analyst-ai/backend.env')
SOURCES = Path('/opt/analyst-ai/backend')
LOCK = Path('/var/lock/analyst-ai-plan-development.lock')
MODEL = 'dashscope/qwen3.5-flash'
MASKED = 'hidden-by-api-key-policy'
SOURCE_NAMES = {'ai_budget.py', 'ai_guarded_client.py', 'ai_broker_access.py'}
DISABLED = {'AI_USER_DAILY_RUB': '0', 'AI_PROJECT_DAILY_RUB': '0',
            'AI_USER_MONTHLY_RUB': '0', 'AI_PROJECT_MONTHLY_RUB': '0',
            'AI_EXTERNAL_PROCESSING_APPROVED': 'false'}
PREFLIGHT_REASONS = {'ready', 'root_transport_required', 'preflight_secret_not_allowed',
    'incomplete_budget_source_proof', 'invalid_source_proof', 'budget_source_not_the_reviewed_version',
    'unsafe_configuration_or_source_file', 'unsafe_environment_permissions', 'unsafe_configuration_file',
    'configuration_changed_while_reading', 'configuration_too_large', 'unsupported_environment_syntax',
    'duplicate_environment_variable', 'unsupported_environment_value',
    'existing_inference_key_must_not_be_replaced', 'custom_route_catalog_requires_separate_review',
    'required_file_missing', 'required_file_access_denied', 'deployment_lock_busy',
    'configuration_encoding_invalid', 'configuration_format_invalid', 'preflight_not_verified'}


def need(condition, code):
    if not condition:
        raise RuntimeError(code)


def read_regular(path):
    info = path.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and path.resolve(strict=True) == path,
         'unsafe_configuration_or_source_file')
    return path.read_bytes()


def parse_environment(raw):
    need(len(raw) <= 128 * 1024, 'configuration_too_large')
    result = {}
    for line in raw.decode('utf-8').splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        key, separator, value = stripped.partition('=')
        need(separator and re.fullmatch('[A-Z][A-Z0-9_]*', key), 'unsupported_environment_syntax')
        need(key not in result, 'duplicate_environment_variable')
        fields = shlex.split(value)
        need(len(fields) <= 1, 'unsupported_environment_value')
        result[key] = fields[0] if fields else ''
    return result


def no_existing_key(settings):
    keys = ['TIMEWEB_AI_TOKEN', 'TIMEWEB_CLOUD_API_KEY', 'ANALYST_OWNER_AI_KEY_ID']
    keys += ['TIMEWEB_AI_' + tier + '_TOKEN' for tier in ('FAST', 'STANDARD', 'PREMIUM')]
    need(not any(settings.get(key, '').strip() for key in keys), 'existing_inference_key_must_not_be_replaced')
    need(not settings.get('AI_ROUTE_CATALOG_JSON', '').strip(), 'custom_route_catalog_requires_separate_review')


def verify_sources(expected):
    need(isinstance(expected, dict) and set(expected) == SOURCE_NAMES, 'incomplete_budget_source_proof')
    for name, value in expected.items():
        need(isinstance(value, str) and re.fullmatch('[a-f0-9]{64}', value), 'invalid_source_proof')
        need(hashlib.sha256(read_regular(SOURCES / name)).hexdigest() == value,
             'budget_source_not_the_reviewed_version')


def validate_prices(pricing):
    need(isinstance(pricing, dict) and set(pricing) == {'input_rub_per_million', 'output_rub_per_million', 'valid_until'},
         'invalid_pricing_fields')
    try:
        rates = [Decimal(pricing[name]) for name in ('input_rub_per_million', 'output_rub_per_million')]
        need(all(rate.is_finite() and 0 < rate <= Decimal('1000000') for rate in rates), 'invalid_pricing_amount')
        deadline = datetime.fromisoformat(pricing['valid_until'].replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        need(deadline.tzinfo is not None and 0 < (deadline - now).total_seconds() <= 7 * 86400,
             'pricing_deadline_invalid')
    except (InvalidOperation, ValueError, TypeError, AttributeError):
        raise RuntimeError('invalid_pricing_format') from None


def require_gateway_key(secret):
    # Match the controller's opaque HTTP-safe credential validation.
    need(secret != MASKED, 'new_gateway_key_masked')
    need(isinstance(secret, str) and 1 <= len(secret) <= 8192
         and all(33 <= ord(c) <= 126 for c in secret), 'new_gateway_key_invalid')


def settings_for(payload, secret):
    key_id = payload.get('key_id')
    need(isinstance(key_id, str) and str(uuid.UUID(key_id)) == key_id, 'invalid_new_key_id')
    require_gateway_key(secret)
    need(payload.get('model') == MODEL, 'unexpected_model')
    pricing = payload.get('pricing')
    validate_prices(pricing)
    settings = {**DISABLED, 'TIMEWEB_AI_TOKEN': secret, 'ANALYST_OWNER_AI_KEY_ID': key_id,
                'TIMEWEB_AI_BASE_URL': 'https://api.timeweb.ai/v1', 'AI_TRANSPORT': 'gateway',
                'AI_ALLOWED_PROCESSING_REGIONS': 'EXTERNAL'}
    for tier in ('FAST', 'STANDARD', 'PREMIUM'):
        prefix = 'AI_' + tier + '_'
        settings['AI_MODEL_' + tier] = MODEL
        settings[prefix + 'TRANSPORT'] = 'gateway'
        settings[prefix + 'PRICING_MODEL'] = MODEL
        settings[prefix + 'PROCESSING_REGION'] = 'EXTERNAL'
        settings[prefix + 'TOKEN_PARAMETER'] = 'max_tokens'
        settings[prefix + 'INPUT_TOKEN_ALLOWANCE'] = '4096'
        settings[prefix + 'INPUT_RUB_PER_MILLION'] = pricing['input_rub_per_million']
        settings[prefix + 'OUTPUT_RUB_PER_MILLION'] = pricing['output_rub_per_million']
        settings[prefix + 'PRICING_VALID_UNTIL'] = pricing['valid_until']
    return settings


def replacement_environment(raw, changes):
    lines = []
    for line in raw.decode('utf-8').splitlines():
        key = line.strip().partition('=')[0]
        if key not in changes:
            lines.append(line)
    for key, value in sorted(changes.items()):
        need(isinstance(value, str) and '\n' not in value and '\r' not in value and '\0' not in value,
             'unsafe_environment_value')
        lines.append(key + '=' + shlex.quote(value))
    result = ('\n'.join(lines) + '\n').encode('utf-8')
    actual = parse_environment(result)
    need(all(actual.get(key) == value for key, value in changes.items()), 'environment_serialization_mismatch')
    return result


def file_identity(info):
    return (info.st_dev, info.st_ino, info.st_uid, info.st_gid, info.st_mode,
            info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def configuration_snapshot():
    fd = os.open(CONFIGURATION, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'rb') as source:
        before = os.fstat(source.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_uid == 0
             and not (before.st_mode & 0o007), 'unsafe_environment_permissions')
        raw = source.read(128 * 1024 + 1)
        after = os.fstat(source.fileno())
    need(len(raw) <= 128 * 1024 and CONFIGURATION.resolve(strict=True) == CONFIGURATION,
         'unsafe_configuration_file')
    identity = file_identity(before)
    need(identity == file_identity(after) == file_identity(CONFIGURATION.lstat()),
         'configuration_changed_while_reading')
    return raw, identity


def require_unchanged(expected):
    need(configuration_snapshot() == expected, 'configuration_changed_before_write')


def atomic_configuration(raw, expected):
    temporary = CONFIGURATION.with_name(CONFIGURATION.name + '.ai-private-staging')
    original_identity = expected[1]
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        with os.fdopen(fd, 'wb') as output:
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())
        os.chown(temporary, original_identity[2], original_identity[3])
        os.chmod(temporary, original_identity[4] & 0o660)
        # The deployment lock serializes cooperating operations. This in-memory
        # comparison also rejects an unrelated administrator's intervening edit.
        require_unchanged(expected)
        os.replace(temporary, CONFIGURATION)
        directory = os.open(CONFIGURATION.parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary.exists():
            temporary.unlink()


def preflight(envelope):
    receipt = {'status': 'not_ready', 'reason': 'preflight_not_verified', 'server_id': 9417611,
               'existing_key_absent': False, 'budget_sources_verified': False, 'configuration_changed': False}
    try:
        import fcntl
        need(os.getuid() == 0, 'root_transport_required')
        need(envelope.get('secret') is None, 'preflight_secret_not_allowed')
        with LOCK.open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            verify_sources(envelope['payload'].get('source_sha256'))
            receipt['budget_sources_verified'] = True
            original = configuration_snapshot()[0]
            no_existing_key(parse_environment(original))
            receipt['existing_key_absent'] = True
        receipt.update(status='ready', reason='ready')
    except BaseException as error:
        candidate = error.args[0] if error.args else None
        if isinstance(error, RuntimeError) and isinstance(candidate, str) and candidate in PREFLIGHT_REASONS:
            receipt['reason'] = candidate
        elif isinstance(error, FileNotFoundError):
            receipt['reason'] = 'required_file_missing'
        elif isinstance(error, PermissionError):
            receipt['reason'] = 'required_file_access_denied'
        elif isinstance(error, BlockingIOError):
            receipt['reason'] = 'deployment_lock_busy'
        elif isinstance(error, UnicodeError):
            receipt['reason'] = 'configuration_encoding_invalid'
        elif isinstance(error, ValueError):
            receipt['reason'] = 'configuration_format_invalid'
    return receipt


def run(envelope):
    import fcntl
    if isinstance(envelope.get('payload'), dict) and envelope['payload'].get('action') == 'preflight':
        return preflight(envelope)
    need(os.getuid() == 0, 'root_transport_required')
    payload = envelope['payload']
    need(isinstance(payload, dict) and payload.get('action') in {'preflight', 'stage_disabled'}, 'invalid_stage_action')
    with LOCK.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        verify_sources(payload.get('source_sha256'))
        original_snapshot = configuration_snapshot()
        original = original_snapshot[0]
        no_existing_key(parse_environment(original))
        changes = settings_for(payload, envelope.get('secret'))
        desired = replacement_environment(original, changes)
        atomic_configuration(desired, original_snapshot)
        need(configuration_snapshot()[0] == desired, 'configuration_write_not_verified')
        # A failure after replacement is indeterminate and is never rolled back
        # over another writer. The provider key remains blocked at verified zero
        # limits and the controller retains it for inspected recovery.
        return {'status': 'staged_disabled', 'server_id': 9417611, 'key_id': payload['key_id'],
                'model': MODEL, 'daily_cap_rub': '0', 'monthly_cap_rub': '0',
                'existing_key_replaced': False, 'service_restarted': False,
                'inference_called': False}


if __name__ == '__main__':
    try:
        print(json.dumps(run(ENVELOPE)), flush=True)
    except BaseException:
        # Private transport discards failure output; do not expose even an
        # exception message originating in configuration or provider material.
        raise SystemExit(1) from None
