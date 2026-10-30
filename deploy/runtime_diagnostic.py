"""One-shot bounded observation of existing runtime; no application imports or writes."""
from __future__ import annotations

from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import time

# This observer must only be dispatched after the exact candidate is deployed.
SOURCE = 'af95e8de8cfd50970d712483b8c17e866f7239c9'
INSTALLED = {
    'autonomous_controller.py': 'cbb25165004afd4f33a2a76cabc13e56c4c458609303a018bb32bd267e832d83',
    'decision_cycle.py': 'a46331652844cde45ae8d63a2887d97da121d55948cc125844a15b99fe181e95',
    'decision_views.py': 'e3ca67c74957973b2bf3d9b4ac5e82efe0fcd710801ee49675f76d8645e41558',
    'margin_policy.py': '8fa653fa401ee5cc322784d92169475022dc463670d218cf854f285b6e609aa3',
    'purchase_policy.py': '36508ad0a99af467d9d0f44a9c26fafb45d16c212b5ae5fc027cab2a5f351eab',
    'strategy_actions.py': 'c0d327eb94a085ef2feb6b2dd5efb44ebdc7c565c41f2964019ab9d8fb01e053',
    'volume_chat.py': '8abeb8a8fba42e5319ec173f401f29bca778be61aad5d4428b97e34f3d4b167b',
    'volume_live.py': '7698a89a3b34a03d262e095d3993e1fb00b7c1805b675a3acf5c90b152cd4d5e',
    'ai_guarded_client.py': 'd65872bcf5d90f34e852da3155f0b9e5852a713ecfb4e55403505143381a0243',
    'investment_chat_policy.py': '60d6a4f7ca5d8047eb5fa0b6963cf7ae79f31df624f3341f0c59b1d92a9604b8',
    'volume_jobs.py': '1ba356d49a4a09f87402ecfb5d959bd9fc4785a4f6ddf5e3cba099f1462d7e6b',
    'portfolio_details.py': '1dafbf959eb4ffe8fc23a304d3047fa4f95e6705459a733196a5e64b06d43ea1',
    'order_lifecycle.py': 'e5560f86c27179be3240e7f37615e9b3c0b90f0ef31d9a0adaabc2bffd0b07ca',
}
FAILED_RELEASE_ARCHIVE = Path('/var/lib/analyst-ai-gpt6-protocol-41068805166')
HEALTH_ENDPOINTS = {
    'public_health': 'https://analyst-ai-2941515.twc1.net/health',
    'public_password_status': 'https://analyst-ai-2941515.twc1.net/auth/owner/status',
    # Port 8080 is pinned in the existing reviewed owner runtime operation.
    'local_health': 'http://127.0.0.1:8080/health',
}
STATES = frozenset({'blocked', 'waiting', 'preview_available', 'queued', 'running',
    'completed', 'failed', 'cancelled', 'uncertain', 'partial', 'stale', 'reserved', 'settled'})
KINDS = frozenset({'chat', 'analysis', 'refresh', 'events', 'reconcile', 'catalogue', 'osint'})
STAGES = frozenset({'queued', 'model_running', 'validating', 'done', 'failed',
    'reconciliation_required', 'analysis_monitor', 'collecting', 'reading_sources'})
