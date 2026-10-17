"""Materialized financial workspace; all collection is an explicit durable job.

Screen reads do not poll the broker. Financial amounts stay in their original
currency; balance observations are never transformed into OHLC quotations.
"""
from __future__ import annotations

from collections import defaultdict
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
import time
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException

try:
    from . import app as backend, portfolio_details as details, research_store, volume_market as market
    from . import volume_state as state, volume_notifications as notifications
    from .ai_budget import MoneyLedger, transaction
    from .ai_guarded_client import GuardedAIClient, GuardError
    from .ai_policy import AnalysisTier
    from .volume_contract import HTTP_ERRORS, decimal, digest, money, now_iso, source, section, safe_section, date_range, text_number, ZERO, financial_context
except ImportError:
    import app as backend
    import portfolio_details as details
    import research_store
    import volume_market as market
    import volume_state as state
    import volume_notifications as notifications
    from ai_budget import MoneyLedger, transaction
    from ai_guarded_client import GuardedAIClient, GuardError
    from ai_policy import AnalysisTier
    from volume_contract import HTTP_ERRORS, decimal, digest, money, now_iso, source, section, safe_section, date_range, text_number, ZERO, financial_context

router = APIRouter(prefix="/workspace", tags=["Materialized workspace"])


@financial_context
def normalize_snapshot(user: Any, dashboard: dict, metadata: dict | None = None) -> dict:
    currency, observed = dashboard["currency"], dashboard["asOf"]
    metadata = metadata or {}
    sources, rows, cash = [], [], defaultdict(Decimal)
    for account in dashboard.get("accounts", []):
        ref = source(dashboard.get("source_method", "GetPortfolio/GetPositions"), account["id"], observed, currency=currency, unit="money")
        sources.append(ref)
        for position in account.get("positions", []):
            uid = position["id"]
            raw = metadata.get(uid) or {}
            try:
                identity = research_store.latest_verified(backend.connect, "issuer_identity", uid, datetime.now(timezone.utc))
            except (ValueError, TypeError, KeyError):
                identity = None
            value = money(position.get("currentValue"))
            meta_source = raw.get("_source")
            if meta_source and not any(r["id"] == meta_source["id"] for r in sources):
                sources.append(meta_source)
            if identity:
                try:
                    from .volume_contract import reviewed_source
                except ImportError:
                    from volume_contract import reviewed_source
                identity_source = reviewed_source(identity["source"], provider="Reviewed issuer register", method="issuer_identity", subject=uid)
                if not any(r["id"] == identity_source["id"] for r in sources):
                    sources.append(identity_source)
            if position.get("instrumentType") == "cash" and value:
                cash[value["currency"]] += decimal(value)
            rows.append({"instrument_uid": uid, "account_id": account["id"], "account_name": account.get("name"),
                         "title": raw.get("name") or position.get("title") or uid, "ticker": raw.get("ticker") or position.get("ticker"),
                         "instrument_type": position.get("instrumentType"), "quantity": text_number(decimal(position.get("quantity"))),
                         "value": value, "blocked": bool(position.get("blocked")), "blocked_quantity": text_number(decimal(position.get("blockedQuantity"))),
                         "source_ids": [ref["id"]], "verified_identity": identity,
                         "metadata": {"sector": raw.get("sector") or position.get("sector"), "country_of_risk": raw.get("countryOfRisk") or position.get("countryOfRisk"),
                                      "country_of_risk_name": raw.get("countryOfRiskName") or position.get("countryOfRiskName"),
                                      "asset_uid": raw.get("assetUid") or position.get("assetUid"), "lot": raw.get("lot") or position.get("lot"),
                                      "exchange": raw.get("exchange") or position.get("exchange"), "isin": raw.get("isin") or position.get("isin"), "source": meta_source}})
    return {"currency": currency, "as_of": observed, "positions": rows, "sources": sources,
            "accounts": [{"id": a["id"], "name": a.get("name"), "value": money(a.get("totalValue"))} for a in dashboard.get("accounts", [])],
            "capital": {"total": money(dashboard.get("totalValue")), "cash": [money(v, c) for c, v in sorted(cash.items())],
                        "blocked_positions_count": sum(p["blocked"] or (decimal(p.get("blocked_quantity")) or ZERO) != 0 for p in rows),
                        "unvalued_positions_count": sum(p["value"] is None for p in rows)}}


