"""Bounded private metadata inventory of the CI tool store and its service profile."""
from collections import Counter, deque
import ctypes
import json
import os
from pathlib import Path
import shutil
import stat
import time
import winreg

REPARSE = stat.FILE_ATTRIBUTE_REPARSE_POINT


def plain(path):
    try:
        return all(stat.S_ISDIR((s := p.lstat()).st_mode) and not s.st_file_attributes & REPARSE for p in (path, *path.parents))
    except OSError:
        return False


def profile_vhd():
    loc = r'Software\Microsoft\Windows\CurrentVersion\Lxss'
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, loc) as root:
        for i in range(winreg.QueryInfoKey(root)[0]):
            with winreg.OpenKey(root, winreg.EnumKey(root, i)) as dist:
                if winreg.QueryValueEx(dist, 'DistributionName')[0] != 'Ubuntu-24.04':
                    continue
                path = Path(winreg.QueryValueEx(dist, 'BasePath')[0]) / 'ext4.vhdx'
                index = path.stat()
                high = ctypes.c_uint32()
                win = ctypes.WinDLL('kernel32', use_last_error=True)
                func = win.GetCompressedFileSizeW
                func.argtypes=[ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_uint32)]
                func.restype=ctypes.c_uint32
                low=func(str(path), ctypes.byref(high))
                physical = None if low == 0xffffffff and ctypes.get_last_error() else (high.value << 32) | low
                return {'logical': index.st_size, 'allocated': physical, 'sparse': bool(index.st_file_attributes & 0x200)}
    return None


def inventory():
    if os.name != 'nt' or os.environ.get('COMPUTERNAME') != 'LAPTOP-NPSGA016':
        raise RuntimeError('owner Windows required')
    drive = Path(os.environ['SystemDrive'] + os.sep)
    stack = deque()
    totals, unreadable = Counter(), Counter()
    for slot in ('', '-2', '-3', '-4'):
        runner = drive / ('actions-runner' + slot)
        if not plain(runner):
            continue
        tools = runner / '_work' / '_tool'
        if plain(tools):
            for child in tools.iterdir():
                if plain(child):
                    stack.append((child, 'tools/' + child.name))
        for path, group in [(runner/'_diag','runner diagnostics'),(runner/'_work'/'_temp','runner temp')]:
            if plain(path):
                stack.append((path,group))
        for parent in (runner/'_work'/'omni-cio-gateway'/'omni-cio-gateway',):
            if plain(parent):
                for child in parent.iterdir():
                    if plain(child) and not child.name.rsplit('-',1)[-1].isdigit():
                        stack.append((child,'other project folders'))
    profile = Path(os.environ['USERPROFILE'])
    if profile.name.lower() == 'networkservice':
        for path, label in ((profile/'.gradle','gradle'),(profile/'.android'/'avd','service avd'),
                            (profile/'AppData'/'Local'/'Temp','service temp')):
            if not plain(path):
                continue
            if label != 'gradle':
                stack.append((path,label))
                continue
            for child in path.iterdir():
                if not plain(child):
                    continue
                if child.name == 'caches':
                    for folder in child.iterdir():
                        if plain(folder):
                            stack.append((folder,'gradle/caches/'+folder.name))
                else:
                    stack.append((child,'gradle/'+child.name))
    count = 0
    limit = time.monotonic() + 100
    while stack and time.monotonic() < limit and count < 3_000_000:
        path, group = stack.popleft()
        try:
            with os.scandir(path) as entries:
                for item in entries:
                    count += 1
                    try:
                        s = item.stat(follow_symlinks=False)
                    except OSError:
                        unreadable[group] += 1
                        continue
                    if s.st_file_attributes & REPARSE:
                        continue
                    if stat.S_ISDIR(s.st_mode):
                        stack.append((item.path,group))
                    elif stat.S_ISREG(s.st_mode):
                        totals[group] += s.st_size
        except OSError:
            unreadable[group] += 1
    try:
        vhd = profile_vhd()
    except OSError:
        vhd = None
    return {'free':shutil.disk_usage(drive).free, 'vhd':vhd, 'groups':dict(totals.most_common(60)),
            'unreadable':dict(unreadable),'partial':bool(stack),'entries':count}


if __name__ == '__main__':
    print(json.dumps(inventory()))
