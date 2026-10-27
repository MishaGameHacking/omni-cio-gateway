"""Repeat the unchanged candidate checks with loopback inside the isolated network."""
from pathlib import Path
import datetime
import fcntl
import hashlib
import json
import os
import subprocess
import time
import xml.etree.ElementTree as ET

ROOT=Path('/var/lib/analyst-ai-build/development')
BASE=ROOT/'candidate-n02-n04-r4-20261027-20261027T061309Z-ea5fd07f'
WORK=ROOT/'candidate-calendar-40465756021'
OLD=ROOT/'calendar-regression-baseline-40465756021'
PYTHON=ROOT/'source49-check-20261027T055218Z-20765533/venv/bin/python'
EXPECTED={
 'backend/volume_market.py':'9c1536cfaddacc2e9bed9a21b24e868ba1a95267f38cf2bb362ec606fd26096c',
 'backend/portfolio_accounting.py':'719b349fe033e354b560d44234579ea5dd9826ec3a13c66c7739cf8d8e63ceef',
 'backend/tests/test_portfolio_accounting.py':'493930a9685845a94043c0c40d77c808d191f5942d1813c65ba744d54c01ea26',
}
BASE_MARKET='5254e7eef732a28db8e3e3ed63b73a65b29ccdb983b78da686ce0bb3500ea87e'
lock=open('/var/lock/analyst-ai-plan-development.lock','a')
fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
for path,expected in EXPECTED.items():
 if hashlib.sha256((WORK/path).read_bytes()).hexdigest()!=expected:raise RuntimeError('candidate_identity_changed')
for root in [BASE,OLD,Path('/opt/analyst-ai')]:
 if hashlib.sha256((root/'backend/volume_market.py').read_bytes()).hexdigest()!=BASE_MARKET:raise RuntimeError('baseline_or_runtime_changed')
regression='backend/tests/test_calendar_start_date.py'
if (WORK/regression).read_bytes()!=(OLD/regression).read_bytes():raise RuntimeError('baseline_test_differs')
EXPECTED[regression]=hashlib.sha256((WORK/regression).read_bytes()).hexdigest()
evidence=ROOT/('n02-n04-check-'+ENVELOPE['run_id'])
evidence.mkdir(mode=0o700)
# A fresh namespace has no external interfaces/routes. Bring up only its own
# loopback for the existing callback-security test; never join the host network.
launcher="set -eu; ip link set dev lo up; test \"$(ls /sys/class/net | wc -l)\" -eq 1; test -z \"$(ip route show default)\"; exec \"$@\""
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
 data=result.stdout+result.stderr
 (evidence/(name+'.log')).write_bytes(data)
 step={'name':name,'exit_code':result.returncode,'seconds':round(time.monotonic()-start,3),
  'external_network':False,'isolated_loopback':True,'log_sha256':hashlib.sha256(data).hexdigest()}
 steps.append(step)
 print('CHECK='+json.dumps(step),flush=True)
 if result.returncode!=expected:
  print(data.decode(errors='replace')[-16000:],flush=True)
  raise RuntimeError('unchanged_candidate_check_failed_'+name)
check('baseline-regression',OLD,['-m','pytest',regression,'-q','--junitxml='+str(evidence/'baseline.xml')],expected=1)
check('calendar-regression',WORK,['-m','pytest',regression,'-q','--junitxml='+str(evidence/'calendar.xml')])
check('accounting-regression',WORK,['-m','pytest','backend/tests/test_portfolio_accounting.py','-q','--junitxml='+str(evidence/'accounting.xml')])
check('full-backend',WORK,['-m','pytest','backend/tests','-q','--junitxml='+str(evidence/'full.xml')],limit=300)
check('health-openapi',WORK,['-c',"from fastapi.testclient import TestClient; from backend.app import app; c=TestClient(app); assert c.get('/health').status_code==200; assert c.get('/openapi.json').status_code==200; print('HEALTH_OPENAPI_OK')"])
def totals(path):
 root=ET.parse(path).getroot()
 suites=[root] if root.tag=='testsuite' else list(root.iter('testsuite'))
 return {key:sum(int(s.attrib.get(key,0)) for s in suites) for key in ('tests','failures','errors','skipped')}
if totals(evidence/'baseline.xml')['failures']!=5:raise RuntimeError('old_defect_not_reproduced_exactly')
for path,expected in EXPECTED.items():
 if hashlib.sha256((WORK/path).read_bytes()).hexdigest()!=expected:raise RuntimeError('candidate_changed_during_check')
if hashlib.sha256(Path('/opt/analyst-ai/backend/volume_market.py').read_bytes()).hexdigest()!=BASE_MARKET:raise RuntimeError('runtime_changed_during_check')
report={'schema':1,'status':'passed','server_id':9417611,'github_sha':ENVELOPE['github_sha'],
 'source_directory':str(WORK),'evidence_directory':str(evidence),'steps':steps,
 'baseline_regression':totals(evidence/'baseline.xml'),'calendar':totals(evidence/'calendar.xml'),
 'accounting':totals(evidence/'accounting.xml'),'full_backend':totals(evidence/'full.xml'),
 'changed_files':{p:{'sha256':value,'bytes':(WORK/p).stat().st_size} for p,value in EXPECTED.items()},
 'runtime_changed':False,'real_orders_enabled':False,'paid_ai_called':False,
 'sonar_passed':False,'native_android_acceptance_passed':False,
 'earlier_failure_receipts_preserved':[40465301512,40465756021],
 'finished_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
(evidence/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
print('VERIFIED_CANDIDATE='+json.dumps(report,indent=2),flush=True)
