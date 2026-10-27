"""Apply the source hierarchy and observability layer to an isolated Timeweb candidate.

Product sources are written, compiled and tested only on Timeweb 9417611.
This operation does not deploy, change runtime settings or touch the owner DB.
"""
from pathlib import Path
import ast
import datetime
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
import urllib.request
import xml.etree.ElementTree as ET

ROOT=Path('/var/lib/analyst-ai-build/development')
BASE=ROOT/'candidate-n08-40468678759'
PRIOR=ROOT/'n08-check-40468678759'
PYTHON=ROOT/'source49-check-20261027T055218Z-20765533/venv/bin/python'
BASE_MARKET='5254e7eef732a28db8e3e3ed63b73a65b29ccdb983b78da686ce0bb3500ea87e'
FILES={
 'backend/source_observability.py':'source_observability.py',
 'backend/application_hierarchy.py':'application_hierarchy.py',
 'backend/workspace_readiness.py':'workspace_readiness.py',
 'backend/tests/test_source_observability.py':'test_source_observability.py',
 'backend/tests/test_workspace_readiness.py':'test_workspace_readiness.py',
 'tools/inspect_runtime_hierarchy.py':'inspect_runtime_hierarchy.py',
}
lock=open('/var/lock/analyst-ai-plan-development.lock','a')
fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
prior=json.loads((PRIOR/'receipt.json').read_text())
if prior.get('status')!='passed' or prior.get('full_backend')!={'tests':3514,'failures':0,'errors':0,'skipped':0}:
 raise RuntimeError('verified_previous_candidate_missing')
raw_manifest=(PRIOR/'source-manifest.json').read_bytes()
if hashlib.sha256(raw_manifest).hexdigest()!='6592616c2387b1bb6603fd79769628b1f220e723d65e9cbe149ab68052162641':
 raise RuntimeError('previous_source_manifest_changed')
for path,expected in json.loads(raw_manifest).items():
 if hashlib.sha256((BASE/path).read_bytes()).hexdigest()!=expected:
  raise RuntimeError('previous_candidate_source_changed')
if hashlib.sha256(Path('/opt/analyst-ai/backend/volume_market.py').read_bytes()).hexdigest()!=BASE_MARKET:
 raise RuntimeError('runtime_changed_requires_fresh_review')
work=ROOT/('candidate-runtime-layer-'+ENVELOPE['run_id'])
evidence=ROOT/('runtime-layer-check-'+ENVELOPE['run_id'])
if work.exists() or evidence.exists():raise RuntimeError('new_candidate_already_exists')
shutil.copytree(BASE,work,ignore=shutil.ignore_patterns('.git','.venv','venv','__pycache__','.pytest_cache','build','.gradle'))
evidence.mkdir(mode=0o700)
for destination,filename in FILES.items():
 target=work/destination
 if target.exists():raise RuntimeError('source_addition_conflict')
 url='https://raw.githubusercontent.com/MishaGameHacking/omni-cio-gateway/'+ENVELOPE['github_sha']+'/deploy/plan-20261027/runtime-layer/'+filename
 with urllib.request.urlopen(url,timeout=20) as response:content=response.read(262145)
 if len(content)>262144:raise RuntimeError('source_transport_limit')
 target.parent.mkdir(parents=True,exist_ok=True)
 target.write_bytes(content)

# Additive API change over the exact preexisting workspace, not a second store.
workspace=work/'backend/volume_workspace.py'
if workspace.read_bytes()!=Path('/opt/analyst-ai/backend/volume_workspace.py').read_bytes():
 raise RuntimeError('workspace_runtime_source_changed')
text=workspace.read_text()
anchor='@router.get("", responses=HTTP_ERRORS)\ndef workspace('
addition='''@router.get("/system-readiness", responses=HTTP_ERRORS)
def system_readiness(user: Annotated[Any, Depends(backend.current_user)],
                     currency: Literal["RUB", "USD", "EUR"] = "RUB") -> dict:
    """Read only the authenticated current connection; never schedule work."""
    try:
        from .workspace_readiness import build_status
    except ImportError:
        from workspace_readiness import build_status
    return build_status(state.saved_snapshot(user, currency), state.active_strategy(int(user["id"])),
                        connected=bool(user["tinvest_token_encrypted"]))


'''
if text.count(anchor)!=1:raise RuntimeError('workspace_route_anchor_changed')
text=text.replace(anchor,addition+anchor)
anchor='    active = state.active_strategy(int(user["id"]))\n    exposures = state.exposure_data'
replacement='''    active = state.active_strategy(int(user["id"]))
    try:
        from .workspace_readiness import build_status
    except ImportError:
        from workspace_readiness import build_status
    sections["system"] = section(build_status(snapshot, active,
        connected=bool(user["tinvest_token_encrypted"])), as_of=observed)
    exposures = state.exposure_data'''
