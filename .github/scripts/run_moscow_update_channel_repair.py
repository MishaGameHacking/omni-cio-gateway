"""Stage and run the audited Moscow update-channel repair.

The checked-in Bash repair is a fail-closed audit template. This launcher makes
only exact, counted substitutions before execution:

* four child-process environment prefixes use ``env`` so Bash does not try to
  reassign readonly variables in the current shell;
* every audited 0.6.0 artifact and policy read-back marker is replaced with the
  exact, immutable, emulator-verified 0.8.0 release identity.

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

# Each tuple is (old marker, new marker, exact expected source occurrences).
# The policy assertions appear twice: once on the server itself and once through
# the public HTTPS hostname. Both must validate the same release identity.
RELEASE_REPLACEMENTS: tuple[tuple[str, str, int], ...] = (
    ('readonly VERSION_CODE="23"', 'readonly VERSION_CODE="32"', 1),
    (
        'readonly VERSION_NAME="0.6.0-preview"',
        'readonly VERSION_NAME="0.8.0-preview"',
        1,
    ),
    (
        'readonly APK_SHA256="31a04b49a03e7ac407092d095a6fbf5a736618850a9ea0765a22ab9e814a4b74"',
        'readonly APK_SHA256="b275ed6d4961bc713ae1b767edb4cfc147982d5476610d1e4dd3419b931cda31"',
        1,
    ),
    ('readonly APK_BYTES="4100464"', 'readonly APK_BYTES="4216696"', 1),
    ('readonly MIN_SDK="33"', 'readonly MIN_SDK="36"', 1),
    ('readonly PUBLISHED_AT="1792031738"', 'readonly PUBLISHED_AT="1792223530"', 1),
    (
        '"notes": "Проверенная версия Analyst AI 0.6.0-preview. Исправлен серверный канал проверки версии.",',
        '"notes": "Проверенная версия Analyst AI 0.8.0-preview. Workspace: новый интерфейс капитала, портфеля, рисков и уведомлений. Настройки оформления и черновик стратегии. Android 16 и новее.",',
        1,
    ),
    ('assert payload["version_code"] == 23', 'assert payload["version_code"] == 32', 2),
    (
        'assert payload["minimum_version_code"] == 23',
        'assert payload["minimum_version_code"] == 32',
        2,
    ),
    (
        'assert payload["version_name"] == "0.6.0-preview"',
        'assert payload["version_name"] == "0.8.0-preview"',
        2,
    ),
    (
        'assert payload["apk_sha256"] == "31a04b49a03e7ac407092d095a6fbf5a736618850a9ea0765a22ab9e814a4b74"',
        'assert payload["apk_sha256"] == "b275ed6d4961bc713ae1b767edb4cfc147982d5476610d1e4dd3419b931cda31"',
        2,
    ),
    ('assert payload["apk_bytes"] == 4100464', 'assert payload["apk_bytes"] == 4216696', 2),
    (
        '# clients. Enforcement can be activated only after the owner verifies 0.6.0.',
        '# clients. Enforcement can be activated only after the owner verifies 0.8.0.',
        1,
    ),
)


def replace_exact_count(source: str, old: str, new: str, expected: int) -> str:
    """Replace an audited marker exactly ``expected`` times and reject drift."""
    count = source.count(old)
    if count != expected:
        raise RuntimeError(f"repair release invariant changed: {old!r}={count}, expected={expected}")
    if new != old and new in source:
        raise RuntimeError(f"new release marker already exists unexpectedly: {new!r}")
    return source.replace(old, new, expected)


def apply_release_identity(source: str) -> str:
    """Apply every exact release identity marker with its audited count."""
    for old, new, expected in RELEASE_REPLACEMENTS:
        source = replace_exact_count(source, old, new, expected)
    return source


def apply_child_environment_prefixes(source: str) -> tuple[str, dict[str, int]]:
    """Replace only the four audited child-process environment prefixes."""
    counts = {prefix: 0 for prefix, _ in PREFIX_REPLACEMENTS}
    output: list[str] = []
    for line in source.splitlines(keepends=True):
        for prefix, replacement in PREFIX_REPLACEMENTS:
            if line.startswith(prefix):
                counts[prefix] += 1
                line = replacement + line[len(prefix):]
                break
        output.append(line)
    return "".join(output), counts


def require_expected_prefix_counts(counts: dict[str, int]) -> None:
    """Reject missing or duplicate audited shell prefixes."""
    unexpected = {prefix: count for prefix, count in counts.items() if count != 1}
    if unexpected:
        raise RuntimeError(
            "repair source invariants changed: "
            + ", ".join(f"{prefix!r}={count}" for prefix, count in unexpected.items())
        )


def validate_child_environment_prefixes(patched: str) -> None:
    """Confirm that no readonly current-shell assignment remains."""
    lines = patched.splitlines()
    for prefix, replacement in PREFIX_REPLACEMENTS:
        if patched.count(replacement) != 1:
            raise RuntimeError(f"staged repair prefix is not unique: {replacement!r}")
        if any(line.startswith(prefix) for line in lines):
            raise RuntimeError(f"readonly assignment remains: {prefix!r}")


def validate_release_identity(patched: str) -> None:
    """Confirm that only the requested 0.8.0 identity is staged."""
    for old, new, expected in RELEASE_REPLACEMENTS:
        if old in patched or patched.count(new) != expected:
            raise RuntimeError(
                f"staged release identity is inconsistent: {new!r}="
                f"{patched.count(new)}, expected={expected}"
            )


def patched_source() -> str:
    """Return a syntax-preserving script for the exact 0.8.0 release."""
    source = apply_release_identity(SOURCE.read_text(encoding="utf-8"))
    patched, counts = apply_child_environment_prefixes(source)
    require_expected_prefix_counts(counts)
    validate_child_environment_prefixes(patched)
    validate_release_identity(patched)
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

