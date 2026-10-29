"""Read-only current/pending decision projection and bounded obsolete-event cleanup."""
from __future__ import annotations
from datetime import datetime, timezone


def _fresh(value, now, seconds):
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return stamp.tzinfo is not None and 0 <= now - stamp.timestamp() < seconds
    except (AttributeError, ValueError, TypeError, OverflowError):
        return False


# Keep one latest explanation per instrument; current facts take precedence.
def _unique(rows):
    result = {}
    for row in rows:
        uid = row.get("instrument_uid")
        if uid and uid not in result:
            result[uid] = row
    return list(result.values())


def project(discovery: dict, events: list, now: int) -> dict:
    candidates = discovery.get("candidates") or []
    current, pending = [], []
    for row in candidates:
        if not _fresh(row.get("as_of"), now, 86400):
            continue
        if row.get("evidence_current") is True:
            current.append(row)
        else:
            pending.append(row)
    current = _unique(current)
    current_ids = {row["instrument_uid"] for row in current}
    pending = _unique([row for row in pending if row.get("instrument_uid") not in current_ids])
    history, seen = [], set()
    for event in events:
        identity = (event.get("kind"), event.get("title"), event.get("summary"))
        if identity in seen or not _fresh(event.get("at"), now, 30 * 86400):
            continue
        seen.add(identity)
        history.append(event)
    return {"current": current, "pending": pending, "history": history,
            "hidden_obsolete_count": max(0, len(candidates) - len(current) - len(pending)),
            "counts": {"current": len(current), "pending": len(pending), "history": len(history)},
            "as_of": datetime.fromtimestamp(now, timezone.utc).isoformat()}


def prune_obsolete_events(db, user_id: int, now: int) -> int:
    # Only repetitive automation status events. Financial operations, decisions,
    # strategy versions and portfolio valuations are not deletion targets.
    cursor = db.execute("""DELETE FROM automation_events WHERE user_id=? AND id IN (
        SELECT id FROM automation_events WHERE user_id=? AND created_at<?
        AND kind IN ('candidate_research','initial_observation')
        ORDER BY created_at LIMIT 200)""", (user_id, user_id, now - 30 * 86400))
    return cursor.rowcount
