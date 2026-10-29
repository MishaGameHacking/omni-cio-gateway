"""Read-only release54 investigation; no model inference or account transactions."""
from contextlib import closing
from pathlib import Path
import json, shlex, sqlite3, time
env = {}
for line in Path("/etc/analyst-ai/backend.env").read_text().splitlines():
    key, sep, value = line.partition("=")
    if sep and not key.startswith("#"):
        parts = shlex.split(value)
        if len(parts) == 1:
            env[key] = parts[0]
report = {"read_only": True, "inference_called": False,
    "gateway_key_present": bool(env.get("TIMEWEB_AI_TOKEN")),
    "agent_fast_key_present": bool(env.get("TIMEWEB_AI_FAST_TOKEN")),
    "configuration": {k: env.get(k) for k in (
        "AI_TRANSPORT", "AI_EXTERNAL_PROCESSING_APPROVED", "AI_ALLOWED_PROCESSING_REGIONS",
        "AI_MODEL_FAST", "AI_MODEL_STANDARD", "AI_MODEL_PREMIUM",
        "AI_USER_DAILY_RUB", "AI_PROJECT_DAILY_RUB", "AI_USER_MONTHLY_RUB", "AI_PROJECT_MONTHLY_RUB",
        "AI_FAST_PROCESSING_REGION", "AI_FAST_INPUT_RUB_PER_MILLION", "AI_FAST_OUTPUT_RUB_PER_MILLION",
        "AI_FAST_PRICING_VALID_UNTIL")}}
dbpath = Path(env.get("DATABASE_PATH", "/var/lib/analyst-ai/backend.db"))
with closing(sqlite3.connect(dbpath.as_uri() + "?mode=ro", uri=True, timeout=10)) as db:
    db.execute("PRAGMA query_only=ON")
    rows = db.execute("SELECT payload_json FROM client_diagnostic_events WHERE process_version=53 ORDER BY received_at DESC LIMIT 6").fetchall()
    report["crashes53"] = [{k: event.get(k) for k in ("kind","capture_version","process_version","exception_code","stage","frames")}
        for (raw,) in rows for event in [json.loads(raw)]]
    report["ai_call_count"] = db.execute("SELECT COUNT(*) FROM ai_money_reservations").fetchone()[0]
    report["history_bounds"] = db.execute("SELECT MIN(created_at),MAX(created_at),COUNT(*) FROM workspace_snapshots").fetchone()
print("RELEASE54_OBSERVATION=" + json.dumps(report), flush=True)
