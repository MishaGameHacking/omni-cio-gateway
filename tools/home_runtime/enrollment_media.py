"""Stage only the signed-source Ubuntu image and published model for the protected Windows account."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile

spec=importlib.util.spec_from_file_location('checked_home_win',Path(__file__).with_name('platform.py'))
platform=importlib.util.module_from_spec(spec)
spec.loader.exec_module(platform)
MODEL='0b2a8980ce155fd97673d8e820b4d29d9c7d99b8fa6806f425d969b145bd52e0'
SIZE=3659530240
DIR=platform.BASE/'enrollment-media-v1'
UBUNTU=platform.IMAGES[0][1]


def matches(path, sha, size=None):
    if not path.exists(): return False
    s=path.lstat()
    platform.require(stat.S_ISREG(s.st_mode) and not s.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
                     and (size is None or s.st_size==size),'untrusted_media')
    with path.open('rb') as f:
        h=hashlib.file_digest(f,'sha256').hexdigest()
    platform.require(h==sha,'incorrect_media_digest')
    return True


def main():
    platform.require(os.environ.get('COMPUTERNAME')=='LAPTOP-NPSGA016' and Path(os.environ['USERPROFILE']).name.lower()=='networkservice',
                     'wrong_machine')
    platform.require(platform.plain(platform.BASE) and json.loads(platform.CLAIM.read_text()).get('phase')=='ready','no_home_lab')
    DIR.mkdir(exist_ok=True)
    platform.require(platform.plain(DIR),'untrusted_directory')
    os_file=DIR/'ubuntu.wsl'
    model=DIR/'model.litertlm'
    platform.require(shutil.disk_usage(DIR).free>20*1024**3,'insufficient_reserve')
    if not matches(os_file,UBUNTU):
        v,h,path=platform.fetch_image()
        try:
            platform.require(h==UBUNTU,'new_operating_system_not_reviewed')
            path.rename(os_file)
        finally:
            path.unlink(missing_ok=True)
    if not matches(model,MODEL,SIZE):
        with tempfile.NamedTemporaryFile(prefix='model-',dir=DIR,delete=False) as temp:
            candidate=Path(temp.name)
        try:
            with candidate.open('wb') as f:
                proc=subprocess.run([platform.WSL,'-d',platform.DISTRO,'-u','analyst-ai','--exec',
                                     '/bin/cat','/opt/analyst-local-ai/model.litertlm'],
                                    stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.DEVNULL,timeout=600)
            platform.require(proc.returncode==0 and matches(candidate,MODEL,SIZE),'failed_weight_copy')
            candidate.rename(model)
        finally:
            candidate.unlink(missing_ok=True)
    print('HOME_MEDIA_VERIFIED='+json.dumps({'ubuntu':'24.04.5','ubuntu_bytes':os_file.stat().st_size,'ubuntu_sha256':UBUNTU,
          'model_bytes':model.stat().st_size,'model_sha256':MODEL,'free_bytes':shutil.disk_usage(DIR).free,'private_data':False}))


if __name__=='__main__':
    try: main()
    except (OSError,ValueError,platform.Failure,subprocess.TimeoutExpired) as error:
        print('HOME_MEDIA_ERROR='+(str(error) if isinstance(error,platform.Failure) else type(error).__name__))
        raise SystemExit(1)
