"""Bound artifact reads/writes even if a source grows after its size was checked."""
from __future__ import annotations

import hashlib
import re
from typing import BinaryIO

MAX_BYTES = 256 * 1024 * 1024


class ArtifactStreamError(ValueError):
    """Do not activate a partially copied or changed artifact."""


def copy_and_hash(source: BinaryIO, expected_size: int, destination: BinaryIO | None = None,
                  expected_sha256: str | None = None) -> str:
    if type(expected_size) is not int or not 0 < expected_size <= MAX_BYTES:
        raise ArtifactStreamError('invalid_artifact_size')
    if expected_sha256 is not None and (
        not isinstance(expected_sha256, str) or re.fullmatch(r'[a-f0-9]{64}', expected_sha256) is None
    ):
        raise ArtifactStreamError('invalid_artifact_digest')
    received = 0
    digest = hashlib.sha256()
    while True:
        chunk = source.read(min(1024 * 1024, expected_size - received + 1))
        if not isinstance(chunk, bytes):
            raise ArtifactStreamError('invalid_artifact_read')
        if not chunk:
            break
        received += len(chunk)
        if received > expected_size:
            raise ArtifactStreamError('artifact_size_changed')
        digest.update(chunk)
        if destination is not None and destination.write(chunk) != len(chunk):
            raise ArtifactStreamError('artifact_short_write')
    if received != expected_size:
        raise ArtifactStreamError('artifact_size_changed')
    actual = digest.hexdigest()
    if expected_sha256 is not None and actual != expected_sha256:
        raise ArtifactStreamError('artifact_checksum_changed')
    return actual
