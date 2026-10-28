"""Prepare a read-only observation using the preceding deployment receipt."""
import json
from pathlib import Path
import shutil

reports = Path("plan-reports")
receipt = json.loads((reports / "receipt.txt").read_text())
if receipt["status"] != "deployed" or receipt["server_id"] != 9417611:
    raise RuntimeError("deployment_receipt_required")
(reports / "deployment.json").write_text(json.dumps(receipt, indent=2))
shutil.copyfile(reports / "transport.json", reports / "deployment-transport.json")
destination = Path("deploy/plan-20261027")
shutil.copyfile("deploy/observe_investment_osint.py", destination / "operation.py")
(destination / "payload.json").write_text(json.dumps({
    "source_commit": receipt["source_commit"], "apk_policy_sha256": receipt["apk_policy_sha256"]}))
