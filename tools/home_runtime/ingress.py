"""Short public HTTPS rehearsal. Only four owner-auth calls in an empty test process are admitted."""
import base64
from contextlib import ExitStack
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
import subprocess
import tempfile
import threading
import time
import urllib.request

SMOKE=Path('/opt/analyst-home-tools/72e400cda5564ab2922843597ca9c66e20950c8a/smoke.py')
VERSION='2026.10.7'
DIGEST='1f99fb518b83dec2ba8d870a7cc991d82a77e6196295a3d2754ba17ab9f91872'
SIZE=40274445


def cloud_binary(dest):
    url='https://github.com/cloudflare/cloudflared/releases/download/'+VERSION+'/cloudflared-linux-amd64'
    h=hashlib.sha256()
    with urllib.request.urlopen(url,timeout=30) as response, dest.open('xb') as f:
        if response.status!=200 or not response.geturl().startswith('https://'): raise ValueError('download_failed')
        total=0
        for block in iter(lambda:response.read(1024**2),b''):
            total+=len(block)
            if total>SIZE: raise ValueError('size_limit')
            f.write(block)
            h.update(block)
    if total!=SIZE or h.hexdigest()!=DIGEST: raise ValueError('edge_digest_mismatch')
    dest.chmod(0o700)


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
        folder=Path(tmp); bin=folder/'cloudflared'
        cloud_binary(bin)
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
        env_edge={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','XDG_CONFIG_HOME':tmp}
        cf=subprocess.Popen([str(bin),'tunnel','--no-autoupdate','--protocol','http2','--metrics','127.0.0.1:0',
                             '--url','http://127.0.0.1:'+str(http.server_port)],cwd=tmp,env=env_edge,
                            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        def close():
            cf.terminate()
            try:cf.wait(timeout=8)
            except subprocess.TimeoutExpired:cf.kill();cf.wait()
        stack.callback(close)
        found=queue.Queue()
        def addresses():
            for line in cf.stdout:
                m=re.search(rb'https://[a-z0-9-]+\.trycloudflare\.com\b',line)
                if m:found.put(m[0].decode())
            found.put(None)
        threading.Thread(target=addresses,daemon=True).start()
        try: origin=found.get(timeout=65)
        except queue.Empty: raise ValueError('temporary_edge_timeout') from None
        if not origin: raise ValueError('temporary_edge_unavailable')
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
