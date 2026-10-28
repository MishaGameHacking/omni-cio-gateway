"""Identity of the backend sources loaded by this process, independent of APKs.

Only executable Python sources and the dependency declaration are included.
User data, credentials, environment settings and the wall clock never enter the
public identity. A process restart with identical sources keeps the same version.
"""
from __future__ import annotations

import hashlib
from pathlib import Path


def source_revision(root: Path) -> str:
    sources = list(root.glob("*.py"))
    requirements = root / "requirements.txt"
    if requirements.is_file():
        sources.append(requirements)
    digest = hashlib.sha256()
    for source in sorted(sources):
        raw = source.read_bytes()
        digest.update(source.name.encode("utf-8") + b"\0")
        digest.update(len(raw).to_bytes(8, "big"))
        digest.update(raw)
    return digest.hexdigest()


SOURCE_REVISION = source_revision(Path(__file__).parent)


def current() -> dict:
    """Return a fresh metadata object for the running, fully installed sources."""
    return {"schema_version": 1, "source_revision": SOURCE_REVISION,
            "version": "srv-" + SOURCE_REVISION[:12]}
