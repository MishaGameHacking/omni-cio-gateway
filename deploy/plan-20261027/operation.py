"""Check malformed persisted-input regressions in isolated Timeweb copies.

The checked prior candidate and runtime are not overwritten. No owner database,
broker calls or paid model calls are used by this acceptance operation.
"""
from pathlib import Path
import datetime
import fcntl
import hashlib
import json
import re
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET

ROOT=Path('/var/lib/analyst-ai-build/development')
BASE=ROOT/'candidate-runtime-layer-40471432615'
PRIOR=ROOT/'runtime-layer-check-40471432615'
PYTHON=ROOT/'source49-check-20261027T055218Z-20765533/venv/bin/python'
BASE_MARKET='5254e7eef732a28db8e3e3ed63b73a65b29ccdb983b78da686ce0bb3500ea87e'
lock=open('/var/lock/analyst-ai-plan-development.lock','a')
fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
prior=json.loads((PRIOR/'receipt.json').read_text())
if prior.get('status')!='passed' or prior.get('full_backend')!={'tests':3561,'failures':0,'errors':0,'skipped':0}:
 raise RuntimeError('verified_prior_layer_missing')
manifest_raw=(PRIOR/'source-manifest.json').read_bytes()
if hashlib.sha256(manifest_raw).hexdigest()!='17befdc650d4d174b32292d6e89f47509d23d07b9864cca658e2d33fdfbf5b23':
 raise RuntimeError('prior_manifest_changed')
for path,expected in json.loads(manifest_raw).items():
 if hashlib.sha256((BASE/path).read_bytes()).hexdigest()!=expected:raise RuntimeError('prior_source_changed')
if hashlib.sha256(Path('/opt/analyst-ai/backend/volume_market.py').read_bytes()).hexdigest()!=BASE_MARKET:
 raise RuntimeError('runtime_changed_before_check')
work=ROOT/('candidate-runtime-hardened-'+ENVELOPE['run_id'])
evidence=ROOT/('runtime-hardened-check-'+ENVELOPE['run_id'])
old=ROOT/('runtime-malformed-baseline-'+ENVELOPE['run_id'])
for path in (work,evidence,old):
 if path.exists():raise RuntimeError('acceptance_path_already_exists')
ignore=shutil.ignore_patterns('.git','.venv','venv','__pycache__','.pytest_cache','build','.gradle')
shutil.copytree(BASE,work,ignore=ignore);shutil.copytree(BASE,old,ignore=ignore)
evidence.mkdir(mode=0o700)
test=r'''"""Malformed saved values never become readiness or crash normal status reads."""
from datetime import datetime, timezone
import pytest
from backend.source_observability import lane_inventory, news_inventory
from backend.workspace_readiness import build_status
NOW=datetime(2026,10,27,9,tzinfo=timezone.utc)

@pytest.mark.parametrize('value',[[],{},False,7])
def test_malformed_attempt_is_unknown_not_a_status_exception(value):
    data={'as_of':NOW.isoformat(),'event_monitor':{'news':value},'events':{'complete':True}}
    lane=next(row for row in lane_inventory(data,now=NOW) if row['id']=='events')
    assert lane['latest_attempt'] is None

@pytest.mark.parametrize('value',[[],{},False,7])
def test_malformed_account_identifier_is_not_selected(value):
    strategy={'config':{'mandate':{'account_id':value}}}
    result=build_status({'accounts':[{'id':'synthetic-owned'}],'positions':[]},strategy,connected=True,now=NOW)
    assert result['mandate']['selected_account_in_snapshot'] is False
    assert result['real_orders_enabled'] is False

def test_absent_news_are_not_reported_as_an_observation():
    assert news_inventory(None,now=NOW)['state']=='not_collected'

@pytest.mark.parametrize('identifier',['','x'*201])
def test_news_identity_must_be_nonempty_and_bounded(identifier):
    result=news_inventory({'events':{'items':[{'id':identifier,'published_at':NOW.isoformat()}]}},now=NOW)
    assert result['invalid_or_future_publications']==1

def test_empty_calendar_response_cannot_claim_complete_coverage():
    data={'calendar':{'state':'available','data':{'as_of':NOW.isoformat(),'exchanges':[]}}}
    lane=next(row for row in lane_inventory(data,now=NOW) if row['id']=='calendar')
    assert lane['coverage_complete'] is False
'''
test_path='backend/tests/test_readiness_malformed.py'
for root in (work,old):(root/test_path).write_text(test)

def replace_once(relative,before,after):
 path=work/relative;text=path.read_text()
 if text.count(before)!=1:raise RuntimeError('source_patch_anchor_changed')
 path.write_text(text.replace(before,after))
replace_once('backend/source_observability.py',
 'complete = calendar.get("state") == "available" and isinstance(raw.get("exchanges"), list)',
 'complete = (calendar.get("state") == "available" and isinstance(raw.get("exchanges"), list)\n                    and bool(raw["exchanges"]))')
replace_once('backend/source_observability.py',
 'attempt if attempt in {"available", "incomplete", "unavailable"} else None',
 'attempt if isinstance(attempt, str) and attempt in {"available", "incomplete", "unavailable"} else None')
replace_once('backend/source_observability.py',
 '    items = mapping(mapping(snapshot).get("events")).get("items", [])',
 '    if not isinstance(snapshot, dict) or "events" not in snapshot:\n        return {"state": "not_collected", "independent_confirmations": None}\n    items = mapping(mapping(snapshot).get("events")).get("items", [])')
replace_once('backend/source_observability.py',
 '        if not isinstance(item, dict) or not isinstance(item.get("id"), str):',
 '        if (not isinstance(item, dict) or not isinstance(item.get("id"), str)\n                or not 1 <= len(item["id"]) <= 200):')