if text.count(anchor)!=1:raise RuntimeError('workspace_status_anchor_changed')
text=text.replace(anchor,replacement)
anchor='"frame_network_requests": False}, "requested_range"'
replacement='"frame_network_requests": False, "public_sources": True, "cash_ledger": True,\n                             "system_readiness": True}, "requested_range"'
if text.count(anchor)!=1:raise RuntimeError('workspace_capability_anchor_changed')
text=text.replace(anchor,replacement)
workspace.write_text(text)

# Preserve a conventional architecture document alongside the actual source.
doc=work/'docs/RUNTIME_HIERARCHY_2026-10-27.md'
doc.write_text('''# Analyst AI: исполняемая иерархия и наблюдаемость\n\nРазработка и проверки этого кандидата выполняются на существующем Timeweb 9417611.\nГраф N00–N11 находится в backend/application_hierarchy.py, построение статуса —\nв backend/workspace_readiness.py, проверка времён/ссылок — в backend/source_observability.py.\n\n## Ответственность слоёв\n\nAndroid отображает сохранённые серверные результаты и отправляет изменения настроек.\nvolume_workspace читает снимок текущего пользователя и брокерского подключения.\nworkspace_readiness объединяет уже прочитанные сведения без сети и записи.\nsource_observability раздельно оценивает время оценки портфеля, публикаций, операций,\nвыплат и календаря; существующие журналы остаются единственным источником данных.\napplication_hierarchy проверяет зависимости и не превращает наличие файла в приёмку этапа.\nportfolio_accounting предоставляет арифметику сверки/TWR/XIRR только при полных входных данных.\npaper_execution и run_paper_execution — изолированная симуляция без брокерского транспорта.\n\n## API\n\nGET /workspace/system-readiness требует прежнюю авторизацию. GET /workspace\nполучает дополнительную секцию system и три capability: public_sources, cash_ledger,\nsystem_readiness. Чтение не запускает брокера, ИИ, миграцию или фоновую задачу.\nНовое время evaluated_at не меняет valuation_as_of и времена свидетельств.\nНовый нативный экран для этого API ещё не включён в APK.\n\n## Проверка и границы\n\nПроверяются границы свежести, будущие/неверные даты, конфликты source IDs,\nнеразрешённые ссылки, независимость времени событий от оценки портфеля,\nотсутствие сети/записи при чтении, изоляция пользователей и смены брокерского токена.\nБесплатные внешние проекты не устанавливаются целиком; новая платная инфраструктура не нужна.\nНи одна из этих функций не включает реальную торговлю или платные AI-вызовы.\nПолный N00–N11, четыре КРА, независимый реальный денежный учёт, sandbox,\n30 торговых сессий и нативная приёмка не объявляются завершёнными.\n\n## Первичные технические основания\n\nhttps://developer.android.com/topic/architecture/recommendations\nhttps://developer.tbank.ru/invest/api/instruments-service-trading-schedules\nhttps://www.sqlite.org/lang_transaction.html\n''',encoding='utf-8')

# Immutable source manifest before running project checks.
def inventory():
 output={}
 for folder in ('backend','tools'):
  for path in sorted((work/folder).rglob('*.py')):
   if path.is_symlink():raise RuntimeError('source_symlink')
   output[str(path.relative_to(work))]=hashlib.sha256(path.read_bytes()).hexdigest()
 return output
