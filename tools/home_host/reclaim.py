"""Run-scoped Android cleanup on the owner's Windows host. No installed software is removed."""
import collections
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from emulator_lease import exclusive_emulator
from storage import LINK, RUN_DIRECTORY, plain_directory, workspaces

DAY = 86400
MODULES = ('app', 'ci-ui-driver')
GENERATED = ('intermediates', 'tmp', 'generated', 'kotlin')
KEEP = {'.jks', '.ks', '.keystore', '.p12', '.pfx', '.key', '.pem', '.db', '.sqlite', '.sqlite3', '.aab', '.apk'}


def extended(path):
    name = str(path)
    return path if name.startswith('\\\\?\\') else Path('\\\\?\\' + name)


def roots():
    for parent in workspaces(Path(os.environ['SystemDrive'] + os.sep)):
        for d in parent.iterdir():
            match = RUN_DIRECTORY.fullmatch(d.name)
            if match and plain_directory(d) and d.stat().st_mtime < time.time() - DAY:
                yield (match[1], int(match[2])), extended(d)


def builds(checkout):
    if not any((checkout / s).is_file() for s in ('settings.gradle.kts', 'settings.gradle')):
        return
    for mod in MODULES:
        module = checkout / mod
        if not plain_directory(module) or not any((module / n).is_file() for n in ('build.gradle.kts', 'build.gradle')):
            continue
        for name in GENERATED:
            d = module / 'build' / name
            if plain_directory(d):
                yield d


def candidates():
    for key, d in roots():
        for checkout in (d, d / 'source', d / 'checkout', d / 'app-source', d / 'project', d / 'client'):
            if plain_directory(checkout):
                for target in builds(checkout):
                    yield key, target


def remove_generated(target, cutoff, report):
    # The caller holds the shared host build lease. Recheck the tree without following links.
    if not plain_directory(target) or target.name not in GENERATED:
        return
    pending = [target]
    dirs, files = [], []
    try:
        while pending:
            parent = pending.pop()
            if parent.stat().st_mtime >= cutoff:
                report['recent_directories_skipped'] += 1
                return
            dirs.append(parent)
            with os.scandir(parent) as entries:
                for entry in entries:
                    s = entry.stat(follow_symlinks=False)
                    if s.st_file_attributes & LINK or s.st_mtime >= cutoff:
                        report['changed_or_linked_directories_skipped'] += 1
                        return
                    path = Path(entry.path)
                    if stat.S_ISDIR(s.st_mode):
                        pending.append(path)
                    elif stat.S_ISREG(s.st_mode) and path.suffix.lower() not in KEEP and not path.name.lower().startswith('.env'):
                        files.append((path, s.st_size, s.st_mtime_ns))
        for path, length, stamp in files:
            try:
                s = path.lstat()
                if s.st_file_attributes & LINK or not stat.S_ISREG(s.st_mode) or s.st_size != length or s.st_mtime_ns != stamp:
                    report['changed_files_skipped'] += 1
                    continue
                path.unlink()
                report['generated_files_removed'] += 1
                report['logical_bytes_removed'] += length
            except OSError:
                report['locked_or_inaccessible_files'] += 1
        for d in reversed(dirs):
            try:
                d.rmdir()
            except OSError:
                pass   # Retain non-empty directories, including protected files.
    except OSError:
        report['unreadable_directories_skipped'] += 1


def main(operation):
    if os.name != 'nt' or os.environ.get('COMPUTERNAME') != 'LAPTOP-NPSGA016':
        raise ValueError('owner host required')
    if operation == 'list':
        return {'runs': sorted(set(key for key, _ in candidates()))}
    if operation != 'apply' or os.environ.get('GITHUB_RUN_ATTEMPT') != '1':
        raise ValueError('unexpected maintenance request')
    verified = {(str(r), int(a)) for r, a in json.load(sys.stdin)}
    drive = Path(os.environ['SystemDrive'] + os.sep)
    before = shutil.disk_usage(drive).free
    counts = collections.Counter()
    with redirect_stdout(io.StringIO()), exclusive_emulator():
        cutoff = time.time() - DAY
        for key, d in candidates():
            if key in verified:
                counts['inspected_generated_directories'] += 1
                remove_generated(d, cutoff, counts)
    return {'before': before, 'after': shutil.disk_usage(drive).free, 'counts': counts, 'verified_runs': len(verified)}


if __name__ == '__main__':
    print(json.dumps(main(sys.argv[1])))
