"""Check a simulation-only execution journal on the existing Timeweb host."""
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import urllib.request
import xml.etree.ElementTree as ET

ROOT=Path('/var/lib/analyst-ai-build/development')
BASE=ROOT/'candidate-calendar-40465756021'
PYTHON=ROOT/'source49-check-20261027T055218Z-20765533/venv/bin/python'
PREVIOUS=ROOT/'n02-n04-check-40466990582/receipt.json'
EXPECTED={
 'backend/volume_market.py':'9c1536cfaddacc2e9bed9a21b24e868ba1a95267f38cf2bb362ec606fd26096c',
 'backend/tests/test_calendar_start_date.py':'40f715b4d94ffa2622abd7c0a4efaa72f333a3fc24df2cb399e673823312a26b',
 'backend/portfolio_accounting.py':'719b349fe033e354b560d44234579ea5dd9826ec3a13c66c7739cf8d8e63ceef',
 'backend/tests/test_portfolio_accounting.py':'493930a9685845a94043c0c40d77c808d191f5942d1813c65ba744d54c01ea26',
}
ADDITIONS={
 'backend/paper_execution.py':('paper_execution.py','c219c230ab1783c1d5a4242017dd2320fc9341cbdfc8d368445646cc4cd86414'),
 'backend/tests/test_paper_execution.py':('test_paper_execution.py','3e51bf1b52d71a4ceace1f8085f37d50c95251a96fd859b7b773f080e88e54ef'),
 'tools/run_paper_execution.py':('run_paper_execution.py','5988b7b63094166f3428730012bfefab2a2f29856cadd4bab0d29cb6c6ee2ff6'),
}
BASE_MARKET='5254e7eef732a28db8e3e3ed63b73a65b29ccdb983b78da686ce0bb3500ea87e'
lock=open('/var/lock/analyst-ai-plan-development.lock','a')
fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
previous=json.loads(PREVIOUS.read_text())
if previous.get('status')!='passed' or previous.get('full_backend')!={'tests':3463,'failures':0,'errors':0,'skipped':0}:
 raise RuntimeError('previous_verified_candidate_receipt_missing')
for path,expected in EXPECTED.items():
 if hashlib.sha256((BASE/path).read_bytes()).hexdigest()!=expected:raise RuntimeError('verified_baseline_changed')
if hashlib.sha256(Path('/opt/analyst-ai/backend/volume_market.py').read_bytes()).hexdigest()!=BASE_MARKET:
 raise RuntimeError('runtime_changed_before_new_candidate')
work=ROOT/('candidate-n08-'+ENVELOPE['run_id'])
evidence=ROOT/('n08-check-'+ENVELOPE['run_id'])
if work.exists() or evidence.exists():raise RuntimeError('candidate_or_evidence_already_exists')
shutil.copytree(BASE,work,ignore=shutil.ignore_patterns('.git','.venv','venv','__pycache__','.pytest_cache','build','.gradle'))
evidence.mkdir(mode=0o700)
for destination,(filename,expected) in ADDITIONS.items():
 target=work/destination
 if target.exists():raise RuntimeError('new_simulation_file_already_exists')
 url='https://raw.githubusercontent.com/MishaGameHacking/omni-cio-gateway/'+ENVELOPE['github_sha']+'/deploy/plan-20261027/'+filename
 with urllib.request.urlopen(url,timeout=20) as response:content=response.read(131073)
 if len(content)>131072 or hashlib.sha256(content).hexdigest()!=expected:
  raise RuntimeError('simulation_source_identity_mismatch')
 target.parent.mkdir(parents=True,exist_ok=True)
 target.write_bytes(content)
 EXPECTED[destination]=expected

def source_manifest():
 result={}
 for root in [work/'backend',work/'tools']:
  for path in sorted(root.rglob('*.py')):
   if path.is_symlink():raise RuntimeError('source_symlink_not_allowed')
   result[str(path.relative_to(work))]=hashlib.sha256(path.read_bytes()).hexdigest()
 return result
manifest=source_manifest()
(evidence/'source-manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
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
  'external_network':False,'isolated_loopback':True,'log_sha256':hashlib.sha256(data).hexdigest(),
  'pytest_summary':summary[-1:]}
 steps.append(step)
 print('CHECK='+json.dumps(step),flush=True)
 if result.returncode:
  print(data.decode(errors='replace')[-20000:],flush=True)
  raise RuntimeError('candidate_check_failed_'+name)
check('paper-regressions',['-m','pytest','backend/tests/test_paper_execution.py','-q','--junitxml='+str(evidence/'paper.xml')])
check('all-new-regressions',['-m','pytest','backend/tests/test_paper_execution.py','backend/tests/test_portfolio_accounting.py','backend/tests/test_calendar_start_date.py','-q','--junitxml='+str(evidence/'targeted.xml')])
check('full-backend',['-m','pytest','backend/tests','-q','--junitxml='+str(evidence/'full.xml')],limit=300)
check('paper-scenarios',['tools/run_paper_execution.py','--output-directory',str(evidence/'paper-scenarios')])
check('health-openapi',['-c',"from fastapi.testclient import TestClient; from backend.app import app; c=TestClient(app); assert c.get('/health').status_code==200; assert c.get('/openapi.json').status_code==200; print('HEALTH_OPENAPI_OK')"])
def totals(path):
 root=ET.parse(path).getroot();suites=[root] if root.tag=='testsuite' else list(root.iter('testsuite'))
 return {key:sum(int(s.attrib.get(key,0)) for s in suites) for key in ('tests','failures','errors','skipped')}
if source_manifest()!=manifest:raise RuntimeError('candidate_source_changed_during_checks')
if hashlib.sha256(Path('/opt/analyst-ai/backend/volume_market.py').read_bytes()).hexdigest()!=BASE_MARKET:
 raise RuntimeError('runtime_changed_during_candidate_checks')
scenarios=json.loads((evidence/'paper-scenarios/report.json').read_text())
if scenarios.get('real_orders_enabled') is not False or scenarios.get('owner_portfolio_used') is not False:
 raise RuntimeError('simulation_boundary_not_proven')
report={'schema':1,'status':'passed','server_id':9417611,'github_sha':ENVELOPE['github_sha'],
 'source_directory':str(work),'evidence_directory':str(evidence),'steps':steps,
 'paper':totals(evidence/'paper.xml'),'targeted':totals(evidence/'targeted.xml'),'full_backend':totals(evidence/'full.xml'),
 'changed_files':{path:{'sha256':value,'bytes':(work/path).stat().st_size} for path,value in EXPECTED.items()},
 'python_source_manifest_sha256':hashlib.sha256((evidence/'source-manifest.json').read_bytes()).hexdigest(),
 'scenarios':scenarios,'runtime_changed':False,'real_orders_enabled':False,'paid_ai_called':False,
 'sandbox_tested':False,'sonar_passed':False,'native_android_acceptance_passed':False,
 'previous_check_run':40466990582,'finished_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
(evidence/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
print('VERIFIED_N08_CANDIDATE='+json.dumps(report,indent=2),flush=True)