def _balance_interval(user_id: int, accounts: list[str], currency: str, begin: datetime, finish: datetime) -> tuple[dict | None, dict | None]:
    if not accounts:
        return None, None
    with closing(backend.connect()) as db:
        details.ensure_history(db)
        rows = db.execute("""SELECT account_id,observed_at,value FROM portfolio_value_history
            WHERE user_id=? AND currency=? AND observed_at>=? AND observed_at<=?
            GROUP BY account_id,observed_at ORDER BY observed_at""",
            (user_id, currency, begin.isoformat(), finish.isoformat())).fetchall()
    points = defaultdict(dict)
    for row in rows:
        if row["account_id"] in accounts:
            value = decimal(row["value"])
            if value is not None:
                points[row["observed_at"]][row["account_id"]] = value
    complete = [{"at": at, "value": sum(values.values(), ZERO)} for at, values in sorted(points.items()) if set(values) == set(accounts)]
    return (complete[0], complete[-1]) if len(complete) >= 2 else (None, None)


@financial_context
def attribution(user: Any, snapshot: dict, operations: list[dict], complete: bool, begin: datetime, finish: datetime) -> dict:
    currency = snapshot["currency"]
    accounts = [a["id"] for a in snapshot["accounts"]]
    opening, closing = _balance_interval(int(user["id"]), accounts, currency, begin, finish)
    sums, unknown_cash_flow, seen = defaultdict(Decimal), False, set()
    actual_begin = datetime.fromisoformat(opening["at"]) if opening else begin
    actual_end = datetime.fromisoformat(closing["at"]) if closing else finish
    for row in operations:
        key = (row["account_id"], row["id"])
        if key in seen or row.get("state") != "OPERATION_STATE_EXECUTED":
            continue
        seen.add(key)
        when = row.get("date")
        try:
            when = datetime.fromisoformat(when.replace("Z", "+00:00"))
        except (TypeError, ValueError, AttributeError):
            complete = False
            continue
        if not actual_begin < when <= actual_end:
            continue
        amount = money(row.get("payment"))
        category = row["category"]
        if amount:
            sums[category, amount["currency"]] += decimal(amount)
        if category in {"deposits", "withdrawals", "other"} and (amount is None or amount["currency"] != currency or category == "other"):
            unknown_cash_flow = True
    change = closing["value"] - opening["value"] if opening and closing else None
    exact = complete and not unknown_cash_flow and change is not None
    external = sums["deposits", currency] + sums["withdrawals", currency] if exact else None
    return {"start": actual_begin.isoformat(), "end": actual_end.isoformat(),
            "requested_start": begin.isoformat(), "requested_end": finish.isoformat(),
            "opening_value": money(opening["value"], currency) if opening else None,
            "closing_value": money(closing["value"], currency) if closing else None, "change": money(change, currency),
            "external_net_flow": money(external, currency), "residual_after_external_flows": money(change - external, currency) if exact else None,
            "flows": [{"category": category, "amount": money(value, code)} for (category, code), value in sorted(sums.items())],
            "complete": exact, "fx_component": None, "explanation":
                "Остаток после внешних потоков включает переоценку, выплаты, комиссии и валютные изменения; это не точная доходность. Валютная компонента отдельно не определена."
                if exact else "Для точного остатка нужны два синхронных снимка всех счетов и полная история внешних потоков в валюте оценки. Неизвестное не подменяется нулём."}