MODELS = frozenset({'dashscope/qwen3.5-flash'})
# Only literal public diagnostic codes may leave the host. Unrecognized strings
# are counted as unknown, even if they happen to look like harmless identifiers.
CODES = frozenset('''real_order_execution_disabled strategy_required automation_paused
account_outside_mandate candidate_account_unverified investment_profile_incomplete
fresh_snapshot_required portfolio_coverage_incomplete broker_connection_required
evidence_revision_required strategy_changed snapshot_changed evidence_changed
decision_inputs_changed candidate_expired decision_expired candidate_constraints_failed
investment_research_incomplete tax_and_settlement_effects
loss_capacity_and_full_investment_profile investment_thesis_and_valuation
no_whole_lot_within_target_and_reserve candidate_quantity_unverified
candidate_cost_unverified sell_owned_units_unverified protected_reserve_would_be_spent
own_cash_unverified borrowed_cash_not_permitted no_candidates_reviewed no_action_required
candidate_input_invalid discovery_incomplete market_price_polling_paused
limit_trading_unavailable broker_purchase_unavailable strategy_rebalance_cooldown
strategy_turnover_limit issuer_rating_required issue_rating_required cash_floor_breached
research_incomplete catalogue_unavailable catalogue_no_eligible_instruments
discovery_stale broker_qualification_required broker_tests_not_confirmed
insufficient_visible_liquidity_at_limit ai_incomplete_response ai_choices_invalid
ai_content_invalid ai_content_not_json ai_content_not_object ai_transport_outcome_unknown
ai_response_not_json ai_usage_missing ai_usage_invalid ai_usage_inconsistent
ai_usage_outside_reserved_bounds ai_usage_requires_reconciliation ai_budget_reconciliation_required
workspace_paid_outcome_unknown workspace_job_cancelled_or_lease_lost
analysis_cancelled analysis_failed worker_lease_expired collection_temporary_failure
ai_prices_missing_stale_or_invalid ai_route_cooling_down ai_route_in_flight
ai_worker_reconciliation_required ai_ruble_budget_not_enabled ai_processing_approval_required
timeweb_ai_key_missing ai_no_route_with_context_capacity ai_context_too_large
ai_http_400 ai_http_401 ai_http_403 ai_http_408 ai_http_429 ai_http_500 ai_http_502 ai_http_503
'''.split())
TABLES = frozenset({'portfolio_decision_cycles', 'automation_discovery',
    'automation_preferences', 'workspace_jobs', 'ai_work_jobs', 'scheduler_leases',
    'ai_money_reservations', 'workspace_snapshots', 'workspace_chat_messages'})


def need(condition, code):
    if not condition:
        raise RuntimeError(code)


def regular(path):
    need(path.is_file() and not path.is_symlink() and path.resolve(strict=True) == path,
         'diagnostic_regular_file_required')
    return path


def token(value, allowed):
    return value if isinstance(value, str) and value in allowed else 'unknown'


def integer(value):
    return value if type(value) is int and 0 <= value <= 10**12 else None


def stamp(value):
    if type(value) is not int or not 0 <= value <= 4_102_444_800:
        return None
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def code(value):
    return None if value is None else token(value, CODES)


def codes(rows):
    if not isinstance(rows, list):
        return ['unknown']
    return sorted({code(item.get('code')) or 'unknown'
                   for item in rows[:100] if isinstance(item, dict)})


def bounded_json(raw):
    if not isinstance(raw, str) or len(raw) > 524288:
        return None
    try:
        value = json.loads(raw)
    except (ValueError, RecursionError):
        return None
    return value if isinstance(value, dict) else None


def authorize(action, name, column, database, trigger):
    if action == sqlite3.SQLITE_READ:
        return sqlite3.SQLITE_OK if name in TABLES or name == 'sqlite_master' else sqlite3.SQLITE_DENY
    if action in {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_TRANSACTION}:
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_PRAGMA and name in {'query_only', 'journal_mode'} and column is None:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def observe_cycles(db, now):
    count, first, last = db.execute('SELECT COUNT(*),MIN(evaluated_at),MAX(evaluated_at) FROM portfolio_decision_cycles').fetchone()
    rows = db.execute('''SELECT evaluated_at,CASE WHEN length(payload_json)<=524288 THEN payload_json ELSE NULL END
        FROM portfolio_decision_cycles ORDER BY evaluated_at DESC LIMIT 12''').fetchall()
    recent = []
    for at, raw in rows:
        value = bounded_json(raw)
        item = {'evaluated_at': stamp(at), 'age_seconds': now - at if type(at) is int else None,
                'payload_valid': value is not None}
        if value is not None:
            execution = value.get('execution')
            item.update(state=token(value.get('state'), STATES), blockers=codes(value.get('blockers')),
                candidate_count=len(value['candidates']) if isinstance(value.get('candidates'), list) else None,
                proposed_action_present=isinstance(value.get('proposed_action'), dict),
                recorded_real_orders_enabled=execution.get('real_orders_enabled')
                    if isinstance(execution, dict) and type(execution.get('real_orders_enabled')) is bool else None)
        recent.append(item)
    return {'rows': count, 'first_at': stamp(first), 'last_at': stamp(last), 'recent': recent,
            'scope': 'stored_audit_all_connections_not_revalidated_current_account',
            'live_trade_execution_verified': False}


