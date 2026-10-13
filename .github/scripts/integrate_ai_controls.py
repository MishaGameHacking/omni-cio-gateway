"""One-use, source-only patch for the reviewed main baseline. No cloud operations.

Transforms pinned text files; a separate CI step must pass all backend tests
before committing them. This does not install the context-minimization
module or change the paused deployment workflow.
"""
from __future__ import annotations
import ast
import hashlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPECTED = {
    'backend/autonomous_ai.py': '819f468b6d9d11f726e1f7609438fcde1ab98d17',
    'backend/tests/test_reliability_041.py': '860a72405b961078b5f71560ea56bae37ac6ca5c',
    'README.md': '8be05ef2812d46a95aca46884ad2da8ce9d64899',
    'backend/analysis_engine.py': 'a973dff7bc1ca5edf108320bdbcaeff47f311d54',
}


def read(path):
    data = subprocess.check_output(['git', 'show', 'HEAD:' + path], cwd=ROOT)
    # Git's blob identifier is SHA-1 by specification; not a security signature.
    digest = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data, usedforsecurity=False).hexdigest()
    if digest != EXPECTED[path]:
        raise RuntimeError('Source baseline changed: ' + path)
    return data.decode()


def replace(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError('Source anchor missing or ambiguous: ' + old[:60])
    return text.replace(old, new, 1)


def function(text, name, replacement):
    nodes = [n for n in ast.parse(text).body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]
    if len(nodes) != 1:
        raise RuntimeError('Function anchor missing: ' + name)
    node = nodes[0]
    lines = text.splitlines(keepends=True)
    return ''.join(lines[:node.lineno-1]) + replacement.rstrip() + '\n' + ''.join(lines[node.end_lineno:])


engine = read('backend/analysis_engine.py')
engine = replace(engine, '    gateway = client or TimewebAIClient()',
    '    if client is None:\n        raise AnalysisValidationError("analysis_explicit_client_required")\n    gateway = client')
ast.parse(engine)
(ROOT / 'backend/analysis_engine.py').write_text(engine, encoding='utf-8', newline='\n')

code = read('backend/autonomous_ai.py')
imports = '''try:
    from .ai_budget import MoneyLedger, BudgetDenied
    from .ai_jobs import AnalysisQueue, CURRENT_JOB, drain, assert_current_owner_in
    from .ai_guarded_client import GuardedAIClient, GuardError
except ImportError:  # uvicorn top-level import compatibility
    from ai_budget import MoneyLedger, BudgetDenied
    from ai_jobs import AnalysisQueue, CURRENT_JOB, drain, assert_current_owner_in
    from ai_guarded_client import GuardedAIClient, GuardError

'''
code = replace(code, 'logger = logging.getLogger(__name__)', imports + 'logger = logging.getLogger(__name__)')
code = replace(code, '        db.commit()\n\n\ndef _profile_from_row',
               '        db.commit()\n    AnalysisQueue(backend.connect).initialize()\n    MoneyLedger(backend.connect).initialize()\n\n\ndef _profile_from_row')
# The original table writers now check the worker fence inside their write lock.
for name in ('_save_snapshot', '_record_run', '_insert_card'):
    node = next(n for n in ast.parse(code).body if isinstance(n, ast.FunctionDef) and n.name == name)
    original = ''.join(code.splitlines(keepends=True)[node.lineno-1:node.end_lineno])
    rewritten = replace(original, '    with closing(backend.connect()) as db:',
        '    with closing(backend.connect()) as db:\n        db.execute("BEGIN IMMEDIATE")\n        assert_current_owner_in(db)')
    code = function(code, name, rewritten)
code = replace(code, '    # Archive the already fetched RUB valuation even when no LLM analysis is needed.',
'''    current_job = CURRENT_JOB.get()
    if current_job:
        AnalysisQueue(backend.connect).assert_owner(*current_job)
    # Archive the already fetched RUB valuation even when no LLM analysis is needed.''')
code = replace(code, '        TimewebAIConfig.from_env().model_for(decision.tier)',
'''        guarded_client = GuardedAIClient(user_id, backend.connect)
        guarded_client.check_ready(decision.tier)''')
code = replace(code, '            context=context,\n        )\n        decision = result.decision',
               '            context=context,\n            client=guarded_client,\n        )\n        decision = result.decision')
code = replace(code, '    except TimewebAIError as exc:\n        error_code = exc.code',
               '    except (TimewebAIError, GuardError, BudgetDenied) as exc:\n        error_code = getattr(exc, "code", str(exc))')
code = replace(code, '    _record_run(\n        user_id=user_id,',
               '    if current_job:\n        AnalysisQueue(backend.connect).assert_owner(*current_job)\n    _record_run(\n        user_id=user_id,')
code = function(code, 'run_scheduler_cycle', '''def run_scheduler_cycle() -> dict[str, int]:
    init_autonomous_db()
    queue = AnalysisQueue(backend.connect)
    with closing(backend.connect()) as db:
        users = db.execute("SELECT id FROM users WHERE tinvest_token_encrypted IS NOT NULL ORDER BY id").fetchall()
    for user in users:
        queue.enqueue(int(user['id']))
    return drain(queue, run_user_analysis)
''')
code = replace(code, '@router.post("/refresh")', '@router.post("/refresh", status_code=202)')
code = function(code, 'refresh', '''def refresh(
    _: RefreshRequest,
    user: sqlite3.Row = Depends(backend.current_user),
) -> dict[str, Any]:
    if not SCHEDULER_ENABLED:
        raise HTTPException(status_code=503, detail="analysis_scheduler_disabled")
    if user['tinvest_token_encrypted'] is None:
        raise HTTPException(status_code=409, detail="tinvest_not_connected")
    queue = AnalysisQueue(backend.connect)
    queue.initialize()
    return {**queue.enqueue(int(user['id'])), 'reason': 'queued_recheck',
            'tier': 'none', 'card_id': None, 'model': None, 'error_code': None}
''')
# Preserve every old Android status field, add private user-scoped diagnostics.
start = code.index('    ai_configured = bool(', code.index('def status('))
end = code.index('    return {', start)
code = code[:start] + '''    init_autonomous_db()
    readiness = []
    guarded = GuardedAIClient(user_id, backend.connect)
    for tier in (AnalysisTier.FAST, AnalysisTier.STANDARD, AnalysisTier.PREMIUM):
        try:
            guarded.check_ready(tier)
            readiness.append({'tier': tier.value, 'ready': True, 'reason': None})
        except (GuardError, BudgetDenied) as error:
            readiness.append({'tier': tier.value, 'ready': False, 'reason': str(error)})
    ai_configured = all(item['ready'] for item in readiness)
''' + code[end:]
code = replace(code, '        "ai_configured": ai_configured,', '''        "ai_configured": ai_configured,
        "route_readiness": readiness,
        "queue": AnalysisQueue(backend.connect).user_status(user_id),
        "spending": MoneyLedger(backend.connect).user_summary(user_id),
        "configuration_is_not_live_inference_proof": True,''')
ast.parse(code)
(ROOT / 'backend/autonomous_ai.py').write_text(code, encoding='utf-8', newline='\n')

tests = read('backend/tests/test_reliability_041.py')
tests = replace(tests, '''        with patch.object(ai, 'run_user_analysis', return_value={'state': 'skipped'}) as run:
            ai.refresh(ai.RefreshRequest(), user=self.user)
        run.assert_called_once_with(self.user_id, force=False)''', '''        with patch.object(ai, 'SCHEDULER_ENABLED', True), patch.object(ai, 'run_user_analysis') as run:
            result = ai.refresh(ai.RefreshRequest(), user=self.user)
        run.assert_not_called()
        self.assertEqual(result['state'], 'queued')
        self.assertEqual(result['tier'], 'none')''')
tests = replace(tests, "        with patch.dict(os.environ, environment), patch.object(ai, 'get_tinvest_portfolio', return_value=sample_snapshot(stock_share=90, cash_share=5)), patch.object(ai, 'analyze_if_needed', side_effect=TimewebAIUpstreamError('timeweb_ai_timeout', retryable=True)):",
"        with patch.dict(os.environ, environment), patch.object(ai.GuardedAIClient, 'check_ready'), patch.object(ai, 'get_tinvest_portfolio', return_value=sample_snapshot(stock_share=90, cash_share=5)), patch.object(ai, 'analyze_if_needed', side_effect=TimewebAIUpstreamError('timeweb_ai_timeout', retryable=True)):")
ast.parse(tests)
(ROOT / 'backend/tests/test_reliability_041.py').write_text(tests, encoding='utf-8', newline='\n')

readme = read('README.md')
readme = readme.replace('Версия 0.5.0 / versionCode 21.', 'Android: версия 0.5.1 / versionCode 22.')
readme = readme.replace('https://94.198.220.228.sslip.io/auth/telegram/callback', 'https://176.98.178.81.sslip.io/auth/telegram/callback')
readme += '''

## Новое серверное ядро анализа (требует отдельного развёртывания)

Очередь SQLite, атомарные резервы оценочной стоимости в рублях, отдельные маршруты
агентов/Gateway, ограничение адресов и диагностика добавлены в исходники.
Подробности и ограничения: `docs/AI_RELIABILITY_CONTROLS.md`.
Опубликованный Android APK остаётся 0.5.1. Обычное развёртывание Timeweb приостановлено;
эти исходники не считаются уже установленными на московский сервер.
Проверка места обработки — ручное подтверждение оператора, не геолокация модели.
Минимизация персонального контекста ещё не внедрена; не включать платную интеграцию
до проверки передаваемых данных и согласованной политики обработки.
'''
(ROOT / 'README.md').write_text(readme, encoding='utf-8', newline='\n')
print('Patched analysis engine, queue integration, regression contract and current documentation; no deployment.')

# Apply the same transaction fence to spending, under the reservation lock.
budget_path = ROOT / 'backend/ai_budget.py'
budget = budget_path.read_text(encoding='utf-8')
budget = replace(budget, 'ceiling: int, user_cap: int, project_cap: int, at: int | None = None) -> None:',
    'ceiling: int, user_cap: int, project_cap: int, at: int | None = None, job: tuple[str, str] | None = None) -> None:')
budget = replace(budget, "        with transaction(self.connect) as db:\n            if db.execute(\"SELECT 1 FROM ai_money_control WHERE name='paused'\").fetchone():",
    "        with transaction(self.connect) as db:\n            if job and not db.execute(\"SELECT 1 FROM ai_work_jobs WHERE id=? AND owner=? AND user_id=? AND status='running' AND expires_at>?\", (*job, user_id, now)).fetchone():\n                raise BudgetDenied('ai_worker_lease_lost')\n            if db.execute(\"SELECT 1 FROM ai_money_control WHERE name='paused'\").fetchone():")
ast.parse(budget)
budget_path.write_text(budget, encoding='utf-8', newline='\n')
guard_path = ROOT / 'backend/ai_guarded_client.py'
guard = replace(guard_path.read_text(encoding='utf-8'),
    "project_cap=micro_rub(self.env.get('AI_PROJECT_DAILY_RUB', '0')))",
    "project_cap=micro_rub(self.env.get('AI_PROJECT_DAILY_RUB', '0')), job=job)")
guard_path.write_text(guard, encoding='utf-8', newline='\n')
jobs_path = ROOT / 'backend/ai_jobs.py'
jobs = jobs_path.read_text(encoding='utf-8')
if 'def assert_current_owner_in' in jobs:
    raise RuntimeError('Fence helper already present')
jobs += '''


def assert_current_owner_in(db: sqlite3.Connection) -> None:
    """Call under the caller's write transaction, before persisting its result."""
    job = CURRENT_JOB.get()
    if job is None:
        return
    row = db.execute("SELECT 1 FROM ai_work_jobs WHERE id=? AND owner=? AND status='running' AND expires_at>?",
                     (*job, int(time.time()))).fetchone()
    if row is None:
        raise LeaseLost('analysis_worker_lease_lost')
'''
jobs_path.write_text(jobs, encoding='utf-8', newline='\n')
