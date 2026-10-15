"""Materialize the Moscow deployment script for byte-exact Linux execution.

Git for Windows may materialize checked-in shell files with CRLF even when the
repository blob uses LF. Copying such a file to Linux makes Bash parse options
like ``pipefail\r``. The first real deployment also exposed an audited shell
compatibility defect: inline environment bindings reused names already declared
``readonly`` by the script. This preflight applies only those exact reviewed
transformations and fails closed if the source shape is unexpected.
"""
from __future__ import annotations

from pathlib import Path
import sys


SCRIPT = Path(__file__).resolve().with_name("deploy_moscow_telegram_browser_auth_remote.sh")
EXPECTED_SHEBANG = b"#!/usr/bin/env bash\n"
REPLACEMENTS = (
    (b'UNIT_FILE="$UNIT_FILE"', b'UNIT_FILE_PATH="$UNIT_FILE"'),
    (b'OLD_EXEC="$OLD_EXEC"', b'OLD_EXEC_VALUE="$OLD_EXEC"'),
    (b'NEW_EXEC="$NEW_EXEC"', b'NEW_EXEC_VALUE="$NEW_EXEC"'),
    (b'os.environ["UNIT_FILE"]', b'os.environ["UNIT_FILE_PATH"]'),
    (b'os.environ["OLD_EXEC"]', b'os.environ["OLD_EXEC_VALUE"]'),
    (b'os.environ["NEW_EXEC"]', b'os.environ["NEW_EXEC_VALUE"]'),
)


def _replace_once_or_accept_materialized(source: bytes, old: bytes, new: bytes) -> bytes:
    old_count = source.count(old)
    new_count = source.count(new)
    if old_count == 1 and new_count == 0:
        return source.replace(old, new, 1)
    if old_count == 0 and new_count == 1:
        return source
    raise RuntimeError("Remote deployment script has an unexpected environment binding")


def normalize_bytes(source: bytes) -> bytes:
    normalized = source.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    if not normalized.startswith(EXPECTED_SHEBANG):
        raise RuntimeError("Remote deployment script has an unexpected shebang")
    if b"\r" in normalized:
        raise RuntimeError("Remote deployment script still contains carriage returns")
    if b"set -euo pipefail\n" not in normalized:
        raise RuntimeError("Remote deployment script lost its fail-closed shell options")
    for old, new in REPLACEMENTS:
        normalized = _replace_once_or_accept_materialized(normalized, old, new)
    return normalized


def main() -> int:
    if not SCRIPT.is_file() or SCRIPT.is_symlink():
        raise RuntimeError("Remote deployment script is missing or linked")
    normalized = normalize_bytes(SCRIPT.read_bytes())
    SCRIPT.write_bytes(normalized)
    if SCRIPT.read_bytes() != normalized:
        raise RuntimeError("Remote deployment script was not written byte-exactly")
    print("TELEGRAM_AUTH_DEPLOYMENT_SCRIPT=materialized", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(
            f"TELEGRAM_AUTH_DEPLOYMENT_SCRIPT=failed type={type(error).__name__}",
            file=sys.stderr,
            flush=True,
        )
        raise
