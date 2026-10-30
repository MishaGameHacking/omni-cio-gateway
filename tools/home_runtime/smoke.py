"""Exercise real password routes using a disposable database and no brokerage data."""
from contextlib import contextmanager
import base64
import http.client
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import tempfile
import time

SOURCE=Path('/opt/analyst-source/853090e11dcefef693366159c97316e55045c4c9/backend')
PYTHON='/opt/analyst-ai/venv/bin/python'


def req(port, path, body=None, headers=None):
    conn=http.client.HTTPConnection('127.0.0.1',port,timeout=8)
    try:
        data=json.dumps(body).encode() if body is not None else None
        conn.request('POST' if data is not None else 'GET',path,body=data,
                     headers={'Content-Type':'application/json',**(headers or {})})
        response=conn.getresponse()
        return response.status,json.loads(response.read(20000))
    finally:
        conn.close()


@contextmanager
def process(env):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        sock.listen()
        port=sock.getsockname()[1]
        proc=subprocess.Popen([PYTHON,'-I','-m','uvicorn','owner_app:create_app','--factory','--workers','1',
              '--fd',str(sock.fileno()),'--app-dir',str(SOURCE),'--no-access-log'],pass_fds=(sock.fileno(),),
              cwd=SOURCE,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,stdin=subprocess.DEVNULL)
        try:
            for _ in range(50):
                if proc.poll() is not None:
                    raise RuntimeError('auth_smoke_start_failed')
                try:
                    if req(port,'/health')==(200,{'status':'ok'}):
                        break
                except OSError:
                    pass
                time.sleep(.4)
            else:
                raise RuntimeError('auth_smoke_start_timeout')
            yield port
        finally:
            proc.terminate()
            try: proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


def run():
    if os.geteuid()==0: raise RuntimeError('nonroot_smoke_required')
    with tempfile.TemporaryDirectory(prefix='analyst-auth-check-') as tmp:
        subject='rehearsal-'+secrets.token_hex(16)
        bootstrap=secrets.token_urlsafe(36)
        password=secrets.token_urlsafe(28)
        env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','FERNET_KEY':base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
             'DATABASE_PATH':tmp+'/check.sqlite','ANALYST_OWNER_TELEGRAM_SUB':subject,
             'BACKEND_PUBLIC_URL':'https://auth-rehearsal.invalid','ANALYST_OWNER_BOOTSTRAP_SECRET':bootstrap,
             'ANALYSIS_SCHEDULER_ENABLED':'false','AI_EXTERNAL_PROCESSING_APPROVED':'false','PYTHONDONTWRITEBYTECODE':'1'}
        with process(env) as port:
            assert req(port,'/me')[0]==401
            assert req(port,'/auth/owner/status')[1].get('configured') is False
            code,setup=req(port,'/auth/owner/setup',{'password':password,'device_name':'rehearsal'},
                           {'X-Owner-Bootstrap':bootstrap})
            assert code==200 and setup.get('access_token')
            code,login=req(port,'/auth/owner/login',{'password':password,'device_name':'rehearsal'})
            assert code==200 and login.get('access_token')
            bearer={'Authorization':'Bearer '+login['access_token']}
            status,me=req(port,'/me',headers=bearer)
            assert status==200 and str(me.get('telegram_id'))==subject
        env.pop('ANALYST_OWNER_BOOTSTRAP_SECRET')
        with process(env) as port:
            assert req(port,'/auth/owner/status')[1].get('configured') is True
            code,me=req(port,'/me',headers=bearer)
            assert code==200 and str(me.get('telegram_id'))==subject
            wrong,_=req(port,'/auth/owner/login',{'password':secrets.token_urlsafe(26),'device_name':'rehearsal'})
            assert wrong==401
    return {'status':'passed','setup':200,'login':200,'authorized_me':200,'restored_session':200,
            'wrong_password':wrong,'anonymous_me':401,'test_storage':'removed','production_data_used':False}


if __name__=='__main__':
    try: print(json.dumps(run()))
    except (AssertionError,OSError,ValueError,RuntimeError,KeyError):
        print(json.dumps({'status':'blocked','reason':'local_auth_check_failed'}))
        raise SystemExit(1)
