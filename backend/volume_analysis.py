"""Structured fact versions behind analysis cards, separate from model prose."""
from contextlib import closing
import json
import zlib
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

try:
    from . import app as backend
    from .volume_contract import HTTP_ERRORS, digest
    from .volume_state import encode
except ImportError:
    import app as backend
    from volume_contract import HTTP_ERRORS, digest
    from volume_state import encode

router = APIRouter(prefix="/workspace/analysis", tags=["Analysis fact versions"])


def initialize() -> None:
    with closing(backend.connect()) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS workspace_analysis_facts (
            card_id TEXT PRIMARY KEY,user_id INTEGER NOT NULL,snapshot_id TEXT NOT NULL,
            facts_blob BLOB NOT NULL,as_of TEXT NOT NULL)""")
        db.commit()


def snapshot_facts(snapshot: dict) -> list[dict]:
    result = []
    def add(key, value, refs, section, identifier):
        result.append({"id": key, "value": value, "source_ids": refs, "as_of": snapshot["as_of"],
                       "highlight": {"section": section, "id": identifier}})
    refs = [r["id"] for r in snapshot.get("sources", []) if r.get("method") in {"GetPortfolio/GetPositions", "GetPortfolio"}]
    add("capital:total:" + snapshot["currency"], snapshot["capital"]["total"], refs, "capital", "total")
    for position in snapshot.get("positions", []):
        key = "position:" + digest({"account_id": position["account_id"], "instrument_uid": position["instrument_uid"]})
        add(key, {"instrument_uid": position["instrument_uid"], "account_id": position["account_id"],
                  "quantity": position.get("quantity"), "value": position.get("value"), "blocked": position.get("blocked"),
                  "blocked_quantity": position.get("blocked_quantity")}, position.get("source_ids", []), "portfolio", position["instrument_uid"])
    for row in snapshot.get("risk_breaches", []):
        add("risk:" + row["direction"] + ":" + row["id"], {k: row[k] for k in ("share_percent", "limit_percent", "breached")}, row["source_ids"], "risks", row["id"])
    for uid, observation in snapshot.get("rating_observations", {}).items():
        for rating in observation.get("data", {}).get("items", []):
            key = "rating:" + digest({k: rating[k] for k in ("agency", "scale", "subject_kind", "subject_id")})
            add(key, {k: rating[k] for k in ("agency", "scale", "subject_kind", "subject_id", "grade", "status", "outlook")},
                [rating["source"]["id"]], "portfolio", uid)
            result[-1]["as_of"] = rating["source"]["checked_at"]
    for item in snapshot.get("events", {}).get("items", []):
        add("event:" + item["id"], {key: item.get(key) for key in ("title", "summary", "occurred_at", "instrument_uids", "relationship")}, item.get("source_ids", []), "events", item["id"])
        result[-1]["as_of"] = snapshot.get("section_as_of", {}).get("events", snapshot["as_of"])
    return result


def capture_in(db, user_id: int, card_id: str) -> None:
    row = db.execute("SELECT id,payload_json FROM workspace_snapshots WHERE user_id=? AND currency='RUB'", (user_id,)).fetchone()
    if row is None:
        return
    snapshot = json.loads(row["payload_json"])
    facts = snapshot_facts(snapshot)
    db.execute("INSERT INTO workspace_analysis_facts VALUES (?,?,?,?,?)", (card_id, user_id, row["id"], zlib.compress(encode(facts).encode(), 6), snapshot["as_of"]))
    db.execute("DELETE FROM workspace_analysis_facts WHERE user_id=? AND card_id NOT IN (SELECT id FROM insight_cards WHERE user_id=?)", (user_id, user_id))


def comparison(user_id: int, current_card: str | None, previous_card: str | None, *, offset: int = 0, limit: int = 20) -> dict:
    if current_card is None:
        return {"available": False, "reason": "analysis_history_empty", "items": [], "counts": {}}
    with closing(backend.connect()) as db:
        current = db.execute("SELECT * FROM workspace_analysis_facts WHERE user_id=? AND card_id=?", (user_id, current_card)).fetchone()
        previous = db.execute("SELECT * FROM workspace_analysis_facts WHERE user_id=? AND card_id=?", (user_id, previous_card)).fetchone() if previous_card else None
    if current is None or previous_card is not None and previous is None:
        return {"available": False, "reason": "legacy_card_without_structured_fact_snapshot", "items": [], "counts": {}}
    now = {r["id"]: r for r in json.loads(zlib.decompress(current["facts_blob"]))}
    old = {r["id"]: r for r in json.loads(zlib.decompress(previous["facts_blob"]))} if previous else {}
    items = []
    counts = {"added": 0, "removed": 0, "changed": 0, "unchanged": 0}
    for identifier in sorted(now.keys() | old.keys()):
        before, after = old.get(identifier), now.get(identifier)
        status = "added" if before is None else "removed" if after is None else "unchanged" if before["value"] == after["value"] else "changed"
        counts[status] += 1
        items.append({"id": identifier, "state": status, "before": before, "after": after,
                      "source_ids": (after or before)["source_ids"],
                      "provenance_changed": before is not None and after is not None and (before["source_ids"] != after["source_ids"] or before["as_of"] != after["as_of"])})
    # Changes are first, while unchanged facts remain available by pagination.
    items.sort(key=lambda item: ({"added": 0, "changed": 1, "removed": 2, "unchanged": 3}[item["state"]], item["id"]))
    selected = items[offset:offset + limit]
    return {"available": True, "reason": None, "current_card_id": current_card, "previous_card_id": previous_card,
            "current_snapshot_id": current["snapshot_id"], "previous_snapshot_id": previous["snapshot_id"] if previous else None,
            "items": selected, "counts": counts, "offset": offset, "total": len(items), "has_more": offset + limit < len(items),
            "basis": "stored_verified_observations_compared_by_stable_fact_identity", "not_a_model_text_comparison": True}


@router.get("/diff", responses=HTTP_ERRORS)
def diff(current_card_id: str, previous_card_id: str | None = None, offset: int = 0, limit: int = 100,
         user: Any = Depends(backend.current_user)) -> dict:
    with closing(backend.connect()) as db:
        for identifier in (current_card_id, previous_card_id):
            if identifier and not db.execute("SELECT 1 FROM insight_cards WHERE user_id=? AND id=?", (int(user["id"]), identifier)).fetchone():
                raise HTTPException(404, "analysis_card_not_found")
    if offset < 0 or not 1 <= limit <= 500:
        raise HTTPException(422, "analysis_diff_page_invalid")
    return comparison(int(user["id"]), current_card_id, previous_card_id, offset=offset, limit=limit)
