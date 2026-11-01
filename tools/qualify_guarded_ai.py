"""Exercise the actual existing server AI client against synthetic facts only.

This is a test driver, not a service configuration or a trading entry point.
The API key stays in memory; the isolated DB contains no owner connection.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import sys
import tempfile
import time
from types import SimpleNamespace
import zipfile

ROOT = Path(__file__).resolve().parent.parent
import httpx

MODEL = 'openai/gpt-6.1-sol'
TESTED_SOURCE = Path('C:/Users/Klima/AndroidStudioProjects/AnalystAI-Lenovo/build/lenovo59-tests-817a4809.zip')
TESTED_SHA256 = '817a4809c5afda3d00c2b57832a025af0c86f8e0a8017ec4819b703822f4f1be'


def load_tested_client(folder):
    """Use the immutable, fully tested Lenovo source, not older GitHub main."""
    if not TESTED_SOURCE.is_file() or TESTED_SOURCE.stat().st_size > 32 * 1024 * 1024:
        raise ValueError('tested_source_missing')
    if hashlib.sha256(TESTED_SOURCE.read_bytes()).hexdigest() != TESTED_SHA256:
        raise ValueError('tested_source_changed')
    source = folder / 'tested-source'
    source.mkdir()
    with zipfile.ZipFile(TESTED_SOURCE) as archive:
        if sum(info.file_size for info in archive.infolist()) > 64 * 1024 * 1024:
            raise ValueError('tested_source_oversized')
        for info in archive.infolist():
            path = PurePosixPath(info.filename)
            if path.parts[:1] != ('backend',):
                continue
            if path.is_absolute() or '..' in path.parts or '\\' in info.filename or ':' in info.filename:
                raise ValueError('tested_source_path_invalid')
            if path.suffix != '.py':
                continue
            target = source.joinpath(*path.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(info))
    sys.path.insert(0, str(source))
    from backend.ai_guarded_client import GuardedAIClient, GuardError
    from backend.tests.ai_broker_fixtures import bind_synthetic_broker
    return GuardedAIClient, GuardError, bind_synthetic_broker, source


def score_evaluation(case, answer):
    # Same criteria as the local and JavaScript model evaluations.
    if not isinstance(answer, dict) or set(answer) != {'decision', 'source_ids', 'reason'}:
        return {'passed': False, 'failure': 'answer_schema'}
    refs = answer.get('source_ids')
    if (not isinstance(refs, list) or not refs or any(not isinstance(v, str) for v in refs)
            or len(refs) != len(set(refs)) or not set(refs) <= set(case['facts']['sources'])
            or not set(case['required_sources']) <= set(refs)):
        return {'passed': False, 'failure': 'source_binding'}
    if not isinstance(answer.get('reason'), str) or not 10 <= len(answer['reason']) <= 600:
        return {'passed': False, 'failure': 'explanation_required'}
    if answer.get('decision') != case['expected']:
        return {'passed': False, 'failure': 'decision_mismatch'}
    return {'passed': True, 'failure': None}


def configuration(key, prices):
    observed = datetime.fromisoformat(prices['checked_at_utc'].replace('Z', '+00:00'))
    now = datetime.now(timezone.utc)
    if prices['status'] != 'metadata_received' or not observed <= now < observed + timedelta(days=1):
        raise ValueError('tariffs_missing_or_stale')
    rows = [m for m in prices['models'] if m['identity'].get('model_name') == MODEL]
    if len(rows) != 1 or rows[0]['identity'].get('is_stopped') is not False or rows[0]['identity'].get('is_deprecated') is not False:
        raise ValueError('tariff_model_unavailable')
    values = rows[0]['parameter_values']
    rates = [Decimal(str(values[name])) for name in ('cost_in', 'cost_cache_write', 'cost_out')]
    if any(not v.is_finite() or not 0 < v <= 1 for v in rates):
        raise ValueError('tariff_invalid')
    # Same conservative per-token interpretation as the JavaScript benchmark.
    return {'AI_TRANSPORT': 'gateway', 'TIMEWEB_AI_TOKEN': key,
            'AI_MODEL_STANDARD': MODEL, 'AI_EXTERNAL_PROCESSING_APPROVED': 'true',
            'AI_ALLOWED_PROCESSING_REGIONS': 'EXTERNAL', 'AI_STANDARD_PROCESSING_REGION': 'EXTERNAL',
            'AI_STANDARD_PRICING_MODEL': MODEL,
            'AI_STANDARD_PRICING_VALID_UNTIL': (observed + timedelta(days=1)).isoformat(),
            'AI_STANDARD_INPUT_RUB_PER_MILLION': str(max(rates[:2]) * 1_000_000),
            'AI_STANDARD_OUTPUT_RUB_PER_MILLION': str(rates[2] * 1_000_000),
            'AI_STANDARD_TOKEN_PARAMETER': 'max_completion_tokens',
            'AI_USER_DAILY_RUB': '30', 'AI_PROJECT_DAILY_RUB': '30',
            'AI_USER_MONTHLY_RUB': '30', 'AI_PROJECT_MONTHLY_RUB': '30'}


def evaluate(folder, *, dry_run):
    folder.mkdir(parents=True, exist_ok=False)
    GuardedAIClient, GuardError, bind_synthetic_broker, source = load_tested_client(folder)
    fixture = json.loads((ROOT / 'tools/fixtures/portfolio-action-v1.json').read_text(encoding='utf-8'))
    prices = json.loads((ROOT / 'docs/evidence/2026-11-01-timeweb-model-pricing.json').read_text(encoding='utf-8'))
    key = 'synthetic-dry-run' if dry_run else os.environ.get('TIMEWEB_AI_TOKEN', '')
    if not re.fullmatch(r'[\x21-\x7e]{1,16384}', key):
        raise ValueError('gateway_credential_missing_or_invalid')
    env = configuration(key, prices)
    def connect():
        return sqlite3.connect(folder / 'ledger.sqlite3', timeout=15)
    bind_synthetic_broker(connect)
    report = {'schema_version': 1, 'started_at_utc': datetime.now(timezone.utc).isoformat(),
              'status': 'running', 'dry_run': dry_run, 'model': MODEL,
              'protocol': 'Existing GuardedAIClient / chat/completions / JSON object',
              'tested_source_sha256': TESTED_SHA256,
              'client_sha256': hashlib.sha256((source / 'backend/ai_guarded_client.py').read_bytes()).hexdigest(),
              'fixture_sha256': hashlib.sha256((ROOT / 'tools/fixtures/portfolio-action-v1.json').read_bytes()).hexdigest(),
              'financial_orders': 0, 'owner_data_transmitted': False, 'automatic_retries': 0,
              'network_model_invocations': 0, 'attempts': [], 'passed': 0,
              'portfolio_manager_qualified': False, 'synthetic_suite_passed': False,
              'estimated_budget_cap_rub': '30', 'provider_invoice_reconciled': False}
    output = folder / 'report.json'
    def save():
        temporary = output.with_suffix('.tmp')
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temporary.replace(output)
    save()
    transport = None
    for scenario in fixture['cases']:
        attempt = {'case_id': scenario['id'], 'expected': scenario['expected'], 'passed': False, 'state': 'prepared'}
        report['attempts'].append(attempt)
        if dry_run:
            def respond(request):
                payload = json.loads(request.content)
                assert request.url == 'https://api.timeweb.ai/v1/chat/completions'
                assert payload['max_completion_tokens'] == 1600 and payload['reasoning_effort'] == 'low'
                assert json.loads(payload['messages'][1]['content']) == scenario['facts']
                assert payload['response_format'] == {'type': 'json_object'}
                return httpx.Response(200, json={'model': MODEL,
                    'usage': {'prompt_tokens': 100, 'completion_tokens': 30, 'total_tokens': 130},
                    'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps({
                        'decision': scenario['expected'], 'source_ids': scenario['required_sources'],
                        'reason': 'Проверено по синтетическим фактам и ограничениям.'})}}]})
            transport = httpx.MockTransport(respond)
        def before_send():
            attempt['state'] = 'dispatch_may_begin'
            if not dry_run:
                report['network_model_invocations'] += 1
            save()
        client = GuardedAIClient(1, connect, env=env, transport=transport,
                                 attempt_id='guarded-sol-v1:' + scenario['id'], before_send=before_send)
        started = time.monotonic()
        try:
            result = client.complete_json(tier=SimpleNamespace(value='standard'), messages=[
                {'role': 'system', 'content': fixture['prompt']},
                {'role': 'user', 'content': json.dumps(scenario['facts'], ensure_ascii=False)}], max_output_tokens=1600)
            attempt.update(state='response_accounted', returned_model=result.model, usage=asdict(result.usage),
                           **score_evaluation(scenario, result.data))
            if attempt['failure'] is None or attempt['failure'] == 'decision_mismatch':
                attempt['answer'] = result.data
            if attempt['passed']:
                report['passed'] += 1
        except GuardError as error:
            attempt['failure'] = error.code if re.fullmatch('[a-z0-9_]{1,100}', error.code) else 'guarded_request_failed'
            report['stopped_reason'] = 'guarded_request_failed_no_retry'
        except Exception:
            attempt['failure'] = 'driver_failed'
            report['stopped_reason'] = 'driver_failed_no_retry'
        attempt['latency_ms'] = round((time.monotonic() - started) * 1000)
        report['ledger'] = client.ledger.user_summary(1, environ=env)
        save()
        if report.get('stopped_reason'):
            break
    report['status'] = 'completed'
    report['synthetic_suite_passed'] = report['passed'] == len(fixture['cases'])
    report['completed_at_utc'] = datetime.now(timezone.utc).isoformat()
    save()
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    # Avoid implicit proxy routes in this fixed-origin diagnostic process.
    for name in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy'):
        os.environ.pop(name, None)
    try:
        if args.dry_run:
            with tempfile.TemporaryDirectory(prefix='analyst-ai-dry-run-') as tmp:
                report = evaluate(Path(tmp) / 'evaluation', dry_run=True)
        else:
            report = evaluate(Path.cwd() / 'guarded-ai-evaluation', dry_run=False)
        print(json.dumps({key: report[key] for key in ('status', 'dry_run', 'passed', 'network_model_invocations', 'synthetic_suite_passed')}))
        return 0 if report['synthetic_suite_passed'] else 2
    except Exception:
        print(json.dumps({'status': 'not_completed', 'reason': 'guarded_evaluation_initialization_failed'}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
