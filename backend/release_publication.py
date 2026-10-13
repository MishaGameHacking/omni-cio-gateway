"""Trusted local publisher; no HTTP write route, deployment or rollout activation.

CI evidence is an operator contract, not cryptographic proof of installation.
Android independently verifies the package and signing certificate.
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
    tested = report.get('installation_evidence')
    if not isinstance(tested, dict) or tested.get('apk_sha256') != sha256:
        raise ReleaseUnavailable('installation_evidence_missing')
    for api in ('33', '36'):
        checks = tested.get(api)
        if not isinstance(checks, dict) or any(checks.get(k) is not True for k in
                                               ('clean_install', 'upgrade', 'launch')):
            raise ReleaseUnavailable('installation_evidence_incomplete')


def _sync_directory(directory: Path) -> None:
    # Windows does not expose POSIX directory fsync. File flushes still apply.
    if os.name != 'nt':
        descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _manifest(directory: Path, destination: Path, release: AndroidRelease, *, immutable: bool) -> None:
    raw = {'schema_version': 1, **asdict(release)}
    if destination.is_symlink():
        raise ReleaseUnavailable('manifest_symlink')
    if immutable and destination.exists():
        with destination.open('rb') as stream:
            previous = stream.read(16_385)
        if len(previous) > 16_384 or json.loads(previous) != raw:
            raise ReleaseUnavailable('immutable_manifest_conflict')
        return
    with tempfile.NamedTemporaryFile(dir=directory, suffix='.json.part', delete=False, mode='w', encoding='utf-8') as dst:
        staged = Path(dst.name)
        try:
            json.dump(raw, dst, ensure_ascii=False)
            dst.flush()
            os.fsync(dst.fileno())
        except BaseException:
            dst.close()
            staged.unlink(missing_ok=True)
            raise
    try:
        os.replace(staged, destination)
        destination.chmod(0o644)
        _sync_directory(directory)
    finally:
        staged.unlink(missing_ok=True)


def _retain(directory: Path, release: AndroidRelease) -> None:
    _manifest(directory, directory / (release.filename[:-4] + '.json'), release, immutable=True)


def publish(root: Path, apk: Path, report: dict, *, expected_certificate: str,
            notes: str = '', now: int | None = None) -> AndroidRelease:
    if apk.is_symlink() or not apk.is_file():
        raise ReleaseUnavailable('invalid_apk')
    size = apk.stat().st_size
    if not 0 < size <= MAX_APK_BYTES:
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
    if candidate.published_at > int(time.time()):
        raise ReleaseUnavailable('release_not_published_yet')
    release_channel = ReleaseChannel(root)
    directory = release_channel.directory(candidate.package_name)
    directory.mkdir(parents=True, exist_ok=True)
    with publication_lock(directory):
        current_file = directory / 'current.json'
        if current_file.exists() or current_file.is_symlink():
            current = release_channel.current(candidate.package_name)
            if candidate.certificate_sha256 != current.certificate_sha256:
                raise ReleaseUnavailable('release_certificate_changed')
            if current.apk_sha256 == candidate.apk_sha256 and current.version_code == candidate.version_code:
                if candidate.min_sdk != current.min_sdk or candidate.version_name != current.version_name:
                    raise ReleaseUnavailable('release_identity_changed')
                _retain(directory, current)
                return current
            if candidate.version_code <= current.version_code:
                raise ReleaseUnavailable('release_downgrade_or_version_reuse')
            # Backfill metadata for the previous publication before superseding it.
            _retain(directory, current)
        with tempfile.NamedTemporaryFile(dir=directory, suffix='.apk.part', delete=False) as dst:
            staged = Path(dst.name)
        try:
            with staged.open('wb') as dst, apk.open('rb') as src:
                shutil.copyfileobj(src, dst, 1024 * 1024)
                dst.flush()
                os.fsync(dst.fileno())
            with staged.open('rb') as src:
                if hashlib.file_digest(src, 'sha256').hexdigest() != candidate.apk_sha256:
                    raise ReleaseUnavailable('apk_changed_while_copying')
            destination = directory / candidate.filename
            if destination.exists() or destination.is_symlink():
                release_channel.verified_file(candidate)
            else:
                os.replace(staged, destination)
                destination.chmod(0o644)
                _sync_directory(directory)
            release_channel.verified_file(candidate)
            _retain(directory, candidate)
            # Only complete, checked bytes may advance the mandatory threshold.
            _manifest(directory, current_file, candidate, immutable=False)
        finally:
            staged.unlink(missing_ok=True)
    return candidate
