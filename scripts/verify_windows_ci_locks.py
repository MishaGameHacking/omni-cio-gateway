from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
import time
from typing import TextIO


ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_ATTEMPTS = 3
_DEFAULT_BACKOFF_SECONDS = 5.0
_COMPILE_TIMEOUT_SECONDS = 180.0
_VERIFY_TIMEOUT_SECONDS = 30.0
_MAX_ATTEMPTS = 3
_MAX_BACKOFF_SECONDS = 30.0

_TRANSIENT_TRANSPORT_MARKERS = (
    "access violation writing",
    "connection aborted",
    "connection broken",
    "connection refused",
    "connection reset",
    "eai_again",
    "econnreset",
    "etimedout",
    "getaddrinfo failed",
    "max retries exceeded",
    "network is unreachable",
    "read timed out",
    "remote end closed connection",
    "temporary failure in name resolution",
    "too many requests",
    "response 429",
    "response 502",
    "response 503",
    "response 504",
)


@dataclass(frozen=True)
class LockPlan:
    source: str
    constraint: str
    compiled: str


_LOCK_PLANS = (
    LockPlan(
        "requirements.in",
        "requirements.txt",
        "windows-compiled-requirements.txt",
    ),
    LockPlan(
        "requirements-dev.in",
        "requirements-dev.txt",
        "windows-compiled-requirements-dev.txt",
    ),
)

Runner = Callable[
    [list[str], Path, float],
    subprocess.CompletedProcess[str],
]
Sleeper = Callable[[float], None]


def _default_runner(
    command: list[str],
    cwd: Path,
    timeout_seconds: float,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        check=False,
        text=True,
        timeout=timeout_seconds,
    )


def _emit(text: str, *, stream: TextIO) -> None:
    if not text:
        return
    stream.write(text)
    if not text.endswith("\n"):
        stream.write("\n")


def _timeout_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def is_transient_transport_failure(stdout: str, stderr: str) -> bool:
    combined = f"{stdout}\n{stderr}".lower()
    return any(marker in combined for marker in _TRANSIENT_TRANSPORT_MARKERS)


def _safe_exit_code(returncode: int) -> int:
    return returncode if 1 <= returncode <= 255 else 1


def _compile_command(plan: LockPlan) -> list[str]:
    return [
        sys.executable,
        "-m",
        "piptools",
        "compile",
        "--allow-unsafe",
        "--generate-hashes",
        "--resolver=backtracking",
        "--strip-extras",
        "--quiet",
        f"--constraint={plan.constraint}",
        f"--output-file={plan.compiled}",
        plan.source,
    ]


def _verify_command(plan: LockPlan) -> list[str]:
    return [
        sys.executable,
        "scripts/windows_ci_lock.py",
        "verify",
        plan.constraint,
        plan.compiled,
    ]


def _remove_partial_output(root: Path, plan: LockPlan) -> bool:
    path = root / plan.compiled
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        print(
            "Windows lock verification could not remove partial output "
            f"{plan.compiled}: {exc}",
            file=sys.stderr,
        )
        return False
    return True


