"""Preserve the public, independently verified client release before moving its update origin."""
from contextlib import closing
import hashlib
import http.client
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import urllib.error
import urllib.request

ORIGIN='https://analyst-ai-2941515.twc1.net'
PACKAGE='ru.omnicio.app.debug'
APK_SHA='d2ea37f2be711e129fbd575aa311d7802597a7e5c2c6c6c547f2e66c9301e4c7'
SIGNER='bbce9534fd4cfee8f3bdcaf51a31cce384a4f303f090c8cae9ec558227d59eb1'
SIZE=29_873_479
NAME=f'Analyst-AI-57-{APK_SHA}.apk'


class DirectOrigin(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise ValueError('production_redirect')


def need(ok,reason):
    if not ok: raise ValueError(reason)


def plain(path):
    for item in (path,*path.parents):
        need(not item.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT,'unexpected_link')


def local_status(path):
    with closing(http.client.HTTPConnection('127.0.0.1',18158,timeout=3)) as conn:
        try:
            conn.request('GET',path)
            r=conn.getresponse()
            if path=='/health' and r.status==200:
                need(json.loads(r.read(1024))=={'status':'ok'},'unexpected_local_health')
            return r.status
        except (OSError,http.client.HTTPException):
            return 0


def run():
    need(os.name=='nt' and os.getenv('COMPUTERNAME')=='LAPTOP-NPSGA016'
         and Path(os.environ['USERPROFILE']).name.casefold()=='networkservice','wrong_owner_host')
    root=Path(os.environ['LOCALAPPDATA'])/'AnalystAI-HomeLab'
    plain(root)
    claim=json.loads((root/'installation.json').read_bytes())
    need(claim.get('marker')=='analyst-home-public-stage-1' and claim.get('phase')=='ready','unowned_cache')
    cache=root/'verified-android-channel'
    cache.mkdir(exist_ok=True)
    plain(cache)
    need(shutil.disk_usage(root).free>2*1024**3,'disk_reserve')
    opener=urllib.request.build_opener(DirectOrigin())
    def get(path):
        return opener.open(urllib.request.Request(ORIGIN+path,headers={'Accept-Encoding':'identity','User-Agent':'AnalystAI-home-cutover/1'}),timeout=18)
    with get('/health') as r:
        need(r.status==200 and json.loads(r.read(1024))=={'status':'ok'},'source_health')
    try:
        with get('/me') as r: anonymous=r.status
    except urllib.error.HTTPError as err:
        anonymous=err.code
        err.close()
    need(anonymous==401,'source_access_boundary')
    with get('/client/update-policy?package_name='+PACKAGE) as r:
        raw=r.read(16385)
        need(r.status==200 and len(raw)<=16384,'policy_bounds')
    release=json.loads(raw)
    need(release.get('schema_version')==1 and release.get('package_name')==PACKAGE,'unknown_channel')
    if release.get('version_code')!=57:
        print('HOME_CHANNEL_CHANGED='+json.dumps({'published_version':release.get('version_code') if type(release.get('version_code')) is int else None}))
        raise ValueError('verify_new_release_independently')
    need(release.get('apk_sha256')==APK_SHA and release.get('certificate_sha256')==SIGNER
         and release.get('apk_bytes')==SIZE and release.get('apk_path')=='/client/apk/'+NAME,'release_differs_from_signed_build')
    with tempfile.NamedTemporaryFile(prefix='download-',dir=cache,delete=False) as f:
        part=Path(f.name)
    try:
        h=hashlib.sha256();count=0
        with get('/client/apk/'+NAME) as r,part.open('wb') as dst:
            need(r.status==200,'missing_source_apk')
            for block in iter(lambda:r.read(1024**2),b''):
                count+=len(block);need(count<=SIZE,'apk_size_limit')
                h.update(block);dst.write(block)
            dst.flush();os.fsync(dst.fileno())
        need(count==SIZE and h.hexdigest()==APK_SHA,'downloaded_apk_mismatch')
        dest=cache/NAME
        if dest.exists():
            plain(dest)
            with dest.open('rb') as f: need(hashlib.file_digest(f,'sha256').hexdigest()==APK_SHA,'cached_apk_mismatch')
        else:
            part.rename(dest)
        policy=cache/('policy-'+hashlib.sha256(raw).hexdigest()+'.json')
        if policy.exists():
            plain(policy);need(policy.read_bytes()==raw,'cached_policy_mismatch')
        else:
            with policy.open('xb') as f: f.write(raw)
    finally:
        part.unlink(missing_ok=True)
    return {'source_health':200,'anonymous_profile':anonymous,'package':PACKAGE,'published_code':57,
            'version_name':release['version_name'],'verified_bytes':count,'apk_sha256':APK_SHA,
            'matches_signed_build':True,'policy_and_apk_on_lenovo':True,'target_health':local_status('/health'),
            'target_anonymous':local_status('/me'),'personal_data':False}


if __name__=='__main__':
    try: print('HOME_RELEASE_SNAPSHOT='+json.dumps(run()),flush=True)
    except Exception as err:
        message=str(err) if isinstance(err,ValueError) and str(err).isidentifier() else type(err).__name__
        print('HOME_RELEASE_ERROR='+message,flush=True)
        raise SystemExit(1)
