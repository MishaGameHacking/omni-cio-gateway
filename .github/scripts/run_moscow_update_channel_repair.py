"""Stage and run the audited Moscow update-channel repair.

The checked-in Bash repair is a fail-closed audit template. This launcher makes
only exact, counted substitutions before execution:

* four child-process environment prefixes use ``env`` so Bash does not try to
  reassign readonly variables in the current shell;
* the previously audited 0.6.0 artifact identity is replaced with the exact,
  immutable, emulator-verified 0.7.1 release identity.

Any missing, duplicated, or changed source marker aborts before cloud access.
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

RELEASE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ('readonly VERSION_CODE="23"', 'readonly VERSION_CODE="26"'),
    (
        'readonly VERSION_NAME="0.6.0-preview"',
        'readonly VERSION_NAME="0.7.1-preview"',
    ),
    (
        'readonly APK_SHA256="31a04b49a03e7ac407092d095a6fbf5a736618850a9ea0765a22ab9e814a4b74"',
        'readonly APK_SHA256="343f46a392f93c5d6014f639d2e1e07ce31c7ffbf3fdd28e85cdeb8659c155a7"',
    ),
    ('readonly APK_BYTES="4100464"', 'readonly APK_BYTES="4151124"'),
    ('readonly PUBLISHED_AT="1792031738"', 'readonly PUBLISHED_AT="1792095055"'),
    (
        '"notes": "Проверенная версия Analyst AI 0.6.0-preview. Исправлен серверный канал проверки версии.",',
        '"notes": "Проверенная версия Analyst AI 0.7.1-preview. Закрытый доступ до пяти аккаунтов и новый интерфейс Spectrum.",',
    ),
)


def replace_exact_once(source: str, old: str, new: str) -> str:
    """Replace one audited marker and reject drift or duplicate identities."""
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"repair release invariant changed: {old!r}={count}")
    if new != old and new in source:
        raise RuntimeError(f"new release marker already exists unexpectedly: {new!r}")
    return source.replace(old, new, 1)


def patched_source() -> str:
    """Return a syntax-preserving script for the exact 0.7.1 release."""
    source = SOURCE.read_text(encoding="utf-8")
    for old, new in RELEASE_REPLACEMENTS:
        source = replace_exact_once(source, old, new)

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
    for old, new in RELEASE_REPLACEMENTS:
        if old in patched or patched.count(new) != 1:
            raise RuntimeError(f"staged release identity is inconsistent: {new!r}")
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