replace_once('backend/workspace_readiness.py',
 '    account_present = bool(mandate) and mandate.get("account_id") in {',
 '    account_present = bool(mandate) and isinstance(mandate.get("account_id"), str) and mandate.get("account_id") in {')

def inventory(root):
 output={}
 for folder in ('backend','tools'):
  for path in sorted((root/folder).rglob('*.py')):
   if path.is_symlink():raise RuntimeError('source_symlink')
   output[str(path.relative_to(root))]=hashlib.sha256(path.read_bytes()).hexdigest()
 return output
manifest=inventory(work)
(evidence/'source-manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
launcher='set -eu; ip link set dev lo up || exit 71; test "$(ip -o link show | wc -l)" -eq 1 || exit 72; test -z "$(ip route show default)" || exit 73; exec "$@"'
env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','HOME':str(evidence),'PYTHONDONTWRITEBYTECODE':'1','PYTHONUNBUFFERED':'1',
 'TELEGRAM_CLIENT_ID':'123456','TELEGRAM_CLIENT_SECRET':'test-only','BACKEND_PUBLIC_URL':'https://example.invalid',
 'FERNET_KEY':'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=',
 'ANALYSIS_SCHEDULER_ENABLED':'false','AI_EXTERNAL_PROCESSING_APPROVED':'false'}
steps=[]
def check(name,source,args,expected=0,limit=240):
 start=time.monotonic()
 result=subprocess.run(['unshare','--net','--','/bin/sh','-c',launcher,'isolated-check',str(PYTHON),*args],
  cwd=source,env={**env,'PYTHONPATH':str(source),'DATABASE_PATH':str(evidence/(name+'.sqlite3'))},
  capture_output=True,timeout=limit)
 data=result.stdout+result.stderr;(evidence/(name+'.log')).write_bytes(data)
 lines=data.decode(errors='replace').splitlines()
 summary=[line for line in lines if re.search(r'\d+ passed',line)]
 step={'name':name,'exit_code':result.returncode,'seconds':round(time.monotonic()-start,3),
       'external_network':False,'log_sha256':hashlib.sha256(data).hexdigest(),'pytest_summary':summary[-1:]}
 steps.append(step);print('CHECK='+json.dumps(step),flush=True)
 if result.returncode!=expected:
  print(data.decode(errors='replace')[-16000:],flush=True)
  (evidence/'failed.json').write_text(json.dumps({'phase':name,'steps':steps,'runtime_changed':False},indent=2)+'\n')
  raise RuntimeError('hardened_check_failed_'+name)
check('malformed-baseline',old,['-m','pytest',test_path,'-q','--junitxml='+str(evidence/'baseline.xml')],expected=1)
check('source-and-hierarchy',work,['-m','pytest','backend/tests/test_source_observability.py','backend/tests/test_workspace_readiness.py',test_path,'-q','--junitxml='+str(evidence/'targeted.xml')])
check('full-backend',work,['-m','pytest','backend/tests','-q','--junitxml='+str(evidence/'full.xml')],limit=300)
check('offline-hierarchy',work,['tools/inspect_runtime_hierarchy.py','--output',str(evidence/'hierarchy.json')])
check('paper-scenarios',work,['tools/run_paper_execution.py','--output-directory',str(evidence/'paper-scenarios')])
check('health-openapi',work,['-c',"from fastapi.testclient import TestClient; from backend.app import app; c=TestClient(app); assert c.get('/health').status_code==200; assert '/workspace/system-readiness' in c.get('/openapi.json').json()['paths']; assert c.get('/workspace/system-readiness').status_code==401; print('HEALTH_OPENAPI_AUTH_OK')"])
def totals(path):
 root=ET.parse(path).getroot();suites=[root] if root.tag=='testsuite' else list(root.iter('testsuite'))
 return {key:sum(int(s.attrib.get(key,0)) for s in suites) for key in ('tests','failures','errors','skipped')}
if totals(evidence/'baseline.xml')!={'tests':12,'failures':8,'errors':0,'skipped':0}:raise RuntimeError('old_defects_not_reproduced_exactly')
if inventory(work)!=manifest:raise RuntimeError('candidate_source_changed')
if hashlib.sha256(Path('/opt/analyst-ai/backend/volume_market.py').read_bytes()).hexdigest()!=BASE_MARKET:raise RuntimeError('runtime_changed')
paths=set(prior['changed_files'])|{test_path}
report={'schema':1,'status':'passed','server_id':9417611,'github_sha':ENVELOPE['github_sha'],
 'source_directory':str(work),'evidence_directory':str(evidence),'steps':steps,
 'baseline':totals(evidence/'baseline.xml'),'targeted':totals(evidence/'targeted.xml'),'full_backend':totals(evidence/'full.xml'),
 'changed_files':{p:{'sha256':manifest[p],'bytes':(work/p).stat().st_size} for p in sorted(paths)},
 'python_source_manifest_sha256':hashlib.sha256((evidence/'source-manifest.json').read_bytes()).hexdigest(),
 'runtime_changed':False,'real_orders_enabled':False,'paid_ai_called':False,
 'apk_built':False,'sandbox_tested':False,'sonar_passed':False,'native_android_acceptance_passed':False,
 'previous_check_run':40471432615,'finished_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
(evidence/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
print('VERIFIED_HARDENED_LAYER='+json.dumps(report,indent=2),flush=True)
# Warnings are preserved, never renamed as clean Sonar results.
log=(evidence/'full-backend.log').read_text(errors='replace')
start=log.find('warnings summary')
if start>=0:print('PRESERVED_TEST_WARNINGS='+log[start:start+1800],flush=True)
