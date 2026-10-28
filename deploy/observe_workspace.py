"""Observe deployed files and persisted runtime activity without executing product tests."""
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shlex
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request

PUBLIC = "https://analyst-ai-2941515.twc1.net"


def get(path):
    try:
        with urllib.request.urlopen(PUBLIC + path, timeout=15) as response:
            return response.status, response.read(1024 * 1024)
    except urllib.error.HTTPError as error:
        return error.code, b""


def main():
    payload = ENVELOPE["payload"]
    receipt_path = Path("/var/lib/analyst-ai-build/development/server-runtime-40721312988/deployment.json")
    receipt = json.loads(receipt_path.read_text())
    if receipt["source_commit"] != payload["source_commit"] or receipt["status"] != "deployed":
        raise RuntimeError("unexpected_deployed_source")
    env = {}
    for line in Path("/etc/analyst-ai/backend.env").read_text().splitlines():
        name, separator, value = line.partition("=")
        if separator and not name.startswith("#"):
            parts = shlex.split(value)
            if len(parts) == 1:
                env[name] = parts[0]
    database = Path(env.get("DATABASE_PATH", "/var/lib/analyst-ai/backend.db"))
    now = int(time.time())
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=10)) as db:
        db.execute("PRAGMA query_only=ON")
        snapshot = db.execute("SELECT MAX(created_at) FROM workspace_snapshots").fetchone()[0]
        jobs = db.execute("SELECT kind,state,COUNT(*) FROM workspace_jobs WHERE created_at>? GROUP BY kind,state",
                          (now-86400,)).fetchall()
        config_row = db.execute("SELECT config_json FROM workspace_strategy_versions ORDER BY confirmed_at DESC LIMIT 1").fetchone()
        config = json.loads(config_row[0]) if config_row else {}
        costs = db.execute("SELECT COUNT(*),COALESCE(SUM(charge),0) FROM ai_money_reservations").fetchone()
        corpus = db.execute("SELECT kind,COUNT(*) FROM osint_publications_v1 WHERE expires_at>? GROUP BY kind", (now,)).fetchall()
        obsolete = db.execute("SELECT COUNT(*) FROM automation_events WHERE created_at<? AND kind IN ('candidate_research','initial_observation')",
                              (now-30*86400,)).fetchone()[0]
    files = {name:hashlib.sha256((Path("/opt/analyst-ai/backend")/name).read_bytes()).hexdigest()
             for name in receipt["installed_sha256"]}
    services = subprocess.run(["systemctl","is-active","--quiet","analyst-ai-owner.service","analyst-ai-updates.service"],
                              timeout=15).returncode == 0
    policy_status, policy = get("/client/update-policy?package_name=ru.omnicio.app.debug")
    report = {"observed_at":datetime.now(timezone.utc).isoformat(),"source_commit":payload["source_commit"],
        "files_match_deployed_receipt": files == receipt["installed_sha256"],"services_active":services,
        "health":get("/health")[0],"unauthenticated_strategy":get("/workspace/strategy")[0],
        "unauthenticated_decisions":get("/automation/decisions")[0],
        "apk_policy_unchanged":policy_status==200 and hashlib.sha256(policy).hexdigest()==receipt["apk_policy_sha256"],
        "latest_snapshot_at":snapshot,"last_24h_jobs":[{"kind":kind,"state":state,"count":count} for kind,state,count in jobs],
        "active_profile_selected":bool(config.get("tuning")),
        "paid_call_reservations":costs[0],"estimated_and_reserved_micro_rub":costs[1],
        "ai_user_daily_rub":env.get("AI_USER_DAILY_RUB","0"),"ai_project_daily_rub":env.get("AI_PROJECT_DAILY_RUB","0"),
        "active_public_documents":dict(corpus),"obsolete_status_events_remaining":obsolete,
        "product_tests_executed":False,"settings_changed":False,"physical_phone_verified":False}
    print("WORKSPACE_RUNTIME_OBSERVED="+json.dumps(report),flush=True)
    if not (report["files_match_deployed_receipt"] and services and report["health"]==200
            and report["unauthenticated_strategy"]==report["unauthenticated_decisions"]==401
            and report["apk_policy_unchanged"]):
        raise RuntimeError("workspace_runtime_observation_failed")


if __name__ == "__main__":
    main()