def observe_discovery(db):
    rows = db.execute('''SELECT state,updated_at,attempted_at,lease_until,
        CASE WHEN length(result_json)<=524288 THEN result_json ELSE NULL END
        FROM automation_discovery ORDER BY updated_at DESC LIMIT 10''').fetchall()
    result = []
    for state, updated, attempted, lease, raw in rows:
        value = bounded_json(raw) or {}
        coverage = value.get('coverage') if isinstance(value.get('coverage'), dict) else {}
        result.append({'state': token(state, STATES), 'updated_at': stamp(updated),
            'attempted_at': stamp(attempted), 'lease_until': stamp(lease),
            'reasons': codes(value.get('reasons', [])),
            'coverage': {key: integer(coverage.get(key)) for key in ('scanned', 'eligible', 'reviewed', 'constraint_checks_passed')}})
    return result


def saved_chat_route(db, identifier, user_id):
    row = db.execute('''SELECT CASE WHEN length(payload_json)<=524288 AND json_valid(payload_json)
        THEN json_extract(payload_json,'$.routing') ELSE NULL END FROM workspace_chat_messages
        WHERE job_id=? AND user_id=? AND role='user' LIMIT 1''', (identifier, user_id)).fetchone()
    value = bounded_json(row[0]) if row else None
    if value is None:
        return None
    return {'model': token(value.get('model'), MODELS),
        'selected_tier': token(value.get('selected_tier'), {'fast', 'standard', 'premium'}),
        'required_tier': token(value.get('required_tier'), {'fast', 'standard', 'premium'}),
        'max_output_tokens': integer(value.get('max_output_tokens'))}


def observe_jobs(db, now, *, chat_routes):
    counts = Counter()
    for kind, state, count in db.execute('SELECT kind,state,COUNT(*) FROM workspace_jobs GROUP BY kind,state'):
        counts[(token(kind, KINDS), token(state, STATES))] += count
    recent = []
    for row in db.execute('''SELECT id,user_id,state,stage,error_code,paid_started,created_at,updated_at,expires_at
        FROM workspace_jobs WHERE kind='chat' ORDER BY created_at DESC LIMIT 10'''):
        identifier, user_id, state, stage, error, paid, created, updated, expires = row
        recent.append({'state': token(state, STATES), 'stage': token(stage, STAGES), 'error_code': code(error),
            'paid_started': bool(paid), 'created_at': stamp(created), 'updated_at': stamp(updated),
            'running_lease_expired': state == 'running' and type(expires) is int and expires <= now,
            'saved_route': saved_chat_route(db, identifier, user_id) if chat_routes else None})
    expired = db.execute("SELECT COUNT(*) FROM workspace_jobs WHERE state='running' AND expires_at<=?", (now,)).fetchone()[0]
    return {'counts': [{'kind': kind, 'state': state, 'count': count} for (kind, state), count in sorted(counts.items())],
            'running_expired': expired, 'recent_chat': recent}


def observe_ledger(db):
    rows = db.execute('''SELECT model,state,input_tokens,output_tokens,created_at,updated_at
        FROM ai_money_reservations ORDER BY created_at DESC LIMIT 10''').fetchall()
    return {'recent': [{'model': token(model, MODELS), 'state': token(state, STATES),
            'input_tokens': integer(inputs), 'output_tokens': integer(outputs),
            'created_at': stamp(created), 'updated_at': stamp(updated)}
            for model, state, inputs, outputs, created, updated in rows],
            'job_link_verified': False, 'finish_reason_persisted': False,
            'max_output_tokens_persisted': False}


def observe_background_jobs(db):
    result = {}
    for label, prefix in (('collection', 'auto.full.%'), ('events', 'auto.events.%'), ('research', 'auto.osint.%')):
        total, created, updated = db.execute('''SELECT COUNT(*),MAX(created_at),MAX(updated_at)
            FROM workspace_jobs WHERE request_id LIKE ?''', (prefix,)).fetchone()
        states = Counter()
        for state, count in db.execute('SELECT state,COUNT(*) FROM workspace_jobs WHERE request_id LIKE ? GROUP BY state', (prefix,)):
            states[token(state, STATES)] += count
        result[label] = {'rows': total, 'last_created_at': stamp(created),
                         'last_updated_at': stamp(updated), 'states': dict(sorted(states.items()))}
    return result


