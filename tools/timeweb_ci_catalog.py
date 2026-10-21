"""Read public VM offers through the existing secret, without logging account data."""
from __future__ import annotations

import json
import math
import os
import re

from timeweb_actions_probe import FLOATING_IPS_PATH, ProbeError, read_catalog, read_path


def positive_number(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def candidate_presets(document: dict) -> list[dict]:
    items = document.get("server_presets")
    if type(items) is not list:
        raise ProbeError("invalid_preset_catalog")
    candidates = []
    for item in items:
        if type(item) is not dict:
            raise ProbeError("invalid_preset")
        fields = ("id", "cpu", "ram", "disk", "price")
        if not all(positive_number(item.get(key)) for key in fields):
            raise ProbeError("invalid_preset_numbers")
        if item["cpu"] < 4 or item["ram"] < 8192 or item["disk"] < 81920:
            continue
        # Project names, passwords, IPs and arbitrary response fields never leave here.
        selected = {key: item[key] for key in fields}
        location = item.get("location")
        if isinstance(location, str) and re.fullmatch(r"[a-z]{2}-\d", location, re.ASCII):
            selected["location"] = location
        candidates.append(selected)
    # Include other regions: globally cheapest entries can all be sold out.
    selected = []
    per_location = {}
    for item in sorted(candidates, key=lambda entry: (entry["price"], entry["id"])):
        location = item.get("location", "unspecified")
        if per_location.get(location, 0) < 2:
            selected.append(item)
            per_location[location] = per_location.get(location, 0) + 1
    return selected


def ubuntu_images(document: dict) -> list[dict]:
    items = document.get("servers_os")
    if type(items) is not list:
        raise ProbeError("invalid_os_catalog")
    result = []
    for item in items:
        if type(item) is not dict:
            raise ProbeError("invalid_os")
        if str(item.get("name", "")).lower() != "ubuntu":
            continue
        if item.get("version") not in ("24.04", "26.04"):
            continue
        if type(item.get("id")) is not int or item["id"] <= 0:
            raise ProbeError("invalid_os_id")
        result.append({"id": item["id"], "name": "ubuntu", "version": item["version"]})
    return result


def floating_ip_summary(document: dict) -> dict:
    """Report possible retained charges without exposing addresses or comments."""
    items = document.get("ips")
    meta = document.get("meta")
    if type(items) is not list or type(meta) is not dict or type(meta.get("total")) is not int:
        raise ProbeError("invalid_ip_inventory")
    if meta["total"] != len(items) or any(type(item) is not dict for item in items):
        raise ProbeError("incomplete_ip_inventory")
    return {"count": len(items), "complete": True,
            "unbound_count": sum(item.get("resource_id") is None for item in items),
            "server_ids": sorted({item["resource_id"] for item in items
                                  if type(item.get("resource_id")) is int})}


def main() -> int:
    try:
        token = os.environ.get("TIMEWEB_CLOUD_TOKEN", "")
        report = {
            "resource_changes": False,
            "kvm_verified": False,
            "presets": candidate_presets(read_catalog(token, "presets")),
            "os": ubuntu_images(read_catalog(token, "os")),
            "floating_ips": floating_ip_summary(read_path(token, FLOATING_IPS_PATH)),
        }
        print("TIMEWEB_CI_CATALOG=" + json.dumps(report, sort_keys=True), flush=True)
    except ProbeError as error:
        print("TIMEWEB_CI_ERROR=" + str(error), flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
