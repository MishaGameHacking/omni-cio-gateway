#!/usr/bin/env python3
"""Materialize the committed catalogue before Gradle on a reused Windows checkout.

Git can keep an unchanged CRLF worktree file after a later commit introduces
`text eol=lf`. Even clean/reset/checkout --force may retain that file while Git
reports it clean. Accept only the committed bytes or that exact checkout-only
conversion. This is not asset generation or a relaxed catalogue comparison.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = 'app/src/main/assets/spectrum3d/catalogue.json'
MAX_CATALOGUE_BYTES = 512 * 1024


def git(root: Path, *arguments: str) -> bytes:
    return subprocess.run(['git', *arguments], cwd=root, check=True,
                          capture_output=True, timeout=15).stdout


def checked_catalogue(root: Path) -> Path:
    path = root
    parts = CATALOGUE.split('/')
    for index, part in enumerate(parts):
        path = path / part
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400):
            raise ValueError('Catalogue checkout must not traverse a link or reparse point')
        if index < len(parts) - 1:
            if not stat.S_ISDIR(info.st_mode):
                raise ValueError('Catalogue checkout parent is not a directory')
        elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_CATALOGUE_BYTES:
            raise ValueError('Catalogue checkout must be one bounded regular file')
    return path


def committed_catalogue(root: Path) -> tuple[str, bytes]:
    if Path(os.fsdecode(git(root, 'rev-parse', '--show-toplevel').strip())).resolve() != root:
        raise ValueError('Catalogue preparation must run at its repository root')
    blob = git(root, 'rev-parse', '--verify', 'HEAD:' + CATALOGUE).strip().decode('ascii')
    if re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', blob) is None:
        raise ValueError('Catalogue has no unambiguous committed blob')
    if git(root, 'rev-parse', '--verify', ':' + CATALOGUE).strip().decode('ascii') != blob:
        raise ValueError('Staged catalogue differs from the checked-out commit')
    if int(git(root, 'cat-file', '-s', blob)) > MAX_CATALOGUE_BYTES:
        raise ValueError('Committed catalogue exceeds its size bound')
    expected = git(root, 'cat-file', 'blob', blob)
    if b'\r' in expected or not expected.endswith(b'\n'):
        raise ValueError('Committed catalogue must already contain canonical LF bytes')
    attributes = git(root, 'check-attr', '--cached', 'text', 'eol', '--', CATALOGUE).decode('utf-8').splitlines()
    if attributes != [CATALOGUE + ': text: set', CATALOGUE + ': eol: lf']:
        raise ValueError('Committed checkout attributes must pin catalogue text to LF')
    return blob, expected


def prepare_checkout(root: Path = ROOT) -> dict[str, object]:
    root = root.resolve(strict=True)
    path = checked_catalogue(root)
    blob, expected = committed_catalogue(root)
    actual = path.read_bytes()
    repaired = False
    if actual != expected:
        if actual != expected.replace(b'\n', b'\r\n'):
            raise ValueError('Catalogue differs from the commit by more than Git LF-to-CRLF conversion')
        # Write a new sibling and replace the known regular file. Never regenerate
        # assets here, mutate the index, or repair arbitrary changed source bytes.
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.catalogue-checkout-', delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(expected)
            checked_catalogue(root)
            if path.read_bytes() != actual:
                raise ValueError('Catalogue changed during checkout preparation')
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        repaired = True
    if checked_catalogue(root).read_bytes() != expected:
        raise ValueError('Catalogue checkout did not preserve the committed bytes')
    return {'catalogue': CATALOGUE, 'git_blob': blob, 'repaired_checkout_crlf': repaired,
            'before_crlf_count': actual.count(b'\r\n'),
            'before_sha256': hashlib.sha256(actual).hexdigest(),
            'canonical_sha256': hashlib.sha256(expected).hexdigest()}


if __name__ == '__main__':
    print('SPECTRUM_CHECKOUT=' + json.dumps(prepare_checkout(), sort_keys=True), flush=True)
