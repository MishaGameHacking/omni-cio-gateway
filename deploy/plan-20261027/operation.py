"""Bounded read-only calendar diagnosis; no application imports or runtime changes."""
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

BASE = Path('/var/lib/analyst-ai-build/development')
POINTER = BASE / 'current-source-n02-n04-r4-20261027.json'
CANDIDATE = BASE / 'candidate-n02-n04-r4-20261027-20261027T061309Z-ea5fd07f'
EXPECTED = {
 'event_monitor.py': '68cf1edfba5226f1f866c9dceb904787e0b68b9808329b08e90418face9573d4',
 'market_schedule.py': '184f3f8a4aca281579a6768e442a357b02bc8620f813a3e6f162a75ed4982498',
 'operations_ledger.py': 'c6874e515e2e526328cdbc3f1f8741c788004765f76f22f057518e7fad90e414',
 'public_sources.py': '274849ad97b7e7cf6bd0cf4bdfd4298da04b94464df85b3e6d9333be1ddcc614',
 'volume_monitor.py': '66ff4c8837ea154c7728b3775c8a0c1e349e7746a2254d87f4edd3224c606e64',
 'volume_workspace.py': 'f555bd502addede8ade3068231322e7ad5c702f83da7d37ee5821a0cb14b2452',
}
lock = open('/var/lock/analyst-ai-plan-development.lock', 'a')
fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
report = {'schema': 1, 'server_id': 9417611, 'operation': 'calendar_read_only_diagnosis',
 'github_sha': ENVELOPE['github_sha'], 'run_id': ENVELOPE['run_id'],
 'checked_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'application_imported': False, 'runtime_changed': False, 'database_mode': 'ro/query_only',
 'real_orders_enabled': False, 'paid_ai_called': False}
for root in [CANDIDATE / 'backend', Path('/opt/analyst-ai/backend')]:
 for name, expected in EXPECTED.items():
  if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
   raise RuntimeError('source_identity_changed')