manifest=inventory()
(evidence/'source-manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
for path in manifest:
 ast.parse((work/path).read_text(encoding='utf-8-sig'),filename=path)
launcher='set -eu; ip link set dev lo up || exit 71; test "$(ip -o link show | wc -l)" -eq 1 || exit 72; test -z "$(ip route show default)" || exit 73; exec "$@"'
env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','HOME':str(evidence),'PYTHONPATH':str(work),
 'PYTHONDONTWRITEBYTECODE':'1','PYTHONUNBUFFERED':'1','TELEGRAM_CLIENT_ID':'123456',
 'TELEGRAM_CLIENT_SECRET':'test-only','BACKEND_PUBLIC_URL':'https://example.invalid',
 'FERNET_KEY':'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=',
 'ANALYSIS_SCHEDULER_ENABLED':'false','AI_EXTERNAL_PROCESSING_APPROVED':'false'}
steps=[]
def check(name,args,limit=240):
 start=time.monotonic()
 result=subprocess.run(['unshare','--net','--','/bin/sh','-c',launcher,'isolated-check',str(PYTHON),*args],
  cwd=work,env={**env,'DATABASE_PATH':str(evidence/(name+'.sqlite3'))},capture_output=True,timeout=limit)
 data=result.stdout+result.stderr
 (evidence/(name+'.log')).write_bytes(data)
 summary=[line for line in data.decode(errors='replace').splitlines() if re.search(r'\d+ passed',line)]
 step={'name':name,'exit_code':result.returncode,'seconds':round(time.monotonic()-start,3),
  'external_network':False,'isolated_loopback':True,'log_sha256':hashlib.sha256(data).hexdigest(),'pytest_summary':summary[-1:]}
 steps.append(step);print('CHECK='+json.dumps(step),flush=True)
 if result.returncode:
  print(data.decode(errors='replace')[-16000:],flush=True)
  (evidence/'failed.json').write_text(json.dumps({'phase':name,'steps':steps,'runtime_changed':False},indent=2)+'\n')
  raise RuntimeError('runtime_layer_check_failed_'+name)
check('source-and-hierarchy',['-m','pytest','backend/tests/test_source_observability.py','backend/tests/test_workspace_readiness.py','-q','--junitxml='+str(evidence/'targeted.xml')])
check('full-backend',['-m','pytest','backend/tests','-q','--junitxml='+str(evidence/'full.xml')],limit=300)
check('offline-hierarchy',['tools/inspect_runtime_hierarchy.py','--output',str(evidence/'hierarchy.json')])
check('paper-scenarios',['tools/run_paper_execution.py','--output-directory',str(evidence/'paper-scenarios')])
check('health-openapi',['-c',"from fastapi.testclient import TestClient; from backend.app import app; c=TestClient(app); assert c.get('/health').status_code==200; spec=c.get('/openapi.json'); assert spec.status_code==200; assert '/workspace/system-readiness' in spec.json()['paths']; assert c.get('/workspace/system-readiness').status_code==401; print('HEALTH_OPENAPI_AUTH_OK')"])
def totals(path):
 root=ET.parse(path).getroot();suites=[root] if root.tag=='testsuite' else list(root.iter('testsuite'))
 return {key:sum(int(s.attrib.get(key,0)) for s in suites) for key in ('tests','failures','errors','skipped')}
if inventory()!=manifest:raise RuntimeError('source_changed_during_checks')
changed={**{path:value['sha256'] for path,value in prior['changed_files'].items()},
         **{path:manifest[path] for path in FILES},'backend/volume_workspace.py':manifest['backend/volume_workspace.py']}
report={'schema':1,'status':'passed','server_id':9417611,'github_sha':ENVELOPE['github_sha'],
 'source_directory':str(work),'evidence_directory':str(evidence),'steps':steps,
 'targeted':totals(evidence/'targeted.xml'),'full_backend':totals(evidence/'full.xml'),
 'changed_files':{path:{'sha256':value,'bytes':(work/path).stat().st_size} for path,value in changed.items()},
 'python_source_manifest_sha256':hashlib.sha256((evidence/'source-manifest.json').read_bytes()).hexdigest(),
 'runtime_changed':False,'real_orders_enabled':False,'paid_ai_called':False,'new_database_server_created':False,
 'apk_built':False,'sandbox_tested':False,'sonar_passed':False,'native_android_acceptance_passed':False,
 'previous_check_run':40468678759,'finished_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
(evidence/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
print('VERIFIED_RUNTIME_LAYER='+json.dumps(report,indent=2),flush=True)
