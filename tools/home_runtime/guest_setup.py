"""Activate the pinned application in the home rehearsal guest, without production credentials."""
import base64
from contextlib import contextmanager
import fcntl
import grp
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

MARKER='analyst-home-public-stage-1'
COMMIT='853090e11dcefef693366159c97316e55045c4c9'
TREE='2166246fb48fc3067ddd776bfe8172b9b13b9e83'
ROOT=Path('/opt/analyst-ai')
LOCAL=Path('/opt/analyst-local-ai')
RELEASE=Path('/opt/analyst-source')/COMMIT
ETC=Path('/etc/analyst-ai')
DB=Path('/var/lib/analyst-ai')
UNITS=Path('/etc/systemd/system')
PORT=18158 if Path('/etc/analyst-protected-home').is_file() else 18157
BASE=f'http://127.0.0.1:{PORT}'
ENV={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LANG':'C.UTF-8','DEBIAN_FRONTEND':'noninteractive',
     'NEEDRESTART_MODE':'l','PIP_CONFIG_FILE':'/dev/null','PIP_DISABLE_PIP_VERSION_CHECK':'1',
     'GIT_TERMINAL_PROMPT':'0','PYTHONDONTWRITEBYTECODE':'1'}
PHASE='validate'


class Blocked(RuntimeError):
    pass


def require(ok, reason):
    if not ok:
        raise Blocked(reason)


def command(args, tag, *, cwd=None, timeout=240):
    try:
        result=subprocess.run(args, env=ENV, cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise Blocked(tag+'_timeout') from None
    if result.returncode:
        message=(result.stderr+result.stdout)[-16000:].lower()
        reason=next((key for key,marker in [('dns',b'resolution'),('tls',b'certificate verify'),
                    ('package_missing',b'unable to locate package'),('version_missing',b'no matching distribution'),
                    ('connection',b'could not connect'),('permission',b'permission denied'),
                    ('space',b'no space left'),('locked',b'could not get lock')] if marker in message),'process')
        raise Blocked(tag+'_'+reason+'_'+str(result.returncode))
    return result.stdout.decode('utf-8',errors='replace').strip()


def contents(path, data, mode=0o644):
    require(path.parent.is_dir() and path.parent.resolve()==path.parent,'unsafe_parent')
    if path.exists() or path.is_symlink():
        require(not path.is_symlink() and path.is_file() and path.stat().st_uid==0 and path.stat().st_mode&0o022==0
                and path.read_bytes()==data,'existing_configuration_differs')
    else:
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,mode)
        with os.fdopen(fd,'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    path.chmod(mode)


def directory(path, mode=0o755):
    if not path.exists() and not path.is_symlink():
        path.mkdir(mode=mode)
    require(path.is_dir() and not path.is_symlink() and path.resolve()==path and path.stat().st_uid==0
            and path.stat().st_mode&0o022==0,'unsafe_runtime_directory')


def validate():
    require(os.geteuid()==0 and Path('/etc/analyst-home-stage').read_text().strip()==MARKER
            and Path('/proc/1/comm').read_text().strip()=='systemd','wrong_guest')
    require(not Path('/mnt/c/Windows').exists(),'host_drives_exposed')


@contextmanager
def lock():
    with open('/run/analyst-home-install.lock','a+b') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX)
        yield


def vendor():
    file=Path(__file__).with_name('upstream_prepare.py')
    spec=importlib.util.spec_from_file_location('home_verified_preparation',file)
    p=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(p)
    require(p.SOURCE==COMMIT and p.LOCAL==LOCAL,'source_policy_mismatch')
    return p


def packages():
    names=['ca-certificates','git','python3-venv','libc++1','libc++abi1','libatomic1']
    missing=[n for n in names if subprocess.run(['dpkg-query','-W','-f=${Status}',n],
             capture_output=True).stdout.strip()!=b'install ok installed']
    if missing:
        command(['apt-get','-o','Acquire::Retries=2','update','-qq'],'ubuntu_index',timeout=360)
        command(['apt-get','-o','Acquire::Retries=2','install','-y','--no-install-recommends',*missing],'ubuntu_packages',timeout=480)
    return missing


def identities():
    try:
        grp.getgrnam('analyst-ai')
    except KeyError:
        command(['groupadd','--system','analyst-ai'],'service_group')
    for name in ['analyst-ai','analyst-local-ai']:
        try:
            row=pwd.getpwnam(name)
        except KeyError:
            command(['useradd','--system','--gid','analyst-ai','--no-create-home','--home-dir','/nonexistent',
                     '--shell','/usr/sbin/nologin',name],'service_identity')
            row=pwd.getpwnam(name)
        require(row.pw_uid>0 and row.pw_gid==grp.getgrnam('analyst-ai').gr_gid and row.pw_shell=='/usr/sbin/nologin',
                'unexpected_service_identity')


