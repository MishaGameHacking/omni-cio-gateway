"""Reuse autonomous broker observations in the materialized workspace."""
from contextlib import closing
from dataclasses import asdict
from datetime import datetime, timezone
import json
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException

PORTFOLIO_SOURCE = 'GetPortfolio/GetPositions'


try:
    from . import app as backend, volume_state as state, volume_workspace as workspace
    from . import volume_market as market, portfolio_details as details
    from .volume_contract import HTTP_ERRORS, digest, section, safe_section, source, money, decimal, text_number
    from .ai_budget import transaction
except ImportError:
    import app as backend
    import volume_state as state
    import volume_workspace as workspace
    import volume_market as market
    import portfolio_details as details
    from volume_contract import HTTP_ERRORS, digest, section, safe_section, source, money, decimal, text_number
    from ai_budget import transaction

router = APIRouter(prefix="/workspace/analysis", tags=["Monitor evidence"])


def _slot_checks_in(db, user_id: int, now: datetime, check: dict) -> None:
    try:
        from .volume_notifications import _preferences, calendar_gate
    except ImportError:
        from volume_notifications import _preferences, calendar_gate
    preferences, _, _ = _preferences(db, user_id)
    local = now.astimezone(ZoneInfo(preferences["timezone"]))
    row = db.execute("SELECT payload_json FROM workspace_snapshots WHERE user_id=? AND currency='RUB'", (user_id,)).fetchone()
    calendar = (json.loads(row[0]) if row else {}).get("calendar", {})
    market_date = now.astimezone(ZoneInfo("Europe/Moscow")).date().isoformat()
    gate = calendar_gate(calendar, market_date)
    if not preferences["enabled"] or not preferences["briefs_enabled"]:
        gate = "rule_disabled"
    elif gate == "scheduled":
        gate = "due"
    for slot in ("morning", "evening"):
        hour, minute = map(int, preferences[slot].split(":"))
        due = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if not 0 <= (local - due).total_seconds() <= 7200:
            continue
        prior = db.execute("SELECT payload_json FROM workspace_records WHERE user_id=? AND kind='monitor_slot' AND id=?", (user_id, slot)).fetchone()
        previous = json.loads(prior[0]) if prior else {}
        # Later checks in the same window cannot erase an observed completed
        # brief with a routine cooldown. A new date starts a new slot record.
        if previous.get("local_date") == local.date().isoformat() and previous.get("card_id") and previous.get("check_id") != check["check_id"]:
            continue
        observed = {key: check.get(key) for key in ("check_id", "checked_at", "state", "reason", "tier", "card_id", "run_id")}
        if gate != "due":
            observed.update(state="skipped", reason=gate, card_id=None, run_id=None)
        observed.update(slot=slot, scheduled_at=due.astimezone(timezone.utc).isoformat(), timezone=preferences["timezone"],
                        local_date=local.date().isoformat(), gate=gate)
        state.record(db, user_id, "monitor_slot", slot, observed)


@router.get("/checks/{identifier}", responses=HTTP_ERRORS)
def check_detail(identifier: str, user: Annotated[Any, Depends(backend.current_user)]) -> dict:
    with closing(backend.connect()) as db:
        row = db.execute("SELECT payload_json FROM workspace_records WHERE user_id=? AND kind='monitor_check' AND id=?", (int(user["id"]), identifier)).fetchone()
    if row is None:
        raise HTTPException(404, "monitor_check_not_found")
    return json.loads(row[0])


def record_check(user_id: int, now: datetime, *, status: str, reason: str, tier: str,
                 card_id: str | None = None, run_id: str | None = None, error_code: str | None = None,
                 trigger: dict | None = None) -> None:
    """Expose skipped checks without turning them into paid analysis runs."""
    try:
        from .ai_jobs import assert_current_owner_in
        from .monitoring_access import assert_monitoring_access_in
    except ImportError:
        from ai_jobs import assert_current_owner_in
        from monitoring_access import assert_monitoring_access_in
    at = now.astimezone(timezone.utc).isoformat()
    with transaction(backend.connect) as db:
        assert_current_owner_in(db)
        assert_monitoring_access_in(db)
        check = {"check_id": at, "checked_at": at, "state": status, "reason": reason,
            "tier": tier, "card_id": card_id, "run_id": run_id, "error_code": error_code,
            "basis": "server_monitor_policy_decision", "trigger": trigger}
        state.record(db, user_id, "monitor_check", at, check)
        _slot_checks_in(db, user_id, now, check)
        db.execute("""DELETE FROM workspace_records WHERE user_id=? AND kind='monitor_check' AND id NOT IN
            (SELECT id FROM workspace_records WHERE user_id=? AND kind='monitor_check' ORDER BY created_at DESC,id DESC LIMIT 1000)""", (user_id, user_id))


