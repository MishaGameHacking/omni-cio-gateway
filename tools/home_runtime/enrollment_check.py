"""Qualify the staged Windows enrollment and observe the foreground WSL lifecycle on the real host."""
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import time

HERE=Path(__file__).parent
HOME=Path(os.environ['LOCALAPPDATA'])/'AnalystAI-HomeLab'
SHELL=Path(os.environ['SystemRoot'])/'System32'/'WindowsPowerShell'/'v1.0'/'powershell.exe'
WSL=Path(os.environ['SystemRoot'])/'System32'/'wsl.exe'
FILES=('Install-AnalystAIHome.ps1','Run-AnalystAIHome.ps1','smoke.py','protected_guest.py','guest_setup.py','upstream_prepare.py')


def require(ok, reason):
    if not ok: raise ValueError(reason)


def plain(path):
    for p in (path,*path.parents):
        require(not p.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT,'reparse_point')


def ps(file,*options,timeout=360):
    p=subprocess.run([str(SHELL),'-NoLogo','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(file),*options],
                     stdin=subprocess.DEVNULL,capture_output=True,timeout=timeout)
    if p.returncode:
        # Expose only known script exception labels, no environment, paths or PowerShell transcript.
        low=(p.stdout+p.stderr).decode('utf-8',errors='ignore').lower()
        keys=('content verification','reparse point','cannot bind','syntax','not recognized','is not recognized',
              'parse','empty string','access is denied','cannot find','exception calling','ambiguous','not supported')
        raise ValueError('powershell_'+next((k.replace(' ','_') for k in keys if k in low),'exit')+'_'+str(p.returncode))
    return p.stdout.decode('utf-8',errors='replace').strip()


def api():
    c=http.client.HTTPConnection('127.0.0.1',18157,timeout=5)
    try:
        c.request('GET','/health')
        r=c.getresponse()
        if r.status!=200 or json.loads(r.read(1024))!={'status':'ok'}: return False
        c.request('GET','/me')
        r=c.getresponse();r.read(8192)
        return r.status==401
    except (OSError, ValueError, http.client.HTTPException):
        return False
    finally:
        c.close()


def stage():
    require(os.environ.get('COMPUTERNAME')=='LAPTOP-NPSGA016' and Path(os.environ['USERPROFILE']).name.lower()=='networkservice','wrong_machine')
    plain(HOME)
    text=(HERE/FILES[0]).read_text('utf-8')
    package=re.search(r"(?m)^\$PackageCode = '([a-f0-9]{20})'$",text)[1]
    dest=HOME/('enroll-'+package)
    dest.mkdir(exist_ok=True);plain(dest)
    for n in FILES:
        before=(HERE/n).read_bytes();target=dest/n
        if target.exists():
            plain(target)
            require(target.read_bytes()==before,'existing_kit_differs')
        else:
            with target.open('xb') as out: out.write(before)
    verified=json.loads(ps(dest/FILES[0],'-VerifyOnly'))
    require(verified.get('package')==package and verified.get('items')==7,'incomplete_media_review')
    out=ps(dest/FILES[1],'-TransportCheck')
    expected=re.search(r'EXPECTED_TRANSPORT=([a-f0-9]{64})',out)
    got=re.search(r'(?m)^([a-f0-9]{64})\s+-\s*$',out)
    require(expected and got and got[1]==expected[1],'binary_transport')
    print('HOME_ENROLLMENT_KIT='+json.dumps({'package':package,'items_verified':7,'model_and_image_verified':True,
          'powershell_transport_bytes':1048601,'native_linux_digest_match':True,
          'shell_syntax':'verified','free_bytes':shutil.disk_usage(HOME).free,
          'installer_sha256':hashlib.sha256((dest/FILES[0]).read_bytes()).hexdigest(),'windows_boot_registered':False}),flush=True)
    # Monitor with Windows HTTP only after the foreground WSL process is created.
    with subprocess.Popen([str(WSL),'-d','AnalystAI-Home','-u','analyst-ai','--exec','/bin/sleep','160'],
                          stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL) as client:
        try:
            for _ in range(40):
                if api(): break
                time.sleep(1)
            require(client.poll() is None and api(),'initial_windows_health')
            start=time.monotonic()
            time.sleep(95)
            require(client.poll() is None and api(),'foreground_windows_health')
            print('HOME_FOREGROUND_OBSERVED='+json.dumps({'seconds':int(time.monotonic()-start),
                  'health':200,'anonymous_me':401,'ordinary_windows_client':True,'boot_tested':False}),flush=True)
        finally:
            if client.poll() is None: client.terminate()


if __name__=='__main__':
    try: stage()
    except (OSError,ValueError,TypeError,subprocess.TimeoutExpired) as e:
        reason=str(e) if isinstance(e,ValueError) and re.fullmatch('[a-z0-9_]{1,96}',str(e)) else type(e).__name__
        print('HOME_ENROLLMENT_ERROR='+reason,flush=True)
        raise SystemExit(1)
