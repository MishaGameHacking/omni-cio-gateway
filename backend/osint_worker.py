"""Free public-source work on the existing durable queue and scheduler."""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import urlencode, urlsplit

from fastapi import HTTPException

try:
    from . import app as backend, osint_store as store, osint_network as net, osint_content as content
    from .osint_catalogue import BY_ID, GDELT_QUERY, IntakeError, MAX_BODY, MAX_PDF, MAX_FEED
    from .osint_analysis import analyze, clean_text
    from .local_research import select_public_fragments
    from .osint_retention import cleanup
    from .ai_budget import transaction
except ImportError:
    import app as backend
    import osint_store as store
    import osint_network as net
    import osint_content as content
    from osint_catalogue import BY_ID, GDELT_QUERY, IntakeError, MAX_BODY, MAX_PDF, MAX_FEED
    from osint_analysis import analyze, clean_text
    from local_research import select_public_fragments
    from osint_retention import cleanup
    from ai_budget import transaction


def guard_for(user_id):
    try:
        from . import autonomous_controller, volume_jobs
    except ImportError:
        import autonomous_controller
        import volume_jobs

    def guard(db):
        volume_jobs.assert_current_in(db)
        if not db.execute("SELECT 1 FROM users WHERE id=?", (user_id,)).fetchone():
            raise HTTPException(409, "osint_owner_missing")
        autonomous_controller.assert_enabled_in(db, user_id)
    return guard


