"""Read-only, authenticated-facing views of persisted public-source evidence."""
from __future__ import annotations

from contextlib import closing
import json
import re
import time

try:
    from .osint_catalogue import SOURCES, catalogue, canonical_url
    from .osint_store import MAX_OBJECT_BYTES, MAX_PUBLICATIONS, MAX_FRONTIER
except ImportError:
    from osint_catalogue import SOURCES, catalogue, canonical_url
    from osint_store import MAX_OBJECT_BYTES, MAX_PUBLICATIONS, MAX_FRONTIER


def status(connect, now: int | None = None) -> dict:
    now = int(time.time()) if now is None else now
    with closing(connect()) as db:
        state = dict(db.execute("SELECT * FROM osint_revision_v1 WHERE singleton=1").fetchone())
        counts = dict(db.execute("SELECT source_id,COUNT(*) FROM osint_publications_v1 WHERE expires_at>? GROUP BY source_id", (now,)))
        targets = db.execute("SELECT * FROM osint_targets_v1").fetchall()
    rows = [_source_status(source, targets, counts, now) for source in SOURCES]
    return {"schema_version": 1, "revision": state["revision"], "server_time": now,
        "state": "attention" if any(row["stale"] or row["state"] in {"partial", "unavailable", "empty"} or row["target_failures"] or row["coverage"].get("truncated") or row["coverage"].get("empty_index") for row in rows) else "current",
        "sources": rows, "documents": sum(counts.values()),
        "due_targets": sum(row["next_at"] <= now and row["lease_until"] <= now for row in targets),
        "in_progress": sum(row["lease_until"] > now for row in targets),
        "storage": {"text_bytes": state["object_bytes"], "text_limit": MAX_OBJECT_BYTES,
                    "document_limit": MAX_PUBLICATIONS, "frontier_limit": MAX_FRONTIER},
        "last_cleanup": state["last_cleanup"], "search_mode": state["search_mode"],
        "paid_models_used": False, "real_orders_enabled": False}


def _source_status(source, targets, counts, now):
    related = [row for row in targets if row["source_id"] == source.id]
    root = next((row for row in related if row["url"] == canonical_url(source.url, source.hosts)), None)
    success = root["last_success"] if root else None
    stale = success is None or now - success > source.interval * 3
    return {"id": source.id, "title": source.title,
        "state": "pending" if root is None else root["status"], "stale": stale,
        "last_check": root["last_check"] if root else None, "last_success": success,
        "next_check": root["next_at"] if root else None, "error": root["error"] if root else None,
        "coverage": json.loads(root["coverage_json"]) if root else {},
        "documents": counts.get(source.id, 0), "targets": len(related),
        "target_failures": sum(row["status"] == "unavailable" for row in related)}


def sources() -> list[dict]:
    return catalogue()


def _record(row, *, full=False):
    value = dict(row)
    analysis = json.loads(value.pop("analysis_json"))
    result = {key: value[key] for key in ("id", "source_id", "url", "title", "kind", "publisher",
        "published_at", "discovered_at", "first_seen", "last_seen", "last_changed", "expires_at", "raw_sha", "revision_sha")}
    result.update(primary_source=bool(value["primary_source"]), analysis=analysis,
                  similar_to=value["similar_id"], similarity_is_corroboration=False)
    if full:
        result["text"] = value["body"]
    return result


def documents(connect, *, limit=25, before_id=None, source_id=None, query=None, now=None) -> dict:
    now = int(time.time()) if now is None else now
    conditions, params = ["p.expires_at>?"], [now]
    if before_id is not None:
        conditions.append("p.id<?")
        params.append(before_id)
    if source_id is not None:
        conditions.append("p.source_id=?")
        params.append(source_id)
    with closing(connect()) as db:
        mode = db.execute("SELECT search_mode FROM osint_revision_v1 WHERE singleton=1").fetchone()[0]
        search_limited = False
        if query:
            tokens = re.findall(r"[^\W_]+", query, re.UNICODE)[:8]
            if not tokens:
                return {"items": [], "next_before_id": None, "search_limited": False}
            if mode == "fts5":
                conditions.append("p.id IN (SELECT rowid FROM osint_search_v1 WHERE osint_search_v1 MATCH ?)")
                params.append(" AND ".join('"' + token + '"' for token in tokens))
            else:
                conditions.append("p.id IN (SELECT id FROM osint_publications_v1 ORDER BY id DESC LIMIT 10000)")
                for token in tokens:
                    conditions.append("p.title LIKE ?")
                    params.append("%" + token + "%")
                search_limited = True
        rows = db.execute("SELECT p.* FROM osint_publications_v1 p WHERE " + " AND ".join(conditions) +
                          " ORDER BY p.id DESC LIMIT ?", (*params, limit + 1)).fetchall()
    return {"items": [_record(row) for row in rows[:limit]],
        "next_before_id": rows[limit - 1]["id"] if len(rows) > limit else None,
        "search_limited": search_limited}


def document(connect, identifier: int, now=None) -> dict | None:
    now = int(time.time()) if now is None else now
    with closing(connect()) as db:
        row = db.execute("""SELECT p.*,o.body FROM osint_publications_v1 p
            JOIN osint_objects_v1 o ON o.sha=p.object_sha WHERE p.id=? AND p.expires_at>?""",
            (identifier, now)).fetchone()
    return _record(row, full=True) if row else None
