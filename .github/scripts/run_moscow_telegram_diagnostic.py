"""Run the read-only Telegram diagnostic with byte-exact LF input over SSH.

Windows text-mode pipes translate newlines to CRLF. The remote Bash script must
be sent as UTF-8 bytes so `set -euo pipefail` is parsed without a trailing CR.
"""
from __future__ import annotations

import subprocess
import sys

import diagnose_moscow_telegram as diagnostic


_original_run = subprocess.run


def binary_safe_run(*args, **kwargs):
    data = kwargs.get("input")
    if isinstance(data, str):
        kwargs["input"] = data.encode("utf-8")
        kwargs.pop("text", None)
        kwargs.pop("encoding", None)
        kwargs.pop("errors", None)
    return _original_run(*args, **kwargs)


def main() -> int:
    diagnostic.subprocess.run = binary_safe_run
    return diagnostic.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(
            f"TELEGRAM_DIAGNOSTIC=failed type={type(error).__name__}",
            file=sys.stderr,
            flush=True,
        )
        raise