def observe_database(path, now):
    regular(path)
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=3)) as db:
        db.execute('PRAGMA query_only=ON')
        db.set_authorizer(authorize)
        deadline = time.monotonic() + 8
        db.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
        db.execute('BEGIN')
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        result = {'query_only': db.execute('PRAGMA query_only').fetchone()[0] == 1,
                  'journal_mode': token(db.execute('PRAGMA journal_mode').fetchone()[0], {'wal', 'delete', 'truncate', 'persist', 'memory', 'off'}),
                  'missing_tables': sorted(TABLES - tables)}
        if 'portfolio_decision_cycles' in tables:
            result['decision_cycles'] = observe_cycles(db, now)
        if 'automation_discovery' in tables:
            result['discovery'] = observe_discovery(db)
        if 'workspace_jobs' in tables:
            result['workspace_jobs'] = observe_jobs(db, now, chat_routes='workspace_chat_messages' in tables)
            result['automatic_jobs'] = observe_background_jobs(db)
        if 'ai_money_reservations' in tables:
            result['model_usage'] = observe_ledger(db)
        if 'automation_preferences' in tables:
            result['automation_preferences'] = dict(db.execute('''SELECT CASE WHEN enabled=1 THEN 'enabled' ELSE 'paused' END,COUNT(*)
                FROM automation_preferences GROUP BY enabled'''))
        if 'scheduler_leases' in tables:
            result['scheduler_leases'] = {'rows': db.execute('SELECT COUNT(*) FROM scheduler_leases').fetchone()[0],
                'unexpired': db.execute('SELECT COUNT(*) FROM scheduler_leases WHERE expires_at>?', (now,)).fetchone()[0]}
        if 'workspace_snapshots' in tables:
            result['snapshot_metadata'] = {'rows': db.execute('SELECT COUNT(*) FROM workspace_snapshots').fetchone()[0],
                'last_saved_at': stamp(db.execute('SELECT MAX(created_at) FROM workspace_snapshots').fetchone()[0])}
        db.rollback()
    return result


def services():
    result = {}
    for name in ('analyst-ai-owner.service', 'analyst-ai-updates.service'):
        output = subprocess.run(['systemctl', 'show', name, '--property=ActiveState,SubState,NRestarts,MainPID,ExecMainStartTimestampMonotonic'],
                                capture_output=True, timeout=10, check=True).stdout.decode()
        values = dict(line.split('=', 1) for line in output.splitlines() if '=' in line)
        restarts = values.get('NRestarts', '')
        pid = values.get('MainPID', '')
        started = values.get('ExecMainStartTimestampMonotonic', '')
        result[name] = {'active': token(values.get('ActiveState'), {'active', 'inactive', 'failed', 'activating', 'deactivating'}),
            'substate': token(values.get('SubState'), {'running', 'dead', 'failed', 'start-pre', 'auto-restart'}),
            'restarts': int(restarts) if restarts.isascii() and restarts.isdigit() and len(restarts) < 10 else None,
            'main_pid': int(pid) if pid.isascii() and pid.isdigit() and len(pid) < 10 else None,
            'process_age_seconds': max(0, int(time.monotonic() - int(started) / 1_000_000))
                if started.isascii() and started.isdigit() and 0 < len(started) < 20 and int(started) > 0 else None}
    return result


def process_waits(pid, proc=Path('/proc')):
    """Thread wait sites only; never read arguments, environment, memory or logs."""
    if type(pid) is not int or not 0 < pid < 10_000_000:
        return {'available': False}
    task = proc / str(pid) / 'task'
    try:
        threads = [path for path in task.iterdir() if re.fullmatch('[0-9]{1,8}', path.name)]
        if len(threads) > 256:
            return {'available': False, 'thread_limit_exceeded': True}
        counts = Counter()
        allowed = {'futex_wait_queue', 'futex_wait_queue_me', 'ep_poll', 'do_epoll_wait',
                   'poll_schedule_timeout', 'hrtimer_nanosleep', 'wait_woken', '0'}
        for path in threads:
            raw = (path / 'wchan').read_text()[:128].strip()
            counts[raw if raw in allowed else 'other'] += 1
        return {'available': True, 'thread_count': len(threads), 'wait_sites': dict(counts)}
    except OSError:
        return {'available': False}


def verify_source(root):
    for name, expected in INSTALLED.items():
        path = regular(root / name)
        need(path.stat().st_size <= 524288, 'runtime_module_size_invalid')
        need(hashlib.sha256(path.read_bytes()).hexdigest() == expected, 'runtime_source_changed')


