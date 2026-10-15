"""Run the read-only Telegram diagnostic with byte-exact LF input over SSH.

Windows text-mode pipes translate newlines to CRLF. The remote Bash script must
be sent as UTF-8 bytes so `set -euo pipefail` is parsed without a trailing CR.
This launcher also appends bounded per-address route/TLS checks so an IPv6-only
routing failure cannot be mistaken for a total Telegram outage.
"""
from __future__ import annotations

import subprocess
import sys

import diagnose_moscow_telegram as diagnostic


_original_run = subprocess.run
_original_remote_script = diagnostic.remote_script

_ROUTE_PROBE = r'''
echo "DIAG_ROUTE_BEGIN"
"$PYTHON_BIN" - <<'ROUTE_PY'
from __future__ import annotations

import socket
import ssl

import certifi

HOSTS = ("oauth.telegram.org", "api.github.com")
context = ssl.create_default_context(cafile=certifi.where())

for host in HOSTS:
    seen: set[tuple[int, str]] = set()
    try:
        resolved = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        print(f"DIAG_ROUTE host={host} resolve=error type={type(exc).__name__} errno={exc.errno}", flush=True)
        continue
    for family, socktype, proto, _canonical, sockaddr in resolved:
        address = sockaddr[0]
        identity = (family, address)
        if identity in seen:
            continue
        seen.add(identity)
        label = "ipv4" if family == socket.AF_INET else "ipv6" if family == socket.AF_INET6 else str(family)
        raw = socket.socket(family, socket.SOCK_STREAM, proto)
        raw.settimeout(8.0)
        try:
            raw.connect(sockaddr)
            with context.wrap_socket(raw, server_hostname=host) as tls:
                print(
                    f"DIAG_ROUTE host={host} family={label} address={address} connect=ok tls=ok protocol={tls.version()}",
                    flush=True,
                )
                raw = None
        except OSError as exc:
            print(
                f"DIAG_ROUTE host={host} family={label} address={address} connect=error type={type(exc).__name__} errno={exc.errno}",
                flush=True,
            )
        finally:
            if raw is not None:
                raw.close()
ROUTE_PY
echo "DIAG_ROUTE_END"
'''


def route_aware_remote_script() -> str:
    source = _original_remote_script()
    marker = 'echo "TELEGRAM_DIAGNOSTIC=complete"'
    if source.count(marker) != 1:
        raise RuntimeError("Telegram diagnostic completion marker changed")
    return source.replace(marker, _ROUTE_PROBE + "\n" + marker)


def binary_safe_run(*args, **kwargs):
    data = kwargs.get("input")
    if isinstance(data, str):
        kwargs["input"] = data.encode("utf-8")
        kwargs.pop("text", None)
        kwargs.pop("encoding", None)
        kwargs.pop("errors", None)
    return _original_run(*args, **kwargs)


def main() -> int:
    diagnostic.remote_script = route_aware_remote_script
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
