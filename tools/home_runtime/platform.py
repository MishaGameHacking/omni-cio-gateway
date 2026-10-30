"""Install or reopen the dedicated, credential-free WSL candidate on the owner laptop."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request
import winreg

DISTRO = 'AnalystAI-Home'
BUILD = 'Ubuntu-24.04'
MARK = 'analyst-home-public-stage-1'
WSL = str(Path(os.environ['SystemRoot']) / 'System32' / 'wsl.exe')
IMAGES = (
    ('24.04.5', 'bb415d824822c4b878125729af451a5d18fb13d1cf5cbed9a7393ad64ac6039e'),
    ('24.04.4', '9b2f7730dc68227dd04a9f3e5eab86ad85caf556b8606ad94f1f29ff5c4fd3f5'),
    ('24.04.3', 'c74833a55e525b1e99e1541509c566bb3e32bdb53bf27ea3347174364a57f47c'),
)
BASE = Path(os.environ['LOCALAPPDATA']) / 'AnalystAI-HomeLab'
LOCATION = BASE / 'linux'
CLAIM = BASE / 'installation.json'
GIB = 1024**3


class Failure(Exception):
    pass


def require(condition, message):
    if not condition:
        raise Failure(message)


def plain(path):
    try:
        return all(stat.S_ISDIR((s := p.lstat()).st_mode) and not s.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
                   for p in (path, *path.parents))
    except OSError:
        return False


def text_output(data):
    return data.decode('utf-16-le' if b'\0' in data[:160] else 'utf-8', errors='replace').strip('\ufeff\0 \r\n')


def command(args, *, input_data=None, timeout=120, code):
    try:
        p = subprocess.run(args, input=input_data, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise Failure(code+'_timeout') from None
    if p.returncode:
        message = text_output(p.stdout) + ' ' + text_output(p.stderr)
        details = re.findall(r'0x[0-9a-fA-F]{8}|\b(?:WSL|Wsl)/[A-Za-z0-9_/.-]+',message)
        raise Failure(code+'_'+str(p.returncode)+('_'+details[-1][:100] if details else ''))
    return p.stdout


def guest(args, *, data=None, timeout=120, code):
    return command([WSL,'-d',DISTRO,'-u','root','--exec',*args],input_data=data,timeout=timeout,code=code)


def distro_entries():
    entries={}
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Lxss') as root:
        default = winreg.QueryValueEx(root,'DefaultDistribution')[0]
        for i in range(winreg.QueryInfoKey(root)[0]):
            name = winreg.EnumKey(root,i)
            with winreg.OpenKey(root,name) as key:
                try:
                    distro = winreg.QueryValueEx(key,'DistributionName')[0]
                    base = winreg.QueryValueEx(key,'BasePath')[0]
                except FileNotFoundError:
                    continue
                entries[distro] = os.path.normcase(os.path.normpath(base.removeprefix('\\\\?\\')))
    return default,entries


def save_claim(row):
    target=CLAIM.with_suffix('.next')
    require(not target.exists() and not target.is_symlink(),'pending_claim_review')
    with target.open('x',encoding='utf-8') as out:
        json.dump(row,out)
        out.flush()
        os.fsync(out.fileno())
    target.replace(CLAIM)


def fetch_image():
    part=BASE/'official-rootfs.wsl'
    require(not part.exists() and not part.is_symlink(),'unverified_download_already_present')
    for version, expected in IMAGES:
        file='ubuntu-'+version+'-wsl-amd64.wsl'
        url='https://releases.ubuntu.com/noble/'+file
        req=urllib.request.Request(url,headers={'Accept-Encoding':'identity','User-Agent':'AnalystAI-home/1'})
        try:
            response=urllib.request.urlopen(req,timeout=50)
        except urllib.error.HTTPError as err:
            if err.code==404:
                continue
            raise Failure('ubuntu_http_'+str(err.code)) from None
        except OSError as err:
            raise Failure('ubuntu_transport_'+type(err).__name__) from None
        try:
            with response, part.open('xb') as out:
                require(response.status==200 and response.geturl().startswith('https://'),'ubuntu_transport_invalid')
                h=hashlib.sha256()
                n=0
                deadline=time.monotonic()+900
                while block:=response.read(1024*1024):
                    n+=len(block)
                    require(n<1536*1024**2 and time.monotonic()<deadline,'ubuntu_download_bound')
                    h.update(block)
                    out.write(block)
            require(h.hexdigest()==expected,'ubuntu_manifest_hash_mismatch')
            return version,expected,part
        except BaseException:
            part.unlink(missing_ok=True)
            raise
    raise Failure('pinned_ubuntu_release_unavailable')


CONFIGURE = b"""import configparser,os,pathlib
assert os.geteuid()==0 and 'VERSION_ID="24.04"' in pathlib.Path('/etc/os-release').read_text()
p=pathlib.Path('/etc/wsl.conf')
assert not p.is_symlink()
c=configparser.ConfigParser(interpolation=None);c.optionxform=str
if p.exists():c.read(p)
for group,values in {'boot':{'systemd':'true'},'interop':{'enabled':'false','appendWindowsPath':'false'},'automount':{'enabled':'false'}}.items():
    if not c.has_section(group):c.add_section(group)
    for key,val in values.items():c.set(group,key,val)
