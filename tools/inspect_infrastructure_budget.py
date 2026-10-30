"""Read fixed Timeweb metadata endpoints; never provision, resize or reveal secrets.

Official SDK schemas: Vds, Finances, GetAllProjectResources200Response and
GetServersPresets200Response. Account recurring cost is a conservative envelope,
not a project invoice or a guarantee about future variable charges.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR, localcontext
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request

SERVER_ID = 9417611
PROJECT_ID = 2941515
BASE = "https://api.timeweb.cloud"
PATHS = {
    "server": f"/api/v1/servers/{SERVER_ID}",
    "project": f"/api/v1/projects/{PROJECT_ID}/resources",
    "finances": "/api/v1/account/finances",
    "presets": "/api/v1/presets/servers",
    "service_costs": "/api/v1/account/services/cost",
    "configurators": "/api/v1/configurator/servers",
    "dedicated_presets": "/api/v1/presets/dedicated-servers",
}
INFRA_CAP = Decimal("11000")
AI_CAP = Decimal("3000")
MAX_BYTES = 4 * 1024 * 1024
RESOURCE_TYPES = ("servers", "balancers", "buckets", "clusters", "databases", "dedicated_servers")


class InspectionError(RuntimeError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ReadOnlyAPI:
    def __init__(self, token):
        if not isinstance(token, str) or not token:
            raise InspectionError("credential_unavailable")
        self._token = token
        self._opener = urllib.request.build_opener(NoRedirect())

    def get(self, path):
        if path not in PATHS.values():
            raise InspectionError("endpoint_not_allowlisted")
        request = urllib.request.Request(BASE + path, method="GET", headers={
            "Authorization": "Bearer " + self._token, "Accept": "application/json"})
        try:
            with self._opener.open(request, timeout=20) as response:
                if response.status != 200:
                    raise InspectionError("unexpected_http_status")
                raw = response.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raise InspectionError("response_limit_exceeded")
            document = json.loads(raw, parse_float=Decimal)
        except (urllib.error.URLError, OSError):
            raise InspectionError("metadata_request_failed") from None
        except (ValueError, TypeError, RecursionError):
            raise InspectionError("invalid_json") from None
        if not isinstance(document, dict):
            raise InspectionError("invalid_document")
        return document


def number(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)) or len(str(value)) > 48:
        return None
    try:
        result = Decimal(value)
    except InvalidOperation:
        return None
    if not result.is_finite() or not 0 <= result <= Decimal("1000000000") or result.as_tuple().exponent < -12:
        return None
    return result


def integer(value, minimum=0):
    return value if type(value) is int and minimum <= value <= 1_000_000_000 else None


def label(value):
    # Only provider location/type identifiers, never arbitrary descriptions.
    return value if isinstance(value, str) and re.fullmatch(r"[a-z0-9][a-z0-9_.:-]{0,47}", value) else None


def public_numeric_shape(value, depth=0):
    # The provider's configurator prices are public catalogue metadata. Retain
    # bounded numeric leaves only until units and billing period are verified.
    amount = number(value)
    if amount is not None:
        return {"number_reported": str(amount)}
    if isinstance(value, dict) and depth < 3 and len(value) <= 32:
        return {key: public_numeric_shape(item, depth + 1) for key, item in value.items()
                if isinstance(key, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,47}", key)}
    return {"uninterpreted_type": type(value).__name__}


def money(value, rounding=ROUND_CEILING):
    with localcontext() as context:
        context.prec = 32
        return format(value.quantize(Decimal("0.01"), rounding=rounding), "f")


def costs(document):
    row = document.get("finances")
    if not isinstance(row, dict):
        return {"verified": False, "reason": "finances_missing"}
    names = ("monthly_cost", "monthly_fee", "hourly_cost", "hourly_fee")
    amounts = {name: number(row.get(name)) for name in names}
    if row.get("currency") != "RUB" or any(value is None for value in amounts.values()):
        return {"verified": False, "reason": "currency_or_cost_unknown"}
    with localcontext() as context:
        context.prec = 32
        ceiling = max(amounts["monthly_cost"], amounts["monthly_fee"],
                      amounts["hourly_cost"] * 744, amounts["hourly_fee"] * 744)
        return {"verified": True, "scope": "account_recurring_services",
                "currency": "RUB", "reported_monthly_cost_rub": money(amounts["monthly_cost"]),
                "reported_monthly_fee_rub": money(amounts["monthly_fee"]),
                "conservative_31_day_rub": money(ceiling),
                "infrastructure_cap_rub": money(INFRA_CAP), "ai_cap_rub": money(AI_CAP),
                "total_cap_rub": money(INFRA_CAP + AI_CAP),
                "selected_budget_profile": "hybrid",
                "alternative_local_only": {"infrastructure_cap_rub": "14000.00", "ai_cap_rub": "0.00",
                                           "selected": False},
                "recurring_within_infrastructure_cap": ceiling <= INFRA_CAP,
                "headroom_before_variable_charges_rub": money(max(Decimal(0), INFRA_CAP - ceiling), ROUND_FLOOR),
                "includes_future_variable_charges": False,
                "provisioning_authorized_by_this_report": False}


def server_summary(document):
    row = document.get("server")
    if not isinstance(row, dict) or type(row.get("id")) is not int or row["id"] != SERVER_ID:
        raise InspectionError("unexpected_server_identity")
    result = {"server_id": SERVER_ID}
    for name in ("cpu", "ram", "gpu", "preset_id", "configurator_id"):
        result[name] = integer(row.get(name))
    result["location"] = label(row.get("location"))
    result["is_dedicated_cpu"] = row.get("is_dedicated_cpu") if type(row.get("is_dedicated_cpu")) is bool else None
    disks = row.get("disks")
    result["disks"] = [{"size_reported": integer(disk.get("size")), "type": label(disk.get("type"))}
                       for disk in disks[:8] if isinstance(disk, dict)] if isinstance(disks, list) else None
    result["ram_unit"] = "MiB_as_reported_by_provider"
    result["hardware_complete"] = all(result[name] is not None for name in ("cpu", "ram", "gpu"))
    return result


def service_cost_summary(document):
    rows, meta = document.get("services_costs"), document.get("meta")
    if not isinstance(rows, list) or len(rows) > 10000:
        return {"complete": False, "target_services": []}
    complete = isinstance(meta, dict) and type(meta.get("total")) is int and meta["total"] == len(rows)
    target = []
    for row in rows:
        if not isinstance(row, dict):
            complete = False
            continue
        if row.get("service_id") != SERVER_ID or row.get("project_id") != PROJECT_ID:
            continue
        cost, total = number(row.get("cost")), number(row.get("total_cost"))
        if cost is None or total is None:
            complete = False
        config = row.get("configuration")
        config = config if isinstance(config, dict) else {}
        target.append({"base_cost_reported": money(cost) if cost is not None else None,
                       "including_addons_reported": money(total) if total is not None else None,
                       "configuration": {name: integer(config.get(name)) for name in ("cpu", "ram", "disk")}})
    return {"complete": complete, "target_services": target,
            "service_id": SERVER_ID, "project_id": PROJECT_ID,
            "billing_period_verified": False, "resize_quote": False,
            "future_addons_included": False}


def project_summary(document):
    result = {"project_id": PROJECT_ID, "resource_counts": {}, "complete": True}
    for name in RESOURCE_TYPES:
        values = document.get(name)
        if not isinstance(values, list) or any(not isinstance(value, dict) for value in values):
            result["resource_counts"][name] = None
            result["complete"] = False
        else:
            result["resource_counts"][name] = len(values)
    servers = document.get("servers", [])
    result["expected_server_present"] = isinstance(servers, list) and any(
        isinstance(row, dict) and type(row.get("id")) is int and row["id"] == SERVER_ID for row in servers)
    return result


def preset_summary(document, server=None):
    rows, meta = document.get("server_presets"), document.get("meta")
    if not isinstance(rows, list) or len(rows) > 10000:
        return {"complete": False, "candidates": []}
    complete = isinstance(meta, dict) and type(meta.get("total")) is int and meta["total"] == len(rows)
    candidates = []
    for row in rows:
        if not isinstance(row, dict):
            complete = False
            continue
        values = {name: integer(row.get(name)) for name in ("id", "cpu", "ram", "disk", "gpu")}
        price = number(row.get("price"))
        if any(values[name] is None for name in ("id", "cpu", "ram", "disk")) or price is None or price <= 0:
            continue
        if price > INFRA_CAP or values["ram"] < 8192:
            continue
        location = label(row.get("location"))
        current_location = server.get("location") if isinstance(server, dict) else None
        candidates.append({**values, "catalogue_monthly_price_rub": money(price),
                           "location": location, "disk_type": label(row.get("disk_type")),
                           "same_location": location == current_location if location and current_location else None})
    # Cheapest available catalogue entries at each memory size; no capacity or
    # final purchase/resize price is inferred from an advertised preset.
    chosen, seen = [], set()
    for row in sorted(candidates, key=lambda value: (Decimal(value["catalogue_monthly_price_rub"]), value["id"])):
        group = (row["ram"], bool(row["gpu"]), row["same_location"])
        if group not in seen:
            chosen.append(row)
            seen.add(group)
        if len(chosen) == 16:
            break
    return {"complete": complete, "candidates": chosen, "availability_verified": False,
            "addons_included_verified": False, "in_place_resize_verified": False}


def configurator_summary(document, server):
    collection, meta = document.get("server_configurators"), document.get("meta")
    if isinstance(collection, dict):
        rows = list(collection.values())
    elif isinstance(collection, list):
        rows = collection
    else:
        return {"complete": False, "current": None, "resize_quote": False}
    if len(rows) > 10000:
        return {"complete": False, "current": None, "resize_quote": False}
    complete = isinstance(meta, dict) and type(meta.get("total")) is int and meta["total"] == len(rows)
    matched = [row for row in rows if isinstance(row, dict) and type(row.get("id")) is int
               and row["id"] == server.get("configurator_id")]
    result = {"complete": complete, "current": None, "resize_quote": False,
              "pricing_period_verified": False}
    if len(matched) != 1:
        result["reason"] = "current_configurator_not_unique_or_missing"
        return result
    row = matched[0]
    requirements = row.get("requirements")
    requirements = requirements if isinstance(requirements, dict) else {}
    fields = [name for name in row if isinstance(name, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,47}", name)]
    # Unknown fields are names only. No raw API objects or private strings escape.
    current = {"id": row["id"], "location": label(row.get("location")),
               "disk_type": label(row.get("disk_type")), "schema_fields": sorted(fields)[:100],
               "requirements": {name: integer(requirements.get(name)) for name in (
                   "cpu_min", "cpu_max", "cpu_step", "ram_min", "ram_max", "ram_step",
                   "disk_min", "disk_max", "disk_step", "gpu_min", "gpu_max", "gpu_step")}}
    prices = {}
    for name in ("price", "cpu_price", "ram_price", "disk_price", "gpu_price", "price_cpu", "price_ram", "price_disk"):
        if name in row:
            value = number(row[name])
            prices[name] = money(value) if value is not None else None
    current["numeric_pricing_fields_unverified"] = prices
    current["prices_numeric_shape_unverified"] = public_numeric_shape(row.get("prices"))
    result["current"] = current
    return result


def dedicated_summary(document):
    rows, meta = document.get("dedicated_servers_presets"), document.get("meta")
    if not isinstance(rows, list) or len(rows) > 10000:
        return {"complete": False, "candidates": []}
    complete = isinstance(meta, dict) and type(meta.get("total")) is int and meta["total"] == len(rows)
    candidates = []
    for row in rows:
        if not isinstance(row, dict):
            complete = False
            continue
        price = number(row.get("price"))
        identifier = integer(row.get("id"), 1)
        if price is None or not 0 < price <= 14000 or identifier is None:
            continue
        cpu, memory, disk = (row.get(name) for name in ("cpu", "memory", "disk"))
        cpu = cpu if isinstance(cpu, dict) else {}
        memory = memory if isinstance(memory, dict) else {}
        disk = disk if isinstance(disk, dict) else {}
        short = cpu.get("description_short")
        short = short if isinstance(short, str) and re.fullmatch(r"[A-Za-z0-9 .,/()+-]{1,120}", short) else None
        candidates.append({"id": identifier, "catalogue_price_rub": money(price),
            "location": label(row.get("location")), "cpu_description": short,
            "cpu_count_reported": integer(cpu.get("count")), "memory_size_mb_reported": integer(memory.get("size")),
            "memory_count_reported": integer(memory.get("count")), "disk_count_reported": integer(disk.get("count")),
            "disk_total_size_reported": integer(disk.get("total_size")), "disk_type": label(disk.get("type")),
            "is_pre_installed": row.get("is_pre_installed") if type(row.get("is_pre_installed")) is bool else None,
            "within_hybrid_base_cap": price <= INFRA_CAP})
    return {"complete": complete, "candidates": sorted(candidates, key=lambda item: Decimal(item["catalogue_price_rub"]))[:12],
            "availability_verified": False, "addons_included_verified": False, "gpu_verified": False,
            "billing_period_verified": False}


def inspect(api):
    documents = {name: api.get(path) for name, path in PATHS.items()}
    server = server_summary(documents["server"])
    return {"schema": 2, "observed_at": datetime.now(timezone.utc).isoformat(),
            "server": server, "project": project_summary(documents["project"]),
            "budget": costs(documents["finances"]), "presets": preset_summary(documents["presets"], server),
            "configurator": configurator_summary(documents["configurators"], server),
            "dedicated": dedicated_summary(documents["dedicated_presets"]),
            "service_costs": service_cost_summary(documents["service_costs"]),
            "read_only": True, "resource_changes": False, "model_inference_called": False}


def main():
    try:
        report = inspect(ReadOnlyAPI(os.environ.get("TIMEWEB_CLOUD_TOKEN", "")))
    except InspectionError as error:
        report = {"status": "unavailable", "code": str(error), "resource_changes": False}
    Path("plan-reports").mkdir(exist_ok=True)
    Path("plan-reports/infrastructure-budget.json").write_text(json.dumps(report, indent=2) + "\n")
    print("INFRASTRUCTURE_BUDGET=" + json.dumps(report), flush=True)
    return 0 if report.get("read_only") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