@financial_context
def _payment_events(user: Any, snapshot: dict, metadata: dict, checkpoint: dict, progress) -> tuple[list[dict], list[dict], bool]:
    rows, sources, complete = [], [], True
    by_uid = defaultdict(list)
    for position in snapshot["positions"]:
        if position["instrument_type"] in {"share", "bond"}:
            by_uid[position["instrument_uid"]].append(position)
    stored = checkpoint.setdefault("payments", {})
    now = datetime.fromisoformat(snapshot["as_of"])
    with details.BrokerReader(user) as reader:
        for index, (uid, held) in enumerate(by_uid.items()):
            progress("collecting_payouts", checkpoint, completed=index, total=len(by_uid))
            kind = held[0]["instrument_type"]
            if uid not in stored:
                method = "coupons" if kind == "bond" else "dividends"
                try:
                    market.pace_instruments(reader.scope)
                    raw = reader.read(method, {"instrumentId": uid, "from": (now - timedelta(days=365)).isoformat(), "to": (now + timedelta(days=365)).isoformat()})
                    stored[uid] = {"data": raw, "as_of": now_iso(), "method": method}
                    progress("collecting_payouts", checkpoint, completed=index + 1, total=len(by_uid))
                except HTTPException:
                    complete = False
                    continue
            raw = stored[uid]
            ref = source(raw["method"], uid, raw["as_of"], ttl=3600)
            sources.append(ref)
            for item in raw["data"].get("events" if kind == "bond" else "dividends", []):
                when = item.get("couponDate") if kind == "bond" else item.get("paymentDate")
                per_unit = money(item.get("payOneBond") if kind == "bond" else item.get("dividendNet"))
                record_date = item.get("fixDate") if kind == "bond" else item.get("recordDate")
                if not when:
                    complete = False
                    continue
                cancelled = str(item.get("dividendType", "")).lower() == "cancelled"
                for position in held:
                    unknown = not record_date or str(record_date)[:10] <= now.date().isoformat()
                    quantity = decimal(position.get("quantity"))
                    amount = money(decimal(per_unit) * quantity, per_unit["currency"]) if per_unit and quantity is not None and quantity > 0 and not unknown and not cancelled else None
                    status = "cancelled" if cancelled else "expected" if amount is not None else "announced"
                    rows.append({"id": digest({"uid": uid, "account": position["account_id"], "event": item}), "instrument_uid": uid,
                                 "account_id": position["account_id"], "title": position["title"], "kind": "coupon" if kind == "bond" else "dividend",
                                 "date": when, "record_date": record_date, "status": status, "amount": amount, "per_unit": per_unit,
                                 "eligibility_unknown": unknown, "source_ids": [ref["id"]], "estimate_is_guaranteed": False})
    return rows, sources, complete