def observe_release_archive():
    archive = FAILED_RELEASE_ARCHIVE
    exists = archive.exists() or archive.is_symlink()
    result = {'release_run': 41068805166, 'archive_present': exists,
              'phase_evidence': 'archive_absent', 'failure': None}
    if not exists:
        return result
    if archive.is_symlink() or not archive.is_dir() or archive.resolve(strict=True) != archive:
        result['phase_evidence'] = 'archive_path_unsafe'
        return result
    result['phase_evidence'] = 'archive_created'
    result['presence'] = {name: (archive / name).exists() or (archive / name).is_symlink()
        for name in ('source-bundle.json', 'before.sqlite3', 'previous-source', 'failure.json', 'deployment.json')}
    failure = archive / 'failure.json'
    if not result['presence']['failure.json']:
        return result
    if failure.is_symlink() or not failure.is_file() or failure.stat().st_size > 65536:
        result['phase_evidence'] = 'failure_record_unreadable'
        return result
    try:
        value = bounded_json(failure.read_text())
    except (UnicodeError, OSError):
        value = None
    if value is None:
        result['phase_evidence'] = 'failure_record_invalid'
        return result
    result['phase_evidence'] = 'failure_recorded'
    result['failure'] = {'status': token(value.get('status'), {'failed'}),
        'code': token(value.get('code'), {'rollback_requires_service_quiescence', 'compatible_source_recovery_not_proven'})
            if value.get('code') is not None else None}
    for key in ('previous_service_restarted', 'installed_files_preserved', 'rollback_performed',
                'owner_credentials_preserved', 'database_restored'):
        result['failure'][key] = value.get(key) if type(value.get(key)) is bool else None
    return result


def observe_http(label):
    need(label in HEALTH_ENDPOINTS, 'diagnostic_http_scope_invalid')
    start = time.monotonic()
    result = {'http_status': None, 'error': None}
    try:
        response = subprocess.run(['curl', '--silent', '--output', os.devnull,
            '--write-out', '%{http_code}', '--max-time', '8', '--connect-timeout', '3',
            '--max-filesize', '4096', '--proto', '=http,https', '--max-redirs', '0',
            HEALTH_ENDPOINTS[label]], capture_output=True, timeout=10, check=False)
        raw = response.stdout
        if len(raw) == 3 and raw.isdigit() and 100 <= int(raw) <= 599:
            result['http_status'] = int(raw)
        if response.returncode:
            result['error'] = {6: 'dns_error', 7: 'connect_error', 28: 'timeout',
                35: 'tls_error', 60: 'tls_error', 63: 'response_too_large'}.get(response.returncode, 'http_transport_error')
        elif result['http_status'] is None:
            result['error'] = 'invalid_http_status'
    except subprocess.TimeoutExpired:
        result['error'] = 'process_timeout'
    except FileNotFoundError:
        result['error'] = 'http_tool_unavailable'
    except OSError:
        result['error'] = 'http_tool_error'
    result['elapsed_ms'] = max(0, round((time.monotonic() - start) * 1000))
    return result


def run(envelope):
    import fcntl
    need(os.getuid() == 0 and envelope.get('payload') == {'source_commit': SOURCE}, 'diagnostic_scope_invalid')
    # Existing lock only; no creation, no changes to service, configuration, DB or application files.
    # Ubuntu's /var/lock aliases /run/lock; use the canonical inode path here.
    with regular(Path('/run/lock/analyst-ai-plan-development.lock')).open('rb') as lock:
        fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        verify_source(Path('/opt/analyst-ai/backend'))
        now = int(time.time())
        service_rows = services()
        result = {'schema': 1, 'status': 'observed', 'server_id': 9417611, 'source_commit': SOURCE,
            'observed_at': stamp(now), 'database': observe_database(Path('/var/lib/analyst-ai/backend.db'), now),
            'services': service_rows, 'failed_release': observe_release_archive(),
            'owner_thread_waits': process_waits(service_rows['analyst-ai-owner.service']['main_pid']),
            'stack_sampler_installed': shutil.which('py-spy') is not None,
            'http': {label: observe_http(label) for label in HEALTH_ENDPOINTS},
            'exact_source_verified': True, 'order_lifecycle_source_verified': True,
            'real_trading_activation_verified': False,
            'application_imported': False, 'broker_called': False,
            'model_called': False, 'database_written': False, 'service_changed': False}
        verify_source(Path('/opt/analyst-ai/backend'))
        print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == '__main__':
    try:
        run(ENVELOPE)
    except Exception:
        # No exception text/traceback can expose DB contents or process output.
        print(json.dumps({'status': 'failed', 'code': 'read_only_runtime_observation_failed', 'server_id': 9417611}), flush=True)
        raise SystemExit(1) from None
