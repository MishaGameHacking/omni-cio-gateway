"""Verify the calendar date correction and test it in an isolated Timeweb copy."""
import contextlib
import datetime as dt
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path('/var/lib/analyst-ai-build/development')
BASE = ROOT / 'candidate-n02-n04-r4-20261027-20261027T061309Z-ea5fd07f'
PYTHON = ROOT / 'source49-check-20261027T055218Z-20765533/venv/bin/python'
# Reuse the exact already-inspected, successful read-only diagnostic. Only its
# requested start date changes; authentication, redaction and hash guards do not.
url = 'https://raw.githubusercontent.com/MishaGameHacking/omni-cio-gateway/11ee6980a047218a0a0ba627f233233d097b6549/deploy/plan-20261027/operation.py'
with urllib.request.urlopen(url, timeout=20) as response:
    raw = response.read(65537)
if len(raw)>65536 or hashlib.sha256(raw).hexdigest()!='d6e7026b2c71d1489a8df3b70135c4e5284c7493863ae01d09cad3835b86e5fd':
    raise RuntimeError('diagnostic_source_mismatch')
text = raw.decode()
old_date = '(today-datetime.timedelta(days=1)).isoformat()'
if text.count(old_date)!=1:raise RuntimeError('diagnostic_patch_mismatch')
text = text.replace(old_date, 'today.isoformat()')
buffer = io.StringIO()
namespace = {'ENVELOPE': ENVELOPE, '__name__': '__main__'}
with contextlib.redirect_stdout(buffer):
    exec(compile(text, 'verified-calendar-start-date-diagnostic', 'exec'), namespace)
probe = json.loads(buffer.getvalue())
namespace['lock'].close()
print('CALENDAR_CURRENT_DAY_PROBE='+json.dumps(probe), flush=True)
if probe.get('calendar',{}).get('http_status')!=200 or not probe['calendar'].get('exchange_count'):
    raise RuntimeError('calendar_correction_not_confirmed_no_product_patch')
lock = open('/var/lock/analyst-ai-plan-development.lock','a')
fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
run_id=ENVELOPE['run_id']
work=ROOT/('candidate-calendar-'+run_id)
evidence=ROOT/('candidate-calendar-check-'+run_id)
if work.exists() or evidence.exists():raise RuntimeError('candidate_already_exists')
shutil.copytree(BASE,work,ignore=shutil.ignore_patterns('.git','.venv','venv','__pycache__','.pytest_cache','build','.gradle'))
evidence.mkdir(mode=0o700)
relative='backend/volume_market.py'
before=(BASE/relative).read_bytes()
if before!=(Path('/opt/analyst-ai')/relative).read_bytes():raise RuntimeError('calendar_runtime_source_changed')
original='    # Include the previous UTC day so an overnight broker window is not lost.\n    today = datetime.combine(datetime.now(timezone.utc).date(), datetime.min.time(), timezone.utc)\n    begin = today - timedelta(days=1)\n'
replacement='    # TradingSchedules rejects a from date before the current UTC date.\n    # Never turn missing previous-day coverage into an assumed open session.\n    today = datetime.combine(datetime.now(timezone.utc).date(), datetime.min.time(), timezone.utc)\n    begin = today\n'
if before.decode().count(original)!=1:raise RuntimeError('calendar_product_patch_mismatch')
(work/relative).write_text(before.decode().replace(original,replacement))
test=r'''"""Regression for the real 2026-10-27 TradingSchedules HTTP 400.

Synthetic calendar payloads only. A successful calendar read never authorizes
trading and does not invent coverage for a previous UTC day.
"""
from datetime import datetime, timedelta, timezone
import os
from unittest.mock import MagicMock
import pytest
from fastapi import HTTPException
os.environ.setdefault('TELEGRAM_CLIENT_ID','123456')
os.environ.setdefault('TELEGRAM_CLIENT_SECRET','test-only')
os.environ.setdefault('BACKEND_PUBLIC_URL','https://example.invalid')
os.environ.setdefault('FERNET_KEY','AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=')
os.environ['ANALYSIS_SCHEDULER_ENABLED']='false'
from backend import volume_market as market

@pytest.mark.parametrize('instant',[
    datetime(2026,10,27,6,59,tzinfo=timezone.utc),
    datetime(2026,10,27,0,0,tzinfo=timezone.utc),
    datetime(2026,10,27,23,59,59,tzinfo=timezone.utc),
    datetime(2026,12,31,23,59,59,tzinfo=timezone.utc),
    datetime(2028,2,29,12,tzinfo=timezone.utc),
])
def test_calendar_request_never_begins_in_previous_utc_day(monkeypatch,instant):
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return instant.astimezone(tz or timezone.utc)
    monkeypatch.setattr(market,'datetime',Clock)
    monkeypatch.setattr(market.details,'BrokerReader',MagicMock())
    seen=[]
    def read(reader,method,body):
        assert method=='calendar'
        seen.append(body)
        assert datetime.fromisoformat(body['from']).date()==instant.date()
        return {'exchanges':[]}
    monkeypatch.setattr(market,'broker_read',read)
    result=market.load_calendar(object())
    assert len(seen)==1
    begin=datetime.fromisoformat(seen[0]['from'])
    finish=datetime.fromisoformat(seen[0]['to'])
    assert begin.utcoffset()==timedelta(0)
    assert timedelta(0)<finish-begin<timedelta(days=14)
    assert result['exchanges']==[]
    assert result['basis']=='broker_sections_not_guaranteed_instrument_availability'
    assert 'trade_permission' not in result

@pytest.mark.parametrize('payload',[{}, {'exchanges':None},{'exchanges':'MOEX'}])
def test_invalid_calendar_response_is_not_treated_as_closed_or_open(monkeypatch,payload):
    monkeypatch.setattr(market.details,'BrokerReader',MagicMock())
    monkeypatch.setattr(market,'broker_read',lambda *args:payload)
    with pytest.raises(HTTPException) as caught:market.load_calendar(object())
    assert caught.value.status_code==502
    assert caught.value.detail=='calendar_invalid_response'

def test_calendar_error_is_preserved_without_a_synthetic_schedule(monkeypatch):
    monkeypatch.setattr(market.details,'BrokerReader',MagicMock())
    def read(*args):raise HTTPException(502,'tinvest_unexpected_status')
    monkeypatch.setattr(market,'broker_read',read)
    with pytest.raises(HTTPException) as caught:market.load_calendar(object())
    assert caught.value.detail=='tinvest_unexpected_status'
'''
(work/'backend/tests/test_calendar_start_date.py').write_text(test)
# Both baseline and candidate are tested with the same new regression, in copies.
baseline=ROOT/('calendar-regression-baseline-'+run_id)
shutil.copytree(work,baseline,ignore=shutil.ignore_patterns('__pycache__','.pytest_cache'))
(baseline/relative).write_bytes(before)
env={'PATH':'/usr/bin:/bin','HOME':str(evidence),'PYTHONPATH':str(work),
     'PYTHONDONTWRITEBYTECODE':'1','PYTHONUNBUFFERED':'1',
     'TELEGRAM_CLIENT_ID':'123456','TELEGRAM_CLIENT_SECRET':'test-only',
     'BACKEND_PUBLIC_URL':'https://example.invalid','FERNET_KEY':'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=',
     'ANALYSIS_SCHEDULER_ENABLED':'false','AI_EXTERNAL_PROCESSING_APPROVED':'false',
     'DATABASE_PATH':str(evidence/'isolated-tests.sqlite3')}
