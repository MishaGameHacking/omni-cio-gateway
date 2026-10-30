"""One-shot bounded observation of existing runtime; no application imports or writes."""
from __future__ import annotations

from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import time

SOURCE = 'cc22cb7ee3fe82eca28e4162e13c4463cab5ddc4'
INSTALLED = {
    'autonomous_controller.py': 'cbb25165004afd4f33a2a76cabc13e56c4c458609303a018bb32bd267e832d83',
    'decision_cycle.py': 'a46331652844cde45ae8d63a2887d97da121d55948cc125844a15b99fe181e95',
    'decision_views.py': 'e3ca67c74957973b2bf3d9b4ac5e82efe0fcd710801ee49675f76d8645e41558',
    'margin_policy.py': '8fa653fa401ee5cc322784d92169475022dc463670d218cf854f285b6e609aa3',
    'purchase_policy.py': '36508ad0a99af467d9d0f44a9c26fafb45d16c212b5ae5fc027cab2a5f351eab',
    'strategy_actions.py': 'c0d327eb94a085ef2feb6b2dd5efb44ebdc7c565c41f2964019ab9d8fb01e053',
    'volume_chat.py': 'fb1b433d9eb1037955991233f6365a600994999628db89cbe56ac3a431b8cfe8',
    'volume_live.py': '7698a89a3b34a03d262e095d3993e1fb00b7c1805b675a3acf5c90b152cd4d5e',
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
        output = subprocess.run(['systemctl', 'show', name, '--property=ActiveState,SubState,NRestarts'],
                                capture_output=True, timeout=10, check=True).stdout.decode()
        values = dict(line.split('=', 1) for line in output.splitlines() if '=' in line)
        restarts = values.get('NRestarts', '')
        result[name] = {'active': token(values.get('ActiveState'), {'active', 'inactive', 'failed', 'activating', 'deactivating'}),
            'substate': token(values.get('SubState'), {'running', 'dead', 'failed', 'start-pre', 'auto-restart'}),
            'restarts': int(restarts) if restarts.isascii() and restarts.isdigit() and len(restarts) < 10 else None}
    return result


def verify_source(root):
    for name, expected in INSTALLED.items():
        path = regular(root / name)
        need(path.stat().st_size <= 524288, 'runtime_module_size_invalid')
        need(hashlib.sha256(path.read_bytes()).hexdigest() == expected, 'runtime_source_changed')


def run(envelope):
    import fcntl
    need(os.getuid() == 0 and envelope.get('payload') == {'source_commit': SOURCE}, 'diagnostic_scope_invalid')
    # Existing lock only; no creation, no changes to service, configuration, DB or application files.
    with regular(Path('/var/lock/analyst-ai-plan-development.lock')).open('rb') as lock:
        fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        verify_source(Path('/opt/analyst-ai/backend'))
        now = int(time.time())
        result = {'schema': 1, 'status': 'observed', 'server_id': 9417611, 'source_commit': SOURCE,
            'observed_at': stamp(now), 'database': observe_database(Path('/var/lib/analyst-ai/backend.db'), now),
            'services': services(), 'application_imported': False, 'broker_called': False,
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