marker=pathlib.Path('/etc/analyst-home-stage')
assert not marker.is_symlink() and (not marker.exists() or marker.read_text().strip()=='analyst-home-public-stage-1')
tmp=p.with_suffix('.analyst-new');assert not tmp.exists()
with tmp.open('x') as o:c.write(o)
tmp.chmod(0o644);tmp.replace(p)
marker.write_text('analyst-home-public-stage-1'+chr(10));marker.chmod(0o644)
"""
IDENTITY = """import json,pathlib,os
p=pathlib.Path
m=p('/proc/mounts').read_text().splitlines()
print(json.dumps({'marker':p('/etc/analyst-home-stage').read_text().strip(),'pid1':p('/proc/1/comm').read_text().strip(),
'uid':os.geteuid(),'windows_drive_mounted':any(x.split()[1] in ['/mnt/c','/mnt/d'] for x in m),
'version':next((l.split('=',1)[1].strip(chr(34)) for l in p('/etc/os-release').read_text().splitlines() if l.startswith('VERSION_ID=')),None)}))"""


def prepare():
    require(os.name=='nt' and os.environ.get('COMPUTERNAME')=='LAPTOP-NPSGA016' and Path(os.environ['USERPROFILE']).name.lower()=='networkservice','wrong_owner_host')
    require(plain(BASE.parent),'unsafe_parent')
    default, entries=distro_entries()
    require(BUILD in entries,'build_installation_missing')
    if BASE.exists():
        require(plain(BASE) and CLAIM.is_file() and not CLAIM.is_symlink(),'unowned_target_directory')
        claim=json.loads(CLAIM.read_text())
        require(claim.get('marker')==MARK and claim.get('distro')==DISTRO,'foreign_claim')
    else:
        require(DISTRO not in entries,'foreign_distribution')
        require(shutil.disk_usage(BASE.parent).free>=64*GIB,'physical_storage_below_installation_reserve')
        BASE.mkdir()
        claim={'marker':MARK,'distro':DISTRO,'phase':'new'}
        save_claim(claim)
    if DISTRO in entries:
        require(entries[DISTRO]==os.path.normcase(str(LOCATION)) and plain(LOCATION),'registered_location_mismatch')
    else:
        require(claim['phase'] in ('new','importing') and not LOCATION.exists(),'ambiguous_incomplete_installation')
        version,sha,archive=fetch_image()
        try:
            claim.update(phase='importing',ubuntu_image=version,sha256=sha)
            save_claim(claim)
            command([WSL,'--import',DISTRO,str(LOCATION),str(archive),'--version','2'],timeout=600,code='wsl_import')
        finally:
            archive.unlink(missing_ok=True)
        current,entries=distro_entries()
        require(current==default and entries.get(DISTRO)==os.path.normcase(str(LOCATION)),'registration_verification_failed')
    if claim.get('phase')!='ready':
        guest(['python3','-I','-'],data=CONFIGURE,code='ubuntu_configure',timeout=150)
        command([WSL,'--terminate',DISTRO],code='reload_owned_distribution')
        for _ in range(30):
            running=text_output(command([WSL,'-l','--running','-q'],code='running_list')).split()
            if DISTRO not in running:
                break
            time.sleep(1)
    state=json.loads(guest(['python3','-I','-c',IDENTITY],code='guest_identity',timeout=150))
    require(state=={'marker':MARK,'pid1':'systemd','uid':0,'windows_drive_mounted':False,'version':'24.04'},'guest_isolation_not_ready')
    require(distro_entries()[0]==default,'default_distribution_changed')
    claim.update(phase='ready')
    save_claim(claim)
    return {'status':'ready','source_image':claim['ubuntu_image'],'image_sha256':claim['sha256'],'linux':state,
            'free_bytes':shutil.disk_usage(BASE).free,'scope':'public_research_only'}


if __name__=='__main__':
    try:
        print(json.dumps(prepare()))
    except (OSError,ValueError,Failure) as err:
        print(json.dumps({'status':'blocked','reason':str(err) if isinstance(err,Failure) else type(err).__name__}))
        raise SystemExit(1)
