"""Read only: model catalogue and non-secret runtime capability flags."""
import json
from pathlib import Path
operation = r'''
import json
from pathlib import Path
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
env = {}
for line in Path("/etc/analyst-ai/backend.env").read_text().splitlines():
    name, separator, value = line.partition("=")
    if separator and not name.startswith("#"):
        env[name] = value.strip().strip('"').strip("'")
allowed = ["AI_TRANSPORT", "AI_EXTERNAL_PROCESSING_APPROVED", "AI_ALLOWED_PROCESSING_REGIONS",
    "AI_USER_DAILY_RUB", "AI_PROJECT_DAILY_RUB", "AI_USER_MONTHLY_RUB", "AI_PROJECT_MONTHLY_RUB",
    "ANALYSIS_SCHEDULER_ENABLED"]
for tier in ("FAST", "STANDARD", "PREMIUM"):
    allowed.extend(["AI_MODEL_" + tier])
    allowed.extend("AI_" + tier + "_" + suffix for suffix in ("PROCESSING_REGION", "INPUT_RUB_PER_MILLION", "OUTPUT_RUB_PER_MILLION", "PRICING_VALID_UNTIL", "TOKEN_PARAMETER"))
report = {"at":datetime.now(timezone.utc).isoformat(), "configuration": {key:env[key] for key in allowed if key in env},
    "gateway_key_present": bool(env.get("TIMEWEB_AI_TOKEN")), "catalog_present": bool(env.get("AI_ROUTE_CATALOG_JSON"))}
for tier in ("FAST", "STANDARD", "PREMIUM"):
    report[tier.lower() + "_agent_key_present"] = bool(env.get("TIMEWEB_AI_" + tier + "_TOKEN"))
database = Path(env.get("DATABASE_PATH", "/var/lib/analyst-ai/backend.sqlite3"))
with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as db:
    db.row_factory = sqlite3.Row
    report["broker_connections"] = db.execute("SELECT COUNT(*) FROM users WHERE tinvest_token_encrypted IS NOT NULL").fetchone()[0]
    row = db.execute("SELECT config_json FROM workspace_strategy_versions ORDER BY confirmed_at DESC LIMIT 1").fetchone()
    if row:
        config = json.loads(row[0])
        mandate = config.get("mandate") or {}
        report["strategy"] = {key:config.get(key) for key in ("goal", "horizon_months", "risk_level", "limits", "reserve")}
        report["mandate"] = {key:mandate.get(key) for key in ("asset_mode", "loss_capacity_percent", "bond_target_percent", "share_target_percent")}
        report["mandate"]["account_selected"] = bool(mandate.get("account_id"))
print("WORKSPACE_INVENTORY=" + json.dumps(report, ensure_ascii=True), flush=True)
'''
destination=Path("deploy/plan-20261027")
(destination/"operation.py").write_text(operation)
(destination/"payload.json").write_text("{}")
