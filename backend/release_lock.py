"""Process-owned publication lock, released even when the publisher is killed."""
from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import stat


class PublicationBusy(RuntimeError):
    """Another publisher owns the channel, or a safe lock cannot be obtained."""


@contextmanager
def publication_lock(directory: Path):
    # Keep the inode: unlinking a lock lets two processes lock different files
    # with the same pathname. Existence alone never means a publisher is active.
    path = directory / ".publishing"
    if path.is_symlink():
        raise PublicationBusy("publication_lock_symlink")
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise PublicationBusy("publication_lock_not_regular")
        try:
            if os.name == "nt":
                import msvcrt
                if os.fstat(descriptor).st_size == 0:
                    os.write(descriptor, b"\0")
                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise PublicationBusy("publication_busy_or_lock_unavailable") from error
        yield
    finally:
        # Closing also releases the OS lock after an exception. On abrupt process
        # termination the kernel closes the descriptor; no stale sentinel remains.
        os.close(descriptor)
