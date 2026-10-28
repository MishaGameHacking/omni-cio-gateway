"""Read-only operational evidence and Android tool inventory on Timeweb.

No app imports, credential decryption, broker calls, DB writes, installation,
service restart or build. Only bounded metadata and aggregate version claims.
"""
from contextlib import closing
import datetime
import fcntl
import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request

ROOT=Path('/var/lib/analyst-ai-build/development')
DEPLOY=ROOT/'runtime-layer-deployment-40473816699/deployment.json'
lock=open('/var/lock/analyst-ai-plan-development.lock','a')
fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
receipt=json.loads(DEPLOY.read_text())
if receipt.get('status')!='passed' or receipt.get('phase')!='deployed':raise RuntimeError('verified_deployment_missing')
for name,row in receipt['files'].items():
 path=Path('/opt/analyst-ai/backend')/name
 if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=row['new']['sha256']:
  raise RuntimeError('runtime_source_changed_since_delivery')
now=int(time.time())
report={'schema':1,'server_id':9417611,'run_id':ENVELOPE['run_id'],'github_sha':ENVELOPE['github_sha'],
 'checked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'application_imported':False,'runtime_changed':False,'database_mode':'ro/query_only',
 'broker_requested':False,'paid_ai_requested':False,'deployed_hashes_match':True}
for name in ('analyst-ai-owner.service','analyst-ai-updates.service'):
 result=subprocess.run(['systemctl','show',name,'--property=ActiveState,SubState,NRestarts'],capture_output=True,text=True,timeout=10)
 if result.returncode:raise RuntimeError('service_status_unavailable')
 report[name]=dict(line.split('=',1) for line in result.stdout.splitlines() if '=' in line)

# Inspect only DATABASE_PATH. The broker token and encryption key are not read.
database=None
for line in Path('/etc/analyst-ai/backend.env').read_text().splitlines():
 key,sep,value=line.partition('=')
 if key=='DATABASE_PATH' and sep:
  values=shlex.split(value,comments=False)
  if len(values)!=1:raise RuntimeError('database_configuration_invalid')
  database=Path(values[0]).resolve()
if database is None:database=Path('/var/lib/analyst-ai/backend.db')
if not database.is_file() or not database.is_relative_to('/var/lib/analyst-ai'):
 raise RuntimeError('database_location_unverified')
