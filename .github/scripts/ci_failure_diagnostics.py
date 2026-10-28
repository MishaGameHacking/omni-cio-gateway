"""Bounded diagnostics for an already-failed, isolated owner-laptop CI worker.

Never changes a test result or launches a process. Only fixed files in the
current job's validated state directory are read. Raw paths from a step receipt
are not followed. JSON framing keeps log text from becoming Actions commands.
"""
from __future__ import annotations

import json
from pathlib import Path
import re

PHASES = frozenset({'build', 'runtime-prepare', 'profile-16384', 'profile-4096', 'validate'})
MAX_LOG_BYTES = 8 * 1024 * 1024
TAIL_CHARACTERS = 16000
MAX_STEP_RECORDS = 100


def _log_tail(path, read_bytes):
    try:
        raw = read_bytes(path, MAX_LOG_BYTES)
    except (OSError, RuntimeError, ValueError) as error:
        return {'available': False, 'error_type': type(error).__name__}
    return {'available': True, 'bytes': len(raw),
            'tail': raw.decode('utf-8', errors='replace')[-TAIL_CHARACTERS:]}


def failure_evidence(state: Path, phase: str, read_bytes) -> dict:
    if phase not in PHASES:
        raise ValueError('unexpected_diagnostic_phase')
    result = {'phase': phase, 'status': 'failed_worker_diagnostic_not_acceptance',
              'worker': _log_tail(state / (phase + '-worker.log'), read_bytes),
              'traceback': _log_tail(state / (phase + '-failure.log'), read_bytes),
              'failed_steps': []}
    try:
        raw = read_bytes(state / (phase + '-steps.json'), 1024 * 1024)
        payload = json.loads(raw)
    except (OSError, RuntimeError, ValueError) as error:
        result['steps_error_type'] = type(error).__name__
        return result
    rows = payload.get('steps') if isinstance(payload, dict) else None
    if not isinstance(rows, list) or len(rows) > MAX_STEP_RECORDS:
        result['steps_error_type'] = 'InvalidStepShape'
        return result
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict) or row.get('exit_code') == 0:
            continue
        label = row.get('label')
        if not isinstance(label, str) or re.fullmatch(r'[a-z][a-z0-9-]{0,79}', label) is None:
            result['steps_error_type'] = 'InvalidStepLabel'
            continue
        # Do not trust row['log']; a receipt cannot redirect diagnostic reads.
        name = f'{phase}-steps-{index:02d}-{label}.log'
        item = {'label': label, 'log': _log_tail(state / name, read_bytes)}
        code = row.get('exit_code')
        item['exit_code'] = code if type(code) is int else None
        result['failed_steps'].append(item)
    return result


def print_worker_failure(state: Path, phase: str, read_bytes) -> None:
    try:
        result = failure_evidence(state, phase, read_bytes)
    except (OSError, RuntimeError, ValueError, TypeError) as error:
        result = {'phase': phase, 'diagnostic_error_type': type(error).__name__}
    print('WINDOWS_ANDROID_FAILURE_EVIDENCE=' + json.dumps(result, ensure_ascii=True), flush=True)
