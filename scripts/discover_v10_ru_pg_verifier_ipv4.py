from __future__ import annotations

import ipaddress
import os
from pathlib import Path
import time
from typing import Any
from urllib.request import OpenerDirector, Request

from scripts import provider_runtime_primitives as _provider_base


TRACE_URL = "https://cloudflare.com/cdn-cgi/trace"
CIDR_ENV = "OMNI_V10_RU_PG_VERIFIER_CIDR"
MAX_RESPONSE_BYTES = 16 * 1024


class EgressStopped(RuntimeError):
    pass


def _fetch_public_ipv4(
    *,
    opener: OpenerDirector | Any | None = None,
) -> str:
    client = opener or _provider_base._NO_REDIRECT_OPENER
    request = Request(
        TRACE_URL,
        headers={
            "Accept": "text/plain",
            "User-Agent": "omni-cio-v10-ru-pg-egress-discovery",
        },
        method="GET",
    )
    try:
        with client.open(request, timeout=15.0) as response:
            status = int(response.status)
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except OSError:
        raise EgressStopped("RU_PG_VERIFIER_EGRESS_DISCOVERY_FAILED") from None
    if status != 200 or len(raw) > MAX_RESPONSE_BYTES:
        raise EgressStopped("RU_PG_VERIFIER_EGRESS_DISCOVERY_FAILED")
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError:
        raise EgressStopped("RU_PG_VERIFIER_EGRESS_RESPONSE_INVALID") from None
    fields: dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        fields[key.strip()] = value.strip()
    value = fields.get("ip", "")
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        raise EgressStopped("RU_PG_VERIFIER_EGRESS_IPV4_INVALID") from None
    if not isinstance(address, ipaddress.IPv4Address) or not address.is_global:
        raise EgressStopped("RU_PG_VERIFIER_EGRESS_IPV4_INVALID")
    return str(address)


def _github_env_path() -> Path:
    raw = os.environ.get("GITHUB_ENV", "").strip()
    if not raw:
        raise EgressStopped("RU_PG_GITHUB_ENV_REQUIRED")
    path = Path(raw)
    if not path.is_absolute():
        raise EgressStopped("RU_PG_GITHUB_ENV_INVALID")
    return path


def discover(*, sleeper=time.sleep) -> str:
    first = _fetch_public_ipv4()
    sleeper(1.0)
    second = _fetch_public_ipv4()
    if first != second:
        raise EgressStopped("RU_PG_VERIFIER_EGRESS_NOT_STABLE")
    cidr = f"{first}/32"

    print(f"::add-mask::{first}")
    print(f"::add-mask::{cidr}")
    with _github_env_path().open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(f"{CIDR_ENV}={cidr}\n")
    print("RU_PG_VERIFIER_EGRESS=READY source=/32")
    return cidr


def main() -> int:
    try:
        discover()
    except EgressStopped as exc:
        print(str(exc))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