def status(path):
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(BASE+path,timeout=4) as r:
            return r.status, json.loads(r.read(16384))
    except urllib.error.HTTPError as e:
        return e.code,{}
    except (OSError,ValueError):
        return 0,{}


def config():
    directory(ETC,0o750)
    path=ETC/'backend.env'
    fixed={'ANALYST_OWNER_TELEGRAM_SUB':'home-rehearsal-unbound-v1','BACKEND_PUBLIC_URL':'https://home-rehearsal.invalid',
           'DATABASE_PATH':str(DB/'home-rehearsal.db'),'ANALYSIS_SCHEDULER_ENABLED':'false',
           'AI_EXTERNAL_PROCESSING_APPROVED':'false','AI_USER_DAILY_RUB':'0','AI_PROJECT_DAILY_RUB':'0',
           'LOCAL_RESEARCH_ENABLED':'true'}
    if path.exists() or path.is_symlink():
        require(path.is_file() and not path.is_symlink() and path.stat().st_uid==0
                and path.stat().st_mode&0o077==0,'stage_configuration_not_private')
        lines=path.read_text().splitlines()
        vals=dict(l.split('=',1) for l in lines)
        key=vals.pop('FERNET_KEY','')
        require(len(lines)==len(fixed)+1 and vals==fixed and len(base64.urlsafe_b64decode(key))==32,'foreign_data_configuration')
    else:
        key=base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
        contents(path,(''.join(k+'='+v+'\n' for k,v in fixed.items())+'FERNET_KEY='+key+'\n').encode(),0o600)


def install_api():
    global PHASE
    PHASE='packages'
    installed=packages()
    identities()
    directory(ROOT)
    directory(LOCAL)
    p=vendor()
    PHASE='source'
    source=p.checkout_source()
    require(source==RELEASE and command(['git','rev-parse','HEAD^{tree}'],'source_tree',cwd=source)==TREE,'source_tree_mismatch')
    files=command(['git','ls-files'],'source_file_list',cwd=source).splitlines()
    require(len(files)==1179,'source_count_mismatch')
    PHASE='backend_dependencies'
    py=ROOT/'venv/bin/python'
    if not py.exists():
        command(['/usr/bin/python3','-m','venv',str(ROOT/'venv')],'backend_venv')
    command([str(py),'-m','pip','install','--only-binary=:all:','--no-cache-dir','-r',str(source/'backend/requirements.txt')],
            'backend_pip',timeout=420)
    command([str(py),'-m','pip','check'],'backend_pip_check')
    PHASE='owner_unit'
    config()
    name='analyst-ai-owner.service'
    contents(UNITS/name,(source/'deploy'/name).read_bytes())
    drop=UNITS/(name+'.d')
    directory(drop)
    override=('[Service]\nWorkingDirectory='+str(source/'backend')+'\nExecStart=\nExecStart='+str(ROOT/'venv/bin/uvicorn')+
              f' owner_app:create_app --factory --host 127.0.0.1 --port {PORT} --workers 1 --no-access-log\n')
    contents(drop/'home.conf',override.encode())
    command(['systemctl','daemon-reload'],'systemd_reload')
    command(['systemctl','enable','--now',name],'owner_start')
    for _ in range(60):
        if status('/health')==(200,{'status':'ok'}):
            break
        time.sleep(1)
    code, data=status('/auth/owner/status')
    require(status('/health')==(200,{'status':'ok'}) and status('/me')[0]==401 and code==200
            and data.get('configured') is False,'owner_health_or_boundary')
    import sqlite3
    with sqlite3.connect('file:'+str(DB/'home-rehearsal.db')+'?mode=ro',uri=True) as db:
        require(db.execute('select count(*) from users').fetchone()==(0,),'shadow_contains_accounts')
        wal=db.execute('pragma journal_mode').fetchone()[0]
    if wal!='wal':
        # The marker and the empty owner-bound database were checked above. Stop only the rehearsal writer.
        PHASE='rehearsal_wal'
        command(['systemctl','stop',name],'pause_shadow')
        try:
            code=("import os,sqlite3; assert os.geteuid()!=0; "
                  "c=sqlite3.connect('/var/lib/analyst-ai/home-rehearsal.db',timeout=8); "
                  "assert c.execute('select count(*) from users').fetchone()==(0,); "
                  "assert c.execute('select telegram_sub from installation_owner').fetchone()==('home-rehearsal-unbound-v1',); "
                  "assert c.execute('pragma journal_mode=wal').fetchone()==('wal',); "
                  "assert c.execute('pragma quick_check').fetchone()==('ok',); c.close()")
            command(['runuser','-u','analyst-ai','--','/usr/bin/python3','-I','-c',code],'sqlite_wal')
        finally:
            command(['systemctl','start',name],'resume_shadow')
        for _ in range(40):
            if status('/health')==(200,{'status':'ok'}): break
            time.sleep(1)
        require(status('/health')==(200,{'status':'ok'}) and status('/me')[0]==401,'restarted_boundary')
        with sqlite3.connect('file:'+str(DB/'home-rehearsal.db')+'?mode=ro',uri=True) as db:
            wal=db.execute('pragma journal_mode').fetchone()[0]
    require(wal=='wal','journal_not_verified')
    return {'status':'api_ready','source':COMMIT,'tree':TREE,'files':len(files),'installed_packages':installed,
            'health':200,'anonymous_me':401,'production_accounts':0,'journal':wal,'scope':'loopback_rehearsal'}


