"""Resolve an explicit explanation target from the owner's persisted evidence.

No collection, inference, notification delivery, or trading occurs here. The
ordinary chat estimate/job/ledger remains the only paid dispatch path. UI text
is never accepted as portfolio evidence and old model prose is never promoted
to a new factual source.
"""
from contextlib import closing
import json
import time
import zlib
from datetime import datetime, timezone

from fastapi import HTTPException

try:
    from . import app as backend, volume_state as state
    from .volume_contract import digest, source
except ImportError:
    import app as backend
    import volume_state as state
    from volume_contract import digest, source


MAX_FACTS = 40
MODEL_INSTRUCTION = """
explanation_context указывает выбранный пользователем объект и связанные facts.
Объясни простыми словами именно этот объект: что проверено, почему это важно,
чего не хватает и что стоит проверить дальше. Не называй старый снимок текущим.
Кандидат и пройденные ограничения не являются рекомендацией или приказом купить.
Историческое событие не доказывает, что риск сохраняется сейчас; сравни его с
текущими фактами. Тексты уведомлений и прежние ответы модели не являются фактами.
Факт о сохранённой проверке подтверждает только результат этой проверки, а не
будущую доходность, исполнение сделки или безопасность актива.
"""
_PRIVATE_FIELDS = {"account_id", "account_ids", "user_id", "broker_key", "snapshot_id"}


def _value(value):
    """Strip local account/binding identifiers from the provider's fact values."""
    if isinstance(value, dict):
        return {key: _value(item) for key, item in value.items() if key not in _PRIVATE_FIELDS}
    if isinstance(value, list):
        return [_value(item) for item in value]
    return value


def _fact(kind, identifier, value, sources, observed):
    return {"id": "explanation:" + kind + ":" + digest(identifier), "value": _value(value),
            "source_ids": list(dict.fromkeys(sources)), "as_of": observed}


def _analysis(db, user_id, identifier, snapshot):
    row = db.execute("""SELECT f.snapshot_id,f.facts_blob,f.as_of FROM workspace_analysis_facts f
        JOIN insight_cards c ON c.id=f.card_id AND c.user_id=f.user_id
        WHERE f.user_id=? AND f.card_id=?""", (user_id, identifier)).fetchone()
    if row is None:
        raise HTTPException(409, "chat_explanation_analysis_facts_unavailable")
    stored = json.loads(zlib.decompress(row["facts_blob"]))
    facts = [_fact("analysis", identifier + ":" + item["id"],
                   {"observation": item["value"], "basis": "stored_analysis_observation",
                    "same_snapshot_as_current": row["snapshot_id"] == snapshot["snapshot_id"]},
                   item.get("source_ids", []), item.get("as_of") or row["as_of"])
             for item in stored[:MAX_FACTS]]
    return facts, {"included": len(facts), "total": len(stored), "historical": True}


def _event(db, user_id, identifier):
    row = db.execute("SELECT payload_json FROM workspace_events WHERE user_id=? AND id=?",
                     (user_id, identifier)).fetchone()
    if row is None:
        raise HTTPException(404, "chat_explanation_event_unavailable")
    event = json.loads(row[0])
    value = {key: event.get(key) for key in ("kind", "title", "details", "instrument_uids", "occurred_at")}
    value["basis"] = "stored_event_not_a_current_risk_assessment"
    refs = event.get("source_ids", [])
    sources = event.get("sources", [])
    return [_fact("event", identifier, value, refs, event.get("occurred_at"))], sources