def collect(user: Any, payload: dict, checkpoint: dict, progress) -> dict:
    currency = payload.get("currency", "RUB")
    begin, requested_finish = date_range(date.fromisoformat(payload["start"]) if payload.get("start") else None,
                                         date.fromisoformat(payload["end"]) if payload.get("end") else None)
    if checkpoint.get("broker_key") not in {None, state.broker_key(user)}:
        raise HTTPException(409, "workspace_broker_connection_changed")
    checkpoint["broker_key"] = state.broker_key(user)
    progress("collecting", checkpoint)
    if "dashboard" not in checkpoint:
        checkpoint["dashboard"] = details.load_dashboard(user, currency)
        progress("capital_collected", checkpoint)
    dashboard = checkpoint["dashboard"]
    metadata = checkpoint.setdefault("metadata", {})
    all_positions = [p for a in dashboard["accounts"] for p in a["positions"]]
    market.portfolio_metadata(user, all_positions, metadata, progress, checkpoint)
    # Every position is retained. Identity metadata is resumable rather than
    # silently slicing a large portfolio at the first 100 instruments.
    unique = {p["id"]: p for p in all_positions if p.get("instrumentType") != "cash"}
    for index, (uid, item) in enumerate(unique.items()):
        if uid not in metadata:
            progress("collecting_metadata", checkpoint, completed=index, total=len(unique))
            try:
                metadata[uid] = market.instrument(user, uid)
            except HTTPException:
                metadata[uid] = {"_unavailable": True}
            progress("collecting_metadata", checkpoint, completed=index + 1, total=len(unique))
    snapshot = normalize_snapshot(user, dashboard, metadata)
    snapshot["snapshot_id"] = digest({"capital": snapshot["capital"], "as_of": snapshot["as_of"], "positions": snapshot["positions"]})
    finish = min(requested_finish, datetime.fromisoformat(snapshot["as_of"]))
    operations, operation_sources, operations_complete = [], [], True
    stored_operations = checkpoint.setdefault("operations", {})
    with details.BrokerReader(user) as reader:
        for account in snapshot["accounts"]:
            account_id = account["id"]
            saved = stored_operations.setdefault(account_id, {"items": [], "cursor": "", "complete": False, "pages": 0})
            while not saved["complete"] and saved["pages"] < 200:
                progress("collecting_operations", checkpoint, completed=saved["pages"], total=None)
                raw = reader.read("operations", {"accountId": account_id, "from": begin.isoformat(), "to": finish.isoformat(), "limit": 1000,
                                                  "cursor": saved["cursor"], "withoutCommissions": False, "withoutTrades": False})
                if not isinstance(raw.get("items", []), list):
                    raise HTTPException(502, "operations_response_invalid")
                seen = {item.get("id") for item in saved["items"]}
                for item in raw.get("items", []):
                    if not isinstance(item, dict) or not item.get("id"):
                        raise HTTPException(502, "operation_identity_missing")
                    if item["id"] not in seen:
                        saved["items"].append(details.normalize_operation(item))
                        seen.add(item["id"])
                saved["pages"] += 1
                saved["as_of"] = now_iso()
                if not raw.get("hasNext"):
                    saved["complete"] = True
                else:
                    cursor = str(raw.get("nextCursor") or "")
                    if not cursor or cursor == saved["cursor"]:
                        raise HTTPException(502, "operations_cursor_invalid")
                    saved["cursor"] = cursor
                progress("collecting_operations", checkpoint, completed=saved["pages"], total=None)
            operations_complete &= saved["complete"]
            ref = source("GetOperationsByCursor", account_id, saved.get("as_of", snapshot["as_of"]), ttl=300)
            operation_sources.append(ref)
            for item in saved["items"]:
                operations.append({**item, "account_id": account_id, "source_ids": [ref["id"]],
                                   "position_ref": {"account_id": account_id, "instrument_uid": item.get("instrumentUid"),
                                                    "currently_held": any(p["account_id"] == account_id and p["instrument_uid"] == item.get("instrumentUid") for p in snapshot["positions"])} if item.get("instrumentUid") else None})
    payout_rows, payout_sources, payouts_complete = _payment_events(user, snapshot, metadata, checkpoint, progress)
    for item in operations:
        if item.get("state") == "OPERATION_STATE_EXECUTED" and item.get("category") in {"coupons", "dividends"}:
            payout_rows.append({"id": "received:" + item["account_id"] + ":" + item["id"], "instrument_uid": item.get("instrumentUid"),
                                "account_id": item["account_id"], "title": item["title"], "kind": "coupon" if item["category"] == "coupons" else "dividend",
                                "date": item["date"], "status": "received", "amount": money(item.get("payment")), "per_unit": None,
                                "eligibility_unknown": False, "source_ids": item["source_ids"], "operation_id": item["id"]})
    if "news" not in checkpoint:
        checkpoint["news"] = safe_section(lambda: market.load_news(user), empty={"items": [], "complete": False})
        progress("collecting_news", checkpoint)
    if "calendar" not in checkpoint:
        def calendar_envelope():
            value = market.calendar(user)
            return section(value, as_of=value["as_of"], sources=[value["source"]])
        checkpoint["calendar"] = safe_section(calendar_envelope, empty={"exchanges": []})
        progress("collecting_calendar", checkpoint)
    held = {p["instrument_uid"]: p for p in snapshot["positions"]}
    events = []
    for item in checkpoint["news"].get("data", {}).get("items", []):
        linked = [uid for uid in item.get("instrument_uids", []) if uid in held]
        if linked:
            events.append({**item, "kind": "news", "instrument_uids": linked, "relationship": "broker_link",
                           "held_positions": [{"instrument_uid": uid, "account_id": p["account_id"], "value": p["value"]} for uid in linked for p in snapshot["positions"] if p["instrument_uid"] == uid],
                           "impact_is_inference": True, "impact": None})
    snapshot.update(attribution=attribution(user, snapshot, operations, operations_complete, begin, finish),
                    payouts={"items": sorted(payout_rows, key=lambda r: str(r.get("date")), reverse=True), "complete": payouts_complete and operations_complete,
                             "received_range": {"start": begin.isoformat(), "end": finish.isoformat()}, "announced_and_received_are_distinct": True},
                    operations={"items": operations, "complete": operations_complete, "start": begin.isoformat(), "end": finish.isoformat()},
                    events={"items": events}, news=checkpoint["news"], calendar=checkpoint["calendar"])
    snapshot["sources"] += operation_sources + payout_sources + checkpoint["news"].get("sources", []) + checkpoint["calendar"].get("sources", [])
    snapshot["collection"] = {"all_positions_retained": True, "total_positions": len(all_positions),
                              "metadata_available": sum(not v.get("_unavailable") for v in metadata.values()),
                              "metadata_total": len(unique), "finished_at": now_iso()}
    progress("persisting", checkpoint)
    persist(user, snapshot)
    return {"snapshot_id": snapshot["snapshot_id"], "currency": currency, "as_of": snapshot["as_of"], "collection": snapshot["collection"]}


