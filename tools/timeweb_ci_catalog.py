"""Read public VM offers through the existing secret, without logging account data."""
from __future__ import annotations

import json
import math
import os
import re

from timeweb_actions_probe import ProbeError, read_catalog


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
    return sorted(candidates, key=lambda item: (item["price"], item["id"]))[:8]


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


def main() -> int:
    try:
        token = os.environ.get("TIMEWEB_CLOUD_TOKEN", "")
        report = {
            "resource_changes": False,
            "kvm_verified": False,
            "presets": candidate_presets(read_catalog(token, "presets")),
            "os": ubuntu_images(read_catalog(token, "os")),
        }
        print("TIMEWEB_CI_CATALOG=" + json.dumps(report, sort_keys=True), flush=True)
    except ProbeError as error:
        print("TIMEWEB_CI_ERROR=" + str(error), flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
