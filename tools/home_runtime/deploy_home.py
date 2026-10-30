"""Stage the real backend and its public model in the owner's independent guest."""
from contextlib import redirect_stdout
import hashlib
import http.client
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys

HERE=Path(__file__).resolve().parent
REV=sys.argv[1]
SHA='0b2a8980ce155fd97673d8e820b4d29d9c7d99b8fa6806f425d969b145bd52e0'
SIZE=3659530240
REMOTE='/opt/analyst-home-tools/'+REV
ALLOWED=('guest_setup.py','upstream_prepare.py','smoke.py','public_check.py')
PUSH="""import sys,pathlib,os,hashlib,re
assert os.geteuid()==0 and pathlib.Path('/etc/analyst-home-stage').read_text().strip()=='analyst-home-public-stage-1'
assert re.fullmatch('[a-f0-9]{40}',sys.argv[1]) and sys.argv[2] in ('guest_setup.py','upstream_prepare.py','smoke.py','public_check.py','ingress_probe.py')
root=pathlib.Path('/opt/analyst-home-tools');d=root/sys.argv[1]
for p in (root,d):
 p.mkdir(exist_ok=True,mode=0o755)
 assert p.resolve()==p and p.is_dir() and p.stat().st_uid==0 and not p.stat().st_mode&0o022
data=sys.stdin.buffer.read(1024*1024+1)
assert len(data)<=1024*1024 and hashlib.sha256(data).hexdigest()==sys.argv[3]
p=d/sys.argv[2]
if p.exists() or p.is_symlink():
 assert p.resolve()==p and p.is_file() and p.stat().st_uid==0 and p.read_bytes()==data
else:
 with p.open('xb') as f:f.write(data)
 p.chmod(0o644)
print('stored')
"""


def module(name,file):
    spec=importlib.util.spec_from_file_location(name,HERE/file)
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


p=module('owner_home_platform','platform.py')


def send_script(name):
    raw=(HERE/name).read_bytes()
    dest=p.guest(['python3','-I','-c',PUSH,REV,name,hashlib.sha256(raw).hexdigest()],
                 data=raw,code='stage_script')
    p.require(dest.strip()==b'stored','stage_write_unverified')


def report(step):
    args=[p.WSL,'-d',p.DISTRO,'-u','root','--exec','python3','-I',REMOTE+'/guest_setup.py',step]
    try:
        proc=subprocess.run(args,capture_output=True,timeout=1200)
        result=json.loads(proc.stdout)
    except (ValueError,subprocess.TimeoutExpired):
        raise p.Failure('guest_'+step+'_unavailable') from None
    if proc.returncode or result.get('status')=='blocked':
        raise p.Failure('guest_'+step+'_'+str(result.get('phase','unknown'))+'_'+str(result.get('reason','unavailable')))
    return result


def weights():
    if report('model-status')['status']=='verified':
        return {'status':'retained_verified','sha256':SHA}
    cache='/home/analyst-ci/.cache/analyst-local-research/'+SHA+'.litertlm'
    sender="""import os,shutil,stat,sys
fd=os.open(sys.argv[1],os.O_RDONLY|os.O_NOFOLLOW)
with os.fdopen(fd,'rb') as f:
 s=os.fstat(f.fileno())
 assert stat.S_ISREG(s.st_mode) and s.st_size==3659530240
 shutil.copyfileobj(f,sys.stdout.buffer,length=1024*1024)
"""
    lease=module('owner_build_lease','emulator_lease.py')
    with redirect_stdout(io.StringIO()),lease.exclusive_emulator():
        running=p.text_output(p.command([p.WSL,'-l','--running','-q'],code='read_build_state')).split()
        try:
            with subprocess.Popen([p.WSL,'-d',p.BUILD,'-u','analyst-ci','--exec','python3','-I','-c',sender,cache],
                                  stdout=subprocess.PIPE,stderr=subprocess.DEVNULL) as src:
                try:
                    with subprocess.Popen([p.WSL,'-d',p.DISTRO,'-u','root','--exec','python3','-I',REMOTE+'/guest_setup.py','receive-model'],
                                          stdin=src.stdout,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL) as dst:
                        src.stdout.close()
                        try: data=dst.communicate(timeout=640)[0]
                        except BaseException:
                            dst.kill()
                            raise
                    src.wait(timeout=20)
                    p.require(src.returncode==0 and dst.returncode==0,'weight_stream_failed')
                finally:
                    if src.poll() is None: src.kill()
        finally:
            if p.BUILD not in running:
                p.command([p.WSL,'--terminate',p.BUILD],code='restore_initial_build_state')
    result=json.loads(data)
    p.require(result.get('sha256')==SHA and result.get('bytes')==SIZE,'weight_stream_verification')
    return result


def before_waking_guest():
    running=p.text_output(p.command([p.WSL,'-l','--running','-q'],code='read_target_state')).split()
    con=http.client.HTTPConnection('127.0.0.1',18157,timeout=5)
    try:
        con.request('GET','/health')
        res=con.getresponse()
        healthy=res.status==200 and json.loads(res.read(2048))=={'status':'ok'}
    except (OSError,ValueError,http.client.HTTPException):
        healthy=False
    finally: con.close()
    return {'was_running':p.DISTRO in running,'windows_loopback_health':healthy}


def functional(script):
    args=[p.WSL,'-d',p.DISTRO,'-u','analyst-ai','--exec','/opt/analyst-ai/venv/bin/python','-I',REMOTE+'/'+script]
    run=subprocess.run(args,capture_output=True,timeout=170)
    try: row=json.loads(run.stdout)
    except ValueError: return {'status':'blocked','reason':'probe_exit_'+str(run.returncode)}
    return row


def main():
    p.require(bool(re.fullmatch('[0-9a-f]{40}',REV)),'invalid_release')
    print('HOME_CONTINUITY_RESULT='+json.dumps(before_waking_guest()),flush=True)
    status=p.prepare()
    p.require(status['status']=='ready','platform_unavailable')
    for name in ALLOWED: send_script(name)
    api=report('api')
    print('HOME_API_RESULT='+json.dumps(api),flush=True)
    print('HOME_WEIGHTS_RESULT='+json.dumps(weights()),flush=True)
    worker=report('ai')
    print('HOME_WORKER_RESULT='+json.dumps(worker),flush=True)
    auth=functional('smoke.py')
    print('HOME_AUTH_RESULT='+json.dumps(auth),flush=True)
    research=functional('public_check.py')
    print('HOME_PUBLIC_RESULT='+json.dumps(research),flush=True)
    p.require(auth.get('status')=='passed' and research.get('status')=='verified','functional_probe_incomplete')


if __name__=='__main__':
    try: main()
    except (OSError,ValueError,p.Failure,subprocess.TimeoutExpired) as error:
        reason=str(error) if isinstance(error,p.Failure) else type(error).__name__
        print('HOME_INSTALL_ERROR='+re.sub('[^A-Za-z0-9_./+-]','',reason)[:190],flush=True)
        raise SystemExit(1)
