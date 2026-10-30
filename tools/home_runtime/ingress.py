"""Short public HTTPS rehearsal. Only four owner-auth calls in an empty test process are admitted."""
import base64
from contextlib import ExitStack, contextmanager
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import queue
import re
import secrets
import shutil
import subprocess
import tempfile
import threading
import time

SMOKE=Path('/opt/analyst-home-tools/72e400cda5564ab2922843597ca9c66e20950c8a/smoke.py')
@contextmanager
def alternate_origin(folder, port):
    # Only a random QA credential, narrow gateway and public challenge enter this development tunnel.
    ssh=shutil.which('ssh',path='/usr/bin:/bin')
    if not ssh:
        raise ValueError('ssh_client_missing')
    args=[ssh,'-F','/dev/null','-T','-o','BatchMode=yes','-o','IdentityAgent=none','-o','IdentitiesOnly=yes',
          '-o','IdentityFile=none','-o','PasswordAuthentication=no','-o','KbdInteractiveAuthentication=no',
          '-o','UserKnownHostsFile='+str(folder/'ssh_hosts'),'-o','GlobalKnownHostsFile=/dev/null',
          '-o','StrictHostKeyChecking=accept-new','-o','ExitOnForwardFailure=yes','-o','ConnectTimeout=14',
          '-o','ServerAliveInterval=25','-R','80:127.0.0.1:'+str(port),'nokey@localhost.run','--','--output','json']
    proc=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                         env={'PATH':'/usr/bin:/bin','LANG':'C','HOME':str(folder)})
    found=queue.Queue()
    def addresses():
        for line in proc.stdout:
            match=re.search(rb'(?:https://)?([a-z0-9-]+\.(?:lhr\.life|localhost\.run))\b',line)
            if match and match[1] not in (b'admin.localhost.run',b'www.localhost.run',b'docs.localhost.run'):
                found.put('https://'+match[1].decode())
        found.put(None)
    threading.Thread(target=addresses,daemon=True).start()
    try:
        try: origin=found.get(timeout=32)
        except queue.Empty: raise ValueError('alternate_origin_timeout') from None
        if not origin: raise ValueError('alternate_origin_unavailable')
        yield origin
    finally:
        if proc.poll() is None: proc.terminate()
        try: proc.wait(timeout=6)
        except subprocess.TimeoutExpired: proc.kill();proc.wait()


def probe():
    if os.geteuid()==0 or not SMOKE.is_file(): raise ValueError('wrong_rehearsal_context')
    spec=importlib.util.spec_from_file_location('checked_auth',SMOKE)
    auth=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(auth)
    for _ in range(45):
        try:
            if auth.req(18157,'/health')==(200,{'status':'ok'}): break
        except OSError: pass
        time.sleep(1)
    else: raise ValueError('installed_api_unavailable')
    with tempfile.TemporaryDirectory(prefix='analyst-https-') as tmp, ExitStack() as stack:
        folder=Path(tmp)
        password,bootstrap,subject=secrets.token_urlsafe(32),secrets.token_urlsafe(36),'internet-check-'+secrets.token_hex(14)
        env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','BACKEND_PUBLIC_URL':'https://home-rehearsal.invalid',
             'DATABASE_PATH':str(folder/'auth.db'),'FERNET_KEY':base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
             'ANALYST_OWNER_TELEGRAM_SUB':subject,'ANALYST_OWNER_BOOTSTRAP_SECRET':bootstrap,
             'ANALYSIS_SCHEDULER_ENABLED':'false','AI_EXTERNAL_PROCESSING_APPROVED':'false','PYTHONDONTWRITEBYTECODE':'1'}
        port=stack.enter_context(auth.process(env))
        if auth.req(port,'/auth/owner/setup',{'password':password,'device_name':'external-rehearsal'},
                    {'X-Owner-Bootstrap':bootstrap})[0]!=200: raise ValueError('disposable_setup_failed')
        nonce=secrets.token_hex(18);proof=secrets.token_hex(32)
        stop=threading.Event()

        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def reply(self,status,body):
                raw=json.dumps(body).encode()
                self.send_response(status); self.send_header('Content-Type','application/json')
                self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(raw)))
                self.end_headers();self.wfile.write(raw)
            def do_GET(self):
                if self.path=='/probe/'+nonce:
                    healthy=auth.req(18157,'/health')==(200,{'status':'ok'})
                    self.reply(200 if healthy else 503,{'proof':proof} if healthy else {})
                elif self.path=='/me':
                    key=self.headers.get('Authorization','')
                    if len(key)>512: self.reply(400,{});return
                    self.reply(*auth.req(port,'/me',headers={'Authorization':key} if key else None))
                else: self.reply(404,{})
            def do_POST(self):
                if self.path=='/finish/'+nonce:
                    self.reply(200,{});stop.set();return
                if self.path!='/auth/owner/login':self.reply(404,{});return
                try:
                    size=int(self.headers.get('Content-Length','0'))
                    if not 0<size<1200:raise ValueError()
                    row=json.loads(self.rfile.read(size))
                    if not isinstance(row,dict) or set(row)-{'password','device_name'}:raise ValueError()
                    self.reply(*auth.req(port,self.path,row))
                except (ValueError,OSError): self.reply(400,{})
        http=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        stack.callback(http.server_close)
        t=threading.Thread(target=http.serve_forever,daemon=True);t.start()
        stack.callback(http.shutdown)
        origin=stack.enter_context(alternate_origin(folder,http.server_port))
        # Node encrypts this one-use message for the external verifier. It never goes to the action log.
        print(json.dumps({'origin':origin,'nonce':nonce,'proofHash':hashlib.sha256(proof.encode()).hexdigest(),
                          'password':password,'subject':subject}),flush=True)
        if not stop.wait(270): raise ValueError('external_verifier_timeout')


if __name__=='__main__':
    try: probe()
    except (ValueError,OSError,RuntimeError) as e:
        reason=str(e) if isinstance(e,ValueError) and re.fullmatch('[a-z_]{1,80}',str(e)) else type(e).__name__
        print(json.dumps({'error':reason}),flush=True)
        raise SystemExit(1)