def receive_model():
    p=vendor()
    directory(LOCAL)
    dest=LOCAL/'model.litertlm'
    if dest.exists():
        require(not dest.is_symlink() and dest.stat().st_uid==0 and dest.stat().st_size==p.MODEL_BYTES
                and p.digest_file(dest)==p.MODEL_SHA,'invalid_existing_model')
        return {'status':'already_verified','sha256':p.MODEL_SHA}
    fd,filename=tempfile.mkstemp(prefix='.incoming-',dir=LOCAL)
    h=hashlib.sha256()
    n=0
    try:
        with os.fdopen(fd,'wb') as handle:
            for block in iter(lambda:sys.stdin.buffer.read(1024**2),b''):
                n+=len(block)
                require(n<=p.MODEL_BYTES,'model_oversize')
                h.update(block)
                handle.write(block)
            handle.flush()
            os.fsync(handle.fileno())
        require(n==p.MODEL_BYTES and h.hexdigest()==p.MODEL_SHA,'model_checksum_mismatch')
        os.chmod(filename,0o644)
        os.replace(filename,dest)
    finally:
        Path(filename).unlink(missing_ok=True)
    return {'status':'model_verified','sha256':p.MODEL_SHA,'bytes':n}


def model_status():
    p=vendor()
    path=LOCAL/'model.litertlm'
    if not path.exists() and not path.is_symlink():
        return {'status':'needed'}
    require(path.is_file() and not path.is_symlink() and path.stat().st_uid==0
            and path.stat().st_size==p.MODEL_BYTES and p.digest_file(path)==p.MODEL_SHA,'invalid_existing_model')
    return {'status':'verified','sha256':p.MODEL_SHA}


def install_model():
    global PHASE
    PHASE='worker_files'
    p=vendor()
    require(model_status()['status']=='verified','missing_weights')
    p.stage_files(RELEASE)
    PHASE='worker_wheel'
    p.install_runtime()
    name='analyst-local-research.service'
    contents(UNITS/name,(LOCAL/'deploy'/name).read_bytes())
    PHASE='worker_start'
    command(['systemctl','daemon-reload'],'worker_reload')
    command(['systemctl','enable','--now',name],'worker_enable')
    import socket
    sock='/run/analyst-local-ai/research.sock'
    for _ in range(100):
        if Path(sock).is_socket() and command(['systemctl','is-active',name],'worker_active')=='active':
            return {'status':'worker_ready','sha256':p.MODEL_SHA,'service':name,'socket':'unix','runtime':'0.18.1'}
        time.sleep(1)
    raise Blocked('worker_socket_timeout')


if __name__=='__main__':
    try:
        validate()
        method={'api':install_api,'receive-model':receive_model,'model-status':model_status,'ai':install_model}[sys.argv[1]]
        with lock():
            result=method()
        print(json.dumps(result))
    except (OSError,ValueError,KeyError,Blocked) as e:
        reason=str(e) if isinstance(e,(Blocked,ValueError)) and re.fullmatch(r'[a-z0-9_]{1,115}',str(e)) else type(e).__name__
        print(json.dumps({'status':'blocked','phase':PHASE,'reason':reason}))
        raise SystemExit(1)