def persist(user: Any, snapshot: dict) -> None:
    user_id = int(user["id"])
    try:
        from . import volume_credit
    except ImportError:
        import volume_credit
    rating_observations = volume_credit.observations(snapshot)
    rating_signature = volume_credit.signature(rating_observations)
    if snapshot.get("rating_signature") != rating_signature:
        snapshot["snapshot_id"] = digest({"positions": snapshot.get("positions", []), "capital": snapshot.get("capital"),
                                          "as_of": snapshot["as_of"], "rating_signature": rating_signature})
    snapshot["rating_signature"] = rating_signature
    snapshot["rating_observations"] = rating_observations
    snapshot["sources"] = list({r["id"]: r for r in snapshot.get("sources", []) +
                               [ref for observation in rating_observations.values() for ref in observation.get("sources", [])]}.values())
    active = state.active_strategy(user_id)
    current_risk = state.exposure_data(snapshot, (active or {}).get("config"))
    old = state.saved_snapshot(user, snapshot["currency"])
    old_risk = state.exposure_data(old, (active or {}).get("config"))
    old_breaches = {(r["direction"], r["id"]): r for r in (old or {}).get("risk_breaches", old_risk["concentrations"]) if r["breached"]}
    new_breaches = {(r["direction"], r["id"]): r for r in current_risk["concentrations"] if r["breached"]}
    all_current = {(r["direction"], r["id"]): r for r in current_risk["concentrations"]}
    complete_axes = {row["direction"] for row in current_risk["coverage"] if row["state"] == "available"}
    snapshot["risk_breaches"] = list(new_breaches.values())
    snapshot["applied_strategy_version"] = (active or {}).get("version", 0)
    with transaction(backend.connect) as db:
        try:
            from .volume_jobs import assert_current_in
            from .ai_jobs import assert_current_owner_in
            from .monitoring_access import assert_monitoring_access_in
        except ImportError:
            from volume_jobs import assert_current_in
            from ai_jobs import assert_current_owner_in
            from monitoring_access import assert_monitoring_access_in
        assert_current_in(db)
        assert_current_owner_in(db)
        assert_monitoring_access_in(db)
        db.execute("""INSERT INTO workspace_snapshots VALUES (?,?,?,?,?,?)
            ON CONFLICT(user_id,currency) DO UPDATE SET id=excluded.id,broker_key=excluded.broker_key,payload_json=excluded.payload_json,created_at=excluded.created_at""",
            (user_id, snapshot["currency"], snapshot["snapshot_id"], state.broker_key(user), state.encode(snapshot), int(time.time())))
        for key in new_breaches.keys() | old_breaches.keys():
            before, after = old_breaches.get(key), new_breaches.get(key)
            if before is not None and after is not None and before["share_percent"] == after["share_percent"]:
                continue
            details_row = after or before
            # An incomplete aggregate may fall below its limit only because a
            # position lost its valuation/identity. That is not risk resolution.
            missing_basis = after is None and (key[0] not in complete_axes or
                key in all_current and all_current[key]["breached"] is None or
                decimal(snapshot.get("capital", {}).get("total")) in {None, ZERO})
            kind = "risk_limit_observed" if after else "risk_data_stale" if missing_basis else "risk_limit_resolved"
            risk_event = state.event(db, user_id, kind, snapshot["snapshot_id"],
                {"title": ("Превышение лимита: " if after else "Основание риска требует обновления: " if missing_basis else "Лимит восстановлен: ") + details_row["label"],
                 "details": {"before": before, "after": after, "strategy_version": (active or {}).get("version", 0)},
                 "instrument_uids": details_row["instrument_uids"], "source_ids": details_row["source_ids"]},
                snapshot["snapshot_id"] + ":" + ":".join(key))
            notifications.enqueue_in(db, user_id, kind="risk", title=risk_event["title"],
                                     body="Проверьте подтверждённый лимит и актуальность источника; это не выполненная сделка.", event_id=risk_event["id"])
        for item in snapshot.get("events", {}).get("items", []):
            state.event(db, user_id, "market_news", snapshot["snapshot_id"], item, item["id"])
        volume_credit.record_changes_in(db, user_id, snapshot, old)


