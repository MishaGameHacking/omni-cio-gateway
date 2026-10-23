"""Compile every tracked Python source, without executing it or contacting services."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
import warnings

WORKERS = 4


def tracked_sources(root: Path) -> list[str]:
    unresolved = subprocess.run(
        ['git', 'ls-files', '--unmerged', '-z'], cwd=root,
        capture_output=True, check=True, timeout=30,
    )
    if unresolved.stdout:
        raise ValueError('The Git index contains unresolved conflicts')
    result = subprocess.run(
        ['git', 'ls-files', '-z', '--', '*.py'], cwd=root,
        capture_output=True, check=True, timeout=30,
    )
    names = sorted(set(result.stdout.decode('utf-8').rstrip('\0').split('\0')))
    if not names or names == ['']:
        raise ValueError('No tracked Python sources were found')
    return names


def check_source(root: Path, name: str) -> dict | None:
    try:
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError('Source path is not a regular checkout file')
        # compile(bytes) honours the file's encoding cookie and catches invalid
        # control flow (e.g. return outside a function) without importing code.
        compile(path.read_bytes(), name, 'exec', dont_inherit=True)
    except SyntaxError as error:
        return {'path': name, 'error': type(error).__name__,
                'line': error.lineno, 'column': error.offset}
    except (OSError, ValueError) as error:
        return {'path': name, 'error': type(error).__name__}
    return None


def audit(root: Path, names: list[str]) -> dict:
    ordered = sorted(set(names))
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        findings = list(pool.map(lambda name: check_source(root, name), ordered))
    return {'files_checked': len(ordered), 'workers': WORKERS,
            'mode': 'compile-without-execution',
            'failures': [item for item in findings if item is not None]}


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    try:
        # Warning policy is unchanged: existing lint/Sonar owns warnings. Do not
        # print source lines (which may contain literals) from compiler warnings.
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', SyntaxWarning)
            report = audit(root, tracked_sources(root))
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print('PYTHON_SOURCE_AUDIT=' + json.dumps({'error': type(error).__name__}))
        return 1
    print('PYTHON_SOURCE_AUDIT=' + json.dumps(report, sort_keys=True))
    return int(bool(report['failures']))


if __name__ == '__main__':
    sys.exit(main())
