"""Count regular files in run-numbered checkouts of this project on the owner laptop."""
from collections import Counter, defaultdict, deque
import json
import os
from pathlib import Path
import re
import shutil
import stat
import time


RUN_DIRECTORY = re.compile(r'[a-z][a-z0-9_-]{0,80}-(\d{10,12})-([1-9]\d{0,2})', re.I)
LINK = stat.FILE_ATTRIBUTE_REPARSE_POINT
MAX_ENTRIES = 2_000_000


def plain_directory(path):
    try:
        return all(stat.S_ISDIR((s := directory.lstat()).st_mode) and not s.st_file_attributes & LINK
                   for directory in (path, *path.parents))
    except OSError:
        return False


def workspaces(destination):
    project = 'omni-cio-gateway'
    current = Path(os.environ['GITHUB_WORKSPACE'])
    if (current.name.casefold(), current.parent.name.casefold(), current.parent.parent.name.casefold()) != (project, project, '_work'):
        raise RuntimeError('unexpected workspace layout')
    runner_roots = {destination / ('actions-runner' + slot) for slot in ('', '-1', '-2', '-3', '-4')}
    runner_roots.add(current.parents[2])
    parents = set()
    for runner in runner_roots:
        scoped = runner / '_work' / project
        for parent in (scoped, scoped / project):
            if parent.drive.casefold() == destination.drive.casefold() and plain_directory(parent):
                parents.add(parent)
    return sorted(parents)


def section(path, group):
    if group != 'other':
        return group
    if path.name.casefold() == '.git':
        return 'git'
    if path.parent.name.casefold() == 'build' and path.parent.parent.name.casefold() in {'app', 'ci-ui-driver'}:
        if path.name.casefold() in {'intermediates', 'tmp'}:
            return 'intermediate'
        if path.name.casefold() == 'outputs':
            return 'release_outputs'
    return group


def measure():
    drive = Path(os.environ['SystemDrive'] + os.sep)
    scan_start = time.time()
    deadline = time.monotonic() + 80
    parents = workspaces(drive)
    queue = deque()
    amounts, newest, folder_count = defaultdict(Counter), {}, Counter()
    inaccessible = 0
    for parent in parents:
        with os.scandir(parent) as entries:
            for entry in entries:
                match = RUN_DIRECTORY.fullmatch(entry.name)
                if not match or not plain_directory(Path(entry.path)):
                    continue
                rid, attempt = match.groups()
                key = (rid, int(attempt))
                stamp = entry.stat(follow_symlinks=False).st_mtime
                newest[key] = max(newest.get(key, 0), stamp)
                folder_count[key] += 1
                queue.append((Path(entry.path), key, 'other'))
    entries_seen = skipped_links = 0
    hit_limit = False
    while queue and not hit_limit:
        directory, key, kind = queue.popleft()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    if entries_seen % 256 == 0 and (entries_seen >= MAX_ENTRIES or time.monotonic() >= deadline):
                        hit_limit = True
                        break
                    entries_seen += 1
                    try:
                        index = entry.stat(follow_symlinks=False)
                    except OSError:
                        inaccessible += 1
                        continue
                    if index.st_file_attributes & LINK:
                        skipped_links += 1
                        continue
                    newest[key] = max(newest[key], index.st_mtime)
                    if stat.S_ISDIR(index.st_mode):
                        path = Path(entry.path)
                        queue.append((path, key, section(path, kind)))
                    elif stat.S_ISREG(index.st_mode):
                        amounts[key][kind] += index.st_size
        except OSError:
            inaccessible += 1
    totals = Counter()
    for value in amounts.values():
        totals.update(value)
    old = [key for key in amounts if amounts[key]['intermediate'] and newest[key] < scan_start - 86400]
    return {
        'free_bytes': shutil.disk_usage(drive).free, 'project_parents': len(parents),
        'checkout_directories': sum(folder_count.values()), 'run_attempts': len(folder_count), 'entries': entries_seen,
        'scan_complete': not hit_limit and inaccessible == 0, 'limited': hit_limit, 'unreadable': inaccessible,
        'skipped_reparse': skipped_links, 'logical_bytes': dict(totals),
        'older_intermediates': sum(amounts[key]['intermediate'] for key in old),
        'largest_older_intermediates': [
            {'run': rid, 'attempt': a, 'bytes': amounts[(rid, a)]['intermediate']}
            for rid, a in sorted(old, key=lambda key: amounts[key]['intermediate'], reverse=True)[:12]
        ],
    }


if __name__ == '__main__':
    if os.name != 'nt' or os.environ.get('COMPUTERNAME') != 'LAPTOP-NPSGA016':
        raise SystemExit('owner Windows required')
    print(json.dumps(measure()))