def _observed_positions(raw: dict | None) -> dict:
    return {(account["id"], item["id"]): {"instrument_uid": item["id"], "account_id": account["id"],
                "title": item.get("title") or item["id"], "quantity": text_number(decimal(item.get("quantity"))),
                "value": money(item.get("currentValue"))}
            for account in (raw or {}).get("accounts", []) for item in account.get("positions", [])}


def _position_changes(current: dict, prior: dict, base_ids: list, has_previous: bool) -> list:
    observations = []
    if not has_previous:
        return observations
    for key in sorted(current.keys() | prior.keys()):
        before, after = prior.get(key), current.get(key)
        if (before or {}).get("quantity") == (after or {}).get("quantity"):
            continue
        item = after or before
        observations.append({"id": "position:" + digest(key), "kind": "cash_quantity" if key[1].startswith("cash:") else "position_quantity",
            "title": item["title"], "before": before, "after": after, "instrument_uids": [key[1]], "source_ids": base_ids})
    return observations


def trigger_evidence(user, raw, previous, previous_row, observation: dict, signals, now: datetime) -> dict:
    """Bind policy signals to actual observations, independently of model text."""
    snapshot = observation["snapshot"]
    current = _observed_positions(raw)
    prior = _observed_positions(previous)
    refs = {ref["id"]: ref for ref in snapshot.get("sources", [])}
    prior_ref = None
    if previous_row is not None and previous is not None:
        prior_at = datetime.fromtimestamp(previous_row["created_at"], timezone.utc).isoformat()
        prior_ref = source("portfolio_snapshots", previous_row["digest"], prior_at,
                           provider="Analyst AI: stored T-Invest observation", currency=snapshot["currency"], unit="money", ttl=0)
        refs[prior_ref["id"]] = prior_ref
    current_ids = [ref["id"] for ref in snapshot["sources"] if ref.get("method") in {"GetPortfolio", PORTFOLIO_SOURCE}]
    base_ids = current_ids + ([prior_ref["id"]] if prior_ref else [])
    observations = [{"id": "portfolio_value", "kind": "portfolio_value", "title": "Наблюдаемая стоимость портфеля",
        "before": money((previous or {}).get("totalValue")), "after": money(raw.get("totalValue")),
        "instrument_uids": [], "source_ids": base_ids}]
    observations.extend(_position_changes(current, prior, base_ids, previous is not None))
    for breach in observation["breaches"]:
        observations.append({"id": "limit:" + digest([breach["direction"], breach["id"]]), "kind": "risk_concentration",
            "title": breach["label"], "before": None, "after": breach,
            "instrument_uids": breach["instrument_uids"], "source_ids": breach["source_ids"]})
    with closing(backend.connect()) as db:
        rows = db.execute("SELECT payload_json FROM workspace_events WHERE user_id=? AND snapshot_id=? AND kind LIKE 'risk_%' ORDER BY created_at DESC,id LIMIT 100",
                          (int(user["id"]), snapshot["snapshot_id"])).fetchall()
    for row in rows:
        event = json.loads(row[0])
        refs.update({ref["id"]: ref for ref in event.get("sources", [])})
        observations.append({"id": event["id"], "kind": event["kind"], "title": event["title"],
            "before": event.get("details", {}).get("before"), "after": event.get("details", {}).get("after"),
            "instrument_uids": event.get("instrument_uids", []), "source_ids": event.get("source_ids", [])})
    selected = observations[:80]
    needed = {identifier for item in selected for identifier in item["source_ids"]}
    return {"snapshot_id": snapshot["snapshot_id"], "previous_snapshot_id": previous_row["digest"] if previous_row is not None else None,
            "as_of": snapshot["as_of"], "checked_at": now.astimezone(timezone.utc).isoformat(),
            "comparison_basis": "previous_autonomous_observation", "policy_signals": asdict(signals),
            "observations": selected, "sources": [ref for identifier, ref in refs.items() if identifier in needed],
            "coverage": {"total": len(observations), "included": len(selected), "truncated": len(selected) < len(observations)},
            "first_observation": previous is None}