report['verified_source_pointer_sha256'] = hashlib.sha256(POINTER.read_bytes()).hexdigest()
report['test_python_exists'] = (BASE / 'source49-check-20261027T055218Z-20765533/venv/bin/python').exists()
report['kvm_available'] = Path('/dev/kvm').exists()
report['cpu_count'] = os.cpu_count()
report['disk_free_bytes'] = shutil.disk_usage(BASE).free
report['android_sdk_directories'] = [str(p) for p in [Path('/opt/android-sdk'), Path('/opt/android'), Path('/var/lib/analyst-ai-build/android-sdk')] if p.is_dir()]
# Dependencies come from the existing runtime venv. This child never imports the app.
child = r'''
import datetime,hashlib,json,re,shlex,sqlite3,ssl
from pathlib import Path
from contextlib import closing
import certifi,httpx
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.fernet import Fernet
settings={}
for line in Path('/etc/analyst-ai/backend.env').read_text().splitlines():
 if not line.strip() or line.lstrip().startswith('#'):continue
 key,sep,value=line.partition('=')
 if key not in {'DATABASE_PATH','FERNET_KEY','ANALYST_OWNER_TELEGRAM_SUB'}:continue
 values=shlex.split(value,comments=False)
 if not sep or len(values)!=1:raise RuntimeError('configuration_parse_failed')
 settings[key]=values[0]
path=Path(settings.get('DATABASE_PATH','/var/lib/analyst-ai/backend.db')).resolve()
if not path.is_file():raise RuntimeError('database_missing')
with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
 db.execute('PRAGMA query_only=ON')
 registry=db.execute('SELECT telegram_sub FROM installation_owner WHERE singleton=1').fetchall()
 rows=db.execute('SELECT telegram_sub,tinvest_token_encrypted FROM users').fetchall()
 if len(registry)!=1 or len(rows)!=1 or rows[0][0]!=registry[0][0] or registry[0][0]!=settings['ANALYST_OWNER_TELEGRAM_SUB']:
  raise RuntimeError('owner_binding_unverified')
 encrypted=rows[0][1]
 if not encrypted:raise RuntimeError('broker_connection_missing')
 token=Fernet(settings['FERNET_KEY'].encode()).decrypt(encrypted).decode()
cert_bytes=Path('/opt/analyst-ai/backend/certs/russian_trusted_root_ca.pem').read_bytes()
cert=x509.load_pem_x509_certificate(cert_bytes)
if cert.fingerprint(hashes.SHA256()).hex()!='d26d2d0231b7c39f92cc738512ba54103519e4405d68b5bd703e9788ca8ecf31':raise RuntimeError('broker_ca_mismatch')
context=ssl.create_default_context(cafile=certifi.where());context.load_verify_locations(cadata=cert_bytes.decode('ascii'))
now=datetime.datetime.now(datetime.timezone.utc)
today=now.replace(hour=0,minute=0,second=0,microsecond=0)
body={'from':(today-datetime.timedelta(days=1)).isoformat(),'to':(today+datetime.timedelta(days=6,hours=23,minutes=59)).isoformat()}
url='https://invest-public-api.tbank.ru/rest/tinkoff.public.invest.api.contract.v1.InstrumentsService/TradingSchedules'
result={'method':'TradingSchedules','request_dates':body,'account_id_sent':False,'token_returned':False,'owner_binding_verified':True,'requests':1}
try:
 with httpx.Client(verify=context,timeout=httpx.Timeout(12,connect=5),follow_redirects=False) as client:
  with client.stream('POST',url,headers={'Authorization':'Bearer '+token,'Accept':'application/json','Content-Type':'application/json'},json=body) as response:
   result['http_status']=response.status_code
   raw=bytearray()
   for part in response.iter_bytes():
    raw.extend(part)
    if len(raw)>1024*1024:raise RuntimeError('calendar_response_too_large')
   result['response_bytes']=len(raw)
   result['response_sha256']=hashlib.sha256(raw).hexdigest()
   try:data=json.loads(raw)
   except ValueError:data={}
   if not isinstance(data,dict):data={}
   code=data.get('code')
   result['upstream_code']=str(code) if re.fullmatch(r'[0-9]{1,6}',str(code)) else None
   # Free-form upstream text is not returned. Diagnose against the official error catalogue.
   text=' '.join(str(data.get(k,'')) for k in ('message','description')).lower()
   result['error_keywords']=[word for word in ('exchange','from','to','date','period','range','maximum','invalid','required','not found','unimplemented','limit') if word in text]
   result['exchange_count']=len(data['exchanges']) if isinstance(data.get('exchanges'),list) else None
except (httpx.TimeoutException,httpx.TransportError) as error:
 result['transport_error_type']=type(error).__name__
finally:
 token='';settings.clear()
print(json.dumps(result))
'''
result = subprocess.run(['/opt/analyst-ai/venv/bin/python', '-c', child], capture_output=True, timeout=35,
 env={'PATH':'/usr/bin:/bin','HOME':'/root','PYTHONDONTWRITEBYTECODE':'1','PYTHONUNBUFFERED':'1'})
report['diagnostic_exit_code'] = result.returncode
if result.returncode == 0:
 report['calendar'] = json.loads(result.stdout)
else:
 report['diagnostic_error'] = 'bounded_calendar_diagnostic_failed'
 report['diagnostic_stderr_bytes'] = len(result.stderr)
for root in [CANDIDATE / 'backend', Path('/opt/analyst-ai/backend')]:
 for name, expected in EXPECTED.items():
  if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
   raise RuntimeError('source_changed_during_diagnosis')
report['source_unchanged'] = True
report['status'] = 'observed' if result.returncode == 0 else 'diagnostic_failed'
directory = BASE / ('plan-audit-' + ENVELOPE['run_id'])
directory.mkdir(mode=0o700)
(directory / 'calendar-diagnostic.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2), flush=True)
if result.returncode != 0:raise SystemExit(1)
