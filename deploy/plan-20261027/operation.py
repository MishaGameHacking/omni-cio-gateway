"""Deploy only the exact checked runtime layer on the existing owner server.

No database is opened by this deployer. No environment, signature, APK, broker
binding, AI budget or trading mode is modified. Interdependent Python files are
replaced only while the owner service is stopped, with checked rollback copies.
"""
from pathlib import Path
import base64
import datetime
import fcntl
import gzip
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import time
import urllib.error
import urllib.request

ROOT=Path('/var/lib/analyst-ai-build/development')
SOURCE=ROOT/'candidate-runtime-hardened-40472430619'
CHECK=ROOT/'runtime-hardened-check-40472430619'
BASE=ROOT/'candidate-n02-n04-r4-20261027-20261027T061309Z-ea5fd07f'
RUNTIME=Path('/opt/analyst-ai/backend')
OWNER='analyst-ai-owner.service'
UPDATER='analyst-ai-updates.service'
ORIGIN='https://analyst-ai-2941515.twc1.net'
PACKAGE='ru.omnicio.app.debug'
CERTIFICATE='bbce9534fd4cfee8f3bdcaf51a31cce384a4f303f090c8cae9ec558227d59eb1'
RUN_ID=ENVELOPE['run_id']
if re.fullmatch(r'[0-9]+',RUN_ID) is None:raise RuntimeError('invalid_run_identity')
FILES=('volume_market.py','volume_workspace.py','portfolio_accounting.py','paper_execution.py',
       'source_observability.py','application_hierarchy.py','workspace_readiness.py')
EXPECTED_OLD={'volume_market.py':'5254e7eef732a28db8e3e3ed63b73a65b29ccdb983b78da686ce0bb3500ea87e',
 'volume_workspace.py':'f555bd502addede8ade3068231322e7ad5c702f83da7d37ee5821a0cb14b2452'}
lock=open('/var/lock/analyst-ai-plan-development.lock','a')
fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
receipt_raw=(CHECK/'receipt.json').read_bytes()
if hashlib.sha256(receipt_raw).hexdigest()!='3c40b314a367b98a2f0b678143c6388a61e0814b8f6f9e161010d0d5fc1b649c':
 raise RuntimeError('checked_receipt_identity_mismatch')
checked=json.loads(receipt_raw)
if checked.get('status')!='passed' or checked.get('full_backend')!={'tests':3573,'failures':0,'errors':0,'skipped':0}:
 raise RuntimeError('full_backend_acceptance_missing')
manifest_raw=(CHECK/'source-manifest.json').read_bytes()
if hashlib.sha256(manifest_raw).hexdigest()!='757605b0d8f59b150e481a2d96186d1ae17f74269ce745a2385ed5f2f21bebd8':
 raise RuntimeError('checked_manifest_identity_mismatch')
manifest=json.loads(manifest_raw)
for relative,expected in manifest.items():
 path=SOURCE/relative
 if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
  raise RuntimeError('checked_source_changed')

def command(args,timeout=60):
 result=subprocess.run(args,capture_output=True,timeout=timeout)
 if result.returncode:raise RuntimeError('bounded_administrative_command_failed')
 return result.stdout

def service(name):
 output=command(['systemctl','show',name,'--property=ActiveState,SubState,MainPID,NRestarts']).decode()
 return dict(line.split('=',1) for line in output.splitlines() if '=' in line)

def digest_file(path):
 if path.is_symlink() or not path.is_file():raise RuntimeError('regular_file_required')
 return hashlib.sha256(path.read_bytes()).hexdigest()

class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None
HTTP=urllib.request.build_opener(NoRedirect())

def response(url,limit=65536):
 request=urllib.request.Request(url,headers={'Accept':'application/json','Cache-Control':'no-cache'})
 try:
  with HTTP.open(request,timeout=12) as result:
   data=result.read(limit+1)
   if len(data)>limit:raise RuntimeError('http_evidence_limit')
   return result.status,data
 except urllib.error.HTTPError as error:
  return error.code,error.read(min(limit,4096))

