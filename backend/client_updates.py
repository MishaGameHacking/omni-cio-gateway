"""Mandatory client compatibility and first-party APK distribution.

No cloud/SSH access and no public release-publishing endpoint. Production keeps
its old behavior until ANDROID_UPDATES_ENABLED=true is explicitly set after a
verified, install-tested APK is present. Client version headers are compatibility
claims, NOT authentication or device attestation.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass, asdict
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time
from typing import Callable, Mapping

from fastapi import Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse

PACKAGES = frozenset({'ru.omnicio.app.debug', 'ru.omnicio.app'})
MAX_APK_BYTES = 256 * 1024 * 1024
CODE_HEADER = 'X-Analyst-Version-Code'
PACKAGE_HEADER = 'X-Analyst-Package'
DIGEST_PATTERN = re.compile(r'[a-f0-9]{64}')
NO_CACHE = {'Cache-Control': 'no-store', 'Vary': 'X-Analyst-Package, X-Analyst-Version-Code'}


class ReleaseUnavailable(ValueError):
    """No trustworthy, downloadable current release can be established."""


def _integer(value: object, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ReleaseUnavailable('invalid_release_integer')
    return value


@dataclass(frozen=True)
class AndroidRelease:
    package_name: str
    version_code: int
    version_name: str
    apk_sha256: str
    apk_bytes: int
    certificate_sha256: str
    min_sdk: int
    published_at: int
    notes: str = ''

    @classmethod
    def parse(cls, raw: object) -> 'AndroidRelease':
        if not isinstance(raw, dict) or type(raw.get('schema_version')) is not int or raw.get('schema_version') != 1:
            raise ReleaseUnavailable('unsupported_release_schema')
        required = set(cls.__dataclass_fields__) - {'notes'}
        if not required <= raw.keys():
            raise ReleaseUnavailable('incomplete_release')
        if not isinstance(raw['package_name'], str) or raw['package_name'] not in PACKAGES:
            raise ReleaseUnavailable('unknown_release_package')
        for key in ('apk_sha256', 'certificate_sha256'):
            if not isinstance(raw[key], str) or not DIGEST_PATTERN.fullmatch(raw[key]):
                raise ReleaseUnavailable('invalid_release_digest')
        name = raw['version_name']
        notes = raw.get('notes', '')
        if not isinstance(name, str) or not 1 <= len(name) <= 64 or any(ord(c) < 32 for c in name):
            raise ReleaseUnavailable('invalid_release_name')
        if not isinstance(notes, str) or len(notes) > 4000:
            raise ReleaseUnavailable('invalid_release_notes')
        return cls(raw['package_name'], _integer(raw['version_code'], 1, 2_100_000_000), name,
                   raw['apk_sha256'], _integer(raw['apk_bytes'], 1, MAX_APK_BYTES),
                   raw['certificate_sha256'], _integer(raw['min_sdk'], 33, 100),
                   _integer(raw['published_at'], 1, 32_503_680_000), notes)

    @property
    def filename(self) -> str:
        return f'Analyst-AI-{self.version_code}-{self.apk_sha256}.apk'

    def public(self) -> dict:
        return {'schema_version': 1, **asdict(self),
                'minimum_version_code': self.version_code,
                'apk_path': f'/client/apk/{self.filename}',
                'version_is_not_attestation': True}


def _file_digest(path: str, expected_size: int) -> str:
    """Rehash bytes, not a cached stat result; filesystem timestamps may collide.

    A same-size rewrite can retain mtime/ctime on some filesystems. Treating
    those fields as an integrity proof would let modified bytes pass the gate.
    Bound reading even if a file grows between stat and open.
    """
    if type(expected_size) is not int or not 0 < expected_size <= MAX_APK_BYTES:
        raise ReleaseUnavailable('invalid_release_size')
    digest = hashlib.sha256()
    received = 0
    with open(path, 'rb') as stream:
        while True:
            chunk = stream.read(min(1024 * 1024, expected_size - received + 1))
            if not chunk:
                break
            received += len(chunk)
            if received > expected_size:
                raise ReleaseUnavailable('release_size_changed')
            digest.update(chunk)
    if received != expected_size:
        raise ReleaseUnavailable('release_size_changed')
    return digest.hexdigest()


class ReleaseChannel:
    def __init__(self, root: Path):
        self.root = root

    def directory(self, package: str) -> Path:
        if not isinstance(package, str) or package not in PACKAGES:
            raise ReleaseUnavailable('unknown_release_package')
        directory = self.root / package
        if directory.is_symlink() or not directory.resolve().is_relative_to(self.root.resolve()):
            raise ReleaseUnavailable('release_directory_invalid')
        return directory

    def _read_manifest(self, package: str, manifest: Path) -> AndroidRelease:
        try:
            if manifest.is_symlink() or not manifest.is_file():
                raise ReleaseUnavailable('invalid_release_manifest')
            with manifest.open('rb') as stream:
                content = stream.read(16_385)
            if len(content) > 16_384:
                raise ReleaseUnavailable('invalid_release_manifest')
            release = AndroidRelease.parse(json.loads(content))
            if release.package_name != package or release.published_at > int(time.time()):
                raise ReleaseUnavailable('release_not_active')
            self.verified_file(release)
            return release
        except (OSError, ValueError, TypeError, KeyError) as error:
            raise ReleaseUnavailable('release_unavailable') from error

    def current(self, package: str) -> AndroidRelease:
        return self._read_manifest(package, self.directory(package) / 'current.json')

    def published(self, package: str, filename: str) -> AndroidRelease:
        """A rollout must not invalidate an APK URL a client has already received."""
        if not valid_apk_filename(filename):
            raise ReleaseUnavailable('invalid_release_filename')
        directory = self.directory(package)
        manifest = directory / (filename[:-4] + '.json')
        if manifest.exists() or manifest.is_symlink():
            release = self._read_manifest(package, manifest)
        else:
            # Compatibility with the initial channel before retained metadata.
            release = self.current(package)
        if release.filename != filename:
            raise ReleaseUnavailable('release_filename_mismatch')
        return release

    def verified_file(self, release: AndroidRelease) -> Path:
        path = self.directory(release.package_name) / release.filename
        try:
            stat = path.stat()
            if path.is_symlink() or not path.is_file() or stat.st_size != release.apk_bytes:
                raise ReleaseUnavailable('release_file_invalid')
            if _file_digest(str(path.resolve()), release.apk_bytes) != release.apk_sha256:
                raise ReleaseUnavailable('release_checksum_invalid')
            return path
        except OSError as error:
            raise ReleaseUnavailable('release_file_unavailable') from error


def valid_apk_filename(filename: str) -> bool:
    return isinstance(filename, str) and re.fullmatch(
        r'Analyst-AI-[1-9][0-9]{0,9}-[a-f0-9]{64}\.apk', filename) is not None


def channel() -> ReleaseChannel:
    return ReleaseChannel(Path(os.getenv('ANDROID_RELEASE_DIR', '/var/lib/analyst-ai/releases')))


def enabled() -> bool:
    return os.getenv('ANDROID_UPDATES_ENABLED', 'false').lower() == 'true'


def initialize(connect: Callable[[], sqlite3.Connection]) -> None:
    with closing(connect()) as db:
        db.execute('''CREATE TABLE IF NOT EXISTS client_versions(
            session_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
            package_name TEXT NOT NULL, version_code INTEGER NOT NULL,
            release_sha256 TEXT, observed_at INTEGER NOT NULL)''')
        db.execute('CREATE INDEX IF NOT EXISTS client_versions_user ON client_versions(user_id)')
        db.commit()


def _client_code(value: str | None) -> int:
    if not value or not re.fullmatch(r'[1-9][0-9]{0,9}', value):
        return 0
    code = int(value)
    return code if code <= 2_100_000_000 else 0


def _service_error() -> HTTPException:
    return HTTPException(503, detail='update_channel_unavailable', headers=NO_CACHE)


def enforce(connect: Callable[[], sqlite3.Connection], *, user_id: int,
            authorization: str, headers: Mapping[str, str]) -> None:
    """Invoke ONLY after validating the session. Unknown/headerless clients get 426."""
    if not enabled():
        return
    package = headers.get(PACKAGE_HEADER.lower()) or headers.get(PACKAGE_HEADER) or ''
    code = _client_code(headers.get(CODE_HEADER.lower()) or headers.get(CODE_HEADER))
    # Legacy preview clients have no header. They are denied, not allowed to
    # poison an updated session belonging to a different device.
    target_package = package if package in PACKAGES else 'ru.omnicio.app.debug'
    try:
        release = channel().current(target_package)
    except ReleaseUnavailable:
        raise _service_error() from None
    supported = package == release.package_name and code == release.version_code
    session_hash = hashlib.sha256(authorization[7:].strip().encode()).hexdigest()
    with closing(connect()) as db:
        db.execute('''INSERT INTO client_versions VALUES(?,?,?,?,?,?)
            ON CONFLICT(session_hash) DO UPDATE SET
            package_name=excluded.package_name, version_code=excluded.version_code,
            release_sha256=excluded.release_sha256, observed_at=excluded.observed_at''',
            (session_hash, user_id, package, code, release.apk_sha256 if supported else None, int(time.time())))
        db.commit()
    if not supported:
        raise HTTPException(426, detail={'code': 'client_update_required',
                            'message': 'Обновите Analyst AI, чтобы продолжить.',
                            'release': release.public()}, headers=NO_CACHE)


def user_can_run(connect: Callable[[], sqlite3.Connection], user_id: int) -> bool:
    """Pause account jobs until at least one unexpired session reports current APK.

    A stale device is always gated itself; it cannot disable another device's
    valid current session. Data is retained. Already-sent network calls cannot
    be unsent; callers must repeat this check before publishing their result.
    """
    if not enabled():
        return True
    with closing(connect()) as db:
        rows = db.execute('''SELECT c.package_name, c.version_code, c.release_sha256
            FROM client_versions c JOIN sessions s ON s.token_hash=c.session_hash
            WHERE c.user_id=? AND s.user_id=c.user_id AND s.expires_at>?''',
            (user_id, int(time.time()))).fetchall()
    for row in rows:
        try:
            current = channel().current(row[0])
            if row[1] == current.version_code and row[2] == current.apk_sha256:
                return True
        except ReleaseUnavailable:
            continue
    return False


def assert_user_can_run(connect: Callable[[], sqlite3.Connection], user_id: int) -> None:
    if not user_can_run(connect, user_id):
        raise HTTPException(426, detail='client_update_required')


def install_routes(app, connect: Callable, authenticate: Callable) -> None:
    @app.get('/client/update-policy', tags=['client updates'])
    def policy(package_name: str = Query(default='ru.omnicio.app.debug')):
        try:
            release = channel().current(package_name)
        except ReleaseUnavailable:
            raise _service_error() from None
        return JSONResponse(release.public(), headers=NO_CACHE)

    @app.post('/client/ready', tags=['client updates'])
    def ready(request: Request, user=Depends(authenticate)):
        enforce(connect, user_id=int(user['id']), authorization=request.headers.get('authorization', ''),
                headers=request.headers)
        return JSONResponse({'ready': True, 'server_enforced': enabled()}, headers=NO_CACHE)

    @app.get('/client/apk/{filename}', tags=['client updates'])
    def apk(filename: str, package_name: str = Query(default='ru.omnicio.app.debug')):
        if not valid_apk_filename(filename):
            raise HTTPException(404, detail='release_not_found')
        try:
            release = channel().published(package_name, filename)
            path = channel().verified_file(release)
        except ReleaseUnavailable:
            raise _service_error() from None
        return FileResponse(path, media_type='application/vnd.android.package-archive', filename=release.filename,
                            headers={'Cache-Control': 'public, max-age=31536000, immutable',
                                     'X-Content-Type-Options': 'nosniff'})