steps=[]
def check(name,source,arguments,expected=0,limit=240):
    start=time.monotonic()
    command=['unshare','--net','--',str(PYTHON),*arguments]
    settings={**env,'PYTHONPATH':str(source),'DATABASE_PATH':str(evidence/(name+'.sqlite3'))}
    result=subprocess.run(command,cwd=source,env=settings,capture_output=True,timeout=limit)
    data=result.stdout+result.stderr
    (evidence/(name+'.log')).write_bytes(data)
    steps.append({'name':name,'exit_code':result.returncode,'seconds':round(time.monotonic()-start,3),
      'network_allowed':False,'log_sha256':hashlib.sha256(data).hexdigest()})
    if result.returncode!=expected:
        print('FAILED_CHECK='+json.dumps(steps[-1]),flush=True)
        print(data.decode(errors='replace')[-16000:],flush=True)
        raise RuntimeError('candidate_check_failed_'+name)
check('baseline-regression',baseline,['-m','pytest','backend/tests/test_calendar_start_date.py','-q','--junitxml='+str(evidence/'baseline.xml')],expected=1)
check('targeted-regression',work,['-m','pytest','backend/tests/test_calendar_start_date.py','-q','--junitxml='+str(evidence/'targeted.xml')])
check('full-backend',work,['-m','pytest','backend/tests','-q','--junitxml='+str(evidence/'full.xml')],limit=300)
check('health-openapi',work,['-c',"from fastapi.testclient import TestClient; from backend.app import app; c=TestClient(app); assert c.get('/health').status_code==200; assert c.get('/openapi.json').status_code==200; print('HEALTH_OPENAPI_OK')"])
def results(path):
    root=ET.parse(path).getroot()
    suites=[root] if root.tag=='testsuite' else list(root.iter('testsuite'))
    return {key:sum(int(s.attrib.get(key,0)) for s in suites) for key in ('tests','failures','errors','skipped')}
if results(evidence/'baseline.xml')['failures']!=5:raise RuntimeError('baseline_regression_not_reproduced_exactly')
if before!=(BASE/relative).read_bytes() or before!=(Path('/opt/analyst-ai')/relative).read_bytes():raise RuntimeError('source_changed_during_check')
report={'schema':1,'status':'passed','server_id':9417611,'github_sha':ENVELOPE['github_sha'],
 'source_directory':str(work),'evidence_directory':str(evidence),'calendar_probe':probe['calendar'],
 'steps':steps,'baseline_regression':results(evidence/'baseline.xml'),'targeted':results(evidence/'targeted.xml'),
 'full_backend':results(evidence/'full.xml'),'runtime_changed':False,'real_orders_enabled':False,
 'changed_files':{p:{'sha256':hashlib.sha256((work/p).read_bytes()).hexdigest(),'bytes':(work/p).stat().st_size}
 for p in [relative,'backend/tests/test_calendar_start_date.py']},
 'finished_at_utc':dt.datetime.now(dt.timezone.utc).isoformat()}
(evidence/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
print('CALENDAR_CANDIDATE='+json.dumps(report,indent=2),flush=True)
