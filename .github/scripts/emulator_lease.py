"""One disposable Android emulator at a time per runner service account/host.

Four runners on one laptop are not four independent machines. Keep CPU/memory
contention and the find-free-port/start race out of device tests. No ADB server,
attached phone, other emulator or stale lock file is killed/deleted here.
"""
from __future__ import annotations

from contextlib import contextmanager
import errno
import math
import os
from pathlib import Path
import stat
import tempfile
import time


class EmulatorLeaseTimeout(TimeoutError):
    pass


def _reject_link(path: Path) -> None:
    metadata = path.lstat()
    if stat.S_ISLNK(metadata.st_mode) or getattr(metadata, 'st_file_attributes', 0) & 0x400:
        raise ValueError('Emulator lease path must not be a link/reparse point')


def _open_lease(path: Path) -> int:
    if path.exists() or path.is_symlink():
        _reject_link(path)
    fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise ValueError('Emulator lease must be one regular file')
        if metadata.st_size == 0:
            os.write(fd, b'0')
            os.fsync(fd)
        return fd
    except BaseException:
        os.close(fd)
        raise


def _try_lock(fd: int) -> bool:
    try:
        if os.name == 'nt':
            import msvcrt
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError as error:
        if error.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
            return False
        raise


def _unlock(fd: int) -> None:
    if os.name == 'nt':
        import msvcrt
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(fd, fcntl.LOCK_UN)


@contextmanager
def _lease_at_path(path: Path, wait_seconds: float):
    if isinstance(wait_seconds, bool) or not isinstance(wait_seconds, (int, float)):
        raise ValueError('Invalid emulator wait')
    if not math.isfinite(wait_seconds) or not 0 <= wait_seconds <= 1200:
        raise ValueError('Invalid emulator wait')
    fd = _open_lease(path)
    owned = False
    deadline = time.monotonic() + wait_seconds
    try:
        while not owned:
            owned = _try_lock(fd)
            if owned:
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise EmulatorLeaseTimeout('Another CI job still owns the host emulator lease')
            time.sleep(min(0.5, remaining))
        yield
    finally:
        try:
            if owned:
                _unlock(fd)
        finally:
            os.close(fd)
        # The inode/path is deliberately retained: unlinking would split the lock.


@contextmanager
def exclusive_emulator():
    # RUNNER_TEMP and workspaces differ across runner services on the same host.
    # tempfile.gettempdir() is shared by the service account, not by a job.
    directory = Path(tempfile.gettempdir()).resolve() / 'analyst-ai-emulator-lease'
    directory.mkdir(mode=0o700, exist_ok=True)
    _reject_link(directory)
    if not directory.is_dir():
        raise ValueError('Invalid emulator lease directory')
    print('EMULATOR_HOST_LEASE=waiting', flush=True)
    with _lease_at_path(directory / 'android.lock', 1200):
        print('EMULATOR_HOST_LEASE=acquired', flush=True)
        yield
    print('EMULATOR_HOST_LEASE=released', flush=True)


def verify_emulator_identity(device, name: str, api: int) -> None:
    identity = device('emu', 'avd', 'name', timeout=10)
    version = device('shell', 'getprop', 'ro.build.version.sdk', timeout=10)
    if identity.returncode or name not in identity.stdout.splitlines():
        raise RuntimeError('Emulator identity mismatch; no package operations permitted')
    if version.returncode or version.stdout.strip() != str(api):
        raise RuntimeError('Emulator Android version mismatch; no package operations permitted')


def collect_runtime_failure(device) -> None:
    """Keep OS exit reasons even when SIGKILL leaves the crash buffer empty."""
    commands = (('logcat', '-d', '-b', 'crash', '-t', '100'),
                ('shell', 'dumpsys', 'activity', 'exit-info', 'ru.omnicio.app.debug'),
                ('logcat', '-d', '-b', 'events', '-v', 'threadtime',
                 'am_kill:I', 'am_proc_died:I', 'am_crash:I', 'am_anr:I', '*:S'),
                ('shell', 'dumpsys', 'meminfo'),
                ('shell', 'dumpsys', 'activity', 'top'))
    for command in commands:
        try:
            response = device(*command, timeout=10)
            print('EMULATOR_RUNTIME_FAILURE=' + ' '.join(command) + '\n' + response.stdout[-16000:], flush=True)
        except Exception as error:
            print('EMULATOR_RUNTIME_DIAGNOSTIC_UNAVAILABLE=' + type(error).__name__, flush=True)
