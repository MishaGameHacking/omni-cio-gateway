"""Qualitative event hypotheses over owned positions and inspectable sources.

This module prepares evidence and validates the model's interpretation. It does
not assert a causal price effect, supply market forecasts, or send model calls.
The existing chat job, model router, reservation and recovery path own dispatch.
"""
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

try:
    from . import app as backend, portfolio_details as details, research_store
    from . import volume_market as market
    from .credit_evidence import EvidenceError
    from .ai_guarded_client import GuardError
    from .volume_contract import digest, reviewed_source, timestamp
except ImportError:
    import app as backend
    import portfolio_details as details
    import research_store
    import volume_market as market
    from credit_evidence import EvidenceError
    from ai_guarded_client import GuardError
    from volume_contract import digest, reviewed_source, timestamp


LABEL = "Гипотеза влияния ИИ — не подтверждённый факт"
DIRECTIONS = {"positive", "negative", "mixed", "unknown"}
HORIZONS = {"short_term", "medium_term", "long_term", "unclear"}
CHANNEL_FIELDS = {"mechanism", "direction", "horizon", "assumptions", "uncertainty", "fact_ids"}
MODEL_INSTRUCTION = """
Для impact_request обязательно верни impact_hypothesis:{channels:[{
mechanism:string,direction:'positive'|'negative'|'mixed'|'unknown',
horizon:'short_term'|'medium_term'|'long_term'|'unclear',assumptions:[string],
uncertainty:string,fact_ids:[string]}]} с 1–4 возможными каналами влияния.
Это условная качественная гипотеза: событие → механизм для компании → влияние
на удерживаемый инструмент. Не объявляй механизм доказанным, не придумывай
ценовой эффект, проценты, финансовый прогноз, эмитента или отсутствующий факт.
Каждый канал ссылается на event_fact_id, хотя бы один position_fact_id и на
company_fact_id, когда он подтверждён. Отдели явно названные предпосылки от
источников; если основания недостаточны, direction='unknown', объясни почему.
Весь основной ответ также сохраняет обычные claims, fact_ids и uncertainties.
"""


def _matching_event(items: list, identifier: str, uid: str) -> dict | None:
    return next((item for item in items if item.get("id") == identifier and uid in item.get("instrument_uids", [])), None)


def _event(user: Any, snapshot: dict, identifier: str, uid: str) -> tuple[dict, list]:
    item = _matching_event(snapshot.get("events", {}).get("items", []), identifier, uid)
    sources = snapshot.get("sources", [])
    if item is None:
        # This is an explicit estimate/message request from the event view. It
        # reuses the same bounded news cache as the dossier, never a render loop.
        news = details.cached(("workspace-news", *details.identity(user)), 300, lambda: market.load_news(user))
        item = _matching_event(news.get("data", {}).get("items", []), identifier, uid)
        sources = news.get("sources", [])
    if item is None:
        raise HTTPException(404, "chat_event_not_linked_to_owned_instrument")
    published = item.get("published_at") or item.get("occurred_at")
    try:
        if timestamp(published) > datetime.now(timezone.utc) or not item.get("title"):
            raise ValueError
    except ValueError:
        raise HTTPException(409, "chat_event_publication_basis_required") from None
    all_sources = {ref["id"]: ref for ref in sources + item.get("evidence_sources", [])}
    identifiers = item.get("source_ids", [])
    if not identifiers or any(ref not in all_sources for ref in identifiers):
        raise HTTPException(409, "chat_event_source_records_required")
    return {**item, "published_at": published}, [all_sources[ref] for ref in identifiers]


def _company(uid: str) -> tuple[dict, dict | None, list]:
    company = {"instrument_uid": uid, "issuer_id": None, "issuer_name": None,
               "identity_state": "unavailable", "fact_id": None, "source_ids": []}
    try:
        identity = research_store.latest_verified(backend.connect, "issuer_identity", uid, datetime.now(timezone.utc))
    except EvidenceError:
        identity = None
    if identity is None:
        return company, None, []
    ref = reviewed_source(identity["source"], provider="Reviewed issuer register", method="issuer_identity", subject=uid)
    identifier = "impact:issuer:" + digest(uid)
    company.update(issuer_id=identity["issuer_id"], issuer_name=identity.get("issuer_name"),
                   identity_state="verified", fact_id=identifier, source_ids=[ref["id"]])
    fact = {"id": identifier, "value": {"instrument_uid": uid, "issuer_id": identity["issuer_id"],
            "issuer_name": identity.get("issuer_name"), "basis": "operator_reviewed_issuer_identity"},
            "source_ids": [ref["id"]], "as_of": ref["observed_at"]}
    return company, fact, [ref]