def policy():
 status,raw=response(ORIGIN+'/client/update-policy?package_name='+PACKAGE)
 if status!=200:raise RuntimeError('public_policy_unavailable')
 value=json.loads(raw)
 if (value.get('package_name')!=PACKAGE or value.get('certificate_sha256')!=CERTIFICATE
     or type(value.get('version_code')) is not int or value['version_code']<49
     or type(value.get('apk_bytes')) is not int or not 1024*1024<value['apk_bytes']<=256*1024*1024
     or not isinstance(value.get('apk_sha256'),str) or re.fullmatch(r'[0-9a-f]{64}',value['apk_sha256']) is None):
  raise RuntimeError('existing_public_channel_identity_unverified')
 expected='/client/apk/Analyst-AI-'+str(value['version_code'])+'-'+value['apk_sha256']+'.apk'
 if value.get('apk_path')!=expected:raise RuntimeError('existing_apk_path_mismatch')
 return value

def apk_proof(value):
 count=0;sha=hashlib.sha256();begin=time.monotonic()
 with HTTP.open(urllib.request.Request(ORIGIN+value['apk_path'],headers={'Accept':'application/vnd.android.package-archive'}),timeout=15) as downloaded:
  if downloaded.status!=200:raise RuntimeError('apk_download_http_failure')
  while True:
   block=downloaded.read(1024*1024)
   if not block:break
   count+=len(block)
   if count>value['apk_bytes'] or time.monotonic()-begin>90:raise RuntimeError('apk_download_limit')
   sha.update(block)
 if count!=value['apk_bytes'] or sha.hexdigest()!=value['apk_sha256']:raise RuntimeError('existing_apk_bytes_mismatch')
 return {'bytes':count,'sha256':sha.hexdigest(),'full_https_download_verified':True,
         'certificate_policy_sha256':value['certificate_sha256'],'new_apk_published':False}

def wait_local_health():
 for _ in range(15):
  try:
   status,raw=response('http://127.0.0.1:8080/health')
   if status==200 and json.loads(raw)=={'status':'ok'}:return
  except (OSError,ValueError,urllib.error.URLError):pass
  time.sleep(1)
 raise RuntimeError('owner_health_not_restored')

def unchanged_runtime():
 for path in (BASE/'backend').glob('*.py'):
  target=RUNTIME/path.name
  if not target.is_file() or target.is_symlink() or digest_file(target)!=digest_file(path):
   raise RuntimeError('runtime_no_longer_matches_reviewed_base')
 for name in FILES:
  target=RUNTIME/name
  if name in EXPECTED_OLD:
   if digest_file(target)!=EXPECTED_OLD[name]:raise RuntimeError('runtime_expected_file_changed')
  elif target.exists() or target.is_symlink():raise RuntimeError('new_runtime_file_already_exists')

unchanged_runtime()
owner_before=service(OWNER);updater_before=service(UPDATER)
if any(item.get('ActiveState')!='active' or item.get('SubState')!='running' for item in (owner_before,updater_before)):
 raise RuntimeError('existing_runtime_service_not_healthy')
