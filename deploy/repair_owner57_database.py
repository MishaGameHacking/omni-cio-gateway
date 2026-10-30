"""Enable persistent SQLite WAL after stopping the existing services; preserve all rows."""
from __future__ import annotations
from contextlib import closing
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import subprocess
import time
import urllib.request
import urllib.error

SERVICES=('analyst-ai-owner.service','analyst-ai-updates.service')
DATABASE=Path('/var/lib/analyst-ai/backend.db')

def need(value, code):
    if not value: raise RuntimeError(code)

def inventory(db):
    tables=[row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    counts={name:db.execute('SELECT count(*) FROM "'+name.replace('"','""')+'"').fetchone()[0] for name in tables}
    auth=db.execute('SELECT singleton,user_id,configured_at,updated_at,scheme FROM owner_password_credentials').fetchall()
    binding=db.execute('SELECT singleton,telegram_sub,policy_version FROM installation_owner').fetchall()
    return counts,auth,binding

def configure(database, backup):
    info=database.lstat()
    need(stat.S_ISREG(info.st_mode) and database.resolve(strict=True)==database and info.st_nlink==1,'untrusted_database')
    need(not backup.exists() and not backup.is_symlink(),'backup_already_exists')
    with closing(sqlite3.connect(database,timeout=10)) as db:
        need(db.execute('PRAGMA quick_check').fetchall()==[('ok',)],'database_integrity_failed')
        before=inventory(db)
        need(len(before[1])==1 and len(before[2])==1,'owner_configuration_unexpected')
        previous=db.execute('PRAGMA journal_mode').fetchone()[0]
        need(previous in ('delete','wal'),'unreviewed_journal_mode')
        fd=os.open(backup,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        os.close(fd)
        with closing(sqlite3.connect(backup)) as saved:
            db.backup(saved)
            need(saved.execute('PRAGMA quick_check').fetchall()==[('ok',)] and inventory(saved)==before,'backup_verification_failed')
        need(db.execute('PRAGMA journal_mode=WAL').fetchone()[0]=='wal','wal_not_enabled')
        need(inventory(db)==before,'database_rows_changed')
        need(db.execute('PRAGMA quick_check').fetchall()==[('ok',)],'database_integrity_failed')
    after=database.stat()
    need((info.st_uid,info.st_gid,stat.S_IMODE(info.st_mode))==(after.st_uid,after.st_gid,stat.S_IMODE(after.st_mode)),'database_permissions_changed')
    return {'previous_mode':previous,'journal_mode':'wal','database_backup_created':True,
            'database_rows_preserved':True,'owner_configuration_preserved':True,'integrity_checked':True}

def service(action):
    subprocess.run(['systemctl',action,*SERVICES],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True,timeout=100)

def service_active():
    return all(subprocess.run(['systemctl','is-active','--quiet',name],timeout=10).returncode==0 for name in SERVICES)

def probe_local(port):
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    root='http://127.0.0.1:'+str(port)
    with opener.open(root+'/health',timeout=10) as response:
        need(response.status==200 and json.loads(response.read(1024))=={'status':'ok'},'health_failed')
    with opener.open(root+'/auth/owner/status',timeout=10) as response:
        need(response.status==200 and json.loads(response.read(4096)).get('configured') is True,'owner_status_failed')
    try:
        with opener.open(urllib.request.Request(root+'/auth/owner/login',data=b'{}',headers={'Content-Type':'application/json'}),timeout=10):
            raise RuntimeError('invalid_auth_payload_accepted')
    except urllib.error.HTTPError as error:
        need(error.code==422 and json.loads(error.read(4096)).get('detail')=='owner_auth_payload_invalid','validation_failed')

def initial_result():
    return {'status':'blocked','server_id':9417611,'previous_mode':'unknown','journal_mode':'unknown',
        'database_backup_created':False,'database_rows_preserved':False,'owner_configuration_preserved':False,
        'integrity_checked':False,'services_active':False,'checks_passed':0,'write_checks_passed':0,
        'maximum_write_wait_ms':0,'passwords_changed':False,'apk_changed':False,'observed_at':int(time.time()),
        'previous_running_kind':'none','previous_running_stage':'none','failure':'none'}

def maintain(result):
    need(os.getuid()==0,'root_required')
    run=ENVELOPE['payload']['run_id']
    need(re.fullmatch('[0-9]{8,20}',run),'invalid_run')
    parent=Path('/var/lib/analyst-ai-build')
    need(parent.resolve(strict=True)==parent and parent.stat().st_uid==0 and not parent.stat().st_mode&0o022,'unsafe_archive_parent')
    archive=parent/('login-wal-'+run)
    archive.mkdir(mode=0o700)
    need(archive.resolve(strict=True)==archive and not archive.stat().st_mode&0o077,'unsafe_archive')
    pid=subprocess.run(['systemctl','show',SERVICES[0],'--property=MainPID','--value'],capture_output=True,text=True,check=True,timeout=10).stdout.strip()
    need(pid.isdigit() and int(pid)>1,'service_not_running')
    args=Path('/proc/'+pid+'/cmdline').read_bytes().decode().split('\0')
    port=int(args[args.index('--port')+1]) if '--port' in args else 8000
    need(1<=port<=65535,'invalid_port')
    try:
        service('stop')
        for name in SERVICES:
            current=subprocess.run(['systemctl','show',name,'--property=MainPID','--value'],capture_output=True,text=True,check=True,timeout=10).stdout.strip()
            need(current=='0','service_still_active')
        result.update(configure(DATABASE,archive/'before.sqlite3'))
        with closing(sqlite3.connect(DATABASE)) as db:
            row=db.execute("SELECT kind,stage FROM workspace_jobs WHERE state='running' ORDER BY updated_at LIMIT 1").fetchone()
            if row:
                result['previous_running_kind']=row[0] if row[0] in ('osint','events','refresh','chat','analysis','reconcile') else 'other'
                result['previous_running_stage']=row[1] if row[1] in ('osint_collecting','persisting','collecting','running','queued','done') else 'other'
    finally:
        service('start')
        result['services_active']=service_active()
    need(result['services_active'],'service_not_active')
    for attempt in range(12):
        try:
            probe_local(port)
            break
        except (OSError,ValueError,RuntimeError):
            if attempt==11:raise
            time.sleep(2)
    for _ in range(6):
        time.sleep(5)
        probe_local(port);result['checks_passed']+=1
        with closing(sqlite3.connect(DATABASE,timeout=2)) as db:
            need(db.execute('PRAGMA journal_mode').fetchone()[0]=='wal','wal_not_persistent')
            started=time.monotonic()
            db.execute('BEGIN IMMEDIATE');db.rollback()
            result['maximum_write_wait_ms']=max(result['maximum_write_wait_ms'],int((time.monotonic()-started)*1000))
            result['write_checks_passed']+=1
    result['status']='repaired'
    (archive/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    receipt=initial_result()
    try:maintain(receipt)
    except sqlite3.OperationalError:receipt['failure']='database_operation_failed'
    except subprocess.TimeoutExpired:receipt['failure']='service_timeout'
    except Exception:receipt['failure']='maintenance_failed'
    print(json.dumps(receipt),flush=True)