def enqueue_cycle(user, request_id=None):
    try:
        from . import volume_jobs
    except ImportError:
        import volume_jobs
    now, user_id = int(time.time()), int(user["id"])
    if request_id is None and not store.due(backend.connect, now):
        return None
    guard = guard_for(user_id)

    def before(db, _identifier):
        guard(db)
        if db.execute("SELECT 1 FROM workspace_jobs WHERE kind='osint' AND state IN ('queued','running')").fetchone():
            raise HTTPException(409, "osint_collection_pending")
    return volume_jobs.enqueue(user_id, request_id or "auto.osint." + str(now // 300),
                               "osint", {"scope": "public_investment"}, before_insert=before)


def extract_pdf(raw: bytes) -> dict:
    # No inherited credentials, shell, document commands, JavaScript or URL opening.
    # The fixed child parser has independent CPU/memory/file-descriptor limits.
    environment = {"PATH": os.defpath, "LANG": "C.UTF-8", "PYTHONIOENCODING": "utf-8"}
    try:
        result = subprocess.run([sys.executable, "-I", str(Path(__file__).with_name("osint_pdf.py"))],
            input=raw, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            env=environment, timeout=25, check=False)
    except subprocess.TimeoutExpired:
        raise IntakeError("osint_pdf_timeout") from None
    if result.returncode or len(result.stdout) > 2 * 1024**2:
        raise IntakeError("osint_pdf_resource_limit")
    try:
        value = json.loads(result.stdout)
    except ValueError:
        raise IntakeError("osint_pdf_parse_failed") from None
    if value.get("error"):
        raise IntakeError(value["error"])
    return value


def _pause(guard):
    with closing(backend.connect()) as db:
        guard(db)


def _throttle(url, guard, delay=3):
    _pause(guard)
    wait = store.reserve_host(backend.connect, urlsplit(url).hostname, delay)
    if wait:
        time.sleep(wait)
    _pause(guard)


def _before(url, source, guard, *, robots_required):
    if not robots_required:
        _throttle(url, guard)
        return
    host, now = urlsplit(url).hostname, int(time.time())
    policy = store.robots(backend.connect, host, now)
    if policy is None:
        status, metadata, raw, _ = net.request("https://" + host + "/robots.txt", source.hosts,
            maximum=131072, before_request=lambda destination: _throttle(destination, guard))
        if status in (429, 503):
            store.defer_host(backend.connect, host, net.retry_at(metadata.get("retry-after"), now, 0, 900))
        store.save_robots(backend.connect, host, raw.decode("utf-8", errors="replace"), status, now)
        policy = {"robots_status": status, "robots_text": raw.decode("utf-8", errors="replace")}
    if policy["robots_status"] not in (200, 404):
        raise IntakeError("osint_robots_unavailable")
    allowed, delay = net.robots_decision(policy["robots_text"] or "", url)
    if policy["robots_status"] == 200 and not allowed:
        raise IntakeError("osint_robots_denied")
    _throttle(url, guard, delay)


def _discovery_url(target, now):
    cursor = json.loads(target["cursor_json"])
    floor = now - 89 * 86400
    start = max(int(cursor.get("start", now - 86400)), floor)
    end = min(start + int(cursor.get("width", 21600)), now - 900)
    if end - start < 900:
        return None, {"start": start, "end": end, "gaps": int(cursor.get("gaps", 0))}
    fmt = lambda value: datetime.fromtimestamp(value, timezone.utc).strftime("%Y%m%d%H%M%S")
    query = {"query": GDELT_QUERY, "mode": "artlist", "format": "json", "sort": "datedesc",
             "maxrecords": "250", "startdatetime": fmt(start), "enddatetime": fmt(end)}
    return target["url"] + "?" + urlencode(query), {"start": start, "end": end,
        "gaps": int(cursor.get("gaps", 0)) + int(int(cursor.get("start", start)) < floor)}


def _parse(target, source, raw, final_url, now, window):
    children, cursor = [], None
    if target["kind"] == "rss":
        items, coverage = content.feed(raw, source, now)
    elif target["kind"] == "index":
        children, coverage = content.report_links(raw, source, final_url, now)
        items = []
    elif target["kind"] == "gdelt":
        items, coverage = content.discovery(raw, now)
        width = window["end"] - window["start"]
        if coverage["truncated"] and width > 900:
            cursor = {"start": window["start"], "width": max(900, width // 2), "gaps": window["gaps"]}
            items = []  # Retry a narrower window before advancing its durable cursor.
        else:
            cursor = {"start": window["end"], "width": 21600,
                      "gaps": window["gaps"] + int(coverage["truncated"])}
        coverage.update(window_start=window["start"], window_end=window["end"],
                        capped_windows=cursor["gaps"], historical_backfill_days=1)
    elif target["kind"] == "pdf":
        parsed = extract_pdf(raw)
        pages = [{"page": row["page"], "text": clean_text(row["text"], 12000)} for row in parsed["pages"]]
        text = clean_text("\n\n".join(row["text"] for row in pages))
        items = [{"url": target["url"], "title": clean_text(target["title"], 400),
            "text": text, "published_at": target["published_at"], "publisher": source.publisher,
            "primary": True, "kind": "report", "raw_sha": store.sha(raw), "original_pdf": raw, "pages": pages}]
        coverage = {"items_seen": 1, "coverage": "official_report_text",
                    "page_count": parsed["page_count"], "truncated": parsed["truncated"], "needs_ocr": parsed["needs_ocr"]}
    else:
        raise IntakeError("osint_target_kind_invalid")
    rows = []
    for item in items:
        analysis = analyze(item["title"], item["text"], report=item["kind"] == "report", pages=item.get("pages"))
        if item["kind"] == "report":
            analysis["extraction"] = {key: coverage[key] for key in ("page_count", "truncated", "needs_ocr")}
        if item["kind"] == "report" and analysis["relevant"]:
            selected = select_public_fragments(item["title"], item["text"])
            if selected["status"] != "disabled":
                analysis["local_research"] = selected
            if selected["status"] == "source_excerpt_selection":
                analysis["version"] += ":local:" + selected["model_sha256"][:16]
        analysis["issuer_hint"] = source.issuer
        analysis["issuer_identity_verified"] = False
        rows.append((item, analysis))
    coverage["relevant"] = sum(analysis["relevant"] for _, analysis in rows)
    return rows, children, coverage, cursor


def _request_headers(target):
    if target["kind"] == "gdelt":
        return {}
    if target["kind"] == "pdf" and not store.has_original(backend.connect, target["body_sha"]):
        return {}
    return {"If-None-Match": target["etag"], "If-Modified-Since": target["last_modified"]}


def process(target, guard):
    source, now = BY_ID[target["source_id"]], int(time.time())
    url, window = target["url"], None
    if target["kind"] == "gdelt":
        url, window = _discovery_url(target, now)
        if url is None:
            return store.finish(backend.connect, target, now=now, status=target["status"],
                next_at=now + source.interval, headers={}, coverage=json.loads(target["coverage_json"]), guard=guard)
    headers = _request_headers(target)
    status, response_headers, raw, final_url = net.request(url, source.hosts, headers,
        maximum={"pdf": MAX_PDF, "rss": MAX_FEED}.get(target["kind"], MAX_BODY),
        before_request=lambda destination: _before(destination, source, guard,
                                                    robots_required=target["kind"] in {"index", "pdf"}))
    now = int(time.time())
    interval = 7 * 86400 if target["kind"] == "pdf" else source.interval
    if status == 304:
        return store.finish(backend.connect, target, now=now, status="not_modified", next_at=now + interval,
            headers=response_headers, coverage=json.loads(target["coverage_json"]), guard=guard)
    if status != 200:
        retry = net.retry_at(response_headers.get("retry-after"), now, target["attempts"], interval)
        if status in (429, 503):
            store.defer_host(backend.connect, urlsplit(final_url).hostname, retry)
        return store.finish(backend.connect, target, now=now, status="unavailable",
            next_at=retry,
            headers={}, coverage={"http_status": status}, error="osint_http_" + str(status), guard=guard)
    rows, children, coverage, cursor = _parse(target, source, raw, final_url, now, window)
    state = "partial" if coverage.get("truncated") or coverage.get("needs_ocr") else "ready"
    if not coverage["items_seen"]:
        state = "empty"
    next_at = now + interval
    if cursor and cursor["start"] < now - 3600:
        next_at = now + 60
    return store.finish(backend.connect, target, now=int(time.time()), status=state, next_at=next_at,
        headers=response_headers, rows=rows, children=children, coverage=coverage,
        cursor=cursor, body_sha=store.sha(raw), guard=guard)


def collect(user, _payload, _checkpoint, progress):
    user_id, started = int(user["id"]), time.monotonic()
    guard = guard_for(user_id)
    _pause(guard)
    retention = cleanup(backend.connect, int(time.time()), guard)
    outcomes = []
    for _ in range(4):
        if time.monotonic() - started > 90:
            break
        progress("osint_collecting")
        _pause(guard)
        target = store.claim(backend.connect, int(time.time()))
        if target is None:
            break
        try:
            outcome = process(target, guard)
        except (IntakeError, OSError, ValueError) as error:
            now = int(time.time())
            code = str(error) if isinstance(error, IntakeError) else "osint_source_unavailable"
            outcome = store.finish(backend.connect, target, now=now, status="unavailable",
                next_at=net.retry_at(None, now, target["attempts"], BY_ID[target["source_id"]].interval),
                headers={}, coverage={}, error=code, guard=guard)
        finally:
            # A pause or cancellation releases only this worker's frontier lease.
            with transaction(backend.connect) as db:
                db.execute("UPDATE osint_targets_v1 SET lease_owner=NULL,lease_until=0 WHERE id=? AND lease_owner=?",
                           (target["id"], target["lease_owner"]))
        outcomes.append({"source_id": target["source_id"], **outcome})
    return {"sources": outcomes, "retention": retention, "paid_model_calls": 0, "orders": 0}


