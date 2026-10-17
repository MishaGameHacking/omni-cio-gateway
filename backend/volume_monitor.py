"""Reuse autonomous broker observations in the materialized workspace."""
from datetime import datetime, timezone

try:
    from . import app as backend, volume_state as state, volume_workspace as workspace
    from . import volume_market as market, portfolio_details as details
    from .volume_contract import digest, section, safe_section
    from .ai_budget import transaction
except ImportError:
    import app as backend
    import volume_state as state
    import volume_workspace as workspace
    import volume_market as market
    import portfolio_details as details
    from volume_contract import digest, section, safe_section
    from ai_budget import transaction


def record_check(user_id: int, now: datetime, *, status: str, reason: str, tier: str,
                 card_id: str | None = None, run_id: str | None = None, error_code: str | None = None) -> None:
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
        state.record(db, user_id, "monitor_check", at, {"checked_at": at, "state": status, "reason": reason,
            "tier": tier, "card_id": card_id, "run_id": run_id, "error_code": error_code,
            "basis": "server_monitor_policy_decision"})
        db.execute("""DELETE FROM workspace_records WHERE user_id=? AND kind='monitor_check' AND id NOT IN
            (SELECT id FROM workspace_records WHERE user_id=? AND kind='monitor_check' ORDER BY created_at DESC,id DESC LIMIT 1000)""", (user_id, user_id))


def ingest(user, raw, now: datetime) -> dict:
    currency = raw.get("currency", "RUB")
    old = state.saved_snapshot(user, currency) or {}
    previous = {(p["account_id"], p["instrument_uid"]): p for p in old.get("positions", [])}
    metadata = {}
    accounts = []
    for account in raw.get("accounts", []):
        positions = []
        for item in account.get("positions", []):
            prior = previous.get((account["id"], item["id"]), {})
            meta = prior.get("metadata", {})
            metadata[item["id"]] = {"sector": meta.get("sector"), "countryOfRisk": meta.get("country_of_risk"),
                                    "countryOfRiskName": meta.get("country_of_risk_name"), "assetUid": meta.get("asset_uid"),
                                    "lot": meta.get("lot"), "isin": meta.get("isin"), "exchange": meta.get("exchange"), "_source": meta.get("source")}
            kind = item.get("instrumentType") or ("cash" if item["id"].startswith("cash:") else prior.get("instrument_type"))
            positions.append({**item, "instrumentType": kind,
                              "blocked": item.get("blocked", prior.get("blocked", False)),
                              "blockedQuantity": item.get("blockedQuantity", prior.get("blocked_quantity"))})
        accounts.append({**account, "positions": positions})
    normalized = workspace.normalize_snapshot(user, {**raw, "currency": currency, "asOf": now.astimezone(timezone.utc).isoformat(), "accounts": accounts}, metadata)
    for key in ("attribution", "payouts", "operations", "events", "news", "calendar", "collection"):
        if key in old:
            normalized[key] = old[key]
    normalized["section_as_of"] = {key: old.get("section_as_of", {}).get(key, old.get("as_of")) for key in ("attribution", "payouts", "operations", "events") if key in old}
    normalized["sources"] += [r for r in old.get("sources", []) if r.get("method") != "GetPortfolio/GetPositions"]
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
        held = {p["instrument_uid"] for p in normalized["positions"]}
        normalized["events"] = {"items": [{**item, "kind": "news", "impact_is_inference": True, "impact": None}
                                         for item in news.get("data", {}).get("items", []) if held.intersection(item.get("instrument_uids", []))]}
        normalized["sources"] += news.get("sources", [])
        normalized["section_as_of"]["events"] = news.get("as_of")
    normalized["snapshot_id"] = digest({"positions": normalized["positions"], "capital": normalized["capital"], "as_of": normalized["as_of"]})
    workspace.persist(user, normalized)
    active = state.active_strategy(int(user["id"]))
    exposure = state.exposure_data(normalized, (active or {}).get("config"))
    breaches = [row for row in exposure["concentrations"] if row["breached"]]
    fingerprint = digest([{k: row[k] for k in ("direction", "id", "share_percent", "limit_percent")} for row in breaches])
    return {"risk_fingerprint": fingerprint, "critical_risk": bool(breaches),
            "risk_message": ("Превышен подтверждённый лимит: " + breaches[0]["label"]) if breaches else None,
            "news_fingerprint": digest(sorted(item["id"] for item in normalized.get("events", {}).get("items", [])))}
