"""Bind an emulator installation result to the actual file tested.

The device callback is supplied only after the parent verified its disposable
AVD. This module cannot select an attached physical device by itself.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

MAX_BYTES = 256 * 1024 * 1024


def apk_digest(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise ValueError('Test APK must be a regular file')
    expected = path.stat().st_size
    if not 0 < expected <= MAX_BYTES:
        raise ValueError('Invalid test APK size')
    total = 0
    digest = hashlib.sha256()
    with path.open('rb') as source:
        while True:
            chunk = source.read(min(1024 * 1024, expected - total + 1))
            if not chunk:
                break
            total += len(chunk)
            if total > expected:
                raise ValueError('Test APK grew during verification')
            digest.update(chunk)
    if total != expected:
        raise ValueError('Test APK changed during verification')
    return digest.hexdigest()


def record_install(device, results: list, label: str, path: Path, *, update: bool = False) -> None:
    record = {'test': label, 'success': False}
    results.append(record)
    try:
        before = apk_digest(path)
        record['apk_sha256'] = before
        command = ['install', '--no-streaming']
        if update:
            command.append('-r')
        response = device(*command, str(path), timeout=240)
        record['output'] = (response.stdout + response.stderr).strip()
        lines = response.stdout.strip().splitlines()
        if response.returncode != 0 or not lines or lines[-1].strip() != 'Success':
            raise RuntimeError('APK installation failed: ' + label)
        if apk_digest(path) != before:
            raise RuntimeError('APK changed while adb was installing it')
        record['success'] = True
    except Exception as error:
        record['error_type'] = type(error).__name__
        raise
    finally:
        print('INSTALL_RESULT=' + json.dumps(record, ensure_ascii=True), flush=True)
