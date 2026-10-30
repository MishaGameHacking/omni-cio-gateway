"""Clear stale wheels left in pip's disposable unpack folders in the runner profile."""
from collections import Counter, defaultdict
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from emulator_lease import exclusive_emulator
from storage import LINK, plain_directory

WHEEL_DIR = re.compile(r'pip-(?:unpack|ephem-wheel-cache)-[a-z0-9_]{6,12}\Z', re.I)
WHEEL_FILE = re.compile(r'[a-z0-9_.+!-]+-[a-z0-9_.+!-]+-[a-z0-9_.]+-[a-z0-9_.]+-[a-z0-9_.]+\.whl(?:\.metadata)?\Z', re.I)


def family(name, is_dir):
    n=name.lower()
    for pattern in (r'(pip-[a-z-]+)-[a-z0-9_]{6,12}$', r'(omnicio-[a-z-]+)-[a-z0-9_]{5,12}$',
                    r'(robolectric-[a-z-]+)\d+$', r'(gradle-[a-z-]+)[0-9._-]+$'):
        m=re.fullmatch(pattern,n)
        if m:
            return m[1]
    if re.fullmatch(r'tmp[a-z0-9_]{6,12}(?:\.[a-z0-9]{1,9})?',n):
        return ('tmpdir' if is_dir else 'tmpfile') + (Path(n).suffix or '-unsuffixed')
    if not is_dir:
        return 'other-file' + (Path(n).suffix[:14] or '-unsuffixed')
    if len(n)>45 or any(c not in 'abcdefghijklmnopqrstuvwxyz-_.0123456789' for c in n):
        return 'other-directory'
    return re.sub(r'[a-f0-9]{7,}|\d{4,}', 'N', n)


def classify_file(path):
    try:
        with open(path,'rb') as f:
            prefix=f.read(16)
    except OSError:
        return 'unavailable'
    for key, label in ((b'SQLite format 3\0','sqlite'),(b'PK\x03\x04','zip'),(b'%PDF','pdf'),
                       (b'\x1f\x8b','gzip'),(b'MZ','windows executable'),(b'\x7fELF','elf')):
        if prefix.startswith(key):
            return label
    return 'other'


def on_windows(pip_idle):
    drive = Path(os.environ['SystemDrive'] + os.sep)
    root = Path(os.environ['USERPROFILE'])/'AppData'/'Local'/'Temp'
    expected = Path(os.environ['SystemRoot'])/'ServiceProfiles'/'NetworkService'/'AppData'/'Local'/'Temp'
    if root!=expected or not plain_directory(root):
        raise ValueError('unexpected temporary directory')
    root=Path('\\\\?\\'+str(root))
    cutoff=time.time()-86400
    deadline=time.monotonic()+440
    totals, ages, entries, removed = Counter(), Counter(), Counter(), Counter()
    sampled=defaultdict(Counter)
    counts=Counter()
    before=shutil.disk_usage(drive).free
    complete=True
    with redirect_stdout(io.StringIO()), exclusive_emulator(), os.scandir(root) as listing:
        for item in listing:
            if time.monotonic()>=deadline:
                complete=False
                break
            try:
                top=item.stat(follow_symlinks=False)
                if top.st_file_attributes & LINK:
                    continue
                is_dir=stat.S_ISDIR(top.st_mode)
                label=family(item.name,is_dir)
                entries[label]+=1
                top_path=Path(item.path)
                if not is_dir:
                    if stat.S_ISREG(top.st_mode):
                        totals[label]+=top.st_size
                        if top.st_mtime<cutoff: ages[label]+=top.st_size
                        if label.startswith('tmpfile') and top.st_size>=16384 and sum(sampled[label].values())<16:
                            sampled[label][classify_file(top_path)]+=1
                    continue
                eligible=bool(WHEEL_DIR.fullmatch(item.name) and pip_idle and top.st_mtime<cutoff)
                dirs, wheels, pending=[],[],[top_path]
                while pending:
                    d=pending.pop()
                    if eligible: dirs.append(d)
                    try:
                        with os.scandir(d) as sub:
                            for e in sub:
                                s=e.stat(follow_symlinks=False)
                                if s.st_file_attributes & LINK:
                                    eligible=False
                                    continue
                                if s.st_mtime>=cutoff: eligible=False
                                if stat.S_ISDIR(s.st_mode):
                                    pending.append(Path(e.path))
                                elif stat.S_ISREG(s.st_mode):
                                    totals[label]+=s.st_size
                                    if s.st_mtime<cutoff: ages[label]+=s.st_size
                                    if eligible and WHEEL_FILE.fullmatch(e.name):
                                        wheels.append((Path(e.path),s.st_size,s.st_mtime_ns))
                    except OSError:
                        counts['unreadable']+=1
                        eligible=False
                if not eligible or not wheels:
                    continue
                for path,length,stamp in wheels:
                    try:
                        s=path.lstat()
                        if not stat.S_ISREG(s.st_mode) or s.st_file_attributes & LINK or s.st_size!=length or s.st_mtime_ns!=stamp:
                            continue
                        if path.suffix.lower()=='.whl' and classify_file(path)!='zip':
                            continue
                        path.unlink()
                        counts['wheels_or_metadata_removed']+=1
                        removed[label]+=length
                    except OSError:
                        counts['busy_or_unreadable']+=1
                for d in reversed(dirs):
                    try: d.rmdir()
                    except OSError: pass
            except OSError:
                counts['unreadable']+=1
    return {'before':before,'after':shutil.disk_usage(drive).free, 'counts':counts,'removed':removed,'complete':complete,
            'pip_idle':pip_idle,'groups':[{'family':k,'bytes':v,'older':ages[k],'roots':entries[k],
                                        'sample_signatures':dict(sampled[k])}
                                       for k,v in totals.most_common(30)]}


