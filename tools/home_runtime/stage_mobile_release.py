"""Stage a known signed Android release on the Lenovo, preserving its actual provenance."""
from contextlib import closing
import base64
import hashlib
import http.client
import json
import os
from pathlib import Path
import shutil
import socket
import ssl
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile

ORIGIN='https://analyst-ai-2941515.twc1.net'
PACKAGE='ru.omnicio.app.debug'
APK_SHA='d2ea37f2be711e129fbd575aa311d7802597a7e5c2c6c6c547f2e66c9301e4c7'
SIGNER='bbce9534fd4cfee8f3bdcaf51a31cce384a4f303f090c8cae9ec558227d59eb1'
BUILD_ZIP='e3ffcd2cfc819acfa6e9de9e8201f40270e25a3bde842befd3fd37836ab25af0'
MEMBER='omni-cio-gateway/omni-cio-gateway/server-version-client-41024346794-1/app/build/outputs/apk/preview/app-preview.apk'
SIZE=29_873_479
NAME=f'Analyst-AI-57-{APK_SHA}.apk'


class DirectOrigin(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise ValueError('unexpected_redirect')


def need(ok,reason):
    if not ok: raise ValueError(reason)


def reason(e):
    if isinstance(e,urllib.error.HTTPError): return 'http_'+str(e.code)
    if isinstance(e,urllib.error.URLError): return reason(e.reason)
    if isinstance(e,ssl.SSLCertVerificationError): return 'certificate_'+str(e.verify_code)
    if isinstance(e,socket.gaierror): return 'dns_'+str(e.errno)
    if isinstance(e,TimeoutError): return 'connection_timeout'
    if isinstance(e,ConnectionRefusedError): return 'connection_refused'
    if isinstance(e,ConnectionResetError): return 'connection_reset'
    if isinstance(e,OSError): return 'transport_'+str(e.errno)
    if isinstance(e,ValueError) and str(e).isidentifier(): return str(e)
    return type(e).__name__


def open_public(path,timeout=12):
    op=urllib.request.build_opener(DirectOrigin())
    return op.open(urllib.request.Request(ORIGIN+path,headers={'Accept-Encoding':'identity','Cache-Control':'no-cache',
                    'User-Agent':'AnalystAI-home-cutover/1'}),timeout=timeout)


def metadata():
    state={'health':0,'anonymous':0,'policy_status':0}
    for key,path in [('health','/health'),('anonymous','/me'),('policy_status','/client/update-policy?package_name='+PACKAGE)]:
        try:
            with open_public(path) as r:
                state[key]=r.status
                if key=='health': need(json.loads(r.read(1024))=={'status':'ok'},'invalid_health')
                if key=='policy_status':
                    raw=r.read(16385);need(len(raw)<=16384,'policy_size')
                    obj=json.loads(raw)
                    need(obj.get('package_name')==PACKAGE and obj.get('schema_version')==1,'unexpected_channel')
                    state['published_code']=obj.get('version_code')
                    state['raw']=base64.b64encode(raw).decode()
        except urllib.error.HTTPError as err:
            state[key]=err.code;err.close()
        except (ValueError,OSError) as err:
            state['phase']=key;state['reason']=reason(err);return state
    if (state['health'],state['anonymous'],state['policy_status'])!=(200,401,200):
        state['reason']='origin_status'
    return state


def stream_apk(out):
    with open_public('/client/apk/'+NAME,timeout=50) as r:
        need(r.status==200,'apk_http_error')
        count=0
        for b in iter(lambda:r.read(1024**2),b''):
            count+=len(b);need(count<=SIZE,'apk_oversize')
            out.write(b)
        need(count==SIZE,'truncated_apk')


def plain(path):
    for item in (path,*path.parents):
        need(not item.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT,'unexpected_link')


def home_cache():
    need(os.name=='nt' and os.getenv('COMPUTERNAME')=='LAPTOP-NPSGA016'
         and Path(os.environ['USERPROFILE']).name.casefold()=='networkservice','wrong_owner_host')
    root=Path(os.environ['LOCALAPPDATA'])/'AnalystAI-HomeLab'
    plain(root)
    obj=json.loads((root/'installation.json').read_bytes())
    need(obj.get('marker')=='analyst-home-public-stage-1' and obj.get('phase')=='ready','unowned_cache')
    cache=root/'verified-android-channel';cache.mkdir(exist_ok=True);plain(cache)
    need(shutil.disk_usage(root).free>2*1024**3,'disk_reserve')
    return cache


def save_public_bytes(path,data):
    if path.exists(): plain(path);need(path.read_bytes()==data,'conflicting_receipt');return
    with path.open('xb') as f: f.write(data)


def check_file(path,sha):
    plain(path)
    with path.open('rb') as f: need(hashlib.file_digest(f,'sha256').hexdigest()==sha,'file_digest_mismatch')


def preserve(cache,writer):
    with tempfile.NamedTemporaryFile(prefix='release-',dir=cache,delete=False) as tmp: source=Path(tmp.name)
    try:
        with source.open('wb') as out:
            writer(out);out.flush();os.fsync(out.fileno())
        need(source.stat().st_size==SIZE,'incorrect_apk_size')
        check_file(source,APK_SHA)
        target=cache/NAME
        if target.exists(): check_file(target,APK_SHA)
        else: source.rename(target)
    finally: source.unlink(missing_ok=True)


def linux(mode,out=None):
    wsl=Path(os.environ['SystemRoot'])/'System32'/'wsl.exe'
    return subprocess.run([str(wsl),'-d','AnalystAI-Home','-u','analyst-ai','--exec','/usr/bin/python3','-I','-',mode],
              input=Path(__file__).read_bytes(),stdout=out or subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=120)


def live(cache):
    for route in ('windows','ubuntu'):
        try:
            if route=='windows': row=metadata()
            else:
                p=linux('metadata');need(p.returncode==0,'linux_probe_exit');row=json.loads(p.stdout)
            summary={k:row[k] for k in ('health','anonymous','policy_status','published_code','phase','reason') if k in row}
            print('HOME_ORIGIN_ROUTE='+json.dumps({'network':route,**summary}),flush=True)
            if row.get('reason'): continue
            need(row.get('published_code')==57,'verify_new_release_independently')
            raw=base64.b64decode(row['raw'],validate=True); obj=json.loads(raw)
            need(obj.get('apk_sha256')==APK_SHA and obj.get('certificate_sha256')==SIGNER and
                 obj.get('apk_bytes')==SIZE and obj.get('apk_path')=='/client/apk/'+NAME,'signed_release_identity_changed')
            def download(out):
                if route=='windows': stream_apk(out)
                else: need(linux('apk',out).returncode==0,'ubuntu_apk_transfer')
            preserve(cache,download)
            save_public_bytes(cache/('policy-'+hashlib.sha256(raw).hexdigest()+'.json'),raw)
            return {'source':'live_production_https','route':route,'live_policy_verified':True,'public_health':200,'anonymous':401}
        except (OSError,http.client.HTTPException,subprocess.TimeoutExpired) as e:
            print('HOME_ORIGIN_ROUTE='+json.dumps({'network':route,'reason':reason(e)}),flush=True)
    return None


def archived(cache,archive):
    check_file(archive,BUILD_ZIP)
    with zipfile.ZipFile(archive) as z:
        info=z.getinfo(MEMBER);need(info.file_size==SIZE,'archived_apk_size')
        def writer(out):
            with z.open(info) as apk: shutil.copyfileobj(apk,out,1024**2)
        preserve(cache,writer)
    provenance={'source':'verified_build_archive','run_id':41024346794,'artifact_id':12963628069,
                'previous_publication_check':41029541401,'archive_sha256':BUILD_ZIP,'live_policy_verified':False}
    save_public_bytes(cache/('build-'+APK_SHA+'.json'),json.dumps(provenance,sort_keys=True).encode()+b'\n')
    return provenance


if __name__=='__main__':
    try:
        mode=sys.argv[1] if len(sys.argv)>1 else 'primary'
        if mode=='metadata': print(json.dumps(metadata()));raise SystemExit(0)
        if mode=='apk': stream_apk(sys.stdout.buffer);raise SystemExit(0)
        cache=home_cache()
        result=archived(cache,Path(sys.argv[2])) if mode=='from-build' else live(cache)
        if result is None: raise SystemExit(4)
        print('HOME_RELEASE_SNAPSHOT='+json.dumps({**result,'published_build':57,'package':PACKAGE,'verified_bytes':SIZE,
                    'apk_sha256':APK_SHA,'matches_verified_signed_build':True,'cached_on_lenovo':True,'private_data':False}),flush=True)
    except Exception as e:
        print('HOME_RELEASE_ERROR='+reason(e),flush=True);raise SystemExit(1)
