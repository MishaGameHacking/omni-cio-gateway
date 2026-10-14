"""Trusted local publisher; no HTTP write route, deployment or rollout activation.

CI evidence is an operator contract, not cryptographic proof of installation.
Android independently verifies the package and signing certificate.
"""
from __future__ import annotations

from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import tempfile
import time

try:
    from .client_updates import AndroidRelease, ReleaseChannel, ReleaseUnavailable, MAX_APK_BYTES
    from .release_lock import publication_lock
    from .release_bytes import copy_and_hash, ArtifactStreamError
    from .installation_evidence import from_ci_reports, InstallationEvidenceError
except ImportError:
    from client_updates import AndroidRelease, ReleaseChannel, ReleaseUnavailable, MAX_APK_BYTES
    from release_lock import publication_lock
    from release_bytes import copy_and_hash, ArtifactStreamError
    from installation_evidence import from_ci_reports, InstallationEvidenceError


def _evidence(report: dict, *, sha256: str, size: int, certificate: str) -> None:
    if not isinstance(report, dict):
        raise ReleaseUnavailable('apk_verification_evidence_mismatch')
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
    if 'installation_tests' in report:
        try:
            derived = from_ci_reports(report['installation_tests'], sha256)
        except InstallationEvidenceError as error:
            raise ReleaseUnavailable('installation_transcript_invalid') from error
        if tested != derived:
            raise ReleaseUnavailable('installation_transcript_conflict')


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


def _resume_prepared(channel: ReleaseChannel, directory: Path, candidate: AndroidRelease) -> AndroidRelease:
    retained_path = directory / (candidate.filename[:-4] + '.json')
    if not retained_path.exists() and not retained_path.is_symlink():
        return candidate
    # A crash may leave checked immutable bytes/metadata, but not current.json.
    # Recover the original timestamp; a retry must not rewrite immutable history.
    retained = channel.published(candidate.package_name, candidate.filename)
    if retained.certificate_sha256 != candidate.certificate_sha256:
        raise ReleaseUnavailable('release_certificate_changed')
    if replace(candidate, published_at=retained.published_at) != retained:
        raise ReleaseUnavailable('release_identity_changed')
    return retained


def _candidate(apk, report, expected_certificate, notes, now):
    if apk.is_symlink() or not apk.is_file():
        raise ReleaseUnavailable('invalid_apk')
    size = apk.stat().st_size
    if not 0 < size <= MAX_APK_BYTES:
        raise ReleaseUnavailable('invalid_apk')
    with apk.open('rb') as src:
        digest = copy_and_hash(src, size)
    _evidence(report, sha256=digest, size=size, certificate=expected_certificate)
    result = AndroidRelease.parse({
        'schema_version': 1, 'package_name': report.get('package'),
        'version_code': report.get('version_code'), 'version_name': report.get('version_name'),
        'apk_sha256': digest, 'apk_bytes': size, 'certificate_sha256': expected_certificate,
        'min_sdk': report.get('min_sdk'), 'notes': notes,
        'published_at': int(time.time()) if now is None else now})
    if result.published_at > int(time.time()):
        raise ReleaseUnavailable('release_not_published_yet')
    return result


def _existing_current(channel, directory, candidate):
    current_file = directory / 'current.json'
    if not current_file.exists() and not current_file.is_symlink():
        return None
    current = channel.current(candidate.package_name)
    if candidate.certificate_sha256 != current.certificate_sha256:
        raise ReleaseUnavailable('release_certificate_changed')
    if current.apk_sha256 == candidate.apk_sha256 and current.version_code == candidate.version_code:
        if replace(candidate, published_at=current.published_at) != current:
            raise ReleaseUnavailable('release_identity_changed')
        _retain(directory, current)
        return current
    if candidate.version_code <= current.version_code:
        raise ReleaseUnavailable('release_downgrade_or_version_reuse')
    _retain(directory, current)
    return None


def _stage_candidate(channel, directory, candidate, apk):
    with tempfile.NamedTemporaryFile(dir=directory, suffix='.apk.part', delete=False) as dst:
        staged = Path(dst.name)
    try:
        with staged.open('wb') as dst, apk.open('rb') as src:
            copy_and_hash(src, candidate.apk_bytes, dst, candidate.apk_sha256)
            dst.flush()
            os.fsync(dst.fileno())
        destination = directory / candidate.filename
        if destination.exists() or destination.is_symlink():
            channel.verified_file(candidate)
        else:
            os.replace(staged, destination)
            destination.chmod(0o644)
            _sync_directory(directory)
        channel.verified_file(candidate)
        _retain(directory, candidate)
        # Only complete, checked bytes may advance the mandatory threshold.
        _manifest(directory, directory / 'current.json', candidate, immutable=False)
    finally:
        staged.unlink(missing_ok=True)


def publish(root: Path, apk: Path, report: dict, *, expected_certificate: str,
            notes: str = '', now: int | None = None) -> AndroidRelease:
    try:
        candidate = _candidate(apk, report, expected_certificate, notes, now)
        channel = ReleaseChannel(root)
        directory = channel.directory(candidate.package_name)
        directory.mkdir(parents=True, exist_ok=True)
        with publication_lock(directory):
            current = _existing_current(channel, directory, candidate)
            if current is not None:
                return current
            candidate = _resume_prepared(channel, directory, candidate)
            _stage_candidate(channel, directory, candidate, apk)
        return candidate
    except ArtifactStreamError as error:
        raise ReleaseUnavailable('apk_changed_while_copying') from error
