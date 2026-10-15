"""Run the audited Bash repair without reassigning readonly shell constants.

Bash applies ``NAME=value command`` assignments in the current shell before it
starts the command. That is rejected when NAME is intentionally readonly, even
when the value is unchanged. The repair needs those names only in child Python
processes, so this launcher performs four exact, fail-closed line-prefix changes
to invoke the external ``env`` command instead. The checked-in repair script and
its hard-coded server/artifact identities remain unchanged and readonly.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / ".github/scripts/repair_moscow_update_channel.sh"

PREFIX_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (
        '    SERVER_ID="$SERVER_ID" SSH_KEY_ID=',
        '    env SERVER_ID="$SERVER_ID" SSH_KEY_ID=',
    ),
    (
        'APK_PATH="$APK_UNIX" REPORT_PATH=',
        'env APK_PATH="$APK_UNIX" REPORT_PATH=',
    ),
    (
        'SSH_PUBLIC_KEY_PATH="$SSH_PUBLIC_KEY_PATH" STATE_PATH=',
        'env SSH_PUBLIC_KEY_PATH="$SSH_PUBLIC_KEY_PATH" STATE_PATH=',
    ),
    (
        'POLICY_PATH="$READBACK_POLICY" PACKAGE_NAME=',
        'env POLICY_PATH="$READBACK_POLICY" PACKAGE_NAME=',
    ),
)


def patched_source() -> str:
    """Return a syntax-preserving repair script with four child-env prefixes."""
    source = SOURCE.read_text(encoding="utf-8")
    counts = {prefix: 0 for prefix, _ in PREFIX_REPLACEMENTS}
    output: list[str] = []

    for line in source.splitlines(keepends=True):
        for prefix, replacement in PREFIX_REPLACEMENTS:
            if line.startswith(prefix):
                counts[prefix] += 1
                line = replacement + line[len(prefix):]
                break
        output.append(line)

    unexpected = {prefix: count for prefix, count in counts.items() if count != 1}
    if unexpected:
        raise RuntimeError(
            "repair source invariants changed: "
            + ", ".join(f"{prefix!r}={count}" for prefix, count in unexpected.items())
        )

    patched = "".join(output)
    for prefix, replacement in PREFIX_REPLACEMENTS:
        if patched.count(replacement) != 1:
            raise RuntimeError(f"staged repair prefix is not unique: {replacement!r}")
        if any(line.startswith(prefix) for line in patched.splitlines()):
            raise RuntimeError(f"readonly assignment remains: {prefix!r}")
    return patched


def bash_executable() -> str:
    configured = os.environ.get("BASH_EXE")
    candidates = (
        configured,
        r"C:\Program Files\Git\bin\bash.exe",
        shutil.which("bash"),
    )
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(candidate)
    raise RuntimeError("Git Bash executable was not found")


def stage_script() -> Path:
    runner_temp = Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir()))
    runner_temp.mkdir(parents=True, exist_ok=True)
    run_id = os.environ.get("GITHUB_RUN_ID", "local")
    if not run_id.replace("-", "").isalnum() or len(run_id) > 80:
        raise RuntimeError("invalid run identifier")
    destination = runner_temp / f"analyst-ai-repair-{run_id}.sh"
    destination.write_text(patched_source(), encoding="utf-8", newline="\n")
    destination.chmod(0o700)
    return destination


def argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="stage and syntax-check the exact repair script without cloud access",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = argument_parser().parse_args(argv)
    destination = stage_script()
    bash = bash_executable()
    try:
        subprocess.run([bash, "-n", str(destination)], check=True)
        if args.check:
            print("READONLY_ENV_REPAIR_CHECK=passed", flush=True)
            return 0
        completed = subprocess.run([bash, str(destination)], check=False)
        return completed.returncode
    finally:
        destination.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