def prepare(user: Any, snapshot: dict, context: dict, selected: list) -> dict | None:
    identifier = context.get("event_id")
    if identifier is None:
        return None
    uid = context.get("instrument_uid")
    if context.get("mode") != "instrument" or not uid or not selected:
        raise HTTPException(422, "chat_event_owned_instrument_context_required")
    item, refs = _event(user, snapshot, identifier, uid)
    company, company_fact, identity_sources = _company(uid)
    event_fact_id = "impact:event:" + digest(identifier)
    event = {"id": identifier, "title": item["title"], "published_at": item["published_at"],
             "fact_id": event_fact_id, "source_ids": list(item["source_ids"]),
             "event_identity_verified": item.get("event_identity_verified") is True,
             "primary_source_verified": bool(item.get("primary_sources"))}
    event_fact = {"id": event_fact_id, "value": {**event, "summary": item.get("summary"),
                  "instrument_uids": [uid], "relationship": "broker_link"},
                  "source_ids": event["source_ids"], "as_of": item["published_at"]}
    positions = [{"instrument_uid": p["instrument_uid"], "account_id": p["account_id"],
                  "account_name": p.get("account_name"), "quantity": p.get("quantity"), "value": p.get("value"),
                  "as_of": snapshot["as_of"], "fact_id": "position:" + str(index), "source_ids": p["source_ids"]}
                 for index, p in enumerate(selected)]
    position_ids = {p["fact_id"] for p in positions}
    sources = {ref["id"]: ref for ref in snapshot.get("sources", []) + refs + identity_sources}
    used = set(event["source_ids"]) | set(company["source_ids"]) | {ref for p in positions for ref in p["source_ids"]}
    if used - sources.keys():
        raise HTTPException(409, "chat_event_source_records_required")
    limitations = ["Канал влияния — условная интерпретация ИИ, а не установленная причинная связь.",
                   "Численный эффект на цену, доходность и вероятность события не рассчитан; торговое поручение не создаётся.",
                   "Позиции и их стоимость относятся к указанному снимку и могли измениться."]
    if company["identity_state"] != "verified":
        limitations.append("Эмитент инструмента не подтверждён; возможный механизм требует дополнительной проверки компании.")
    if not event["primary_source_verified"]:
        limitations.append("Первичный источник публикации не установлен; брокерская связь подтверждает только отнесение новости к инструменту.")
    return {"facts": [event_fact] + ([company_fact] if company_fact else []), "sources": [sources[key] for key in sorted(used)],
            "event": event, "companies": [company], "positions": positions, "limitations": limitations,
            "model_request": {"event_fact_id": event_fact_id, "company_fact_id": company.get("fact_id"),
                              "position_fact_ids": sorted(position_ids), "output_kind": "conditional_qualitative_hypothesis"},
            "snapshot_id": snapshot["snapshot_id"], "as_of": snapshot["as_of"]}


def _text(value: Any, code: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise GuardError(code)
    return value.strip()


def _channel(raw: Any, request: dict, facts: dict) -> dict:
    if not isinstance(raw, dict) or set(raw) != CHANNEL_FIELDS:
        raise GuardError("ai_impact_channel_invalid")
    mechanism = _text(raw["mechanism"], "ai_impact_mechanism_required", 2500)
    uncertainty = _text(raw["uncertainty"], "ai_impact_uncertainty_required", 1500)
    if not isinstance(raw["direction"], str) or not isinstance(raw["horizon"], str) or raw["direction"] not in DIRECTIONS or raw["horizon"] not in HORIZONS:
        raise GuardError("ai_impact_direction_or_horizon_invalid")
    assumptions = raw["assumptions"]
    if not isinstance(assumptions, list) or not 1 <= len(assumptions) <= 6:
        raise GuardError("ai_impact_assumptions_required")
    assumptions = [_text(value, "ai_impact_assumptions_required", 1000) for value in assumptions]
    identifiers = raw["fact_ids"]
    if not isinstance(identifiers, list) or any(not isinstance(value, str) or value not in facts for value in identifiers):
        raise GuardError("ai_impact_fact_not_in_context")
    required = {request["event_fact_id"]}
    if request.get("company_fact_id"):
        required.add(request["company_fact_id"])
    if not required.issubset(identifiers) or not set(request["position_fact_ids"]).intersection(identifiers):
        raise GuardError("ai_impact_event_company_position_chain_required")
    return {"mechanism": mechanism, "direction": raw["direction"], "horizon": raw["horizon"],
            "assumptions": assumptions, "uncertainty": uncertainty, "fact_ids": list(dict.fromkeys(identifiers)),
            "source_ids": sorted({ref for identifier in identifiers for ref in facts[identifier]["source_ids"]})}


def validate(raw: Any, packet: dict) -> dict | None:
    context = packet.get("impact_context")
    if context is None:
        if raw is not None:
            raise GuardError("ai_impact_event_context_required")
        return None
    if not isinstance(raw, dict) or set(raw) != {"channels"} or not isinstance(raw["channels"], list) or not 1 <= len(raw["channels"]) <= 4:
        raise GuardError("ai_impact_hypothesis_required")
    facts = {fact["id"]: fact for fact in packet["facts"]}
    channels = [_channel(row, context["model_request"], facts) for row in raw["channels"]]
    all_sources = {ref["id"]: ref for ref in packet.get("sources", [])}
    used = {ref["id"] for ref in context["sources"]} | {ref for row in channels for ref in row["source_ids"]}
    if used - all_sources.keys():
        raise GuardError("ai_impact_source_not_in_context")
    return {key: context[key] for key in ("event", "companies", "positions", "limitations", "snapshot_id", "as_of")} | {
        "kind": "hypothesis", "label": LABEL, "channels": channels, "computed_financial_impact": None,
        "sources": [all_sources[key] for key in sorted(used)],
        "interpretation": True, "execution_state": "not_executed"}