policy_before=policy()
if response(ORIGIN+'/health')[0]!=200:raise RuntimeError('public_health_precondition_failed')
environment=Path('/etc/analyst-ai/backend.env')
env_sha=digest_file(environment)
unit_sha=hashlib.sha256(command(['systemctl','cat',OWNER,UPDATER])).hexdigest()
change='runtime-layer-20261027-'+RUN_ID
rollback=Path('/opt/analyst-ai/.backend-deployments')/change
rollback.mkdir(mode=0o700)
(rollback/'old').mkdir(mode=0o700);(rollback/'stage').mkdir(mode=0o700)
evidence=ROOT/('runtime-layer-deployment-'+RUN_ID);evidence.mkdir(mode=0o700)
records={}
for name in FILES:
 target=RUNTIME/name;raw=(SOURCE/'backend'/name).read_bytes()
 if hashlib.sha256(raw).hexdigest()!=manifest['backend/'+name]:raise RuntimeError('deployment_source_hash_mismatch')
 info=target.stat() if target.exists() else (RUNTIME/'app.py').stat()
 old=None
 if target.exists():
  old={'sha256':digest_file(target),'bytes':target.stat().st_size}
  shutil.copy2(target,rollback/'old'/name)
 stage=rollback/'stage'/name
 with stage.open('xb') as output:output.write(raw);output.flush();os.fsync(output.fileno())
 os.chown(stage,info.st_uid,info.st_gid);stage.chmod(stat.S_IMODE(info.st_mode))
 records[name]={'old':old,'new':{'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}}
# Compile with the real runtime interpreter without importing the application.
compile_code='import pathlib,sys; p=pathlib.Path(sys.argv[1]); [compile(x.read_text(),str(x),"exec") for x in p.glob("*.py")]; print("SYNTAX_OK")'
command(['/opt/analyst-ai/venv/bin/python','-B','-c',compile_code,str(rollback/'stage')])
report={'schema':1,'server_id':9417611,'change_id':change,'github_sha':ENVELOPE['github_sha'],
 'source_directory':str(SOURCE),'checked_source_manifest_sha256':hashlib.sha256(manifest_raw).hexdigest(),
 'test_run':40472430619,'test_receipt_sha256':hashlib.sha256(receipt_raw).hexdigest(),
 'full_backend':checked['full_backend'],'targeted':checked['targeted'],'files':records,
 'rollback_directory':str(rollback),'database_opened_by_deployer':False,
 'real_orders_requested':False,'paid_ai_requested':False,'new_resources_created':False,
 'apk_changed':False,'native_android_acceptance_passed':False,'sonar_passed':False,
 'started_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'phase':'staged','status':'pending'}
installed=[];stopped=False
try:
 command(['systemctl','stop',OWNER]);stopped=True
 if service(OWNER).get('ActiveState') not in {'inactive','failed'}:raise RuntimeError('owner_did_not_stop')
 unchanged_runtime()
 if digest_file(environment)!=env_sha:raise RuntimeError('configuration_changed_before_replacement')
 for name in FILES:
  os.replace(rollback/'stage'/name,RUNTIME/name);installed.append(name)
 descriptor=os.open(RUNTIME,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(descriptor)
 finally:os.close(descriptor)
 command(['systemctl','start',OWNER]);stopped=False
 wait_local_health()
 health={'local_health_http':200,'public_health_http':response(ORIGIN+'/health')[0]}
 if health['public_health_http']!=200:raise RuntimeError('public_health_failed')
 for route in ('/workspace','/workspace/system-readiness','/workspace/public-sources','/workspace/cash-ledger'):
  local=response('http://127.0.0.1:8080'+route)[0];public=response(ORIGIN+route)[0]
  health[route]={'noauth_local_http':local,'noauth_public_http':public}
  if local!=401 or public!=401:raise RuntimeError('private_route_authentication_failed')
 for name,row in records.items():
  if digest_file(RUNTIME/name)!=row['new']['sha256']:raise RuntimeError('deployed_source_hash_mismatch')
 if digest_file(environment)!=env_sha or hashlib.sha256(command(['systemctl','cat',OWNER,UPDATER])).hexdigest()!=unit_sha:
  raise RuntimeError('runtime_configuration_changed')
 if policy()!=policy_before:raise RuntimeError('existing_update_policy_changed')
 channel=apk_proof(policy_before)
 if policy()!=policy_before:raise RuntimeError('channel_changed_during_full_download')
 updater_after=service(UPDATER)
 if updater_after['MainPID']!=updater_before['MainPID'] or updater_after['ActiveState']!='active':
  raise RuntimeError('public_updater_process_changed')
 report.update(status='passed',phase='deployed',health=health,channel=channel,
  update_version_code=policy_before['version_code'],update_version_name=policy_before['version_name'],
  min_sdk=policy_before['min_sdk'],environment_unchanged=True,service_units_unchanged=True,
  updater_pid_unchanged=True,owner_service=service(OWNER),rollback_performed=False)
except Exception as error:
 report.update(status='failed',error_type=type(error).__name__,error_code=str(error) if isinstance(error,RuntimeError) else 'deployment_or_verification_error')
 if installed or stopped:
  try:
   command(['systemctl','stop',OWNER])
   for name in reversed(installed):
    target=RUNTIME/name
    if digest_file(target)!=records[name]['new']['sha256']:raise RuntimeError('rollback_parallel_change_detected')
    if records[name]['old'] is None:target.unlink()
    else:
     temporary=rollback/'stage'/('restore-'+name)
     shutil.copy2(rollback/'old'/name,temporary)
     os.replace(temporary,target)
   command(['systemctl','start',OWNER]);wait_local_health()
   report['rollback_succeeded']=True
  except Exception as rollback_error:
   report['rollback_succeeded']=False;report['rollback_error_type']=type(rollback_error).__name__
 report['finished_at_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
 (evidence/'deployment.json').write_text(json.dumps(report,indent=2)+'\n')
 print('RUNTIME_DEPLOYMENT='+json.dumps(report,indent=2),flush=True)
 raise SystemExit(1)

report['finished_at_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
(evidence/'deployment.json').write_text(json.dumps(report,indent=2)+'\n')
# Runtime succeeded; handoff writing cannot roll back an otherwise healthy service.
notes=f'''# Analyst AI: проверенное серверное обновление 27.10.2026\n\nСерверный слой обновлён на Timeweb 9417611: **{report['finished_at_utc']}**.\nЭто обновление backend, не новый APK и не завершение всего плана N00–N11.\n\n## Фактически применено\n\n- Исправлена начальная UTC-дата TradingSchedules, ранее вызывавшая HTTP 400.\n- Добавлены source_observability, application_hierarchy и workspace_readiness.\n- Доступен защищённый GET /workspace/system-readiness; /workspace получает\n  дополнительную секцию system и capabilities public_sources/cash_ledger/system_readiness.\n- Разделены время оценки портфеля, публикации, получения и проверки сведений.\n  Конфликты источников, будущие/неверные даты и неполнота отражаются явно.\n- Установлены чистые библиотеки portfolio_accounting и paper_execution.\n  Сверка/TWR/XIRR требуют полных подтверждённых входов; живой результат владельца\n  ими ещё не вычисляется. Исполнитель остаётся симулятором без брокерского транспорта.\n\n## Проверки\n\n[Timeweb acceptance 40472430619](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40472430619):\n2016 тестов и1557 subtests прошли;59 целевых тестов прошли.\nВ12 сценариях повреждённых данных прежний код дал8 FAIL; исправленный прошёл все.\nИсторические неуспешные отчёты сохранены; проверки не ослаблялись.\nОстаётся одно предупреждение зависимости Starlette о deprecated AnyIO BlockingPortal.\nПроверены три синтетических сценария журнала, offline CLI, health/OpenAPI и авторизация.\nЭто не тесты телефона, не sandbox-брокер и не Sonar для полного выпуска.\n\n## Доставка и сохранность\n\n[Развёртывание {RUN_ID}](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/{RUN_ID}).\nСемь файлов заменены при остановленной owner-службе; прежние байты сохранены\nдля отката. Health локально и по HTTPS —200, закрытые маршруты без входа —401.\nDeployer не открывал БД; env и systemd units не изменились, updater не перезапускался.\nПакет и канал сохранены: {PACKAGE}, {policy_before['version_name']} /code{policy_before['version_code']}.\nВесь публичный APK повторно скачан: {channel['bytes']} байт, SHA256 {channel['sha256']}.\nminSdk={policy_before['min_sdk']}. Новый APK не выпускался, установка на телефоне не подтверждена.\nНативный экран для нового API пока не включён в APK.\n\n## Точная точка продолжения\n\nРабочий backend: /opt/analyst-ai/backend.\nПолный проверенный кандидат: {SOURCE}.\nМанифест Python-исходников SHA256: {hashlib.sha256(manifest_raw).hexdigest()}.\nПриёмка: {CHECK}. Доставка: {evidence}. Откат: {rollback}.\n[Иерархия](RUNTIME_HIERARCHY_2026-10-27.md).\n\n## Не завершено\n\nАвтоматический проверенный охват четырёх КРА и финансовой отчётности, полный\nденежный учёт и независимая сверка реального счёта, полный планировщик и\nсквозная оценка риска/ИИ, sandbox-исполнение, новая нативная приёмка,\nexact-head Sonar,30 реальных торговых сессий и кандидат полного выпуска.\nРеальные поручения и платные AI-вызовы этим обновлением не включены.\nGitHub — резервная копия; дальнейшие изменения/сборки/тесты выполнять на Timeweb.\n'''
release_relative='docs/RUNTIME_LAYER_RELEASE_2026-10-27.md'
(SOURCE/release_relative).write_text(notes,encoding='utf-8')
header=f'''## Актуальная точка продолжения —27.10.2026, серверный слой runtime-layer\n\nПроверенный серверный пакет применён: {report['finished_at_utc']}.\n[Фактические изменения, тесты, хеши и ограничения](docs/RUNTIME_LAYER_RELEASE_2026-10-27.md).\nРазработка, сборки и тесты — существующий Timeweb9417611; GitHub — резервная копия.\nКандидат: {SOURCE}.\n2016tests+1557subtests PASS;59 новых проверок слоя PASS.\nAPK {policy_before['version_code']} сохранён, новый APK не выпускался. Полный N00–N11 не завершён.\nНативная приёмка, Sonar, реальный денежный учёт, четыре КРА и sandbox остаются открытыми.\nРеальные поручения/платные AI-вызовы не включать. Старые записи ниже — история.\n\n---\n\n'''
export_files={}
for path,expected in checked['changed_files'].items():
 raw=(SOURCE/path).read_bytes()
 if hashlib.sha256(raw).hexdigest()!=expected['sha256']:raise RuntimeError('handoff_source_changed')
 export_files[path]=raw.decode('utf-8')
export_files['docs/RUNTIME_HIERARCHY_2026-10-27.md']=(SOURCE/'docs/RUNTIME_HIERARCHY_2026-10-27.md').read_text()
export_files[release_relative]=notes
export_files['docs/timeweb-2026-10-27/evidence/runtime-layer-deployment.json']=json.dumps(report,indent=2)+'\n'
export_files['docs/timeweb-2026-10-27/evidence/runtime-hardened-check.json']=receipt_raw.decode()
export_files['docs/timeweb-2026-10-27/evidence/runtime-layer-source-manifest.json']=manifest_raw.decode()
for name in ('AGENTS.md','README.md'):
 text=header+(SOURCE/name).read_text()
 (SOURCE/name).write_text(text)
 export_files[name]=text
pointer={'schema':1,'server_id':9417611,'source_directory':str(SOURCE),'evidence_directory':str(evidence),
 'check_run':40472430619,'deployment_run':int(RUN_ID),'python_source_manifest_sha256':hashlib.sha256(manifest_raw).hexdigest(),
 'status':'deployed','apk_changed':False,'update_version_code':policy_before['version_code'],
 'full_plan_complete':False,'finished_at_utc':report['finished_at_utc']}
(ROOT/('current-source-runtime-layer-'+RUN_ID+'.json')).write_text(json.dumps(pointer,indent=2)+'\n')
export={'schema':1,'base_commit':'40b261af67eca24a5131be2d5b99e06f73224817','deployment_run':int(RUN_ID),
 'deployment_github_sha':ENVELOPE['github_sha'],'check_run':40472430619,
 'source_manifest_sha256':hashlib.sha256(manifest_raw).hexdigest(),
 'files':{path:{'content':text,'sha256':hashlib.sha256(text.encode()).hexdigest()} for path,text in export_files.items()}}
export_raw=json.dumps(export,sort_keys=True,ensure_ascii=False).encode()
if len(export_raw)>2*1024*1024:raise RuntimeError('source_backup_export_limit')
(evidence/'source-export.json').write_bytes(export_raw)
print('RUNTIME_DEPLOYMENT='+json.dumps(report,indent=2),flush=True)
print('SOURCE_EXPORT='+base64.b64encode(gzip.compress(export_raw,mtime=0)).decode(),flush=True)
