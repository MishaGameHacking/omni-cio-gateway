"""Read-only operational observation of the deployed public corpus; no product tests."""
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request

PUBLIC = "https://analyst-ai-2941515.twc1.net"
DATABASE = Path("/var/lib/analyst-ai/backend.db")


def fetch(path):
    try:
        with urllib.request.urlopen(PUBLIC + path, timeout=15) as response:
            return response.status, response.read(1024 * 1024)
    except urllib.error.HTTPError as error:
        return error.code, b""


def sample():
    with closing(sqlite3.connect(DATABASE.as_uri() + "?mode=ro", uri=True, timeout=10)) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        targets = [dict(row) for row in db.execute("""SELECT source_id,kind,url,status,error,last_check,
            last_success,next_at,coverage_json FROM osint_targets_v1 ORDER BY source_id,length(url)""")]
        rows = []
        for source in sorted({row["source_id"] for row in targets}):
            root = next(row for row in targets if row["source_id"] == source and row["kind"] != "pdf")
            count = db.execute("SELECT COUNT(*) FROM osint_publications_v1 WHERE source_id=? AND expires_at>?",
                               (source, int(time.time()))).fetchone()[0]
            related = [row for row in targets if row["source_id"] == source]
            rows.append({"source_id": source, "status": root["status"], "error": root["error"],
                         "last_check": root["last_check"], "last_success": root["last_success"],
                         "coverage": json.loads(root["coverage_json"]), "documents": count,
                         "pdf_pending": sum(row["kind"] == "pdf" and row["last_check"] is None for row in related)})
        counts = {row[0]: row[1] for row in db.execute(
            "SELECT kind,COUNT(*) FROM osint_publications_v1 WHERE expires_at>? GROUP BY kind", (int(time.time()),))}
        jobs = [dict(row) for row in db.execute("""SELECT state,stage,error_code,paid_started,created_at,updated_at
            FROM workspace_jobs WHERE kind='osint' ORDER BY created_at DESC LIMIT 5""")]
        reports = []
        for row in db.execute("""SELECT source_id,url,raw_sha,analysis_json FROM osint_publications_v1
            WHERE kind='report' AND expires_at>? ORDER BY id DESC LIMIT 5""", (int(time.time()),)):
            analysis = json.loads(row["analysis_json"])
            reports.append({"source_id": row["source_id"], "url": row["url"], "sha256": row["raw_sha"],
                            "extraction": analysis.get("extraction"),
                            "financial_candidates": len(analysis.get("financial_candidates", []))})
    return {"sources": rows, "active_documents": counts, "jobs": jobs, "report_samples": reports}


def main():
    payload = ENVELOPE["payload"]
    deadline = time.monotonic() + 650
    observed = None
    while time.monotonic() < deadline:
        observed = sample()
        checked = sum(row["last_check"] is not None for row in observed["sources"])
        if checked == 8 and (observed["active_documents"].get("report", 0)
                             or sum(row["pdf_pending"] for row in observed["sources"]) == 0):
            break
        time.sleep(10)
    policy_status, policy = fetch("/client/update-policy?package_name=ru.omnicio.app.debug")
    receipt = {"schema": 1, "server_id": 9417611, "source_commit": payload["source_commit"],
        "observed_at": datetime.now(timezone.utc).isoformat(), "health": fetch("/health")[0],
        "unauthenticated_osint": fetch("/workspace/osint/status")[0],
        "apk_policy_unchanged": policy_status == 200 and hashlib.sha256(policy).hexdigest() == payload["apk_policy_sha256"],
        "product_tests_executed": False, "observation": observed}
    receipt["services_active"] = subprocess.run(["systemctl", "is-active", "--quiet",
        "analyst-ai-owner.service", "analyst-ai-updates.service"], timeout=15).returncode == 0
    print(json.dumps(receipt, ensure_ascii=True), flush=True)
    if receipt["health"] != 200 or receipt["unauthenticated_osint"] != 401 or not receipt["apk_policy_unchanged"] or not receipt["services_active"]:
        raise RuntimeError("runtime_observation_failed")


if __name__ == "__main__":
    main()
