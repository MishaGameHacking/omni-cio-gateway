"""Public OSINT corpus and crawl frontier inside the existing SQLite database."""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
import sqlite3
import time
import uuid

try:
    from .ai_budget import transaction
    from .osint_catalogue import SOURCES, BY_ID, IntakeError, target_url
    from .osint_analysis import bands
except ImportError:
    from ai_budget import transaction
    from osint_catalogue import SOURCES, BY_ID, IntakeError, target_url
    from osint_analysis import bands

MAX_OBJECT_BYTES = 256 * 1024**2
MAX_PUBLICATIONS = 100000
MAX_FRONTIER = 5000
NEWS_DAYS = 30
REPORT_DAYS = 5 * 366


def encoded(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha(value: str | bytes) -> str:
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def initialize(connect) -> None:
    with transaction(connect) as db:
        statements = (
            """CREATE TABLE IF NOT EXISTS osint_revision_v1 (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1),revision INTEGER NOT NULL,
                object_bytes INTEGER NOT NULL DEFAULT 0,publications INTEGER NOT NULL DEFAULT 0,
                last_cleanup INTEGER NOT NULL DEFAULT 0,search_mode TEXT NOT NULL DEFAULT 'indexed')""",
            """CREATE TABLE IF NOT EXISTS osint_targets_v1 (
                id TEXT PRIMARY KEY,source_id TEXT NOT NULL,url TEXT NOT NULL,kind TEXT NOT NULL,
                title TEXT NOT NULL,published_at INTEGER,context TEXT NOT NULL DEFAULT '',
                next_at INTEGER NOT NULL DEFAULT 0,lease_owner TEXT,lease_until INTEGER NOT NULL DEFAULT 0,
                attempts INTEGER NOT NULL DEFAULT 0,last_check INTEGER,last_success INTEGER,
                status TEXT NOT NULL DEFAULT 'pending',error TEXT,etag TEXT,last_modified TEXT,
                body_sha TEXT,cursor_json TEXT NOT NULL DEFAULT '{}',coverage_json TEXT NOT NULL DEFAULT '{}',
                UNIQUE(source_id,url))""",
            "CREATE INDEX IF NOT EXISTS osint_targets_due ON osint_targets_v1(next_at,lease_until)",
            """CREATE TABLE IF NOT EXISTS osint_objects_v1 (
                sha TEXT PRIMARY KEY,title TEXT NOT NULL,body TEXT NOT NULL,
                bytes INTEGER NOT NULL,created_at INTEGER NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS osint_publications_v1 (
                id INTEGER PRIMARY KEY,key_sha TEXT UNIQUE NOT NULL,source_id TEXT NOT NULL,
                url TEXT NOT NULL,title TEXT NOT NULL,kind TEXT NOT NULL,publisher TEXT NOT NULL,
                primary_source INTEGER NOT NULL,published_at INTEGER,discovered_at INTEGER,
                first_seen INTEGER NOT NULL,last_seen INTEGER NOT NULL,last_changed INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,object_sha TEXT NOT NULL,raw_sha TEXT NOT NULL,
                analysis_json TEXT NOT NULL,revision_sha TEXT NOT NULL,similar_id INTEGER)""",
            "CREATE INDEX IF NOT EXISTS osint_publications_expiry ON osint_publications_v1(expires_at)",
            "CREATE INDEX IF NOT EXISTS osint_publications_time ON osint_publications_v1(last_changed DESC,id DESC)",
            "CREATE INDEX IF NOT EXISTS osint_publications_object ON osint_publications_v1(object_sha)",
            "CREATE INDEX IF NOT EXISTS osint_publications_source ON osint_publications_v1(source_id,expires_at)",
            """CREATE TABLE IF NOT EXISTS osint_history_v1 (
                publication_id INTEGER NOT NULL,revision_sha TEXT NOT NULL,object_sha TEXT NOT NULL,
                raw_sha TEXT NOT NULL,observed_at INTEGER NOT NULL,
                PRIMARY KEY(publication_id,revision_sha))""",
            "CREATE INDEX IF NOT EXISTS osint_history_age ON osint_history_v1(observed_at)",
            "CREATE INDEX IF NOT EXISTS osint_history_object ON osint_history_v1(object_sha)",
            """CREATE TABLE IF NOT EXISTS osint_similarity_v1 (
                band INTEGER NOT NULL,value INTEGER NOT NULL,publication_id INTEGER NOT NULL,
                PRIMARY KEY(band,value,publication_id))""",
            """CREATE TABLE IF NOT EXISTS osint_hosts_v1 (
                host TEXT PRIMARY KEY,next_at REAL NOT NULL DEFAULT 0,robots_text TEXT,
                robots_expires INTEGER NOT NULL DEFAULT 0,robots_status INTEGER)""",
            """CREATE TABLE IF NOT EXISTS osint_rejections_v1 (
                target_id TEXT NOT NULL,reason TEXT NOT NULL,count INTEGER NOT NULL,at INTEGER NOT NULL,
                PRIMARY KEY(target_id,reason,at))""",
        )
        for statement in statements:
            db.execute(statement)
        db.execute("INSERT OR IGNORE INTO osint_revision_v1(singleton,revision) VALUES(1,1)")
        try:
            db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS osint_search_v1 USING fts5(title,body,tokenize='unicode61')")
            db.execute("UPDATE osint_revision_v1 SET search_mode='fts5' WHERE singleton=1 AND search_mode!='fts5'")
        except sqlite3.OperationalError:
            pass
        for source in SOURCES:
            add_target(db, source.id, {"url": source.url, "kind": source.kind, "title": source.title}, now=0)


def add_target(db, source_id: str, item: dict, now: int) -> bool:
    source = BY_ID[source_id]
    url = target_url(source, item["url"], item["kind"])
    key = sha(source_id + "\0" + url)
    if db.execute("SELECT 1 FROM osint_targets_v1 WHERE id=?", (key,)).fetchone():
        return False
    if db.execute("SELECT COUNT(*) FROM osint_targets_v1").fetchone()[0] >= MAX_FRONTIER:
        raise IntakeError("osint_frontier_capacity")
    db.execute("""INSERT INTO osint_targets_v1(id,source_id,url,kind,title,published_at,context,next_at)
        VALUES(?,?,?,?,?,?,?,?)""", (key, source_id, url, item["kind"], item["title"][:400],
        item.get("published_at"), item.get("context", "")[:1000], now))
    return True


def due(connect, now: int) -> bool:
    with closing(connect()) as db:
        return db.execute("SELECT 1 FROM osint_targets_v1 WHERE next_at<=? AND lease_until<=? LIMIT 1",
                          (now, now)).fetchone() is not None


def claim(connect, now: int) -> dict | None:
    with transaction(connect) as db:
        row = db.execute("""SELECT * FROM osint_targets_v1 WHERE next_at<=? AND lease_until<=?
            ORDER BY CASE WHEN kind IN ('rss','gdelt') AND next_at<? THEN 0 ELSE 1 END,
            next_at,id LIMIT 1""", (now, now, now - 300)).fetchone()
        if row is None:
            return None
        owner = uuid.uuid4().hex
        db.execute("UPDATE osint_targets_v1 SET lease_owner=?,lease_until=? WHERE id=?",
                   (owner, now + 600, row["id"]))
        return {**dict(row), "lease_owner": owner}


def assert_claim(db, target, now: int) -> None:
    current = db.execute("SELECT lease_owner,lease_until FROM osint_targets_v1 WHERE id=?", (target["id"],)).fetchone()
    if current is None or current[0] != target["lease_owner"] or current[1] <= now:
        raise IntakeError("osint_target_lease_lost")


def reserve_host(connect, host: str, delay: int = 3) -> float:
    now = time.time()
    with transaction(connect) as db:
        row = db.execute("SELECT next_at FROM osint_hosts_v1 WHERE host=?", (host,)).fetchone()
        at = max(now, row[0] if row else now)
        if at - now > 20:
            raise IntakeError("osint_host_throttled")
        db.execute("""INSERT INTO osint_hosts_v1(host,next_at) VALUES(?,?)
            ON CONFLICT(host) DO UPDATE SET next_at=excluded.next_at""", (host, at + delay))
    return max(0.0, at - now)


def robots(connect, host: str, now: int) -> dict | None:
    with closing(connect()) as db:
        row = db.execute("SELECT * FROM osint_hosts_v1 WHERE host=? AND robots_expires>?", (host, now)).fetchone()
    return dict(row) if row else None


def save_robots(connect, host: str, raw: str, status: int, now: int) -> None:
    with transaction(connect) as db:
        db.execute("""INSERT INTO osint_hosts_v1(host,robots_text,robots_status,robots_expires) VALUES(?,?,?,?)
            ON CONFLICT(host) DO UPDATE SET robots_text=excluded.robots_text,
            robots_status=excluded.robots_status,robots_expires=excluded.robots_expires""",
            (host, raw[:131072], status, now + (86400 if status in (200, 404) else 900)))


def _similar(db, value: str, identifier: int, now: int) -> int | None:
    candidates = set()
    for band, part in bands(value):
        candidates.update(row[0] for row in db.execute("""SELECT s.publication_id FROM osint_similarity_v1 s
            JOIN osint_publications_v1 p ON p.id=s.publication_id
            WHERE s.band=? AND s.value=? AND p.expires_at>? AND p.id!=? LIMIT 100""",
            (band, part, now, identifier)))
    for candidate in sorted(candidates):
        row = db.execute("SELECT analysis_json FROM osint_publications_v1 WHERE id=?", (candidate,)).fetchone()
        previous = json.loads(row[0])["simhash"]
        if (int(previous, 16) ^ int(value, 16)).bit_count() <= 3:
            return candidate
    return None


def _save_object(db, title, text, now):
    digest = sha(title + "\0" + text)
    exists = db.execute("SELECT 1 FROM osint_objects_v1 WHERE sha=?", (digest,)).fetchone()
    if not exists:
        size = len((title + text).encode())
        used = db.execute("SELECT object_bytes FROM osint_revision_v1 WHERE singleton=1").fetchone()[0]
        if used + size > MAX_OBJECT_BYTES:
            raise IntakeError("osint_corpus_capacity")
        db.execute("INSERT INTO osint_objects_v1 VALUES(?,?,?,?,?)", (digest, title, text, size, now))
        db.execute("UPDATE osint_revision_v1 SET object_bytes=object_bytes+? WHERE singleton=1", (size,))
    return digest


def save_publication(db, source, item: dict, analysis: dict, now: int) -> bool:
    if not analysis["relevant"]:
        return False
    key = sha(item["url"])
    old = db.execute("SELECT * FROM osint_publications_v1 WHERE key_sha=?", (key,)).fetchone()
    if old and old["primary_source"] and not item["primary"]:
        return False
    age_basis = item.get("published_at") or (old["first_seen"] if old else now)
    lifetime = (REPORT_DAYS if item["kind"] == "report" else NEWS_DAYS) * 86400
    expiry = age_basis + lifetime
    if expiry <= now:
        return False
    raw_sha = item.get("raw_sha") or sha(item["title"] + "\0" + item["text"])
    revision = sha(encoded({key: item.get(key) for key in ("title", "text", "published_at", "primary")}
                          ) + raw_sha + analysis["version"])
    if old and old["revision_sha"] == revision:
        db.execute("UPDATE osint_publications_v1 SET last_seen=? WHERE id=?", (now, old["id"]))
        return False
    if not old and db.execute("SELECT publications FROM osint_revision_v1 WHERE singleton=1").fetchone()[0] >= MAX_PUBLICATIONS:
        raise IntakeError("osint_corpus_capacity")
    object_sha = _save_object(db, item["title"], item["text"], now)
    values = (source.id, item["url"], item["title"], item["kind"], item["publisher"], int(item["primary"]),
              item.get("published_at"), item.get("discovered_at"), now, now, expiry, object_sha, raw_sha,
              encoded(analysis), revision)
    if old:
        identifier = old["id"]
        db.execute("""INSERT OR IGNORE INTO osint_history_v1 VALUES(?,?,?,?,?)""",
                   (identifier, old["revision_sha"], old["object_sha"], old["raw_sha"], now))
        db.execute("""UPDATE osint_publications_v1 SET source_id=?,url=?,title=?,kind=?,publisher=?,
            primary_source=?,published_at=?,discovered_at=?,last_seen=?,last_changed=?,expires_at=?,
            object_sha=?,raw_sha=?,analysis_json=?,revision_sha=? WHERE id=?""", (*values, identifier))
    else:
        db.execute("""INSERT INTO osint_publications_v1(source_id,url,title,kind,publisher,primary_source,
            published_at,discovered_at,last_seen,last_changed,expires_at,object_sha,raw_sha,analysis_json,
            revision_sha,key_sha,first_seen) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (*values, key, now))
        identifier = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute("UPDATE osint_revision_v1 SET publications=publications+1 WHERE singleton=1")
    similar = _similar(db, analysis["simhash"], identifier, now)
    db.execute("UPDATE osint_publications_v1 SET similar_id=? WHERE id=?", (similar, identifier))
    db.execute("DELETE FROM osint_similarity_v1 WHERE publication_id=?", (identifier,))
    db.executemany("INSERT INTO osint_similarity_v1 VALUES(?,?,?)",
                   [(band, part, identifier) for band, part in bands(analysis["simhash"])])
    mode = db.execute("SELECT search_mode FROM osint_revision_v1 WHERE singleton=1").fetchone()[0]
    if mode == "fts5":
        db.execute("DELETE FROM osint_search_v1 WHERE rowid=?", (identifier,))
        db.execute("INSERT INTO osint_search_v1(rowid,title,body) VALUES(?,?,?)", (identifier, item["title"], item["text"]))
    db.execute("UPDATE osint_revision_v1 SET revision=revision+1 WHERE singleton=1")
    return True


def finish(connect, target, *, now: int, status: str, next_at: int, headers: dict,
           coverage: dict, rows=(), children=(), error=None, body_sha=None, cursor=None, guard=None) -> dict:
    changed = 0
    with transaction(connect) as db:
        if guard:
            guard(db)
        assert_claim(db, target, now)
        source = BY_ID[target["source_id"]]
        for item, analysis in rows:
            changed += int(save_publication(db, source, item, analysis, now))
        for child in children:
            add_target(db, source.id, child, now)
        if coverage.get("rejected"):
            db.execute("INSERT OR REPLACE INTO osint_rejections_v1 VALUES(?,?,?,?)",
                       (target["id"], "input_rejected", coverage["rejected"], now))
        success = status in {"ready", "empty", "not_modified", "partial"}
        db.execute("""UPDATE osint_targets_v1 SET next_at=?,lease_owner=NULL,lease_until=0,
            attempts=?,last_check=?,last_success=?,status=?,error=?,etag=?,last_modified=?,
            body_sha=?,cursor_json=?,coverage_json=? WHERE id=?""",
            (next_at, 0 if success else target["attempts"] + 1, now,
             now if success else target["last_success"], status, error,
             headers.get("etag", target["etag"]) if success else target["etag"],
             headers.get("last-modified", target["last_modified"]) if success else target["last_modified"],
             body_sha or target["body_sha"], encoded(cursor if cursor is not None else json.loads(target["cursor_json"])),
             encoded(coverage), target["id"]))
        if target["status"] != status:
            db.execute("UPDATE osint_revision_v1 SET revision=revision+1 WHERE singleton=1")
    return {"changed": changed, "status": status}
