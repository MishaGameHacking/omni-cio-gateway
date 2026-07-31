from __future__ import annotations

import os
from pathlib import Path


def permissions_are_owner_only(mode: int) -> bool:
    """Validate restrictive POSIX modes without misreading Windows ACL metadata."""

    if os.name == "nt":
        # Windows exposes ACLs rather than meaningful group/other POSIX mode bits.
        return True
    return not bool(mode & 0o077)


def fsync_directory(root: Path) -> None:
    """Flush directory metadata where the host OS exposes directory descriptors."""

    if os.name == "nt":
        # Native Windows rejects opening a directory through os.open. File payloads
        # are still fsynced before the atomic os.replace operation.
        return
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    fd = os.open(root, flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
