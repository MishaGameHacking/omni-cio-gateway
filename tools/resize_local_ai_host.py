"""Budgeted CPU/RAM update of the existing VM, only after its verified backup.

No server creation/deletion, disk enlargement, OS change, credentials in receipts,
broker calls or inference. An ambiguous PATCH is never automatically repeated.
"""
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request

import inspect_infrastructure_budget as inspection

TARGET = {"configurator_id": 153, "cpu": 4, "ram": 8192, "disk": 30720}
PATH = "/api/v1/servers/9417611"
BASE = "68e0fb73feddf178c29d990633edae42aa7adda3"


def need(condition, code):
    if not condition:
        raise RuntimeError(code)


def plan(observation):
    server, project, budget = (observation[key] for key in ("server", "project", "budget"))
    need(server["server_id"] == 9417611 and server["configurator_id"] == 153
         and server["location"] == "nl-1" and server["gpu"] == 0
         and server["disks"] == [{"size_reported": 30720, "type": "nvme"}]
         and type(server["cpu"]) is int and type(server["ram"]) is int
         and (server["cpu"], server["ram"]) in {(2, 4096), (4, 8192)}, "resize_server_changed")
    need(project["complete"] and project["expected_server_present"]
         and project["resource_counts"] == {name: int(name == "servers") for name in inspection.RESOURCE_TYPES},
         "resize_project_changed")
    need(budget["verified"] and budget["currency"] == "RUB", "resize_account_cost_unknown")
    configuration = observation["configurator"]
    need(configuration["complete"] and configuration["current"]["id"] == 153, "resize_configurator_missing")
    prices = configuration["current"]["prices_numeric_shape_unverified"]
    amounts = {key: inspection.number(prices[key].get("number_reported")) for key in ("cpu", "ram", "disk")}
    need(all(value is not None and value > 0 for value in amounts.values()), "resize_prices_invalid")
    requirements = configuration["current"]["requirements"]
    for key in ("cpu", "ram", "disk"):
        lower, upper, step = (requirements[key + suffix] for suffix in ("_min", "_max", "_step"))
        need(all(type(value) is int for value in (lower, upper, step)) and step > 0
             and lower <= TARGET[key] <= upper and (TARGET[key] - lower) % step == 0,
             "resize_target_unavailable")
    service = observation["service_costs"]
    need(service["complete"] and len(service["target_services"]) == 1, "resize_service_cost_missing")
    cost = service["target_services"][0]
    need(cost["configuration"] == {"cpu": server["cpu"], "ram": server["ram"] // 1024, "disk": 30},
         "resize_billing_units_mismatch")
    current_base = sum(amounts[key] * cost["configuration"][key] for key in amounts)
    need(inspection.number(cost["base_cost_reported"]) == current_base, "resize_tariff_period_unverified")
    total = inspection.number(cost["including_addons_reported"])
    need(total is not None and total >= current_base, "resize_addons_unknown")
    target_base = amounts["cpu"] * 4 + amounts["ram"] * 8 + amounts["disk"] * 30
    delta = target_base - current_base
    monthly = max(Decimal(budget["reported_monthly_cost_rub"]), Decimal(budget["reported_monthly_fee_rub"]))
    conservative = max(monthly + delta, Decimal(budget["conservative_31_day_rub"]) + delta * Decimal(31) / Decimal(28))
    reserve = Decimal("1000")
    need(conservative.is_finite() and conservative + reserve <= Decimal("11000"), "resize_budget_exceeded")
    return {"status": "already_sized" if server["ram"] == 8192 else "within_budget",
        "server_id": 9417611, "target": dict(TARGET), "target_base_monthly_estimate_rub": inspection.money(target_base),
        "target_with_unchanged_addons_estimate_rub": inspection.money(target_base + total - current_base),
        "account_conservative_31_day_estimate_rub": inspection.money(conservative),
        "variable_charge_reserve_rub": "1000.00", "infrastructure_cap_rub": "11000.00", "external_ai_cap_rub": "3000.00",
        "price_is_estimate_not_quote": True, "disk_changed": False, "os_changed": False}


def validate_backup(receipt, run_id, now):
    need(receipt.get("status") == "backup_verified" and receipt.get("server_id") == 9417611
         and receipt.get("source_commit") == BASE and receipt.get("run_id") == run_id
         and receipt.get("sqlite_integrity") == "ok" and receipt.get("source_files") == 108
         and receipt.get("services_enabled") is True and receipt.get("application_changed") is False,
         "resize_backup_unverified")
    checked = datetime.fromisoformat(receipt["observed_at"])
    need(checked.tzinfo is not None and 0 <= (now - checked).total_seconds() <= 300, "resize_backup_stale")


def execute(api, backup, run_id, now, apply=False):
    proposal = plan(inspection.inspect(api))
    if not apply or proposal["status"] == "already_sized":
        return {**proposal, "patch_sent": False}
    validate_backup(backup, run_id, now)
    status = api.patch(PATH, {"configurator": dict(TARGET)})
    need(status in (200, 202, 204), "resize_request_not_accepted")
    return {**proposal, "status": "resize_requested", "patch_sent": True,
            "configuration_verified_after_reboot": False}


class ResizeAPI(inspection.ReadOnlyAPI):
    def patch(self, path, body):
        need(path == PATH and body == {"configurator": TARGET}, "resize_patch_scope_invalid")
        request = urllib.request.Request(inspection.BASE + path, method="PATCH", data=json.dumps(body).encode(),
            headers={"Authorization": "Bearer " + self._token, "Accept": "application/json", "Content-Type": "application/json"})
        try:
            with self._opener.open(request, timeout=45) as response:
                return response.status
        except (OSError, urllib.error.URLError):
            raise RuntimeError("resize_outcome_unknown_read_provider_state_before_retry") from None


def main():
    need(sys.argv[1:] in ([], ["--apply"]), "resize_arguments_invalid")
    apply = sys.argv[1:] == ["--apply"]
    backup = None
    if apply:
        raw = Path("plan-reports/receipt.txt").read_text()
        matches = [line.removeprefix("PRE_RESIZE_BACKUP=") for line in raw.splitlines() if line.startswith("PRE_RESIZE_BACKUP=")]
        need(len(matches) == 1, "resize_backup_receipt_missing")
        backup = json.loads(matches[0])
    result = execute(ResizeAPI(os.environ["TIMEWEB_CLOUD_TOKEN"]), backup, os.environ["GITHUB_RUN_ID"],
                     datetime.now(timezone.utc), apply=apply)
    print("LOCAL_AI_RESIZE=" + json.dumps(result), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        allowed = {"resize_budget_exceeded", "resize_target_unavailable", "resize_outcome_unknown_read_provider_state_before_retry",
                   "resize_server_changed", "resize_backup_stale", "resize_backup_unverified", "resize_request_not_accepted"}
        code = str(error) if type(error) is RuntimeError and str(error) in allowed else "resize_validation_failed"
        print(json.dumps({"status": "failed", "code": code, "automatic_retry": False}), flush=True)
        raise SystemExit(1) from None
