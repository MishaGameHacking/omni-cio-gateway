import json
from pathlib import Path
import shutil
source = Path("deploy/observe_investment_osint.py").read_text()
if "observed = None" not in source or "time.monotonic() + 650" not in source:
    raise RuntimeError("observation_contract_changed")
source = source.replace("observed = None", "observed = sample()").replace("time.monotonic() + 650", "time.monotonic()")
prefix = "import json\nfrom pathlib import Path\nENVELOPE['payload'] = json.loads(Path('/var/lib/analyst-ai-build/development/server-runtime-40704536699/deployment.json').read_text())\n"
destination = Path("deploy/plan-20261027")
(destination / "operation.py").write_text(prefix + "\nimport hashlib\nimport sqlite3\nimport time\nfrom contextlib import closing\nwith closing(sqlite3.connect('/var/lib/analyst-ai/backend.db', timeout=30)) as db:\n    if not db.execute(\"SELECT 1 FROM osint_targets_v1 WHERE source_id='moex_reports' AND kind='index'\").fetchone():\n        raise RuntimeError(\"approved_report_source_missing\")\n    url = \"https://www.moex.com/media/msfo/summary-micex-rts-fs-2q2026-rus.pdf\"\n    identifier = hashlib.sha256((\"moex_reports\" + \"\\0\" + url).encode()).hexdigest()\n    db.execute(\"\"\"INSERT OR IGNORE INTO osint_targets_v1\n        (id,source_id,url,kind,title,context,next_at) VALUES(?, 'moex_reports', ?, 'pdf', ?, ?, 0)\"\"\",\n        (identifier, url, \"Московская Биржа — МСФО за 6 месяцев 2026 года\",\n         \"Официальная страница МСФО MOEX; прямая опубликованная ссылка проверена 28.10.2026.\"))\n    db.execute(\"UPDATE osint_targets_v1 SET next_at=0 WHERE id=? AND last_check IS NULL AND lease_until<=?\",\n               (identifier, int(time.time())))\n    db.commit()\n" + source)
(destination / "payload.json").write_text("{}")