def _run_compile_plan(
    plan: LockPlan,
    *,
    root: Path,
    attempts: int,
    backoff_seconds: float,
    compile_timeout_seconds: float,
    runner: Runner,
    sleeper: Sleeper,
) -> int:
    command = _compile_command(plan)
    for attempt in range(1, attempts + 1):
        if not _remove_partial_output(root, plan):
            return 74
        try:
            completed = runner(command, root, compile_timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            stdout = _timeout_text(exc.stdout)
            stderr = _timeout_text(exc.stderr)
            _emit(stdout, stream=sys.stdout)
            _emit(stderr, stream=sys.stderr)
            if attempt == attempts:
                print(
                    f"pip-compile timed out after {compile_timeout_seconds:g}s on "
                    f"attempt {attempt}/{attempts} for {plan.source}; lock gate "
                    "remains failed closed.",
                    file=sys.stderr,
                )
                return 75
            delay = min(backoff_seconds * attempt, _MAX_BACKOFF_SECONDS)
            print(
                f"pip-compile timed out after {compile_timeout_seconds:g}s on attempt "
                f"{attempt}/{attempts} for {plan.source}; retrying after {delay:g}s.",
                file=sys.stderr,
            )
            sleeper(delay)
            continue
        except OSError as exc:
            print(f"pip-compile launcher failed: {exc}", file=sys.stderr)
            return 70

        _emit(completed.stdout, stream=sys.stdout)
        _emit(completed.stderr, stream=sys.stderr)
        if completed.returncode == 0:
            return 0

        if not is_transient_transport_failure(completed.stdout, completed.stderr):
            print(
                f"pip-compile failed for {plan.source} with a non-transient resolver "
                "or content error; retry is forbidden.",
                file=sys.stderr,
            )
            return _safe_exit_code(completed.returncode)

        if attempt == attempts:
            print(
                f"pip-compile transient transport failure persisted for {plan.source} "
                f"after {attempts} attempts; lock gate remains failed closed.",
                file=sys.stderr,
            )
            return _safe_exit_code(completed.returncode)

        delay = min(backoff_seconds * attempt, _MAX_BACKOFF_SECONDS)
        print(
            f"pip-compile transient transport failure on attempt {attempt}/{attempts} "
            f"for {plan.source}; retrying after {delay:g}s.",
            file=sys.stderr,
        )
        sleeper(delay)
    return 1


def verify_windows_ci_locks(
    *,
    root: Path = ROOT,
    attempts: int = _DEFAULT_ATTEMPTS,
    backoff_seconds: float = _DEFAULT_BACKOFF_SECONDS,
    compile_timeout_seconds: float = _COMPILE_TIMEOUT_SECONDS,
    verify_timeout_seconds: float = _VERIFY_TIMEOUT_SECONDS,
    runner: Runner = _default_runner,
    sleeper: Sleeper = time.sleep,
) -> int:
    if not 1 <= attempts <= _MAX_ATTEMPTS:
        raise ValueError(f"attempts must be between 1 and {_MAX_ATTEMPTS}")
    if not 0.0 <= backoff_seconds <= _MAX_BACKOFF_SECONDS:
        raise ValueError(
            f"backoff_seconds must be between 0 and {_MAX_BACKOFF_SECONDS:g}"
        )
    if compile_timeout_seconds <= 0 or verify_timeout_seconds <= 0:
        raise ValueError("subprocess timeouts must be positive")

    for plan in _LOCK_PLANS:
        status = _run_compile_plan(
            plan,
            root=root,
            attempts=attempts,
            backoff_seconds=backoff_seconds,
            compile_timeout_seconds=compile_timeout_seconds,
            runner=runner,
            sleeper=sleeper,
        )
        if status != 0:
            return status

        try:
            verified = runner(_verify_command(plan), root, verify_timeout_seconds)
        except subprocess.TimeoutExpired:
            print(
                "Windows lock projection verification timed out for "
                f"{plan.constraint}; lock gate remains failed closed.",
                file=sys.stderr,
            )
            return 75
        except OSError as exc:
            print(f"Windows lock verifier launcher failed: {exc}", file=sys.stderr)
            return 70

        _emit(verified.stdout, stream=sys.stdout)
        _emit(verified.stderr, stream=sys.stderr)
        if verified.returncode != 0:
            print(
                f"Windows lock projection verification failed for {plan.constraint}; "
                "retry is forbidden.",
                file=sys.stderr,
            )
            return _safe_exit_code(verified.returncode)

    print("Bounded Windows lock verification passed.")
    return 0


def main() -> int:
    try:
        return verify_windows_ci_locks()
    except ValueError as exc:
        print(f"Windows lock verification policy error: {exc}", file=sys.stderr)
        return 64


if __name__ == "__main__":
    raise SystemExit(main())
