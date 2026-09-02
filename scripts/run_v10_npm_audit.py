from __future__ import annotations

import argparse
from collections.abc import Callable, Iterator, Mapping
from contextlib import AbstractContextManager, contextmanager
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import TextIO

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl


_AUDIT_LEVELS = ("info", "low", "moderate", "high", "critical", "none")
_AUDIT_RESULT_MARKERS = (
    "# npm audit report",
    " severity vulnerability",
    " severity vulnerabilities",
)
_TRANSIENT_REGISTRY_MARKERS = (
    "client network socket disconnected before secure tls connection was established",
    "econnreset",
    "etimedout",
    "eai_again",
    "econnrefused",
    "econnaborted",
    "enetunreach",
    "ehostunreach",
    "socket hang up",
    "network timeout",
    "network request to",
    "fetch failed",
    "audit endpoint returned an error",
    "429 too many requests",
    "response 408",
    "response 425",
    "response 429",
    "response 500",
    "response 502",
    "response 503",
    "response 504",
)
_MAX_ATTEMPTS = 5
_MAX_BACKOFF_SECONDS = 60.0
_DEFAULT_ATTEMPTS = 5
_DEFAULT_BACKOFF_SECONDS = 15.0
_HOST_LOCK_FILENAME = "omni-cio-v10-npm-audit.lock"
_HOST_LOCK_ROOT_ENV = "OMNI_CIO_NPM_AUDIT_LOCK_ROOT"
_HOST_LOCK_WAIT_SECONDS = 600.0
_HOST_LOCK_POLL_SECONDS = 0.25

Runner = Callable[[list[str]], subprocess.CompletedProcess[str]]
Sleeper = Callable[[float], None]
Monotonic = Callable[[], float]
LockFactory = Callable[[], AbstractContextManager[None]]


class AuditTransportLockError(RuntimeError):
    """Fail-closed host transport serialization failure."""


def _safe_exit_code(returncode: int) -> int:
    return returncode if 1 <= returncode <= 255 else 1


def _emit(text: str, *, stream: TextIO) -> None:
    if not text:
        return
    stream.write(text)
    if not text.endswith("\n"):
        stream.write("\n")


def is_transient_registry_failure(stdout: str, stderr: str) -> bool:
    combined = f"{stdout}\n{stderr}".lower()
    if any(marker in combined for marker in _AUDIT_RESULT_MARKERS):
        return False
    return any(marker in combined for marker in _TRANSIENT_REGISTRY_MARKERS)


def _host_lock_path(
    environ: Mapping[str, str] = os.environ,
    *,
    platform: str = sys.platform,
) -> Path:
    configured_root = environ.get(_HOST_LOCK_ROOT_ENV, "").strip()
    if configured_root:
        return Path(configured_root) / _HOST_LOCK_FILENAME

    if platform == "win32":
        system_root = (
            environ.get("SystemRoot", "").strip()
            or environ.get("WINDIR", "").strip()
        )
        if not system_root:
            raise AuditTransportLockError(
                "npm audit host transport lock root is unavailable; "
                "security gate remains failed closed."
            )
        return Path(system_root) / "Temp" / _HOST_LOCK_FILENAME

    return Path("/var/tmp") / _HOST_LOCK_FILENAME


def _lock_wait(
    *,
    deadline: float,
    monotonic: Monotonic,
    sleeper: Sleeper,
    poll_seconds: float,
) -> None:
    remaining = deadline - monotonic()
    if remaining <= 0:
        raise AuditTransportLockError(
            "npm audit host transport lock timed out; security gate remains failed closed."
        )
    sleeper(min(poll_seconds, remaining))


