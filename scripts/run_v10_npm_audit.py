from __future__ import annotations

import argparse
from collections.abc import Callable, Iterator, Mapping
from contextlib import AbstractContextManager, contextmanager
import errno
import os
import socket
import subprocess
import sys
import time
from typing import TextIO


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
_HOST_SLOT_ADDRESS = "127.0.0.1"
_HOST_SLOT_PORT_ENV = "OMNI_CIO_NPM_AUDIT_SLOT_PORT"
_HOST_SLOT_PORT = 43867
_HOST_SLOT_PORT_MIN = 32000
_HOST_SLOT_PORT_MAX = 49151
_HOST_SLOT_WAIT_SECONDS = 600.0
_HOST_SLOT_POLL_SECONDS = 0.25

Runner = Callable[[list[str]], subprocess.CompletedProcess[str]]
Sleeper = Callable[[float], None]
Monotonic = Callable[[], float]
LockFactory = Callable[[], AbstractContextManager[None]]
SocketFactory = Callable[[], socket.socket]


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


def _resolve_host_slot_port(environ: Mapping[str, str] = os.environ) -> int:
    configured = environ.get(_HOST_SLOT_PORT_ENV, "").strip()
    if not configured:
        return _HOST_SLOT_PORT
    if not configured.isascii() or not configured.isdigit():
        raise AuditTransportLockError(
            f"{_HOST_SLOT_PORT_ENV} must contain only decimal digits; "
            "security gate remains failed closed."
        )

    port = int(configured)
    if not _HOST_SLOT_PORT_MIN <= port <= _HOST_SLOT_PORT_MAX:
        raise AuditTransportLockError(
            f"{_HOST_SLOT_PORT_ENV} must be an integer from {_HOST_SLOT_PORT_MIN} "
            f"through {_HOST_SLOT_PORT_MAX}; security gate remains failed closed."
        )
    return port


def _is_host_slot_contention(exc: OSError) -> bool:
    return exc.errno == errno.EADDRINUSE


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
            "npm audit host transport slot timed out; security gate remains failed closed."
        )
    sleeper(min(poll_seconds, remaining))


def _close_host_slot_socket(slot: socket.socket) -> None:
    try:
        slot.close()
    except OSError as exc:
        raise AuditTransportLockError(
            "npm audit host transport slot release failed; "
            "security gate remains failed closed."
        ) from exc


def _new_host_slot_socket() -> socket.socket:
    try:
        slot = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    except OSError as exc:
        raise AuditTransportLockError(
            "npm audit host transport slot could not create a socket; "
            "security gate remains failed closed."
        ) from exc

    if sys.platform != "win32":
        return slot

    exclusive_option = getattr(socket, "SO_EXCLUSIVEADDRUSE", None)
    if exclusive_option is None:
        _close_host_slot_socket(slot)
        raise AuditTransportLockError(
            "npm audit host transport slot cannot enforce Windows exclusive binding; "
            "security gate remains failed closed."
        )
    try:
        slot.setsockopt(socket.SOL_SOCKET, exclusive_option, 1)
    except OSError as exc:
        _close_host_slot_socket(slot)
        raise AuditTransportLockError(
            "npm audit host transport slot could not enforce Windows exclusive binding; "
            "security gate remains failed closed."
        ) from exc
    return slot


@contextmanager
def _audit_transport_lock(
    *,
    address: str = _HOST_SLOT_ADDRESS,
    port: int | None = None,
    environ: Mapping[str, str] = os.environ,
    wait_seconds: float = _HOST_SLOT_WAIT_SECONDS,
    poll_seconds: float = _HOST_SLOT_POLL_SECONDS,
    sleeper: Sleeper = time.sleep,
    monotonic: Monotonic = time.monotonic,
    socket_factory: SocketFactory = _new_host_slot_socket,
) -> Iterator[None]:
    """Serialize npm audit transport through one loopback slot per physical host."""

    resolved_port = _resolve_host_slot_port(environ) if port is None else port
    waited = False
    deadline = monotonic() + wait_seconds
    slot: socket.socket | None = None

    while True:
        candidate = socket_factory()
        try:
            candidate.bind((address, resolved_port))
        except OSError as exc:
            _close_host_slot_socket(candidate)
            if not _is_host_slot_contention(exc):
                raise AuditTransportLockError(
                    "npm audit host transport slot bind failed; "
                    "security gate remains failed closed."
                ) from exc
            waited = True
            _lock_wait(
                deadline=deadline,
                monotonic=monotonic,
                sleeper=sleeper,
                poll_seconds=poll_seconds,
            )
            continue
        slot = candidate
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
        if slot is None:
            raise AuditTransportLockError(
                "npm audit host transport slot disappeared before release; "
                "security gate remains failed closed."
            )
        _close_host_slot_socket(slot)


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
