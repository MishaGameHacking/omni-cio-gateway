"""Parse Timeweb network inventory consistently across deployment consumers."""

from __future__ import annotations

import ipaddress
from collections.abc import Iterator
from typing import Any


def network_addresses(
    resource: dict[str, Any], *, public_only: bool = False,
) -> Iterator[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    for network in resource.get("networks") or []:
        network_type = str(network.get("type") or "").lower()
        if public_only and network_type in {"local", "private"}:
            continue
        for item in network.get("ips") or []:
            try:
                address = ipaddress.ip_address(str(item.get("ip") or "").strip())
            except ValueError:
                continue
            yield address
