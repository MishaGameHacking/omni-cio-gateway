from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


_EXIT_TIMEOUT = 124
_KILL_TIMEOUT_SECONDS = 10


def _kill_process_tree(process_id: int) -> None:
    try:
        subprocess.run(
            ["taskkill.exe", "/PID", str(process_id), "/T", "/F"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=_KILL_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        # The outer timeout remains authoritative. GitHub runner cleanup is the
        # final containment layer if Windows refuses a bounded taskkill request.
        return


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bound the complete WP22A Phase 2 PowerShell rehearsal process tree."
    )
    parser.add_argument("--powershell", default="powershell.exe")
    parser.add_argument("--script", required=True)
    parser.add_argument("--python-path", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=240)
    args = parser.parse_args()

    if not 60 <= args.timeout_seconds <= 600:
        raise SystemExit("WP22A_PHASE2_OUTER_TIMEOUT_RANGE_INVALID")

    script_path = Path(args.script).resolve()
    python_path = Path(args.python_path).resolve()
    if not script_path.is_file():
        raise SystemExit("WP22A_PHASE2_OUTER_SCRIPT_NOT_FOUND")
    if not python_path.is_file():
        raise SystemExit("WP22A_PHASE2_OUTER_PYTHON_NOT_FOUND")

    command = [
        args.powershell,
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        "-PythonPath",
        str(python_path),
    ]
    print("WP22A_PHASE2_OUTER_STAGE=rehearsal_start", flush=True)
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
        )
    except OSError:
        print("WP22A_PHASE2_OUTER_START_FAILED", file=sys.stderr, flush=True)
        return 125

    try:
        try:
            return_code = process.wait(timeout=args.timeout_seconds)
        except subprocess.TimeoutExpired:
            print("WP22A_PHASE2_OUTER_WATCHDOG_TIMEOUT", file=sys.stderr, flush=True)
            _kill_process_tree(process.pid)
            try:
                process.wait(timeout=_KILL_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                pass
            return _EXIT_TIMEOUT
        if return_code != 0:
            print(
                f"WP22A_PHASE2_OUTER_CHILD_EXIT={return_code}",
                file=sys.stderr,
                flush=True,
            )
        return return_code
    finally:
        if process.poll() is None:
            _kill_process_tree(process.pid)


if __name__ == "__main__":
    raise SystemExit(main())
