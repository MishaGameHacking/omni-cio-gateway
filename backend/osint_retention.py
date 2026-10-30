"""Bounded retention for the public corpus only; never portfolio or reviewed facts."""
from __future__ import annotations

try:
    from .ai_budget import transaction
except ImportError:
    from ai_budget import transaction

DAY = 86400


def cleanup(connect, now: int, guard=None) -> dict:
    with transaction(connect) as db:
        if guard:
            guard(db)
        state = db.execute("SELECT last_cleanup,search_mode FROM osint_revision_v1 WHERE singleton=1").fetchone()
        if state["last_cleanup"] > now - 3600:
            return {"expired": 0, "objects": 0, "skipped": True}
        expired = [row[0] for row in db.execute(
            "SELECT id FROM osint_publications_v1 WHERE expires_at<=? ORDER BY expires_at LIMIT 1000", (now,))]
        for identifier in expired:
            db.execute("""INSERT OR REPLACE INTO osint_tombstones_v1(key_sha,raw_sha,last_seen)
                SELECT key_sha,raw_sha,? FROM osint_publications_v1 WHERE id=? AND published_at IS NULL""",
                (now, identifier))
            db.execute("DELETE FROM osint_similarity_v1 WHERE publication_id=?", (identifier,))
            if state["search_mode"] == "fts5":
                db.execute("DELETE FROM osint_search_v1 WHERE rowid=?", (identifier,))
            db.execute("DELETE FROM osint_history_v1 WHERE publication_id=?", (identifier,))
            db.execute("DELETE FROM osint_publications_v1 WHERE id=?", (identifier,))
        db.execute("DELETE FROM osint_tombstones_v1 WHERE key_sha IN "
                   "(SELECT key_sha FROM osint_tombstones_v1 WHERE last_seen<? LIMIT 2000)", (now - 365 * DAY,))
        db.execute("DELETE FROM osint_tombstones_v1 WHERE key_sha IN "
                   "(SELECT key_sha FROM osint_tombstones_v1 ORDER BY last_seen DESC LIMIT -1 OFFSET 200000)")
        db.execute("UPDATE osint_publications_v1 SET similar_id=NULL WHERE similar_id IS NOT NULL AND "
                   "NOT EXISTS(SELECT 1 FROM osint_publications_v1 p WHERE p.id=osint_publications_v1.similar_id)")
        db.execute("DELETE FROM osint_history_v1 WHERE rowid IN "
                   "(SELECT rowid FROM osint_history_v1 WHERE observed_at<? LIMIT 2000)", (now - 365 * DAY,))
        unused = db.execute("""SELECT sha,bytes FROM osint_objects_v1 o WHERE created_at<?
            AND NOT EXISTS(SELECT 1 FROM osint_publications_v1 p WHERE p.object_sha=o.sha)
            AND NOT EXISTS(SELECT 1 FROM osint_history_v1 h WHERE h.object_sha=o.sha) LIMIT 1000""",
            (now - 30 * DAY,)).fetchall()
        db.executemany("DELETE FROM osint_objects_v1 WHERE sha=?", [(row["sha"],) for row in unused])
        originals = db.execute("""SELECT sha FROM osint_originals_v1 o WHERE created_at<?
            AND NOT EXISTS(SELECT 1 FROM osint_publications_v1 p WHERE p.raw_sha=o.sha)
            AND NOT EXISTS(SELECT 1 FROM osint_history_v1 h WHERE h.raw_sha=o.sha) LIMIT 1000""",
            (now - 30 * DAY,)).fetchall()
        db.executemany("DELETE FROM osint_originals_v1 WHERE sha=?", [(row["sha"],) for row in originals])
        db.execute("DELETE FROM osint_rejections_v1 WHERE rowid IN "
                   "(SELECT rowid FROM osint_rejections_v1 WHERE at<? LIMIT 2000)", (now - 30 * DAY,))
        # Completed OSINT job receipts are bounded separately, without touching other job kinds.
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='workspace_jobs'").fetchone():
            jobs = [row[0] for row in db.execute("""SELECT id FROM workspace_jobs WHERE kind='osint'
                AND state IN ('completed','failed','cancelled') AND updated_at<? LIMIT 1000""", (now - 7 * DAY,))]
            db.executemany("DELETE FROM workspace_job_requests WHERE job_id=?", [(job,) for job in jobs])
            db.executemany("DELETE FROM workspace_jobs WHERE id=?", [(job,) for job in jobs])
        db.execute("""UPDATE osint_revision_v1 SET last_cleanup=?,publications=publications-?,
            object_bytes=object_bytes-?,revision=revision+? WHERE singleton=1""",
            (now, len(expired), sum(row["bytes"] for row in unused), int(bool(expired))))
    return {"expired": len(expired), "objects": len(unused), "originals": len(originals), "skipped": False}
