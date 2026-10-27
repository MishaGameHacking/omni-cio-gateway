"""Preserve the checked observation and handoff text on Timeweb; no app execution."""
from pathlib import Path
import fcntl
import hashlib
import json
import urllib.request
ROOT=Path('/var/lib/analyst-ai-build/development')
SOURCE=ROOT/'candidate-runtime-hardened-40472430619'
REPORT=ROOT/'post-runtime-observation-40475214918/observation.json'
lock=open('/var/lock/analyst-ai-plan-development.lock','a')
fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
raw=REPORT.read_bytes()
if hashlib.sha256(raw).hexdigest()!='0875da4701fe82685d7de13b3bd5e0264c8d1b7482867c0f1817b1b4cfdfc1d8':
 raise RuntimeError('observation_receipt_changed')
# The receipt hash covers JSON plus the final newline, exactly as printed.
observed=json.loads(raw)
if observed.get('run_id')!='40475214918' or observed.get('read_only_verified') is not True:
 raise RuntimeError('read_only_observation_unverified')
deployed=json.loads((ROOT/'runtime-layer-deployment-40473816699/deployment.json').read_text())
for name,value in deployed['files'].items():
 if hashlib.sha256((Path('/opt/analyst-ai/backend')/name).read_bytes()).hexdigest()!=value['new']['sha256']:
  raise RuntimeError('runtime_source_changed')
folder=ROOT/('runtime-handoff-'+ENVELOPE['run_id']);folder.mkdir(mode=0o700)
files={}
for relative in ('docs/RUNTIME_POSTDEPLOY_2026-10-27.md','docs/TIMEWEB_CURRENT_SOURCE_2026-10-27.md'):
 url='https://raw.githubusercontent.com/MishaGameHacking/omni-cio-gateway/'+ENVELOPE['github_sha']+'/'+relative
 with urllib.request.urlopen(url,timeout=20) as response:
  data=response.read(32769)
 if len(data)>32768:raise RuntimeError('documentation_size_limit')
 target=SOURCE/relative
 if target.exists():
  old=folder/(target.name+'.previous');old.write_bytes(target.read_bytes())
 temporary=target.with_name(target.name+'.'+ENVELOPE['run_id']+'.tmp')
 with temporary.open('xb') as out:out.write(data)
 temporary.replace(target)
 files[relative]={'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
(folder/'postdeployment-observation.json').write_bytes(raw)
result={'status':'saved','server_id':9417611,'runtime_changed':False,'project_code_executed':False,
 'source_directory':str(SOURCE),'handoff_directory':str(folder),'observation_run':40475214918,
 'github_sha':ENVELOPE['github_sha'],'files':files}
(folder/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2),flush=True)