@contextmanager
def _audit_transport_lock(
    *,
    wait_seconds: float = _HOST_LOCK_WAIT_SECONDS,
    poll_seconds: float = _HOST_LOCK_POLL_SECONDS,
    sleeper: Sleeper = time.sleep,
    monotonic: Monotonic = time.monotonic,
) -> Iterator[None]:
    """Serialize npm audit transport across runner services on one physical host."""

    lock_path = _host_lock_path()
    try:
        lock_file = lock_path.open("a+b")
    except OSError as exc:
        raise AuditTransportLockError(
            "npm audit host transport lock could not be opened; "
            "security gate remains failed closed."
        ) from exc

    waited = False
    with lock_file:
        deadline = monotonic() + wait_seconds
        if sys.platform == "win32":
            lock_file.seek(0, os.SEEK_END)
            if lock_file.tell() == 0:
                lock_file.write(b"\0")
                lock_file.flush()

            while True:
                lock_file.seek(0)
                try:
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError:
                    waited = True
                    _lock_wait(
                        deadline=deadline,
                        monotonic=monotonic,
                        sleeper=sleeper,
                        poll_seconds=poll_seconds,
                    )
                else:
                    break

            if waited:
                print(
                    "npm audit host transport slot waited for a concurrent audit; "
                    "proceeding serially.",
                    file=sys.stderr,
                )
            try:
                yield
            finally:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            return

        while True:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                waited = True
                _lock_wait(
                    deadline=deadline,
                    monotonic=monotonic,
                    sleeper=sleeper,
                    poll_seconds=poll_seconds,
                )
            except OSError as exc:
                raise AuditTransportLockError(
                    "npm audit host transport lock failed; "
                    "security gate remains failed closed."
                ) from exc
            else:
                break

        if waited:
            print(
                "npm audit host transport slot waited for a concurrent audit; "
                "proceeding serially.",
                file=sys.stderr,
            )
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _default_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        check=False,
        text=True,
    )


def run_audit(
    *,
    npm: str,
    audit_level: str = "high",
    attempts: int = _DEFAULT_ATTEMPTS,
    backoff_seconds: float = _DEFAULT_BACKOFF_SECONDS,
    runner: Runner = _default_runner,
    sleeper: Sleeper = time.sleep,
    lock_factory: LockFactory = _audit_transport_lock,
) -> int:
    if audit_level not in _AUDIT_LEVELS:
        raise ValueError(f"unsupported npm audit level: {audit_level}")
    if not 1 <= attempts <= _MAX_ATTEMPTS:
        raise ValueError(f"attempts must be between 1 and {_MAX_ATTEMPTS}")
    if not 0.0 <= backoff_seconds <= _MAX_BACKOFF_SECONDS:
        raise ValueError(
            f"backoff_seconds must be between 0 and {_MAX_BACKOFF_SECONDS:g}"
        )
    if not npm.strip() or any(character in npm for character in "\r\n"):
        raise ValueError("npm command must be a non-empty single-line value")

    command = [npm, "audit", f"--audit-level={audit_level}"]
    try:
        with lock_factory():
            for attempt in range(1, attempts + 1):
                try:
                    completed = runner(command)
                except OSError as exc:
                    print(f"npm audit launcher failed: {exc}", file=sys.stderr)
                    return 70

                _emit(completed.stdout, stream=sys.stdout)
                _emit(completed.stderr, stream=sys.stderr)

                if completed.returncode == 0:
                    return 0

                if not is_transient_registry_failure(
                    completed.stdout, completed.stderr
                ):
                    print(
                        "npm audit failed with a security finding or non-transient error; "
                        "retry is forbidden.",
                        file=sys.stderr,
                    )
                    return _safe_exit_code(completed.returncode)

                if attempt == attempts:
                    print(
                        f"npm audit registry transport failed after {attempts} attempts; "
                        "security gate remains failed closed.",
                        file=sys.stderr,
                    )
                    return _safe_exit_code(completed.returncode)

                delay = min(
                    backoff_seconds * attempt,
                    _MAX_BACKOFF_SECONDS,
                )
                print(
                    f"npm audit registry transport failed on attempt {attempt}/{attempts}; "
                    f"retrying after {delay:g}s.",
                    file=sys.stderr,
                )
                sleeper(delay)
    except AuditTransportLockError as exc:
        print(str(exc), file=sys.stderr)
        return 75

    return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run mandatory npm audit with host serialization and bounded retries only "
            "for recognized transient registry transport failures."
        )
    )
    parser.add_argument("--npm", default="npm")
    parser.add_argument("--audit-level", choices=_AUDIT_LEVELS, default="high")
    parser.add_argument("--attempts", type=int, default=_DEFAULT_ATTEMPTS)
    parser.add_argument(
        "--backoff-seconds",
        type=float,
        default=_DEFAULT_BACKOFF_SECONDS,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return run_audit(
            npm=args.npm,
            audit_level=args.audit_level,
            attempts=args.attempts,
            backoff_seconds=args.backoff_seconds,
        )
    except ValueError as exc:
        print(f"npm audit policy error: {exc}", file=sys.stderr)
        return 64


if __name__ == "__main__":
    raise SystemExit(main())