def ai_data(user: Any) -> dict:
    user_id = int(user["id"])
    with closing(backend.connect()) as db:
        row = db.execute("SELECT * FROM analysis_runs WHERE user_id=? ORDER BY created_at DESC,id DESC LIMIT 1", (user_id,)).fetchone()
        cards = db.execute("SELECT id,title,summary,actions_json,evidence_json,created_at FROM insight_cards WHERE user_id=? ORDER BY created_at DESC,id DESC LIMIT 2", (user_id,)).fetchall()
        checked = db.execute("SELECT payload_json FROM workspace_records WHERE user_id=? AND kind='monitor_check' ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
        check_rows = db.execute("SELECT payload_json FROM workspace_records WHERE user_id=? AND kind='monitor_check' ORDER BY id DESC LIMIT 20", (user_id,)).fetchall()
        slot_rows = db.execute("SELECT payload_json FROM workspace_records WHERE user_id=? AND kind='monitor_slot' ORDER BY id", (user_id,)).fetchall()
        monitor_jobs = db.execute("SELECT id,status,result_json,error_code,created_at,updated_at,cancel_requested_at FROM ai_work_jobs WHERE user_id=? ORDER BY created_at DESC,id DESC LIMIT 20", (user_id,)).fetchall()
    last_check = json.loads(checked[0]) if checked else None
    last = None if not row else {"id": row["id"], "created_at": datetime.fromtimestamp(row["created_at"], timezone.utc).isoformat(),
                                 "state": row["state"], "reason": row["reason"], "tier": row["tier"],
                                 "card_id": last_check.get("card_id") if last_check and last_check.get("run_id") == row["id"] else None}
    current = {"title": cards[0]["title"], "summary": cards[0]["summary"], "actions": json.loads(cards[0]["actions_json"])} if cards else {}
    previous = {"title": cards[1]["title"], "summary": cards[1]["summary"], "actions": json.loads(cards[1]["actions_json"])} if len(cards) > 1 else {}
    diff = {"previous_card_id": cards[1]["id"] if len(cards) > 1 else None, "current_card_id": cards[0]["id"] if cards else None,
            "added": [{"field": k, "value": v} for k, v in current.items() if k not in previous],
            "removed": [{"field": k, "value": v} for k, v in previous.items() if k not in current],
            "changed": [{"field": k, "before": previous[k], "after": v, "source_ids": []} for k, v in current.items() if k in previous and previous[k] != v],
            "unchanged": [{"field": k, "value": v, "source_ids": []} for k, v in current.items() if k in previous and previous[k] == v],
            "scope": "stored_report_fields_and_evidence_records", "fact_comparison_available": False,
            "comparison_limit": "Historical cards do not bind every sentence to stable structured fact IDs; text equality is not proof of unchanged underlying facts."}
    evidence_current = json.loads(cards[0]["evidence_json"]) if cards else []
    evidence_previous = json.loads(cards[1]["evidence_json"]) if len(cards) > 1 else []
    diff["evidence_diff"] = {
        "added": [row for row in evidence_current if row not in evidence_previous],
        "removed": [row for row in evidence_previous if row not in evidence_current],
        "unchanged": [row for row in evidence_current if row in evidence_previous],
        "current_source_ids": sorted({row["source_id"] for row in evidence_current if row.get("source_id")}),
        "previous_source_ids": sorted({row["source_id"] for row in evidence_previous if row.get("source_id")})}
    try:
        from .volume_analysis import comparison
    except ImportError:
        from volume_analysis import comparison
    structured = comparison(user_id, diff["current_card_id"], diff["previous_card_id"])
    diff["structured_facts"] = structured
    diff["fact_comparison_available"] = structured["available"]
    try:
        GuardedAIClient(user_id, backend.connect).check_ready(AnalysisTier.FAST)
        readiness = {"available": True, "reason": None}
    except GuardError as error:
        readiness = {"available": False, "reason": error.code}
    try:
        from .volume_jobs import user_jobs
    except ImportError:
        from volume_jobs import user_jobs
    observed_jobs = [{"job_id": row["id"], "state": "cancelled" if row["error_code"] == "analysis_cancelled" else "cancel_requested" if row["cancel_requested_at"] and row["status"] == "running" else row["status"],
                      "result": json.loads(row["result_json"]) if row["result_json"] else None, "error_code": row["error_code"],
                      "created_at": datetime.fromtimestamp(row["created_at"], timezone.utc).isoformat(),
                      "updated_at": datetime.fromtimestamp(row["updated_at"], timezone.utc).isoformat(), "kind": "scheduled_monitor"} for row in monitor_jobs]
    check_history = []
    for record in check_rows:
        item = json.loads(record[0])
        summary = {key: item.get(key) for key in ("check_id", "checked_at", "state", "reason", "tier", "card_id", "run_id", "error_code")}
        summary["observation_count"] = (item.get("trigger") or {}).get("coverage", {}).get("total", 0)
        check_history.append(summary)
    return {"last_run": last, "last_check": last_check, "check_history": check_history,
            "slot_checks": [json.loads(row[0]) for row in slot_rows], "monitor_jobs": observed_jobs,
            "next_runs": notifications.schedule_slots(user_id), "jobs": user_jobs(user_id),
            "budget": MoneyLedger(backend.connect).user_summary(user_id), "readiness": readiness, "analysis_diff": diff}


@router.get("", responses=HTTP_ERRORS)
def workspace(currency: Literal["RUB", "USD", "EUR"] = "RUB", start: date | None = None, end: date | None = None,
              user: Any = Depends(backend.current_user)) -> dict:
    snapshot = state.saved_snapshot(user, currency)
    observed = (snapshot or {}).get("as_of")
    stale = observed is not None and (datetime.now(timezone.utc) - datetime.fromisoformat(observed)).total_seconds() > 900
    missing = "workspace_refresh_required" if user["tinvest_token_encrypted"] else "tinvest_not_connected"
    base_state = "partial" if stale else "available" if snapshot else "unavailable"
    reason = "snapshot_stale" if stale else None if snapshot else missing
    sections = {}
    for key, empty in (("capital", {"total": None, "cash": []}), ("attribution", {}), ("payouts", {"items": [], "complete": False}), ("events", {"items": []})):
        data = (snapshot or {}).get(key, empty)
        item_state = "partial" if snapshot and data.get("complete") is False else base_state
        section_observed = (snapshot or {}).get("section_as_of", {}).get(key, observed)
        section_stale = section_observed is not None and (datetime.now(timezone.utc) - datetime.fromisoformat(section_observed)).total_seconds() > 900
        if section_stale:
            item_state = "partial"
        sections[key] = section(data, state=item_state, reason="snapshot_stale" if section_stale else reason or ("source_coverage_incomplete" if item_state == "partial" else None), as_of=section_observed, sources=(snapshot or {}).get("sources", []))
    active = state.active_strategy(int(user["id"]))
    exposures = state.exposure_data(snapshot, (active or {}).get("config"))
    exposure_state = "partial" if snapshot and any(not axis["complete"] for axis in exposures["axes"]) else base_state
    sections["exposures"] = section({"axes": exposures["axes"]}, state=exposure_state, reason=reason or ("identity_or_valuation_coverage_incomplete" if exposure_state == "partial" else None), as_of=observed)
    sections["goals"] = section(state.goal_data(user), as_of=observed)
    sections["risks"] = section(state.risk_data(user, currency), state=base_state, reason=reason, as_of=observed)
    sections["ai"] = section(ai_data(user), as_of=now_iso())
    sections["strategy"] = section(state.strategy_data(int(user["id"])), state="available" if active else "not_configured", reason=None if active else "strategy_confirmation_required")
    sections["notifications"] = section(notifications.preferences_data(int(user["id"])), as_of=now_iso())
    return {"schema_version": 1, "snapshot_id": (snapshot or {}).get("snapshot_id"), "as_of": observed, "currency": currency,
            "sections": sections, "sources": (snapshot or {}).get("sources", []), "collection": (snapshot or {}).get("collection"),
            "capabilities": {"read_only_broker": True, "refresh_requires_explicit_job": True, "chat": True,
                             "strategy_confirmation": True, "notification_channel": "app_poll", "push_delivery": False,
                             "frame_network_requests": False}, "requested_range": {"start": str(start) if start else None, "end": str(end) if end else None}}


@router.get("/operations/{account_id}/{operation_id}/position", responses=HTTP_ERRORS)
def operation_position(account_id: str, operation_id: str, user: Any = Depends(backend.current_user)) -> dict:
    snapshot = state.saved_snapshot(user)
    operation = next((row for row in (snapshot or {}).get("operations", {}).get("items", []) if row["account_id"] == account_id and row["id"] == operation_id), None)
    if operation is None:
        raise HTTPException(404, "operation_not_in_workspace")
    uid = operation.get("instrumentUid")
    held = [p for p in (snapshot or {}).get("positions", []) if p["account_id"] == account_id and p["instrument_uid"] == uid]
    return {"operation": operation, "position_ref": operation["position_ref"], "positions": held,
            "relationship": "broker_instrument_uid", "as_of": (snapshot or {}).get("as_of")}