with closing(sqlite3.connect(database.as_uri()+'?mode=ro',uri=True,timeout=2)) as db:
 db.execute('PRAGMA query_only=ON')
 db.execute('PRAGMA busy_timeout=2000')
 db.set_progress_handler(lambda: 1 if time.monotonic()>deadline else 0,10000)
 deadline=time.monotonic()+8
 tables={row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
 if {'client_versions','sessions','users','installation_owner'}<=tables:
  rows=db.execute('''SELECT cv.version_code,COUNT(*),MAX(cv.observed_at)
   FROM client_versions cv JOIN sessions s ON s.token_hash=cv.session_hash AND s.user_id=cv.user_id
   JOIN users u ON u.id=cv.user_id JOIN installation_owner io ON io.singleton=1 AND io.telegram_sub=u.telegram_sub
   WHERE s.expires_at>=? AND cv.observed_at BETWEEN ? AND ? AND cv.package_name=?
   GROUP BY cv.version_code ORDER BY cv.version_code DESC LIMIT 10''',
   (now,now-86400,now,'ru.omnicio.app.debug')).fetchall()
  report['authenticated_client_version_claims']={'window_seconds':86400,'device_attestation':False,
   'groups':[{'version_code':row[0],'active_session_count':row[1],
              'latest_reported_at_utc':datetime.datetime.fromtimestamp(row[2],datetime.timezone.utc).isoformat()} for row in rows]}
 if {'workspace_snapshots','users','installation_owner'}<=tables:
  # Only timing/status fields are selected. No financial amounts or identifiers.
  fields=('$.as_of','$.event_monitor.checked_at','$.event_monitor.complete','$.event_monitor.calendar',
   '$.event_monitor.news','$.event_monitor.operations','$.event_monitor.payout_announcements',
   '$.calendar.state','$.calendar.data.as_of')
  columns=','.join('json_extract(w.payload_json,?)' for _ in fields)
  query='SELECT '+columns+",json_array_length(json_extract(w.payload_json,'$.calendar.data.exchanges')) FROM workspace_snapshots w JOIN users u ON u.id=w.user_id JOIN installation_owner io ON io.singleton=1 AND io.telegram_sub=u.telegram_sub WHERE w.currency='RUB' AND json_valid(w.payload_json) LIMIT 2"
  rows=db.execute(query,fields).fetchall()
  names=('valuation_as_of','event_checked_at','events_complete','calendar_attempt','news_attempt',
   'operations_attempt','payouts_attempt','calendar_state','calendar_as_of','calendar_exchange_count')
  report['saved_owner_snapshot_status']={'current_broker_fingerprint_revalidated':False,
   'scope':'saved_owner_RUB_snapshots_only','rows':[dict(zip(names,row)) for row in rows]}
 report['read_only_verified']=db.execute('PRAGMA query_only').fetchone()[0]==1

class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None
opener=urllib.request.build_opener(NoRedirect())
for name,url in [('health','https://analyst-ai-2941515.twc1.net/health'),
                 ('policy','https://analyst-ai-2941515.twc1.net/client/update-policy?package_name=ru.omnicio.app.debug')]:
 try:
  with opener.open(url,timeout=12) as response:
   raw=response.read(65537)
   if len(raw)>65536:raise RuntimeError('public_response_limit')
   value=json.loads(raw)
   report[name]={'http_status':response.status,'response_sha256':hashlib.sha256(raw).hexdigest()}
   if name=='policy':report[name].update({key:value.get(key) for key in ('version_code','version_name','package_name','min_sdk','apk_bytes','apk_sha256','certificate_sha256')})
 except (OSError,ValueError) as error:
  report[name]={'error_type':type(error).__name__}

sdk=Path('/opt/analyst-android-sdk')
files=['platforms/android-37/android.jar','build-tools/37.0.0/apksigner','build-tools/37.0.0/aapt',
 'build-tools/37.0.0/zipalign','platform-tools/adb','emulator/emulator','cmdline-tools/latest/bin/sdkmanager']
report['android_environment']={'sdk_root':str(sdk),'files':{name:(sdk/name).is_file() for name in files},
 'system_images_api37':[str(path.relative_to(sdk)) for path in (sdk/'system-images/android-37').glob('*/*/source.properties')][:12],
 'jdk17':Path('/usr/lib/jvm/java-17-openjdk-amd64/bin/java').is_file(),'kvm_available':Path('/dev/kvm').exists(),
 'gradle98_cached':[str(path) for path in Path('/var/cache/analyst-ai/gradle/wrapper/dists').glob('gradle-9.8.1-bin/*/gradle-9.8.1/bin/gradle')][:4],
 'signing_keystore_present':Path('/var/lib/analyst-ai-build/.android/debug.keystore').is_file()}
workspace=Path('/srv/analyst-ai/workspace')
if (workspace/'.git').exists():
 result=subprocess.run(['git','rev-parse','HEAD'],cwd=workspace,capture_output=True,text=True,timeout=5)
 head=result.stdout.strip()
 report['android_environment']['existing_workspace_head']=head if re.fullmatch(r'[0-9a-f]{40}',head) else None
mem={}
for line in Path('/proc/meminfo').read_text().splitlines():
 key,_,value=line.partition(':')
 if key in {'MemTotal','MemAvailable','SwapTotal','SwapFree'}:mem[key+'_kib']=int(value.split()[0])
report['capacity']={**mem,'disk_free_bytes':shutil.disk_usage(ROOT).free}
counts={}
for path in Path('/proc').glob('[0-9]*/comm'):
 try:name=path.read_text().strip()
 except OSError:continue
 if name in {'java','adb','qemu-system-x86','emulator','gradle'}:counts[name]=counts.get(name,0)+1
report['active_build_process_names']=counts
report['status']='observed'
directory=ROOT/('post-runtime-observation-'+ENVELOPE['run_id']+'-'+str(time.time_ns()))
directory.mkdir(mode=0o700)
(directory/'observation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2),flush=True)
