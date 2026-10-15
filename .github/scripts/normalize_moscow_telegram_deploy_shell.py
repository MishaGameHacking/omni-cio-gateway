"""Normalize the remote Moscow deployment script to byte-exact LF endings.

Git for Windows may materialize checked-in shell files with CRLF even when the
repository blob uses LF. Copying such a file to Linux makes Bash parse options
like ``pipefail\r``. This preflight rewrites only the audited remote deployment
script and fails closed if its shebang or byte structure is unexpected.
"""
from __future__ import annotations

from pathlib import Path
import sys


SCRIPT = Path(__file__).resolve().with_name("deploy_moscow_telegram_browser_auth_remote.sh")
EXPECTED_SHEBANG = b"#!/usr/bin/env bash\n"


def normalize_bytes(source: bytes) -> bytes:
    normalized = source.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    if not normalized.startswith(EXPECTED_SHEBANG):
        raise RuntimeError("Remote deployment script has an unexpected shebang")
    if b"\r" in normalized:
        raise RuntimeError("Remote deployment script still contains carriage returns")
    if b"set -euo pipefail\n" not in normalized:
        raise RuntimeError("Remote deployment script lost its fail-closed shell options")
    return normalized


def main() -> int:
    if not SCRIPT.is_file() or SCRIPT.is_symlink():
        raise RuntimeError("Remote deployment script is missing or linked")
    normalized = normalize_bytes(SCRIPT.read_bytes())
    SCRIPT.write_bytes(normalized)
    if SCRIPT.read_bytes() != normalized:
        raise RuntimeError("Remote deployment script was not written byte-exactly")
    print("TELEGRAM_AUTH_DEPLOYMENT_LINE_ENDINGS=lf", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(
            f"TELEGRAM_AUTH_DEPLOYMENT_LINE_ENDINGS=failed type={type(error).__name__}",
            file=sys.stderr,
            flush=True,
        )
        raise