def ingest(user, raw, now: datetime) -> dict:
    currency = raw.get("currency", "RUB")
    old = state.saved_snapshot(user, currency) or {}
    previous = {(p["account_id"], p["instrument_uid"]): p for p in old.get("positions", [])}
    accounts, metadata = _monitor_accounts(raw, previous)
    normalized = workspace.normalize_snapshot(user, {**raw, "currency": currency, "source_method": PORTFOLIO_SOURCE, "asOf": now.astimezone(timezone.utc).isoformat(), "accounts": accounts}, metadata)
    for key in ("attribution", "payouts", "operations", "events", "news", "calendar", "collection", "event_monitor"):
        if key in old:
            normalized[key] = old[key]
    normalized["section_as_of"] = {key: old.get("section_as_of", {}).get(key, old.get("as_of")) for key in ("attribution", "payouts", "operations", "events") if key in old}
    normalized["sources"] += [r for r in old.get("sources", []) if r.get("method") not in {PORTFOLIO_SOURCE, "GetPortfolio"}]
    # Enrich only the already-configured workspace. This adds no surprise HTTP
    # fanout to a new/disconnected session or deterministic analysis tests.
    if old.get("calendar"):
        def calendar_envelope():
            result = market.calendar(user)
            return section(result, as_of=result["as_of"], sources=[result["source"]])
        normalized["calendar"] = safe_section(calendar_envelope, empty={"exchanges": []})
    if old.get("news"):
        news = safe_section(lambda: details.cached(("workspace-news", *details.identity(user)), 900, lambda: market.load_news(user)), empty={"items": []})
        normalized["news"] = news
        normalized["events"] = {"items": workspace._held_news(normalized, news)}
        normalized["sources"] += news.get("sources", [])
        normalized["section_as_of"]["events"] = news.get("as_of")
    normalized["snapshot_id"] = digest({key: normalized[key] for key in ("positions", "capital", "as_of", "position_coverage")})
    workspace.persist(user, normalized)
    active = state.active_strategy(int(user["id"]))
    exposure = state.exposure_data(normalized, (active or {}).get("config"))
    breaches = [row for row in exposure["concentrations"] if row["breached"]]
    try:
        from .volume_credit import critical
    except ImportError:
        from volume_credit import critical
    credit = [uid for uid, rating in normalized.get("rating_observations", {}).items()
              if critical(rating, old.get("rating_observations", {}).get(uid))]
    fingerprint = digest({"limits": [{k: row[k] for k in ("direction", "id", "share_percent", "limit_percent")} for row in breaches],
                          "credit": normalized.get("rating_signature") if credit else None})
    risk_message = None
    if breaches:
        risk_message = "Превышен подтверждённый лимит: " + breaches[0]["label"]
    elif credit:
        risk_message = "Изменилось проверенное основание кредитного риска"
    return {"snapshot": normalized, "breaches": breaches, "risk_fingerprint": fingerprint, "critical_risk": bool(breaches or credit),
            "risk_message": risk_message,
            "credit_evidence": [{"instrument_uid": uid, **normalized["rating_observations"][uid]} for uid in credit[:40]],
            "credit_coverage": {"critical_instruments": len(credit), "included": min(40, len(credit))},
            "news_fingerprint": digest(sorted(item["id"] for item in normalized.get("events", {}).get("items", [])))}


def _monitor_accounts(raw, previous):
    # Instrument facts are shared by UID; a newly held position on another
    # account must not replace that evidence with an empty account history.
    previous_metadata = {uid: row.get("metadata", {}) for (_, uid), row in previous.items()}
    metadata = {}
    accounts = []
    for account in raw.get("accounts", []):
        positions = []
        for item in account.get("positions", []):
            prior = previous.get((account["id"], item["id"]), {})
            meta = previous_metadata.get(item["id"], {})
            metadata[item["id"]] = {"sector": meta.get("sector"), "countryOfRisk": meta.get("country_of_risk"),
                                    "countryOfRiskName": meta.get("country_of_risk_name"), "assetUid": meta.get("asset_uid"),
                                    "lot": meta.get("lot"), "isin": meta.get("isin"), "exchange": meta.get("exchange"),
                                    "currency": meta.get("instrument_currency"), "_source": meta.get("source")}
            kind = item.get("instrumentType") or ("cash" if item["id"].startswith("cash:") else prior.get("instrument_type"))
            positions.append({**item, "instrumentType": kind,
                              "blocked": item.get("blocked", prior.get("blocked", False)),
                              "blockedQuantity": item.get("blockedQuantity", prior.get("blocked_quantity"))})
        accounts.append({**account, "positions": positions})
    return accounts, metadata
