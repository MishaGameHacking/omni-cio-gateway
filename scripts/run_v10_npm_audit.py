from __future__ import annotations

import argparse
from collections.abc import Callable
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

Runner = Callable[[list[str]], subprocess.CompletedProcess[str]]
Sleeper = Callable[[float], None]


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
    attempts: int = 3,
    backoff_seconds: float = 5.0,
    runner: Runner = _default_runner,
    sleeper: Sleeper = time.sleep,
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

        if not is_transient_registry_failure(completed.stdout, completed.stderr):
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

        delay = backoff_seconds * attempt
        print(
            f"npm audit registry transport failed on attempt {attempt}/{attempts}; "
            f"retrying after {delay:g}s.",
            file=sys.stderr,
        )
        sleeper(delay)

    return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run mandatory npm audit with bounded retries only for recognized transient "
            "registry transport failures."
        )
    )
    parser.add_argument("--npm", default="npm")
    parser.add_argument("--audit-level", choices=_AUDIT_LEVELS, default="high")
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--backoff-seconds", type=float, default=5.0)
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