def prepare(user, snapshot, context, risk, active):
    target = context.get("explanation")
    if target is None:
        return None
    if context.get("mode") != "portfolio" or any(context.get(key) for key in
            ("account_id", "instrument_uid", "event_id", "start", "end")):
        raise HTTPException(422, "chat_explanation_scope_invalid")
    kind, identifier = target["kind"], target["id"]
    user_id = int(user["id"])
    sources, coverage = [], {"included": 1, "total": 1, "historical": False}
    with closing(backend.connect()) as db:
        if kind == "risk":
            item = next((row for row in risk.get("concentrations", [])
                         if row["direction"] + ":" + row["id"] == identifier), None)
            if item is None:
                raise HTTPException(404, "chat_explanation_risk_unavailable")
            value = {key: item.get(key) for key in
                     ("direction", "label", "share_percent", "limit_percent", "breached", "instrument_uids")}
            value["basis"] = "current_portfolio_concentration_against_saved_limits"
            facts = [_fact(kind, identifier, value, item.get("source_ids", []), snapshot["as_of"])]
        elif kind == "notification":
            row = db.execute("""SELECT source_card_id,event_id FROM workspace_notification_outbox
                WHERE user_id=? AND id=?""", (user_id, identifier)).fetchone()
            if row is None:
                raise HTTPException(404, "chat_explanation_notification_unavailable")
            if row["source_card_id"]:
                facts, coverage = _analysis(db, user_id, row["source_card_id"], snapshot)
            elif row["event_id"]:
                facts, sources = _event(db, user_id, row["event_id"])
                coverage["historical"] = True
            else:
                raise HTTPException(409, "chat_explanation_evidence_unavailable")
        elif kind == "analysis":
            facts, coverage = _analysis(db, user_id, identifier, snapshot)
        elif kind == "document":
            if not identifier.isascii() or not identifier.isdecimal() or len(identifier) > 18:
                raise HTTPException(422, "chat_explanation_target_invalid")
            try:
                from . import osint_read
            except ImportError:
                import osint_read
            item = osint_read.document(backend.connect, int(identifier))
            if item is None:
                raise HTTPException(404, "chat_explanation_document_unavailable")
            observed = datetime.fromtimestamp(item["last_seen"], timezone.utc).isoformat()
            published = datetime.fromtimestamp(item["published_at"], timezone.utc).isoformat() if item["published_at"] else None
            ref = source("saved_publication", str(item["id"]), observed, provider=item["publisher"],
                         url=item["url"], published_at=published, ttl=3600)
            body = item.get("text", "")
            value = {"title": item["title"], "excerpt": body[:6000], "kind": item["kind"],
                     "publisher": item["publisher"], "primary_source": item["primary_source"],
                     "published_at": published, "revision": item["revision_sha"],
                     "basis": "publisher_statement_not_independently_verified_financial_fact",
                     "extraction": item["analysis"].get("extraction"),
                     "issuer_identity_verified": False}
            facts = [_fact(kind, identifier + ":" + item["revision_sha"], value, [ref["id"]], observed)]
            sources = [ref]
            coverage = {"included": min(len(body), 6000), "total": len(body),
                        "unit": "characters", "historical": True, "truncated": len(body) > 6000}
        elif kind == "candidate":
            # This view checks the owner, current broker binding, strategy and
            # evidence revision. It reads persisted records without discovery.
            try:
                from . import autonomous_controller as controller
            except ImportError:
                import autonomous_controller as controller
            discovery = controller._discovery(user, active, int(time.time()))
            item = next((row for row in discovery.get("candidates", [])
                         if row.get("instrument_uid") == identifier), None)
            if item is None:
                raise HTTPException(404, "chat_explanation_candidate_unavailable")
            value = {key: item.get(key) for key in
                     ("instrument_uid", "ticker", "name", "instrument_type", "checks", "missing_evidence",
                      "constraints_passed", "evidence_current", "recommendation_complete", "expires_at")}
            value["basis"] = "persisted_research_checks_not_a_trade_recommendation"
            # Catalogue provenance does not prove the candidate's full checks.
            # The fact states only what the owner's research process recorded.
            facts = [_fact(kind, identifier, value, [], item.get("as_of") or discovery.get("as_of"))]
            coverage["historical"] = item.get("evidence_current") is not True
        else:
            raise HTTPException(422, "chat_explanation_target_invalid")
    if not facts:
        raise HTTPException(409, "chat_explanation_evidence_unavailable")
    return {"target": {"kind": kind, "id": identifier, "fact_ids": [row["id"] for row in facts],
                       "coverage": coverage}, "facts": facts, "sources": sources}