def remove_cold_unpack(path, cutoff):
    stats = Counter()
    try:
        top = path.lstat()
        if top.st_file_attributes & LINK or not stat.S_ISDIR(top.st_mode) or top.st_mtime >= cutoff:
            return stats
        files = []
        with os.scandir(path) as children:
            for entry in children:
                s = entry.stat(follow_symlinks=False)
                if s.st_file_attributes & LINK or not stat.S_ISREG(s.st_mode) or s.st_mtime >= cutoff:
                    return stats
                if not WHEEL_FILE.fullmatch(entry.name):
                    continue
                if entry.name.lower().endswith('.whl') and classify_file(entry.path) != 'zip':
                    continue
                files.append((Path(entry.path), s.st_size, s.st_mtime_ns))
        for member, length, stamp in files:
            s = member.lstat()
            if s.st_file_attributes & LINK or not stat.S_ISREG(s.st_mode) or s.st_size!=length or s.st_mtime_ns!=stamp:
                continue
            member.unlink()
            stats['files'] += 1
            stats['logical_bytes'] += length
        try:
            path.rmdir()
            stats['retired_unpack_folders'] += 1
        except OSError:
            pass  # A foreign or locked file keeps its original name and folder.
    except OSError:
        stats['busy_or_inaccessible'] += 1
    return stats


def finish_wheels(pip_idle):
    from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
    drive = Path(os.environ['SystemDrive']+os.sep)
    path = Path(os.environ['USERPROFILE'])/'AppData'/'Local'/'Temp'
    expect = Path(os.environ['SystemRoot'])/'ServiceProfiles'/'NetworkService'/'AppData'/'Local'/'Temp'
    if path!=expect or not plain_directory(path):
        raise ValueError('wrong service temp')
    root = Path('\\\\?\\'+str(path))
    total = Counter()
    deadline = time.monotonic()+1020
    cutoff = time.time()-86400
    complete = True
    before = shutil.disk_usage(drive).free
    if not pip_idle:
        return {'before':before,'after':before,'counts':{},'complete':False,'pip_idle':False}
    with redirect_stdout(io.StringIO()), exclusive_emulator(), os.scandir(root) as items, ThreadPoolExecutor(max_workers=4) as pool:
        pending = set()
        for entry in items:
            if time.monotonic() >= deadline:
                complete = False
                break
            if not WHEEL_DIR.fullmatch(entry.name) or not entry.name.lower().startswith('pip-unpack-'):
                continue
            pending.add(pool.submit(remove_cold_unpack, Path(entry.path), cutoff))
            if len(pending) >= 32:
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                for job in done:
                    total.update(job.result())
        for job in pending:
            total.update(job.result())
    return {'before':before,'after':shutil.disk_usage(drive).free,'counts':total,'complete':complete,'pip_idle':True}


if __name__ == '__main__':
    if os.name!='nt' or os.environ.get('COMPUTERNAME')!='LAPTOP-NPSGA016' or os.environ.get('GITHUB_RUN_ATTEMPT')!='1':
        raise SystemExit('owner host and initial job required')
    operation = finish_wheels if sys.argv[2:] == ['finish-unpack'] else on_windows
    print(json.dumps(operation(sys.argv[1]=='idle')))
