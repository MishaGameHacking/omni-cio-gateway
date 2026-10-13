"""Local trusted-publisher primitive. Never exposed as an HTTP route.

The publisher must run existing apksigner/zipalign/installation checks on the
EXACT bytes first. Evidence validation is an operator/CI contract, not a new
cryptographic attestation service. APK signing is independently checked by the
Android client and by Android itself. This module does not upload, delete,
create servers, enable enforcement, or change signing keys.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import time

try:
    from .client_updates import AndroidRelease, ReleaseChannel, ReleaseUnavailable, MAX_APK_BYTES
except ImportError:
    from client_updates import AndroidRelease, ReleaseChannel, ReleaseUnavailable, MAX_APK_BYTES


@contextmanager
def publication_lock(directory: Path):
    lock = directory / '.publishing'
    # Do not auto-break this lock: another host/process may still be publishing.
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    try:
        yield
    finally:
        lock.unlink()


def _evidence(report: dict, *, sha256: str, size: int, certificate: str) -> None:
    expected = {'sha256': sha256, 'bytes': size, 'certificate_sha256': certificate,
                'signature_v2': True, 'zipalign_16kb': True, 'debuggable': False, 'test_only': False}
    if any(type(report.get(k)) is not type(v) or report.get(k) != v for k, v in expected.items()):
        raise ReleaseUnavailable('apk_verification_evidence_mismatch')
    # Prepared by the release runner after the install tests, including hash
    # binding; never infer success from absent/skipped tests.
    tested = report.get('installation_evidence')
    if not isinstance(tested, dict) or tested.get('apk_sha256') != sha256:
        raise ReleaseUnavailable('installation_evidence_missing')
    for api in ('33', '36'):
        checks = tested.get(api)
        if not isinstance(checks, dict) or any(checks.get(k) is not True for k in
                                               ('clean_install', 'upgrade', 'launch')):
            raise ReleaseUnavailable('installation_evidence_incomplete')


def publish(root: Path, apk: Path, report: dict, *, expected_certificate: str,
            notes: str = '', now: int | None = None) -> AndroidRelease:
    size = apk.stat().st_size
    if apk.is_symlink() or not 0 < size <= MAX_APK_BYTES:
        raise ReleaseUnavailable('invalid_apk')
    with apk.open('rb') as src:
        digest = hashlib.file_digest(src, 'sha256').hexdigest()
    _evidence(report, sha256=digest, size=size, certificate=expected_certificate)
    candidate = AndroidRelease.parse({
        'schema_version': 1, 'package_name': report.get('package'),
        'version_code': report.get('version_code'), 'version_name': report.get('version_name'),
        'apk_sha256': digest, 'apk_bytes': size, 'certificate_sha256': expected_certificate,
        'min_sdk': report.get('min_sdk'), 'notes': notes,
        'published_at': int(time.time()) if now is None else now})
    directory = root / candidate.package_name
    directory.mkdir(parents=True, exist_ok=True)
    with publication_lock(directory):
        current_file = directory / 'current.json'
        if current_file.exists():
            current = ReleaseChannel(root).current(candidate.package_name)
            if current.apk_sha256 == candidate.apk_sha256 and current.version_code == candidate.version_code:
                return current
            if candidate.version_code <= current.version_code:
                raise ReleaseUnavailable('release_downgrade_or_version_reuse')
            if candidate.certificate_sha256 != current.certificate_sha256:
                raise ReleaseUnavailable('release_certificate_changed')
        temporary: list[Path] = []
        try:
            with tempfile.NamedTemporaryFile(dir=directory, suffix='.apk.part', delete=False) as dst:
                staged = Path(dst.name)
                temporary.append(staged)
                with apk.open('rb') as src:
                    shutil.copyfileobj(src, dst, 1024 * 1024)
                dst.flush()
                os.fsync(dst.fileno())
            with staged.open('rb') as src:
                if hashlib.file_digest(src, 'sha256').hexdigest() != candidate.apk_sha256:
                    raise ReleaseUnavailable('apk_changed_while_copying')
            destination = directory / candidate.filename
            os.replace(staged, destination)
            destination.chmod(0o644)
            ReleaseChannel(root).verified_file(candidate)
            with tempfile.NamedTemporaryFile(dir=directory, suffix='.json.part', delete=False, mode='w', encoding='utf-8') as dst:
                manifest = Path(dst.name)
                temporary.append(manifest)
                json.dump({'schema_version': 1, **asdict(candidate)}, dst, ensure_ascii=False)
                dst.flush()
                os.fsync(dst.fileno())
            # Threshold changes only AFTER the complete APK exists and hashes match.
            os.replace(manifest, current_file)
            current_file.chmod(0o644)
        finally:
            for path in temporary:
                path.unlink(missing_ok=True)
    return candidate
