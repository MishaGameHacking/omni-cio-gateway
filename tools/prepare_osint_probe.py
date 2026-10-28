import json
from pathlib import Path
import shutil
source = Path("deploy/observe_investment_osint.py").read_text()
if "observed = None" not in source or "time.monotonic() + 650" not in source:
    raise RuntimeError("observation_contract_changed")
source = source.replace("observed = None", "observed = sample()").replace("time.monotonic() + 650", "time.monotonic()")
source = "\ndef report_target_status():\n    with closing(sqlite3.connect(DATABASE.as_uri() + \"?mode=ro\", uri=True)) as db:\n        db.row_factory = sqlite3.Row\n        return [dict(row) for row in db.execute(\"SELECT url,kind,status,error,last_check,next_at,coverage_json FROM osint_targets_v1 WHERE url LIKE '%/media/%' OR (kind='pdf' AND last_check IS NOT NULL) ORDER BY last_check DESC LIMIT 24\")]\n" + source
source = source.replace("    print(json.dumps(receipt, ensure_ascii=True), flush=True)", "    receipt[\"report_targets\"] = report_target_status()\n    print(json.dumps(receipt, ensure_ascii=True), flush=True)")
prefix = "import json\nfrom pathlib import Path\nENVELOPE['payload'] = json.loads(Path('/var/lib/analyst-ai-build/development/server-runtime-40704536699/deployment.json').read_text())\n"
destination = Path("deploy/plan-20261027")
(destination / "operation.py").write_text(prefix + source)
(destination / "payload.json").write_text("{}")
