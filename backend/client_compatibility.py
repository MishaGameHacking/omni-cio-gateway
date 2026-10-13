"""Check active client observations without rehashing one APK per old session.

A release reader must verify the current artifact before returning its identity.
Only this invocation shares that read: the next permission check reads it again.
Session ownership/expiry is checked again AFTER the artifact read, so a revoked
or expired session cannot be revived by a previously loaded observation.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
import re
import sqlite3

Identity = tuple[int, str]


def _active(db: sqlite3.Connection, user_id: int, package: str, at: float,
            identity: Identity | None = None) -> bool:
    query = '''SELECT 1 FROM client_versions c JOIN sessions s
        ON s.token_hash=c.session_hash AND s.user_id=c.user_id
        WHERE c.user_id=? AND c.package_name=? AND s.expires_at>?'''
    parameters = (user_id, package, at)
    if identity is not None:
        query += ' AND c.version_code=? AND c.release_sha256=?'
        parameters += identity
    return db.execute(query + ' LIMIT 1', parameters).fetchone() is not None


def has_current_session(db: sqlite3.Connection, user_id: int, *,
                        packages: Iterable[str],
                        verified_release: Callable[[str], Identity | None],
                        clock: Callable[[], float]) -> bool:
    """At most one verified artifact read for each supported package per check.

    No cross-request memoization or path/stat based digest cache is used. None
    from the reader means that channel is unavailable, not that it is current.
    """
    if type(user_id) is not int or user_id <= 0:
        raise ValueError('invalid_user_id')
    for package in sorted(set(packages)):
        if not _active(db, user_id, package, clock()):
            continue
        identity = verified_release(package)
        if identity is None:
            continue
        version, digest = identity
        if type(version) is not int or version <= 0 or not isinstance(digest, str) or re.fullmatch(r'[0-9a-f]{64}', digest) is None:
            raise ValueError('invalid_verified_release_identity')
        if _active(db, user_id, package, clock(), identity):
            return True
    return False
